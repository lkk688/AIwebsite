import json
import time
import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.api.schemas import ChatRequest, ChatResponse
from app.core.config import settings
from app.core.logging import SessionLogger
from app.core.services import chat_service, store, mailer, llm
from app.tools.base import ToolContext

logger = logging.getLogger("jwl.api")
router = APIRouter()

@router.post("/init")
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
        from app.services.rag.product import get_product_rag
        prag = get_product_rag()
        if prag._vecs is None:
            prag.build_index()
            logger.info("INIT_CHAT | Product RAG built")
        else:
            logger.info("INIT_CHAT | Product RAG already ready")
    except Exception as e:
        logger.error(f"INIT_CHAT | Product RAG failed: {e}")

    # 3. Build KB RAG
    try:
        from app.services.rag.kb import get_kb_rag
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


@router.post("", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """
    Standard Chat API (Non-streaming).
    Processes user messages, interacts with LLM, and handles tool calls (like sending emails).
    Matches chat_stream logic with SessionLogger, persistence, and Agent Loop.
    """
    # 1) Get payload (messages + dynamic tools)
    payload = chat_service.prepare_llm_messages(req.messages, req.locale, conversation_id=req.conversation_id)
    messages = payload["messages"]
    tools = payload["tools"]
    slots = payload.get("slots", {})
    
    # Initialize Session Logger
    session_logger = SessionLogger(settings.log_dir, req.conversation_id)
    
    user_input = req.messages[-1].text if req.messages else ""
    logger.info(f"CHAT START | Input: '{user_input}' | Tools: {len(tools)} | Locale: {req.locale}")
    session_logger.info(f"CHAT START | Input: '{user_input}' | Tools: {len(tools)} | Locale: {req.locale}")
    
    # Check for user name update
    if req.conversation_id:
        try:
            st = chat_service.state_store.get_or_create(req.conversation_id, req.locale)
            # user_name = st.slots.get("name") # Not used in sync response yet, but available
        except Exception:
            pass

    try:
        # Create Context
        ctx = ToolContext(store=store, mailer=mailer, locale=req.locale, settings=settings, slots=slots, session_logger=session_logger)

        current_messages = messages
        MAX_TURNS = 2
        
        # Log prompt
        try:
            logger.info(f"CHAT PROMPT | Messages: {json.dumps(current_messages, ensure_ascii=False)}")
            session_logger.info(f"CHAT PROMPT | Messages: {json.dumps(current_messages, ensure_ascii=False)}")
        except Exception:
            pass

        final_response_text = ""
        final_action = None
        final_action_data = None
        
        for turn in range(MAX_TURNS):
            logger.info(f"CHAT TURN {turn+1}/{MAX_TURNS}")
            
            # Execute LLM (Sync)
            # llm.complete returns { text: str, tool_call: dict }
            result = llm.complete(messages=current_messages, tools=tools, temperature=0.6)
            
            # Check for tool call
            if result.tool_call:
                tool_name = result.tool_call.get("name")
                tool_args = result.tool_call.get("arguments", {}) or {}
                
                logger.info(f"CHAT TURN {turn+1} TOOL_DETECTED | Name: {tool_name}")
                session_logger.info(f"TOOL START: {tool_name} Args: {json.dumps(tool_args, ensure_ascii=False)}")
                
                # Append assistant thought
                current_messages.append({
                    "role": "assistant",
                    "content": result.text or "" # Might be empty if tool call only
                })

                # Process tool
                proc_res = chat_service.process_tool_call(tool_name, tool_args, ctx, req.allow_actions)
                
                # 1. Handle Skip/Blocking -> Return immediately
                if proc_res["skip_reason"]:
                    logger.info(f"CHAT TOOL_SKIP | Reason: {proc_res['skip_reason']}")
                    session_logger.info(f"TOOL SKIP: {proc_res['skip_reason']}")
                    return ChatResponse(response=(result.text + "\n\n" + proc_res["client_response"]).strip())

                # 2. Capture Action Data (to be returned in final response)
                if proc_res["ui_action"]:
                    final_action = proc_res["ui_action"]
                    final_action_data = proc_res["ui_data"]

                # 3. Handle System Message (Feed back to LLM for next turn)
                if proc_res["system_msg"]:
                    current_messages.append({
                        "role": "user",
                        "content": proc_res["system_msg"]
                    })
                    # Persist system msg
                    if req.conversation_id:
                        chat_service.persist_turn(req.conversation_id, "user", proc_res["system_msg"], req.locale)
                
                # Loop continues to next turn to get LLM's final comment
                continue
            
            else:
                # No tool call -> Final Response
                final_response_text = result.text
                logger.info(f"CHAT COMPLETE | Turn: {turn+1} | Response length: {len(final_response_text)}")
                session_logger.info(f"CHAT RESPONSE: {final_response_text}")
                
                # Persist assistant response
                if req.conversation_id:
                    chat_service.persist_turn(req.conversation_id, "assistant", final_response_text, req.locale)
                
                break
        
        # End of loop
        session_logger.close()
        
        return ChatResponse(
            response=final_response_text,
            action=final_action,
            action_data=final_action_data
        )

    except Exception as e:
        session_logger.error(f"CHAT ERROR: {e}")
        session_logger.close()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stream")
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
                    
                    # Call standardized processor
                    proc_res = chat_service.process_tool_call(tool_name, tool_args, ctx, req.allow_actions)
                    
                    # 1. Handle Skip/Blocking
                    if proc_res["skip_reason"]:
                        logger.info(f"CHAT_STREAM TOOL_SKIP | Reason: {proc_res['skip_reason']}")
                        yield sse({"type": "final", "text": proc_res["client_response"]})
                        yield sse({"type": "done"})
                        return

                    # 2. Handle UI Actions
                    if proc_res["ui_action"] == "product_search":
                        # For product search, we send a 'final' packet with data, but loop continues for LLM comment
                        yield sse({
                            "type": "final",
                            "action": "product_search",
                            "action_data": proc_res["ui_data"],
                            "text": "".join(assistant_text_chunks)
                        })
                    elif proc_res["ui_action"] == "send_inquiry":
                         yield sse({
                            "type": "action_event",
                            "action": "send_inquiry",
                            "action_data": proc_res["ui_data"],
                        })
                    elif proc_res["ui_action"] == "send_inquiry_failed":
                         # Maybe notify UI of failure?
                         pass
                    
                    # 3. Handle System Message (Feed back to LLM)
                    if proc_res["system_msg"]:
                        current_messages.append({
                            "role": "user",
                            "content": proc_res["system_msg"]
                        })
                        if req.conversation_id:
                            chat_service.persist_turn(req.conversation_id, "user", proc_res["system_msg"], req.locale)
                    
                    # Loop continues to next turn to generate response based on tool output

            # End of loop
            logger.info("CHAT_STREAM LOOP END | Max turns reached or finished")
            yield sse({"type": "done"})
        
        finally:
            session_logger.close()

    return StreamingResponse(gen(), media_type="text/event-stream")
