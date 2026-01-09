import json
import logging
from typing import Any, Dict, List, Optional, Tuple, Iterable, Generator

from app.core.config import settings

logger = logging.getLogger("jwl.llm")

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
        if self.backend == "litellm" and getattr(settings, "litellm_model", None):
            return settings.litellm_model
        return settings.llm_model

    def _convert_tools_for_litellm(self, tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Converts 'flattened' tool definitions (used by OpenAI Responses API/ToolRegistry in this project)
        to standard OpenAI Chat Completions format (nested 'function' dict) required by LiteLLM.
        
        Input (Flattened):
        { "type": "function", "name": "foo", "parameters": {...} }
        
        Output (Standard):
        { "type": "function", "function": { "name": "foo", "parameters": {...} } }
        """
        if not tools:
            return []
            
        standard_tools = []
        for t in tools:
            if "function" in t:
                # Already standard
                standard_tools.append(t)
            else:
                # Convert flattened to nested
                # Note: LiteLLM/OpenAI Chat Completions usually expect 'name', 'description', 'parameters' inside 'function'
                func_def = {
                    "name": t.get("name"),
                    "parameters": t.get("parameters"),
                }
                if "description" in t:
                    func_def["description"] = t["description"]
                if "strict" in t:
                     # 'strict' is a new OpenAI feature, usually top-level in Responses API but inside function in Chat API?
                     # Actually in new Structured Outputs, it's inside function.
                    func_def["strict"] = t["strict"]
                    
                standard_tools.append({
                    "type": "function",
                    "function": func_def
                })
        return standard_tools

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
            # OpenAI Responses API
            kwargs = {
                "model": self._model_name(),
                "input": messages,
            }
            if tools:
                kwargs["tools"] = tools

            try:
                resp = self.client.responses.create(**kwargs)
                text = getattr(resp, "output_text", "") or ""
                tool_call = _extract_tool_call_from_openai_response(resp)
                return LLMResult(text=text, tool_call=tool_call)
            except Exception as e:
                logger.error(f"OpenAI complete error: {e}")
                raise

        # LiteLLM -> Standard Chat Completions API style
        # https://docs.litellm.ai/docs/completion
        
        # Convert tools to standard format
        std_tools = self._convert_tools_for_litellm(tools)
        
        try:
            resp = self.litellm.completion(
                model=self._model_name(),
                messages=messages,
                tools=std_tools if std_tools else None,
                temperature=temperature,
                api_key=settings.litellm_api_key,
                api_base=settings.litellm_api_base,
            )
            choice = resp["choices"][0]
            msg = choice.get("message", {}) or {}
            text = msg.get("content") or ""
            tool_call = _extract_tool_call_from_litellm_message(msg)
            return LLMResult(text=text, tool_call=tool_call)
        except Exception as e:
            logger.error(f"LiteLLM complete error: {e}")
            raise
    
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

        # LiteLLM
        std_tools = self._convert_tools_for_litellm(tools)
        yield from self._stream_litellm(messages=messages, tools=std_tools, temperature=temperature)

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
        """
        kwargs = {
            "model": self._model_name(),
            "input": messages,
            "stream": True,
        }
        if tools:
            kwargs["tools"] = tools

        try:
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

                if et == "response.function_call_arguments.delta":
                    d = self._ev_get(ev, "delta", "")
                    if d:
                        arg_buf.append(d)
                    continue

                if et == "response.function_call_arguments.done":
                    if emitted_tool_call:
                        continue

                    tool_name = self._ev_get(ev, "name", None)
                    if not tool_name and tools:
                        tool_name = tools[0].get("name")

                    args_str = self._ev_get(ev, "arguments", None)
                    if not args_str:
                        args_str = "".join(arg_buf)

                    args = _parse_json_safe(args_str)

                    last_tool_name = tool_name
                    emitted_tool_call = True
                    yield {"type": "tool_call", "name": last_tool_name, "arguments": args}
                    continue

                if et in ("response.completed", "response.done"):
                    break
                
                continue
        except Exception as e:
            logger.error(f"OpenAI stream error: {e}")
            yield {"type": "error", "message": str(e)}

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
        """
        try:
            stream = self.litellm.completion(
                model=self._model_name(),
                messages=messages,
                tools=tools if tools else None,
                temperature=temperature,
                stream=True,
                api_key=settings.litellm_api_key,
                api_base=settings.litellm_api_base,
            )

            # We need to accumulate tool calls because they might be streamed in fragments
            # (delta.tool_calls[index].function.arguments += chunk)
            # However, simpler approach: wait for finish_reason="tool_calls" and extract from final object if provider supports it,
            # OR accumulate manually.
            # Most LiteLLM providers stream standard chunks.
            
            tool_call_chunks = []
            
            for chunk in stream:
                choice = (chunk.get("choices") or [{}])[0]
                delta = choice.get("delta") or {}

                # Text tokens
                txt = delta.get("content")
                if txt:
                    yield {"type": "delta", "text": txt}

                # Accumulate tool calls if present in delta
                if delta.get("tool_calls"):
                    # Standard OpenAI streaming format:
                    # delta.tool_calls is a list of ToolCallChunk
                    # We might need to handle multiple tool calls or just first one.
                    # For now, let's just buffer it or rely on finish logic if provider supports it.
                    # But actually, 'message' is NOT usually present in chunk choices for streaming, only 'delta'.
                    # So we MUST accumulate if we want to support streaming tool calls properly.
                    for tc in delta.get("tool_calls", []):
                        index = tc.index
                        if len(tool_call_chunks) <= index:
                            tool_call_chunks.append({"name": "", "arguments": ""})
                        
                        fn = tc.function
                        if fn:
                            if fn.name:
                                tool_call_chunks[index]["name"] += fn.name
                            if fn.arguments:
                                tool_call_chunks[index]["arguments"] += fn.arguments

                finish = choice.get("finish_reason")
                if finish in ("tool_calls", "stop", "function_call"):
                    pass

            # After stream ends, emit tool calls if any
            for tc in tool_call_chunks:
                if tc["name"]:
                    args = _parse_json_safe(tc["arguments"])
                    yield {
                        "type": "tool_call",
                        "name": tc["name"],
                        "arguments": args,
                    }

        except Exception as e:
            logger.error(f"LiteLLM stream error: {e}")
            yield {"type": "error", "message": str(e)}

        yield {"type": "done"}


def _parse_json_safe(json_str: str) -> Dict[str, Any]:
    try:
        if isinstance(json_str, str) and json_str.strip():
            return json.loads(json_str)
        return {}
    except Exception:
        return {"_raw": json_str}


def _extract_tool_call_from_openai_response(resp: Any) -> Optional[Dict[str, Any]]:
    """
    OpenAI Responses API output extraction.
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
            arguments = _parse_json_safe(args)
            return {"name": name, "arguments": arguments}

    return None


def _extract_tool_call_from_litellm_message(msg: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    tool_calls = msg.get("tool_calls") or []
    if tool_calls:
        tc = tool_calls[0]
        fn = tc.get("function") or {}
        name = fn.get("name")
        args = fn.get("arguments")
        arguments = _parse_json_safe(args)
        return {"name": name, "arguments": arguments}
        
    # Fallback for older function_call format
    if msg.get("function_call"):
        fc = msg["function_call"]
        name = fc.get("name")
        args = fc.get("arguments")
        arguments = _parse_json_safe(args)
        return {"name": name, "arguments": arguments}
        
    return None
