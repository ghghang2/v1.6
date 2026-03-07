"""Persist chat history in a lightweight SQLite database.

The database is created in the repository root as ``chat_history.db``.
Two tables:
  chat_log      — every message row for every session.
  session_meta  — per-session key/value metadata (context summaries,
                  turn summary caches, task logs, etc.).
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "chat_history.db"


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

def init_db() -> None:
    """Create tables if they do not exist. Idempotent."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS chat_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id  TEXT NOT NULL,
                role        TEXT NOT NULL,
                content     TEXT,
                tool_id     TEXT,
                tool_name   TEXT,
                tool_args   TEXT,
                ts          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_session ON chat_log(session_id)"
        )
        conn.execute("""
            CREATE TABLE IF NOT EXISTS session_meta (
                session_id  TEXT NOT NULL,
                key         TEXT NOT NULL,
                value       TEXT,
                ts          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (session_id, key)
            )
        """)
        conn.commit()


# ---------------------------------------------------------------------------
# Chat log
# ---------------------------------------------------------------------------

def log_message(session_id: str, role: str, content: str) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO chat_log (session_id, role, content) VALUES (?, ?, ?)",
            (session_id, role, content),
        )
        conn.commit()


def log_row(session_id: str, role: str, content: str,
            tool_id: str = "", tool_name: str = "", tool_args: str = "") -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO chat_log (session_id, role, content, tool_id, tool_name, tool_args) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, role, content or "", tool_id or "", tool_name or "", tool_args or ""),
        )
        conn.commit()


def log_tool_msg(session_id: str, tool_id: str, tool_name: str,
                 tool_args: str, content: str) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO chat_log (session_id, role, content, tool_id, tool_name, tool_args) "
            "VALUES (?, 'tool', ?, ?, ?, ?)",
            (session_id, content, tool_id, tool_name, tool_args),
        )
        conn.commit()


def load_history(session_id: str,
                 limit: int | None = None) -> list[tuple[str, str, str, str, str]]:
    with sqlite3.connect(DB_PATH) as conn:
        query = (
            "SELECT role, content,"
            " COALESCE(tool_id, ''), COALESCE(tool_name, ''), COALESCE(tool_args, '')"
            " FROM chat_log WHERE session_id = ? ORDER BY id ASC"
        )
        params: list = [session_id]
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)
        return conn.execute(query, params).fetchall()


def get_session_ids() -> list[str]:
    with sqlite3.connect(DB_PATH) as conn:
        return [r[0] for r in conn.execute(
            "SELECT DISTINCT session_id FROM chat_log ORDER BY ts DESC"
        ).fetchall()]


def replace_session_history(session_id: str,
                             history: list[tuple[str, str, str, str, str]]) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM chat_log WHERE session_id = ?", (session_id,))
        conn.executemany(
            "INSERT INTO chat_log (session_id, role, content, tool_id, tool_name, tool_args) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [(session_id, r, c, tid, tname, targs) for r, c, tid, tname, targs in history],
        )
        conn.commit()


# ---------------------------------------------------------------------------
# session_meta helpers (shared upsert pattern)
# ---------------------------------------------------------------------------

def _meta_set(session_id: str, key: str, value: str) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO session_meta (session_id, key, value, ts) "
            "VALUES (?, ?, ?, CURRENT_TIMESTAMP) "
            "ON CONFLICT(session_id, key) DO UPDATE SET value=excluded.value, ts=excluded.ts",
            (session_id, key, value),
        )
        conn.commit()


def _meta_get(session_id: str, key: str) -> str:
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT value FROM session_meta WHERE session_id=? AND key=?",
            (session_id, key),
        ).fetchone()
        return row[0] if row and row[0] else ""


# ---------------------------------------------------------------------------
# Context summary  (legacy — kept for backward compat with old sessions)
# ---------------------------------------------------------------------------

def save_context_summary(session_id: str, summary: str) -> None:
    _meta_set(session_id, "context_summary", summary)


def load_context_summary(session_id: str) -> str:
    return _meta_get(session_id, "context_summary")


# ---------------------------------------------------------------------------
# Turn summary cache  {sha1_hash: summary_text}
# ---------------------------------------------------------------------------

def save_turn_summaries(session_id: str, cache: dict) -> None:
    """Persist the full in-memory turn-summary cache for *session_id*."""
    _meta_set(session_id, "turn_summaries", json.dumps(cache))


def load_turn_summaries(session_id: str) -> dict:
    """Return the stored turn-summary cache, or {} if none exists."""
    raw = _meta_get(session_id, "turn_summaries")
    try:
        return json.loads(raw) if raw else {}
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Task log
# ---------------------------------------------------------------------------

def save_task_log(session_id: str, task_log: list) -> None:
    _meta_set(session_id, "task_log", json.dumps(task_log))


def load_task_log(session_id: str) -> list:
    raw = _meta_get(session_id, "task_log")
    try:
        return json.loads(raw) if raw else []
    except Exception:
        return []