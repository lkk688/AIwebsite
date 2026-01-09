from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Literal, Optional

import os
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))  # backend/
ENV_PATH = os.path.join(BASE_DIR, ".env")

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_PATH, #".env",
        env_file_encoding="utf-8",
        extra="ignore",          # ✅ 忽略 env 里多余旧字段
        case_sensitive=False,
    )

    # ---- backend switch (给默认值可以) ----
    llm_backend: Literal["openai", "litellm"] = Field(default="openai", alias="LLM_BACKEND")
    llm_model: str = Field(default="gpt-4.1-mini", alias="LLM_MODEL")
    # Selection for model prompt style: "default", "deepseek", "qwen", etc.
    model_type: str = Field(default="default", alias="MODEL_TYPE")

    # ---- OpenAI (API KEY 建议必填) ----
    openai_api_key: str = Field(alias="OPENAI_API_KEY")               # ✅ 无默认值：必须从 env 来
    openai_base_url: str = Field(default="https://api.openai.com/v1", alias="OPENAI_BASE_URL")

    # ---- LiteLLM (只有切换时才用，所以可以 Optional) ----
    litellm_api_key: Optional[str] = Field(default=None, alias="LITELLM_API_KEY")
    litellm_api_base: Optional[str] = Field(default=None, alias="LITELLM_API_BASE")
    litellm_model: Optional[str] = Field(default=None, alias="LITELLM_MODEL")

    # ---- Data (建议也从 env 来，但可给默认) ----
    data_dir: str = Field(default="../src/data", alias="DATA_DIR")

    #new add embeddings
    embeddings_backend: Literal["openai", "litellm"] = Field(default="openai", alias="EMBEDDINGS_BACKEND")
    embeddings_model: str = Field(default="text-embedding-3-small", alias="EMBEDDINGS_MODEL")

    # OpenAI embeddings
    openai_api_key: str = Field(alias="OPENAI_API_KEY")
    openai_base_url: str = Field(default="https://api.openai.com/v1", alias="OPENAI_BASE_URL")

    # LiteLLM embeddings（走本地/多provider）
    litellm_api_key: Optional[str] = Field(default=None, alias="LITELLM_API_KEY")
    litellm_api_base: Optional[str] = Field(default=None, alias="LITELLM_API_BASE")

    # ---- AWS SES（生产建议必填；本地可 Optional）----
    aws_region: str = Field(default="us-west-2", alias="AWS_REGION")
    aws_access_key_id: Optional[str] = Field(default=None, alias="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: Optional[str] = Field(default=None, alias="AWS_SECRET_ACCESS_KEY")
    ses_from_email: Optional[str] = Field(default=None, alias="SES_FROM_EMAIL")
    ses_to_email: Optional[str] = Field(default=None, alias="SES_TO_EMAIL")
    ses_configuration_set: Optional[str] = Field(default=None, alias="SES_CONFIGURATION_SET")

    # ---- Features ----
    enable_semantic_search: bool = Field(default=True, alias="ENABLE_SEMANTIC_SEARCH")
    
    # Thresholds
    # Lexical: count of matched keywords + boost. Default 1.0 means at least one match.
    lexical_min_score_threshold: float = Field(default=1.0, alias="LEXICAL_MIN_SCORE_THRESHOLD")
    
    # Semantic: Cosine similarity (0.0 to 1.0). 
    # 0.25 is a reasonable default for "somewhat relevant". 0.5 is "very relevant".
    semantic_min_score_threshold: float = Field(default=0.25, alias="SEMANTIC_MIN_SCORE_THRESHOLD")
    
    # High Relevance Semantic Threshold: Cosine similarity (0.0 to 1.0).
    # Items with semantic score above this are considered "High Relevance" (shown initially).
    # Default 0.45 corresponds to a strong semantic match.
    semantic_high_relevance_threshold: float = Field(default=0.45, alias="SEMANTIC_HIGH_RELEVANCE_THRESHOLD")

    # Relevance threshold for UI "Show More" feature
    # Items with LEXICAL score >= this value will be marked as "high" relevance
    search_relevance_threshold: float = Field(default=4.0, alias="SEARCH_RELEVANCE_THRESHOLD")

    # Vector Index Backend
    vector_index_type: Literal["numpy", "faiss"] = Field(default="numpy", alias="VECTOR_INDEX_TYPE")

    # Knowledge Base
    kb_data_dir: str = Field(default="../src/data/kb", alias="KB_DATA_DIR")
    kb_context_file: str = Field(default="../src/data/websiteinfo.json", alias="KB_CONTEXT_FILE")

    # Logging
    log_dir: str = Field(default="logs/", alias="LOG_DIR")

    # Prompt Engineering
    desc_max_len: int = Field(default=150, alias="DESC_MAX_LEN")  # Limit product description length in RAG context


settings = Settings()