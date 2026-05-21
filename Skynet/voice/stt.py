from __future__ import annotations

import logging
import os
import tempfile
import threading
import time
import wave
from typing import TYPE_CHECKING, Any

import pyaudio

if TYPE_CHECKING:
    from Skynet.core.event_bus import EventBus

from Skynet.core.component import Component
from Skynet.core.events import STTTranscribedEvent
from Skynet.core.runtime_state import ComponentState

logger = logging.getLogger(__name__)

_RATE = 16000
_CHANNELS = 1
_CHUNK = 1024
_FORMAT = pyaudio.paInt16
_SILENCE_S = 1.5
_MODEL_LOAD_TIMEOUT = 300
_DEFAULT_SILENCE_DB = 500


def _list_input_devices() -> list[dict]:
    """Return all PyAudio input devices as {index, name}."""
    audio = pyaudio.PyAudio()
    try:
        devices = []
        for i in range(audio.get_device_count()):
            info = audio.get_device_info_by_index(i)
            if info.get("maxInputChannels", 0) > 0:
                devices.append({"index": i, "name": info["name"]})
        return devices
    finally:
        audio.terminate()


def _find_mic_index(name: str) -> int | None:
    """Return the first PyAudio input device whose name contains `name` (case-insensitive)."""
    audio = pyaudio.PyAudio()
    try:
        count = audio.get_device_count()
        logger.info("Audio input devices:")
        for i in range(count):
            info = audio.get_device_info_by_index(i)
            if info.get("maxInputChannels", 0) > 0:
                logger.info("  [%d] %s", i, info["name"])
        name_lower = name.lower()
        for i in range(count):
            info = audio.get_device_info_by_index(i)
            if info.get("maxInputChannels", 0) > 0 and name_lower in info["name"].lower():
                logger.info("STT mic pinned to [%d] %s", i, info["name"])
                return i
        logger.warning("STT mic '%s' not found — falling back to system default", name)
        return None
    finally:
        audio.terminate()


class STTComponent(Component):
    def __init__(
        self,
        *,
        bus: EventBus,
        model_name: str = "base",
        device: str = "cpu",
        compute_type: str = "int8",
        mic_device: str | None = None,
        silence_db: int = _DEFAULT_SILENCE_DB,
        mode: str = "continuous",
    ) -> None:
        super().__init__(name="stt")
        self._bus = bus
        self._model_name = model_name
        self._device = device
        self._compute_type = compute_type
        self._mic_device = mic_device
        self._silence_db = max(100, int(silence_db))
        self._mode: str = mode if mode in ("continuous", "push_to_talk", "disabled") else "continuous"
        self._mic_index: int | None = None
        self._model: Any = None
        self._model_ready = threading.Event()
        self._stop_flag = threading.Event()
        self._ptt_active = threading.Event()
        self._ptt_stop   = threading.Event()
        self._health = ComponentState.OFFLINE

    async def start(self) -> None:
        import asyncio
        self._health = ComponentState.IDLE
        self._stop_flag.clear()
        if self._mic_device:
            self._mic_index = _find_mic_index(self._mic_device)
        asyncio.get_event_loop().run_in_executor(None, self._load_model)
        threading.Thread(target=self._listener_loop, daemon=True, name="stt-loop").start()

    def _load_model(self) -> None:
        try:
            from faster_whisper import WhisperModel
            logger.info("STT loading %s on %s/%s — may download on first run",
                        self._model_name, self._device, self._compute_type)
            self._model = WhisperModel(
                self._model_name,
                device=self._device,
                compute_type=self._compute_type,
                local_files_only=False,  # False on first run to download; True after
            )
            self._model_ready.set()
            logger.info("STT model ready (%s)", self._model_name)
        except Exception:
            logger.exception("STT model failed to load")

    def set_mode(self, mode: str) -> None:
        if mode not in ("continuous", "push_to_talk", "disabled"):
            logger.warning("STT: unknown mode '%s'", mode)
            return
        self._mode = mode
        logger.info("STT mode → %s", mode)
        # Wake the listener loop in case it's blocked on ptt_active
        self._ptt_active.set()
        self._ptt_active.clear()

    def start_ptt(self) -> None:
        if self._mode != "push_to_talk":
            return
        self._ptt_stop.clear()
        self._ptt_active.set()
        logger.info("STT PTT start")

    def stop_ptt(self) -> None:
        self._ptt_stop.set()
        logger.info("STT PTT stop")

    def _listener_loop(self) -> None:
        if not self._model_ready.wait(timeout=_MODEL_LOAD_TIMEOUT):
            logger.warning("STT model not ready — voice loop aborted")
            return
        logger.info("STT listener started (mode=%s)", self._mode)
        while not self._stop_flag.is_set():
            try:
                mode = self._mode
                if mode == "disabled":
                    self._stop_flag.wait(timeout=0.5)
                    continue
                if mode == "push_to_talk":
                    if not self._ptt_active.wait(timeout=0.5):
                        continue
                    if self._stop_flag.is_set():
                        break
                    audio_bytes = self._listen_ptt()
                    self._ptt_active.clear()
                    self._ptt_stop.clear()
                else:
                    audio_bytes = self._listen()
                if not audio_bytes or self._stop_flag.is_set():
                    continue
                text = self._transcribe(audio_bytes)
                if text:
                    logger.info("STT heard: %s", text)
                    self._emit_transcript(text)
            except Exception:
                logger.exception("STT listener error")
                self._stop_flag.wait(timeout=1.0)

    async def stop(self) -> None:
        self._stop_flag.set()
        self._model = None
        self._health = ComponentState.OFFLINE

    def health(self) -> ComponentState:
        return self._health

    @staticmethod
    def list_input_devices() -> list[dict]:
        return _list_input_devices()

    def set_mic_device(self, name: str | None) -> None:
        self._mic_device = name
        self._mic_index = _find_mic_index(name) if name else None
        logger.info("STT mic → %s (index=%s)", name or "default", self._mic_index)

    def set_sensitivity(self, silence_db: int) -> None:
        self._silence_db = max(100, int(silence_db))
        logger.info("STT silence threshold → %d", self._silence_db)

    def transcribe_file(self, path: str, language: str | None = None) -> str:
        """Transcribe any audio file. Auto-detects language when language=None."""
        if not self._model_ready.wait(timeout=30):
            raise RuntimeError("STT model not ready for file transcription")
        kwargs: dict = {"beam_size": 2, "vad_filter": False}
        if language:
            kwargs["language"] = language
        segments, _ = self._model.transcribe(path, **kwargs)
        return " ".join(s.text.strip() for s in segments).strip()

    def _emit_transcript(self, text: str) -> None:
        self._bus.publish(STTTranscribedEvent(transcript=text))

    def listen_and_emit(self) -> None:
        if not self._model_ready.wait(timeout=_MODEL_LOAD_TIMEOUT):
            logger.warning("STT model not ready after %ds — skipping", _MODEL_LOAD_TIMEOUT)
            return
        audio_bytes = self._listen()
        if not audio_bytes:
            return
        text = self._transcribe(audio_bytes)
        if text:
            self._emit_transcript(text)

    def _listen(self) -> bytes:
        audio = pyaudio.PyAudio()
        try:
            stream = audio.open(
                format=_FORMAT, channels=_CHANNELS, rate=_RATE,
                input=True, frames_per_buffer=_CHUNK,
                input_device_index=self._mic_index,
            )
        except Exception:
            audio.terminate()
            return b""
        frames = []
        silent_chunks = 0
        silence_limit = int(_SILENCE_S * _RATE / _CHUNK)
        recording = False
        try:
            while not self._stop_flag.is_set():
                data = stream.read(_CHUNK, exception_on_overflow=False)
                try:
                    amplitude = max(
                        abs(int.from_bytes(data[i:i+2], "little", signed=True))
                        for i in range(0, len(data), 2)
                    )
                except Exception:
                    break
                if amplitude > self._silence_db:
                    recording = True
                    silent_chunks = 0
                    frames.append(data)
                elif recording:
                    frames.append(data)
                    silent_chunks += 1
                    if silent_chunks >= silence_limit:
                        break
        finally:
            stream.stop_stream()
            stream.close()
            audio.terminate()
        return b"".join(frames)

    def _listen_ptt(self) -> bytes:
        """Record until ptt_stop is set (push-to-talk mode)."""
        audio = pyaudio.PyAudio()
        try:
            stream = audio.open(
                format=_FORMAT, channels=_CHANNELS, rate=_RATE,
                input=True, frames_per_buffer=_CHUNK,
                input_device_index=self._mic_index,
            )
        except Exception:
            audio.terminate()
            return b""
        frames = []
        try:
            while not self._ptt_stop.is_set() and not self._stop_flag.is_set():
                frames.append(stream.read(_CHUNK, exception_on_overflow=False))
        finally:
            stream.stop_stream()
            stream.close()
            audio.terminate()
        return b"".join(frames)

    def _transcribe(self, audio_bytes: bytes) -> str:
        # Gate: require at least 1 second of audio (16-bit samples = 2 bytes each)
        if len(audio_bytes) < _RATE * 2:
            return ""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            tmp = f.name
            _write_wav(tmp, audio_bytes)
        try:
            t0 = time.perf_counter()
            segments, _ = self._model.transcribe(
                tmp, language="en", beam_size=2, vad_filter=True
            )
            text = " ".join(s.text.strip() for s in segments).strip()
            logger.info("[T] STT %dms  audio=%.1fs", int((time.perf_counter() - t0) * 1000),
                        len(audio_bytes) / (_RATE * 2))
            return text
        finally:
            os.unlink(tmp)


def _write_wav(path: str, pcm: bytes) -> None:
    with wave.open(path, "wb") as wf:
        wf.setnchannels(_CHANNELS)
        wf.setsampwidth(2)
        wf.setframerate(_RATE)
        wf.writeframes(pcm)
