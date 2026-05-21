from __future__ import annotations

import json
import logging
import threading
from typing import TYPE_CHECKING

from Skynet.memory import session_store

if TYPE_CHECKING:
    from Skynet.providers.base import LLMProvider

logger = logging.getLogger(__name__)

_SUMMARY_PROMPT = """\
You are a memory compression assistant. Given a conversation, produce:
1. A 2-3 sentence summary of what was discussed.
2. A JSON list of important facts to remember about the user (max 5 items).
   Facts should be concrete and reusable: preferences, names, stated goals, habits.
   If there are no meaningful facts, return an empty list.

Respond ONLY with valid JSON in this exact format:
{"summary": "...", "facts": ["...", "..."]}

Do not add any other text."""


def _extract(response: str) -> tuple[str, list[str]]:
    """Parse LLM response into (summary, facts). Gracefully handles bad output."""
    text = response.strip()
    start = text.find("{")
    end = text.rfind("}") + 1
    if start == -1 or end == 0:
        return text[:300], []
    try:
        data = json.loads(text[start:end])
        return str(data.get("summary", text[:300])), list(data.get("facts", []))
    except Exception:
        return text[:300], []


def compress_async(
    history: list[tuple[str, str]],
    provider: "LLMProvider",
    turn_count: int = 0,
) -> threading.Thread:
    """Compress `history` in a background thread and save to session store."""
    def _run() -> None:
        try:
            turns_text = "\n".join(
                f"User: {u}\nNexux: {a}" for u, a in history
            )
            messages = [
                {"role": "system", "content": _SUMMARY_PROMPT},
                {"role": "user", "content": turns_text},
            ]
            response = provider.complete(messages)
            summary, facts = _extract(response)

            # SQLite — fast retrieval by recency
            session_store.save_session_summary(summary, facts, turn_count)

            # Qdrant — semantic retrieval by meaning
            from Skynet.memory import vector_store
            vector_store.store(summary, entry_type="summary")
            for fact in facts:
                vector_store.store(fact, entry_type="fact")

            total = vector_store.count()
            logger.info(
                "Memory compressed: %d turns → summary + %d facts  (Qdrant total: %d)",
                turn_count, len(facts), total,
            )
        except Exception:
            logger.exception("Memory compression failed")

    t = threading.Thread(target=_run, daemon=False, name="mem-compress")
    t.start()
    return t
