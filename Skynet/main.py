# Skynet/main.py
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import logging
import logging.handlers
import warnings
from pathlib import Path


def _setup_logging() -> None:
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)

    fmt_console = logging.Formatter("%(levelname)s %(name)s — %(message)s")
    fmt_file = logging.Formatter("%(asctime)s %(levelname)s %(name)s — %(message)s")

    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(fmt_console)

    file_handler = logging.handlers.RotatingFileHandler(
        logs_dir / "nexux.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(fmt_file)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(console)
    root.addHandler(file_handler)

    # Suppress noisy third-party loggers on console (still go to file at DEBUG)
    for name in ("faster_whisper", "phonemizer", "urllib3", "httpx", "httpcore",
                  "transformers", "torch", "qdrant_client", "fastembed"):
        logging.getLogger(name).setLevel(logging.WARNING)


_setup_logging()
logger = logging.getLogger(__name__)

warnings.filterwarnings("ignore", message="Couldn't find ffmpeg", category=RuntimeWarning)
warnings.filterwarnings("ignore", message="`huggingface_hub` cache-system uses symlinks", category=UserWarning)

from Skynet.core import config as cfg_mod
from Skynet.core.runtime_manager import RuntimeManager
from Skynet.core.orchestrator import Orchestrator
from Skynet.voice.stt import STTComponent
from Skynet.voice.tts import TTSComponent
from Skynet.providers.registry import get_provider
from Skynet.ui.server import start_server


def _setup_cuda_dlls() -> None:
    """Add NVIDIA DLL directories to PATH — borrowed from Dictate project."""
    import os
    import site
    try:
        for p in site.getsitepackages():
            for subdir in ("nvidia/cudnn/bin", "nvidia/cublas/bin", "nvidia/cuda_runtime/bin"):
                full = os.path.join(p, subdir.replace("/", os.sep))
                if os.path.exists(full):
                    os.add_dll_directory(full)
                    os.environ["PATH"] = full + os.pathsep + os.environ["PATH"]
    except Exception:
        pass


def _setup_ffmpeg() -> None:
    """Create ffmpeg.exe shim so subprocess("ffmpeg") works on Windows.

    imageio_ffmpeg bundles ffmpeg as 'ffmpeg-win-x86_64-vX.Y.exe'.
    subprocess.Popen with shell=False only finds '.exe' by exact name,
    so we copy the binary once to a temp dir as 'ffmpeg.exe'.
    """
    import os
    import shutil
    import tempfile
    from pathlib import Path
    try:
        import imageio_ffmpeg
        src = imageio_ffmpeg.get_ffmpeg_exe()
        shim_dir = Path(tempfile.gettempdir()) / "nexux_ffmpeg"
        shim_dir.mkdir(exist_ok=True)
        shim = shim_dir / "ffmpeg.exe"
        if not shim.exists():
            shutil.copy2(src, shim)
        os.environ["PATH"] = str(shim_dir) + os.pathsep + os.environ.get("PATH", "")
    except Exception:
        pass


def main() -> None:
    import os
    _setup_cuda_dlls()
    _setup_ffmpeg()
    cfg = cfg_mod.load()
    # Pre-resolve transformers.pipeline in the main thread to prevent a race condition:
    # faster_whisper (STT thread) partially initializes the transformers package, and
    # f5_tts (TTS thread) then fails to find `pipeline` in the partial module.
    from transformers import pipeline as _  # noqa: F401
    manager = RuntimeManager()
    stt_cfg = cfg["stt"]
    stt = STTComponent(
        bus=manager.bus,
        model_name=stt_cfg["model"],
        device=stt_cfg.get("device", "cpu"),
        compute_type=stt_cfg.get("compute_type", "int8"),
        mic_device=stt_cfg.get("mic_device") or None,
        silence_db=stt_cfg.get("silence_db", 500),
        mode=stt_cfg.get("mode", "continuous"),
    )
    tts_cfg = cfg["tts"]
    tts = TTSComponent(
        bus=manager.bus,
        backend=tts_cfg.get("backend", "f5tts"),
        ref_audio=tts_cfg.get("ref_audio", ""),
        ref_text=tts_cfg.get("ref_text", ""),
        speed=tts_cfg.get("speed", 1.0),
        voice_id=tts_cfg.get("voice_id", "af_bella"),
    )
    provider = get_provider("llm1", cfg)

    # LLM2 for memory compression — optional, falls back to LLM1 if not configured
    mem_cfg = cfg.get("memory", {})
    memory_provider = None
    if mem_cfg.get("enabled") and cfg.get("llm2", {}).get("enabled"):
        try:
            memory_provider = get_provider("llm2", cfg)
            logger.info("Memory LLM2 provider ready")
        except Exception as e:
            logger.warning("LLM2 not available, using LLM1 for memory: %s", e)

    # Wire LLM2 as cheap supervisory model (verifier + compressor)
    from Skynet.core.verifier import register_verifier_model
    register_verifier_model(memory_provider)  # None if LLM2 not configured → heuristic fallback

    orc = Orchestrator(
        bus=manager.bus,
        provider=provider,
        memory_provider=memory_provider,
        tts_batch=cfg["tts"].get("tts_batch", 0),
        compress_at=mem_cfg.get("compress_at", 20),
    )
    manager.register("audio_device", stt, deps=[])
    manager.register("tts", tts, deps=["audio_device"])
    manager.register("orchestrator", orc, deps=[])

    # Wire tool executor to live runtime so get_system_info / reload_skills work
    from Skynet.tools.executor import register as register_tools
    register_tools(orc._router, manager)

    start_server(manager, host="127.0.0.1", port=7799)


if __name__ == "__main__":
    main()
