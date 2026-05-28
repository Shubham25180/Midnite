from __future__ import annotations

import atexit
import json
import logging
import threading
import warnings
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _atexit_close() -> None:
    """Cleanly close the Qdrant client at interpreter exit to suppress __del__ ImportError."""
    global _client
    if _client is not None:
        try:
            _client.close()
        except Exception:
            pass
        _client = None


atexit.register(_atexit_close)

_DB_PATH = Path("data/qdrant")
_IDENTITY_PATH = Path("data/identity.json")
_COLLECTION = "nexux_memory"
# fastembed internal name for BAAI/bge-small-en-v1.5 (33MB, 384-dim, CPU-fast)
_EMBED_MODEL = "BAAI/bge-small-en-v1.5"
_VECTOR_NAME = "fast-bge-small-en"
_VECTOR_SIZE = 384
_MIN_SCORE = 0.35
_TOP_K = 5

_client: Any = None
_lock = threading.Lock()
_identity_lock = threading.Lock()


def _get_client() -> Any:
    global _client
    with _lock:
        if _client is None:
            from qdrant_client import QdrantClient
            _DB_PATH.mkdir(parents=True, exist_ok=True)
            _client = QdrantClient(path=str(_DB_PATH))
            _ensure_collection(_client)
    return _client


def _ensure_collection(client: Any) -> None:
    from qdrant_client.models import Distance, VectorParams
    names = {c.name for c in client.get_collections().collections}
    if _COLLECTION in names:
        # Verify the vector config is compatible; recreate if not
        info = client.get_collection(_COLLECTION)
        cfg = info.config.params.vectors
        existing_names = set(cfg.keys()) if isinstance(cfg, dict) else {""}
        if _VECTOR_NAME not in existing_names:
            logger.warning(
                "Qdrant collection '%s' has incompatible schema — recreating", _COLLECTION
            )
            client.delete_collection(_COLLECTION)
            names.discard(_COLLECTION)

    if _COLLECTION not in names:
        client.create_collection(
            collection_name=_COLLECTION,
            vectors_config={_VECTOR_NAME: VectorParams(size=_VECTOR_SIZE, distance=Distance.COSINE)},
        )
        logger.info("Qdrant collection '%s' created", _COLLECTION)
    else:
        count = client.count(collection_name=_COLLECTION).count
        logger.info("Qdrant collection '%s' ready (%d entries)", _COLLECTION, count)


def _update_identity_json(text: str) -> None:
    """Append a core fact to data/identity.json (deduplicated by text)."""
    with _identity_lock:
        try:
            _IDENTITY_PATH.parent.mkdir(parents=True, exist_ok=True)
            if _IDENTITY_PATH.exists():
                data = json.loads(_IDENTITY_PATH.read_text(encoding="utf-8"))
            else:
                data = {"version": 1, "facts": []}
            existing = {f["text"].lower().strip() for f in data.get("facts", [])}
            if text.lower().strip() not in existing:
                data.setdefault("facts", []).append(
                    {"text": text.strip(), "ts": datetime.now().isoformat()}
                )
                _IDENTITY_PATH.write_text(
                    json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
                )
                logger.info("Identity JSON updated (%d facts): %s", len(data["facts"]), text[:80])
        except Exception:
            logger.exception("Failed to update identity.json")


def load_identity() -> list[str]:
    """Return pinned core facts from data/identity.json — Layer 1 of cognitive state."""
    try:
        if not _IDENTITY_PATH.exists():
            return []
        data = json.loads(_IDENTITY_PATH.read_text(encoding="utf-8"))
        return [f["text"] for f in data.get("facts", []) if isinstance(f.get("text"), str)]
    except Exception:
        logger.debug("Failed to load identity.json")
        return []


def store(text: str, entry_type: str = "summary", extra: dict | None = None) -> None:
    """Embed and persist one memory entry."""
    if not text.strip():
        return
    if entry_type == "core":
        _update_identity_json(text)
    from qdrant_client.models import PointStruct
    import uuid
    now = datetime.now()
    metadata = {
        "type": entry_type,
        "ts": now.isoformat(),
        "hour_of_day": now.hour,
        "day_of_week": now.strftime("%A"),
        "text": text,
        **(extra or {}),
    }
    try:
        client = _get_client()
        # Use fastembed via models.Document (new API, no deprecation warning)
        from qdrant_client import models as qm
        client.upsert(
            collection_name=_COLLECTION,
            points=[
                qm.PointStruct(
                    id=str(uuid.uuid4()),
                    vector={_VECTOR_NAME: qm.Document(text=text, model=_EMBED_MODEL)},
                    payload=metadata,
                )
            ],
        )
        logger.debug("Qdrant stored (%s): %d chars", entry_type, len(text))
    except RuntimeError as e:
        if "cannot schedule new futures" in str(e) or "interpreter shutdown" in str(e):
            logger.warning("Qdrant store skipped — interpreter shutting down")
        else:
            logger.exception("Qdrant store failed")
    except Exception:
        logger.exception("Qdrant store failed")


def search(query: str, top_k: int = _TOP_K, entry_type: str | None = None) -> list[dict]:
    """Return semantically similar memories, best first."""
    try:
        client = _get_client()
        if client.count(collection_name=_COLLECTION).count == 0:
            return []
        from qdrant_client import models as qm
        flt = None
        if entry_type:
            flt = qm.Filter(
                must=[qm.FieldCondition(key="type", match=qm.MatchValue(value=entry_type))]
            )
        results = client.query_points(
            collection_name=_COLLECTION,
            query=qm.Document(text=query, model=_EMBED_MODEL),
            using=_VECTOR_NAME,
            limit=top_k,
            query_filter=flt,
        )
        return [
            {"text": r.payload.get("text", ""), "score": r.score, "meta": r.payload}
            for r in results.points
            if r.score >= _MIN_SCORE
        ]
    except Exception:
        logger.exception("Qdrant search failed")
        return []


def build_relevant_context(query: str, top_k: int = 3) -> str:
    """
    Retrieve semantically relevant past memories.
    Returns injection-ready string or '' if nothing found.
    """
    hits = search(query, top_k=top_k)
    if not hits:
        return ""
    lines = [f"- {h['meta'].get('text', h.get('text', ''))}" for h in hits]
    return "Relevant memory:\n" + "\n".join(lines)


def count() -> int:
    try:
        return _get_client().count(collection_name=_COLLECTION).count
    except Exception:
        return 0
