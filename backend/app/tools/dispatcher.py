import logging
from typing import Any, Callable, Dict, Optional
from pydantic import ValidationError

from app.tools.registry import ToolRegistry
from app.tools.base import ToolContext
from app.tools.schemas import create_tool_validator
from app.products.resolve import get_resolver

logger = logging.getLogger("jwl.tools.dispatcher")

class ToolDispatcher:
    """
    Central dispatcher for executing tools.
    """
    def __init__(self, registry: ToolRegistry):
        self.registry = registry
        self._handlers: Dict[str, Callable] = {}

    def register(self, handler_key: str, handler_func: Callable):
        """
        Register a python function for a specific handler key.
        """
        self._handlers[handler_key] = handler_func

    def dispatch(self, tool_name: str, tool_args: Dict[str, Any], ctx: ToolContext) -> Any:
        """
        Dispatches a tool call to the appropriate handler.
        """
        # 1. Validate tool existence
        # We need the spec for validation schema
        tool_spec = self.registry._tools.get(tool_name)
        if not tool_spec:
             logger.warning(f"Tool '{tool_name}' not found in registry.")
             return {"error": f"Tool '{tool_name}' not configured."}

        handler_key = tool_spec.handler
        if not handler_key:
            logger.warning(f"No handler key configured for tool '{tool_name}'")
            return {"error": f"Tool '{tool_name}' not configured with a handler."}

        # [Schema Validation & Resolution]
        try:
            # Special logic for send_inquiry product resolution
            # (Could be generalized if we add a 'requires_product_context' flag to tool spec)
            if tool_name == "send_inquiry":
                # Resolve product info
                resolver = get_resolver()
                
                # STRICT RULE: If we have an active product pinned in context, we MUST use it.
                # This enforces the "anti-drift" rule where the tool call must match the current conversation focus.
                # Even if the LLM generated different args (drift), we override with the pinned product.
                resolved = None
                if ctx.active_product:
                    resolved = resolver.resolve(ctx.active_product.get("id"), ctx.active_product.get("slug"))
                    if resolved:
                        logger.info(f"Dispatcher: Enforcing pinned product {resolved['id']} (overriding any LLM args)")

                # If no active product (or invalid), try to resolve from args
                if not resolved:
                    arg_pid = tool_args.get("product_id")
                    arg_slug = tool_args.get("product_slug")
                    resolved = resolver.resolve(arg_pid, arg_slug)
                
                if resolved:
                    tool_args["product_id"] = resolved["id"]
                    tool_args["product_slug"] = resolved["slug"]
            
            # Dynamic Validation
            # Create validator from spec.parameters (JSON Schema)
            validator_cls = create_tool_validator(tool_name, tool_spec.parameters)
            validated = validator_cls(**tool_args)
            tool_args = validated.model_dump()
                
        except (ValidationError, ValueError) as e:
            cid = ctx.conversation_id if hasattr(ctx, "conversation_id") else "unknown"
            logger.error(f"Tool Validation Failed [cid={cid}]: {tool_name} - {e}")
            return {"error": f"Validation Error: {str(e)}"}

        # 2. Find Python implementation
        func = self._handlers.get(handler_key)
        if not func:
            logger.warning(f"No python implementation registered for handler key '{handler_key}' (tool: {tool_name})")
            return {"error": f"Handler implementation '{handler_key}' missing."}
            
        # 3. Execute
        try:
            return func(ctx, **tool_args)
        except Exception as e:
            logger.error(f"Error executing tool '{tool_name}': {e}", exc_info=True)
            return {"error": str(e)}
