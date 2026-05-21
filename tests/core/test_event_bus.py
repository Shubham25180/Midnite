import pytest
from Skynet.core.event_bus import EventBus
from Skynet.core.events import BaseEvent, STTTranscribedEvent, OrchestratorResponseEvent


@pytest.fixture
def bus():
    return EventBus()


def test_subscribe_and_receive(bus):
    received = []
    bus.subscribe(STTTranscribedEvent, received.append)
    bus.publish(STTTranscribedEvent(transcript="hi"))
    assert len(received) == 1
    assert received[0].transcript == "hi"


def test_subscriber_only_receives_its_type(bus):
    stt_received = []
    orc_received = []
    bus.subscribe(STTTranscribedEvent, stt_received.append)
    bus.subscribe(OrchestratorResponseEvent, orc_received.append)
    bus.publish(STTTranscribedEvent(transcript="hello"))
    assert len(stt_received) == 1
    assert len(orc_received) == 0


def test_unsubscribe_via_token(bus):
    received = []
    token = bus.subscribe(STTTranscribedEvent, received.append)
    bus.unsubscribe(token)
    bus.publish(STTTranscribedEvent(transcript="should not arrive"))
    assert len(received) == 0


def test_multiple_subscribers_same_type(bus):
    a, b = [], []
    bus.subscribe(STTTranscribedEvent, a.append)
    bus.subscribe(STTTranscribedEvent, b.append)
    bus.publish(STTTranscribedEvent(transcript="broadcast"))
    assert len(a) == 1
    assert len(b) == 1


def test_publish_non_base_event_raises(bus):
    with pytest.raises(TypeError):
        bus.publish("not an event")


def test_base_event_subclass_only_triggers_exact_type(bus):
    base_received = []
    stt_received = []
    bus.subscribe(BaseEvent, base_received.append)
    bus.subscribe(STTTranscribedEvent, stt_received.append)
    bus.publish(STTTranscribedEvent(transcript="sub"))
    # BaseEvent subscribers should NOT receive STTTranscribedEvent unless explicitly subscribed
    assert len(stt_received) == 1
    assert len(base_received) == 0
