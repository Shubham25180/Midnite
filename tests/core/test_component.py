# tests/core/test_component.py
import pytest
from Skynet.core.component import Component
from Skynet.core.runtime_state import ComponentState


class MinimalComponent(Component):
    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    def health(self) -> ComponentState:
        return ComponentState.IDLE


class BrokenComponent(Component):
    pass


def test_minimal_component_instantiates():
    c = MinimalComponent(name="test")
    assert c.name == "test"


def test_broken_component_cannot_instantiate():
    with pytest.raises(TypeError):
        BrokenComponent(name="broken")


def test_health_returns_component_state():
    c = MinimalComponent(name="minimal")
    assert c.health() == ComponentState.IDLE


@pytest.mark.asyncio
async def test_start_and_stop_callable():
    c = MinimalComponent(name="lifecycle")
    await c.start()
    assert c.health() == ComponentState.IDLE
    await c.stop()
    assert c.health() == ComponentState.IDLE
