import json
from typing import Any, Dict, List, Optional, Tuple, Iterable

from .settings import settings


def build_send_inquiry_tool_schema_openai() -> List[Dict[str, Any]]:
    # Responses API 的 function tool schema：type/name/parameters 平铺 + strict
    # 参考 OpenAI function calling guide（Responses 模式）  [oai_citation:2‡OpenAI Platform](https://platform.openai.com/docs/guides/function-calling)
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
    # LiteLLM 走 chat.completions 风格（function schema nested under "function"）
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
            # litellm backend
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
        Non-stream call.
        messages: [{"role":"system"|"user"|"assistant","content":"..."}]
        """
        if self.backend == "openai":
            # Responses API 推荐做法：input 直接传 messages items  [oai_citation:3‡OpenAI Platform](https://platform.openai.com/docs/guides/migrate-to-responses)
            resp = self.client.responses.create(
                model=self._model_name(),
                input=messages,
                tools=tools,
                #temperature=temperature,
            )
            text = getattr(resp, "output_text", "") or ""
            tool_call = _extract_tool_call_from_openai_response(resp)
            return LLMResult(text=text, tool_call=tool_call)

        # litellm -> chat.completions style
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

    def stream(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]], temperature: float = 0.5) -> Iterable[Dict[str, Any]]:
        """
        Yield dict events:
          {"type":"delta","text":"..."}
          {"type":"tool_call","name":"send_inquiry","arguments":{...}}
          {"type":"done"}
        """
        if self.backend == "openai":
            # Responses API streaming events: response.output_text.delta, response.function_call_arguments.*  [oai_citation:4‡OpenAI Platform](https://platform.openai.com/docs/api-reference/responses-streaming)
            stream = self.client.responses.create(
                model=self._model_name(),
                input=messages,
                tools=tools,
                #temperature=temperature,
                stream=True,
            )

            arg_buf = ""
            tool_name: Optional[str] = None
            tool_args: Optional[Dict[str, Any]] = None

            for event in stream:
                et = getattr(event, "type", None) or (event.get("type") if isinstance(event, dict) else None)

                if et == "response.output_text.delta":
                    delta = getattr(event, "delta", None) or event.get("delta")
                    if delta:
                        yield {"type": "delta", "text": delta}

                elif et == "response.function_call_arguments.delta":
                    d = getattr(event, "delta", None) or event.get("delta")
                    if d:
                        arg_buf += d

                elif et == "response.function_call_arguments.done":
                    tool_name = getattr(event, "name", None) or event.get("name")
                    args_str = getattr(event, "arguments", None) or event.get("arguments") or arg_buf
                    try:
                        tool_args = json.loads(args_str) if isinstance(args_str, str) else (args_str or {})
                    except Exception:
                        tool_args = {"_raw": args_str}

                    yield {"type": "tool_call", "name": tool_name, "arguments": tool_args}

                elif et == "response.completed":
                    # end
                    break

            yield {"type": "done"}
            return

        # litellm streaming (chat.completions style)
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
            choice = chunk["choices"][0]
            delta = choice.get("delta", {}) or {}

            # text token
            if "content" in delta and delta["content"]:
                yield {"type": "delta", "text": delta["content"]}

            # tool call (best-effort;不同 provider 行为会有差异)
            if "tool_calls" in delta and delta["tool_calls"]:
                # 这里不强依赖分片拼接，等最终 message/tool_calls 更可靠
                pass

            if choice.get("finish_reason") in ("tool_calls", "stop"):
                msg = choice.get("message") or {}
                final_tool_call = _extract_tool_call_from_litellm_message(msg)

        if final_tool_call:
            yield {"type": "tool_call", "name": final_tool_call["name"], "arguments": final_tool_call.get("arguments", {})}

        yield {"type": "done"}


def _extract_tool_call_from_openai_response(resp: Any) -> Optional[Dict[str, Any]]:
    """
    Responses API output 是 items 数组，可能包含 function_call item。  [oai_citation:5‡OpenAI Platform](https://platform.openai.com/docs/guides/migrate-to-responses)
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