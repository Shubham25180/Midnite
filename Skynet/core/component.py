# Skynet/core/component.py
from __future__ import annotations

from abc import ABC, abstractmethod

from Skynet.core.runtime_state import ComponentState


class Component(ABC):
    def __init__(self, *, name: str) -> None:
        self.name = name

    @abstractmethod
    async def start(self) -> None: ...

    @abstractmethod
    async def stop(self) -> None: ...

    @abstractmethod
    def health(self) -> ComponentState: ...
