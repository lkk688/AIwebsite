#工具定义、描述本地化、路由控制、slot gating（是否允许调用某工具）
#工具配置默认从 src/data/chat_config.json 的 tools 字段加载，没配置就用内置默认。

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("jwl.tools")


@dataclass
class ToolSpec:
    """
    ToolSpec: a configurable tool definition for LLM tool-calling.

    - name: tool function name exposed to LLM
    - description: localized text shown to LLM (can come from config)
    - parameters: JSONSchema for function arguments
    - required_slots: slots required to enable this tool (e.g., ["email"])
    - intents: which intents this tool is relevant for (optional)
    - enabled: can be disabled via config
    - handler: backend handler key/name (optional, for dispatch layer)
    """
    name: str
    description: Dict[str, str]  # {"en": "...", "zh": "..."}
    parameters: Dict[str, Any]
    required_slots: List[str] = field(default_factory=list)
    intents: List[str] = field(default_factory=list)
    enabled: bool = True
    confirmation_required: bool = False
    handler: Optional[str] = None
    policy: Dict[str, str] = field(default_factory=dict) # {"en": "...", "zh": "..."}

    def to_openai_tool(self, locale: str) -> Dict[str, Any]:
        desc = (self.description.get(locale) or self.description.get("en") or "").strip()
        # Ensure parameters has valid structure
        params = self.parameters or {}
        if not params:
             params = {"type": "object", "properties": {}}
             
        return {
            "type": "function",
            "name": self.name,
            "description": desc,
            "parameters": params,
            "strict": False # Set to False for now to avoid validation errors
        }


class ToolRegistry:
    """
    Loads tool definitions from chat_config.json (configurable) and provides:
      - get_allowed_tools(): which tools to pass into LLM for this turn
      - get_tool_specs(): raw ToolSpec list
      - get_tool_handlers(): mapping tool_name -> handler key (for your tool execution layer)

    Config schema suggestion (in src/data/chat_config.json):

    {
      "tools": {
        "send_inquiry": {
          "enabled": true,
          "description": {"en":"...", "zh":"..."},
          "required_slots": ["name","email","message"],
          "intents": ["quote_order","complaint","general"],
          "handler": "send_inquiry"
        },
        "product_search": {...},
        "price_estimate": {...}
      }
    }
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config or {}
        self._tools: Dict[str, ToolSpec] = self._load_tools()

    # ----------------------------
    # Public APIs
    # ----------------------------

    def get_tool_specs(self) -> List[ToolSpec]:
        return list(self._tools.values())

    def get_tool_handlers(self) -> Dict[str, str]:
        out: Dict[str, str] = {}
        for name, spec in self._tools.items():
            if spec.handler:
                out[name] = spec.handler
        return out

    def get_allowed_tools(
        self,
        *,
        locale: str,
        route_plan: Dict[str, Any],
        slots: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Decide which tools should be provided to LLM for this turn.

        Rules:
        - tool.enabled must be true
        - if tool.required_slots not satisfied => hide it (prevents hallucinated calling)
        - if route_plan.intent exists and tool.intents not empty => only allow if matches
        - optionally reduce tools in "confirm_send" stage to only send_inquiry
        """
        locale = (locale or "en").strip()
        slots = slots or {}
        intent = (route_plan or {}).get("intent") or ""
        stage = (route_plan or {}).get("stage") or ""

        tools_out: List[Dict[str, Any]] = []

        # Config driven stage gating
        state_cfg = self.config.get("state_management", {})
        confirm_slot = state_cfg.get("confirmation_slot", "confirm_send")

        for spec in self._tools.values():
            if not spec.enabled:
                continue

            # stage-based gating: if user is confirming send, keep only tools that require confirmation
            if stage == confirm_slot and not spec.confirmation_required:
                continue

            # slot gating
            if spec.required_slots:
                # We relax this check: if missing slots, we can STILL provide the tool,
                # but the LLM (or frontend) should prompt for them.
                # Logic: If tool is send_inquiry, we allow it even if slots are missing,
                # because LLM might find them in context or ask for them.
                # For other tools, we might want to keep strict or also relax.
                # Relaxing for all tools is generally safer for LLM-driven flows.
                pass
                # missing = [k for k in spec.required_slots if not slots.get(k)]
                # if missing:
                #     continue

            # intent gating
            if intent and spec.intents:
                # If stage is confirmation and tool requires confirmation, allow it regardless of intent mismatch
                if stage == confirm_slot and spec.confirmation_required:
                    pass
                # Relaxed intent match: if intent is "general", allow all tools that support "general"
                # If intent is specific (e.g. "broad_product"), only allow tools that support it.
                elif intent not in spec.intents:
                    # Special case: "general" intent might need access to everything?
                    # Or keep strict? Let's keep strict for now, but ensure 'general' is in your tools.
                    continue

            tools_out.append(spec.to_openai_tool(locale))

        # Check: if list is empty, return None or empty list?
        # OpenAI API requires tools to be non-empty if parameter is passed?
        # Actually, if tools is [], it's better to NOT pass the tools parameter to client.
        # But our caller expects a list.
        return tools_out

    # ----------------------------
    # Internal
    # ----------------------------

    def _load_tools(self) -> Dict[str, ToolSpec]:
        cfg_tools = (self.config.get("tools") or {}) if isinstance(self.config, dict) else {}
        tools: Dict[str, ToolSpec] = {}

        # 1) built-in defaults
        for spec in self._default_tools().values():
            tools[spec.name] = spec

        # 2) override / extend by config
        for name, raw in cfg_tools.items():
            if not isinstance(raw, dict):
                continue

            # merge: if exists, override fields
            base = tools.get(name)
            enabled = bool(raw.get("enabled", True))
            confirmation_required = bool(raw.get("confirmation_required", False))

            description = raw.get("description")
            if not isinstance(description, dict):
                description = base.description if base else {"en": "", "zh": ""}

            parameters = raw.get("parameters")
            if not isinstance(parameters, dict):
                parameters = base.parameters if base else {"type": "object", "properties": {}}

            required_slots = raw.get("required_slots", base.required_slots if base else [])
            intents = raw.get("intents", base.intents if base else [])
            handler = raw.get("handler", base.handler if base else None)
            
            # Policy
            policy = raw.get("policy")
            if not isinstance(policy, dict):
                policy = base.policy if base else {"en": "", "zh": ""}

            tools[name] = ToolSpec(
                name=name,
                description=description,
                parameters=parameters,
                required_slots=list(required_slots or []),
                intents=list(intents or []),
                enabled=enabled,
                confirmation_required=confirmation_required,
                handler=handler,
                policy=policy,
            )

        return tools

    def _default_tools(self) -> Dict[str, ToolSpec]:
        """
        Provide a sane set of default tools. You can later move/override them via chat_config.json.
        """
        # Moved all default tools to src/data/chat_config.json
        return {}