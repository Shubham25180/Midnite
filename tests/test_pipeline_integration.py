"""tests/test_pipeline_integration.py

Full pipeline integration test: 5 STT turns through the Orchestrator,
asserting the rolling window stays at ≤ _WINDOW user messages in context.
"""
import asyncio
import pytest

from Skynet.core.event_bus import EventBus
from Skynet.core.events import STTTranscribedEvent, OrchestratorResponseEvent
from Skynet.core.orchestrator import Orchestrator, _WINDOW


class MockProvider:
    """Tool-calling mock provider — matches LLMProvider.complete_with_tools(messages, tools)."""

    def __init__(self) -> None:
        self.calls: list[list[dict]] = []
        self._n = 0

    def complete_with_tools(self, messages: list[dict], tools: list[dict]) -> tuple[str, list]:
        self.calls.append(list(messages))
        reply = f"reply {self._n}"
        self._n += 1
        return reply, []  # text, no tool calls

    def stream(self, messages: list[dict]):
        yield ""  # unused; kept for interface compatibility

    def complete(self, messages: list[dict]) -> str:
        raise NotImplementedError


@pytest.mark.asyncio
async def test_pipeline_five_turns_rolling_window():
    bus = EventBus()
    provider = MockProvider()
    orc = Orchestrator(bus=bus, provider=provider)
    await orc.start()

    n_turns = _WINDOW + 2
    for i in range(n_turns):
        done = asyncio.Event()

        def _on_response(event: OrchestratorResponseEvent, _done: asyncio.Event = done) -> None:
            _done.set()

        token = bus.subscribe(OrchestratorResponseEvent, _on_response)
        bus.publish(STTTranscribedEvent(transcript=f"turn {i}"))
        await asyncio.wait_for(done.wait(), timeout=5.0)
        bus.unsubscribe(token)

    assert len(provider.calls) == n_turns, (
        f"Expected {n_turns} provider calls, got {len(provider.calls)}"
    )

    # Once history >= _WINDOW - 1, context is capped at _WINDOW user messages
    for call_idx in range(_WINDOW - 1, n_turns):
        user_msgs = [m for m in provider.calls[call_idx] if m["role"] == "user"]
        assert len(user_msgs) == _WINDOW, (
            f"Turn {call_idx}: expected {_WINDOW} user messages in context, "
            f"got {len(user_msgs)}: {[m['content'] for m in user_msgs]}"
        )

    final_contents = [m["content"] for m in provider.calls[n_turns - 1]]
    assert not any("turn 0" in c for c in final_contents), (
        f"'turn 0' should have been evicted from context by turn {n_turns - 1}, "
        f"but found it in: {final_contents}"
    )

    assert len(orc._history) == n_turns, (
        f"Expected {n_turns} history pairs, got {len(orc._history)}"
    )

    await orc.stop()
