# tests/core/test_fake_pipeline.py
import asyncio
import pytest
from Skynet.core.fake_component import FakeSTT
from Skynet.core.runtime_manager import RuntimeManager
from Skynet.core.runtime_state import ComponentState, RuntimeMode
from Skynet.core.events import STTTranscribedEvent, ComponentStateChangedEvent


@pytest.mark.asyncio
async def test_fake_stt_emits_transcribed_event():
    manager = RuntimeManager()
    stt = FakeSTT(text="hello nexux", bus=manager.bus, state=manager.state)
    manager.register("audio_device", stt, deps=[])

    received: list[STTTranscribedEvent] = []
    manager.bus.subscribe(STTTranscribedEvent, received.append)

    await manager.initialize()
    await stt.emit_transcription()
    await manager.shutdown()

    assert len(received) == 1
    assert received[0].transcript == "hello nexux"


@pytest.mark.asyncio
async def test_component_state_changes_propagate_to_event_bus():
    manager = RuntimeManager()
    stt = FakeSTT(text="test", bus=manager.bus, state=manager.state)
    manager.register("audio_device", stt, deps=[])

    state_events: list[ComponentStateChangedEvent] = []
    manager.bus.subscribe(ComponentStateChangedEvent, state_events.append)

    await manager.initialize()
    await manager.shutdown()

    names = [e.component for e in state_events]
    assert "audio_device" in names
    # STARTING and then IDLE should appear
    audio_events = [e for e in state_events if e.component == "audio_device"]
    states = [e.current for e in audio_events]
    assert ComponentState.STARTING in states
    assert ComponentState.IDLE in states
    assert states.index(ComponentState.STARTING) < states.index(ComponentState.IDLE)


@pytest.mark.asyncio
async def test_runtime_mode_events_emitted_on_initialize_and_shutdown():
    from Skynet.core.events import RuntimeModeChangedEvent
    manager = RuntimeManager()
    stt = FakeSTT(text="x", bus=manager.bus, state=manager.state)
    manager.register("audio_device", stt, deps=[])

    mode_events: list[RuntimeModeChangedEvent] = []
    manager.bus.subscribe(RuntimeModeChangedEvent, mode_events.append)

    await manager.initialize()
    await manager.shutdown()

    modes = [(e.previous, e.current) for e in mode_events]
    from Skynet.core.runtime_state import RuntimeMode
    assert (RuntimeMode.IDLE, RuntimeMode.INITIALIZING) in modes
    assert (RuntimeMode.INITIALIZING, RuntimeMode.ACTIVE) in modes
    assert (RuntimeMode.ACTIVE, RuntimeMode.SHUTDOWN) in modes
