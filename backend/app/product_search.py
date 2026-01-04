from __future__ import annotations

import re
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple, Optional

from .settings import settings

# ---------------------------
# Load Configuration
# ---------------------------
def load_search_config() -> Dict[str, Any]:
    # No hardcoded defaults for fields or labels to ensure logic is data-driven.
    # Minimal fallback structure only to prevent immediate crash if file missing.
    config = {
        "stop_words": [],
        "domain_stop_words": [],
        "fields": {},
        "ui_labels": {}
    }
    
    try:
        # Assuming src/data/search_config.json is relative to backend root or configured data dir
        
        # Hardcode fix for testing environment if needed, or rely on correct relative path
        # In this project structure:
        # backend/app/product_search.py
        # src/data/search_config.json
        # The relative path from app/ is "../../src/data"
        
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # backend/
        project_root = os.path.dirname(base_dir) # AIwebsite/
        config_path = os.path.join(project_root, "src", "data", "search_config.json")
        
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                config.update(loaded)
        else:
             print(f"WARN: search_config.json not found at {config_path}")
    except Exception as e:
        print(f"WARN: Failed to load search_config.json: {e}")
        
    return config

SEARCH_CONFIG = load_search_config()

# ---------------------------
# Text helpers
# ---------------------------

_TOKEN_SPLIT_RE = re.compile(r"[^a-z0-9\u4e00-\u9fff]+")

STOP_WORDS = set(SEARCH_CONFIG.get("stop_words", []))
DOMAIN_STOP_WORDS = set(SEARCH_CONFIG.get("domain_stop_words", []))
STOP_WORDS.update(DOMAIN_STOP_WORDS)

FIELD_MAP = SEARCH_CONFIG.get("fields", {})

def _tokenize(q: str) -> List[str]:
    q = (q or "").lower().strip()
    parts = _TOKEN_SPLIT_RE.split(q)
    # Filter out stop words and single characters (unless they are numbers/kanji)
    return [p for p in parts if p and p not in STOP_WORDS and (len(p) > 1 or not p.isascii())]


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
    Focused lexical scoring: count keyword occurrences primarily in high-value fields.
    Fields: Name, Category, Tags (High Priority), Description (Low Priority).
    """
    # Use configurable field names with safe defaults
    f_name = FIELD_MAP.get("name", "name")
    f_cat = FIELD_MAP.get("category", "category")
    f_tags = FIELD_MAP.get("tags", "tags")
    f_id = FIELD_MAP.get("id", "id")
    f_slug = FIELD_MAP.get("slug", "slug")

    name = _get_locale_text(p, f_name, locale).lower()
    category = str(p.get(f_cat, "") or "").lower()
    tags = " ".join(p.get(f_tags, []) or []).lower()
    
    # Description - often too verbose, so we might want to check it but weight it less
    # or exclude it if we want strict matching. 
    # Current optimization request: "limit the lexical match to only title, categories and tags"
    # So we will exclude description from the main "haystack" or score it separately.
    
    # High priority haystack
    hay_high = f"{name} {category} {tags}"
    
    # ID/Slug are also high priority for exact lookups
    pid = str(p.get(f_id, "") or "").lower()
    slug = str(p.get(f_slug, "") or "").lower()
    
    s = 0
    for kw in keywords:
        if not kw: 
            continue
            
        # 1. Check high-value fields (Score +1)
        if kw in hay_high or kw in pid or kw in slug:
            
            # Bonus: if it's in the name/category/tags specifically (double counting effectively, but emphasizes relevance)
            if kw in name:
                s += 2 # Stronger signal for name
            if kw in category:
                s += 3 # Very strong signal if it matches category
            if kw in tags:
                s += 2 # Strong signal if it matches tags
            
            # Base match score (only if we haven't already added significant points)
            if s == 0:
                s += 1
            elif s == 0 and (kw in pid or kw in slug):
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
    # Use configurable field names with safe defaults
    f_name = FIELD_MAP.get("name", "name")
    f_id = FIELD_MAP.get("id", "id")
    f_slug = FIELD_MAP.get("slug", "slug")

    qn = _norm(query)

    pid = _norm(str(p.get(f_id, "") or ""))
    slug = _norm(str(p.get(f_slug, "") or ""))
    name = _norm(_get_locale_text(p, f_name, locale))

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
    f_asset = FIELD_MAP.get("assetDir", "assetDir")
    asset_dir = p.get(f_asset)
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
    semantic_min_score: float = 0.25,
    lexical_min_score: float = 1.0,
    hybrid_alpha: float = 0.35,
) -> List[Dict[str, Any]]:
    """
    Search products by keyword (lexical) and optionally semantic search.

    Filtering Logic:
      - If semantic=False: Return items with lexical_score >= lexical_min_score.
      - If semantic=True: Return items with lexical_score >= lexical_min_score OR semantic_score >= semantic_min_score.
    
    Scores:
      - Lexical: token count + exact match boost.
      - Semantic: cosine similarity (0-1).
    """
    q = (query or "").strip()
    if not q:
        return []

    keywords = _tokenize(q)

    # 1) Lexical scores
    # list of (final_lex_score, product, raw_lex, boost)
    lexical_scored: List[Tuple[float, Dict[str, Any], int, int]] = []
    for p in products:
        lex = score_product_lexical(p, keywords, locale) if keywords else 0
        boost = exact_match_boost(p, q, locale)
        final_lex = lex + boost
        if final_lex > 0:
            lexical_scored.append((float(final_lex), p, lex, boost))

    # Sort lexical descending
    lexical_scored.sort(key=lambda x: x[0], reverse=True)

    # Dynamic Semantic Logic:
    # If we have "good enough" lexical matches, skip semantic search to save cost/latency.
    # Criteria for "good enough":
    # 1. We have at least 'limit' number of lexical matches.
    # 2. The top matches have a high score (e.g. >= 2.0, meaning multiple keyword hits).
    # 3. The query is short (likely a specific keyword search like "backpack").
    
    should_run_semantic = semantic
    
    if semantic:
        high_quality_lexical_count = sum(1 for x in lexical_scored if x[0] >= 2.0)
        # Use number of valid keywords after stop-word removal to decide if it is a short query
        is_short_query = len(keywords) < 2
        
        # If we have many high-quality matches and it's a short keyword query, skip semantic
        if high_quality_lexical_count >= 5 and is_short_query:
             print(f"DEBUG: [Optimization] Skipping semantic search. Found {high_quality_lexical_count} strong lexical matches for short query '{q}' (keywords={keywords}).")
             should_run_semantic = False
    
    # If semantic disabled (either by config or dynamic logic), filter by lexical threshold only
    if not should_run_semantic:
        print(f"DEBUG: [Lexical Only] Query='{q}' limit={limit} lex_min={lexical_min_score}")
        filtered_lex = []
        for score, p, lex, boost in lexical_scored:
            if score >= lexical_min_score:
                # Debug why we got this score
                name = _get_locale_text(p, "name", locale).lower()
                category = str(p.get("category", "") or "").lower()
                tags = " ".join(p.get("tags", []) or []).lower()
                matched_field = []
                for kw in keywords:
                    if kw in name: matched_field.append("NAME")
                    if kw in category: matched_field.append("CAT")
                    if kw in tags: matched_field.append("TAG")
                
                print(f"DEBUG: MATCH [Lexical] id={p.get('id')} score={score} (lex={lex} boost={boost}) why={matched_field}")
                filtered_lex.append((score, p, lex, boost))
            else:
                print(f"DEBUG: DROP  [Lexical] id={p.get('id')} score={score} < {lexical_min_score}")
        
        return _format_results(filtered_lex[:limit], locale)

    # 2) Semantic search (topK ids + score)
    # Optimization: Filter out domain stop words from the query before sending to embedding model
    # This prevents the embedding from being skewed by generic terms like "bag" or "product"
    
    # Reconstruct query from valid tokens (which already exclude STOP_WORDS and DOMAIN_STOP_WORDS)
    # But we might want to keep some structure. 
    # _tokenize filters out everything. Let's try a simpler approach:
    # Remove only the words in DOMAIN_STOP_WORDS from the original query string for the semantic search.
    
    semantic_query = q
    if semantic:
        # Split by space to check words, case insensitive
        query_parts = q.split()
        # Filter out both generic STOP_WORDS and DOMAIN_STOP_WORDS (STOP_WORDS includes DOMAIN_STOP_WORDS)
        filtered_parts = [w for w in query_parts if w.lower() not in STOP_WORDS]
        if filtered_parts:
            semantic_query = " ".join(filtered_parts)
            print(f"DEBUG: [Semantic Optimization] Original='{q}' -> Optimized='{semantic_query}'")
        else:
            # If everything was filtered out (e.g. user just typed "bags"), keep original
            semantic_query = q

    top_k = semantic_top_k or max(limit * 3, 12)  # fetch more for better hybrid merge
    sem_hits = _semantic_search_ids(query=semantic_query, locale=locale, top_k=top_k)

    # Map id -> semantic score
    sem_map: Dict[str, float] = {h.id: h.score for h in sem_hits}

    # 3) Hybrid merge
    # Build a map of product by id for fast lookup
    by_id: Dict[str, Dict[str, Any]] = {}
    f_id = FIELD_MAP.get("id", "id")
    for p in products:
        pid = str(p.get(f_id) or "")
        if pid:
            by_id[pid] = p

    # Start with lexical candidates
    merged: Dict[str, Dict[str, Any]] = {}

    for final_lex, p, lex, boost in lexical_scored:
        pid = str(p.get(f_id) or "")
        ssem = sem_map.get(pid, 0.0)
        # Hybrid score for sorting (matches previous formula to keep sorting consistent)
        hybrid = float(final_lex) + float(hybrid_alpha) * float(ssem) * 100.0
        merged[pid] = {
            "p": p,
            "hybrid": hybrid,
            "lex": float(lex),
            "boost": float(boost),
            "sem": float(ssem),
            "lex_total": float(final_lex)
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
            "lex_total": float(boost)
        }

    # Sort by hybrid score
    merged_list = sorted(merged.values(), key=lambda x: x["hybrid"], reverse=True)

    # Filter out low-score results
    filtered_list = []
    print(f"DEBUG: [Hybrid Search] Query='{q}' limit={limit}")
    print(f"DEBUG: Thresholds -> Lexical >= {lexical_min_score} OR Semantic >= {semantic_min_score}")

    for item in merged_list:
        lex_total = item["lex_total"]
        sem_score = item["sem"]
        pid = item['p'].get(f_id)
        
        is_lexical_pass = lex_total >= lexical_min_score
        is_semantic_pass = sem_score >= semantic_min_score
        
        # Decide match type for logging
        match_type = "NONE"
        if is_lexical_pass and is_semantic_pass:
            match_type = "BOTH"
        elif is_lexical_pass:
            match_type = "LEXICAL"
        elif is_semantic_pass:
            match_type = "SEMANTIC"

        if is_lexical_pass or is_semantic_pass:
            print(f"DEBUG: MATCH [{match_type}] id={pid} lex_total={lex_total} sem={sem_score:.4f} hybrid={item['hybrid']:.2f}")
            filtered_list.append(item)
        else:
            print(f"DEBUG: DROP  [Low Score] id={pid} lex_total={lex_total} sem={sem_score:.4f}")

    # Apply limit after filtering
    final_list = filtered_list[:limit]

    # Format
    results: List[Dict[str, Any]] = []
    
    # Use configurable field names
    f_name = FIELD_MAP.get("name", "name")
    f_cat = FIELD_MAP.get("category", "category")
    f_tags = FIELD_MAP.get("tags", "tags")
    f_id = FIELD_MAP.get("id", "id")
    f_slug = FIELD_MAP.get("slug", "slug")
    f_desc = FIELD_MAP.get("description", "description")
    f_asset = FIELD_MAP.get("assetDir", "assetDir")

    for item in final_list:
        p = item["p"]
        
        # Calculate relevance tag for UI
        # Logic: High confidence if lexical score is high (>=threshold) OR semantic score is very high (>= high_rel_threshold)
        # This allows UI to show "Top Results" first without knowing the scoring details.
        lex_total = item["lex_total"]
        sem_score = item["sem"]
        
        relevance_threshold = settings.search_relevance_threshold
        sem_high_rel_threshold = settings.semantic_high_relevance_threshold
        
        is_high_confidence = lex_total >= relevance_threshold or sem_score >= sem_high_rel_threshold
        relevance = "high" if is_high_confidence else "low"
        
        # DEBUG: show why it is high or low
        if is_high_confidence:
            reason = []
            if lex_total >= relevance_threshold: reason.append(f"lex({lex_total})>={relevance_threshold}")
            if sem_score >= sem_high_rel_threshold: reason.append(f"sem({sem_score:.4f})>={sem_high_rel_threshold}")
            print(f"DEBUG: RELEVANCE [HIGH] id={p.get(f_id)} reason={', '.join(reason)}")
        else:
            print(f"DEBUG: RELEVANCE [LOW]  id={p.get(f_id)} lex={lex_total} sem={sem_score:.4f}")

        results.append({
            "score": round(item["hybrid"], 3),
            "relevance": relevance,
            "lex_score": round(item["lex"], 3),
            "exact_boost": round(item["boost"], 3),
            "semantic_score": round(item["sem"], 6),

            "id": p.get(f_id),
            "slug": p.get(f_slug),
            "category": p.get(f_cat),
            "tags": p.get(f_tags, []),
            "name": _get_locale_text(p, f_name, locale),
            "description": _get_locale_text(p, f_desc, locale)[:220],
            "assetDir": p.get(f_asset),
            "image": _product_image_url(p),
        })
    return results


def _format_results(scored: List[Tuple[float, Dict[str, Any], int, int]], locale: str) -> List[Dict[str, Any]]:
    """
    Format lexical-only results into the same schema your UI already expects.
    """
    # Use configurable field names
    f_name = FIELD_MAP.get("name", "name")
    f_cat = FIELD_MAP.get("category", "category")
    f_tags = FIELD_MAP.get("tags", "tags")
    f_id = FIELD_MAP.get("id", "id")
    f_slug = FIELD_MAP.get("slug", "slug")
    f_desc = FIELD_MAP.get("description", "description")
    f_asset = FIELD_MAP.get("assetDir", "assetDir")

    results: List[Dict[str, Any]] = []
    for final_score, p, lex, boost in scored:
        
        # Calculate relevance (Lexical Only Mode)
        # In lexical-only mode, final_score IS the lex_total.
        # Threshold matches the logic in hybrid mode for "high confidence".
        relevance_threshold = settings.search_relevance_threshold
        is_high_confidence = final_score >= relevance_threshold
        relevance = "high" if is_high_confidence else "low"
        
        # DEBUG: if this item is shown, log its relevance status
        # print(f"DEBUG: Item {p.get(f_id)} score={final_score} relevance={relevance}")
        
        results.append({
            "score": int(final_score),
            "relevance": relevance,
            "lex_score": int(lex),
            "exact_boost": int(boost),

            "id": p.get(f_id),
            "slug": p.get(f_slug),
            "category": p.get(f_cat),
            "tags": p.get(f_tags, []),
            "name": _get_locale_text(p, f_name, locale),
            "description": _get_locale_text(p, f_desc, locale)[:220],
            "assetDir": p.get(f_asset),
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

    # Use configurable field names
    f_name = FIELD_MAP.get("name", "name")
    f_cat = FIELD_MAP.get("category", "category")
    f_tags = FIELD_MAP.get("tags", "tags")
    f_id = FIELD_MAP.get("id", "id")
    f_slug = FIELD_MAP.get("slug", "slug")
    f_desc = FIELD_MAP.get("description", "description")

    # Load UI labels from config
    labels = SEARCH_CONFIG.get("ui_labels", {}).get(locale, SEARCH_CONFIG.get("ui_labels", {}).get("en", {}))
    title = labels.get("top_products", "[Top Products]")
    hint = labels.get("choose_relevant", "Choose the most relevant product(s) below and cite id/slug.")

    lines = []
    for h in hits:
        # Since h is already formatted in search_products using _get_locale_text, 
        # keys like 'name' and 'description' are already strings. 
        # BUT 'id', 'slug', 'category', 'tags' are direct from product dict usually.
        # Let's check search_products return structure.
        # It returns a new dict with keys: id, slug, category, tags, name, description, etc.
        # So we can just use those keys directly.
        
        pid = h.get("id", "")
        slug = h.get("slug", "")
        lines.append(f"- id={pid} slug={slug} name={h['name']}\n  category={h.get('category','')} tags={h.get('tags',[])}\n  desc={h.get('description','')}")

    return f"{title}\n{hint}\n\n" + "\n\n".join(lines)