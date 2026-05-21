from pathlib import Path
import yaml

_CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "settings.yaml"

_REQUIRED_KEYS = ["stt", "llm1", "llm2", "tts", "memory"]


def load() -> dict:
    if not _CONFIG_PATH.exists():
        raise FileNotFoundError(f"settings.yaml not found at {_CONFIG_PATH}")

    with open(_CONFIG_PATH, "r") as f:
        cfg = yaml.safe_load(f)

    if cfg is None:
        raise ValueError("settings.yaml is empty")

    missing = [k for k in _REQUIRED_KEYS if k not in cfg]
    if missing:
        raise ValueError(f"settings.yaml missing required keys: {missing}")

    return cfg
