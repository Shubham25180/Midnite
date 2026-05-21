import sys
from unittest.mock import MagicMock

# Patch heavy native deps before any Skynet import touches them
sys.modules.setdefault("f5_tts", MagicMock())
sys.modules.setdefault("f5_tts.api", MagicMock())
sys.modules.setdefault("sounddevice", MagicMock())

import asyncio
import pytest
from unittest.mock import patch, MagicMock
from Skynet.voice.tts import TTSComponent
from Skynet.core.runtime_state import ComponentState
from Skynet.core.event_bus import EventBus
from Skynet.core.events import OrchestratorResponseEvent

_REF = "dummy.wav"
_REF_TEXT = "Hi, I'm Nexux."


@pytest.fixture
def bus():
    return EventBus()


@pytest.mark.asyncio
async def test_tts_starts_and_reaches_idle(bus):
    # F5TTS is imported lazily inside _load_model — patch at the source module
    with patch("f5_tts.api.F5TTS") as MockF5TTS, \
         patch("Skynet.voice.tts.Path") as MockPath:
        MockPath.return_value.exists.return_value = True
        MockF5TTS.return_value = MagicMock()
        tts = TTSComponent(bus=bus, ref_audio=_REF, ref_text=_REF_TEXT)
        await tts.start()
        assert tts.health() == ComponentState.IDLE
        await tts.stop()


@pytest.mark.asyncio
async def test_tts_degrades_when_ref_audio_missing(bus):
    with patch("f5_tts.api.F5TTS"), \
         patch("Skynet.voice.tts.Path") as MockPath:
        MockPath.return_value.exists.return_value = False
        tts = TTSComponent(bus=bus, ref_audio="missing.wav", ref_text=_REF_TEXT)
        await tts.start()
        assert tts.health() == ComponentState.DEGRADED


@pytest.mark.asyncio
async def test_tts_speaks_on_orchestrator_event(bus):
    import numpy as np
    fake_wav = np.zeros(4800, dtype=np.float32)  # real array so dtype works
    with patch("f5_tts.api.F5TTS") as MockF5TTS, \
         patch("Skynet.voice.tts.Path") as MockPath, \
         patch("Skynet.voice.tts.sd") as mock_sd:
        MockPath.return_value.exists.return_value = True
        mock_model = MagicMock()
        mock_model.infer.return_value = (fake_wav, 24000, None)
        MockF5TTS.return_value = mock_model

        tts = TTSComponent(bus=bus, ref_audio=_REF, ref_text=_REF_TEXT)
        await tts.start()
        await asyncio.sleep(0.1)  # let background _load_model thread finish
        bus.publish(OrchestratorResponseEvent(response="Hello there"))
        await asyncio.sleep(0.1)
        mock_model.infer.assert_called_once_with(
            ref_file=_REF,
            ref_text=_REF_TEXT,
            gen_text="Hello there",
            speed=1.0,
        )
        mock_sd.play.assert_called_once()
        assert mock_sd.play.call_args[0][1] == 24000
        await tts.stop()
