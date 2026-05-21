import pytest
from fastapi.testclient import TestClient
from Skynet.core.runtime_manager import RuntimeManager
from Skynet.ui.server import build_app


@pytest.fixture
def client(tmp_path):
    import yaml
    settings_file = tmp_path / "settings.yaml"
    settings_file.write_text(yaml.dump({
        "stt": {"backend": "whisper", "model": "base", "enabled": True},
        "llm1": {"backend": "ollama", "model": "llama3.2", "enabled": True},
        "llm2": {"backend": None, "enabled": False},
        "tts": {"backend": "pyttsx3", "enabled": True},
        "memory": {"enabled": False},
    }))
    manager = RuntimeManager()
    app = build_app(manager)
    return TestClient(app), str(settings_file)


def test_get_status(client):
    c, _ = client
    r = c.get("/api/status")
    assert r.status_code == 200
    data = r.json()
    assert "runtime_mode" in data
    assert "components" in data


def test_get_hardware(client):
    c, _ = client
    r = c.get("/api/hardware")
    assert r.status_code == 200
    data = r.json()
    assert "cpu_percent" in data
    assert "ram_used_gb" in data
    assert "ram_total_gb" in data
    assert "gpu_percent" in data   # None if no GPU driver
    assert "vram_used_gb" in data


def test_get_component_status(client):
    c, _ = client
    r = c.get("/api/component-status")
    assert r.status_code == 200
    data = r.json()
    assert "ollama" in data
    assert data["ollama"] in ("reachable", "unreachable")


def test_list_ollama_models(client):
    c, _ = client
    r = c.get("/api/models")
    assert r.status_code == 200
    data = r.json()
    assert "models" in data
    assert isinstance(data["models"], list)


def test_save_and_get_settings(client, tmp_path, monkeypatch):
    c, _ = client
    # Point settings route to tmp_path so we don't clobber real config
    import Skynet.ui.routes.settings as settings_mod
    monkeypatch.setattr(settings_mod, "_SETTINGS_PATH", tmp_path / "settings.yaml")

    payload = {"foo": "bar", "nested": {"x": 1}}
    r = c.post("/api/settings", json=payload)
    assert r.status_code == 200
    assert r.json() == {"status": "saved"}

    r2 = c.get("/api/settings")
    assert r2.status_code == 200
    assert r2.json() == payload
