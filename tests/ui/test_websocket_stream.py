# tests/ui/test_websocket_stream.py
import asyncio
import pytest
from Skynet.core.event_bus import EventBus
from Skynet.core.events import ComponentStateChangedEvent, OrchestratorResponseEvent
from Skynet.core.runtime_state import ComponentState
from Skynet.ui.ws.stream import EventStreamBroadcaster


@pytest.fixture
def bus():
    return EventBus()


@pytest.mark.asyncio
async def test_broadcaster_delivers_to_client(bus):
    broadcaster = EventStreamBroadcaster(bus)
    broadcaster.start()
    q = broadcaster.add_client()

    bus.publish(ComponentStateChangedEvent(
        component="stt",
        previous=ComponentState.OFFLINE,
        current=ComponentState.STARTING,
    ))
    await asyncio.sleep(0.05)

    assert not q.empty()
    msg = q.get_nowait()
    assert msg["type"] == "component_state"
    assert msg["component"] == "stt"
    assert msg["current"] == "starting"

    broadcaster.stop()
    broadcaster.remove_client(q)


@pytest.mark.asyncio
async def test_each_client_gets_own_copy(bus):
    broadcaster = EventStreamBroadcaster(bus)
    broadcaster.start()
    q1 = broadcaster.add_client()
    q2 = broadcaster.add_client()

    bus.publish(OrchestratorResponseEvent(response="hello"))
    await asyncio.sleep(0.05)

    assert not q1.empty()
    assert not q2.empty()
    assert q1.get_nowait()["response"] == "hello"
    assert q2.get_nowait()["response"] == "hello"

    broadcaster.stop()


@pytest.mark.asyncio
async def test_removed_client_gets_no_events(bus):
    broadcaster = EventStreamBroadcaster(bus)
    broadcaster.start()
    q = broadcaster.add_client()
    broadcaster.remove_client(q)

    bus.publish(OrchestratorResponseEvent(response="should not arrive"))
    await asyncio.sleep(0.05)

    assert q.empty()
    broadcaster.stop()
