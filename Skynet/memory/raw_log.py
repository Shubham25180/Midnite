from __future__ import annotations

import json
import logging
import threading
from datetime import date
from pathlib import Path

logger = logging.getLogger(__name__)

_LOG_DIR = Path("logs/sessions")
_lock = threading.Lock()


def _log_path() -> Path:
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    return _LOG_DIR / f"{date.today().isoformat()}.jsonl"


def append(role: str, content: str, metadata: dict | None = None) -> None:
    """Append one turn to today's raw session log. Thread-safe."""
    entry = {"role": role, "content": content}
    if metadata:
        entry.update(metadata)
    line = json.dumps(entry, ensure_ascii=False)
    with _lock:
        try:
            with open(_log_path(), "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            logger.exception("Raw log write failed")


def read_today(limit: int = 100) -> list[dict]:
    """Read up to `limit` entries from today's log (most recent last)."""
    path = _log_path()
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
        entries = [json.loads(l) for l in lines if l.strip()]
        return entries[-limit:]
    except Exception:
        logger.exception("Raw log read failed")
        return []
