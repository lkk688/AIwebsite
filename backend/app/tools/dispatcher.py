import logging
from typing import Any, Callable, Dict, Optional
from .registry import ToolRegistry
from .base import ToolContext

logger = logging.getLogger("jwl.tools.dispatcher")

class ToolDispatcher:
    """
    Central dispatcher for executing tools.
    
    Usage:
      dispatcher = ToolDispatcher(registry)
      dispatcher.register("product_search", handle_product_search)
      ...
      result = dispatcher.dispatch("product_search", {"query": "bags"}, ctx)
    """
    def __init__(self, registry: ToolRegistry):
        self.registry = registry
        self._handlers: Dict[str, Callable] = {}

    def register(self, handler_key: str, handler_func: Callable):
        """
        Register a python function for a specific handler key.
        The handler key corresponds to 'handler' field in chat_config.json tools.
        """
        self._handlers[handler_key] = handler_func

    def dispatch(self, tool_name: str, tool_args: Dict[str, Any], ctx: ToolContext) -> Any:
        """
        Dispatches a tool call to the appropriate handler.
        
        1. Looks up the tool spec in registry to find the 'handler' key.
        2. Looks up the python function for that handler key.
        3. Calls function(ctx, **tool_args).
        """
        # 1. Validate tool existence
        # (The registry usually maps by tool_name)
        # We need to find the tool spec for this tool_name
        # Note: registry._tools is internal, but we can expose a method or access it if needed.
        # registry.get_tool_handlers() returns {tool_name: handler_key}
        
        handler_map = self.registry.get_tool_handlers()
        handler_key = handler_map.get(tool_name)
        
        if not handler_key:
            logger.warning(f"No handler key configured for tool '{tool_name}'")
            return {"error": f"Tool '{tool_name}' not configured with a handler."}

        # [Injection] Inject product context from slots if missing
        # This ensures that even if LLM forgets to pass product_id, we use the one from context
        if tool_name == "send_inquiry":
            if not tool_args.get("product_id") and ctx.slots.get("product_id"):
                tool_args["product_id"] = ctx.slots.get("product_id")
                logger.info(f"Dispatcher: Injected product_id='{tool_args['product_id']}' from slots")
            
            # Also try to find slug or other info? 
            # We assume slots might contain product_slug if we extracted it, but usually we only extract product_id
            if not tool_args.get("product_slug") and ctx.slots.get("product_slug"):
                 tool_args["product_slug"] = ctx.slots.get("product_slug")

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
