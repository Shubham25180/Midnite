# Skynet/ui/routes/models.py
from __future__ import annotations

import requests
from fastapi import APIRouter

router = APIRouter(prefix="/api/models", tags=["models"])


@router.get("")
def list_ollama_models():
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=3)
        if r.status_code == 200:
            data = r.json()
            return {"models": [m["name"] for m in data.get("models", [])]}
    except Exception:
        pass
    return {"models": []}
