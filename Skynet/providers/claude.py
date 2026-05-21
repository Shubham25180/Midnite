import os
from typing import Iterator
import anthropic
from .base import LLMProvider


class ClaudeProvider(LLMProvider):
    def __init__(self, model: str):
        self.model = model
        self._client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    def complete(self, messages: list[dict]) -> str:
        system, msgs = _split_system(messages)
        kwargs = {"model": self.model, "max_tokens": 2048, "messages": msgs}
        if system:
            kwargs["system"] = system
        response = self._client.messages.create(**kwargs)
        return response.content[0].text

    def complete_with_tools(
        self, messages: list[dict], tools: list[dict]
    ) -> tuple[str, list[dict]]:
        """Native Anthropic tool calling — always structured, never text fallback."""
        system, msgs = _split_system(messages)
        anthropic_tools = _to_anthropic_tools(tools)
        anthropic_msgs = _to_anthropic_messages(msgs)

        kwargs: dict = {
            "model": self.model,
            "max_tokens": 4096,
            "tools": anthropic_tools,
            "messages": anthropic_msgs,
        }
        if system:
            kwargs["system"] = system

        response = self._client.messages.create(**kwargs)

        text = ""
        tool_calls: list[dict] = []
        for block in response.content:
            if hasattr(block, "text"):
                text += block.text
            elif block.type == "tool_use":
                tool_calls.append({
                    "name": block.name,
                    "arguments": block.input,
                    "_tool_use_id": block.id,   # required for tool_result pairing
                })

        return text.strip(), tool_calls

    def stream(self, messages: list[dict]) -> Iterator[str]:
        system, msgs = _split_system(messages)
        kwargs = {"model": self.model, "max_tokens": 2048, "messages": msgs}
        if system:
            kwargs["system"] = system
        with self._client.messages.stream(**kwargs) as stream:
            for text in stream.text_stream:
                yield text


# ── Conversion helpers ────────────────────────────────────────────────────────

def _split_system(messages: list[dict]) -> tuple[str, list[dict]]:
    """Pull the first system message out; Anthropic takes it separately."""
    if messages and messages[0]["role"] == "system":
        return messages[0]["content"], messages[1:]
    return "", messages


def _to_anthropic_tools(tools: list[dict]) -> list[dict]:
    """Convert OpenAI-style tool definitions to Anthropic format."""
    result = []
    for t in tools:
        fn = t.get("function", t)
        result.append({
            "name": fn["name"],
            "description": fn.get("description", ""),
            "input_schema": fn.get("parameters", {"type": "object", "properties": {}}),
        })
    return result


def _to_anthropic_messages(messages: list[dict]) -> list[dict]:
    """
    Convert OpenAI/Ollama-style messages to Anthropic format.
    Handles tool call/result pairs in multi-turn history.
    """
    result: list[dict] = []
    for msg in messages:
        role = msg.get("role", "user")

        # Ollama-style tool result → Anthropic tool_result in user message
        if role == "tool":
            tool_use_id = msg.get("tool_use_id", "unknown")
            result.append({
                "role": "user",
                "content": [{"type": "tool_result", "tool_use_id": tool_use_id, "content": str(msg["content"])}],
            })

        # Assistant message with tool_calls (Ollama format) → Anthropic tool_use blocks
        elif role == "assistant" and msg.get("tool_calls"):
            content: list[dict] = []
            if msg.get("content"):
                content.append({"type": "text", "text": msg["content"]})
            for tc in msg["tool_calls"]:
                fn = tc.get("function", tc)
                content.append({
                    "type": "tool_use",
                    "id": tc.get("_tool_use_id", f"call_{fn.get('name', 'unknown')}"),
                    "name": fn.get("name", ""),
                    "input": fn.get("arguments", {}),
                })
            result.append({"role": "assistant", "content": content})

        else:
            result.append({"role": role, "content": msg.get("content", "")})

    return result
