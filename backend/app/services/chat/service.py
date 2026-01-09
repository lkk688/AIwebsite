from __future__ import annotations

import json
import os
import re
import logging
from typing import List, Dict, Any, Optional, Tuple

from app.core.config import settings, BASE_DIR
from app.services.rag.product import build_rag_context, get_product_rag, format_product_context
from app.services.rag.kb import get_kb_rag
from app.services.chat.state import (
    LRUConversationStore,
    update_state_from_messages,
)
from app.tools.registry import ToolRegistry
from app.tools.dispatcher import ToolDispatcher
from app.tools.handlers import handle_product_search, handle_send_inquiry, handle_get_product_details
from app.tools.base import ToolContext
from app.services.chat.router import EmbeddingIntentRouter


logger = logging.getLogger("jwl.chat")


class ChatService:
    """
    Main LLM chat context builder service.
    
    Responsibilities:
      - Manages conversation state (history, summary, slots) via LRU cache.
      - Routes queries to appropriate RAG sources (Product vs KB).
      - Assembles the final prompt for the LLM, including system instructions and context.
      - Supports multi-model configuration (OpenAI, DeepSeek, Qwen, etc.).
    """
    def _format_slots(self, slots: Dict[str, Any], locale: str) -> str:
        """
        Compact conversation slots into a string for LLM injection.
        Only includes stable/useful keys to save tokens.
        Only include key information slots like name/email/quantity/product_id/confirm_send, make LLM remember them.
        """
        if not slots:
            return ""
        
        # Get confirmation slot name from config
        state_cfg = self.config.get("state_management", {})
        confirm_slot = state_cfg.get("confirmation_slot", "confirm_send")
        
        # keep only stable keys
        keep_keys = ["name", "email", "quantity", "product_id", confirm_slot]
        keep = {}
        for k in keep_keys:
            if k in slots and slots[k] not in (None, "", False):
                keep[k] = slots[k]
        if not keep:
            return ""
        title = "对话关键信息(自动提取)" if locale == "zh" else "Conversation Slots (auto-extracted)"
        return f"{title}:\n{json.dumps(keep, ensure_ascii=False)}"

    def __init__(self, data_store, embedder):
        """
        added `embedder` here to support embedding-based intent routing.
        data_store: provides website_info, products, etc.
        embedder: EmbeddingsClient
        """
        self.store = data_store
        self.config = self._load_config()
        self.embedder = embedder

        # In-memory LRU cache (configurable via settings)
        # Used to store conversation state across requests.
        max_items = getattr(settings, "conversation_cache_size", 2000) or 2000
        ttl = getattr(settings, "conversation_cache_ttl_seconds", 24 * 3600) or (24 * 3600)
        self.state_store = LRUConversationStore(max_items=int(max_items), ttl_seconds=int(ttl))

        # tool registry (config-driven)
        self.tool_registry = ToolRegistry(self.config)
        
        # Setup Dispatcher and register handlers
        self.dispatcher = ToolDispatcher(self.tool_registry)
        self.dispatcher.register("product_search", handle_product_search)
        self.dispatcher.register("send_inquiry", handle_send_inquiry)
        self.dispatcher.register("get_product_details", handle_get_product_details)
        # Register price_estimate if implemented
        # self.dispatcher.register("price_estimate", handle_price_estimate)

        # intent router (config-driven; fallback to defaults)
        self.intent_router = EmbeddingIntentRouter(self.embedder, self.config)

    def _load_config(self) -> Dict[str, Any]:
        """
        Loads chat configuration from src/data/chat_config.json.
        This config contains system prompts, keywords, and tool responses.
        """
        config = {
            "system_prompts": {},
            "model_prompts": {},
            "context_keywords": {},
            "tool_responses": {},
            "routing_keywords": {},
            "tools": {},
            "intent_examples": {},
            "intent_mapping": {},
        }
        try:
            project_root = os.path.dirname(BASE_DIR)
            config_path = os.path.join(project_root, "src", "data", "chat_config.json")

            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    if isinstance(loaded, dict):
                        config.update(loaded)
            else:
                logger.warning("chat_config.json not found at %s", config_path)
        except Exception as e:
            logger.error("Failed to load chat_config.json: %s", e)

        return config

    def get_tool_response(self, key: str, locale: str, **kwargs) -> str:
        """
        Retrieves a localized string for tool outputs (e.g. email sent confirmation).
        """
        tool_res = self.config.get("tool_responses", {})
        responses = tool_res.get(locale) or tool_res.get("en") or {}
        text = responses.get(key, "")
        if kwargs:
            try:
                return text.format(**kwargs)
            except Exception:
                return text
        return text

    # ---------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------
    def _incoming_to_dict_messages(self, messages: List[Any]) -> List[Dict[str, str]]:
        """
        Normalizes incoming messages (which might be objects or dicts) into standard dict format.
        """
        out: List[Dict[str, str]] = []
        for m in messages:
            role = getattr(m, "role", None) or (m.get("role") if isinstance(m, dict) else None) or "user"
            text = getattr(m, "text", None) or (m.get("text") if isinstance(m, dict) else None) or ""
            out.append({"role": str(role), "text": str(text)})
        return out

    def _build_rag_query(self, turns: List[Dict[str, str]], max_chars: int = 900) -> str:
        """
        Constructs a search query from the last few turns of conversation.
        """
        user_texts = [t["text"] for t in turns if t.get("role") == "user" and t.get("text")]
        q = " ".join(user_texts[-3:])
        q = q.strip()
        if len(q) > max_chars:
            q = q[-max_chars:]
        return q

    # --------------------------------------------------------------------------
    # Modular Helpers
    # --------------------------------------------------------------------------

    def _check_keywords(self, text: str, keyword_list: List[str]) -> bool:
        """Helper to check if any keyword matches the text."""
        text = (text or "").lower().strip()
        for k in keyword_list:
            # Handle regex patterns (start with \ or contain special chars like \b)
            if "\\" in k or "[" in k:
                try:
                    if re.search(k, text):
                        return True
                except re.error:
                    pass
            else:
                if k in text:
                    return True
        return False

    #changed name from _determine_routing to _determine_routing_keywords
    def _determine_routing_keywords(self, query: str) -> Tuple[bool, bool]:
        """
        Decides on retrieval strategy based on query content.
        Returns: (is_technical, is_broad)
        """
        routing_cfg = self.config.get("routing_keywords", {})
        tech_keys = routing_cfg.get("technical", [])
        broad_keys = routing_cfg.get("broad", [])
        
        is_tech = self._check_keywords(query, tech_keys)
        is_broad = self._check_keywords(query, broad_keys)
        return is_tech, is_broad

    def _get_model_key(self) -> str:
        """
        Determine which model prompt configuration to use.
        Priority:
        1. Explicit `MODEL_TYPE` setting.
        2. Auto-detection from LLM model name.
        3. Default fallback.
        """
        # 1. Explicit override via MODEL_TYPE
        # getattr returns Any, convert to string to avoid Pylint no-member on .lower()
        explicit = str(getattr(settings, "model_type", "default"))
        if explicit and explicit != "default":
            return explicit

        # 2. Auto-detection from model name
        if settings.llm_backend == "litellm":
            # Convert to string to avoid Pylint error
            #model = str(settings.litellm_model or "").lower()
            model = str(getattr(settings, "litellm_model", "") or "").lower()
        else:
            # Convert to string to avoid Pylint error
            #model = str(settings.llm_model or "").lower()
            model = str(getattr(settings, "llm_model", "") or "").lower()
            
        # Fuzzy match against config keys in model_prompts
        model_prompts = self.config.get("model_prompts", {}) or {}
        
        # Check explicit match first
        if model in model_prompts:
            return model
            
        # Check partial match (e.g. "deepseek" in "ollama/deepseek-r1")
        for key in model_prompts.keys():
            if key != "default" and key in model:
                return key
                
        return "default"

    def _build_system_prompt(self, locale: str) -> str:
        """
        Constructs the base system prompt based on the selected model and locale.
        """
        model_key = self._get_model_key()
        prompts_map = self.config.get("model_prompts", {}) or {}

        prompts = None
        v = prompts_map.get(model_key)
        if isinstance(v, dict):
            prompts = v.get(locale)
        if not prompts:
            v = prompts_map.get("default")
            if isinstance(v, dict):
                prompts = v.get(locale)

        if not prompts:
            prompts = (self.config.get("system_prompts", {}) or {}).get(locale) or {}
        if not prompts:
            prompts = (self.config.get("system_prompts", {}) or {}).get("en") or {}

        info = self.store.website_info
        company = (info.get("companyName", {}) or {}).get(locale) or (info.get("companyName", {}) or {}).get("en") or "JWL Travel Gear"

        role = (prompts.get("role") or "").replace("{company}", company)
        strict = prompts.get("strict_policy", "") or ""
        general = prompts.get("general_rules", "") or ""
        output = prompts.get("output_req", "") or ""

        return f"{role}\n\n{strict}\n\n{general}\n\n{output}".strip()

    def _manage_state(self, conversation_id: Optional[str], incoming_msgs: List[Dict[str, str]], locale: str) -> Tuple[List[Dict[str, str]], str, Dict[str, Any]]:
        """
        Updates conversation state (history, summary, slots) and returns the latest view.
        """
        if conversation_id:
            st = self.state_store.get_or_create(conversation_id, locale=locale)
            st = update_state_from_messages(st, incoming_msgs, config=self.config)
            self.state_store.upsert(st)
            return st.recent_turns[:], st.summary or "", st.slots or {}
        return incoming_msgs, "", {}

    def persist_turn(self, conversation_id: str, role: str, content: str, locale: str = "en") -> None:
        """
        Manually append a single turn to the conversation state and persist it.
        Useful for saving assistant responses and tool outputs generated during streaming.
        """
        if not conversation_id:
            return
        
        st = self.state_store.get_or_create(conversation_id, locale=locale)
        
        # Append to recent_turns directly to preserve history
        new_msg = {"role": role, "text": content}
        st.recent_turns.append(new_msg)
        
        # Keep last 20
        if len(st.recent_turns) > 20:
            st.recent_turns = st.recent_turns[-20:]
            
        self.state_store.upsert(st)

    # ---------------------------------------------------------
    # Route Plan (new add)
    # ---------------------------------------------------------
    def _build_route_plan(self, query: str, locale: str, slots: Dict[str, Any]) -> Dict[str, Any]:
        """
        A unified routing plan to control:
          - intent (embedding-based if available)
          - broad/tech flags
          - product_k / kb_k
          - stage (e.g., confirm_send)
        """
        q = (query or "").strip()
        slots = slots or {}
        
        # Load routing configuration
        routing_rules = self.config.get("routing_rules", {})
        strategy = routing_rules.get("strategy", "keyword")
        heuristics = routing_rules.get("heuristics", {})
        rag_allocs = routing_rules.get("rag_allocations", {})
        no_rag_intents = routing_rules.get("no_rag_intents", [])

        # stage
        stage = ""
        # Improved stage detection logic (Config Driven)
        state_cfg = self.config.get("state_management", {})
        confirm_slot = state_cfg.get("confirmation_slot", "confirm_send")
        
        if slots.get(confirm_slot) is True:
            stage = confirm_slot
        elif slots.get("name") and slots.get("email") and (slots.get("message") or slots.get("product_id")):
             pass

        intent = "general"
        intent_score = 0.0
        is_broad = False
        is_tech = False

        # 1) Embedding Router
        intent_res = self.intent_router.route(q)

        if strategy == "embedding":
            # Pure embedding strategy: trust the router primarily
            if intent_res:
                is_broad = intent_res.is_broad
                is_tech = intent_res.is_tech
                intent = intent_res.intent
                intent_score = intent_res.score
            else:
                # Fallback if embedding router yields nothing (e.g. empty query or below min_score)
                intent = "general"
                intent_score = 0.0
                
        else:
            # Keyword/Hybrid Strategy (Legacy behavior)
            if intent_res:
                is_broad = intent_res.is_broad
                is_tech = intent_res.is_tech
                intent = intent_res.intent
                intent_score = intent_res.score
            else:
                # Fallback: keyword-based routing
                is_tech, is_broad = self._determine_routing_keywords(q)
                intent = "general"
                intent_score = 0.0

        # 3) derive k using config
        default_k = rag_allocs.get("default", {"product": 3, "kb": 3})
        prod_k = default_k.get("product", 3)
        kb_k = default_k.get("kb", 3)
        
        # Heuristic: Downgrade intent if score is low (Apply to both strategies to be safe against noise)
        low_score_thresh = heuristics.get("low_score_threshold", 0.45)
        downgrade_list = heuristics.get("downgrade_intents", [])
        
        if intent in downgrade_list and intent_score < low_score_thresh:
             intent = "general" # downgrade intent
             is_broad = False # Reset flags for downgraded intent
             is_tech = False
             
        if is_broad:
            broad_k = rag_allocs.get("broad", {"product": 3, "kb": 1})
            prod_k = broad_k.get("product", 3)
            kb_k = broad_k.get("kb", 1)
        elif is_tech:
            tech_k = rag_allocs.get("tech", {"product": 2, "kb": 3})
            prod_k = tech_k.get("product", 2)
            kb_k = tech_k.get("kb", 3)

        # Force disable RAG for configured intents (e.g., chitchat, context_aware)
        if intent in no_rag_intents:
            prod_k = 0
            kb_k = 0
            # Also clear stage if intent is chitchat to prevent getting stuck in confirmation loops
            if intent == "chitchat":
                stage = ""

        # Keyword-based Short Query Heuristic
        if strategy == "keyword":
            short_len = heuristics.get("short_query_max_len", 15)
            short_keywords = heuristics.get("short_query_keywords", [])
            
            if len(q) < short_len:
                short_q = q.lower()
                # Check for exact word match or substring if configured
                if any(x in short_q for x in short_keywords):
                    # Downgrade to general/action-oriented, skip RAG
                    prod_k = 0
                    kb_k = 0
                    is_broad = False
                    is_tech = False

        # Force disable RAG if downgraded to general with low score/no keywords
        if intent == "general" and not is_broad and not is_tech:
            prod_k = 0
            kb_k = 0

        # [Config Driven] Apply retrieval overrides based on stage
        retrieval_overrides = self.config.get("retrieval_overrides", {})
        stage_overrides = retrieval_overrides.get("on_stage", {}).get(stage)
        if stage_overrides:
            if "product_k" in stage_overrides:
                prod_k = stage_overrides["product_k"]
            if "kb_k" in stage_overrides:
                kb_k = stage_overrides["kb_k"]

        return {
            "intent": intent,
            "intent_score": intent_score,
            "is_broad": is_broad,
            "is_tech": is_tech,
            "product_k": prod_k,
            "kb_k": kb_k,
            "stage": stage,
        }
    
    # ---------------------------------------------------------
    # Retrieval
    # ---------------------------------------------------------

    def build_company_context(self, query: str, locale: str, k: int) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Retrieves Knowledge Base (KB) context.
        
        Args:
            query: The user's query string.
            locale: Language code ('en' or 'zh').
            k: Number of chunks to retrieve.
            
        Returns:
            Tuple of (formatted_context_string, metadata_list_for_logging)
        """
        try:
            if k <= 0:
                return "", []
                
            kb = get_kb_rag()
            # pylint: disable=assignment-from-no-return
            hits = kb.retrieve(query, locale=locale, k=k)
            if not hits:
                return "", []

            parts = []
            hits_meta = []
            for hit in hits:
                parts.append(hit["text"])
                md = hit.get("metadata", {}) or {}
                hits_meta.append({
                    "kb_id": md.get("kb_id"),
                    "lang": md.get("lang"),
                    "source": hit.get("source"),
                    "score": f"{hit.get('score', 0):.4f}",
                    "title": md.get("title", ""),
                    "text_preview": (hit.get("text", "")[:60] + "...") if hit.get("text") else "",
                })

            return "\n---\n".join(parts), hits_meta
        except Exception as e:
            logger.error("KB RAG retrieval failed: %s", e)
            return "", []

    # def _retrieve_context(self, query: str, locale: str, is_tech: bool, is_broad: bool, slots: Dict[str, Any]) -> Tuple[str, str, Dict[str, Any]]:
    #     """
    #     Orchestrates RAG retrieval (Product + KB) based on routing logic.
    #     """
    #     # Logic from original prepare_llm_messages regarding prod_k, kb_k
    #     prod_k = 3
    #     kb_k = 3
    #     if is_broad:
    #         prod_k = 3
    #         kb_k = 1
    #     if is_tech:
    #         prod_k = 2
    #         kb_k = 3
            
    #     rag_info = build_rag_context(query=query, locale=locale, k=prod_k)
    #     prod_ctx = rag_info.get("context", "")
    #     rag_mode = rag_info.get("mode", "none")
        
    #     # Refine routing
    #     if rag_mode == "exact":
    #          # exact product => keep KB minimal unless it's clearly technical
    #          if not is_tech:
    #             kb_k = 0
    #          else:
    #             kb_k = 1
        
    #     # If user is confirming send or has full info, reduce KB context to zero to focus on action
    #     if slots.get("confirm_send") or (slots.get("name") and slots.get("email") and slots.get("product_id")):
    #          kb_k = 0
    #          prod_k = 1

    #     comp_ctx, kb_hits_summary = self.build_company_context(query, locale, k=kb_k)
        
    #     debug_info = {
    #         "rag_mode": rag_mode,
    #         "hits_summary": rag_info.get("hits_summary", []),
    #         "kb_hits": kb_hits_summary
    #     }
    #     return prod_ctx, comp_ctx, debug_info

    #add new route_plan
    def _retrieve_context(
        self,
        query: str,
        locale: str,
        route_plan: Dict[str, Any],
        slots: Dict[str, Any],
    ) -> Tuple[str, str, Dict[str, Any]]:
        """
        Orchestrates RAG retrieval (Product + KB) based on routing plan.
        """
        slots = slots or {}
        prod_k = int(route_plan.get("product_k", 3))
        kb_k = int(route_plan.get("kb_k", 3))

        # product rag
        rag_info = build_rag_context(
            query=query,
            locale=locale,
            k=prod_k,
            #desc_max=120, 
        )
        prod_ctx = rag_info.get("context", "")
        rag_mode = rag_info.get("mode", "none")

        # [Constraint] If we have a selected product and user didn't switch (mode!=exact) and not broad search,
        # we lock context to that product to avoid unrelated search results.
        last_pid = slots.get("product_id")
        if last_pid and rag_mode != "exact" and not route_plan.get("is_broad") and prod_k > 0:
             # Try to fetch the specific product
             try:
                 rag = get_product_rag()
                 p = rag.get_product_by_id(last_pid)
                 if p:
                     # Override RAG context
                     title = "[Current Focus Product]" if locale != "zh" else "[当前聚焦产品]"
                     prod_ctx = format_product_context([p], locale, title_override=title)
                     rag_mode = "context_lock"
                     rag_info["hits_summary"] = [{"id": p.get("id"), "slug": p.get("slug"), "name": str(p.get("name", {}))}]
                     logger.info(f"Context locked to product_id={last_pid}")
             except Exception as e:
                 logger.error(f"Failed to lock context to product {last_pid}: {e}")

        # [Config Driven] Apply RAG mode overrides
        retrieval_overrides = self.config.get("retrieval_overrides", {})
        mode_overrides = retrieval_overrides.get("on_rag_mode", {}).get(rag_mode)
        
        if mode_overrides:
            # Check conditions (unless_flags)
            skip = False
            for flag in mode_overrides.get("unless_flags", []):
                if route_plan.get(flag):
                    skip = True
                    break
            
            if not skip:
                overrides = mode_overrides.get("overrides", {})
                if "kb_k" in overrides:
                    kb_k = overrides["kb_k"]
                if "product_k" in overrides:
                    prod_k = overrides["product_k"]

        comp_ctx, kb_hits_summary = self.build_company_context(query, locale, k=kb_k)

        debug_info = {
            "rag_mode": rag_mode,
            "hits_summary": rag_info.get("hits_summary", []),
            "kb_hits": kb_hits_summary,
        }
        
        logger.info(f"RAG Retrieval: mode={rag_mode} product_hits={len(rag_info.get('hits_summary', []))} kb_hits={len(kb_hits_summary)}")
        
        return prod_ctx, comp_ctx, debug_info

    def _assemble_full_context(self, locale: str, sys_prompt: str, summary: str, slots: Dict[str, Any], prod_ctx: str, comp_ctx: str) -> str:
        """
        Combines system prompt, conversation summary, slots, and RAG context into one text block.
        """
        # Summary
        summary_block = ""
        if summary:
            title = "对话摘要(压缩)" if locale == "zh" else "Conversation Summary (compressed)"
            s = summary.strip()
            if len(s) > 900:
                s = s[-900:]
            summary_block = f"{title}:\n{s}"
            
        # Slots
        slots_block = self._format_slots(slots, locale)
        
        ctx_parts: List[str] = []
        if summary_block:
            ctx_parts.append(summary_block)
        if slots_block:
            ctx_parts.append(slots_block)
        
        if comp_ctx:
            prefix = "公司知识库:\n" if locale == "zh" else "Knowledge Base:\n"
            ctx_parts.append(prefix + comp_ctx)
        
        if prod_ctx:
            ctx_parts.append(prod_ctx)
            
        system_content = sys_prompt
        if ctx_parts:
            system_content += "\n\n[Context]\n" + "\n\n".join(ctx_parts)
            
        return system_content

    def _format_recent_history(self, turns: List[Dict[str, str]], limit: int = 12) -> List[Dict[str, Any]]:
        """
        Formats the recent conversation history for the LLM.
        Maps internal roles ('bot') to LLM roles ('assistant').
        """
        formatted_history: List[Dict[str, Any]] = []
        # only keep recent turns (already compressed)
        for t in turns[-limit:]:
            role = t.get("role", "user")
            if role == "bot":
                role = "assistant"
            if role not in ("system", "user", "assistant"):
                role = "user"
            formatted_history.append({"role": role, "content": t.get("text", "")})
        return formatted_history

    # --------------------------------------------------------------------------
    # Tool Execution
    # --------------------------------------------------------------------------
    def process_tool_call(
        self, 
        tool_name: str, 
        tool_args: Dict[str, Any], 
        ctx: ToolContext, 
        allow_actions: bool = True
    ) -> Dict[str, Any]:
        """
        Orchestrates tool execution with permission checks, logging, and result formatting.
        Returns a standardized execution result:
        {
            "tool_name": str,
            "success": bool,
            "result": Any,
            "ui_action": Optional[str],
            "ui_data": Optional[Dict],
            "system_msg": Optional[str],
            "client_response": Optional[str],
            "skip_reason": Optional[str]
        }
        """
        response = {
            "tool_name": tool_name,
            "tool_args": tool_args,
            "success": False,
            "result": None,
            "ui_action": None,
            "ui_data": None,
            "system_msg": None,
            "client_response": None,
            "skip_reason": None
        }

        # 1. Pre-execution Checks (Specific to sensitive tools)
        if tool_name == "send_inquiry":
            if not allow_actions:
                response["skip_reason"] = "allow_actions=False"
                response["client_response"] = self.get_tool_response("confirm_needed", ctx.locale)
                if hasattr(ctx, "session_logger") and ctx.session_logger:
                    ctx.session_logger.info("TOOL SKIP: allow_actions=False")
                return response

            if not (tool_args.get("name") and tool_args.get("email") and tool_args.get("message")):
                response["skip_reason"] = "missing_fields"
                response["client_response"] = self.get_tool_response("missing_info", ctx.locale)
                if hasattr(ctx, "session_logger") and ctx.session_logger:
                    ctx.session_logger.info("TOOL SKIP: Missing fields")
                return response
                
            # Inject source for tracking
            tool_args["source"] = "chat_tool"

        # 2. Execution
        if hasattr(ctx, "session_logger") and ctx.session_logger:
            ctx.session_logger.info(f"TOOL EXEC: {tool_name} Args: {json.dumps(tool_args, ensure_ascii=False)}")
            
        exec_result = self.dispatcher.dispatch(tool_name, tool_args, ctx)
        response["result"] = exec_result
        
        if hasattr(ctx, "session_logger") and ctx.session_logger:
            # truncate result if too long for logs?
            res_log = json.dumps(exec_result, ensure_ascii=False, default=str)
            if len(res_log) > 2000: res_log = res_log[:2000] + "..."
            ctx.session_logger.info(f"TOOL RETURN: {tool_name} Result: {res_log}")

        # 3. Post-execution Logic & Formatting
        
        # Check for errors
        error_msg = None
        if isinstance(exec_result, dict):
            if exec_result.get("error"):
                error_msg = exec_result.get("error")
            elif "ok" in exec_result and not exec_result["ok"]:
                error_msg = exec_result.get("error", "Unknown error")
        
        if error_msg:
             response["success"] = False
             response["system_msg"] = f"System Notification: Tool '{tool_name}' failed. Error: {error_msg}"
             response["client_response"] = self.get_tool_response("failure", ctx.locale, error=error_msg)
             if tool_name == "send_inquiry":
                 response["ui_action"] = "send_inquiry_failed"
                 response["ui_data"] = {"inquiry_id": exec_result.get("inquiry_id"), "error": error_msg}
             
             if hasattr(ctx, "session_logger") and ctx.session_logger:
                 ctx.session_logger.error(f"TOOL FAIL: {tool_name} Error: {error_msg}")
             return response

        # Success handling
        response["success"] = True
        
        if tool_name == "send_inquiry":
            response["ui_action"] = "send_inquiry"
            response["ui_data"] = {"inquiry_id": exec_result["inquiry_id"], "ses": exec_result.get("ses")}
            response["system_msg"] = f"System Notification: Tool '{tool_name}' executed successfully. Inquiry ID: {exec_result['inquiry_id']}. The email HAS been sent. Please confirm to the user that it is done."
            response["client_response"] = self.get_tool_response("success", ctx.locale)
            if hasattr(ctx, "session_logger") and ctx.session_logger:
                ctx.session_logger.info(f"TOOL SUCCESS: {tool_name} ID={exec_result['inquiry_id']}")
            
        elif tool_name == "product_search":
            count = len(exec_result.get("results", []))
            response["ui_action"] = "product_search"
            response["ui_data"] = exec_result
            response["system_msg"] = f"System Notification: Tool '{tool_name}' returned {count} results. Please summarize or recommend based on these results."
            # client_response is usually handled by LLM text, but for sync API we might want to return something?
            # Sync API uses LLM response.
            
        elif tool_name == "get_product_details":
            # Truncate for context window safety
            res_str = json.dumps(exec_result, ensure_ascii=False)
            if len(res_str) > 6000: res_str = res_str[:6000] + "...(truncated)"
            response["system_msg"] = f"System Notification: Tool '{tool_name}' output: {res_str}"
            
        return response

    # --------------------------------------------------------------------------
    # Main Entry Point
    # --------------------------------------------------------------------------

    def prepare_llm_messages(
        self,
        messages: List[Any],
        locale: str,
        *,
        conversation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Returns {"messages": [...], "tools": [...]}
        Orchestrates the creation of the message list for the LLM.
        
        Steps:
        1. Manage conversation state (update history, slots).
        2. Determine routing (broad vs technical).
        3. Retrieve RAG context (Product + KB).
        4. Select and build system prompt.
        5. Assemble all context into the system message.
        6. Append recent chat history.
        """
        locale = (locale or "en").strip()
        
        # 1. Manage State
        incoming = self._incoming_to_dict_messages(messages)
        turns, conv_summary, slots = self._manage_state(conversation_id, incoming, locale)
        
        # 2. Build Query & Routing
        rag_query = self._build_rag_query(turns)
        plan = self._build_route_plan(rag_query, locale, slots)
        
        # Log route plan for debugging
        logger.info(f"Route Plan: intent={plan.get('intent')} score={plan.get('intent_score'):.2f} stage={plan.get('stage')} is_broad={plan.get('is_broad')} is_tech={plan.get('is_tech')}")

        # 3. Retrieve Context
        # Only retrieve product context if intent is NOT 'quote_order' or 'send_inquiry' related
        # or if we are not in 'confirm_send' stage, to avoid cluttering prompt.
        # But wait, we might need product details for the quote?
        # Let's trust the route_plan k values.
        prod_ctx, comp_ctx, debug_info = self._retrieve_context(rag_query, locale, plan, slots)

        # 4. Build System Prompt
        sys_prompt = self._build_system_prompt(locale)
        
        # 5. Assemble Final System Content
        system_content = self._assemble_full_context(locale, sys_prompt, conv_summary, slots, prod_ctx, comp_ctx)
        
        # 6. Final Messages Construction
        llm_messages: List[Dict[str, Any]] = [{"role": "system", "content": system_content}]
        
        # Append formatted history
        llm_messages.extend(self._format_recent_history(turns))

        # tools (config-driven) New Add
        tools = self.tool_registry.get_allowed_tools(locale=locale, route_plan=plan, slots=slots)
        
        # Dynamic Prompt Construction:
        # Instead of static system prompt, we append policies from allowed tools.
        # 1. Base system prompt (Role, General Rules) - stripped of specific tool policies if possible
        # 2. Append tool policies
        
        # NOTE: Currently _build_system_prompt returns a monolithic string from config.
        # We should ideally refactor config to separate "role" from "policies".
        # For now, we append dynamic policies to the end of system_content.
        
        # Only append tool policies if we actually have tools and intent is not just 'general'/low confidence
        # But wait, if we have tools, we should probably show policies?
        # If tools are empty (Standard Mode), no policies needed.
        if tools:
            tool_specs = self.tool_registry.get_tool_specs() # Get all specs to find policies
            # Filter specs by allowed tools
            allowed_names = {t["name"] for t in tools}
            
            dynamic_policies = []
            for spec in tool_specs:
                if spec.name in allowed_names and spec.policy:
                    p_text = spec.policy.get(locale) or spec.policy.get("en")
                    if p_text:
                        dynamic_policies.append(p_text)
            
            if dynamic_policies:
                system_content += "\n\n[Tool Policies]\n" + "\n\n".join(dynamic_policies)
            
        # Update system message content
        llm_messages[0]["content"] = system_content

        # ---------- debug log ----------
        try:
            logger.info(
                "chat_context locale=%s conv_id=%s intent=%s score=%.3f rag_mode=%s is_broad=%s is_tech=%s stage=%s model_key=%s\n"
                "Summary: %s\nSlots: %s\nProduct Hits: %s\nKB Hits: %s\nTools: %s\nContext Length: %d",
                locale,
                conversation_id,
                plan.get("intent"),
                float(plan.get("intent_score") or 0.0),
                debug_info.get("rag_mode"),
                bool(plan.get("is_broad")),
                bool(plan.get("is_tech")),
                plan.get("stage"),
                self._get_model_key(),
                conv_summary,
                json.dumps(slots, ensure_ascii=False),
                json.dumps(debug_info.get("hits_summary", []), ensure_ascii=False),
                json.dumps(debug_info.get("kb_hits", []), ensure_ascii=False),
                json.dumps([t["function"]["name"] for t in tools], ensure_ascii=False),
                len(system_content),
            )
        except Exception:
            pass
            
        #return llm_messages
        return {"messages": llm_messages, "tools": tools, "slots": slots}
