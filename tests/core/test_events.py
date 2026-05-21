import time
from Skynet.core.events import (
    BaseEvent, STTTranscribedEvent, OrchestratorResponseEvent,
    ComponentStateChangedEvent, RuntimeModeChangedEvent,
)
from Skynet.core.runtime_state import ComponentState, RuntimeMode


def test_base_event_auto_timestamp():
    before = time.time()
    e = BaseEvent()
    after = time.time()
    assert before <= e.timestamp <= after


def test_base_event_sequence_ids_increment():
    e1 = BaseEvent()
    e2 = BaseEvent()
    assert e2.sequence_id == e1.sequence_id + 1


def test_stt_event_carries_transcript():
    e = STTTranscribedEvent(transcript="hello world")
    assert e.transcript == "hello world"
    assert hasattr(e, "timestamp")
    assert hasattr(e, "sequence_id")


def test_orchestrator_response_event():
    e = OrchestratorResponseEvent(response="I can help with that.")
    assert e.response == "I can help with that."


def test_component_state_changed_event():
    e = ComponentStateChangedEvent(
        component="stt",
        previous=ComponentState.OFFLINE,
        current=ComponentState.STARTING,
    )
    assert e.component == "stt"
    assert e.previous == ComponentState.OFFLINE
    assert e.current == ComponentState.STARTING


def test_runtime_mode_changed_event():
    e = RuntimeModeChangedEvent(
        previous=RuntimeMode.IDLE,
        current=RuntimeMode.INITIALIZING,
    )
    assert e.previous == RuntimeMode.IDLE
    assert e.current == RuntimeMode.INITIALIZING
