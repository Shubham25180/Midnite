from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any

import sounddevice as sd

if TYPE_CHECKING:
    from Skynet.core.event_bus import EventBus

from Skynet.core.component import Component
from Skynet.core.events import OrchestratorResponseEvent
from Skynet.core.runtime_state import ComponentState

logger = logging.getLogger(__name__)

# How long _speak will wait for the model before giving up on a single utterance.
# Short enough that we don't stall the speech queue; long enough for fast loads.
_SPEAK_WAIT_SEC = 10
# How long we'll wait at all (covers cold model download on first run — kokoro is 327 MB)
_MODEL_LOAD_TIMEOUT = 600


def _kokoro_lang(voice_id: str) -> str:
    return {"b": "b", "j": "j", "z": "z", "e": "e", "f": "f", "p": "p"}.get(
        voice_id[:1].lower(), "a"
    )


class TTSComponent(Component):
    def __init__(
        self,
        *,
        bus: EventBus,
        backend: str = "f5tts",
        ref_audio: str = "",
        ref_text: str = "",
        speed: float = 1.0,
        voice_id: str = "af_bella",
    ) -> None:
        super().__init__(name="tts")
        self._bus = bus
        self._backend = backend
        self._ref_audio = ref_audio
        self._ref_text = ref_text
        self._speed = speed
        self._voice_id = voice_id
        self._model: Any = None
        self._model_ready = threading.Event()
        self._health = ComponentState.OFFLINE
        self._token: str | None = None

        # Speech synthesis runs here — single worker keeps audio sequential
        self._speech_executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="tts-speech"
        )
        # Model loading runs here — never blocks the speech queue
        self._load_executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="tts-load"
        )

    async def start(self) -> None:
        if self._backend == "f5tts" and not Path(self._ref_audio).exists():
            logger.error("TTS ref audio missing: %s — drop a 10-15s WAV there", self._ref_audio)
            self._health = ComponentState.DEGRADED
            return
        self._token = self._bus.subscribe(OrchestratorResponseEvent, self._on_response)
        self._health = ComponentState.IDLE
        self._load_executor.submit(self._load_model)

    def _load_model(self) -> None:
        try:
            if self._backend == "kokoro":
                self._load_kokoro()
            else:
                self._load_f5tts()
        except Exception:
            logger.exception("TTS model failed to load (backend=%s)", self._backend)

    def _load_f5tts(self) -> None:
        from f5_tts.api import F5TTS
        self._model = F5TTS()
        if not self._ref_text:
            self._ref_text = self._transcribe_ref_audio(self._ref_audio)
        self._model_ready.set()
        logger.info("F5-TTS model ready")

    def _load_kokoro(self) -> None:
        from kokoro import KPipeline
        lang = _kokoro_lang(self._voice_id)
        self._model = KPipeline(lang_code=lang)
        self._model_ready.set()
        logger.info("Kokoro model ready (lang=%s, voice=%s)", lang, self._voice_id)

    def _transcribe_ref_audio(self, path: str) -> str:
        try:
            from faster_whisper import WhisperModel
            model = WhisperModel("tiny", device="cpu", compute_type="int8")
            segments, _ = model.transcribe(path, language="en", beam_size=1)
            text = " ".join(s.text.strip() for s in segments).strip()
            logger.info("TTS ref audio transcribed: %s", text)
            return text
        except Exception:
            logger.exception("TTS ref transcription failed")
            return ""

    async def stop(self) -> None:
        if self._token:
            self._bus.unsubscribe(self._token)
            self._token = None
        self._speech_executor.shutdown(wait=False)
        self._load_executor.shutdown(wait=False)
        self._model = None
        self._health = ComponentState.OFFLINE

    def health(self) -> ComponentState:
        return self._health

    # ── Live hot-reload setters ─────────────────────────────────────────────

    def set_speed(self, speed: float) -> None:
        self._speed = max(0.5, min(2.0, float(speed)))
        logger.info("TTS speed → %.1f", self._speed)

    def set_ref_audio(self, path: str, ref_text: str) -> None:
        self._ref_audio = path
        self._ref_text = ref_text
        logger.info("TTS ref audio → %s", path)

    def set_voice(self, voice_id: str) -> None:
        """Hot-swap Kokoro voice. Reloads model only if lang_code changes."""
        if self._backend != "kokoro":
            self._voice_id = voice_id
            return
        needs_reload = _kokoro_lang(voice_id) != _kokoro_lang(self._voice_id)
        self._voice_id = voice_id
        if needs_reload:
            self._model = None
            self._model_ready.clear()
            self._load_executor.submit(self._load_model)
            logger.info("Kokoro reloading for lang change (voice=%s)", voice_id)
        else:
            logger.info("Kokoro voice → %s", voice_id)

    def set_backend(self, backend: str, voice_id: str | None = None) -> None:
        """Hot-swap TTS backend. Uses the load executor so speech is never blocked."""
        new_voice = voice_id or self._voice_id
        needs_reload = backend != self._backend or (
            backend == "kokoro"
            and _kokoro_lang(new_voice) != _kokoro_lang(self._voice_id)
        )
        self._backend = backend
        if voice_id:
            self._voice_id = voice_id
        if not needs_reload:
            return
        self._model = None
        self._model_ready.clear()
        self._load_executor.submit(self._load_model)
        logger.info("TTS backend → %s (voice=%s)", self._backend, self._voice_id)

    def get_backend(self) -> str:
        return self._backend

    def get_voice_id(self) -> str:
        return self._voice_id

    # ── Event handler ───────────────────────────────────────────────────────

    def _on_response(self, event: OrchestratorResponseEvent) -> None:
        if self._health == ComponentState.IDLE and event.response:
            loop = asyncio.get_event_loop()
            loop.run_in_executor(self._speech_executor, self._speak, event.response)

    # ── Speech ──────────────────────────────────────────────────────────────

    def _speak(self, text: str) -> None:
        if self._backend == "kokoro":
            self._speak_kokoro(text)
        else:
            self._speak_f5tts(text)

    def _wait_for_model(self) -> bool:
        """Wait for model in small increments; return True when ready."""
        waited = 0.0
        while waited < _MODEL_LOAD_TIMEOUT:
            if self._model_ready.wait(timeout=_SPEAK_WAIT_SEC):
                return True
            waited += _SPEAK_WAIT_SEC
            logger.info("TTS waiting for model… (%.0fs / %ds)", waited, _MODEL_LOAD_TIMEOUT)
        logger.warning("TTS model not ready after %ds — dropping utterance", _MODEL_LOAD_TIMEOUT)
        return False

    def _speak_f5tts(self, text: str) -> None:
        if not self._wait_for_model():
            return
        try:
            import time
            from Skynet.core.prosody import format_for_tts
            import numpy as np
            tts_text = format_for_tts(text)
            if not tts_text:
                return
            t0 = time.perf_counter()
            wav, sr, _ = self._model.infer(
                ref_file=self._ref_audio,
                ref_text=self._ref_text,
                gen_text=tts_text,
                speed=self._speed,
            )
            wav = np.concatenate([wav, np.zeros(int(sr * 0.3), dtype=wav.dtype)])
            t_synth = time.perf_counter()
            sd.play(wav, sr)
            sd.wait()
            t_done = time.perf_counter()
            logger.info("[T] TTS synth=%dms play=%dms  %d chars",
                        int((t_synth - t0) * 1000), int((t_done - t_synth) * 1000), len(tts_text))
        except Exception:
            logger.exception("F5-TTS failed to speak")

    def _kokoro_voice_arg(self) -> str:
        """Use pre-downloaded local .pt if available, else voice name (HF hub lookup)."""
        local = Path("config/voices/kokoro/voices") / f"{self._voice_id}.pt"
        return str(local) if local.exists() else self._voice_id

    def _speak_kokoro(self, text: str) -> None:
        if not self._wait_for_model():
            return
        try:
            import time
            from Skynet.core.prosody import format_for_tts
            import numpy as np
            tts_text = format_for_tts(text)
            if not tts_text:
                return
            voice = self._kokoro_voice_arg()
            t0 = time.perf_counter()
            chunks = [
                audio
                for _, _, audio in self._model(tts_text, voice=voice, speed=self._speed)
            ]
            if not chunks:
                return
            wav = np.concatenate(chunks)
            wav = np.concatenate([wav, np.zeros(int(24000 * 0.3), dtype=wav.dtype)])
            t_synth = time.perf_counter()
            sd.play(wav, 24000)
            sd.wait()
            t_done = time.perf_counter()
            logger.info("[T] TTS synth=%dms play=%dms  %d chars",
                        int((t_synth - t0) * 1000), int((t_done - t_synth) * 1000), len(tts_text))
        except Exception:
            logger.exception("Kokoro TTS failed to speak")
