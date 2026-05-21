import asyncio
import pytest
from unittest.mock import MagicMock
from Skynet.core.orchestrator import Orchestrator, _WINDOW
from Skynet.core.runtime_state import ComponentState
from Skynet.core.event_bus import EventBus
from Skynet.core.events import STTTranscribedEvent, OrchestratorResponseEvent


@pytest.fixture
def bus():
    return EventBus()


@pytest.fixture
def mock_provider():
    p = MagicMock()
    p.stream.side_effect = lambda msgs: iter(["I can help with that."])
    # Agentic path: return text with no tool calls so the loop terminates
    p.complete_with_tools.return_value = ("I can help with that.", [])
    return p


@pytest.mark.asyncio
async def test_orchestrator_starts_and_reaches_idle(bus, mock_provider):
    orc = Orchestrator(bus=bus, provider=mock_provider)
    await orc.start()
    assert orc.health() == ComponentState.IDLE
    await orc.stop()


@pytest.mark.asyncio
async def test_orchestrator_responds_to_stt_event(bus, mock_provider):
    responses = []
    bus.subscribe(OrchestratorResponseEvent, responses.append)

    orc = Orchestrator(bus=bus, provider=mock_provider)
    await orc.start()
    bus.publish(STTTranscribedEvent(transcript="what can you do?"))
    # Qdrant client cold-init can take ~1s on first call — wait up to 10s
    deadline = asyncio.get_event_loop().time() + 10.0
    while not responses and asyncio.get_event_loop().time() < deadline:
        await asyncio.sleep(0.05)
    await orc.stop()

    assert len(responses) >= 1
    combined = " ".join(r.response for r in responses)
    assert "I can help with that." in combined


@pytest.mark.asyncio
async def test_rolling_window_limits_context(bus, mock_provider):
    orc = Orchestrator(bus=bus, provider=mock_provider)
    await orc.start()

    for i in range(_WINDOW + 2):
        bus.publish(STTTranscribedEvent(transcript=f"turn {i}"))
        await asyncio.sleep(0.1)

    last_call_msgs = mock_provider.complete_with_tools.call_args[0][0]
    user_msgs = [m for m in last_call_msgs if m["role"] == "user"]
    assert len(user_msgs) <= _WINDOW, f"Expected <={_WINDOW} user msgs in context, got {len(user_msgs)}"

    content_texts = [m.get("content") or "" for m in last_call_msgs]
    assert not any("turn 0" in t for t in content_texts)

    await orc.stop()
