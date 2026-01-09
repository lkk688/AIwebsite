import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import setup_logging
from app.adapters.db import init_db
from app.api.routes import chat, general

setup_logging()
logger = logging.getLogger("jwl.main")

app = FastAPI(title="JWL Travel Gear API")

# Initialize DB
init_db()

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
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])

@app.on_event("startup")
async def startup_event():
    logger.info("Application starting up...")
    # Optional: trigger heavy RAG loading here if desired
    # from app.core.services import init_product_rag, store, embedder
    # init_product_rag(store.products, embedder)

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Application shutting down...")
