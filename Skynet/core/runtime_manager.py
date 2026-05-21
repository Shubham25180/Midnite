# Skynet/core/runtime_manager.py
from __future__ import annotations

import logging

from Skynet.core.component import Component
from Skynet.core.component_registry import ComponentRegistry
from Skynet.core.event_bus import EventBus
from Skynet.core.runtime_state import RuntimeMode, ComponentState, RuntimeState
from Skynet.core.tasks import BackgroundRunner

logger = logging.getLogger(__name__)


class RuntimeManager:
    def __init__(self) -> None:
        self.bus = EventBus()
        self.state = RuntimeState(self.bus)
        self.registry = ComponentRegistry(self.state)
        self.runner = BackgroundRunner()
        self._components: dict[str, Component] = {}

    def register(self, name: str, component: Component, *, deps: list[str]) -> None:
        self.registry.register(name, deps=deps)
        self._components[name] = component

    def get_component(self, name: str) -> Component | None:
        return self._components.get(name)

    async def initialize(self) -> None:
        self.state.set_runtime_mode(RuntimeMode.INITIALIZING, source="RuntimeManager.initialize")
        await self.runner.start()
        for name in self.registry.start_order():
            comp = self._components[name]
            # Fix 1: Skip components already marked FAILED by cascade_failure
            if self.state.get_component_state(name) == ComponentState.FAILED:
                continue
            self.state.set_component_state(name, ComponentState.STARTING, source="RuntimeManager")
            try:
                await comp.start()
                current_health = comp.health()
                self.state.set_component_state(name, current_health, source="RuntimeManager")
            except Exception:
                logger.exception("Component %r failed to start", name)
                self.state.set_component_state(name, ComponentState.FAILED, source="RuntimeManager")
                self.registry.cascade_failure(name)
        # Fix 2: INITIALIZING → ACTIVE is valid; INITIALIZING → DEGRADED is not.
        # Transition to ACTIVE first, then step to DEGRADED if any component failed.
        self.state.set_runtime_mode(RuntimeMode.ACTIVE, source="RuntimeManager.initialize")
        failed = [
            name for name in self.registry.components
            if self.state.get_component_state(name) == ComponentState.FAILED
        ]
        if failed:
            logger.warning("Components failed during init: %s — entering DEGRADED", failed)
            self.state.set_runtime_mode(RuntimeMode.DEGRADED, source="RuntimeManager.initialize")

    async def shutdown(self) -> None:
        self.state.set_runtime_mode(RuntimeMode.SHUTDOWN, source="RuntimeManager.shutdown")
        for name in reversed(self.registry.start_order()):
            comp = self._components[name]
            try:
                await comp.stop()
                self.state.set_component_state(
                    name, ComponentState.OFFLINE, source="RuntimeManager.shutdown"
                )
            except Exception:
                logger.exception("Component %r failed to stop cleanly", name)
        await self.runner.stop()
        self.state.set_runtime_mode(RuntimeMode.IDLE, source="RuntimeManager.shutdown")
