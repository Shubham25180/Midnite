# Skynet/core/component_registry.py
from __future__ import annotations

import logging
from collections import defaultdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from Skynet.core.runtime_state import RuntimeState

from Skynet.core.runtime_state import ComponentState

logger = logging.getLogger(__name__)


class ComponentRegistry:
    def __init__(self, state: RuntimeState) -> None:
        self._state = state
        self._deps: dict[str, list[str]] = {}
        self._reverse: dict[str, list[str]] = defaultdict(list)

    @property
    def components(self) -> set[str]:
        return set(self._deps.keys())

    def register(self, name: str, *, deps: list[str]) -> None:
        for dep in deps:
            if dep not in self._deps:
                raise ValueError(f"{name!r}: unknown dependency {dep!r}")
        self._deps[name] = deps
        for dep in deps:
            self._reverse[dep].append(name)

    def deps_of(self, name: str) -> list[str]:
        return self._deps.get(name, [])

    def start_order(self) -> list[str]:
        visited: set[str] = set()
        order: list[str] = []

        def visit(node: str) -> None:
            if node in visited:
                return
            visited.add(node)
            for dep in self._deps.get(node, []):
                visit(dep)
            order.append(node)

        for name in self._deps:
            visit(name)
        return order

    def cascade_failure(self, failed: str) -> None:
        for dependent in self._reverse.get(failed, []):
            current = self._state.get_component_state(dependent)
            if current not in (ComponentState.OFFLINE, ComponentState.FAILED):
                logger.warning("Cascading failure: %s → %s", failed, dependent)
                try:
                    self._state.set_component_state(
                        dependent, ComponentState.FAILED, source="cascade"
                    )
                    self.cascade_failure(dependent)
                except ValueError:
                    pass
