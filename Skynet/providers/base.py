from abc import ABC, abstractmethod
from typing import Iterator


class LLMProvider(ABC):
    @abstractmethod
    def complete(self, messages: list[dict]) -> str:
        """Send messages, return full response string."""
        ...

    @abstractmethod
    def stream(self, messages: list[dict]) -> Iterator[str]:
        """Send messages, yield response chunks as they arrive."""
        ...

    def complete_with_tools(
        self, messages: list[dict], tools: list[dict]
    ) -> tuple[str, list[dict]]:
        """Send messages with tool schemas. Returns (text, tool_calls).

        tool_calls is a list of {"name": str, "arguments": dict}.
        text is empty when tool_calls is non-empty and vice versa.
        Override in providers that support function calling.
        """
        raise NotImplementedError(f"{type(self).__name__} does not support tool calling")
