# Skynet/core/prosody.py
"""Prosody formatter — applied to text just before TTS synthesis.

The UI always shows the raw LLM text. This module shapes the same text
for the voice layer: strips roleplay markers, injects ellipsis pauses
where speech would naturally hesitate, and normalises punctuation.
"""
from __future__ import annotations

import re

# Strip *action* and _action_ roleplay markers (including surrounding spaces)
_ACTION = re.compile(r'\s*[*_][^*_\n]+[*_]\s*')

# "word, and/but/so/or/yet word" → "word... and word"  (coordinating pause)
_COORD_COMMA = re.compile(r',\s+(and|but|so|or|yet)\b', re.IGNORECASE)

# Em-dash used as dramatic pause → ellipsis
_EM_DASH = re.compile(r'\s*—\s*')

# Trailing "..." already present — normalise to single ellipsis
_MULTI_DOT = re.compile(r'\.{2,}')

# Collapse multiple spaces
_SPACES = re.compile(r'  +')


def format_for_tts(text: str) -> str:
    """Return TTS-ready version of *text* with natural pause markers."""
    # 1. Strip roleplay action markers
    text = _ACTION.sub(' ', text)

    # 2. Coordinating comma → breath pause
    text = _COORD_COMMA.sub(r'... \1', text)

    # 3. Em-dash → pause
    text = _EM_DASH.sub('... ', text)

    # 4. Normalise existing ellipses
    text = _MULTI_DOT.sub('...', text)

    # 5. Clean whitespace
    text = _SPACES.sub(' ', text).strip()

    return text
