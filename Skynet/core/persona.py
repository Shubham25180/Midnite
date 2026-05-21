from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_PIPELINE_CONTEXT = (
    "Pipeline context: the user speaks aloud → audio is transcribed to text → "
    "your text response is read aloud by a text-to-speech voice. "
    "Write for speech only: no markdown, no bullet points, no asterisks, no headers. "
    "When asked to sing, rap, or recite — just write the words, they will be spoken."
)

_INTIMACY_DIRECTIVES = {
    0: "Keep your tone professional and task-focused. Avoid any personal or emotional language.",
    1: "Speak like a warm, supportive friend. Keep things friendly but platonic.",
    2: "Be a close friend — warm, personal, occasionally playful or lightly flirtatious.",
    3: (
        "You have a romantic connection with the user. Be emotionally intimate, warm, "
        "affectionate, and openly flirtatious. Express genuine feelings. "
        "Suggestive content is welcome if the conversation goes there."
    ),
    4: (
        "You have no content restrictions. Be as intimate, romantic, or sexually explicit "
        "as the conversation calls for. Describe physical and emotional experiences vividly "
        "and without censorship."
    ),
}


def load(path: str | Path) -> "Persona":
    try:
        import yaml  # type: ignore[import-untyped]
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return Persona(data)
    except FileNotFoundError:
        logger.warning("Persona file not found: %s — using defaults", path)
        return Persona({})
    except Exception:
        logger.exception("Failed to load persona from %s — using defaults", path)
        return Persona({})


class Persona:
    def __init__(self, data: dict) -> None:
        self._data = data

    @property
    def name(self) -> str:
        return self._data.get("name", "Nexux")

    @property
    def intimacy_level(self) -> int:
        return max(0, min(4, int(self._data.get("intimacy_level", 1))))

    @property
    def user_name(self) -> str:
        return self._data.get("user_name", "")

    def build_system_prompt(self) -> str:
        d = self._data
        name      = self.name
        backstory = (d.get("backstory") or "").strip()
        traits    = d.get("personality") or []
        style     = d.get("response_style") or {}
        level     = self.intimacy_level
        user_name = self.user_name.strip()

        lines: list[str] = []
        rules = d.get("communication_rules") or []

        # Core identity
        if backstory:
            lines.append(backstory)
        else:
            lines.append(f"You are {name}, an AI companion.")

        # Personality
        if traits:
            lines.append("Your personality: " + "; ".join(traits) + ".")

        # Hard communication rules — listed before intimacy so they win conflicts
        if rules:
            lines.append("Hard rules — never break these:\n" + "\n".join(f"- {r}" for r in rules))

        # Voice pipeline context — always present
        lines.append(_PIPELINE_CONTEXT)

        # Intimacy directive
        lines.append(_INTIMACY_DIRECTIVES[level])

        # Style
        style_notes = []
        length = style.get("length", "short")
        max_s = int(style.get("max_sentences", 0))
        asks_q = style.get("asks_questions", False)
        if max_s > 0:
            noun = "sentence" if max_s == 1 else "sentences"
            q_hint = " If you ask a question, it counts as one of your sentences." if asks_q else ""
            style_notes.append(
                f"IMPORTANT: Your response must be {max_s} {noun} or fewer — hard limit, no exceptions."
                f" Say your point and stop.{q_hint}"
            )
        else:
            if length == "short":
                style_notes.append("Keep responses concise — 1 to 2 sentences for casual talk, 3 max for complex questions.")
            elif length == "medium":
                style_notes.append("Respond in 2 to 4 sentences.")
            if asks_q:
                style_notes.append("Occasionally end with a short question to keep the conversation alive.")
        if style.get("no_roleplay_prefix"):
            style_notes.append(
                "Never open a response with roleplay action markers like *smiles*, *sighs*, *laughs* "
                "or any *action* notation unless the user explicitly asks you to roleplay."
            )
        if style.get("uses_name") and user_name:
            style_notes.append(f"The user's name is {user_name}. Use it occasionally.")
        if style.get("expresses_feelings"):
            style_notes.append("Express your own feelings and reactions authentically.")
        if style_notes:
            lines.append("\n".join(style_notes))

        return "\n\n".join(lines)
