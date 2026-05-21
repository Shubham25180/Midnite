# Skynet/ui/routes/voices.py
from __future__ import annotations

import json
import re
import subprocess
import tempfile
import wave
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import yaml
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

if TYPE_CHECKING:
    from Skynet.core.runtime_manager import RuntimeManager

_SETTINGS_PATH = Path("config/settings.yaml")
_LIBRARY_PATH  = Path("config/voice_library.json")
_VOICES_DIR    = Path("config/voices")
_KOKORO_DIR    = Path("config/voices/kokoro")
_SAFE_RE       = re.compile(r"[^\w\-]")

KOKORO_VOICES = [
    {"id": "af_bella",    "name": "Bella",    "gender": "F", "accent": "American", "style": "Warm & Breathy"},
    {"id": "af_sky",      "name": "Sky",      "gender": "F", "accent": "American", "style": "Bright & Energetic"},
    {"id": "af_sarah",    "name": "Sarah",    "gender": "F", "accent": "American", "style": "Clear & Professional"},
    {"id": "af_nicole",   "name": "Nicole",   "gender": "F", "accent": "American", "style": "Calm & Smooth"},
    {"id": "af_heart",    "name": "Heart",    "gender": "F", "accent": "American", "style": "Sweet & Gentle"},
    {"id": "am_adam",     "name": "Adam",     "gender": "M", "accent": "American", "style": "Deep & Resonant"},
    {"id": "am_michael",  "name": "Michael",  "gender": "M", "accent": "American", "style": "Authoritative"},
    {"id": "bf_emma",     "name": "Emma",     "gender": "F", "accent": "British",  "style": "Crisp & Refined"},
    {"id": "bf_isabella", "name": "Isabella", "gender": "F", "accent": "British",  "style": "Warm & Cultured"},
    {"id": "bm_george",   "name": "George",   "gender": "M", "accent": "British",  "style": "Distinguished"},
    {"id": "bm_lewis",    "name": "Lewis",    "gender": "M", "accent": "British",  "style": "Casual & Clear"},
]

_KOKORO_IDS = {v["id"] for v in KOKORO_VOICES}


# ── Helpers ────────────────────────────────────────────────────────────────

def _load_library() -> dict:
    if not _LIBRARY_PATH.exists():
        return {"voices": []}
    with open(_LIBRARY_PATH, encoding="utf-8") as f:
        return json.load(f)


def _save_library(data: dict) -> None:
    _LIBRARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_LIBRARY_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _load_settings() -> dict:
    if not _SETTINGS_PATH.exists():
        return {}
    with open(_SETTINGS_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _save_settings(data: dict) -> None:
    with open(_SETTINGS_PATH, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True)


def _safe_name(raw: str) -> str:
    cleaned = _SAFE_RE.sub("_", raw.strip().lower())[:40]
    return cleaned or "voice"


_REF_MAX_SEC = 12


def _convert_to_wav(src: Path, dst: Path, max_sec: int = _REF_MAX_SEC) -> None:
    cmd = ["ffmpeg", "-y", "-i", str(src)]
    if max_sec:
        cmd += ["-t", str(max_sec)]
    cmd += ["-ar", "24000", "-ac", "1", str(dst)]
    subprocess.run(cmd, check=True, capture_output=True)


def _get_wav_duration(wav: Path) -> float:
    try:
        with wave.open(str(wav), "rb") as wf:
            return round(wf.getnframes() / wf.getframerate(), 1)
    except Exception:
        return 0.0


def _transcribe_wav(manager: RuntimeManager | None, wav_path: str) -> str:
    if manager is None:
        return ""
    stt = manager.get_component("audio_device")
    if stt is None or not hasattr(stt, "transcribe_file"):
        return ""
    try:
        return stt.transcribe_file(wav_path)
    except Exception:
        return ""


# ── Router ─────────────────────────────────────────────────────────────────

def make_voice_router(manager: RuntimeManager | None) -> APIRouter:
    router = APIRouter(prefix="/api/voices", tags=["voices"])

    # ── F5-TTS custom voice library ────────────────────────────────────────

    @router.get("")
    def list_voices() -> dict:
        lib = _load_library()
        cfg = _load_settings()
        active = cfg.get("tts", {}).get("ref_audio", "").replace("\\", "/")
        voices = lib.get("voices", [])

        in_lib = any(v["file"].replace("\\", "/") == active for v in voices)
        active_extra = None
        if active and not in_lib and Path(active).exists():
            active_extra = {
                "name": Path(active).stem,
                "file": active,
                "ref_text": cfg.get("tts", {}).get("ref_text", ""),
                "duration": _get_wav_duration(Path(active)),
                "builtin": True,
            }

        return {"voices": voices, "active": active, "active_extra": active_extra}

    @router.post("/upload")
    async def upload_voice(
        file: UploadFile = File(...),
        name: str = Form(""),
    ) -> dict:
        voice_name = _safe_name(name or Path(file.filename or "voice").stem)
        _VOICES_DIR.mkdir(parents=True, exist_ok=True)

        suffix = Path(file.filename or "audio.bin").suffix or ".bin"
        tmp_path = Path(tempfile.mktemp(suffix=suffix))
        wav_path = _VOICES_DIR / f"{voice_name}.wav"
        try:
            tmp_path.write_bytes(await file.read())
            try:
                _convert_to_wav(tmp_path, wav_path)
            except (subprocess.CalledProcessError, FileNotFoundError) as exc:
                detail = getattr(exc, "stderr", b"").decode(errors="replace") or str(exc)
                raise HTTPException(status_code=422, detail=f"Audio conversion failed: {detail}")
        finally:
            tmp_path.unlink(missing_ok=True)

        ref_text = _transcribe_wav(manager, str(wav_path))
        entry = {
            "name": voice_name,
            "file": str(wav_path).replace("\\", "/"),
            "ref_text": ref_text,
            "duration": _get_wav_duration(wav_path),
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }

        lib = _load_library()
        lib["voices"] = [v for v in lib.get("voices", []) if v["name"] != voice_name]
        lib["voices"].append(entry)
        _save_library(lib)
        return entry

    @router.delete("/{name}")
    def delete_voice(name: str) -> dict:
        lib = _load_library()
        entry = next((v for v in lib.get("voices", []) if v["name"] == name), None)
        if entry is None:
            raise HTTPException(status_code=404, detail="Voice not found")
        wav = Path(entry["file"])
        if wav.exists() and wav.parent.resolve() == _VOICES_DIR.resolve():
            wav.unlink(missing_ok=True)
        lib["voices"] = [v for v in lib["voices"] if v["name"] != name]
        _save_library(lib)
        return {"deleted": name, "count": len(lib["voices"])}

    @router.post("/{name}/activate")
    def activate_voice(name: str) -> dict:
        lib = _load_library()
        entry = next((v for v in lib.get("voices", []) if v["name"] == name), None)
        if entry is None:
            raise HTTPException(status_code=404, detail="Voice not found")

        cfg = _load_settings()
        tts_cfg = cfg.setdefault("tts", {})
        tts_cfg["backend"] = "f5tts"
        tts_cfg["ref_audio"] = entry["file"]
        tts_cfg["ref_text"] = entry["ref_text"]
        _save_settings(cfg)

        if manager is not None:
            tts = manager.get_component("tts")
            if tts is not None:
                if hasattr(tts, "set_backend"):
                    tts.set_backend("f5tts")
                if hasattr(tts, "set_ref_audio"):
                    tts.set_ref_audio(entry["file"], entry["ref_text"])

        return {"active": entry["file"], "ref_text": entry["ref_text"], "backend": "f5tts"}

    # ── Kokoro voices ──────────────────────────────────────────────────────

    @router.get("/kokoro")
    def list_kokoro_voices() -> dict:
        cfg = _load_settings()
        tts_cfg = cfg.get("tts", {})
        active_id = tts_cfg.get("voice_id", "") if tts_cfg.get("backend") == "kokoro" else ""
        _KOKORO_DIR.mkdir(parents=True, exist_ok=True)
        voices = [
            {**v, "downloaded": (_KOKORO_DIR / "voices" / f"{v['id']}.pt").exists()}
            for v in KOKORO_VOICES
        ]
        return {"voices": voices, "active": active_id}

    @router.post("/kokoro/{voice_id}/activate")
    def activate_kokoro_voice(voice_id: str) -> dict:
        if voice_id not in _KOKORO_IDS:
            raise HTTPException(status_code=404, detail=f"Unknown Kokoro voice: {voice_id}")

        cfg = _load_settings()
        tts_cfg = cfg.setdefault("tts", {})
        tts_cfg["backend"] = "kokoro"
        tts_cfg["voice_id"] = voice_id
        _save_settings(cfg)

        if manager is not None:
            tts = manager.get_component("tts")
            if tts is not None and hasattr(tts, "set_backend"):
                tts.set_backend("kokoro", voice_id)

        return {"active": voice_id, "backend": "kokoro"}

    @router.post("/kokoro/{voice_id}/download")
    def download_kokoro_voice(voice_id: str) -> dict:
        if voice_id not in _KOKORO_IDS:
            raise HTTPException(status_code=404, detail=f"Unknown Kokoro voice: {voice_id}")
        _KOKORO_DIR.mkdir(parents=True, exist_ok=True)
        try:
            from huggingface_hub import hf_hub_download
            path = hf_hub_download(
                repo_id="hexgrad/Kokoro-82M",
                filename=f"voices/{voice_id}.pt",
                local_dir=str(_KOKORO_DIR),
            )
            return {"downloaded": voice_id, "path": str(path)}
        except ImportError:
            raise HTTPException(status_code=500, detail="huggingface_hub not installed — pip install huggingface_hub")
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Download failed: {exc}") from exc

    @router.post("/kokoro/download-all")
    def download_all_kokoro_voices() -> dict:
        _KOKORO_DIR.mkdir(parents=True, exist_ok=True)
        try:
            from huggingface_hub import hf_hub_download
        except ImportError:
            raise HTTPException(status_code=500, detail="huggingface_hub not installed — pip install huggingface_hub")
        downloaded, failed = [], []
        for v in KOKORO_VOICES:
            try:
                hf_hub_download(
                    repo_id="hexgrad/Kokoro-82M",
                    filename=f"voices/{v['id']}.pt",
                    local_dir=str(_KOKORO_DIR),
                )
                downloaded.append(v["id"])
            except Exception as exc:
                failed.append({"id": v["id"], "error": str(exc)})
        return {"downloaded": downloaded, "failed": failed, "total": len(KOKORO_VOICES)}

    return router
