from __future__ import annotations

import json
import os
import re
import logging
from typing import List, Dict, Any, Optional, Tuple

from .settings import settings
from .product_rag import build_rag_context
from .kb_rag import get_kb_rag
from .conversation_state import (
    LRUConversationStore,
    update_state_from_messages,
)

logger = logging.getLogger("jwl.chat")


def _is_technical_query(q: str) -> bool:
    """
    Heuristic routing:
    '专业问' -> KB more, product less.
    """
    t = (q or "").lower()
    keys = [
        "reach", "cpsia", "prop 65", "rohs", "ce", "lfgb", "fda",
        "azo", "phthalate", "lead time", "incoterms", "fob", "cif", "ddp",
        "gsm", "denier", "tpu", "pu", "eva", "ykk", "seam", "stitch",
        "waterproof", "water resistant", "coating", "lamination",
        "air shipping", "sea shipping", "customs", "hs code",
        "合规", "认证", "材质", "工艺", "印花", "海运", "空运", "关税", "ddp", "fob", "cif",
    ]
    return any(k in t for k in keys)


def _is_broad_category_query(q: str) -> bool:
    """
    '泛问' -> product more, KB less.
    """
    t = (q or "").lower().strip()
    patterns = [
        r"\bdo you have\b",
        r"\bwhat do you have\b",
        r"\bshow me\b",
        r"\bany\b.*\bbags?\b",
        r"\bbackpacks?\b$",
        r"\bbags?\b$",
        r"\b你们有\b",
        r"\b有什么\b",
        r"\b有哪些\b",
    ]
    return any(re.search(p, t) for p in patterns)


def _format_slots(slots: Dict[str, Any], locale: str) -> str:
    """
    Compact slots for LLM.
    """
    if not slots:
        return ""
    # keep only stable keys
    keep = {}
    for k in ["name", "email", "quantity", "product_id", "confirm_send"]:
        if k in slots and slots[k] not in (None, "", False):
            keep[k] = slots[k]
    if not keep:
        return ""
    title = "对话关键信息(自动提取)" if locale == "zh" else "Conversation Slots (auto-extracted)"
    return f"{title}:\n{json.dumps(keep, ensure_ascii=False)}"


class ChatService:
    """
    Main LLM chat context builder.
    Adds:
      - server-side conversation state cache keyed by conversation_id
      - automatic compression into summary + slots
      - RAG routing + compact prompts
    """
    def __init__(self, data_store):
        self.store = data_store
        self.config = self._load_config()

        # In-memory LRU cache (you can later switch to SQLite store if needed)
        max_items = getattr(settings, "conversation_cache_size", 2000) or 2000
        ttl = getattr(settings, "conversation_cache_ttl_seconds", 24 * 3600) or (24 * 3600)
        self.state_store = LRUConversationStore(max_items=int(max_items), ttl_seconds=int(ttl))

    def _load_config(self) -> Dict[str, Any]:
        config = {
            "system_prompts": {},
            "context_keywords": {},
            "tool_responses": {}
        }
        try:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # backend/
            project_root = os.path.dirname(base_dir)
            config_path = os.path.join(project_root, "src", "data", "chat_config.json")

            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    config.update(loaded)
            else:
                logger.warning("chat_config.json not found at %s", config_path)
        except Exception as e:
            logger.error("Failed to load chat_config.json: %s", e)

        return config

    def build_system_prompt(self, locale: str) -> str:
        prompts = self.config.get("system_prompts", {}).get(locale, self.config.get("system_prompts", {}).get("en", {}))

        info = self.store.website_info
        company = (info.get("companyName", {}) or {}).get(locale) or (info.get("companyName", {}) or {}).get("en") or "JWL Travel Gear"

        role = prompts.get("role", "").replace("{company}", company)
        strict = prompts.get("strict_policy", "")
        general = prompts.get("general_rules", "")
        output = prompts.get("output_req", "")

        return f"{role}\n\n{strict}\n\n{general}\n\n{output}".strip()

    def build_company_context(self, query: str, locale: str, k: int) -> Tuple[str, List[Dict[str, Any]]]:
        """
        KB RAG (already locale-filtered in kb_rag.retrieve()).
        Returns (context_string, hits_summary)
        """
        try:
            kb = get_kb_rag()
            hits = kb.retrieve(query, locale=locale, k=k)
            if not hits:
                return "", []

            parts = []
            hits_meta = []
            for hit in hits:
                parts.append(hit["text"])
                md = hit.get("metadata", {}) or {}
                hits_meta.append({
                    "kb_id": md.get("kb_id"),
                    "lang": md.get("lang"),
                    "source": hit.get("source"),
                    "score": f"{hit.get('score', 0):.4f}",
                    "title": md.get("title", ""),
                    "text_preview": (hit.get("text", "")[:60] + "...") if hit.get("text") else "",
                })

            return "\n---\n".join(parts), hits_meta
        except Exception as e:
            logger.error("KB RAG retrieval failed: %s", e)
            return "", []

    def _incoming_to_dict_messages(self, messages: List[Any]) -> List[Dict[str, str]]:
        """
        Accept pydantic objects or dict-like.
        """
        out: List[Dict[str, str]] = []
        for m in messages:
            role = getattr(m, "role", None) or (m.get("role") if isinstance(m, dict) else None) or "user"
            text = getattr(m, "text", None) or (m.get("text") if isinstance(m, dict) else None) or ""
            out.append({"role": str(role), "text": str(text)})
        return out

    def _build_rag_query(self, turns: List[Dict[str, str]], max_chars: int = 900) -> str:
        """
        Use last few user turns to build retrieval query.
        """
        user_texts = [t["text"] for t in turns if t.get("role") == "user" and t.get("text")]
        q = " ".join(user_texts[-3:])
        q = q.strip()
        if len(q) > max_chars:
            q = q[-max_chars:]
        return q

    def prepare_llm_messages(
        self,
        messages: List[Any],
        locale: str,
        *,
        conversation_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Build LLM messages:
          - system prompt
          - [Conversation Summary] + [Slots]
          - [Context] = KB + Product (routed)
          - recent turns only (not full history)
        """
        locale = (locale or "en").strip()

        # ---------- state store ----------
        incoming = self._incoming_to_dict_messages(messages)

        # if no conversation_id, behave like stateless: treat incoming as full short history
        if conversation_id:
            st = self.state_store.get_or_create(conversation_id, locale=locale)
            st = update_state_from_messages(st, incoming)
            self.state_store.upsert(st)
            turns = st.recent_turns[:]  # already includes incoming
            conv_summary = st.summary or ""
            slots = st.slots or {}
        else:
            turns = incoming
            conv_summary = ""
            slots = {}

        # ---------- routing + retrieval query ----------
        rag_query = self._build_rag_query(turns)

        is_tech = _is_technical_query(rag_query)
        is_broad = _is_broad_category_query(rag_query)

        # product topk + kb topk routing:
        # - exact product => product only (structured) + KB small
        # - broad => product more, KB less
        # - technical => KB more, product less
        prod_k = 3
        kb_k = 3

        if is_broad:
            prod_k = 3
            kb_k = 1
        if is_tech:
            prod_k = 2
            kb_k = 3

        rag_info = build_rag_context(query=rag_query, locale=locale, k=prod_k, desc_max=120)
        prod_ctx = rag_info.get("context", "")
        rag_mode = rag_info.get("mode", "none")

        # refine routing when exact hit
        if rag_mode == "exact":
            # exact product => keep KB minimal unless it's clearly technical
            prod_k = 1
            kb_k = 1 if not is_tech else 2

        comp_ctx, kb_hits_summary = self.build_company_context(rag_query, locale, k=kb_k)

        # ---------- system prompt ----------
        sys_prompt = self.build_system_prompt(locale)

        # summary + slots into system (reduces token pressure)
        summary_block = ""
        if conv_summary:
            title = "对话摘要(压缩)" if locale == "zh" else "Conversation Summary (compressed)"
            # keep it short to prevent prompt bloat
            s = conv_summary.strip()
            if len(s) > 900:
                s = s[-900:]
            summary_block = f"{title}:\n{s}"

        slots_block = _format_slots(slots, locale)

        # ---------- context assembly ----------
        ctx_parts: List[str] = []
        if summary_block:
            ctx_parts.append(summary_block)
        if slots_block:
            ctx_parts.append(slots_block)

        # Avoid too much mixed context:
        # - Put KB as "Company/Knowledge" and Product as "Product"
        if comp_ctx:
            prefix = "公司知识库:\n" if locale == "zh" else "Knowledge Base:\n"
            ctx_parts.append(prefix + comp_ctx)

        if prod_ctx:
            ctx_parts.append(prod_ctx)

        system_content = sys_prompt
        if ctx_parts:
            system_content += "\n\n[Context]\n" + "\n\n".join(ctx_parts)

        # ---------- final LLM messages: system + recent turns ----------
        llm_messages: List[Dict[str, Any]] = [{"role": "system", "content": system_content}]

        # only keep recent turns (already compressed)
        for t in turns[-12:]:
            role = t.get("role", "user")
            if role == "bot":
                role = "assistant"
            if role not in ("system", "user", "assistant"):
                role = "user"
            llm_messages.append({"role": role, "content": t.get("text", "")})

        # ---------- debug log ----------
        try:
            logger.info(
                "chat_context locale=%s conv_id=%s rag_mode=%s is_broad=%s is_tech=%s\n"
                "Product Hits: %s\nKB Hits: %s\nContext Length: %d",
                locale,
                conversation_id,
                rag_mode,
                is_broad,
                is_tech,
                json.dumps(rag_info.get("hits_summary", []), ensure_ascii=False),
                json.dumps(kb_hits_summary, ensure_ascii=False),
                len(system_content),
            )
        except Exception:
            pass

        return llm_messages