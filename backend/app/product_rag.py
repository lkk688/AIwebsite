from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
import re
import numpy as np
from difflib import SequenceMatcher

from .embeddings_client import EmbeddingsClient
from .db import sha256_text, get_cached_product_embedding, upsert_product_embedding
from .vector_index import get_vector_index, VectorIndex
from .settings import settings
import time
import logging

__all__ = ["ProductRAG", "init_product_rag", "get_product_rag", "build_rag_context"]

logger = logging.getLogger("jwl.rag")

# def _norm(s: str) -> str:
#     s = (s or "").strip().lower()
#     s = re.sub(r"\s+", " ", s)
#     return s

def _norm(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"\s+", " ", s)
    # 去掉常见标点/括号等噪声（可选）
    s = re.sub(r"[()（）\[\]【】{}<>]", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s

# def _get_locale_text(p: Dict[str, Any], key: str, locale: str) -> str:
#     v = p.get(key, {})
#     if isinstance(v, dict):
#         return v.get(locale) or v.get("en") or ""
#     return str(v) if v is not None else ""

def _get_locale_text(obj: Dict[str, Any], key: str, locale: str) -> str:
    v = obj.get(key, None)
    if v is None:
        return ""
    if isinstance(v, dict):
        vv = v.get(locale) or v.get("en")
        if vv is None:
            return ""
        if isinstance(vv, list):
            return "\n".join([str(x) for x in vv if x is not None])
        if isinstance(vv, dict):
            import json
            return json.dumps(vv, ensure_ascii=False)
        return str(vv)
    if isinstance(v, list):
        return "\n".join([str(x) for x in v if x is not None])
    return str(v)

def product_to_doc_text(p: Dict[str, Any]) -> str:
    # 用于 embedding：中英都放进去，增强召回
    name_en = _get_locale_text(p, "name", "en")
    name_zh = _get_locale_text(p, "name", "zh")
    desc_en = _get_locale_text(p, "description", "en")
    desc_zh = _get_locale_text(p, "description", "zh")
    cat = str(p.get("category", ""))
    tags = " ".join(p.get("tags", []) or [])
    # materials/spec 可能是 dict/list，简单转字符串
    materials = p.get("materials", "")
    specs = p.get("specifications", "")

    return "\n".join([
        f"id: {p.get('id','')}",
        f"slug: {p.get('slug','')}",
        f"category: {cat}",
        f"tags: {tags}",
        f"name_en: {name_en}",
        f"name_zh: {name_zh}",
        f"desc_en: {desc_en}",
        f"desc_zh: {desc_zh}",
        f"materials: {materials}",
        f"specifications: {specs}",
    ])


class ProductRAG:
    def __init__(self, products: List[Dict[str, Any]], embedder: EmbeddingsClient):
        self.products = products
        self.embedder = embedder

        self._doc_texts: List[str] = []
        self._vecs: Optional[np.ndarray] = None
        self.vector_index: VectorIndex = get_vector_index(settings.vector_index_type)
        logger.info(f"ProductRAG initialized with {settings.vector_index_type} index")

    def build_index(self) -> None:
        t0 = time.time()
        n = len(self.products)
        logger.info("RAG build_index start: products=%d model=%s", n, self.embedder.model)

        self._doc_texts = [product_to_doc_text(p) for p in self.products]

        vecs = [None] * n
        missing_texts = []
        missing_idxs = []
        model = self.embedder.model

        cache_hit = 0
        for i, p in enumerate(self.products):
            # 每 100 个打一行进度（产品多时有用，少也无妨）
            if (i + 1) % 100 == 0:
                logger.info("RAG cache scan progress: %d/%d", i + 1, n)

            pid = p.get("id") or ""
            doc_hash = sha256_text(self._doc_texts[i])
            cached = get_cached_product_embedding(pid, model, doc_hash)
            if cached is not None:
                vecs[i] = cached
                cache_hit += 1
            else:
                missing_idxs.append(i)
                missing_texts.append(self._doc_texts[i])

        logger.info("RAG cache scan done: hit=%d missing=%d", cache_hit, len(missing_texts))

        if missing_texts:
            t1 = time.time()
            new_vecs = self.embedder.embed(missing_texts)
            logger.info("RAG embed computed: batch=%d took=%.2fs", len(missing_texts), time.time() - t1)

            for idx, emb in zip(missing_idxs, new_vecs):
                vecs[idx] = emb
                pid = self.products[idx].get("id") or ""
                doc_hash = sha256_text(self._doc_texts[idx])
                upsert_product_embedding(pid, model, doc_hash, emb)

            logger.info("RAG cache updated: rows=%d", len(missing_texts))

        self._vecs = np.array(vecs, dtype=np.float32)
        logger.info("RAG build_index done: shape=%s took=%.2fs", self._vecs.shape, time.time() - t0)
        
        # Build Vector Index
        t2 = time.time()
        self.vector_index.build(self._vecs)
        logger.info("Vector index built: type=%s took=%.2fs", settings.vector_index_type, time.time() - t2)
        
    # def build_index(self) -> None:
    #     self._doc_texts = [product_to_doc_text(p) for p in self.products]
    #     vecs = self.embedder.embed(self._doc_texts)
    #     self._vecs = np.array(vecs, dtype=np.float32)

    # def exact_match(self, query: str, locale: str) -> Optional[Dict[str, Any]]:
    #     """
    #     当用户明确提到某一款产品：
    #     - 命中 id / slug
    #     - name 近似匹配（中/英）
    #     """
    #     qn = _norm(query)
    #     if not qn:
    #         return None

    #     # 1) id / slug 直接包含
    #     for p in self.products:
    #         pid = _norm(p.get("id", ""))
    #         slug = _norm(p.get("slug", ""))
    #         if pid and pid in qn:
    #             return p
    #         if slug and slug in qn:
    #             return p

    #     # 2) name 精确包含（双向）
    #     # 3) name fuzzy（SequenceMatcher）
    #     best: Tuple[float, Optional[Dict[str, Any]]] = (0.0, None)
    #     for p in self.products:
    #         name_local = _norm(_get_locale_text(p, "name", locale))
    #         name_en = _norm(_get_locale_text(p, "name", "en"))
    #         name_zh = _norm(_get_locale_text(p, "name", "zh"))

    #         for cand in [name_local, name_en, name_zh]:
    #             if not cand:
    #                 continue
    #             if cand in qn or qn in cand:
    #                 return p
    #             # fuzzy
    #             r = SequenceMatcher(None, qn, cand).ratio()
    #             if r > best[0]:
    #                 best = (r, p)

    #     # 阈值可调：产品少时宁愿严格一点
    #     if best[0] >= 0.82:
    #         return best[1]
    #     return None

    def exact_match(self, query: str, locale: str) -> Optional[Dict[str, Any]]:
        """
        三层：
        1) id/slug 直接包含
        2) name contains（双向包含，en/zh 都看）
        3) fuzzy（SequenceMatcher），阈值可调
        """
        qn = _norm(query)
        if not qn:
            return None

        # ---- 1) id/slug 直接包含（强命中）----
        for p in self.products:
            pid = _norm(p.get("id", ""))
            slug = _norm(p.get("slug", ""))
            if pid and pid in qn:
                return p
            if slug and slug in qn:
                return p

        # ---- 2) name contains（强命中）----
        for p in self.products:
            name_local = _norm(_get_locale_text(p, "name", locale))
            name_en = _norm(_get_locale_text(p, "name", "en"))
            name_zh = _norm(_get_locale_text(p, "name", "zh"))

            for cand in (name_local, name_en, name_zh):
                if not cand:
                    continue
                # 双向包含：用户可能只输入部分名字
                if cand in qn or qn in cand:
                    return p

        # ---- 3) fuzzy（弱命中）----
        best_score = 0.0
        best_p: Optional[Dict[str, Any]] = None

        for p in self.products:
            candidates = [
                _norm(_get_locale_text(p, "name", locale)),
                _norm(_get_locale_text(p, "name", "en")),
                _norm(_get_locale_text(p, "name", "zh")),
                _norm(p.get("slug", "")),
            ]
            candidates = [c for c in candidates if c]
            if not candidates:
                continue

            # 取最相似的一个作为该产品得分
            s = max(SequenceMatcher(None, qn, c).ratio() for c in candidates)
            if s > best_score:
                best_score = s
                best_p = p

        # 阈值：0.82~0.90 之间看你产品命名是否相似
        if best_score >= 0.84:
            return best_p
        return None

    def semantic_search(self, query: str, k: int = 5) -> List[Tuple[float, Dict[str, Any]]]:
        if self._vecs is None:
            self.build_index()

        qv = np.array(self.embedder.embed([query])[0], dtype=np.float32)
        
        # Use Vector Index
        scores, indices = self.vector_index.search(qv, top_k=min(k, len(self.products)))
        
        out = []
        for score, idx in zip(scores, indices):
            # idx might be int64 or int
            idx = int(idx)
            if idx < len(self.products):
                out.append((float(score), self.products[idx]))
        return out

    def retrieve(self, query: str, locale: str, k: int = 5) -> Dict[str, Any]:
        """
        返回：
        - mode: "exact" | "rag"
        - products: List[product]
        """
        hit = self.exact_match(query, locale)
        if hit is not None:
            return {"mode": "exact", "products": [hit]}

        hits = self.semantic_search(query, k=k)
        return {"mode": "rag", "products": [p for _, p in hits]}

    def search(self, query: str, locale: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        For product_search.py integration.
        Returns [{"id": "...", "score": 0.95}, ...]
        """
        hits = self.semantic_search(query, k=top_k)
        out = []
        for score, p in hits:
            out.append({"id": p.get("id"), "score": score})
        return out

    def get_product_by_id(self, product_id: str) -> Optional[Dict[str, Any]]:
        """
        Direct lookup by ID.
        """
        if not product_id:
            return None
        pid = _norm(product_id)
        for p in self.products:
            if _norm(p.get("id", "")) == pid:
                return p
        return None


# Singleton management
_rag_instance: Optional[ProductRAG] = None

def init_product_rag(products: List[Dict[str, Any]], embedder: EmbeddingsClient) -> ProductRAG:
    global _rag_instance
    if _rag_instance is None:
        _rag_instance = ProductRAG(products, embedder)
    return _rag_instance

def get_product_rag() -> ProductRAG:
    global _rag_instance
    if _rag_instance is None:
        raise RuntimeError("ProductRAG not initialized. Call init_product_rag first.")
    return _rag_instance

def build_rag_context(query: str, locale: str, k: int = 5) -> Dict[str, Any]:
    """
    Standalone function to get RAG context string for LLM injection.
    """
    rag = get_product_rag()
    ret = rag.retrieve(query, locale, k=k)
    mode = ret["mode"]
    hits = ret["products"]
    
    # Format hits into string
    lines = []
    for h in hits:
        pid = h.get("id", "")
        slug = h.get("slug", "")
        name = _get_locale_text(h, "name", locale)
        cat = h.get("category", "")
        tags = h.get("tags", [])
        desc = _get_locale_text(h, "description", locale)
        
        # Include variants info if available
        variants = h.get("variants", [])
        variants_info = f"variants_count={len(variants)}"
        if variants:
             # Add simple summary of variants, e.g. colors
             # Assuming variant has 'name' or 'color' or 'en'/'zh' keys based on locale
             # The JSON structure shows variants as:
             # { "key": "army-green", "sku": "...", "en": "Army Green", "zh": "军绿色" }
             
             v_names = []
             for v in variants[:8]:
                 # Try to get localized name first, then fallback to 'name', then 'key'
                 val = v.get(locale) or v.get("en") or v.get("name") or v.get("key") or "v"
                 v_names.append(str(val))
                 
             variants_info += f" examples={v_names}"
             if len(variants) > 8:
                 variants_info += "..."

        lines.append(
            f"- id={pid} slug={slug} name={name}\n"
            f"  category={cat} tags={tags}\n"
            f"  {variants_info}\n"
            f"  desc={desc[:settings.desc_max_len]}"
        )
    
    if not lines:
        return {"context": "", "mode": mode, "hits_summary": []}

    title = "[Semantic TopK]" if locale != "zh" else "[语义检索 TopK]"
    hint = "Choose the most relevant product(s) below and cite id/slug." if locale != "zh" else "请从下面选择最相关的产品，并引用 id/slug。"
    
    ctx_str = f"{title}\n{hint}\n\n" + "\n\n".join(lines)
    
    # hits summary for logging
    hits_summary = [{"id": h.get("id"), "slug": h.get("slug"), "name": _get_locale_text(h, "name", locale)} for h in hits]
    
    return {"context": ctx_str, "mode": mode, "hits_summary": hits_summary}

def format_product_context(hits: List[Dict[str, Any]], locale: str, title_override: str = None) -> str:
    """
    Helper to format a list of products into context string.
    """
    lines = []
    for h in hits:
        pid = h.get("id", "")
        slug = h.get("slug", "")
        name = _get_locale_text(h, "name", locale)
        cat = h.get("category", "")
        tags = h.get("tags", [])
        desc = _get_locale_text(h, "description", locale)
        
        # Include variants info if available
        variants = h.get("variants", [])
        variants_info = f"variants_count={len(variants)}"
        if variants:
             v_names = []
             for v in variants[:8]:
                 val = v.get(locale) or v.get("en") or v.get("name") or v.get("key") or "v"
                 v_names.append(str(val))
             variants_info += f" examples={v_names}"
             if len(variants) > 8:
                 variants_info += "..."

        lines.append(
            f"- id={pid} slug={slug} name={name}\n"
            f"  category={cat} tags={tags}\n"
            f"  {variants_info}\n"
            f"  desc={desc[:settings.desc_max_len]}"
        )
    
    if not lines:
        return ""

    if title_override:
        title = title_override
        hint = ""
    else:
        title = "[Product Context]" if locale != "zh" else "[产品上下文]"
        hint = "Focus on this product." if locale != "zh" else "请关注此产品。"

    return f"{title}\n{hint}\n\n" + "\n\n".join(lines)