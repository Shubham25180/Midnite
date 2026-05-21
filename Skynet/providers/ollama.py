import json
from typing import Iterator
import requests
from .base import LLMProvider


_DEFAULT_CTX = 16384  # 16k — fits comfortably on 16 GB VRAM with 14b Q4_KM weights


class OllamaProvider(LLMProvider):
    def __init__(self, model: str, base_url: str = "http://localhost:11434",
                 num_ctx: int = _DEFAULT_CTX):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.num_ctx = num_ctx

    def complete(self, messages: list[dict]) -> str:
        response = requests.post(
            f"{self.base_url}/api/chat",
            json={
                "model": self.model,
                "messages": messages,
                "stream": False,
                "options": {"num_ctx": self.num_ctx},
            },
            timeout=120,
        )
        response.raise_for_status()
        return response.json()["message"]["content"]

    def complete_with_tools(
        self, messages: list[dict], tools: list[dict]
    ) -> tuple[str, list[dict]]:
        response = requests.post(
            f"{self.base_url}/api/chat",
            json={
                "model": self.model,
                "messages": messages,
                "tools": tools,
                "stream": False,
                "options": {"num_ctx": self.num_ctx},
            },
            timeout=120,
        )
        response.raise_for_status()
        msg = response.json().get("message", {})
        text = msg.get("content", "") or ""
        raw_calls = msg.get("tool_calls") or []
        tool_calls = [
            {
                "name": tc.get("function", {}).get("name", ""),
                "arguments": tc.get("function", {}).get("arguments", {}),
            }
            for tc in raw_calls
        ]
        return text.strip(), tool_calls

    def stream(self, messages: list[dict]) -> Iterator[str]:
        resp = requests.post(
            f"{self.base_url}/api/chat",
            json={
                "model": self.model,
                "messages": messages,
                "stream": True,
                "options": {"num_ctx": self.num_ctx},
            },
            stream=True,
            timeout=120,
        )
        resp.raise_for_status()
        for line in resp.iter_lines():
            if line:
                chunk = json.loads(line)
                if content := chunk.get("message", {}).get("content"):
                    yield content
                if chunk.get("done"):
                    break
