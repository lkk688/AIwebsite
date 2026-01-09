import json
import time
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, EmailStr

from .settings import settings
from .logging_utils import SessionLogger
from .data_store import DataStore
from .product_search import search_products
from .email_ses import SesMailer
from .llm_client import LLMClient
from .db import init_db, insert_inquiry, mark_inquiry_sent, mark_inquiry_failed
from .embeddings_client import EmbeddingsClient
from .product_rag import init_product_rag
from .kb_rag import init_kb_rag
from .chat_service import ChatService
from .tools.dispatcher import ToolDispatcher
from .tools.base import ToolContext
from .tools.handlers import handle_product_search, handle_send_inquiry, handle_get_product_details
import logging
import os
import time

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
llm = LLMClient()
embedder = EmbeddingsClient()
chat_service = ChatService(store, embedder)
init_product_rag(store.products, embedder)
init_kb_rag(embedder)

# Initialize Tool Dispatcher
dispatcher = ToolDispatcher(chat_service.tool_registry)
dispatcher.register("product_search", handle_product_search)
dispatcher.register("send_inquiry", handle_send_inquiry)
dispatcher.register("get_product_details", handle_get_product_details)

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


@app.post("/api/chat/init")
async def init_chat():
    """
    Triggers initialization of RAG indices (Product, KB) and Intent Router.
    This is called when the chat window opens to ensure low latency for the first message.
    """
    start = time.time()
    logger.info("INIT_CHAT | Starting initialization...")
    
    # 1. Build Intent Router
    try:
        if hasattr(chat_service, "intent_router") and chat_service.intent_router:
            chat_service.intent_router.build()
            logger.info("INIT_CHAT | Intent Router built")
    except Exception as e:
        logger.error(f"INIT_CHAT | Intent Router failed: {e}")

    # 2. Build Product RAG
    try:
        from .product_rag import get_product_rag
        prag = get_product_rag()
        # Check if already built (check internal flag or just call it, it has checks)
        # But build_index() in ProductRAG doesn't have an 'is_built' check, it rebuilds?
        # Let's check ProductRAG code. It sets self._vecs.
        if prag._vecs is None:
            prag.build_index()
            logger.info("INIT_CHAT | Product RAG built")
        else:
            logger.info("INIT_CHAT | Product RAG already ready")
    except Exception as e:
        logger.error(f"INIT_CHAT | Product RAG failed: {e}")

    # 3. Build KB RAG
    try:
        from .kb_rag import get_kb_rag
        krag = get_kb_rag()
        if krag._vecs is None:
            krag.build_index()
            logger.info("INIT_CHAT | KB RAG built")
        else:
             logger.info("INIT_CHAT | KB RAG already ready")
    except Exception as e:
        logger.error(f"INIT_CHAT | KB RAG failed: {e}")

    duration = time.time() - start
    logger.info(f"INIT_CHAT | Complete in {duration:.2f}s")
    return {"status": "ready", "duration": duration}


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
    ctx = ToolContext(store=store, mailer=mailer, locale=req.locale, settings=settings)
    result = handle_send_inquiry(
        ctx,
        name=req.name,
        email=str(req.email),
        message=req.message,
        source="api/send-email"
    )

    if result["ok"]:
        return {"status": "success", "inquiry_id": result["inquiry_id"], "ses": result.get("ses")}
    else:
        return {
            "status": "failed",
            "inquiry_id": result.get("inquiry_id"),
            "error": result.get("error"),
        }


@app.post("/api/inquiry")
async def submit_inquiry(req: EmailRequest):
    """
    Submit an inquiry. This endpoint stores the inquiry in the database ONLY.
    """
    # Pass mailer=None to skip sending email
    ctx = ToolContext(store=store, mailer=None, locale=req.locale, settings=settings)
    result = handle_send_inquiry(
        ctx,
        name=req.name,
        email=str(req.email),
        message=req.message,
        source="api/inquiry"
    )

    if result["ok"]:
        return {"status": "success", "inquiry_id": result["inquiry_id"], "ses": None}
    else:
        return {
            "status": "failed",
            "inquiry_id": result.get("inquiry_id"),
            "error": result.get("error"),
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
    # 1) Get payload (messages + dynamic tools)
    payload = chat_service.prepare_llm_messages(req.messages, req.locale, conversation_id=req.conversation_id)
    messages = payload["messages"]
    slots = payload.get("slots", {})
    
    # 2) Decide whether to allow tool execution
    # If req.allow_actions is True, we pass the tools to LLM.
    # If False, we might still pass read-only tools (like product_search),
    # but for sensitive tools (send_inquiry), we need careful handling.
    # The ToolRegistry inside chat_service already filters tools based on logic.
    # But here we double-check if we want to suppress ALL tools or just rely on registry.
    
    # Current logic: use tools from payload if allow_actions is True, else empty?
    # Actually, read-only tools (search) should be allowed even if allow_actions=False (which usually means "don't send email yet").
    # But for compatibility with frontend "Action Mode", let's stick to the registry's output,
    # OR if you want to strictly disable actions unless confirmed:
    tools = payload["tools"]
    
    # If req.allow_actions is False, we might want to filter out 'send_inquiry' specifically again,
    # but registry might have already done it or kept it for "planning".
    # Let's trust the registry output which is built for the current turn.
    
    # Legacy override: if frontend says allow_actions=False, maybe we shouldn't pass *any* tool?
    # NO, product_search is safe.
    # So we use the tools returned by service (which are filtered by intent/stage).
    
    try:
        result = llm.complete(messages=messages, tools=tools, temperature=0.6)

        # Tool call guard (execute only if frontend allow_actions=True)
        if result.tool_call:
            tool_name = result.tool_call.get("name")
            tool_args = result.tool_call.get("arguments", {}) or {}
            
            # Create Context
            ctx = ToolContext(store=store, mailer=mailer, locale=req.locale, settings=settings, slots=slots)

            # --- Case A: send_inquiry (Sensitive) ---
            if tool_name == "send_inquiry":
                if not req.allow_actions:
                    tip = chat_service.get_tool_response("confirm_needed", req.locale)
                    return ChatResponse(response=(result.text + "\n\n" + tip).strip())

                name = tool_args.get("name")
                email = tool_args.get("email")
                message = tool_args.get("message")

                if not (name and email and message):
                    tip = chat_service.get_tool_response("missing_info", req.locale)
                    return ChatResponse(response=(result.text + "\n\n" + tip).strip())

                # Dispatch
                exec_result = dispatcher.dispatch(tool_name, tool_args, ctx)

                if exec_result.get("ok"):
                    confirm = chat_service.get_tool_response("success", req.locale)
                    return ChatResponse(
                        response=confirm,
                        action="send_inquiry",
                        action_data={"inquiry_id": exec_result["inquiry_id"], "ses": exec_result.get("ses")},
                    )
                else:
                    fail_text = chat_service.get_tool_response("failure", req.locale, error=exec_result.get("error"))
                    return ChatResponse(
                        response=fail_text,
                        action="send_inquiry_failed",
                        action_data={"inquiry_id": exec_result.get("inquiry_id"), "error": exec_result.get("error")},
                    )
            
            # --- Case B: product_search (Read-only / Safe) ---
            elif tool_name == "product_search":
                exec_result = dispatcher.dispatch(tool_name, tool_args, ctx)
                if "error" in exec_result:
                    return ChatResponse(response=f"Tool error: {exec_result['error']}")

                return ChatResponse(
                    response=result.text, # "I found some bags..."
                    action="product_search",
                    action_data=exec_result
                )

        return ChatResponse(response=result.text)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest):
    # 1) Get payload
    payload = chat_service.prepare_llm_messages(req.messages, req.locale, conversation_id=req.conversation_id)
    messages = payload["messages"]
    tools = payload["tools"]
    slots = payload.get("slots", {})

    # Check for user name update
    user_name = None
    if req.conversation_id:
        try:
            st = chat_service.state_store.get_or_create(req.conversation_id, req.locale)
            user_name = st.slots.get("name")
        except Exception:
            pass

    # Log Input
    user_input = req.messages[-1].text if req.messages else ""
    logger.info(f"CHAT_STREAM START | Input: '{user_input}' | Tools: {len(tools)} | Locale: {req.locale}")

    def sse(payload: dict):
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")

    def gen():
        # Initialize Session Logger
        session_logger = SessionLogger(settings.log_dir, req.conversation_id)
        session_logger.info(f"CHAT_STREAM START | Input: '{user_input}' | Tools: {len(tools)} | Locale: {req.locale}")

        try:
            # Send user update if detected
            if user_name:
                yield sse({"type": "user_update", "name": user_name})

            # Create Context for stream
            ctx = ToolContext(store=store, mailer=mailer, locale=req.locale, settings=settings, slots=slots, session_logger=session_logger)
            
            current_messages = messages
            # Allow max 2 turns (1 tool execution + 1 follow-up)
            MAX_TURNS = 2
            
            # Log the full prompt (RAG context is in system message)
            try:
                logger.info(f"CHAT_STREAM PROMPT | Messages: {json.dumps(current_messages, ensure_ascii=False)}")
                session_logger.info(f"CHAT_STREAM PROMPT | Messages: {json.dumps(current_messages, ensure_ascii=False)}")
            except Exception:
                pass

            if not tools:
                logger.info("CHAT_STREAM START (Standard Mode) | No tools available")
            else:
                logger.info(f"CHAT_STREAM START (Agent Mode) | Max Turns: {MAX_TURNS} | Tools: {len(tools)}")

            for turn in range(MAX_TURNS):
                pending_tool = None
                assistant_text_chunks = []
                tool_called_in_this_turn = False
                
                logger.info(f"CHAT_STREAM TURN {turn+1}/{MAX_TURNS} | Messages count: {len(current_messages)}")

                try:
                    t0 = time.time()
                    t_first = None
                    token_count = 0
                    
                    stream_gen = llm.stream(messages=current_messages, tools=tools, temperature=0.6)
                    
                    for ev in stream_gen:
                        if t_first is None:
                            t_first = time.time()
                        
                        t = ev.get("type")

                        if t == "delta":
                            text = ev.get("text", "")
                            token_count += 1 # Rough estimate
                            assistant_text_chunks.append(text)
                            yield sse({"type": "delta", "text": text})

                        elif t == "tool_call":
                            pending_tool = ev
                            tool_called_in_this_turn = True
                            logger.info(f"CHAT_STREAM TURN {turn+1} TOOL_DETECTED | Name: {ev.get('name')} | Args: {ev.get('arguments')}")
                            session_logger.info(f"TOOL START: {ev.get('name')} Args: {json.dumps(ev.get('arguments'), ensure_ascii=False)}")
                            yield sse({
                                "type": "tool_call",
                                "name": ev.get("name"),
                                "arguments": ev.get("arguments", {}),
                            })

                        elif t == "done":
                            break
                    
                    t_end = time.time()
                    latency_first = (t_first - t0) * 1000 if t_first else 0
                    latency_total = (t_end - t0) * 1000
                    tokens_per_sec = token_count / (t_end - t_first) if (t_first and t_end > t_first) else 0
                    
                    logger.info(f"LLM Perf: first_token={latency_first:.0f}ms total={latency_total:.0f}ms tokens={token_count} rate={tokens_per_sec:.1f}t/s")

                except Exception as e:
                    logger.exception(f"CHAT_STREAM TURN {turn+1} LLM ERROR")
                    session_logger.error(f"CHAT_STREAM LLM ERROR: {e}")
                    yield sse({"type": "error", "message": str(e)})
                    return

                # If no tool called, we are done
                if not tool_called_in_this_turn:
                    final_response = "".join(assistant_text_chunks).strip()
                    logger.info(f"CHAT_STREAM COMPLETE | Turn: {turn+1} | Response length: {len(final_response)}")
                    # logger.info(f"CHAT_STREAM RESPONSE: {final_response}") # Avoid duplicate log
                    logger.debug(f"CHAT_STREAM RESPONSE_FULL: {final_response}")
                    session_logger.info(f"CHAT_STREAM RESPONSE: {final_response}")

                    if req.conversation_id:
                        chat_service.persist_turn(req.conversation_id, "assistant", final_response, req.locale)

                    yield sse({"type": "final", "text": final_response})
                    yield sse({"type": "done"})
                    return

                # Handle Tool Execution
                if pending_tool:
                    tool_name = pending_tool.get("name")
                    tool_args = pending_tool.get("arguments", {}) or {}
                    
                    logger.info(f"CHAT_STREAM TURN {turn+1} TOOL_EXEC | Action: {tool_name} | Args: {json.dumps(tool_args, ensure_ascii=False)}")

                    # Append assistant's thought/tool_call to history
                    current_messages.append({
                        "role": "assistant",
                        "content": "".join(assistant_text_chunks)
                    })
                    
                    exec_result = {}

                    # --- Send Inquiry ---
                    if tool_name == "send_inquiry":
                        if not req.allow_actions:
                            logger.info("CHAT_STREAM TOOL_SKIP | Reason: allow_actions=False")
                            session_logger.info("TOOL SKIP: allow_actions=False")
                            final_text = chat_service.get_tool_response("confirm_needed", req.locale)
                            yield sse({"type": "final", "text": final_text})
                            yield sse({"type": "done"})
                            return

                        name = tool_args.get("name")
                        email = tool_args.get("email")
                        message = tool_args.get("message")

                        if not (name and email and message):
                            logger.info("CHAT_STREAM TOOL_SKIP | Reason: Missing fields")
                            session_logger.info("TOOL SKIP: Missing fields")
                            final_text = chat_service.get_tool_response("missing_info", req.locale)
                            yield sse({"type": "final", "text": final_text})
                            yield sse({"type": "done"})
                            return

                        # Inject source
                        tool_args["source"] = "chat_stream_tool"
                        exec_result = dispatcher.dispatch(tool_name, tool_args, ctx)
                        session_logger.info(f"TOOL RETURN: {tool_name} Result: {json.dumps(exec_result, ensure_ascii=False, default=str)}")

                        if exec_result.get("ok"):
                            logger.info(f"CHAT_STREAM TOOL_SUCCESS | InquiryID: {exec_result['inquiry_id']}")
                            # Yield action event for UI update
                            # We use 'action' field to trigger UI side effects without replacing text
                            yield sse({
                                "type": "action_event", # Custom type or reuse 'final' with action? 
                                # If we use 'final', it might clear text. 
                                # Let's use a safe way: 'tool_result'? 
                                # The frontend likely listens to 'action' in 'final'.
                                # If we send 'final' with empty text, it might clear screen.
                                # So let's send 'action' only if supported, or rely on LLM confirmation text.
                                # But we want the UI to show the 'Success' state (checkmark).
                                # We'll send a 'final' packet with action, but with current text?
                                # Actually, just let the LLM say "Sent".
                                # But we need the 'action_data' for the inquiry_id.
                                # We will send a special packet.
                                "action": "send_inquiry",
                                "action_data": {"inquiry_id": exec_result["inquiry_id"], "ses": exec_result.get("ses")},
                            })
                            
                            # Feed success back to LLM
                            sys_msg = f"System Notification: Tool '{tool_name}' executed successfully. Inquiry ID: {exec_result['inquiry_id']}. The email HAS been sent. Please confirm to the user that it is done."
                            current_messages.append({
                                "role": "user",
                                "content": sys_msg
                            })
                            # Persist tool result
                            if req.conversation_id:
                                chat_service.persist_turn(req.conversation_id, "user", sys_msg, req.locale)
                                
                        else:
                            logger.error(f"CHAT_STREAM TOOL_FAIL | Error: {exec_result.get('error')}")
                            # Feed error
                            sys_msg = f"System Notification: Tool '{tool_name}' failed. Error: {exec_result.get('error')}"
                            current_messages.append({
                                "role": "user",
                                "content": sys_msg
                            })
                            if req.conversation_id:
                                chat_service.persist_turn(req.conversation_id, "user", sys_msg, req.locale)

                    # --- Get Product Details ---
                    elif tool_name == "get_product_details":
                        exec_result = dispatcher.dispatch(tool_name, tool_args, ctx)
                        session_logger.info(f"TOOL RETURN: {tool_name} Result: {json.dumps(exec_result, ensure_ascii=False, default=str)}")
                        logger.info(f"CHAT_STREAM TOOL_RESULT | Tool: {tool_name} | Result Keys: {list(exec_result.keys())}")
                        
                        # Feed result back to LLM
                        res_str = json.dumps(exec_result, ensure_ascii=False)
                        if len(res_str) > 6000: res_str = res_str[:6000] + "...(truncated)"
                        
                        sys_msg = f"System Notification: Tool '{tool_name}' output: {res_str}"
                        current_messages.append({
                            "role": "user",
                            "content": sys_msg
                        })
                        # Persist tool result (maybe truncated? or full? Persisting huge JSON might be bad for token limits next time)
                        # We might want to persist a summary or the full thing. 
                        # For now, persist it so the model remembers it saw the details.
                        if req.conversation_id:
                            chat_service.persist_turn(req.conversation_id, "user", sys_msg, req.locale)

                    # --- Product Search ---
                    elif tool_name == "product_search":
                        exec_result = dispatcher.dispatch(tool_name, tool_args, ctx)
                        session_logger.info(f"TOOL RETURN: {tool_name} Result: {len(exec_result.get('results', []))} hits")
                        logger.info(f"CHAT_STREAM TOOL_RESULT | Tool: {tool_name} | Results: {len(exec_result.get('results', []))}")
                        
                        # Return results to frontend to render
                        yield sse({
                            "type": "final", # This triggers UI rendering of cards
                            "action": "product_search",
                            "action_data": exec_result,
                            "text": "".join(assistant_text_chunks) # Keep existing text?
                        })
                        
                        # Feed back to LLM so it can comment
                        sys_msg = f"System Notification: Tool '{tool_name}' returned {len(exec_result.get('results', []))} results. Please summarize or recommend based on these results."
                        current_messages.append({
                            "role": "user",
                            "content": sys_msg
                        })
                        if req.conversation_id:
                            chat_service.persist_turn(req.conversation_id, "user", sys_msg, req.locale)
                    
                    else:
                        # Unknown tool?
                        logger.warning(f"CHAT_STREAM TOOL_UNKNOWN | Name: {tool_name}")
                        session_logger.warning(f"TOOL UNKNOWN: {tool_name}")
                        sys_msg = f"System Notification: Tool '{tool_name}' execution failed (unknown tool)."
                        current_messages.append({
                            "role": "user",
                            "content": sys_msg
                        })
                        if req.conversation_id:
                            chat_service.persist_turn(req.conversation_id, "user", sys_msg, req.locale)

                    # Loop continues to next turn to generate response based on tool output

            # End of loop
            logger.info("CHAT_STREAM LOOP END | Max turns reached or finished")
            yield sse({"type": "done"})
        
        finally:
            session_logger.close()

    return StreamingResponse(gen(), media_type="text/event-stream")