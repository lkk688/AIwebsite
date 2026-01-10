import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import setup_logging
from app.adapters.db import init_db
from app.adapters import db
from app.core import security
from app.api.routes import chat, general, admin, auth

setup_logging()
logger = logging.getLogger("jwl.main")

app = FastAPI(title="JWL Travel Gear API")

# Initialize DB
init_db()

# Create default admin if not exists
try:
    existing_admin = db.get_user_by_username("admin")
    if not existing_admin:
        hashed_pw = security.get_password_hash("admin123")
        db.create_user("admin", hashed_pw, is_superuser=True)
        logger.info("Created default admin user: admin / admin123")
except Exception as e:
    logger.error(f"Failed to check/create admin user: {e}")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(general.router, prefix="/api", tags=["General"])
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])

@app.on_event("startup")
async def startup_event():
    logger.info("Application starting up...")
    # Optional: trigger heavy RAG loading here if desired
    # from app.core.services import init_product_rag, store, embedder
    # init_product_rag(store.products, embedder)

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Application shutting down...")
