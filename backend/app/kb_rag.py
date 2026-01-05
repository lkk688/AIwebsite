import json
import os
import glob
import re
import time
import logging
from typing import List, Dict, Any, Optional, Tuple
import numpy as np

from .settings import settings
from .embeddings_client import EmbeddingsClient
from .vector_index import get_vector_index, VectorIndex
from .db import sha256_text, get_cached_kb_embedding, upsert_kb_embedding

logger = logging.getLogger("jwl.kb_rag")

class KnowledgeBaseRAG:
    def __init__(self, embedder: EmbeddingsClient):
        self.embedder = embedder
        self.chunks: List[Dict[str, Any]] = [] # stores {"text": "...", "metadata": {...}}
        self._vecs: Optional[np.ndarray] = None
        self.vector_index: VectorIndex = get_vector_index(settings.vector_index_type)
        self.context_data: Dict[str, Any] = {}
        
    def load_data(self) -> None:
        """
        Load data from KB directory and context file.
        """
        # 1. Load context data (websiteinfo.json) for template replacement
        context_path = os.path.join(settings.data_dir, os.path.basename(settings.kb_context_file))
        # Handle relative path if needed, but settings.data_dir is usually absolute or relative to backend root
        # Let's resolve absolute path based on settings logic
        if not os.path.isabs(context_path):
             # settings.data_dir is typically relative to backend execution or hardcoded
             # We can try to resolve it relative to backend root if it starts with ..
             # But settings.py resolves BASE_DIR. Let's trust settings.data_dir is correct relative to CWD or absolute.
             # Actually, settings.data_dir default is "../src/data".
             # Let's use a robust resolution similar to other parts of the app
             base_dir = os.path.dirname(os.path.abspath(__file__)) # backend/app
             backend_root = os.path.dirname(base_dir) # backend
             # Resolve against backend root if relative
             if not os.path.isabs(settings.kb_context_file):
                 # Try to resolve relative to backend root's parent (project root) because default is "../src/data/..."
                 # But settings.data_dir is "../src/data". 
                 # Let's simplify: try to find the file.
                 pass

        # Robust path resolution for context file
        possible_paths = [
            settings.kb_context_file,
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "src", "data", "websiteinfo.json"), # Hard fallback
            os.path.abspath(settings.kb_context_file)
        ]
        
        for p in possible_paths:
            if os.path.exists(p):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        self.context_data = json.load(f)
                    logger.info(f"Loaded KB context data from {p}")
                    break
                except Exception as e:
                    logger.error(f"Failed to load context file {p}: {e}")
        
        # Flatten context data for easier replacement (e.g. contact.email -> value)
        # Or just support top-level keys. The user request example was {{SALES_EMAIL}}.
        # Let's extract some common fields to top level for convenience
        self.replacements = self._build_replacements(self.context_data)

        # 2. Load KB files (.jsonl)
        kb_dir = settings.kb_data_dir
        if not os.path.isabs(kb_dir):
             # Try to resolve relative to project root
             project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
             kb_dir = os.path.join(project_root, "src", "data", "kb")
        
        if not os.path.exists(kb_dir):
            logger.warning(f"KB directory not found: {kb_dir}")
            return

        jsonl_files = glob.glob(os.path.join(kb_dir, "*.jsonl"))
        self.chunks = []
        
        for file_path in jsonl_files:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            item = json.loads(line)
                            # item should be {"text": "...", "metadata": ...}
                            # Support raw text or other formats? Let's assume schema.
                            if "text" in item:
                                # Template replacement
                                text = self._process_template(item["text"])
                                self.chunks.append({
                                    "text": text,
                                    "metadata": item.get("metadata", {}),
                                    "source": os.path.basename(file_path)
                                })
                        except json.JSONDecodeError:
                            logger.warning(f"Invalid JSON in {file_path}: {line[:50]}...")
            except Exception as e:
                logger.error(f"Error reading KB file {file_path}: {e}")
                
        logger.info(f"Loaded {len(self.chunks)} chunks from {len(jsonl_files)} KB files.")

    def _build_replacements(self, data: Dict[str, Any]) -> Dict[str, str]:
        """
        Extract key-value pairs for template replacement.
        Supports nested keys flattened with dot notation, or specific business logic mapping.
        """
        replacements = {}
        
        # Recursive flattener
        def flatten(obj, prefix=""):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    flatten(v, f"{prefix}{k}." if prefix else f"{k}.")
            elif isinstance(obj, list):
                # Join lists with comma or newline? 
                replacements[prefix[:-1]] = ", ".join(map(str, obj))
            else:
                replacements[prefix[:-1]] = str(obj)

        flatten(data)
        
        # Add some shortcuts/aliases if needed based on user request {{SALES_EMAIL}}
        # Check if we have specific keys
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
        for key, value in self.replacements.items():
            pattern = f"{{{{{key}}}}}"
            if pattern in text:
                text = text.replace(pattern, value)
        return text

    def build_index(self) -> None:
        if not self.chunks:
            self.load_data()
            
        if not self.chunks:
            logger.warning("No KB chunks to index.")
            return

        t0 = time.time()
        n = len(self.chunks)
        model = self.embedder.model
        logger.info("KB RAG build_index start: chunks=%d model=%s", n, model)

        texts = [c["text"] for c in self.chunks]
        vecs = [None] * n
        missing_texts = []
        missing_idxs = []

        # Reuse caching logic
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
                text = texts[idx]
                chunk_hash = sha256_text(text)
                upsert_kb_embedding(chunk_hash, model, emb)

        self._vecs = np.array(vecs, dtype=np.float32)
        
        # Build Vector Index
        t2 = time.time()
        self.vector_index.build(self._vecs)
        logger.info("KB Vector index built: type=%s took=%.2fs", settings.vector_index_type, time.time() - t2)

    def retrieve(self, query: str, k: int = 3) -> List[Dict[str, Any]]:
        if self._vecs is None:
            self.build_index()
            
        if not self.chunks:
            return []

        qv = np.array(self.embedder.embed([query])[0], dtype=np.float32)
        
        scores, indices = self.vector_index.search(qv, top_k=min(k, len(self.chunks)))
        
        results = []
        for score, idx in zip(scores, indices):
            idx = int(idx)
            if idx < len(self.chunks):
                item = self.chunks[idx].copy()
                item["score"] = float(score)
                results.append(item)
                
        return results

# Singleton management
_kb_rag_instance: Optional[KnowledgeBaseRAG] = None

def init_kb_rag(embedder: EmbeddingsClient) -> KnowledgeBaseRAG:
    global _kb_rag_instance
    if _kb_rag_instance is None:
        _kb_rag_instance = KnowledgeBaseRAG(embedder)
        # Pre-load/build index in background? Or lazy.
        # Let's lazy load on first request or explicitly call load_data here.
        # _kb_rag_instance.load_data() 
    return _kb_rag_instance

def get_kb_rag() -> KnowledgeBaseRAG:
    global _kb_rag_instance
    if _kb_rag_instance is None:
        raise RuntimeError("KnowledgeBaseRAG not initialized. Call init_kb_rag first.")
    return _kb_rag_instance
