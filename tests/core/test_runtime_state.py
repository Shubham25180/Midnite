import pytest
from Skynet.core.runtime_state import RuntimeState, RuntimeMode, ComponentState
from Skynet.core.event_bus import EventBus
from Skynet.core.events import ComponentStateChangedEvent, RuntimeModeChangedEvent


@pytest.fixture
def bus():
    return EventBus()


@pytest.fixture
def state(bus):
    return RuntimeState(bus)


def test_initial_runtime_mode_is_idle(state):
    assert state.runtime_mode == RuntimeMode.IDLE


def test_initial_component_state_is_offline_for_unknown(state):
    assert state.get_component_state("stt") == ComponentState.OFFLINE


def test_valid_runtime_transition_idle_to_initializing(state):
    state.set_runtime_mode(RuntimeMode.INITIALIZING, source="test")
    assert state.runtime_mode == RuntimeMode.INITIALIZING


def test_invalid_runtime_transition_raises(state):
    with pytest.raises(ValueError, match="Invalid transition"):
        state.set_runtime_mode(RuntimeMode.ACTIVE, source="test")


def test_runtime_transition_emits_event(state, bus):
    received = []
    bus.subscribe(RuntimeModeChangedEvent, received.append)
    state.set_runtime_mode(RuntimeMode.INITIALIZING, source="test")
    assert len(received) == 1
    assert received[0].previous == RuntimeMode.IDLE
    assert received[0].current == RuntimeMode.INITIALIZING


def test_valid_component_transition_offline_to_starting(state):
    state.set_component_state("stt", ComponentState.STARTING, source="test")
    assert state.get_component_state("stt") == ComponentState.STARTING


def test_invalid_component_transition_raises(state):
    with pytest.raises(ValueError, match="Invalid transition"):
        state.set_component_state("stt", ComponentState.BUSY, source="test")


def test_component_transition_emits_event(state, bus):
    received = []
    bus.subscribe(ComponentStateChangedEvent, received.append)
    state.set_component_state("stt", ComponentState.STARTING, source="test")
    assert len(received) == 1
    assert received[0].component == "stt"
    assert received[0].previous == ComponentState.OFFLINE
    assert received[0].current == ComponentState.STARTING


def test_no_direct_state_mutation_allowed(state):
    with pytest.raises(AttributeError):
        state._runtime_mode = RuntimeMode.ACTIVE  # hits __setattr__ guard

    with pytest.raises(AttributeError):
        state.runtime_mode = RuntimeMode.ACTIVE  # hits read-only property
