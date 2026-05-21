# tests/core/test_tasks.py
import asyncio
import pytest
from Skynet.core.tasks import BackgroundRunner, TaskPriority, TaskType


@pytest.fixture
async def runner():
    r = BackgroundRunner()
    await r.start()
    yield r
    await r.stop()


@pytest.mark.asyncio
async def test_enqueue_and_run_coroutine(runner):
    result = []

    async def work():
        result.append(1)

    await runner.enqueue(work(), priority=TaskPriority.NORMAL, task_type=TaskType.COMPUTE)
    await runner.join()
    assert result == [1]


@pytest.mark.asyncio
async def test_higher_priority_runs_first(runner):
    order = []
    await runner.stop()

    r = BackgroundRunner()

    async def low():
        order.append("low")

    async def high():
        order.append("high")

    await r.start()
    await r.enqueue(low(), priority=TaskPriority.LOW, task_type=TaskType.IO)
    await r.enqueue(high(), priority=TaskPriority.HIGH, task_type=TaskType.COMPUTE)
    await r.join()
    await r.stop()
    assert order[0] == "high"
