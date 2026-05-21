from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SkillResult:
    """What TaskRouter returns after routing a transcript."""
    transcript: str
    # Name of matched skill, for logging
    skill: str = "chat"
    # Skip LLM entirely — speak this string directly
    direct: str | None = None
    # Replaces the entire system prompt (rare edge cases only)
    prompt_override: str | None = None


class Skill:
    name: str = "base"

    def match(self, transcript: str) -> bool:
        raise NotImplementedError

    def build(self, transcript: str) -> SkillResult:
        raise NotImplementedError
