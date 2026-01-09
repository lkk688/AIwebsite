import json
from typing import Any, Dict, List, Optional, Tuple, Iterable, Generator

from .settings import settings


def build_send_inquiry_tool_schema_openai() -> List[Dict[str, Any]]:
    # Function tool schema for OpenAI Responses API: type/name/parameters are flattened + strict mode enabled.
    # See OpenAI Function Calling Guide (Responses pattern):
    # https://platform.openai.com/docs/guides/function-calling
    return [{
        "type": "function",
        "name": "send_inquiry",
        "description": "Send a customer inquiry email to the sales team. Use ONLY after the user explicitly confirms sending and provides name/email/message.",
        "strict": True,
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "name": {"type": "string"},
                "email": {"type": "string"},
                "message": {"type": "string"},
            },
            "required": ["name", "email", "message"]
        }
    }]


def build_send_inquiry_tool_schema_litellm() -> List[Dict[str, Any]]:
    # LiteLLM follows the standard Chat Completions API style (function schema nested under "function").
    # See LiteLLM Provider Format:
    # https://docs.litellm.ai/docs/completion/input#tools
    return [{
        "type": "function",
        "function": {
            "name": "send_inquiry",
            "description": "Send a customer inquiry email to the sales team. Use ONLY after the user explicitly confirms sending and provides name/email/message.",
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "name": {"type": "string"},
                    "email": {"type": "string"},
                    "message": {"type": "string"},
                    "locale": {"type": "string", "enum": ["en", "zh"]}
                },
                "required": ["name", "email", "message"]
            }
        }
    }]


class LLMResult:
    def __init__(self, text: str, tool_call: Optional[Dict[str, Any]] = None):
        self.text = text
        self.tool_call = tool_call


class LLMClient:
    def __init__(self):
        self.backend = settings.llm_backend

        if self.backend == "openai":
            from openai import OpenAI
            self.client = OpenAI(
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url,
            )
        else:
            # LiteLLM backend for multi-provider support
            # https://docs.litellm.ai/docs/
            import litellm
            self.litellm = litellm

    def _model_name(self) -> str:
        if self.backend == "litellm" and settings.litellm_model:
            return settings.litellm_model
        return settings.llm_model

    def tools(self) -> List[Dict[str, Any]]:
        return build_send_inquiry_tool_schema_openai() if self.backend == "openai" else build_send_inquiry_tool_schema_litellm()

    def complete(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]], temperature: float = 0.5) -> LLMResult:
        """
        Perform a non-streaming completion call to the LLM.
        
        Args:
            messages: List of message dicts [{"role": "system"|"user"|"assistant", "content": "..."}]
            tools: List of tool definitions
            temperature: Sampling temperature
            
        Returns:
            LLMResult containing text response and optional tool call
        """
        if self.backend == "openai":
            # Recommended approach for OpenAI Responses API: pass message items directly as input.
            # See OpenAI Migration Guide to Responses:
            # https://platform.openai.com/docs/guides/migrate-to-responses
            kwargs = {
                "model": self._model_name(),
                "input": messages,
                #"temperature": temperature, # Note: temperature might not be supported in all Responses API versions yet
            }
            if tools:
                kwargs["tools"] = tools

            resp = self.client.responses.create(**kwargs)
            text = getattr(resp, "output_text", "") or ""
            tool_call = _extract_tool_call_from_openai_response(resp)
            return LLMResult(text=text, tool_call=tool_call)

        # LiteLLM -> Standard Chat Completions API style
        # https://docs.litellm.ai/docs/completion
        resp = self.litellm.completion(
            model=self._model_name(),
            messages=messages,
            tools=tools,
            temperature=temperature,
            api_key=settings.litellm_api_key,
            api_base=settings.litellm_api_base,
        )
        choice = resp["choices"][0]
        msg = choice.get("message", {}) or {}
        text = msg.get("content") or ""
        tool_call = _extract_tool_call_from_litellm_message(msg)
        return LLMResult(text=text, tool_call=tool_call)
    
    def stream(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        temperature: float = 0.5,
    ) -> Iterable[Dict[str, Any]]:
        """
        Perform a streaming completion call to the LLM.

        Yields normalized dict events:
          {"type": "delta", "text": "..."}
          {"type": "tool_call", "name": "send_inquiry", "arguments": {...}}
          {"type": "done"}
        """
        if self.backend == "openai":
            yield from self._stream_openai_responses(messages=messages, tools=tools)
            return

        yield from self._stream_litellm(messages=messages, tools=tools, temperature=temperature)

    # -------------------------------
    # OpenAI Responses Streaming
    # -------------------------------

    def _ev_type(self, ev: Any) -> Optional[str]:
        if isinstance(ev, dict):
            return ev.get("type")
        return getattr(ev, "type", None)

    def _ev_get(self, ev: Any, key: str, default=None):
        """
        Safe getter for both dict events and SDK event objects.
        """
        if isinstance(ev, dict):
            return ev.get(key, default)
        return getattr(ev, key, default)

    def _stream_openai_responses(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
    ) -> Generator[Dict[str, Any], None, None]:
        """
        OpenAI Responses API streaming -> normalized events.

        We accumulate function-call arguments across delta events and emit ONE tool_call at args.done.
        """
        # Fix for 400 Bad Request: "Missing required parameter: 'tools[0].name'"
        # If tools is empty, don't pass it.
        # Also ensure tools format is correct (handled by ToolRegistry).
        kwargs = {
            "model": self._model_name(),
            "input": messages,
            "stream": True,
        }
        if tools:
            kwargs["tools"] = tools

        stream = self.client.responses.create(**kwargs)

        arg_buf: List[str] = []
        last_tool_name: Optional[str] = None
        emitted_tool_call = False

        for ev in stream:
            et = self._ev_type(ev)

            if et == "response.output_text.delta":
                delta = self._ev_get(ev, "delta", "")
                if delta:
                    yield {"type": "delta", "text": delta}
                continue

            # Arguments stream in chunks
            if et == "response.function_call_arguments.delta":
                d = self._ev_get(ev, "delta", "")
                if d:
                    arg_buf.append(d)
                continue

            # Arguments complete -> emit tool_call once
            if et == "response.function_call_arguments.done":
                if emitted_tool_call:
                    continue

                tool_name = self._ev_get(ev, "name", None)
                # ✅ fallback: some SDK/provider cases may not include name
                if not tool_name and tools:
                    tool_name = tools[0].get("name")

                args_str = self._ev_get(ev, "arguments", None)
                if not args_str:
                    args_str = "".join(arg_buf)

                args: Dict[str, Any]
                try:
                    args = json.loads(args_str) if isinstance(args_str, str) and args_str.strip() else {}
                except Exception:
                    args = {"_raw": args_str}

                last_tool_name = tool_name
                emitted_tool_call = True
                yield {"type": "tool_call", "name": last_tool_name, "arguments": args}
                continue

            # Completed
            if et in ("response.completed", "response.done"):
                break

            # Ignore all other event types
            continue

        yield {"type": "done"}

    # -------------------------------
    # LiteLLM Streaming (ChatCompletions style)
    # -------------------------------

    def _stream_litellm(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        temperature: float,
    ) -> Generator[Dict[str, Any], None, None]:
        """
        LiteLLM streaming -> normalized events.

        Note: tool calls are provider-dependent; we attempt best-effort extraction on finish.
        """
        stream = self.litellm.completion(
            model=self._model_name(),
            messages=messages,
            tools=tools,
            temperature=temperature,
            stream=True,
            api_key=settings.litellm_api_key,
            api_base=settings.litellm_api_base,
        )

        final_tool_call = None

        for chunk in stream:
            choice = (chunk.get("choices") or [{}])[0]
            delta = choice.get("delta") or {}

            # Text tokens
            txt = delta.get("content")
            if txt:
                yield {"type": "delta", "text": txt}

            # Some providers stream tool_calls fragments; we skip assembling fragments here.
            # We will extract the final tool call from the final message if present.
            finish = choice.get("finish_reason")
            if finish in ("tool_calls", "stop"):
                msg = choice.get("message") or {}
                final_tool_call = _extract_tool_call_from_litellm_message(msg)

        if final_tool_call:
            yield {
                "type": "tool_call",
                "name": final_tool_call.get("name"),
                "arguments": final_tool_call.get("arguments", {}) or {},
            }

        yield {"type": "done"}

    # def stream(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]], temperature: float = 0.5) -> Iterable[Dict[str, Any]]:
    #     """
    #     Perform a streaming completion call to the LLM.
        
    #     Yields dict events:
    #       {"type": "delta", "text": "..."}
    #       {"type": "tool_call", "name": "send_inquiry", "arguments": {...}}
    #       {"type": "done"}
    #     """
    #     if self.backend == "openai":
    #         # OpenAI Responses API Streaming
    #         # Events: response.output_text.delta, response.function_call_arguments.delta, etc.
    #         # See OpenAI Responses Streaming Reference:
    #         # https://platform.openai.com/docs/api-reference/responses-streaming
    #         stream = self.client.responses.create(
    #             model=self._model_name(),
    #             input=messages,
    #             tools=tools,
    #             #temperature=temperature,
    #             stream=True,
    #         )

    #         arg_buf = ""
    #         tool_name: Optional[str] = None
    #         tool_args: Optional[Dict[str, Any]] = None

    #         for event in stream:
    #             et = getattr(event, "type", None) or (event.get("type") if isinstance(event, dict) else None)

    #             if et == "response.output_text.delta":
    #                 delta = getattr(event, "delta", None) or event.get("delta")
    #                 if delta:
    #                     yield {"type": "delta", "text": delta}

    #             elif et == "response.function_call_arguments.delta":
    #                 d = getattr(event, "delta", None) or event.get("delta")
    #                 if d:
    #                     arg_buf += d

    #             elif et == "response.function_call_arguments.done":
    #                 tool_name = getattr(event, "name", None) or event.get("name")
    #                 args_str = getattr(event, "arguments", None) or event.get("arguments") or arg_buf
    #                 try:
    #                     tool_args = json.loads(args_str) if isinstance(args_str, str) else (args_str or {})
    #                 except Exception:
    #                     tool_args = {"_raw": args_str}

    #                 yield {"type": "tool_call", "name": tool_name, "arguments": tool_args}

    #             elif et == "response.completed":
    #                 # Stream completed
    #                 break

    #         yield {"type": "done"}
    #         return

    #     # LiteLLM Streaming (Standard Chat Completions style)
    #     # https://docs.litellm.ai/docs/completion/stream
    #     stream = self.litellm.completion(
    #         model=self._model_name(),
    #         messages=messages,
    #         tools=tools,
    #         temperature=temperature,
    #         stream=True,
    #         api_key=settings.litellm_api_key,
    #         api_base=settings.litellm_api_base,
    #     )

    #     final_tool_call = None
    #     for chunk in stream:
    #         choice = chunk["choices"][0]
    #         delta = choice.get("delta", {}) or {}

    #         # Text token
    #         if "content" in delta and delta["content"]:
    #             yield {"type": "delta", "text": delta["content"]}

    #         # Tool call (best-effort; behavior varies by provider)
    #         # We accumulate or wait for finish_reason to parse the full tool call
    #         if "tool_calls" in delta and delta["tool_calls"]:
    #             # We don't rely on fragmented tool call assembly here, 
    #             # waiting for the final message/tool_calls is more reliable.
    #             pass

    #         if choice.get("finish_reason") in ("tool_calls", "stop"):
    #             msg = choice.get("message") or {}
    #             final_tool_call = _extract_tool_call_from_litellm_message(msg)

    #     if final_tool_call:
    #         yield {"type": "tool_call", "name": final_tool_call["name"], "arguments": final_tool_call.get("arguments", {})}

    #     yield {"type": "done"}


def _extract_tool_call_from_openai_response(resp: Any) -> Optional[Dict[str, Any]]:
    """
    OpenAI Responses API output is a list of items, which may include a function_call item.
    See OpenAI Responses API Structure:
    https://platform.openai.com/docs/guides/migrate-to-responses
    """
    output = getattr(resp, "output", None)
    if output is None and isinstance(resp, dict):
        output = resp.get("output")

    if not isinstance(output, list):
        return None

    for item in output:
        t = getattr(item, "type", None) or (item.get("type") if isinstance(item, dict) else None)
        if t == "function_call":
            name = getattr(item, "name", None) or item.get("name")
            args = getattr(item, "arguments", None) or item.get("arguments")
            try:
                arguments = json.loads(args) if isinstance(args, str) else (args or {})
            except Exception:
                arguments = {"_raw": args}
            return {"name": name, "arguments": arguments}

    return None


def _extract_tool_call_from_litellm_message(msg: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    tool_calls = msg.get("tool_calls") or []
    if not tool_calls:
        return None
    tc = tool_calls[0]
    fn = tc.get("function") or {}
    name = fn.get("name")
    args = fn.get("arguments")
    try:
        arguments = json.loads(args) if isinstance(args, str) else (args or {})
    except Exception:
        arguments = {"_raw": args}
    return {"name": name, "arguments": arguments}
