# Skynet/ui/routes/settings.py
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml
from fastapi import APIRouter, HTTPException

if TYPE_CHECKING:
    from Skynet.core.runtime_manager import RuntimeManager

_SETTINGS_PATH = Path("config/settings.yaml")
_PERSONA_PATH = Path("config/personas/nexux.yaml")


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"{path} not found")
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _save_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True)


def _deep_merge(base: dict, update: dict) -> dict:
    for k, v in update.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
    return base


def make_debug_router(manager: RuntimeManager | None) -> APIRouter:
    router = APIRouter(prefix="/api/debug", tags=["debug"])

    @router.get("/prompt")
    def get_prompt_debug() -> dict:
        if manager is None:
            return {"system": "", "history": [], "window": 0}
        orch = manager.get_component("orchestrator")
        if orch is None or not hasattr(orch, "preview_messages"):
            return {"system": "(orchestrator not running)", "history": [], "window": 0}
        return orch.preview_messages()

    return router


def make_mic_router(manager: RuntimeManager | None) -> APIRouter:
    router = APIRouter(prefix="/api/settings/mic", tags=["mic"])

    @router.get("/devices")
    def get_mic_devices() -> list:
        stt = manager.get_component("audio_device") if manager else None
        if stt is None or not hasattr(stt, "list_input_devices"):
            return []
        try:
            return stt.list_input_devices()
        except Exception:
            return []

    @router.get("")
    def get_mic() -> dict:
        cfg = _load_yaml(_SETTINGS_PATH)
        stt_cfg = cfg.get("stt", {})
        return {
            "mic_device": stt_cfg.get("mic_device", ""),
            "silence_db": stt_cfg.get("silence_db", 500),
        }

    @router.patch("")
    def patch_mic(data: dict) -> dict:
        cfg = _load_yaml(_SETTINGS_PATH)
        stt_cfg = cfg.setdefault("stt", {})
        result: dict = {}

        if "mic_device" in data:
            name = data["mic_device"] or ""
            stt_cfg["mic_device"] = name
            result["mic_device"] = name
            if manager is not None:
                stt = manager.get_component("audio_device")
                if stt is not None and hasattr(stt, "set_mic_device"):
                    stt.set_mic_device(name or None)
        else:
            result["mic_device"] = stt_cfg.get("mic_device", "")

        if "silence_db" in data:
            db = max(100, int(data["silence_db"]))
            stt_cfg["silence_db"] = db
            result["silence_db"] = db
            if manager is not None:
                stt = manager.get_component("audio_device")
                if stt is not None and hasattr(stt, "set_sensitivity"):
                    stt.set_sensitivity(db)
        else:
            result["silence_db"] = stt_cfg.get("silence_db", 500)

        _save_yaml(_SETTINGS_PATH, cfg)
        return result

    return router


def make_stt_router(manager: "RuntimeManager | None") -> APIRouter:
    router = APIRouter(prefix="/api/settings/stt", tags=["stt"])

    @router.get("")
    def get_stt() -> dict:
        cfg = _load_yaml(_SETTINGS_PATH)
        stt_cfg = cfg.get("stt", {})
        return {
            "mode": stt_cfg.get("mode", "continuous"),
            "enabled": stt_cfg.get("mode", "continuous") != "disabled",
        }

    @router.patch("")
    def patch_stt(data: dict) -> dict:
        cfg = _load_yaml(_SETTINGS_PATH)
        stt_cfg = cfg.setdefault("stt", {})
        mode = data.get("mode")
        if mode in ("continuous", "push_to_talk", "disabled"):
            stt_cfg["mode"] = mode
            _save_yaml(_SETTINGS_PATH, cfg)
            if manager is not None:
                stt = manager.get_component("audio_device")
                if stt is not None and hasattr(stt, "set_mode"):
                    stt.set_mode(mode)
        return {"mode": stt_cfg.get("mode", "continuous")}

    return router


def make_tools_router(manager: "RuntimeManager | None") -> APIRouter:
    router = APIRouter(prefix="/api/settings/tools", tags=["tools"])

    @router.get("")
    def get_tools() -> list:
        from Skynet.tools.definitions import TOOL_DEFINITIONS
        cfg = _load_yaml(_SETTINGS_PATH)
        disabled = set((cfg.get("tools") or {}).get("disabled") or [])
        return [
            {
                "name": t["function"]["name"],
                "description": t["function"]["description"][:72],
                "enabled": t["function"]["name"] not in disabled,
            }
            for t in TOOL_DEFINITIONS
        ]

    @router.patch("")
    def patch_tools(data: dict) -> dict:
        name = (data.get("name") or "").strip()
        enabled = data.get("enabled")
        if not name or enabled is None:
            raise HTTPException(status_code=400, detail="name and enabled required")
        cfg = _load_yaml(_SETTINGS_PATH)
        tools_cfg = cfg.setdefault("tools", {})
        disabled: set = set(tools_cfg.get("disabled") or [])
        if enabled:
            disabled.discard(name)
        else:
            disabled.add(name)
        tools_cfg["disabled"] = sorted(disabled)
        _save_yaml(_SETTINGS_PATH, cfg)
        return {"disabled": sorted(disabled)}

    return router


def make_llm2_router(manager: "RuntimeManager | None") -> APIRouter:
    router = APIRouter(prefix="/api/settings/llm2", tags=["llm2"])

    @router.get("")
    def get_llm2() -> dict:
        cfg = _load_yaml(_SETTINGS_PATH)
        llm = cfg.get("llm2", {})
        return {
            "backend": llm.get("backend", "ollama"),
            "model":   llm.get("model", ""),
            "enabled": llm.get("enabled", True),
        }

    @router.patch("")
    def patch_llm2(data: dict) -> dict:
        import logging as _logging
        _log = _logging.getLogger(__name__)
        cfg = _load_yaml(_SETTINGS_PATH)
        llm_cfg = cfg.setdefault("llm2", {})
        if "backend" in data:
            llm_cfg["backend"] = data["backend"]
        if "model" in data:
            llm_cfg["model"] = data["model"]
        if "enabled" in data:
            llm_cfg["enabled"] = bool(data["enabled"])
        _save_yaml(_SETTINGS_PATH, cfg)
        hot_reloaded = False
        if manager is not None:
            try:
                from Skynet.providers.registry import get_provider
                from Skynet.core.verifier import register_verifier_model
                if llm_cfg.get("enabled", True):
                    new_provider = get_provider("llm2", cfg)
                    register_verifier_model(new_provider)
                    # Also update orchestrator's memory_provider
                    orc = manager.get_component("orchestrator")
                    if orc is not None and hasattr(orc, "_memory_provider"):
                        orc._memory_provider = new_provider
                    hot_reloaded = True
                else:
                    register_verifier_model(None)
                    orc = manager.get_component("orchestrator")
                    if orc is not None and hasattr(orc, "_memory_provider"):
                        orc._memory_provider = None
                    hot_reloaded = True
            except Exception as exc:
                _log.warning("LLM2 hot-reload failed: %s", exc)
        return {
            "backend":     llm_cfg.get("backend", "ollama"),
            "model":       llm_cfg.get("model", ""),
            "enabled":     llm_cfg.get("enabled", True),
            "hot_reloaded": hot_reloaded,
        }

    return router


def make_router(manager: "RuntimeManager | None") -> APIRouter:
    router = APIRouter(prefix="/api/settings", tags=["settings"])

    # ── Raw settings.yaml ──────────────────────────────────────────────

    @router.get("")
    def get_settings() -> Any:
        return _load_yaml(_SETTINGS_PATH)

    @router.post("")
    def save_settings(data: dict) -> dict:
        _save_yaml(_SETTINGS_PATH, data)
        return {"status": "saved"}

    # ── Persona ────────────────────────────────────────────────────────

    @router.get("/persona")
    def get_persona() -> Any:
        return _load_yaml(_PERSONA_PATH)

    @router.patch("/persona")
    def patch_persona(data: dict) -> Any:
        current = _load_yaml(_PERSONA_PATH)
        merged = _deep_merge(current, data)
        _save_yaml(_PERSONA_PATH, merged)
        return merged

    # ── LLM ────────────────────────────────────────────────────────────

    @router.get("/llm")
    def get_llm() -> dict:
        cfg = _load_yaml(_SETTINGS_PATH)
        llm = cfg.get("llm1", {})
        return {
            "backend": llm.get("backend", "ollama"),
            "model": llm.get("model", ""),
            "enabled": llm.get("enabled", True),
        }

    @router.patch("/llm")
    def patch_llm(data: dict) -> dict:
        import logging
        _log = logging.getLogger(__name__)
        cfg = _load_yaml(_SETTINGS_PATH)
        llm_cfg = cfg.setdefault("llm1", {})
        if "backend" in data:
            llm_cfg["backend"] = data["backend"]
        if "model" in data:
            llm_cfg["model"] = data["model"]
        _save_yaml(_SETTINGS_PATH, cfg)
        hot_reloaded = False
        if manager is not None:
            try:
                from Skynet.providers.registry import get_provider
                new_provider = get_provider("llm1", cfg)
                orc = manager.get_component("orchestrator")
                if orc is not None and hasattr(orc, "set_provider"):
                    orc.set_provider(new_provider)
                    hot_reloaded = True
            except Exception as exc:
                _log.warning("LLM hot-reload failed: %s", exc)
        return {
            "backend": llm_cfg.get("backend", "ollama"),
            "model": llm_cfg.get("model", ""),
            "hot_reloaded": hot_reloaded,
        }

    # ── Voice ──────────────────────────────────────────────────────────

    @router.get("/voice")
    def get_voice() -> dict:
        cfg = _load_yaml(_SETTINGS_PATH)
        tts = cfg.get("tts", {})
        return {
            "speed": tts.get("speed", 1.0),
            "tts_batch": tts.get("tts_batch", 0),
            "backend": tts.get("backend", "f5tts"),
            "voice_id": tts.get("voice_id", "af_bella"),
        }

    @router.patch("/voice")
    def patch_voice(data: dict) -> dict:
        cfg = _load_yaml(_SETTINGS_PATH)
        tts_cfg = cfg.setdefault("tts", {})
        result: dict = {}

        if "speed" in data:
            speed = max(0.5, min(2.0, float(data["speed"])))
            tts_cfg["speed"] = speed
            result["speed"] = speed
            if manager is not None:
                tts = manager.get_component("tts")
                if tts is not None and hasattr(tts, "set_speed"):
                    tts.set_speed(speed)
        else:
            result["speed"] = tts_cfg.get("speed", 1.0)

        if "tts_batch" in data:
            batch = max(0, int(data["tts_batch"]))
            tts_cfg["tts_batch"] = batch
            result["tts_batch"] = batch
            if manager is not None:
                orc = manager.get_component("orchestrator")
                if orc is not None and hasattr(orc, "set_tts_batch"):
                    orc.set_tts_batch(batch)
        else:
            result["tts_batch"] = tts_cfg.get("tts_batch", 0)

        if "backend" in data:
            backend = str(data["backend"])
            voice_id = data.get("voice_id") or None
            tts_cfg["backend"] = backend
            if voice_id:
                tts_cfg["voice_id"] = voice_id
            result["backend"] = backend
            result["voice_id"] = voice_id or tts_cfg.get("voice_id", "af_bella")
            if manager is not None:
                tts = manager.get_component("tts")
                if tts is not None and hasattr(tts, "set_backend"):
                    tts.set_backend(backend, voice_id)
        elif "voice_id" in data:
            voice_id = str(data["voice_id"])
            tts_cfg["voice_id"] = voice_id
            result["voice_id"] = voice_id
            result["backend"] = tts_cfg.get("backend", "f5tts")
            if manager is not None:
                tts = manager.get_component("tts")
                if tts is not None and hasattr(tts, "set_voice"):
                    tts.set_voice(voice_id)
        else:
            result["backend"] = tts_cfg.get("backend", "f5tts")
            result["voice_id"] = tts_cfg.get("voice_id", "af_bella")

        _save_yaml(_SETTINGS_PATH, cfg)
        return result

    return router
