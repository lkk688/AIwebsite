#负责：用 embedding 做 意图/路由（更通用），输出 route plan。
#数据来源：chat_config.json 的 intent_examples（可配），没配就用默认。

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from ..embeddings_client import EmbeddingsClient
from ..vector_index import get_vector_index, VectorIndex
from ..settings import settings

logger = logging.getLogger("jwl.intent_router")


@dataclass
class IntentResult:
    intent: str
    score: float
    is_broad: bool
    is_tech: bool


class EmbeddingIntentRouter:
    """
    A lightweight intent router using embeddings.

    - Load intent examples from config:
      {
        "intent_examples": {
          "broad_product": ["Do you have backpacks?", "..."],
          "technical": ["What is TPU coating?", "..."],
          "quote_order": ["I need 1000 units quote", "..."],
          ...
        },
        "intent_mapping": {
          "broad_product": {"is_broad": true, "is_tech": false},
          "technical": {"is_broad": false, "is_tech": true},
          "quote_order": {"is_broad": false, "is_tech": false}
        }
      }

    - We compute one centroid vector per intent (mean of example embeddings).
    - Search with VectorIndex (numpy/faiss) for speed.
    """

    def __init__(self, embedder: EmbeddingsClient, config: Dict[str, Any]):
        self.embedder = embedder
        self.config = config or {}

        self._intent_names: List[str] = []
        self._intent_vecs: Optional[np.ndarray] = None
        self._index: VectorIndex = get_vector_index(getattr(settings, "vector_index_type", "numpy"))

        self._built = False

    def build(self) -> None:
        if self._built:
            return

        t0 = time.time()
        examples = self._get_intent_examples()
        if not examples:
            logger.warning("No intent examples configured; router will fallback to defaults.")
            examples = self._default_intent_examples()

        intent_names = sorted(examples.keys())
        centroids: List[np.ndarray] = []

        # Compute centroid per intent
        for intent in intent_names:
            sents = [x for x in (examples.get(intent) or []) if isinstance(x, str) and x.strip()]
            if not sents:
                continue
            vecs = self.embedder.embed(sents)  # List[List[float]]
            mat = np.array(vecs, dtype=np.float32)
            centroid = mat.mean(axis=0)
            # normalize
            denom = np.linalg.norm(centroid) + 1e-12
            centroid = centroid / denom
            centroids.append(centroid)

        if not centroids:
            logger.warning("Intent centroids empty; router disabled.")
            self._built = True
            return

        self._intent_names = intent_names[: len(centroids)]
        self._intent_vecs = np.stack(centroids, axis=0).astype(np.float32)

        # build index
        self._index.build(self._intent_vecs)

        self._built = True
        logger.info(
            "Intent router built: intents=%d dim=%d index=%s took=%.2fs",
            len(self._intent_names),
            int(self._intent_vecs.shape[1]),
            getattr(settings, "vector_index_type", "numpy"),
            time.time() - t0,
        )

    def route(self, query: str, *, min_score: float = 0.25) -> Optional[IntentResult]:
        """
        Return the best intent for query.
        Score is cosine similarity (normalized vectors).
        """
        q = (query or "").strip()
        if not q:
            return None

        if not self._built:
            self.build()

        if self._intent_vecs is None or not self._intent_names:
            return None

        qv = np.array(self.embedder.embed([q])[0], dtype=np.float32)
        qv = qv / (np.linalg.norm(qv) + 1e-12)

        scores, idxs = self._index.search(qv, top_k=1)
        if len(idxs) == 0:
            return None

        best_idx = int(idxs[0])
        best_score = float(scores[0])

        if best_idx < 0 or best_idx >= len(self._intent_names):
            return None

        if best_score < min_score:
            return None

        intent = self._intent_names[best_idx]
        flags = self._intent_flags(intent)

        return IntentResult(
            intent=intent,
            score=best_score,
            is_broad=bool(flags.get("is_broad", False)),
            is_tech=bool(flags.get("is_tech", False)),
        )

    # --------------------------
    # Config helpers
    # --------------------------

    def _get_intent_examples(self) -> Dict[str, List[str]]:
        v = self.config.get("intent_examples")
        if isinstance(v, dict):
            out: Dict[str, List[str]] = {}
            for k, arr in v.items():
                if isinstance(arr, list):
                    out[str(k)] = [str(x) for x in arr if isinstance(x, (str, int, float))]
            return out
        return {}

    def _intent_flags(self, intent: str) -> Dict[str, Any]:
        mapping = self.config.get("intent_mapping")
        if isinstance(mapping, dict):
            v = mapping.get(intent)
            if isinstance(v, dict):
                return v
        return {"is_broad": False, "is_tech": False}

    def _default_intent_examples(self) -> Dict[str, List[str]]:
        # This serves as a minimal fallback if config is not provided
        return {}