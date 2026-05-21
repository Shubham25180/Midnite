from __future__ import annotations

import json
import logging
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

_DB_PATH = Path("logs/memory.db")
_lock = threading.Lock()


def _conn() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    c.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            ts        TEXT NOT NULL,
            summary   TEXT NOT NULL,
            facts     TEXT DEFAULT '[]',
            turn_count INTEGER DEFAULT 0
        )
    """)
    c.commit()
    return c


def save_session_summary(summary: str, facts: list[str], turn_count: int = 0) -> None:
    """Persist a compressed session summary."""
    with _lock:
        try:
            c = _conn()
            c.execute(
                "INSERT INTO sessions (ts, summary, facts, turn_count) VALUES (?,?,?,?)",
                (datetime.now().isoformat(), summary, json.dumps(facts), turn_count),
            )
            c.commit()
            c.close()
            logger.info("Session summary saved (%d turns)", turn_count)
        except Exception:
            logger.exception("Session store write failed")


def load_recent_summaries(n: int = 3) -> list[dict]:
    """Return the N most recent session summaries, newest first."""
    with _lock:
        try:
            c = _conn()
            rows = c.execute(
                "SELECT ts, summary, facts, turn_count FROM sessions ORDER BY id DESC LIMIT ?",
                (n,),
            ).fetchall()
            c.close()
            return [
                {
                    "ts": r[0],
                    "summary": r[1],
                    "facts": json.loads(r[2]),
                    "turn_count": r[3],
                }
                for r in rows
            ]
        except Exception:
            logger.exception("Session store read failed")
            return []


def build_memory_context(n_sessions: int = 2) -> str:
    """
    Return a compact memory string to inject into LLM1 context.
    Returns empty string if no memory exists yet.
    """
    sessions = load_recent_summaries(n_sessions)
    if not sessions:
        return ""

    parts: list[str] = []
    for s in reversed(sessions):   # chronological order
        ts = s["ts"][:10]          # date only
        parts.append(f"[{ts}] {s['summary']}")
        if s["facts"]:
            fact_strs = [
                next(iter(f.values())) if isinstance(f, dict) else str(f)
                for f in s["facts"]
            ]
            parts.append("Known facts: " + "; ".join(fact_strs))

    return "Previous session memory:\n" + "\n".join(parts)
