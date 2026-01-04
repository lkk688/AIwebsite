import json
import os
import logging
from typing import List, Dict, Any, Optional

from .settings import settings
# pylint: disable=no-name-in-module
from .product_rag import build_rag_context

logger = logging.getLogger("jwl.chat")

class ChatService:
    def __init__(self, data_store):
        self.store = data_store
        self.config = self._load_config()
        
    def _load_config(self) -> Dict[str, Any]:
        config = {
            "system_prompts": {},
            "context_keywords": {},
            "tool_responses": {}
        }
        try:
            # Assuming src/data/chat_config.json is relative to backend root
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # backend/
            project_root = os.path.dirname(base_dir) # AIwebsite/
            config_path = os.path.join(project_root, "src", "data", "chat_config.json")
            
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    config.update(loaded)
            else:
                logger.warning(f"chat_config.json not found at {config_path}")
        except Exception as e:
            logger.error(f"Failed to load chat_config.json: {e}")
            
        return config

    def get_tool_response(self, key: str, locale: str, **kwargs) -> str:
        responses = self.config.get("tool_responses", {}).get(locale, self.config.get("tool_responses", {}).get("en", {}))
        text = responses.get(key, "")
        if kwargs:
            try:
                return text.format(**kwargs)
            except Exception:
                return text
        return text

    def build_system_prompt(self, locale: str) -> str:
        """
        Builds the system prompt for the LLM based on the user's locale.
        """
        prompts = self.config.get("system_prompts", {}).get(locale, self.config.get("system_prompts", {}).get("en", {}))
        
        info = self.store.website_info
        company = (info.get("companyName", {}) or {}).get(locale) or (info.get("companyName", {}) or {}).get("en") or "JWL Travel Gear"
        
        role = prompts.get("role", "").replace("{company}", company)
        strict = prompts.get("strict_policy", "")
        general = prompts.get("general_rules", "")
        output = prompts.get("output_req", "")
        
        return f"{role}\n\n{strict}\n\n{general}\n\n{output}"

    def build_company_context(self, query: str, locale: str) -> str:
        """
        Retrieves relevant company information based on keywords.
        """
        q = query.lower()
        parts = []
        
        keywords_config = self.config.get("context_keywords", {})
        
        for section, conf in keywords_config.items():
            keys = conf.get("keys", [])
            if any(k in q for k in keys):
                data_source = conf.get("data_source")
                data_key = conf.get("data_key")
                
                data = None
                if data_source == "website_info":
                    data = self.store.website_info.get(data_key, {})
                elif data_source == "certifications":
                    data = self.store.certifications
                
                if data:
                    parts.append(json.dumps(data, ensure_ascii=False, indent=2))

        return "\n\n".join(parts)

    def prepare_llm_messages(self, messages: List[Any], locale: str) -> List[Dict[str, Any]]:
        """
        Converts request messages to LLM format with context injection.
        """
        # 1) Build system prompt
        sys_prompt = self.build_system_prompt(locale)

        # 2) Build dynamic product context (Sliding window retrieval)
        user_msgs = [m for m in messages if m.role in ("user",) or m.role not in ("assistant", "bot", "system")]
        
        rag_query = ""
        if user_msgs:
            # Take last 3 messages
            recent_msgs = user_msgs[-3:] 
            rag_query = " ".join([m.text for m in recent_msgs])
            if len(rag_query) > 800:
                rag_query = rag_query[-800:]

        # RAG Retrieval
        rag_info = build_rag_context(query=rag_query, locale=locale, k=5)
        prod_ctx = rag_info["context"]

        # Company Context
        comp_ctx = self.build_company_context(rag_query, locale)

        # 3) Assemble Context
        ctx_parts = []
        if comp_ctx:
            prefix = "公司信息:\n" if locale == "zh" else "Company info:\n"
            ctx_parts.append(prefix + comp_ctx)
        if prod_ctx:
            ctx_parts.append(prod_ctx)

        system_content = sys_prompt
        if ctx_parts:
            system_content += "\n\n[Context]\n" + "\n\n".join(ctx_parts)

        # 4) Format Messages
        llm_messages = [{"role": "system", "content": system_content}]
        for m in messages:
            role = "assistant" if m.role == "bot" else m.role
            if role not in ("system", "user", "assistant"):
                role = "user"
            llm_messages.append({"role": role, "content": m.text})

        # Log for debug
        try:
            logger.info(
                "chat_context locale=%s rag_mode=%s hit=%s ctx_len=%d",
                locale,
                rag_info.get("mode"),
                rag_info.get("hits_summary"),
                len(prod_ctx or ""),
            )
        except Exception:
            pass

        return llm_messages
