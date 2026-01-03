import re
from typing import Any, Dict, List, Tuple


def _tokenize(q: str) -> List[str]:
    q = q.lower().strip()
    parts = re.split(r"[^a-z0-9\u4e00-\u9fff]+", q)
    return [p for p in parts if p]


def _get_locale_text(obj: Dict[str, Any], key: str, locale: str) -> str:
    v = obj.get(key, {})
    if isinstance(v, dict):
        return v.get(locale) or v.get("en") or ""
    return str(v) if v is not None else ""


def score_product(p: Dict[str, Any], keywords: List[str], locale: str) -> int:
    name = _get_locale_text(p, "name", locale)
    desc = _get_locale_text(p, "description", locale)
    category = str(p.get("category", ""))
    tags = " ".join(p.get("tags", []) or [])
    materials = _get_locale_text(p, "materials", locale)
    specs = _get_locale_text(p, "specifications", locale)

    hay = f"{name} {desc} {category} {tags} {materials} {specs}".lower()
    s = 0
    for kw in keywords:
        if kw and kw in hay:
            s += 1
    return s


def search_products(products: List[Dict[str, Any]], query: str, locale: str = "en", limit: int = 8) -> List[Dict[str, Any]]:
    keywords = _tokenize(query)
    if not keywords:
        return []

    scored: List[Tuple[int, Dict[str, Any]]] = []
    for p in products:
        sc = score_product(p, keywords, locale)
        if sc > 0:
            scored.append((sc, p))

    scored.sort(key=lambda x: x[0], reverse=True)
    results: List[Dict[str, Any]] = []
    for sc, p in scored[:limit]:
        results.append({
            "score": sc,
            "id": p.get("id"),
            "slug": p.get("slug"),
            "category": p.get("category"),
            "tags": p.get("tags", []),
            "name": _get_locale_text(p, "name", locale),
            "description": _get_locale_text(p, "description", locale)[:220],
            "assetDir": p.get("assetDir"),
        })
    return results


def build_product_context(products: List[Dict[str, Any]], query: str, locale: str, limit: int = 3) -> str:
    hits = search_products(products, query, locale=locale, limit=limit)
    if not hits:
        return ""

    lines = []
    for h in hits:
        lines.append(f"- {h['name']} ({h.get('category','')}): {h.get('description','')}...")

    title = "相关产品" if locale == "zh" else "Relevant Products"
    return f"{title}:\n" + "\n".join(lines)