from dataclasses import dataclass, field
from typing import Any, Dict, Optional

@dataclass
class ToolContext:
    """
    Context passed to tool handlers during execution.
    Contains references to necessary backend services.
    """
    store: Any           # DataStore
    mailer: Any          # SesMailer
    locale: str = "en"
    user: Optional[Dict[str, Any]] = None
    conversation_id: Optional[str] = None
    settings: Any = None
    slots: Dict[str, Any] = field(default_factory=dict)
    active_product: Optional[Dict[str, str]] = None
    session_logger: Any = None
