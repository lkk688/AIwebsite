import sqlite3
from datetime import datetime, timezone
from typing import Optional, Dict, Any
import json
import os
import hashlib
from typing import List, Optional

def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

DB_FILE = os.environ.get("INQUIRIES_DB_FILE", "inquiries.db")


def get_conn():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")       # 并发更稳
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn


def init_db():
    conn = get_conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS inquiries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at_utc TEXT NOT NULL,
            source TEXT,
            locale TEXT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            message TEXT NOT NULL,
            status TEXT NOT NULL,            -- pending | sent | failed
            ses_message_id TEXT,
            error TEXT,
            meta_json TEXT
        );
        """
    )
    # ✅ 新增：缓存产品 embeddings
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS product_embeddings (
            product_id TEXT NOT NULL,
            model TEXT NOT NULL,
            doc_hash TEXT NOT NULL,
            embedding_json TEXT NOT NULL,
            updated_at_utc TEXT NOT NULL,
            PRIMARY KEY (product_id, model)
        );
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_product_embeddings_model_hash ON product_embeddings(model, doc_hash);"
    )

    # ✅ 新增：缓存 KB embeddings
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS kb_embeddings (
            kb_hash TEXT NOT NULL,           -- SHA256 of text
            model TEXT NOT NULL,
            embedding_json TEXT NOT NULL,
            updated_at_utc TEXT NOT NULL,
            PRIMARY KEY (kb_hash, model)
        );
        """
    )

    conn.commit()
    conn.close()


def insert_inquiry(
    name: str,
    email: str,
    message: str,
    source: str = "unknown",
    locale: str = "en",
    meta: Optional[Dict[str, Any]] = None,
) -> int:
    conn = get_conn()
    ts = datetime.now(timezone.utc).isoformat()
    meta_json = json.dumps(meta, ensure_ascii=False) if meta else None

    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO inquiries(created_at_utc, source, locale, name, email, message, status, meta_json)
        VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
        """,
        (ts, source, locale, name, email, message, meta_json),
    )
    conn.commit()
    rid = cur.lastrowid
    conn.close()
    return rid


def mark_inquiry_sent(inquiry_id: int, ses_message_id: str):
    conn = get_conn()
    conn.execute(
        "UPDATE inquiries SET status='sent', ses_message_id=?, error=NULL WHERE id=?",
        (ses_message_id, inquiry_id),
    )
    conn.commit()
    conn.close()


def mark_inquiry_failed(inquiry_id: int, error: str):
    conn = get_conn()
    conn.execute(
        "UPDATE inquiries SET status='failed', error=? WHERE id=?",
        (error, inquiry_id),
    )
    conn.commit()
    conn.close()

def get_cached_product_embedding(product_id: str, model: str, doc_hash: str) -> Optional[List[float]]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT embedding_json FROM product_embeddings WHERE product_id=? AND model=? AND doc_hash=?",
        (product_id, model, doc_hash),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    try:
        return json.loads(row[0])
    except Exception:
        return None

def upsert_product_embedding(product_id: str, model: str, doc_hash: str, embedding: List[float]) -> None:
    conn = get_conn()
    ts = datetime.now(timezone.utc).isoformat()
    emb_json = json.dumps(embedding)
    conn.execute(
        """
        INSERT INTO product_embeddings(product_id, model, doc_hash, embedding_json, updated_at_utc)
        VALUES(?, ?, ?, ?, ?)
        ON CONFLICT(product_id, model) DO UPDATE SET
          doc_hash=excluded.doc_hash,
          embedding_json=excluded.embedding_json,
          updated_at_utc=excluded.updated_at_utc
        """,
        (product_id, model, doc_hash, emb_json, ts),
    )
    conn.commit()
    conn.close()

def get_cached_kb_embedding(kb_hash: str, model: str) -> Optional[List[float]]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT embedding_json FROM kb_embeddings WHERE kb_hash=? AND model=?",
        (kb_hash, model),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    try:
        return json.loads(row[0])
    except Exception:
        return None

def upsert_kb_embedding(kb_hash: str, model: str, embedding: List[float]) -> None:
    conn = get_conn()
    ts = datetime.now(timezone.utc).isoformat()
    emb_json = json.dumps(embedding)
    conn.execute(
        """
        INSERT INTO kb_embeddings(kb_hash, model, embedding_json, updated_at_utc)
        VALUES(?, ?, ?, ?)
        ON CONFLICT(kb_hash, model) DO UPDATE SET
          embedding_json=excluded.embedding_json,
          updated_at_utc=excluded.updated_at_utc
        """,
        (kb_hash, model, emb_json, ts),
    )
    conn.commit()
    conn.close()