# tests/core/test_component_registry.py
import pytest
from Skynet.core.component_registry import ComponentRegistry
from Skynet.core.runtime_state import RuntimeState, ComponentState
from Skynet.core.event_bus import EventBus


@pytest.fixture
def setup():
    bus = EventBus()
    state = RuntimeState(bus)
    registry = ComponentRegistry(state)
    return bus, state, registry


def test_register_component_no_deps(setup):
    _, _, registry = setup
    registry.register("audio_device", deps=[])
    assert "audio_device" in registry.components


def test_register_with_dependency(setup):
    _, _, registry = setup
    registry.register("audio_device", deps=[])
    registry.register("stt", deps=["audio_device"])
    assert "audio_device" in registry.deps_of("stt")


def test_register_missing_dep_raises(setup):
    _, _, registry = setup
    with pytest.raises(ValueError, match="unknown dependency"):
        registry.register("stt", deps=["audio_device"])


def test_topological_start_order(setup):
    _, _, registry = setup
    registry.register("audio_device", deps=[])
    registry.register("stt", deps=["audio_device"])
    registry.register("tts", deps=["audio_device"])
    registry.register("llm1_provider", deps=[])
    registry.register("orchestrator", deps=["llm1_provider"])
    order = registry.start_order()
    assert set(order) == {"audio_device", "stt", "tts", "llm1_provider", "orchestrator"}
    assert order.index("audio_device") < order.index("stt")
    assert order.index("audio_device") < order.index("tts")
    assert order.index("llm1_provider") < order.index("orchestrator")


def test_cascade_failure_to_dependents(setup):
    _, state, registry = setup
    registry.register("audio_device", deps=[])
    registry.register("stt", deps=["audio_device"])
    # Advance states so cascade transition is valid
    state.set_component_state("audio_device", ComponentState.STARTING, source="test")
    state.set_component_state("audio_device", ComponentState.IDLE, source="test")
    state.set_component_state("stt", ComponentState.STARTING, source="test")
    state.set_component_state("stt", ComponentState.IDLE, source="test")
    # Simulate audio_device failing
    state.set_component_state("audio_device", ComponentState.DEGRADED, source="test")
    state.set_component_state("audio_device", ComponentState.FAILED, source="test")
    registry.cascade_failure("audio_device")
    assert state.get_component_state("stt") == ComponentState.FAILED
