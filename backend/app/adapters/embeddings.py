from __future__ import annotations
from typing import List
from app.core.config import settings

class EmbeddingsClient:
    def __init__(self):
        self.backend = settings.embeddings_backend
        self.model = settings.embeddings_model

        if self.backend == "openai":
            from openai import OpenAI
            self.client = OpenAI(
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url,
            )
        else:
            import litellm
            self.litellm = litellm

    def embed(self, texts: List[str]) -> List[List[float]]:
        """
        Return embeddings aligned with `texts`.
        """
        if self.backend == "openai":
            # OpenAI embeddings batch
            resp = self.client.embeddings.create(
                model=self.model,
                input=texts,
            )
            # resp.data[i].embedding
            return [d.embedding for d in resp.data]

        # LiteLLM embeddings (provider-dependent)
        resp = self.litellm.embedding(
            model=self.model,
            input=texts,
            api_key=settings.litellm_api_key,
            api_base=settings.litellm_api_base,
        )
        # resp["data"][i]["embedding"]
        return [d["embedding"] for d in resp["data"]]