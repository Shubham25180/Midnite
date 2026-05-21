# Skynet/ui/ws/stream.py
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from Skynet.core.event_bus import EventBus

from Skynet.core.events import (
    ComponentStateChangedEvent,
    RuntimeModeChangedEvent,
    STTTranscribedEvent,
    OrchestratorResponseEvent,
    ContextStatsEvent,
)

logger = logging.getLogger(__name__)


class EventStreamBroadcaster:
    """Push events to each connected WS client via its own asyncio.Queue.

    Events are published from various threads (STT daemon, asyncio loop).
    All pushes go through loop.call_soon_threadsafe so put_nowait is always
    called from the event loop thread, which is the only safe way to use
    asyncio.Queue without a lock.
    """

    def __init__(self, bus: EventBus) -> None:
        self._bus = bus
        self._loop: asyncio.AbstractEventLoop | None = None
        self._clients: set[asyncio.Queue] = set()
        self._tokens: list[str] = []

    def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._tokens = [
            self._bus.subscribe(ComponentStateChangedEvent, self._on_component_state),
            self._bus.subscribe(RuntimeModeChangedEvent, self._on_runtime_mode),
            self._bus.subscribe(STTTranscribedEvent, self._on_stt),
            self._bus.subscribe(OrchestratorResponseEvent, self._on_response),
            self._bus.subscribe(ContextStatsEvent, self._on_context_stats),
        ]

    def stop(self) -> None:
        for token in self._tokens:
            self._bus.unsubscribe(token)
        self._tokens = []

    def add_client(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=500)
        self._clients.add(q)
        return q

    def remove_client(self, q: asyncio.Queue) -> None:
        self._clients.discard(q)

    # ── internal push ─────────────────────────────────────────────────────

    def _push(self, msg: dict) -> None:
        if self._loop is None:
            return

        def _enqueue() -> None:
            for q in list(self._clients):
                try:
                    q.put_nowait(msg)
                except asyncio.QueueFull:
                    logger.warning("WS client queue full — dropping %s", msg.get("type"))

        self._loop.call_soon_threadsafe(_enqueue)

    # ── event handlers ─────────────────────────────────────────────────────

    def _on_component_state(self, event: ComponentStateChangedEvent) -> None:
        self._push({
            "type": "component_state",
            "component": event.component,
            "previous": event.previous.name.lower() if event.previous is not None else None,
            "current": event.current.name.lower() if event.current is not None else None,
            "timestamp": event.timestamp,
        })

    def _on_runtime_mode(self, event: RuntimeModeChangedEvent) -> None:
        self._push({
            "type": "runtime_mode",
            "previous": event.previous.name.lower() if event.previous is not None else None,
            "current": event.current.name.lower() if event.current is not None else None,
            "timestamp": event.timestamp,
        })

    def _on_stt(self, event: STTTranscribedEvent) -> None:
        self._push({
            "type": "stt_transcript",
            "transcript": event.transcript,
            "timestamp": event.timestamp,
        })

    def _on_response(self, event: OrchestratorResponseEvent) -> None:
        self._push({
            "type": "orchestrator_response",
            "response": event.response,
            "timestamp": event.timestamp,
        })

    def _on_context_stats(self, event: ContextStatsEvent) -> None:
        self._push({
            "type": "context_stats",
            "turns_used": event.turns_used,
            "turns_total": event.turns_total,
            "tokens_est": event.tokens_est,
            "timestamp": event.timestamp,
        })
