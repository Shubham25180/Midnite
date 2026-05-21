from __future__ import annotations

import logging
from pathlib import Path

from Skynet.task.skill import SkillResult

logger = logging.getLogger(__name__)

_INDEX_PATH = Path("config/skills/index.yaml")


class TaskRouter:
    def __init__(self) -> None:
        self._skill_index: list[dict] = []
        self._load_index()

    # ── Routing ────────────────────────────────────────────────────────────────

    def route(self, transcript: str) -> SkillResult:
        """All transcripts pass through — the LLM decides skill routing via load_skill tool."""
        return SkillResult(transcript=transcript)

    # ── Skill index ────────────────────────────────────────────────────────────

    def reload_skills(self) -> int:
        self._load_index()
        logger.info("Skill index reloaded: %d skills", len(self._skill_index))
        return len(self._skill_index)

    def _load_index(self) -> None:
        try:
            import yaml
            if _INDEX_PATH.exists():
                with open(_INDEX_PATH, encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                self._skill_index = data.get("skills", [])
            else:
                self._skill_index = []
        except Exception:
            logger.exception("Failed to load skill index")
            self._skill_index = []

    @property
    def skill_index(self) -> list[dict]:
        return list(self._skill_index)
