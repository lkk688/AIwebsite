import logging
from typing import Any, Dict, List, Optional
from .base import ToolContext
from app.product_search import search_products
from app.db import insert_inquiry, mark_inquiry_sent, mark_inquiry_failed
from app.settings import settings
from app.product_rag import get_product_rag

logger = logging.getLogger("jwl.tools.handlers")

def handle_get_product_details(ctx: ToolContext, product_id: str) -> Dict[str, Any]:
    """
    Fetches full details of a product.
    """
    logger.info(f"Tool Exec: get_product_details id='{product_id}'")
    try:
        rag = get_product_rag()
        p = rag.get_product_by_id(product_id)
        if not p:
            return {"error": f"Product not found: {product_id}"}
        
        # Return full dict, maybe sanitize or format?
        # The LLM is smart enough to read JSON.
        return {"product": p}
    except Exception as e:
        logger.error(f"Error fetching product details: {e}")
        return {"error": str(e)}

def handle_product_search(ctx: ToolContext, query: str, limit: int = 5) -> Dict[str, Any]:
    """
    Executes product search.
    """
    logger.info(f"Tool Exec: product_search query='{query}' limit={limit} locale={ctx.locale}")
    
    # Use semantic search if enabled in settings
    semantic = False
    if ctx.settings:
        semantic = getattr(ctx.settings, "enable_semantic_search", False)
        
    results = search_products(
        products=ctx.store.products,
        query=query,
        locale=ctx.locale,
        limit=limit,
        semantic=semantic
    )
    
    return {
        "query": query,
        "results": results
    }

def handle_send_inquiry(
    ctx: ToolContext, 
    name: str, 
    email: str, 
    message: str, 
    product_id: Optional[str] = None,
    product_slug: Optional[str] = None,
    source: str = "chat_tool"
) -> Dict[str, Any]:
    """
    Handles sending an inquiry email + DB persistence.
    """
    logger.info(f"Tool Exec: send_inquiry name='{name}' email='{email}' pid='{product_id}' source='{source}'")
    
    # Append product info to message if present
    full_message = message
    if product_id or product_slug:
        full_message += "\n\n" + "="*30 + "\n[Related Product Context]\n"
        if product_id:
            full_message += f"Product ID: {product_id}\n"
        if product_slug:
            full_message += f"Product Slug: {product_slug}\n"
        full_message += "="*30
    
    # 1. DB Insert
    try:
        inquiry_id = insert_inquiry(
            name=name,
            email=email,
            message=full_message,
            source=source,
            locale=ctx.locale,
            meta={"ua": "backend-tool", "product_id": product_id, "product_slug": product_slug}
        )
        if hasattr(ctx, "session_logger") and ctx.session_logger:
            ctx.session_logger.info(f"DB INSERT: Inquiry saved with ID {inquiry_id}")
    except Exception as e:
        logger.error(f"Failed to insert inquiry to DB: {e}")
        if hasattr(ctx, "session_logger") and ctx.session_logger:
            ctx.session_logger.error(f"DB INSERT FAILED: {e}")
        return {"ok": False, "error": "Database error"}

    # 2. Send Email (if mailer is available)
    if not ctx.mailer:
        if hasattr(ctx, "session_logger") and ctx.session_logger:
            ctx.session_logger.warning("EMAIL SEND SKIP: Mailer not configured")
        return {
            "ok": True, 
            "inquiry_id": inquiry_id, 
            "ses": None, 
            "note": "Mailer not configured"
        }

    try:
        ses_resp = ctx.mailer.send_inquiry(name, email, full_message)
        ses_message_id = ses_resp.get("messageId") if isinstance(ses_resp, dict) else None
        mark_inquiry_sent(inquiry_id, ses_message_id or "")
        
        if hasattr(ctx, "session_logger") and ctx.session_logger:
            ctx.session_logger.info(f"EMAIL SENT: MessageId {ses_message_id}")
            
        return {
            "ok": True,
            "inquiry_id": inquiry_id,
            "ses": ses_resp,
            "error": None
        }
    except Exception as e:
        err_msg = str(e)
        logger.error(f"Failed to send SES email: {err_msg}")
        if hasattr(ctx, "session_logger") and ctx.session_logger:
            ctx.session_logger.error(f"EMAIL SEND FAILED: {err_msg}")
        mark_inquiry_failed(inquiry_id, err_msg)
        return {
            "ok": False,
            "inquiry_id": inquiry_id,
            "ses": None,
            "error": err_msg
        }
