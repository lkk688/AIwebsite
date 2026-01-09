from app.core.config import settings
from app.services.data import DataStore
from app.adapters.llm import LLMClient
from app.adapters.embeddings import EmbeddingsClient
from app.services.chat.service import ChatService
from app.adapters.email import SesMailer
from app.services.rag.product import init_product_rag
from app.services.rag.kb import init_kb_rag

# Initialize Singletons
store = DataStore(settings.data_dir)
llm = LLMClient()
embedder = EmbeddingsClient()
chat_service = ChatService(store, embedder)

# RAG Initialization
# Note: These might be slow, maybe trigger in startup event?
# For now, keeping as is.
init_product_rag(store.products, embedder)
init_kb_rag(embedder)

mailer = SesMailer(
    region=settings.aws_region,
    access_key_id=settings.aws_access_key_id,
    secret_access_key=settings.aws_secret_access_key,
    from_email=settings.ses_from_email,
    to_email=settings.ses_to_email,
    configuration_set=settings.ses_configuration_set,
)
