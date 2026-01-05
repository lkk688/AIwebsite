import json
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, EmailStr

from .settings import settings
from .data_store import DataStore
from .product_search import search_products
from .email_ses import SesMailer
from .llm_client import LLMClient
from .db import init_db, insert_inquiry, mark_inquiry_sent, mark_inquiry_failed
from .embeddings_client import EmbeddingsClient
from .product_rag import init_product_rag
from .kb_rag import init_kb_rag
from .chat_service import ChatService
import logging
import os

def setup_logging():
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )
    # Silence noisy libraries
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("botocore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

setup_logging()
logger = logging.getLogger("jwl.api")

def _get_locale_text(obj: Dict[str, Any], key: str, locale: str) -> str:
    """
    支持字段形态：
    - {"en": "...", "zh": "..."} -> 返回 locale，否则 fallback en
    - ["a", "b"] -> join
    - {"en": [..], "zh":[..]} -> join
    - {"en": {..}, "zh":{..}} -> json stringify
    - 其它 -> str
    """
    v = obj.get(key, None)
    if v is None:
        return ""

    if isinstance(v, dict):
        vv = v.get(locale) or v.get("en")
        if vv is None:
            return ""
        if isinstance(vv, list):
            return "\n".join([str(x) for x in vv if x is not None])
        if isinstance(vv, dict):
            return json.dumps(vv, ensure_ascii=False)
        return str(vv)

    if isinstance(v, list):
        return "\n".join([str(x) for x in v if x is not None])

    return str(v)

app = FastAPI()
init_db()

# Configure CORS (Cross-Origin Resource Sharing)
# https://fastapi.tiangolo.com/tutorial/cors/
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change to your specific domain in production for security
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

store = DataStore(settings.data_dir)
chat_service = ChatService(store)
llm = LLMClient()
embedder = EmbeddingsClient()
init_product_rag(store.products, embedder)
init_kb_rag(embedder)

# Initialize SES Mailer
# Uses boto3 to send emails via AWS SES
# https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ses.html
mailer = SesMailer(
    region=settings.aws_region,
    access_key_id=settings.aws_access_key_id,
    secret_access_key=settings.aws_secret_access_key,
    from_email=settings.ses_from_email,
    to_email=settings.ses_to_email,
    configuration_set=settings.ses_configuration_set,
)



def send_inquiry_with_db_email(name: str, email: str, message: str, source: str, locale: str):
    """
    Process an inquiry:
    1. Write to SQLite database first (persistence).
    2. Attempt to send an email via AWS SES.
    3. Update the database with the send status (success/failure).
    
    Returns a unified structure suitable for the /api/send-email endpoint and the chat tool.
    """
    inquiry_id = insert_inquiry(
        name=name,
        email=email,
        message=message,
        source=source,
        locale=locale,
        meta={"ua": "api"}  # You can also add request headers / IP, etc.
    )

    try:
        # Send email via SES
        ses_resp = mailer.send_inquiry(name, email, message)  # Returns {"messageId": "..."}
        ses_message_id = ses_resp.get("messageId") if isinstance(ses_resp, dict) else None
        mark_inquiry_sent(inquiry_id, ses_message_id or "")
        return {
            "ok": True,
            "inquiry_id": inquiry_id,
            "ses": ses_resp,
            "error": None,
        }
    except Exception as e:
        err = str(e)
        mark_inquiry_failed(inquiry_id, err)
        return {
            "ok": False,
            "inquiry_id": inquiry_id,
            "ses": None,
            "error": err,
        }

def send_inquiry_with_db(name: str, email: str, message: str, source: str, locale: str):
    """
    Process an inquiry (Database Only):
    1. Write to SQLite database.
    2. Does NOT send an email via SES (useful for testing or specific workflows).
    
    Returns a unified structure suitable for the /api/inquiry endpoint.
    """
    try:
        inquiry_id = insert_inquiry(
            name=name,
            email=email,
            message=message,
            source=source,
            locale=locale,
            meta={"ua": "api"}  # You can also add request headers / IP, etc.
        )

        return {
            "ok": True,
            "inquiry_id": inquiry_id,
            "ses": None,
            "error": None,
        }
    except Exception as e:
        return {
            "ok": False,
            "inquiry_id": None,
            "ses": None,
            "error": str(e),
        }


# ----------- Schemas -----------
# Pydantic models for request/response validation
# https://docs.pydantic.dev/latest/

class ChatMessage(BaseModel):
    role: str  # user|assistant|system or your frontend bot
    text: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    locale: str = "en"
    allow_actions: bool = False  # Set to true only after frontend confirmation
    debug: bool = False
    conversation_id: Optional[str] = None  # UUID for state tracking

class ChatResponse(BaseModel):
    response: str
    action: Optional[str] = None
    action_data: Optional[Dict[str, Any]] = None


class EmailRequest(BaseModel):
    name: str
    email: EmailStr
    message: str
    locale: str = "en"




# ----------- APIs -----------

@app.get("/api/health")
async def health():
    """
    Health check endpoint.
    """
    return {"status": "ok", "products_loaded": len(store.products), "llm_backend": settings.llm_backend}


@app.post("/api/send-email")
async def send_email(req: EmailRequest):
    """
    Send an email via SES and record it in the database.
    """
    result = send_inquiry_with_db_email(
        name=req.name,
        email=str(req.email),
        message=req.message,
        source="api/send-email",
        locale=req.locale,
    )

    if result["ok"]:
        return {"status": "success", "inquiry_id": result["inquiry_id"], "ses": result["ses"]}
    else:
        # Do not raise exception here: return failure reason, frontend can prompt user to "try again later/use form"
        return {
            "status": "failed",
            "inquiry_id": result["inquiry_id"],
            "error": result["error"],
        }


@app.post("/api/inquiry")
async def submit_inquiry(req: EmailRequest):
    """
    Submit an inquiry. This endpoint stores the inquiry in the database ONLY.
    It provides a dedicated endpoint for inquiry submission, distinct from the generic send-email.
    """
    result = send_inquiry_with_db(
        name=req.name,
        email=str(req.email),
        message=req.message,
        source="api/inquiry",
        locale=req.locale,
    )

    if result["ok"]:
        return {"status": "success", "inquiry_id": result["inquiry_id"], "ses": result["ses"]}
    else:
        return {
            "status": "failed",
            "inquiry_id": result["inquiry_id"],
            "error": result["error"],
        }

@app.get("/api/products/search")
async def products_search(
    q: str = Query(..., min_length=1),
    locale: str = Query("en"),
    limit: int = Query(8, ge=1, le=50),
):
    """
    Search for products by keyword.
    """
    results = search_products(
        store.products, 
        q, 
        locale=locale, 
        limit=limit,
        semantic=settings.enable_semantic_search,
        lexical_min_score=settings.lexical_min_score_threshold,
        semantic_min_score=settings.semantic_min_score_threshold
    )
    return {"query": q, "count": len(results), "results": results}


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """
    Standard Chat API (Non-streaming).
    Processes user messages, interacts with LLM, and handles tool calls (like sending emails).
    """
    messages = chat_service.prepare_llm_messages(req.messages, req.locale, conversation_id=req.conversation_id)
    #tools = llm.tools()
    tools = llm.tools() if req.allow_actions else []

    try:
        result = llm.complete(messages=messages, tools=tools, temperature=0.6)

        # Tool call guard (execute only if frontend allow_actions=True)
        if result.tool_call and result.tool_call.get("name") == "send_inquiry":
            if not req.allow_actions:
                tip = chat_service.get_tool_response("confirm_needed", req.locale)
                return ChatResponse(response=(result.text + "\n\n" + tip).strip())

            args = result.tool_call.get("arguments", {}) or {}
            name = args.get("name")
            email = args.get("email")
            message = args.get("message")

            if not (name and email and message):
                tip = chat_service.get_tool_response("missing_info", req.locale)
                return ChatResponse(response=(result.text + "\n\n" + tip).strip())

            send_result = send_inquiry_with_db_email(
                name=name,
                email=email,
                message=message,
                source="chat_tool",
                locale=req.locale,
            )

            if send_result["ok"]:
                confirm = chat_service.get_tool_response("success", req.locale)
                return ChatResponse(
                    response=confirm,
                    action="send_inquiry",
                    action_data={"inquiry_id": send_result["inquiry_id"], "ses": send_result["ses"]},
                )
            else:
                # ✅ Critical: Return failure case to ChatResponse
                fail_text = chat_service.get_tool_response("failure", req.locale, error=send_result["error"])
                return ChatResponse(
                    response=fail_text,
                    action="send_inquiry_failed",
                    action_data={"inquiry_id": send_result["inquiry_id"], "error": send_result["error"]},
                )
        return ChatResponse(response=result.text)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest):
    messages = chat_service.prepare_llm_messages(req.messages, req.locale, conversation_id=req.conversation_id)
    tools = llm.tools() if req.allow_actions else []  # ✅ 和 /api/chat 对齐

    # Log Input
    user_input = req.messages[-1].text if req.messages else ""
    logger.info(f"CHAT_STREAM START | Input: '{user_input}' | Tools: {len(tools)} | Locale: {req.locale}")

    def sse(payload: dict):
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")

    def gen():
        pending_tool = None
        assistant_text_chunks = []

        try:
            # Log full prompt for debugging RAG/Hallucinations
            logger.info(f"CHAT_STREAM PROMPT | Messages: {json.dumps(messages, ensure_ascii=False)}")
            
            logger.info("CHAT_STREAM LLM | Connecting to model...")
            for ev in llm.stream(messages=messages, tools=tools, temperature=0.6):
                t = ev.get("type")

                if t == "delta":
                    assistant_text_chunks.append(ev.get("text", ""))
                    yield sse({"type": "delta", "text": ev.get("text", "")})

                elif t == "tool_call":
                    pending_tool = ev
                    logger.info(f"CHAT_STREAM TOOL_DETECTED | Name: {ev.get('name')} | Args: {ev.get('arguments')}")
                    yield sse({
                        "type": "tool_call",
                        "name": ev.get("name"),
                        "arguments": ev.get("arguments", {}),
                    })

                elif t == "done":
                    # ✅ 统一在 done 时输出 final（确保用户看到结果）
                    if pending_tool and pending_tool.get("name") == "send_inquiry":
                        logger.info(f"CHAT_STREAM TOOL_EXEC | Action: send_inquiry")
                        
                        if not req.allow_actions:
                            logger.info("CHAT_STREAM TOOL_SKIP | Reason: allow_actions=False")
                            final_text = chat_service.get_tool_response("confirm_needed", req.locale)
                            yield sse({"type": "final", "text": final_text})
                            yield sse({"type": "done"})
                            return

                        args = pending_tool.get("arguments", {}) or {}
                        name = args.get("name")
                        email = args.get("email")
                        message = args.get("message")

                        if not (name and email and message):
                            logger.info("CHAT_STREAM TOOL_SKIP | Reason: Missing fields")
                            final_text = chat_service.get_tool_response("missing_info", req.locale)
                            yield sse({"type": "final", "text": final_text})
                            yield sse({"type": "done"})
                            return

                        # ✅ 走 DB + SES，并把成功/失败返回给用户
                        send_result = send_inquiry_with_db_email(
                            name=name,
                            email=email,
                            message=message,
                            source="chat_stream_tool",
                            locale=req.locale,
                        )

                        if send_result["ok"]:
                            logger.info(f"CHAT_STREAM TOOL_SUCCESS | InquiryID: {send_result['inquiry_id']}")
                            final_text = chat_service.get_tool_response("success", req.locale)
                            yield sse({
                                "type": "final",
                                "text": final_text,
                                "action": "send_inquiry",
                                "action_data": {"inquiry_id": send_result["inquiry_id"], "ses": send_result["ses"]},
                            })
                        else:
                            logger.error(f"CHAT_STREAM TOOL_FAIL | Error: {send_result['error']}")
                            final_text = chat_service.get_tool_response("failure", req.locale, error=send_result["error"])
                            yield sse({
                                "type": "final",
                                "text": final_text,
                                "action": "send_inquiry_failed",
                                "action_data": {"inquiry_id": send_result["inquiry_id"], "error": send_result["error"]},
                            })

                        yield sse({"type": "done"})
                        return

                    # 没 tool call
                    final_response = "".join(assistant_text_chunks).strip()
                    logger.info(f"CHAT_STREAM COMPLETE | Response: '{final_response[:100]}...'")
                    yield sse({"type": "final", "text": final_response})
                    yield sse({"type": "done"})
                    return

        except GeneratorExit:
            # ✅ 客户端断开会触发；别当错误
            logger.warning("CHAT_STREAM ABORT | Client disconnected")
            return
        except Exception as e:
            logger.exception("CHAT_STREAM ERROR")
            yield sse({"type": "error", "message": str(e)})
            return

    return StreamingResponse(gen(), media_type="text/event-stream")