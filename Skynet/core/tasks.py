# Skynet/core/tasks.py
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Coroutine, Any

logger = logging.getLogger(__name__)


class TaskPriority(IntEnum):
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3


class TaskType(str):
    COMPUTE = "compute"
    IO = "io"
    NETWORK = "network"
    INDEXING = "indexing"


@dataclass(order=True)
class _QueueItem:
    priority: int
    seq: int = field(compare=True)
    coro: Coroutine = field(compare=False)
    task_type: str = field(compare=False)


class BackgroundRunner:
    def __init__(self) -> None:
        self._queue: asyncio.PriorityQueue[_QueueItem] | None = None
        self._worker_task: asyncio.Task | None = None
        self._seq = 0
        self._running = False

    async def start(self) -> None:
        self._queue = asyncio.PriorityQueue()
        self._running = True
        self._worker_task = asyncio.create_task(self._worker())

    async def stop(self) -> None:
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

    async def enqueue(self, coro: Coroutine, *, priority: TaskPriority, task_type: str) -> None:
        if self._queue is None:
            raise RuntimeError("BackgroundRunner not started — call start() first")
        self._seq += 1
        item = _QueueItem(priority=priority.value, seq=self._seq, coro=coro, task_type=task_type)
        await self._queue.put(item)

    async def join(self) -> None:
        if self._queue is not None:
            await self._queue.join()

    async def _worker(self) -> None:
        assert self._queue is not None
        while self._running:
            try:
                item = await asyncio.wait_for(self._queue.get(), timeout=0.1)
                try:
                    await item.coro
                except Exception:
                    logger.exception("BackgroundRunner task failed [type=%s]", item.task_type)
                finally:
                    self._queue.task_done()
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
