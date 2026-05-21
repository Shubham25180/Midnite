from __future__ import annotations

import time
from dataclasses import dataclass, field
from itertools import count
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from Skynet.core.runtime_state import ComponentState, RuntimeMode

_seq = count(1)


def _next_seq() -> int:
    return next(_seq)


@dataclass
class BaseEvent:
    timestamp: float = field(default_factory=time.time)
    sequence_id: int = field(default_factory=_next_seq)


@dataclass
class STTTranscribedEvent(BaseEvent):
    transcript: str = ""


@dataclass
class OrchestratorResponseEvent(BaseEvent):
    response: str = ""


@dataclass
class ComponentStateChangedEvent(BaseEvent):
    component: str = ""
    previous: ComponentState | None = None
    current: ComponentState | None = None


@dataclass
class RuntimeModeChangedEvent(BaseEvent):
    previous: RuntimeMode | None = None
    current: RuntimeMode | None = None


@dataclass
class ContextStatsEvent(BaseEvent):
    turns_used: int = 0
    turns_total: int = 0
    tokens_est: int = 0   # rough estimate: chars / 4

