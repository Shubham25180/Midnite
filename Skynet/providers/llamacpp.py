from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterator

from .base import LLMProvider

logger = logging.getLogger(__name__)


def _download_model(repo_id: str, filename: str) -> str:
    """Download a GGUF from HuggingFace on first run, return local path."""
    from huggingface_hub import hf_hub_download
    logger.info("LLM downloading %s/%s — first run only", repo_id, filename)
    path = hf_hub_download(repo_id=repo_id, filename=filename)
    logger.info("LLM model cached at %s", path)
    return path


class LlamaCppProvider(LLMProvider):
    """
    Direct llama.cpp inference — no Ollama, no separate process.
    Model loads into VRAM once and stays there; all context control is ours.
    """

    def __init__(
        self,
        model_path: str | None = None,
        repo_id: str | None = None,
        filename: str | None = None,
        n_gpu_layers: int = -1,   # -1 = all layers on GPU
        n_ctx: int = 8192,
        verbose: bool = False,
    ) -> None:
        if not model_path and not (repo_id and filename):
            raise ValueError("Provide model_path OR (repo_id + filename)")
        self._model_path = model_path
        self._repo_id = repo_id
        self._filename = filename
        self._n_gpu_layers = n_gpu_layers
        self._n_ctx = n_ctx
        self._verbose = verbose
        self._llm = None  # lazy-loaded

    def _ensure_loaded(self) -> None:
        if self._llm is not None:
            return
        from llama_cpp import Llama
        path = self._model_path or _download_model(self._repo_id, self._filename)
        logger.info("LLM loading %s (%d gpu layers, ctx=%d)", path, self._n_gpu_layers, self._n_ctx)
        self._llm = Llama(
            model_path=str(path),
            n_gpu_layers=self._n_gpu_layers,
            n_ctx=self._n_ctx,
            verbose=self._verbose,
        )
        logger.info("LLM ready")

    def complete(self, messages: list[dict]) -> str:
        self._ensure_loaded()
        result = self._llm.create_chat_completion(messages=messages, stream=False)
        return result["choices"][0]["message"]["content"]

    def stream(self, messages: list[dict]) -> Iterator[str]:
        self._ensure_loaded()
        for chunk in self._llm.create_chat_completion(messages=messages, stream=True):
            delta = chunk["choices"][0]["delta"]
            content = delta.get("content")
            if content:
                yield content
