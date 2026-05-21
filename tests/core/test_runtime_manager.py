# tests/core/test_runtime_manager.py
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock
from Skynet.core.runtime_manager import RuntimeManager
from Skynet.core.component import Component
from Skynet.core.runtime_state import ComponentState, RuntimeMode
from Skynet.core.event_bus import EventBus


class FakeComp(Component):
    def __init__(self, name: str):
        super().__init__(name=name)
        self._state = ComponentState.OFFLINE

    async def start(self) -> None:
        self._state = ComponentState.IDLE

    async def stop(self) -> None:
        self._state = ComponentState.OFFLINE

    def health(self) -> ComponentState:
        return self._state


@pytest.fixture
async def manager():
    m = RuntimeManager()
    return m


@pytest.mark.asyncio
async def test_register_and_start_component(manager):
    comp = FakeComp("fake")
    manager.register("fake", comp, deps=[])
    await manager.initialize()
    assert manager.state.get_component_state("fake") == ComponentState.IDLE
    await manager.shutdown()


@pytest.mark.asyncio
async def test_initialize_sets_runtime_active(manager):
    comp = FakeComp("fake")
    manager.register("fake", comp, deps=[])
    await manager.initialize()
    assert manager.state.runtime_mode == RuntimeMode.ACTIVE
    await manager.shutdown()


@pytest.mark.asyncio
async def test_shutdown_returns_to_idle(manager):
    comp = FakeComp("fake")
    manager.register("fake", comp, deps=[])
    await manager.initialize()
    await manager.shutdown()
    # Graceful shutdown passes through SHUTDOWN then returns to IDLE so
    # the system can be re-initialized without restarting the process.
    assert manager.state.runtime_mode == RuntimeMode.IDLE
    assert manager.state.get_component_state("fake") == ComponentState.OFFLINE


def test_runtime_manager_has_no_cognitive_methods():
    # Fix 4: Construct RuntimeManager directly — the async fixture passes a coroutine
    # to sync tests, so manager would be a coroutine object, not a RuntimeManager.
    m = RuntimeManager()
    forbidden = ["think", "respond", "chat", "transcribe", "speak", "route", "execute"]
    for method in forbidden:
        assert not hasattr(m, method), f"RuntimeManager must not have method: {method!r}"
