import pytest
from unittest.mock import MagicMock
from app.tools.dispatcher import ToolDispatcher
from app.tools.base import ToolContext
from app.tools.registry import ToolRegistry
from app.products.resolve import get_resolver

# Mock Data
MOCK_PRODUCTS = [
    {
        "id": "jwl-outdoor-018",
        "slug": "multi-day-hiking-backpack",
        "name": {"en": "Multi-day Hiking Backpack"},
    },
    {
        "id": "other-bag-002",
        "slug": "other-bag",
        "name": {"en": "Other Bag"},
    }
]

@pytest.fixture
def setup_dispatcher():
    # Setup resolver
    get_resolver(MOCK_PRODUCTS)
    
    # Setup registry with send_inquiry
    config = {
        "tools": {
            "send_inquiry": {
                "handler": "send_inquiry",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "email": {"type": "string"},
                        "message": {"type": "string"},
                        "product_id": {"type": "string"},
                        "product_slug": {"type": "string"}
                    },
                    "required": ["name", "email", "message"]
                }
            }
        }
    }
    registry = ToolRegistry(config)
    dispatcher = ToolDispatcher(registry)
    
    # Register mock handler
    mock_handler = MagicMock()
    mock_handler.return_value = {"success": True}
    dispatcher.register("send_inquiry", mock_handler)
    
    return dispatcher, mock_handler

def test_injection_missing_product(setup_dispatcher):
    dispatcher, mock_handler = setup_dispatcher
    
    # Context with active product
    ctx = ToolContext(
        store=MagicMock(),
        mailer=None,
        locale="en",
        active_product={"id": "jwl-outdoor-018", "slug": "multi-day-hiking-backpack"}
    )
    
    # Call tool without product args
    args = {
        "name": "Test User",
        "email": "test@example.com",
        "message": "I want this."
    }
    
    dispatcher.dispatch("send_inquiry", args, ctx)
    
    # Verify handler called with injected product
    call_args = mock_handler.call_args[1]
    assert call_args["product_id"] == "jwl-outdoor-018"
    assert call_args["product_slug"] == "multi-day-hiking-backpack"

def test_injection_override_wrong_product(setup_dispatcher):
    dispatcher, mock_handler = setup_dispatcher
    
    # Context with active product (pinned)
    ctx = ToolContext(
        store=MagicMock(),
        mailer=None,
        locale="en",
        active_product={"id": "jwl-outdoor-018", "slug": "multi-day-hiking-backpack"}
    )
    
    # Call tool with DIFFERENT product (drift)
    args = {
        "name": "Test User",
        "email": "test@example.com",
        "message": "I want this.",
        "product_id": "other-bag-002", # LLM hallucinated or drifted
        "product_slug": "other-bag"
    }
    
    dispatcher.dispatch("send_inquiry", args, ctx)
    
    # Verify handler called with PINNED product (override)
    # CURRENTLY this might fail if logic is "if not resolved"
    call_args = mock_handler.call_args[1]
    assert call_args["product_id"] == "jwl-outdoor-018"
    assert call_args["product_slug"] == "multi-day-hiking-backpack"
