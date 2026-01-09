from __future__ import annotations

import time
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict

logger = logging.getLogger("jwl.state")

# - manage server-side session data using a UUID ( conversation_id ).
# - Implemented an LRU (Least Recently Used) cache to store conversation history, slots (e.g., name, email), and summaries.
# - This allows the LLM to remember context across multiple messages without requiring the frontend to send the entire history every time.

@dataclass
class ConversationState:
    """
    State object for a single conversation (keyed by UUID).
    """
    conversation_id: str
    locale: str = "en"
    # Compact summary of the conversation so far (to inject into system prompt)
    summary: str = ""
    # Extracted slots (name, email, product_interest, etc.)
    slots: Dict[str, Any] = field(default_factory=dict)
    # The last N raw messages (to keep immediate context fresh)
    recent_turns: List[Dict[str, str]] = field(default_factory=list)
    # Timestamp of last update (for TTL/LRU)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ConversationState:
        return cls(**data)


class LRUConversationStore:
    """
    In-memory LRU cache for ConversationState.
    """
    def __init__(self, max_items: int = 2000, ttl_seconds: int = 86400):
        self.max_items = max_items
        self.ttl_seconds = ttl_seconds
        # Dict[conversation_id, ConversationState]
        self._store: Dict[str, ConversationState] = {}
        # List of conversation_ids in access order (MRU at end)
        self._access_order: List[str] = []

    def get_or_create(self, conversation_id: str, locale: str = "en") -> ConversationState:
        now = time.time()
        
        if conversation_id in self._store:
            st = self._store[conversation_id]
            # Check TTL
            if now - st.updated_at > self.ttl_seconds:
                del self._store[conversation_id]
                if conversation_id in self._access_order:
                    self._access_order.remove(conversation_id)
            else:
                # Move to end (MRU)
                if conversation_id in self._access_order:
                    self._access_order.remove(conversation_id)
                self._access_order.append(conversation_id)
                # Update locale if changed? Maybe keep original. 
                # Let's assume locale might update if user switches language.
                if locale and locale != st.locale:
                    st.locale = locale
                return st

        # Create new
        new_st = ConversationState(conversation_id=conversation_id, locale=locale)
        self.upsert(new_st)
        return new_st

    def upsert(self, state: ConversationState) -> None:
        cid = state.conversation_id
        state.updated_at = time.time()
        
        if cid in self._store:
            if cid in self._access_order:
                self._access_order.remove(cid)
        else:
            # Evict if full
            if len(self._store) >= self.max_items:
                lru_id = self._access_order.pop(0)
                if lru_id in self._store:
                    del self._store[lru_id]
        
        self._store[cid] = state
        self._access_order.append(cid)


def update_state_from_messages(state: ConversationState, messages: List[Dict[str, str]]) -> ConversationState:
    """
    Updates the state with new messages.
    - Appends to recent_turns
    - (Future) Could call LLM to update summary/slots here or in background
    """
    # Simple logic: just append new messages to recent_turns
    # Deduplication logic might be needed if frontend sends full history every time
    
    # We assume 'messages' contains the FULL history from frontend or just new ones?
    # If frontend sends full history, we need to detect what's new.
    # But usually chat APIs receive full history in 'messages'.
    # 
    # STRATEGY:
    # If the user sends full history, we can just replace recent_turns or take the last N.
    # But we want to maintain summary.
    # 
    # For this implementation, let's assume `messages` is the FULL history for the current request context.
    # We will store the last N messages in `recent_turns`.
    # `summary` and `slots` would be updated by a separate process (not implemented here to save latency, 
    # or implemented as a simple heuristic).
    
    # Heuristic slot extraction (simple regex)
    # This is a placeholder for real extraction logic
    import re
    text_combined = " ".join([m.get("text", "") for m in messages if m.get("role") == "user"])
    
    # Extract email
    email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", text_combined)
    if email_match:
        state.slots["email"] = email_match.group(0)
        
    # Extract potential name (improved)
    # 1. "Name: X"
    name_match = re.search(r"(?:name|contact)[\s]*[:\-is]+[\s]*([A-Z][a-zA-Z]+(?: [A-Z][a-zA-Z]+)?)", text_combined, re.IGNORECASE)
    if name_match:
        state.slots["name"] = name_match.group(1)
    else:
        # 2. "I am X", "My name is X"
        name_match = re.search(r"(?:my name is|i am) ([A-Z][a-zA-Z]+(?: [A-Z][a-zA-Z]+)?)", text_combined, re.IGNORECASE)
        if name_match:
            state.slots["name"] = name_match.group(1)
        
    # Confirm send - Only check the LATEST user message to avoid sticky state
    # We shouldn't use text_combined for this, as it includes history.
    last_user_msg = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            last_user_msg = m.get("text", "")
            break
            
    if re.search(r"(confirm|send it|yes|ok|sure|please do)", last_user_msg, re.IGNORECASE):
        state.slots["confirm_send"] = True
    else:
        # If the user says something else (like a new question), reset confirmation
        # This prevents "What else can you do?" from being treated as confirmation state
        state.slots["confirm_send"] = False
        
    # Reset confirm_send if user says "thank you" or indicates completion (redundant but safe)
    if re.search(r"(thank you|thanks|done|finished|bye)", last_user_msg, re.IGNORECASE):
        state.slots["confirm_send"] = False

    # Update recent turns (keep last 20)
    state.recent_turns = messages[-20:]
    
    return state
