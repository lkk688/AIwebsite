from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple, Optional

# ---------------------------
# Text helpers
# ---------------------------

_TOKEN_SPLIT_RE = re.compile(r"[^a-z0-9\u4e00-\u9fff]+")


def _tokenize(q: str) -> List[str]:
    q = (q or "").lower().strip()
    parts = _TOKEN_SPLIT_RE.split(q)
    return [p for p in parts if p]


def _norm(s: str) -> str:
    """Normalize for fuzzy/exact matching."""
    s = (s or "").lower()
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _flatten_value(v: Any, locale: str = "en") -> str:
    """
    Flatten nested structures commonly found in product JSON:
      - {"en": "...", "zh": "..."}
      - {"en": [...], "zh":[...]}
      - {"en": {...}, "zh": {...}}
      - list[str], dict[str, Any]
    """
    if v is None:
        return ""

    # locale dict: {"en": "...", "zh": "..."} or {"en":[...], "zh":[...]} etc.
    if isinstance(v, dict):
        # if looks like locale dict
        if locale in v or "en" in v or "zh" in v:
            vv = v.get(locale) or v.get("en") or v.get("zh") or ""
            return _flatten_value(vv, locale=locale)

        # plain dict -> join key: value
        parts = []
        for k, val in v.items():
            parts.append(f"{k}: {_flatten_value(val, locale=locale)}")
        return " ".join([p for p in parts if p])

    if isinstance(v, list):
        return " ".join([_flatten_value(x, locale=locale) for x in v if x is not None])

    return str(v)


def _get_locale_text(obj: Dict[str, Any], key: str, locale: str) -> str:
    """
    Robust locale getter:
      - if obj[key] is {"en": "...", "zh":"..."} -> return locale fallback to en
      - if obj[key] is list/dict -> flatten
      - else -> str
    """
    v = obj.get(key, None)
    return _flatten_value(v, locale=locale)


# ---------------------------
# Scoring
# ---------------------------

def score_product_lexical(p: Dict[str, Any], keywords: List[str], locale: str) -> int:
    """
    Simple lexical scoring: count keyword occurrences in a combined "haystack".
    (Fast and cheap; good baseline.)
    """
    name = _get_locale_text(p, "name", locale)
    desc = _get_locale_text(p, "description", locale)
    category = str(p.get("category", "") or "")
    tags = " ".join(p.get("tags", []) or [])
    materials = _get_locale_text(p, "materials", locale)
    specs = _get_locale_text(p, "specifications", locale)

    # include id/slug as well for exact-ish matching
    pid = str(p.get("id", "") or "")
    slug = str(p.get("slug", "") or "")

    hay = f"{pid} {slug} {name} {desc} {category} {tags} {materials} {specs}".lower()

    s = 0
    for kw in keywords:
        if kw and kw in hay:
            s += 1

    # small bonus if keyword hits name
    name_l = name.lower()
    for kw in keywords:
        if kw and kw in name_l:
            s += 1

    return s


def exact_match_boost(p: Dict[str, Any], query: str, locale: str) -> int:
    """
    If query seems to mention a specific product:
      - id substring
      - slug substring
      - name substring
    apply a big boost so it ranks at top.
    """
    qn = _norm(query)

    pid = _norm(str(p.get("id", "") or ""))
    slug = _norm(str(p.get("slug", "") or ""))
    name = _norm(_get_locale_text(p, "name", locale))

    boost = 0
    if pid and pid in qn:
        boost += 50
    if slug and slug in qn:
        boost += 40
    # name match is fuzzy-ish; only boost if sufficiently long
    if name and len(name) >= 8 and name in qn:
        boost += 35

    return boost


def _product_image_url(p: Dict[str, Any]) -> Optional[str]:
    asset_dir = p.get("assetDir")
    if not asset_dir:
        return None
    return f"/images/products/{asset_dir}/1_thumb.webp"


# ---------------------------
# Semantic search integration (optional)
# ---------------------------

@dataclass
class SemanticHit:
    id: str
    score: float

from .product_rag import get_product_rag
def _semantic_search_ids(query: str, locale: str, top_k: int) -> List[SemanticHit]:
    """
    Adapter layer to your product_rag.py.
    """
    try:
        rag = get_product_rag()
        hits = rag.search(query=query, locale=locale, top_k=top_k)  # list[dict]
    except Exception:
        return []

    out: List[SemanticHit] = []
    for h in hits or []:
        pid = (h.get("id") if isinstance(h, dict) else None) or ""
        sc = (h.get("score") if isinstance(h, dict) else None)
        try:
            scf = float(sc)
        except Exception:
            scf = 0.0
        if pid:
            out.append(SemanticHit(id=pid, score=scf))
    return out


# ---------------------------
# Public APIs used by app.py
# ---------------------------

def search_products(
    products: List[Dict[str, Any]],
    query: str,
    locale: str = "en",
    limit: int = 8,
    *,
    semantic: bool = False,
    semantic_top_k: Optional[int] = None,
    semantic_min_score: float = 0.0,
    hybrid_alpha: float = 0.35,
) -> List[Dict[str, Any]]:
    """
    Search products by keyword (lexical) and optionally semantic search.

    Backward-compatible defaults:
      - semantic=False -> only lexical
      - return format matches your current UI needs

    Hybrid scoring:
      final_score = lexical_score + int(alpha * semantic_score * 100)
    """
    q = (query or "").strip()
    if not q:
        return []

    keywords = _tokenize(q)

    # 1) Lexical scores
    lexical_scored: List[Tuple[float, Dict[str, Any], int, int]] = []
    for p in products:
        lex = score_product_lexical(p, keywords, locale) if keywords else 0
        boost = exact_match_boost(p, q, locale)
        final_lex = lex + boost
        if final_lex > 0:
            lexical_scored.append((float(final_lex), p, lex, boost))

    # Sort lexical
    lexical_scored.sort(key=lambda x: x[0], reverse=True)

    # If semantic disabled, return lexical top
    if not semantic:
        return _format_results(lexical_scored[:limit], locale)

    # 2) Semantic search (topK ids + score)
    top_k = semantic_top_k or max(limit * 3, 12)  # fetch more for better hybrid merge
    sem_hits = _semantic_search_ids(query=q, locale=locale, top_k=top_k)

    # Map id -> semantic score
    sem_map: Dict[str, float] = {h.id: h.score for h in sem_hits if h.score >= semantic_min_score}

    # 3) Hybrid merge
    # Build a map of product by id for fast lookup
    by_id: Dict[str, Dict[str, Any]] = {}
    for p in products:
        pid = str(p.get("id") or "")
        if pid:
            by_id[pid] = p

    # Start with lexical candidates (keep their detailed breakdown)
    merged: Dict[str, Dict[str, Any]] = {}

    for final_lex, p, lex, boost in lexical_scored:
        pid = str(p.get("id") or "")
        ssem = sem_map.get(pid, 0.0)
        hybrid = float(final_lex) + float(hybrid_alpha) * float(ssem) * 100.0
        merged[pid] = {
            "p": p,
            "hybrid": hybrid,
            "lex": float(lex),
            "boost": float(boost),
            "sem": float(ssem),
        }

    # Add semantic-only hits not present in lexical
    for pid, ssem in sem_map.items():
        if pid in merged:
            continue
        p = by_id.get(pid)
        if not p:
            continue
        boost = exact_match_boost(p, q, locale)
        hybrid = float(boost) + float(hybrid_alpha) * float(ssem) * 100.0
        merged[pid] = {
            "p": p,
            "hybrid": hybrid,
            "lex": 0.0,
            "boost": float(boost),
            "sem": float(ssem),
        }

    # Sort by hybrid score
    merged_list = sorted(merged.values(), key=lambda x: x["hybrid"], reverse=True)[:limit]

    # Filter out low-score results
    # 1. If lexical score > 0 (keyword match), we almost always keep it (threshold 1.0).
    # 2. If semantic only, hybrid score = alpha * sem * 100.
    #    alpha=0.35. A "good" match often has cosine similarity > 0.4-0.5.
    #    0.35 * 0.4 * 100 = 14.0.
    #    0.35 * 0.5 * 100 = 17.5.
    #    0.35 * 0.6 * 100 = 21.0.
    # Let's set a stricter threshold for pure semantic matches, e.g., 18.0 (~0.51 similarity).
    # This prevents weak semantic associations from cluttering results.
    
    filtered_list = []
    print(f"DEBUG: Search query='{q}' limit={limit}")
    for item in merged_list:
        lex = item["lex"]
        boost = item["boost"]
        hybrid = item["hybrid"]
        
        print(f"DEBUG: id={item['p'].get('id')} lex={lex} boost={boost} hybrid={hybrid} sem={item['sem']}")

        # If we have keyword match or exact match boost, keep it (score will be >= 1)
        if lex > 0 or boost > 0:
            filtered_list.append(item)
        # If pure semantic, enforce a stricter threshold
        elif hybrid > 20.0:
            filtered_list.append(item)

    # Format
    results: List[Dict[str, Any]] = []
    for item in filtered_list:
        p = item["p"]
        results.append({
            "score": round(item["hybrid"], 3),
            "lex_score": round(item["lex"], 3),
            "exact_boost": round(item["boost"], 3),
            "semantic_score": round(item["sem"], 6),

            "id": p.get("id"),
            "slug": p.get("slug"),
            "category": p.get("category"),
            "tags": p.get("tags", []),
            "name": _get_locale_text(p, "name", locale),
            "description": _get_locale_text(p, "description", locale)[:220],
            "assetDir": p.get("assetDir"),
            "image": _product_image_url(p),
        })
    return results


def _format_results(scored: List[Tuple[float, Dict[str, Any], int, int]], locale: str) -> List[Dict[str, Any]]:
    """
    Format lexical-only results into the same schema your UI already expects.
    """
    results: List[Dict[str, Any]] = []
    for final_score, p, lex, boost in scored:
        results.append({
            "score": int(final_score),
            "lex_score": int(lex),
            "exact_boost": int(boost),

            "id": p.get("id"),
            "slug": p.get("slug"),
            "category": p.get("category"),
            "tags": p.get("tags", []),
            "name": _get_locale_text(p, "name", locale),
            "description": _get_locale_text(p, "description", locale)[:220],
            "assetDir": p.get("assetDir"),
            "image": _product_image_url(p),
        })
    return results


def build_product_context(products: List[Dict[str, Any]], query: str, locale: str, limit: int = 3, *, semantic: bool = True) -> str:
    """
    Build short product context string for prompt injection (RAG-lite).
    By default semantic=True here to help chat answer broad questions.
    """
    hits = search_products(products, query, locale=locale, limit=limit, semantic=semantic)
    if not hits:
        return ""

    lines = []
    for h in hits:
        pid = h.get("id", "")
        slug = h.get("slug", "")
        lines.append(f"- id={pid} slug={slug} name={h['name']}\n  category={h.get('category','')} tags={h.get('tags',[])}\n  desc={h.get('description','')}")

    title = "[Top Products]" if locale != "zh" else "[相关产品 Top]"
    hint = "Choose the most relevant product(s) below and cite id/slug." if locale != "zh" else "请从下面选择最相关的产品，并引用 id/slug。"
    return f"{title}\n{hint}\n\n" + "\n\n".join(lines)