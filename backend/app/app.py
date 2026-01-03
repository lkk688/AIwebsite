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
from .embeddings_client import EmbeddingsClient
from .product_rag import ProductRAG
import logging
from typing import Any, Dict, List
import os

def setup_logging():
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )

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

embedder = EmbeddingsClient()
product_rag = ProductRAG(store.products, embedder)
product_rag.build_index()  # 产品少，启动时建一次即可

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

def build_rag_context(query: str, locale: str, k: int = 5) -> Dict[str, Any]:
    r = product_rag.retrieve(query, locale=locale, k=k)
    mode = r.get("mode")
    products = r.get("products", []) or []

    def name_of(p: Dict[str, Any]) -> str:
        return _get_locale_text(p, "name", locale)

    hits_summary = [{"id": p.get("id"), "slug": p.get("slug"), "name": name_of(p)} for p in products[: min(len(products), 5)]]

    if not products:
        return {"mode": "none", "products": [], "context": "", "hits_summary": []}

    # exact：给 1 个全量；rag：给 top3~5 摘要
    if mode == "exact":
        p = products[0]
        ctx = (
            ("【匹配到指定产品】\n" if locale == "zh" else "[Exact Product Match]\n") +
            "请基于以下产品信息回答，并在答案中引用 product id/slug。\n" if locale == "zh"
            else "Answer using the product info below and cite product id/slug.\n"
        )
        ctx += (
            f"- id: {p.get('id')}\n"
            f"- slug: {p.get('slug')}\n"
            f"- name: {name_of(p)}\n"
            f"- category: {p.get('category')}\n"
            f"- tags: {p.get('tags', [])}\n"
            f"- description: {_get_locale_text(p, 'description', locale)}\n"
            f"- materials: {_get_locale_text(p, 'materials', locale)}\n"
            f"- specifications: {_get_locale_text(p, 'specifications', locale)}\n"
            f"- variants: {p.get('variants', [])}\n"
        )
        return {"mode": mode, "products": [p], "context": ctx, "hits_summary": hits_summary}

    # rag
    take = min(5, len(products))
    title = "【语义检索 TopK】" if locale == "zh" else "[Semantic TopK]"
    ctx_lines = [title, ("请从以下候选产品中选择最相关的回答，并引用 id/slug。\n" if locale == "zh"
                         else "Choose the most relevant product(s) below and cite id/slug.\n")]

    for p in products[:take]:
        ctx_lines.append(
            f"- id={p.get('id')} slug={p.get('slug')} name={name_of(p)}\n"
            f"  category={p.get('category')} tags={p.get('tags', [])}\n"
            f"  desc={_get_locale_text(p, 'description', locale)[:260]}\n"
        )

    return {"mode": mode, "products": products[:take], "context": "\n".join(ctx_lines), "hits_summary": hits_summary}

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

# def build_system_prompt(locale: str) -> str:
#     """
#     Builds the system prompt for the LLM based on the user's locale.
#     Includes company info and rules for the AI assistant.
#     """
#     info = store.website_info
#     company = (info.get("companyName", {}) or {}).get(locale) or (info.get("companyName", {}) or {}).get("en") or "JWL Travel Gear"

#     if locale == "zh":
#         return f"""你是 {company} 的网站客服 AI 助手（箱包/背包工厂）。
# 目标：专业、简洁、准确地回答用户关于公司、产品、OEM/ODM 的问题。

# 规则：
# 1) 只根据我提供的上下文回答；没有把握就建议用户联系我们。
# 2) 用户想询价/打样/下单：先询问需求（品类、数量、目标价格、材质、logo 工艺、交期、目的市场等）。
# 3) 只有当用户明确表示“确认发送邮件”并提供 name/email/message 时，才可以调用 send_inquiry 工具。
# 4) 如果用户没确认或信息不全：请继续追问，不要调用工具。
# """
#     else:
#         return f"""You are the website support AI assistant for {company}, a premium bag manufacturer.
# Goal: answer questions about products, OEM/ODM services, and company info accurately and professionally.

# Rules:
# 1) Answer only based on the provided context. If uncertain, suggest contacting support.
# 2) For quotes/sampling/orders: ask for requirements (category, quantity, target price, materials, logo method, lead time, market).
# 3) Only call the send_inquiry tool AFTER the user explicitly confirms sending an email and provides name/email/message.
# 4) If not confirmed or missing info: ask follow-up questions and do NOT call the tool.
# """

def build_system_prompt(locale: str) -> str:
    """
    Builds the system prompt for the LLM based on the user's locale.
    Includes company info and rules for the AI assistant.
    """
    info = store.website_info
    company = (info.get("companyName", {}) or {}).get(locale) or (info.get("companyName", {}) or {}).get("en") or "JWL Travel Gear"

    if locale == "zh":
        return f"""你是 {company} 的网站客服 AI 助手（箱包/背包工厂）。
目标：专业、简洁、准确地回答用户关于公司、产品、OEM/ODM 的问题。

严格动作策略（非常重要）：
- 你有一个工具 send_inquiry(name, email, message)，用于给销售团队发送邮件。
- 如果用户已经提供了必填字段：name / email / message，并且明确表示“确认发送 / 直接发送 / 现在就发 / 不用再问，直接发”，
  你必须立刻调用 send_inquiry 发送邮件。
- 满足上述条件时，不要再追问目标价格、材质、Logo、交期、市场等额外信息（这些是可选项），
  可以在邮件发送后再作为补充追问。

通用规则：
1) 只根据提供的上下文回答；没有把握就建议用户联系我们。
2) 用户想询价/打样/下单但未确认发送邮件，或缺少必填字段：请简洁追问。
3) 只有当用户明确确认发送 AND 已提供 name/email/message，才可以调用 send_inquiry。
4) 未确认：先让用户确认发送。
5) 信息不全：只询问缺失的字段。

输出要求：
- 调用 send_inquiry 时，message 要包含：产品/数量/用户已给出的所有需求信息。
- 不要编造用户未提供的信息。
"""
    else:
        return f"""You are the website support AI assistant for {company}, a premium bag manufacturer.
Goal: answer questions about products, OEM/ODM services, and company info accurately and professionally.

STRICT ACTION POLICY (IMPORTANT):
- You have a tool called send_inquiry(name, email, message) that sends an email to the sales team.
- If the user has provided ALL required fields (name, email, message) AND explicitly confirms sending
  (e.g., "confirm send", "just send", "send it now", "please send"), you MUST call send_inquiry immediately.
- When the above condition is met, DO NOT ask for additional details (price, materials, lead time, market, etc.).
  Those details are optional and can be asked only AFTER the email is sent, or in a follow-up message.

GENERAL RULES:
1) Answer only based on the provided context. If uncertain, suggest contacting support.
2) If the user wants a quote/sampling/order but has NOT confirmed sending an email OR is missing required fields,
   ask concise follow-up questions.
3) Only call send_inquiry AFTER explicit confirmation AND required fields are present.
4) If confirmation is missing: ask the user to confirm sending.
5) If required fields are missing: ask ONLY for the missing fields.

OUTPUT REQUIREMENT:
- When calling send_inquiry, pass a single clear message that includes the product(s) and quantity and any details provided.
- Do not invent details that the user did not provide.
"""


def build_company_context(query: str, locale: str) -> str:
    """
    Retrieves relevant company information (About, Contact, Services, Certifications)
    based on keywords in the user's query.
    """
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
    """
    Converts the chat request into the format required by the LLM.
    Constructs the system prompt and injects context (product info, company info).
    """
    # 1) Build system prompt
    sys = build_system_prompt(req.locale)

    # 2) Build dynamic product context (simple JSON scan based on last user message)
    last_user = ""
    for m in reversed(req.messages):
        if m.role in ("user",) or m.role not in ("assistant", "bot", "system"):
            last_user = m.text
            break

    #prod_ctx = build_product_context(store.products, last_user, req.locale, limit=3)
    #Use RAG
    # 1) RAG 检索
    rag_info = build_rag_context(query=last_user, locale=req.locale, k=5)
    prod_ctx = rag_info["context"]  # 已经是 string

    # 2) 公司信息（只在关键词触发时注入）
    comp_ctx = build_company_context(last_user, req.locale)

    # 3) 拼接 system content（把产品放在最后，最靠近用户问题）
    ctx_parts = []
    if comp_ctx:
        ctx_parts.append(("公司信息:\n" if req.locale == "zh" else "Company info:\n") + comp_ctx)
    if prod_ctx:
        ctx_parts.append(prod_ctx)

    system_content = sys
    if ctx_parts:
        system_content += "\n\n[Context]\n" + "\n\n".join(ctx_parts)

    # 4) 生成 messages
    messages: List[Dict[str, Any]] = [{"role": "system", "content": system_content}]
    for m in req.messages:
        role = "assistant" if m.role == "bot" else m.role
        if role not in ("system", "user", "assistant"):
            role = "user"
        messages.append({"role": role, "content": m.text})

    # 5) 日志（调试 RAG 是否注入成功的关键）
    try:
        logger.info(
            "chat_context locale=%s rag_mode=%s hit=%s ctx_len=%d",
            req.locale,
            rag_info.get("mode"),
            rag_info.get("hits_summary"),
            len(prod_ctx or ""),
        )
    except Exception:
        pass

    return messages


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
    results = search_products(store.products, q, locale=locale, limit=limit)
    return {"query": q, "count": len(results), "results": results}


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """
    Standard Chat API (Non-streaming).
    Processes user messages, interacts with LLM, and handles tool calls (like sending emails).
    """
    messages = to_llm_messages(req)
    #tools = llm.tools()
    tools = llm.tools() if req.allow_actions else []

    try:
        result = llm.complete(messages=messages, tools=tools, temperature=0.6)

        # Tool call guard (execute only if frontend allow_actions=True)
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

            send_result = send_inquiry_with_db_email(
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
                # ✅ Critical: Return failure case to ChatResponse
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


# @app.post("/api/chat/stream")
# async def chat_stream(req: ChatRequest):
#     """
#     Streaming Chat API using Server-Sent Events (SSE).
#     Returns incremental text updates and tool call events.
#     """
#     messages = to_llm_messages(req)
#     tools = llm.tools()

#     def gen():
#         """
#         SSE Generator: Yields messages formatted as `data: {...}\n\n`
#         """
#         pending_tool = None

#         try:
#             for ev in llm.stream(messages=messages, tools=tools, temperature=0.6):
#                 if ev["type"] == "delta":
#                     payload = {"type": "delta", "text": ev["text"]}
#                     yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")

#                 elif ev["type"] == "tool_call":
#                     pending_tool = ev
#                     payload = {"type": "tool_call", "name": ev.get("name"), "arguments": ev.get("arguments", {})}
#                     yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")

#                 elif ev["type"] == "done":
#                     # If there is a tool_call, send a final one at the end (execution depends on frontend allow_actions)
#                     if pending_tool and pending_tool.get("name") == "send_inquiry":
#                         if req.allow_actions:
#                             args = pending_tool.get("arguments", {}) or {}
#                             name = args.get("name")
#                             email = args.get("email")
#                             message = args.get("message")
#                             if name and email and message:
#                                 ses = mailer.send_inquiry(name=name, email=email, message=message)
#                                 final_text = "已发送给我们的团队，我们会尽快联系你。" if req.locale == "zh" else "Sent to our team. We’ll get back to you shortly."
#                                 payload = {"type": "final", "text": final_text, "action": "send_inquiry", "action_data": {"ses": ses}}
#                                 yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")
#                             else:
#                                 final_text = "信息不全：需要 name/email/message 才能发送。" if req.locale == "zh" else "Missing fields: name/email/message are required."
#                                 payload = {"type": "final", "text": final_text}
#                                 yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")
#                         else:
#                             final_text = "如需发送邮件，请点击确认并提供姓名/邮箱/留言内容。" if req.locale == "zh" else "To send an email, please confirm and provide name/email/message."
#                             payload = {"type": "final", "text": final_text}
#                             yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")
#                     else:
#                         payload = {"type": "done"}
#                         yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")

#         except Exception as e:
#             payload = {"type": "error", "message": str(e)}
#             yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")

#     return StreamingResponse(gen(), media_type="text/event-stream")

@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest):
    messages = to_llm_messages(req)
    tools = llm.tools() if req.allow_actions else []  # ✅ 和 /api/chat 对齐

    def sse(payload: dict):
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")

    def gen():
        pending_tool = None
        assistant_text_chunks = []

        try:
            for ev in llm.stream(messages=messages, tools=tools, temperature=0.6):
                t = ev.get("type")

                if t == "delta":
                    assistant_text_chunks.append(ev.get("text", ""))
                    yield sse({"type": "delta", "text": ev.get("text", "")})

                elif t == "tool_call":
                    pending_tool = ev
                    yield sse({
                        "type": "tool_call",
                        "name": ev.get("name"),
                        "arguments": ev.get("arguments", {}),
                    })

                elif t == "done":
                    # ✅ 统一在 done 时输出 final（确保用户看到结果）
                    if pending_tool and pending_tool.get("name") == "send_inquiry":
                        if not req.allow_actions:
                            final_text = "如需发送邮件，请点击确认并提供姓名/邮箱/留言内容。" if req.locale == "zh" \
                                else "To send an email, please confirm and provide name/email/message."
                            yield sse({"type": "final", "text": final_text})
                            yield sse({"type": "done"})
                            return

                        args = pending_tool.get("arguments", {}) or {}
                        name = args.get("name")
                        email = args.get("email")
                        message = args.get("message")

                        if not (name and email and message):
                            final_text = "信息不全：需要 name/email/message 才能发送。" if req.locale == "zh" \
                                else "Missing fields: name/email/message are required."
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
                            final_text = "已发送给我们的团队，我们会尽快联系你。" if req.locale == "zh" \
                                else "Sent to our team. We’ll get back to you shortly."
                            yield sse({
                                "type": "final",
                                "text": final_text,
                                "action": "send_inquiry",
                                "action_data": {"inquiry_id": send_result["inquiry_id"], "ses": send_result["ses"]},
                            })
                        else:
                            final_text = (
                                "邮件发送失败（我们已记录你的信息）。请稍后再试，或直接通过网站联系方式联系我们。\n"
                                f"错误信息：{send_result['error']}"
                            ) if req.locale == "zh" else (
                                "Email sending failed (we have saved your message). Please try again later or contact us via the website.\n"
                                f"Error: {send_result['error']}"
                            )
                            yield sse({
                                "type": "final",
                                "text": final_text,
                                "action": "send_inquiry_failed",
                                "action_data": {"inquiry_id": send_result["inquiry_id"], "error": send_result["error"]},
                            })

                        yield sse({"type": "done"})
                        return

                    # 没 tool call
                    yield sse({"type": "final", "text": "".join(assistant_text_chunks).strip()})
                    yield sse({"type": "done"})
                    return

        except GeneratorExit:
            # ✅ 客户端断开会触发；别当错误
            logger.warning("SSE client disconnected (GeneratorExit)")
            return
        except Exception as e:
            logger.exception("chat_stream error")
            yield sse({"type": "error", "message": str(e)})
            return

    return StreamingResponse(gen(), media_type="text/event-stream")