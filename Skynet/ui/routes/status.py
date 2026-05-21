# Skynet/ui/routes/status.py
from __future__ import annotations

import requests
from fastapi import APIRouter

router = APIRouter(prefix="/api/component-status", tags=["status"])


@router.get("")
def get_component_status():
    ollama_ok = False
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=2)
        ollama_ok = r.status_code == 200
    except Exception:
        pass

    return {
        "ollama": "reachable" if ollama_ok else "unreachable",
    }
