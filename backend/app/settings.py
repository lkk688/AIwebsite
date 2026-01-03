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

    # ---- OpenAI (API KEY 建议必填) ----
    openai_api_key: str = Field(alias="OPENAI_API_KEY")               # ✅ 无默认值：必须从 env 来
    openai_base_url: str = Field(default="https://api.openai.com/v1", alias="OPENAI_BASE_URL")

    # ---- LiteLLM (只有切换时才用，所以可以 Optional) ----
    litellm_api_key: Optional[str] = Field(default=None, alias="LITELLM_API_KEY")
    litellm_api_base: Optional[str] = Field(default=None, alias="LITELLM_API_BASE")
    litellm_model: Optional[str] = Field(default=None, alias="LITELLM_MODEL")

    # ---- Data (建议也从 env 来，但可给默认) ----
    data_dir: str = Field(default="../src/data", alias="DATA_DIR")

    # ---- AWS SES（生产建议必填；本地可 Optional）----
    aws_region: str = Field(default="us-west-2", alias="AWS_REGION")
    aws_access_key_id: Optional[str] = Field(default=None, alias="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: Optional[str] = Field(default=None, alias="AWS_SECRET_ACCESS_KEY")
    ses_from_email: Optional[str] = Field(default=None, alias="SES_FROM_EMAIL")
    ses_to_email: Optional[str] = Field(default=None, alias="SES_TO_EMAIL")
    ses_configuration_set: Optional[str] = Field(default=None, alias="SES_CONFIGURATION_SET")


settings = Settings()