from __future__ import annotations

import re

from Skynet.task.skill import Skill, SkillResult

# Verbs that suggest the LLM needs to DO something, not just chat
_VERBS = re.compile(
    r"\b(create|write|build|make|add|generate|implement|code|program|"
    r"edit|modify|update|change|fix|refactor|delete|remove|"
    r"run|execute|install|test|deploy|read|open|check|"
    r"show me|list)\b",
    re.IGNORECASE,
)

# Objects that are files, code, or system things (allow plural/suffix with \w*)
_OBJECTS = re.compile(
    r"\b(skills?|files?|codes?|scripts?|functions?|features?|tools?|"
    r"modules?|classes?|methods?|tests?|packages?|"
    r"pip|commands?|bash|terminal|folders?|director(y|ies)|"
    r"configs?|settings|persona|yaml|json|python|\.py)\b",
    re.IGNORECASE,
)

_ALWAYS_AGENTIC = re.compile(
    r"\b("
    r"what (skills?|files?|components?) (do you have|are|exist)"
    r"|what (are your|can you) (skills?|capabilities|abilities|tools?)"
    r"|what can you do"
    r"|(do you have|have you got) (any )?(skills?|tools?|capabilities)"
    r"|system (status|info|state)"
    r"|show (me )?your (skills?|files?|status)"
    r"|run (the )?tests?"
    r"|reload (skills?|the system)"
    r")\b",
    re.IGNORECASE,
)


class AgenticSkill(Skill):
    name = "agentic"

    def match(self, transcript: str) -> bool:
        if _ALWAYS_AGENTIC.search(transcript):
            return True
        return bool(_VERBS.search(transcript) and _OBJECTS.search(transcript))

    def build(self, transcript: str) -> SkillResult:
        return SkillResult(
            transcript=transcript,
            skill=self.name,
            agentic=True,
        )
