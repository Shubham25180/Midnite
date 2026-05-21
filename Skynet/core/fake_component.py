# Skynet/core/fake_component.py
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from Skynet.core.event_bus import EventBus
    from Skynet.core.runtime_state import RuntimeState

from Skynet.core.component import Component
from Skynet.core.events import STTTranscribedEvent
from Skynet.core.runtime_state import ComponentState


class FakeSTT(Component):
    """Test double — returns hardcoded text without touching hardware or AI."""

    def __init__(self, *, text: str, bus: EventBus, state: RuntimeState) -> None:
        super().__init__(name="audio_device")
        self._text = text
        self._bus = bus
        self._state = state  # accepted for interface parity; not used by this test double
        self._health = ComponentState.OFFLINE

    async def start(self) -> None:
        self._health = ComponentState.IDLE

    async def stop(self) -> None:
        self._health = ComponentState.OFFLINE

    def health(self) -> ComponentState:
        return self._health

    async def emit_transcription(self) -> None:
        self._bus.publish(STTTranscribedEvent(transcript=self._text))
