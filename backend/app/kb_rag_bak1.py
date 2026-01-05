from __future__ import annotations

import glob
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .settings import settings
from .embeddings_client import EmbeddingsClient
from .vector_index import get_vector_index, VectorIndex
from .db import sha256_text, get_cached_kb_embedding, upsert_kb_embedding

logger = logging.getLogger("jwl.kb_rag")


def _normalize_locale(locale: str) -> str:
    """
    Normalize locale to "en" or "zh" (extend if you add more).
    """
    loc = (locale or "en").strip().lower()
    if loc.startswith("zh"):
        return "zh"
    return "en"


def _resolve_project_root() -> str:
    """
    backend/app/ -> backend/ -> project_root/
    """
    app_dir = os.path.dirname(os.path.abspath(__file__))          # .../backend/app
    backend_dir = os.path.dirname(app_dir)                        # .../backend
    project_root = os.path.dirname(backend_dir)                   # .../project_root
    return project_root


def _resolve_path(p: str) -> str:
    """
    Resolve a path that may be:
      - absolute
      - relative to current working dir
      - relative to project root
    """
    if not p:
        return p
    if os.path.isabs(p):
        return p
    # try cwd-relative
    if os.path.exists(p):
        return os.path.abspath(p)
    # project root relative
    pr = _resolve_project_root()
    pp = os.path.join(pr, p)
    return os.path.abspath(pp)


def _safe_join_lines(lines: Any) -> str:
    if lines is None:
        return ""
    if isinstance(lines, list):
        return "\n".join([str(x) for x in lines if x is not None])
    return str(lines)


class KnowledgeBaseRAG:
    """
    KB RAG loader + embed/cache + vector search.

    ✅ Does NOT require changing your KB jsonl format.
    Supports:
      1) add metadata.lang (mapped from item.locale)
      2) filter retrieval results by locale (avoid en/zh mixed)
      3) dedupe results (by kb_id) so you don't get repeated entries
    """

    def __init__(self, embedder: EmbeddingsClient):
        self.embedder = embedder

        # Each chunk:
        # {
        #   "text": "...",
        #   "metadata": {"kb_id": "...", "lang": "en|zh", "title": "...", "tags": [], "priority": int, ...},
        #   "source": "kb_xxx.jsonl"
        # }
        self.chunks: List[Dict[str, Any]] = []
        self._vecs: Optional[np.ndarray] = None
        self.vector_index: VectorIndex = get_vector_index(settings.vector_index_type)

        # Optional: used if you do template replacements like {{SALES_EMAIL}}
        self.context_data: Dict[str, Any] = {}
        self.replacements: Dict[str, str] = {}

    # ---------------------------
    # Load + normalize schema
    # ---------------------------

    def load_data(self) -> None:
        """
        Load:
          - optional context file for template replacement
          - all *.jsonl in kb_data_dir

        JSONL format supported (your current one):
          {"id":"kb_xxx","locale":"en","title":"...","text":"...","tags":[...],"source":"template","priority":4}
        Also supports legacy format:
          {"text":"...", "metadata": {...}}
        """
        # 1) Load optional context file for template replacement
        self.context_data = {}
        self.replacements = {}

        try:
            ctx_path = _resolve_path(getattr(settings, "kb_context_file", "") or "")
            if ctx_path and os.path.exists(ctx_path):
                with open(ctx_path, "r", encoding="utf-8") as f:
                    self.context_data = json.load(f)
                logger.info("Loaded KB context data from %s", ctx_path)
                self.replacements = self._build_replacements(self.context_data)
        except Exception as e:
            logger.warning("Failed to load kb_context_file: %s", e)

        # 2) Load KB files
        kb_dir = _resolve_path(getattr(settings, "kb_data_dir", "") or getattr(settings, "kb_data_dir", "") or "")
        if not kb_dir:
            # fallback: backend/src/data/kb if settings not set properly
            pr = _resolve_project_root()
            kb_dir = os.path.join(pr, "src", "data", "kb")

        if not os.path.exists(kb_dir):
            logger.warning("KB directory not found: %s", kb_dir)
            self.chunks = []
            return

        jsonl_files = sorted(glob.glob(os.path.join(kb_dir, "*.jsonl")))
        self.chunks = []

        for file_path in jsonl_files:
            base = os.path.basename(file_path)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    for line_no, line in enumerate(f, 1):
                        line = (line or "").strip()
                        if not line:
                            continue
                        try:
                            item = json.loads(line)

                            # ---- normalize schema ----
                            if isinstance(item, dict) and "text" in item and "metadata" in item:
                                # legacy
                                text = self._process_template(_safe_join_lines(item.get("text")))
                                md = item.get("metadata", {}) or {}
                                kb_id = md.get("kb_id") or item.get("id") or f"{base}:{line_no}"
                                lang = _normalize_locale(md.get("lang") or md.get("locale") or "en")
                                md = {**md, "kb_id": kb_id, "lang": lang}
                            else:
                                # your current flat schema
                                text = self._process_template(_safe_join_lines(item.get("text")))
                                kb_id = item.get("id") or f"{base}:{line_no}"
                                lang = _normalize_locale(item.get("locale") or item.get("lang") or "en")
                                md = {
                                    "kb_id": kb_id,
                                    "lang": lang,
                                    "title": item.get("title") or "",
                                    "tags": item.get("tags") or [],
                                    "priority": int(item.get("priority", 0) or 0),
                                    "source": item.get("source") or "kb",
                                    # optional future fields (won't break if missing)
                                    "summary": item.get("summary") or "",
                                }

                            if not text:
                                continue

                            self.chunks.append(
                                {
                                    "text": text,
                                    "metadata": md,
                                    "source": base,
                                }
                            )

                        except json.JSONDecodeError:
                            logger.warning("Invalid JSON in %s:%d -> %s", base, line_no, line[:80])
                        except Exception as e:
                            logger.warning("KB line parse error %s:%d -> %s", base, line_no, e)

            except Exception as e:
                logger.error("Error reading KB file %s: %s", file_path, e)

        logger.info("Loaded %d chunks from %d KB files.", len(self.chunks), len(jsonl_files))

    def _build_replacements(self, data: Dict[str, Any]) -> Dict[str, str]:
        """
        Extract key-value pairs for template replacement.
        Supports nested keys flattened with dot notation.
        """
        replacements: Dict[str, str] = {}

        def flatten(obj: Any, prefix: str = "") -> None:
            if isinstance(obj, dict):
                for k, v in obj.items():
                    flatten(v, f"{prefix}{k}." if prefix else f"{k}.")
            elif isinstance(obj, list):
                replacements[prefix[:-1]] = ", ".join(map(str, obj))
            else:
                replacements[prefix[:-1]] = str(obj)

        flatten(data)

        # common aliases (optional)
        if "contact.email.en" in replacements:
            replacements["SALES_EMAIL"] = replacements["contact.email.en"]
        elif "contact.email" in replacements:
            replacements["SALES_EMAIL"] = replacements["contact.email"]

        if "companyName.en" in replacements:
            replacements["COMPANY_NAME"] = replacements["companyName.en"]

        return replacements

    def _process_template(self, text: str) -> str:
        """
        Replace {{KEY}} with values from replacements.
        """
        if not text or not self.replacements:
            return text or ""
        out = text
        for key, value in self.replacements.items():
            token = f"{{{{{key}}}}}"
            if token in out:
                out = out.replace(token, value)
        return out

    # ---------------------------
    # Index build + caching
    # ---------------------------

    def build_index(self) -> None:
        if not self.chunks:
            self.load_data()

        if not self.chunks:
            logger.warning("No KB chunks to index.")
            self._vecs = None
            return

        t0 = time.time()
        n = len(self.chunks)
        model = self.embedder.model
        logger.info("KB RAG build_index start: chunks=%d model=%s", n, model)

        texts = [c["text"] for c in self.chunks]
        vecs: List[Optional[List[float]]] = [None] * n
        missing_texts: List[str] = []
        missing_idxs: List[int] = []

        cache_hit = 0
        for i, text in enumerate(texts):
            chunk_hash = sha256_text(text)
            cached = get_cached_kb_embedding(chunk_hash, model)
            if cached is not None:
                vecs[i] = cached
                cache_hit += 1
            else:
                missing_idxs.append(i)
                missing_texts.append(text)

        logger.info("KB RAG cache scan done: hit=%d missing=%d", cache_hit, len(missing_texts))

        if missing_texts:
            t1 = time.time()
            new_vecs = self.embedder.embed(missing_texts)
            logger.info("KB RAG embed computed: batch=%d took=%.2fs", len(missing_texts), time.time() - t1)

            for idx, emb in zip(missing_idxs, new_vecs):
                vecs[idx] = emb
                chunk_hash = sha256_text(texts[idx])
                upsert_kb_embedding(chunk_hash, model, emb)

        # type: ignore[arg-type]
        self._vecs = np.array(vecs, dtype=np.float32)

        t2 = time.time()
        self.vector_index.build(self._vecs)
        logger.info("KB Vector index built: type=%s took=%.2fs", settings.vector_index_type, time.time() - t2)
        logger.info("KB RAG build_index done: shape=%s took=%.2fs", self._vecs.shape, time.time() - t0)

    # ---------------------------
    # Retrieve (locale filter + dedupe)
    # ---------------------------

    def retrieve(self, query: str, locale: str, k: int = 3) -> List[Dict[str, Any]]:
        """
        Returns top-k KB chunks for the query.
        ✅ filters by locale (lang) so prompt won't mix languages
        ✅ dedup by kb_id (keep best score)
        """
        if not query or not query.strip():
            return []

        if self._vecs is None:
            self.build_index()

        if not self.chunks or self._vecs is None:
            return []

        want_lang = _normalize_locale(locale)

        qv = np.array(self.embedder.embed([query])[0], dtype=np.float32)

        # Oversample then filter+dedupe; cheap at your scale (172 chunks).
        oversample = min(max(k * 6, 12), len(self.chunks))
        scores, indices = self.vector_index.search(qv, top_k=oversample)

        results: List[Dict[str, Any]] = []
        best_by_id: Dict[str, Tuple[float, Dict[str, Any]]] = {}

        for score, idx in zip(scores, indices):
            idx_i = int(idx)
            if idx_i < 0 or idx_i >= len(self.chunks):
                continue

            item = self.chunks[idx_i]
            md = item.get("metadata", {}) or {}

            lang = _normalize_locale(str(md.get("lang") or md.get("locale") or "en"))
            if lang != want_lang:
                continue

            kb_id = str(md.get("kb_id") or "")
            if not kb_id:
                kb_id = sha256_text(item.get("text", ""))

            s = float(score)
            if kb_id not in best_by_id or s > best_by_id[kb_id][0]:
                out = item.copy()
                out["score"] = s
                best_by_id[kb_id] = (s, out)

        # sort by score desc, return top k
        for _, out in sorted(best_by_id.values(), key=lambda x: x[0], reverse=True)[:k]:
            results.append(out)

        return results


# Singleton management
_kb_rag_instance: Optional[KnowledgeBaseRAG] = None


def init_kb_rag(embedder: EmbeddingsClient) -> KnowledgeBaseRAG:
    global _kb_rag_instance
    if _kb_rag_instance is None:
        _kb_rag_instance = KnowledgeBaseRAG(embedder)
    return _kb_rag_instance


def get_kb_rag() -> KnowledgeBaseRAG:
    global _kb_rag_instance
    if _kb_rag_instance is None:
        raise RuntimeError("KnowledgeBaseRAG not initialized. Call init_kb_rag first.")
    return _kb_rag_instance