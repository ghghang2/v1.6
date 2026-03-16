"""Persist chat history in a lightweight SQLite database.

The database is created in the repository root as ``chat_history.db``.
Tables:
  chat_log      — every message row for every session.
  session_meta  — per-session key/value metadata (context summaries,
                  turn summary caches, task logs, etc.).
  episodic_store — L2 episodic memory: append-only log of tool exchanges
                   with entity refs and importance scores.
  core_memory   — L1 typed persistent slots: goal, constraints,
                  active_entities, error_history, last_correction.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).resolve().parent.parent / "chat_history.db"

# Error detection for protected exchanges
def _is_error_content(content: str) -> bool:
    """Check if content contains error indicators."""
    content_lower = (content or "").lower()
    error_patterns = (
        "error", "exception", "failed", "cannot", "traceback", "fatal", "fatal error",
        "unexpected", "invalid", "permission denied", "not found"
    )
    return any(p in content_lower for p in error_patterns)



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
                error_flag  INTEGER DEFAULT 0,
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
        # ── L2 Episodic store ──────────────────────────────────────────────
        conn.execute("""
            CREATE TABLE IF NOT EXISTS episodic_store (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id      TEXT NOT NULL,
                turn_id         INTEGER DEFAULT 0,
                action_type     TEXT DEFAULT '',
                entity_refs     TEXT DEFAULT '[]',
                outcome_summary TEXT DEFAULT '',
                importance_score REAL DEFAULT 1.0,
                ts              TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ep_session "
            "ON episodic_store(session_id, importance_score DESC)"
        )
        # ── L1 Core Memory ─────────────────────────────────────────────────
        conn.execute("""
            CREATE TABLE IF NOT EXISTS core_memory (
                session_id  TEXT NOT NULL,
                key         TEXT NOT NULL,
                value       TEXT DEFAULT '',
                ts          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (session_id, key)
            )
        """)
        conn.commit()


# ---------------------------------------------------------------------------
# Chat log
# ---------------------------------------------------------------------------

def log_message(session_id: str, role: str, content: str) -> None:
    # Determine error flag
    error_flag = 1 if _is_error_content(content) else 0
    
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO chat_log (session_id, role, content, error_flag) VALUES (?, ?, ?, ?)",
            (session_id, role, content, error_flag),
        )
        conn.commit()


def log_row(session_id: str, role: str, content: str,
            tool_id: str = "", tool_name: str = "", tool_args: str = "") -> None:
    # Determine error flag
    error_flag = 1 if _is_error_content(content) else 0
    
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO chat_log (session_id, role, content, tool_id, tool_name, tool_args, error_flag) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (session_id, role, content or "", tool_id or "", tool_name or "", tool_args or "", error_flag),
        )
        conn.commit()


def log_tool_msg(session_id: str, tool_id: str, tool_name: str,
                 tool_args: str, content: str) -> None:
    # Determine error flag for tool messages
    error_flag = 1 if _is_error_content(content) else 0
    
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO chat_log (session_id, role, content, tool_id, tool_name, tool_args, error_flag) "
            "VALUES (?, 'tool', ?, ?, ?, ?, ?)",
            (session_id, content, tool_id, tool_name, tool_args, error_flag),
        )
        conn.commit()


def load_history(session_id: str,
                 limit: int | None = None) -> list[tuple[str, str, int, str, str, str]]:
    with sqlite3.connect(DB_PATH) as conn:
        query = (
            "SELECT role, content,"
            " COALESCE(tool_id, ''), COALESCE(tool_name, ''), COALESCE(tool_args, ''), error_flag"
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
                             history: list[tuple[str, str, str, str, str, int]]) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM chat_log WHERE session_id = ?", (session_id,))
        conn.executemany(
            "INSERT INTO chat_log (session_id, role, content, tool_id, tool_name, tool_args, error_flag) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [(session_id, r, c, tid, tname, targs, ef) for r, c, tid, tname, targs, ef in history],
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


# ---------------------------------------------------------------------------
# L2 Episodic Store
# ---------------------------------------------------------------------------

def append_episodic(
    session_id: str,
    turn_id: int,
    action_type: str,
    entity_refs: str,       # JSON-encoded list of strings
    outcome_summary: str,
    importance_score: float,
) -> None:
    """Append one tool-exchange record to the episodic store."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO episodic_store "
            "(session_id, turn_id, action_type, entity_refs, outcome_summary, importance_score) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, turn_id, action_type, entity_refs, outcome_summary, importance_score),
        )
        conn.commit()


def query_episodic_by_entities(
    session_id: str,
    entity_refs: list[str],
    limit: int = 5,
) -> list[dict]:
    """Return episodic entries whose entity_refs overlap with *entity_refs*.

    Uses a LIKE search over the JSON-encoded entity_refs column so no JSON
    extension is required.  Returns rows sorted by importance_score DESC.
    """
    if not entity_refs:
        return []
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        # Build a WHERE clause that checks for any entity match
        clauses = " OR ".join("entity_refs LIKE ?" for _ in entity_refs)
        params: list[Any] = [f"%{e}%" for e in entity_refs]
        params += [session_id, limit]
        rows = conn.execute(
            f"SELECT id, turn_id, action_type, entity_refs, outcome_summary, importance_score "
            f"FROM episodic_store "
            f"WHERE ({clauses}) AND session_id = ? "
            f"ORDER BY importance_score DESC "
            f"LIMIT ?",
            params,
        ).fetchall()
    return [dict(r) for r in rows]


def query_episodic_top_importance(
    session_id: str,
    min_score: float = 3.0,
    limit: int = 5,
) -> list[dict]:
    """Return the highest-importance episodic entries for *session_id*."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, turn_id, action_type, entity_refs, outcome_summary, importance_score "
            "FROM episodic_store "
            "WHERE session_id = ? AND importance_score >= ? "
            "ORDER BY importance_score DESC "
            "LIMIT ?",
            (session_id, min_score, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def delete_episodic_for_session(session_id: str) -> None:
    """Remove all episodic entries for *session_id* (used on session reset)."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "DELETE FROM episodic_store WHERE session_id = ?", (session_id,)
        )
        conn.commit()


# ---------------------------------------------------------------------------
# L1 Core Memory
# ---------------------------------------------------------------------------

_CORE_MEMORY_KEYS = frozenset(
    {"goal", "constraints", "active_entities", "error_history", "last_correction"}
)


def get_core_memory(session_id: str) -> dict:
    """Return all core memory slots for *session_id* as a plain dict."""
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT key, value FROM core_memory WHERE session_id = ?",
            (session_id,),
        ).fetchall()
    return {k: v for k, v in rows if v}


def set_core_memory_key(session_id: str, key: str, value: str) -> None:
    """Upsert a single core memory slot."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO core_memory (session_id, key, value, ts) "
            "VALUES (?, ?, ?, CURRENT_TIMESTAMP) "
            "ON CONFLICT(session_id, key) "
            "DO UPDATE SET value=excluded.value, ts=excluded.ts",
            (session_id, key, value),
        )
        conn.commit()


def update_core_memory(session_id: str, updates: dict) -> None:
    """Upsert multiple core memory slots in a single transaction."""
    if not updates:
        return
    with sqlite3.connect(DB_PATH) as conn:
        for key, value in updates.items():
            conn.execute(
                "INSERT INTO core_memory (session_id, key, value, ts) "
                "VALUES (?, ?, ?, CURRENT_TIMESTAMP) "
                "ON CONFLICT(session_id, key) "
                "DO UPDATE SET value=excluded.value, ts=excluded.ts",
                (session_id, key, str(value)),
            )
        conn.commit()


def clear_core_memory(session_id: str) -> None:
    """Delete all core memory entries for *session_id* (used on session reset)."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "DELETE FROM core_memory WHERE session_id = ?", (session_id,)
        )
        conn.commit()

_GLOBAL_SESSION_ID = "__global__"
_GLOBAL_MONITORING_KEY = "monitoring_global_v1"
 
 
def save_global_monitoring_stats(stats: dict) -> None:
    """Persist cross-session monitoring aggregates to session_meta.
 
    Uses the sentinel session_id '__global__' so no new table is required.
    The value is JSON-serialised and stored under key 'monitoring_global_v1'.
    """
    _meta_set(_GLOBAL_SESSION_ID, _GLOBAL_MONITORING_KEY, json.dumps(stats))
 
 
def load_global_monitoring_stats() -> dict | None:
    """Load cross-session monitoring aggregates from session_meta.
 
    Returns the parsed dict, or None if no data has been saved yet.
    """
    raw = _meta_get(_GLOBAL_SESSION_ID, _GLOBAL_MONITORING_KEY)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None