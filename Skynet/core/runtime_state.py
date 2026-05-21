from __future__ import annotations

import logging
from enum import Enum, auto
from typing import TYPE_CHECKING

from Skynet.core.events import ComponentStateChangedEvent, RuntimeModeChangedEvent

if TYPE_CHECKING:
    from Skynet.core.event_bus import EventBus

logger = logging.getLogger(__name__)


class ComponentState(Enum):
    OFFLINE = auto()
    STARTING = auto()
    IDLE = auto()
    BUSY = auto()
    DEGRADED = auto()
    FAILED = auto()


class RuntimeMode(Enum):
    IDLE = auto()
    INITIALIZING = auto()
    ACTIVE = auto()
    DEGRADED = auto()
    SHUTDOWN = auto()
    MAINTENANCE = auto()


# ---------------------------------------------------------------------------
# Transition graphs
# ---------------------------------------------------------------------------

_RUNTIME_TRANSITIONS: dict[RuntimeMode, set[RuntimeMode]] = {
    RuntimeMode.IDLE:         {RuntimeMode.INITIALIZING, RuntimeMode.MAINTENANCE},
    RuntimeMode.INITIALIZING: {RuntimeMode.ACTIVE, RuntimeMode.SHUTDOWN, RuntimeMode.MAINTENANCE},
    RuntimeMode.ACTIVE:       {RuntimeMode.DEGRADED, RuntimeMode.SHUTDOWN, RuntimeMode.MAINTENANCE},
    RuntimeMode.DEGRADED:     {RuntimeMode.ACTIVE, RuntimeMode.SHUTDOWN, RuntimeMode.MAINTENANCE},
    RuntimeMode.SHUTDOWN:     {RuntimeMode.IDLE, RuntimeMode.MAINTENANCE},
    RuntimeMode.MAINTENANCE:  {RuntimeMode.IDLE, RuntimeMode.SHUTDOWN},
}

_COMPONENT_TRANSITIONS: dict[ComponentState, set[ComponentState]] = {
    ComponentState.OFFLINE:   {ComponentState.STARTING},
    ComponentState.STARTING:  {ComponentState.IDLE, ComponentState.FAILED, ComponentState.OFFLINE},
    ComponentState.IDLE:      {ComponentState.BUSY, ComponentState.DEGRADED, ComponentState.FAILED, ComponentState.OFFLINE},
    ComponentState.BUSY:      {ComponentState.IDLE, ComponentState.DEGRADED, ComponentState.FAILED, ComponentState.OFFLINE},
    ComponentState.DEGRADED:  {ComponentState.IDLE, ComponentState.FAILED, ComponentState.OFFLINE},
    ComponentState.FAILED:    {ComponentState.OFFLINE},
}


# ---------------------------------------------------------------------------
# RuntimeState — single source of truth for runtime + component states.
# All mutations MUST go through set_runtime_mode / set_component_state.
# Direct attribute assignment raises AttributeError.
# ---------------------------------------------------------------------------

class RuntimeState:
    # The dict *reference* in _component_states is frozen by __setattr__.
    # Only set_component_state() may mutate its contents.
    __slots__ = ("_runtime_mode", "_component_states", "_bus")

    def __init__(self, bus: EventBus) -> None:
        object.__setattr__(self, "_runtime_mode", RuntimeMode.IDLE)
        object.__setattr__(self, "_component_states", {})
        object.__setattr__(self, "_bus", bus)

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError(
            "Direct mutation of RuntimeState is forbidden — use transition methods"
        )

    @property
    def runtime_mode(self) -> RuntimeMode:
        return self._runtime_mode

    def get_component_state(self, component: str) -> ComponentState:
        return self._component_states.get(component, ComponentState.OFFLINE)

    def set_runtime_mode(self, new_mode: RuntimeMode, *, source: str) -> None:
        current = self._runtime_mode
        if new_mode == current:
            raise ValueError(
                f"Self-transition on {current!r} is a no-op (source={source!r})"
            )
        allowed = _RUNTIME_TRANSITIONS.get(current, set())
        if new_mode not in allowed:
            raise ValueError(
                f"Invalid transition: RuntimeMode {current!r} → {new_mode!r} "
                f"(source={source!r})"
            )
        logger.info("RuntimeMode %s → %s [source=%s]", current, new_mode, source)
        object.__setattr__(self, "_runtime_mode", new_mode)
        self._bus.publish(RuntimeModeChangedEvent(previous=current, current=new_mode))

    def set_component_state(
        self, component: str, new_state: ComponentState, *, source: str
    ) -> None:
        current = self.get_component_state(component)
        if new_state == current:
            raise ValueError(
                f"Self-transition on {current!r} is a no-op (source={source!r})"
            )
        allowed = _COMPONENT_TRANSITIONS.get(current, set())
        if new_state not in allowed:
            raise ValueError(
                f"Invalid transition: {component!r} {current!r} → {new_state!r} "
                f"(source={source!r})"
            )
        logger.info(
            "Component[%s] %s → %s [source=%s]", component, current, new_state, source
        )
        self._component_states[component] = new_state
        self._bus.publish(
            ComponentStateChangedEvent(
                component=component, previous=current, current=new_state,
            )
        )
