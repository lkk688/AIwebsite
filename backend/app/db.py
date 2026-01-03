import sqlite3
from datetime import datetime, timezone
from typing import Optional, Dict, Any
import json
import os

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