from fastapi import APIRouter, Query
from app.api.schemas import EmailRequest
from app.core.config import settings
from app.core.services import store, mailer
from app.tools.base import ToolContext
from app.services.chat.service import ChatService # Need dispatcher
# Accessing chat_service from core.services to avoid circular imports if possible
from app.core.services import chat_service
from app.services.product import search_products

router = APIRouter()

@router.get("/health")
async def health():
    """
    Health check endpoint.
    """
    return {"status": "ok", "products_loaded": len(store.products), "llm_backend": settings.llm_backend}


@router.post("/send-email")
async def send_email(req: EmailRequest):
    """
    Send an email via SES and record it in the database.
    """
    ctx = ToolContext(store=store, mailer=mailer, locale=req.locale, settings=settings)
    # Use dispatcher from chat_service
    result = chat_service.dispatcher.dispatch(
        "send_inquiry",
        {
            "name": req.name,
            "email": str(req.email),
            "message": req.message,
            "source": "api/send-email"
        },
        ctx
    )

    if result["ok"]:
        return {"status": "success", "inquiry_id": result["inquiry_id"], "ses": result.get("ses")}
    else:
        return {
            "status": "failed",
            "inquiry_id": result.get("inquiry_id"),
            "error": result.get("error"),
        }


@router.post("/inquiry")
async def submit_inquiry(req: EmailRequest):
    """
    Submit an inquiry. This endpoint stores the inquiry in the database ONLY.
    """
    # Pass mailer=None to skip sending email
    ctx = ToolContext(store=store, mailer=None, locale=req.locale, settings=settings)
    result = chat_service.dispatcher.dispatch(
        "send_inquiry",
        {
            "name": req.name,
            "email": str(req.email),
            "message": req.message,
            "source": "api/inquiry"
        },
        ctx
    )

    if result["ok"]:
        return {"status": "success", "inquiry_id": result["inquiry_id"], "ses": None}
    else:
        return {
            "status": "failed",
            "inquiry_id": result.get("inquiry_id"),
            "error": result.get("error"),
        }

@router.get("/products/search")
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
