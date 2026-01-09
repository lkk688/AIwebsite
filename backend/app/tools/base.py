from dataclasses import dataclass
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
    settings: Any = None
