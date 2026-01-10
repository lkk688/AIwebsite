import pytest
import json
from unittest.mock import MagicMock, patch
from typing import Dict, Any, List

from app.services.chat.service import ChatService
from app.services.chat.state import ConversationState
from app.tools.base import ToolContext
from app.tools.schemas import create_tool_validator
from pydantic import ValidationError

# Mock Data
MOCK_PRODUCTS = [
    {
        "id": "jwl-outdoor-018",
        "slug": "multi-day-hiking-backpack",
        "name": {"en": "Multi-day Hiking Backpack", "zh": "多日徒步背包"},
        "category": "Backpacks",
        "description": {"en": "Great for hiking", "zh": "适合徒步"},
        "tags": ["hiking", "outdoor"]
    },
    {
        "id": "jwl-lunch-001",
        "slug": "insulated-lunch-bag",
        "name": {"en": "Insulated Lunch Bag", "zh": "保温午餐包"},
        "category": "Lunch Bags",
        "tags": ["lunch", "food"]
    }
]

@pytest.fixture
def mock_store():
    store = MagicMock()
    store.products = MOCK_PRODUCTS
    store.website_info = {}
    return store

@pytest.fixture
def mock_embedder():
    return MagicMock()

@pytest.fixture
def chat_service(mock_store, mock_embedder):
    # Patch get_product_rag in both service and handlers
    with patch("app.services.chat.service.get_product_rag") as mock_rag_getter, \
         patch("app.tools.handlers.get_product_rag") as mock_rag_getter_handlers:
        
        mock_rag = MagicMock()
        mock_rag.get_product_by_id.side_effect = lambda pid: next((p for p in MOCK_PRODUCTS if p["id"] == pid), None)
        mock_rag_getter.return_value = mock_rag
        mock_rag_getter_handlers.return_value = mock_rag
        
        # Patch build_rag_context to simulate TopK
        with patch("app.services.chat.service.build_rag_context") as mock_build_rag:
            mock_build_rag.return_value = {"context": "MOCK CONTEXT", "mode": "search", "hits_summary": []}
            
            # Patch get_kb_rag
            with patch("app.services.chat.service.get_kb_rag") as mock_kb_getter:
                mock_kb = MagicMock()
                mock_kb.retrieve.return_value = []
                mock_kb_getter.return_value = mock_kb
                
                # Patch DB insert to avoid DB writes
                with patch("app.tools.handlers.insert_inquiry") as mock_db:
                    mock_db.return_value = "mock_inquiry_id"
                
                    service = ChatService(mock_store, mock_embedder)
                    # Mock intent router to avoid numpy errors
                    service.intent_router = MagicMock()
                    service.intent_router.route.return_value = None
                    
                    # Override config for tests with FULL structure required by dynamic logic
                    service.config = {
                        "tools": {
                            "get_product_details": {
                                "handler": "get_product_details",
                                "parameters": {"properties": {"product_id": {"type": "string"}}, "required": ["product_id"]}
                            },
                            "send_inquiry": {
                                "handler": "send_inquiry",
                                "parameters": {
                                    "properties": {
                                        "name": {"type": "string"},
                                        "email": {"type": "string"},
                                        "message": {"type": "string"},
                                        "product_id": {"type": "string"},
                                        "product_slug": {"type": "string"},
                                        "meta": {"type": "object"}
                                    },
                                    "required": ["name", "email", "message"],
                                    "additionalProperties": False
                                }
                            }
                        },
                        "routing_rules": {},
                        "model_prompts": {"default": {"en": {"role": "You are AI"}}},
                        "state_management": {
                            "confirmation_slot": "confirm_send",
                            "confirmation_keywords": {
                                "strong": {"en": ["send it", "confirm send"]},
                                "weak": {"en": ["ok", "yes"]},
                                "ask_confirm": {"en": ["confirm sending?"]}
                            }
                        },
                        "ui_labels": {
                            "current_product": {"en": "[Current Focus Product]"},
                            "conversation_summary": {"en": "Summary"},
                            "conversation_slots": {"en": "Slots"}
                        },
                        "tool_responses": {
                            "confirm_needed": {"en": "Confirm?"},
                            "missing_info": {"en": "Missing info"},
                            "success": {"en": "Sent"},
                            "failure": {"en": "Failed"}
                        }
                    }
                    
                    # Re-initialize registry with test config to populate _tools correctly
                    from app.tools.registry import ToolRegistry
                    service.tool_registry = ToolRegistry(service.config)
                    # Update dispatcher's registry reference
                    service.dispatcher.registry = service.tool_registry
                    
                    # Need to init resolver with products
                    from app.products.resolve import get_resolver
                    get_resolver(MOCK_PRODUCTS)
                    
                    yield service

# Test A: active_product set via get_product_details
def test_active_product_set_via_tool(chat_service):
    # Simulate tool execution
    ctx = ToolContext(store=chat_service.store, mailer=None, locale="en", conversation_id="test_conv_a")
    
    # 1. Execute tool
    res = chat_service.process_tool_call(
        "get_product_details", 
        {"product_id": "jwl-outdoor-018"}, 
        ctx
    )
    assert res["success"] is True
    
    # 2. Check State
    st = chat_service.state_store.get_or_create("test_conv_a")
    assert st.active_product is not None
    assert st.active_product["id"] == "jwl-outdoor-018"
    assert st.active_product["slug"] == "multi-day-hiking-backpack"

# Test B: material question uses active_product and does NOT run product TopK
def test_drift_proof_retrieval(chat_service):
    cid = "test_conv_b"
    # Set active product
    st = chat_service.state_store.get_or_create(cid)
    st.active_product = {"id": "jwl-outdoor-018", "slug": "multi-day-hiking-backpack"}
    chat_service.state_store.upsert(st)
    
    # User asks material (product question)
    msgs = [{"role": "user", "text": "What is the material?"}]
    
    with patch("app.services.chat.service.build_rag_context") as mock_search:
        mock_search.return_value = {"context": "", "mode": "search"} # Should NOT be called or ignored
        
        # Prepare messages
        payload = chat_service.prepare_llm_messages(msgs, "en", conversation_id=cid)
        
        # mock_search (build_rag_context) should NOT be called because we lock context
        mock_search.assert_not_called()
        
        # The system content should contain the locked product title
        sys_content = payload["messages"][0]["content"]
        assert "[Current Focus Product]" in sys_content
        assert "Multi-day Hiking Backpack" in sys_content

# Test C: quote flow confirm + missing fields only
def test_confirmation_gating_and_slot_filling(chat_service):
    cid = "test_conv_c"
    
    # 1. User asks quote
    msgs = [{"role": "user", "text": "I want to order 1000 pcs"}]
    chat_service.prepare_llm_messages(msgs, "en", conversation_id=cid)
    
    # 2. Assistant asks confirm (Simulated history)
    chat_service.persist_turn(cid, "assistant", "Do you confirm sending?", "en")
    
    # 3. User confirms and gives name
    msgs.append({"role": "assistant", "text": "Do you confirm sending?"})
    msgs.append({"role": "user", "text": "Yes, send it. I am Liu Kaikai"})
    
    # This should trigger state machine -> confirm_send=True
    chat_service.prepare_llm_messages(msgs, "en", conversation_id=cid)
    
    st = chat_service.state_store.get_or_create(cid)
    assert st.slots.get("confirm_send") is True
    
    # 4. Tool call with missing email
    # LLM calls send_inquiry (simulated)
    ctx = ToolContext(store=chat_service.store, mailer=None, locale="en", conversation_id=cid, slots=st.slots, active_product=st.active_product)
    
    # Missing email -> should skip
    res = chat_service.process_tool_call(
        "send_inquiry",
        {"name": "Liu Kaikai", "message": "1000 pcs"}, # missing email
        ctx
    )
    assert res["success"] is False
    assert res["skip_reason"] == "missing_fields"
    
    # 5. User provides email
    msgs.append({"role": "assistant", "text": "Email?"})
    msgs.append({"role": "user", "text": "lkk688@gmail.com"})
    chat_service.prepare_llm_messages(msgs, "en", conversation_id=cid) # Updates state if we had extractor
    
    # Assuming LLM now calls tool with all fields
    res = chat_service.process_tool_call(
        "send_inquiry",
        {
            "name": "Liu Kaikai", 
            "email": "lkk688@gmail.com", 
            "message": "1000 pcs",
            "product_id": "jwl-outdoor-018",
            "product_slug": "multi-day-hiking-backpack"
        },
        ctx
    )
    assert res["success"] is True
    
    # Check slots updated
    st = chat_service.state_store.get_or_create(cid)
    assert st.slots["name"] == "Liu Kaikai"
    assert st.slots["email"] == "lkk688@gmail.com"
    assert st.slots["confirm_send"] is False # Reset after success

# Test D: schema forbids extra args
def test_schema_extra_forbid(chat_service):
    ctx = ToolContext(store=chat_service.store, mailer=None, locale="en")
    
    # Attempt to call with 'hacker_field' which is forbidden by schema
    res = chat_service.process_tool_call(
        "send_inquiry",
        {
            "name": "Test",
            "email": "test@test.com",
            "message": "msg",
            "hacker_field": "hacker" # Forbidden
        },
        ctx
    )
    assert res["success"] is False
    assert "Validation Error" in str(res.get("system_msg") or res.get("error") or str(res))
    
# Test F: Backend confirmation logic
def test_backend_confirmation_logic(chat_service):
    # Strong confirmation
    assert chat_service.is_confirm_send("send it", "en") is True
    assert chat_service.is_confirm_send("confirm send", "en") is True
    
    # Weak confirmation without "send" -> False
    assert chat_service.is_confirm_send("ok", "en") is False
    assert chat_service.is_confirm_send("yes", "en") is False
    
    # Weak confirmation with "send" -> True
    assert chat_service.is_confirm_send("yes send", "en") is True
    
    # Irrelevant text -> False
    assert chat_service.is_confirm_send("hello", "en") is False

# Test G: Active Product Pinning (Drift Prevention)
def test_active_product_pinning(chat_service):
    cid = "test_conv_g"
    
    # 1. Set active product
    st = chat_service.state_store.get_or_create(cid)
    st.active_product = {"id": "jwl-outdoor-018", "slug": "multi-day-hiking-backpack"}
    chat_service.state_store.upsert(st)
    
    # 2. User confirms (Quote intent)
    msgs = [{"role": "user", "text": "Yes, send it."}]
    
    # Mock retrieval to ensure we don't call it
    with patch("app.services.chat.service.build_rag_context") as mock_search:
        mock_search.return_value = {"context": "WRONG CONTEXT", "mode": "search"}
        
        # Prepare messages
        res = chat_service.prepare_llm_messages(msgs, "en", conversation_id=cid)
        
        # Should NOT call search because we are in confirm/quote stage with active product
        # Wait, intent router might return 'quote_order' or 'context_aware'
        # Let's ensure our mock intent router returns quote_order if needed, 
        # but pure keyword "Yes send it" might trigger 'context_aware' or 'quote_order'.
        
        # Check system content
        sys_content = res["messages"][0]["content"]
        assert "[Current Focus Product]" in sys_content
        assert "Multi-day Hiking Backpack" in sys_content
        assert "WRONG CONTEXT" not in sys_content
