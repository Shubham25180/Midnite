from __future__ import annotations

import re

from Skynet.task.skill import Skill, SkillResult

_PATTERN = re.compile(
    # Unambiguous song-object words (almost always a request)
    r"\b(lullaby|ballad|jingle|chant)\b"
    # Verb + object: "sing a song", "rap about X", "write me a poem"
    r"|\b(sing|hum|rap|recite|perform)\s+(me\s+)?(a\s+|about\s+|something|us\s+)?"
    r"(song|lullaby|poem|rap|ballad|verse|jingle|chant|rhyme|lyrics)?\b"
    r"|\bsing\s+(me|us|a|it|something)\b"
    r"|\b(write|make|compose|give\s+me|do)\s+(me\s+|us\s+)?a\s+(song|poem|rap|lullaby|jingle|rhyme)\b",
    re.IGNORECASE,
)


class SingSkill(Skill):
    name = "sing"

    def match(self, transcript: str) -> bool:
        return bool(_PATTERN.search(transcript))

    def build(self, transcript: str) -> SkillResult:
        return SkillResult(
            transcript=transcript,
            skill=self.name,
            inject=(
                "The user wants you to sing, rap, or perform. "
                "Your words will be spoken aloud by TTS — that IS your voice. "
                "Write the actual lyrics or words. No preamble, no 'here goes', "
                "no disclaimers. Just start. Keep it short — 4 to 8 lines max."
            ),
        )
