import json
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, EmailStr

from .settings import settings
from .data_store import DataStore
from .product_search import build_product_context, search_products
from .email_ses import SesMailer
from .llm_client import LLMClient
from .db import init_db, insert_inquiry, mark_inquiry_sent, mark_inquiry_failed

app = FastAPI()
init_db()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境请改成你的域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

store = DataStore(settings.data_dir)
llm = LLMClient()

mailer = SesMailer(
    region=settings.aws_region,
    access_key_id=settings.aws_access_key_id,
    secret_access_key=settings.aws_secret_access_key,
    from_email=settings.ses_from_email,
    to_email=settings.ses_to_email,
    configuration_set=settings.ses_configuration_set,
)

def send_inquiry_with_db(name: str, email: str, message: str, source: str, locale: str):
    """
    先写入 SQLite（pending），再调用 SES。
    返回统一结构，供 /api/send-email 和 chat tool 共用。
    """
    inquiry_id = insert_inquiry(
        name=name,
        email=email,
        message=message,
        source=source,
        locale=locale,
        meta={"ua": "api"}  # 你也可以加 request headers / ip 等
    )

    try:
        ses_resp = mailer.send_inquiry(name, email, message)  # {"messageId": "..."}
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

# ----------- Schemas -----------

class ChatMessage(BaseModel):
    role: str  # user|assistant|system 或你前端的 bot
    text: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    locale: str = "en"
    allow_actions: bool = False  # 前端确认后才置 true


class ChatResponse(BaseModel):
    response: str
    action: Optional[str] = None
    action_data: Optional[Dict[str, Any]] = None


class EmailRequest(BaseModel):
    name: str
    email: EmailStr
    message: str
    locale: str = "en"


# ----------- Prompts -----------

def build_system_prompt(locale: str) -> str:
    info = store.website_info
    company = (info.get("companyName", {}) or {}).get(locale) or (info.get("companyName", {}) or {}).get("en") or "JWL Travel Gear"

    if locale == "zh":
        return f"""你是 {company} 的网站客服 AI 助手（箱包/背包工厂）。
目标：专业、简洁、准确地回答用户关于公司、产品、OEM/ODM 的问题。

规则：
1) 只根据我提供的上下文回答；没有把握就建议用户联系我们。
2) 用户想询价/打样/下单：先询问需求（品类、数量、目标价格、材质、logo 工艺、交期、目的市场等）。
3) 只有当用户明确表示“确认发送邮件”并提供 name/email/message 时，才可以调用 send_inquiry 工具。
4) 如果用户没确认或信息不全：请继续追问，不要调用工具。
"""
    else:
        return f"""You are the website support AI assistant for {company}, a premium bag manufacturer.
Goal: answer questions about products, OEM/ODM services, and company info accurately and professionally.

Rules:
1) Answer only based on the provided context. If uncertain, suggest contacting support.
2) For quotes/sampling/orders: ask for requirements (category, quantity, target price, materials, logo method, lead time, market).
3) Only call the send_inquiry tool AFTER the user explicitly confirms sending an email and provides name/email/message.
4) If not confirmed or missing info: ask follow-up questions and do NOT call the tool.
"""


def build_company_context(query: str, locale: str) -> str:
    q = query.lower()
    parts = []

    if any(k in q for k in ["about", "company", "history", "mission", "factory", "manufacture", "关于", "公司", "工厂", "使命"]):
        parts.append(json.dumps(store.website_info.get("about", {}), ensure_ascii=False, indent=2))

    if any(k in q for k in ["contact", "email", "phone", "address", "location", "reach", "联系", "邮箱", "电话", "地址", "微信"]):
        parts.append(json.dumps(store.website_info.get("contact", {}), ensure_ascii=False, indent=2))

    if any(k in q for k in ["service", "oem", "odm", "custom", "design", "quality", "定制", "打样", "品质"]):
        parts.append(json.dumps(store.website_info.get("services", {}), ensure_ascii=False, indent=2))

    if any(k in q for k in ["certifi", "standard", "audit", "认证", "标准", "验厂"]):
        parts.append(json.dumps(store.certifications, ensure_ascii=False, indent=2))

    return "\n\n".join(parts)


def to_llm_messages(req: ChatRequest) -> List[Dict[str, Any]]:
    # 1) system
    sys = build_system_prompt(req.locale)

    # 2) dynamic product context (simple JSON scan)
    last_user = ""
    for m in reversed(req.messages):
        if m.role in ("user",) or m.role not in ("assistant", "bot", "system"):
            last_user = m.text
            break

    prod_ctx = build_product_context(store.products, last_user, req.locale, limit=3)
    comp_ctx = build_company_context(last_user, req.locale)

    ctx = ""
    if prod_ctx:
        ctx += prod_ctx + "\n\n"
    if comp_ctx:
        ctx += ("公司信息:\n" if req.locale == "zh" else "Company info:\n") + comp_ctx + "\n\n"

    system_content = sys + ("\n\n[Context]\n" + ctx if ctx else "")

    messages: List[Dict[str, Any]] = [{"role": "system", "content": system_content}]

    for m in req.messages:
        role = m.role
        if role == "bot":
            role = "assistant"
        if role not in ("system", "user", "assistant"):
            role = "user"
        messages.append({"role": role, "content": m.text})

    return messages


# ----------- APIs -----------

@app.get("/api/health")
async def health():
    return {"status": "ok", "products_loaded": len(store.products), "llm_backend": settings.llm_backend}


@app.post("/api/send-email")
async def send_email(req: EmailRequest):
    result = send_inquiry_with_db(
        name=req.name,
        email=str(req.email),
        message=req.message,
        source="api/send-email",
        locale=req.locale,
    )

    if result["ok"]:
        return {"status": "success", "inquiry_id": result["inquiry_id"], "ses": result["ses"]}
    else:
        # 这里不抛异常：返回失败原因，前端可提示用户“稍后再试/改用表单”
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
    results = search_products(store.products, q, locale=locale, limit=limit)
    return {"query": q, "count": len(results), "results": results}


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    messages = to_llm_messages(req)
    #tools = llm.tools()
    tools = llm.tools() if req.allow_actions else []

    try:
        result = llm.complete(messages=messages, tools=tools, temperature=0.6)

        # tool call guard（只有前端 allow_actions=True 才执行）
        if result.tool_call and result.tool_call.get("name") == "send_inquiry":
            if not req.allow_actions:
                tip = "请确认是否要发送邮件，并提供姓名/邮箱/留言内容。" if req.locale == "zh" else \
                    "Please confirm you want to send an email and provide name/email/message."
                return ChatResponse(response=(result.text + "\n\n" + tip).strip())

            args = result.tool_call.get("arguments", {}) or {}
            name = args.get("name")
            email = args.get("email")
            message = args.get("message")

            if not (name and email and message):
                tip = "信息不全：需要 name/email/message 才能发送。" if req.locale == "zh" else \
                    "Missing fields: name/email/message are required."
                return ChatResponse(response=(result.text + "\n\n" + tip).strip())

            send_result = send_inquiry_with_db(
                name=name,
                email=email,
                message=message,
                source="chat_tool",
                locale=req.locale,
            )

            if send_result["ok"]:
                confirm = "已发送给我们的团队，我们会尽快联系你。" if req.locale == "zh" else \
                        "Sent to our team. We’ll get back to you shortly."
                return ChatResponse(
                    response=confirm,
                    action="send_inquiry",
                    action_data={"inquiry_id": send_result["inquiry_id"], "ses": send_result["ses"]},
                )
            else:
                # ✅ 关键：失败情况返回给 ChatResponse
                fail_text = (
                    "邮件发送失败（我们已记录你的信息）。请稍后再试，或直接通过网站联系方式联系我们。\n"
                    f"错误信息：{send_result['error']}"
                ) if req.locale == "zh" else (
                    "Email sending failed (we have saved your message). Please try again later or contact us via the website.\n"
                    f"Error: {send_result['error']}"
                )
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
    messages = to_llm_messages(req)
    tools = llm.tools()

    def gen():
        """
        SSE: 每条消息 `data: {...}\n\n`
        """
        pending_tool = None

        try:
            for ev in llm.stream(messages=messages, tools=tools, temperature=0.6):
                if ev["type"] == "delta":
                    payload = {"type": "delta", "text": ev["text"]}
                    yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")

                elif ev["type"] == "tool_call":
                    pending_tool = ev
                    payload = {"type": "tool_call", "name": ev.get("name"), "arguments": ev.get("arguments", {})}
                    yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")

                elif ev["type"] == "done":
                    # 如果有 tool_call，最后再发一个 final（是否执行由前端 allow_actions 决定）
                    if pending_tool and pending_tool.get("name") == "send_inquiry":
                        if req.allow_actions:
                            args = pending_tool.get("arguments", {}) or {}
                            name = args.get("name")
                            email = args.get("email")
                            message = args.get("message")
                            if name and email and message:
                                ses = mailer.send_inquiry(name=name, email=email, message=message)
                                final_text = "已发送给我们的团队，我们会尽快联系你。" if req.locale == "zh" else "Sent to our team. We’ll get back to you shortly."
                                payload = {"type": "final", "text": final_text, "action": "send_inquiry", "action_data": {"ses": ses}}
                                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")
                            else:
                                final_text = "信息不全：需要 name/email/message 才能发送。" if req.locale == "zh" else "Missing fields: name/email/message are required."
                                payload = {"type": "final", "text": final_text}
                                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")
                        else:
                            final_text = "如需发送邮件，请点击确认并提供姓名/邮箱/留言内容。" if req.locale == "zh" else "To send an email, please confirm and provide name/email/message."
                            payload = {"type": "final", "text": final_text}
                            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")
                    else:
                        payload = {"type": "done"}
                        yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")

        except Exception as e:
            payload = {"type": "error", "message": str(e)}
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")

    return StreamingResponse(gen(), media_type="text/event-stream")