from typing import Any, Dict, List, Optional
from pydantic import BaseModel, EmailStr

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
