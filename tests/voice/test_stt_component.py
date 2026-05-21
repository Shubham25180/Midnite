import sys
from unittest.mock import MagicMock

# Patch heavy native deps before any Skynet import touches them
sys.modules.setdefault("pyaudio", MagicMock())
sys.modules.setdefault("faster_whisper", MagicMock())

import asyncio
import pytest
from unittest.mock import patch
from Skynet.voice.stt import STTComponent
from Skynet.core.runtime_state import ComponentState
from Skynet.core.event_bus import EventBus
from Skynet.core.events import STTTranscribedEvent


@pytest.fixture
def bus():
    return EventBus()


@pytest.mark.asyncio
async def test_stt_starts_and_reaches_idle(bus):
    # WhisperModel is now imported lazily inside _load_model
    with patch("faster_whisper.WhisperModel") as MockModel:
        MockModel.return_value = MagicMock()
        stt = STTComponent(bus=bus, model_name="base")
        await stt.start()
        # start() returns immediately — model loads in background
        assert stt.health() == ComponentState.IDLE
        await asyncio.sleep(0.1)  # let background thread finish
        await stt.stop()


@pytest.mark.asyncio
async def test_stt_emits_transcribed_event(bus):
    received = []
    bus.subscribe(STTTranscribedEvent, received.append)

    mock_model = MagicMock()
    mock_seg = MagicMock()
    mock_seg.text = "hello"
    mock_model.transcribe.return_value = ([mock_seg], None)

    with patch("faster_whisper.WhisperModel", return_value=mock_model):
        stt = STTComponent(bus=bus, model_name="base")
        await stt.start()
        await asyncio.sleep(0.1)  # let _load_model background thread set model_ready
        stt._emit_transcript("hello")
        assert len(received) == 1
        assert received[0].transcript == "hello"
        await stt.stop()
