# Nexux V0.1 Core Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Nexux V0.1 cognitive core loop with a live web dashboard at localhost:7799.

**Architecture:** Typed EventBus as the nervous system, RuntimeState as the state machine, ComponentRegistry for dependency management, and RuntimeManager for lifecycle coordination only. FastAPI serves a WebSocket-streaming dashboard; cognitive logic lives exclusively in Orchestrator → TaskRouter.

**Tech Stack:** Python 3.11+, FastAPI, uvicorn, asyncio, faster-whisper, pyttsx3, requests (Ollama), anthropic SDK

---

## File Map

| File | Responsibility |
|------|----------------|
| `Skynet/core/events.py` | BaseEvent + all V0.1 event dataclasses |
| `Skynet/core/event_bus.py` | Typed pub/sub with subscription tokens |
| `Skynet/core/runtime_state.py` | RuntimeMode + ComponentState enums, transition methods |
| `Skynet/core/component.py` | Component ABC (start/stop/health) |
| `Skynet/core/component_registry.py` | Dependency graph, topological start order, cascading failure |
| `Skynet/core/runtime_manager.py` | Lifecycle coordinator — NO cognition |
| `Skynet/core/tasks.py` | BackgroundRunner, TaskPriority, TaskType |
| `Skynet/core/resource_manager.py` | Stub — interface only |
| `Skynet/core/orchestrator.py` | Cognitive flow, rolling window — replaces brain.py |
| `Skynet/task/task_router.py` | Routes intent to orchestrator (V0.1: passthrough) |
| `Skynet/task/workflow_executor.py` | Stub V0.1 |
| `Skynet/ui/server.py` | FastAPI app — transport only |
| `Skynet/ui/routes/settings.py` | GET/POST settings.yaml |
| `Skynet/ui/routes/hardware.py` | Mic, audio, CPU, GPU, RAM |
| `Skynet/ui/routes/status.py` | Component connectivity checks |
| `Skynet/ui/routes/models.py` | Available Ollama models |
| `Skynet/ui/ws/stream.py` | EventBus subscriber → WebSocket push |
| `Skynet/ui/static/index.html` | Dashboard HTML |
| `Skynet/ui/static/js/api.js` | All fetch() calls |
| `Skynet/ui/static/js/websocket.js` | WS connection + reconnect |
| `Skynet/ui/static/js/dashboard.js` | Hardware row + component cards rendering |
| `Skynet/ui/static/js/runtime.js` | Initialize/shutdown actions |
| `Skynet/voice/stt.py` | STT adapted to Component ABC |
| `Skynet/voice/tts.py` | TTS (pyttsx3 initially) |
| `Skynet/main.py` | Thin launcher: config + RuntimeManager + UI server |
| `tests/core/test_events.py` | Event dataclass tests |
| `tests/core/test_event_bus.py` | Pub/sub tests |
| `tests/core/test_runtime_state.py` | State machine tests |
| `tests/core/test_component_registry.py` | Dependency graph tests |
| `tests/core/test_runtime_manager.py` | Lifecycle + boundary tests |
| `tests/core/test_fake_pipeline.py` | Architecture verification end-to-end |
| `tests/core/test_orchestrator.py` | Rolling window + provider swap test |

---

## Group 1: EventBus

### Task 1: events.py — BaseEvent + V0.1 event dataclasses

**Files:**
- Create: `Skynet/core/events.py`
- Create: `tests/core/test_events.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/core/test_events.py
import time
from Skynet.core.events import (
    BaseEvent, STTTranscribedEvent, OrchestratorResponseEvent,
    ComponentStateChangedEvent, RuntimeModeChangedEvent,
)
from Skynet.core.runtime_state import ComponentState, RuntimeMode


def test_base_event_auto_timestamp():
    before = time.time()
    e = BaseEvent()
    after = time.time()
    assert before <= e.timestamp <= after


def test_base_event_sequence_ids_increment():
    e1 = BaseEvent()
    e2 = BaseEvent()
    assert e2.sequence_id == e1.sequence_id + 1


def test_stt_event_carries_transcript():
    e = STTTranscribedEvent(transcript="hello world")
    assert e.transcript == "hello world"
    assert hasattr(e, "timestamp")
    assert hasattr(e, "sequence_id")


def test_orchestrator_response_event():
    e = OrchestratorResponseEvent(response="I can help with that.")
    assert e.response == "I can help with that."


def test_component_state_changed_event():
    e = ComponentStateChangedEvent(
        component="stt",
        previous=ComponentState.OFFLINE,
        current=ComponentState.STARTING,
    )
    assert e.component == "stt"
    assert e.previous == ComponentState.OFFLINE
    assert e.current == ComponentState.STARTING


def test_runtime_mode_changed_event():
    e = RuntimeModeChangedEvent(
        previous=RuntimeMode.IDLE,
        current=RuntimeMode.INITIALIZING,
    )
    assert e.previous == RuntimeMode.IDLE
    assert e.current == RuntimeMode.INITIALIZING
```

- [ ] **Step 2: Run test to verify it fails**

```
python -m pytest tests/core/test_events.py -v
```

Expected: `ModuleNotFoundError` or `ImportError`

- [ ] **Step 3: Write minimal implementation**

```python
# Skynet/core/events.py
import time
from dataclasses import dataclass, field
from itertools import count
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from Skynet.core.runtime_state import ComponentState, RuntimeMode

_seq = count(1)


def _next_seq() -> int:
    return next(_seq)


@dataclass
class BaseEvent:
    timestamp: float = field(default_factory=time.time)
    sequence_id: int = field(default_factory=_next_seq)


@dataclass
class STTTranscribedEvent(BaseEvent):
    transcript: str = ""


@dataclass
class OrchestratorResponseEvent(BaseEvent):
    response: str = ""


@dataclass
class ComponentStateChangedEvent(BaseEvent):
    component: str = ""
    previous: "ComponentState | None" = None
    current: "ComponentState | None" = None


@dataclass
class RuntimeModeChangedEvent(BaseEvent):
    previous: "RuntimeMode | None" = None
    current: "RuntimeMode | None" = None
```

- [ ] **Step 4: Run test to verify it passes**

```
python -m pytest tests/core/test_events.py -v
```

Expected: all 6 tests PASS

- [ ] **Step 5: Commit**

```
rtk git add Skynet/core/events.py tests/core/test_events.py
rtk git commit -m "feat(core): typed event dataclasses with auto-increment sequence_id"
```

---

### Task 2: event_bus.py — typed pub/sub

**Files:**
- Create: `Skynet/core/event_bus.py`
- Create: `tests/core/test_event_bus.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/core/test_event_bus.py
import asyncio
import pytest
from Skynet.core.event_bus import EventBus
from Skynet.core.events import BaseEvent, STTTranscribedEvent, OrchestratorResponseEvent


@pytest.fixture
def bus():
    return EventBus()


def test_subscribe_and_receive(bus):
    received = []
    bus.subscribe(STTTranscribedEvent, received.append)
    bus.publish(STTTranscribedEvent(transcript="hi"))
    assert len(received) == 1
    assert received[0].transcript == "hi"


def test_subscriber_only_receives_its_type(bus):
    stt_received = []
    orc_received = []
    bus.subscribe(STTTranscribedEvent, stt_received.append)
    bus.subscribe(OrchestratorResponseEvent, orc_received.append)
    bus.publish(STTTranscribedEvent(transcript="hello"))
    assert len(stt_received) == 1
    assert len(orc_received) == 0


def test_unsubscribe_via_token(bus):
    received = []
    token = bus.subscribe(STTTranscribedEvent, received.append)
    bus.unsubscribe(token)
    bus.publish(STTTranscribedEvent(transcript="should not arrive"))
    assert len(received) == 0


def test_multiple_subscribers_same_type(bus):
    a, b = [], []
    bus.subscribe(STTTranscribedEvent, a.append)
    bus.subscribe(STTTranscribedEvent, b.append)
    bus.publish(STTTranscribedEvent(transcript="broadcast"))
    assert len(a) == 1
    assert len(b) == 1


def test_publish_non_base_event_raises(bus):
    with pytest.raises(TypeError):
        bus.publish("not an event")


def test_base_event_subclass_only_triggers_exact_type(bus):
    base_received = []
    stt_received = []
    bus.subscribe(BaseEvent, base_received.append)
    bus.subscribe(STTTranscribedEvent, stt_received.append)
    bus.publish(STTTranscribedEvent(transcript="sub"))
    # BaseEvent subscribers should NOT receive STTTranscribedEvent unless explicitly subscribed
    assert len(stt_received) == 1
    assert len(base_received) == 0
```

- [ ] **Step 2: Run test to verify it fails**

```
python -m pytest tests/core/test_event_bus.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# Skynet/core/event_bus.py
from __future__ import annotations

import uuid
from collections import defaultdict
from typing import Callable, Type

from Skynet.core.events import BaseEvent

SubscriptionToken = str


class EventBus:
    def __init__(self) -> None:
        # Map: event_type -> {token: callback}
        self._subscribers: dict[type, dict[str, Callable]] = defaultdict(dict)

    def subscribe(self, event_type: Type[BaseEvent], callback: Callable) -> SubscriptionToken:
        token = str(uuid.uuid4())
        self._subscribers[event_type][token] = callback
        return token

    def unsubscribe(self, token: SubscriptionToken) -> None:
        for callbacks in self._subscribers.values():
            callbacks.pop(token, None)

    def publish(self, event: BaseEvent) -> None:
        if not isinstance(event, BaseEvent):
            raise TypeError(f"EventBus.publish requires a BaseEvent subclass, got {type(event)}")
        for callback in list(self._subscribers[type(event)].values()):
            callback(event)
```

- [ ] **Step 4: Run test to verify it passes**

```
python -m pytest tests/core/test_event_bus.py -v
```

Expected: all 6 tests PASS

- [ ] **Step 5: Commit**

```
rtk git add Skynet/core/event_bus.py tests/core/test_event_bus.py
rtk git commit -m "feat(core): EventBus — typed pub/sub with subscription tokens"
```

---

## Group 2: State Machine

### Task 3: runtime_state.py — state machine with transition methods

**Files:**
- Create: `Skynet/core/runtime_state.py`
- Create: `tests/core/test_runtime_state.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/core/test_runtime_state.py
import pytest
from Skynet.core.runtime_state import RuntimeState, RuntimeMode, ComponentState
from Skynet.core.event_bus import EventBus
from Skynet.core.events import ComponentStateChangedEvent, RuntimeModeChangedEvent


@pytest.fixture
def bus():
    return EventBus()


@pytest.fixture
def state(bus):
    return RuntimeState(bus)


def test_initial_runtime_mode_is_idle(state):
    assert state.runtime_mode == RuntimeMode.IDLE


def test_initial_component_state_is_offline_for_unknown(state):
    assert state.get_component_state("stt") == ComponentState.OFFLINE


def test_valid_runtime_transition_idle_to_initializing(state):
    state.set_runtime_mode(RuntimeMode.INITIALIZING, source="test")
    assert state.runtime_mode == RuntimeMode.INITIALIZING


def test_invalid_runtime_transition_raises(state):
    with pytest.raises(ValueError, match="Invalid transition"):
        state.set_runtime_mode(RuntimeMode.ACTIVE, source="test")


def test_runtime_transition_emits_event(state, bus):
    received = []
    bus.subscribe(RuntimeModeChangedEvent, received.append)
    state.set_runtime_mode(RuntimeMode.INITIALIZING, source="test")
    assert len(received) == 1
    assert received[0].previous == RuntimeMode.IDLE
    assert received[0].current == RuntimeMode.INITIALIZING


def test_valid_component_transition_offline_to_starting(state):
    state.set_component_state("stt", ComponentState.STARTING, source="test")
    assert state.get_component_state("stt") == ComponentState.STARTING


def test_invalid_component_transition_raises(state):
    with pytest.raises(ValueError, match="Invalid transition"):
        state.set_component_state("stt", ComponentState.BUSY, source="test")


def test_component_transition_emits_event(state, bus):
    received = []
    bus.subscribe(ComponentStateChangedEvent, received.append)
    state.set_component_state("stt", ComponentState.STARTING, source="test")
    assert len(received) == 1
    assert received[0].component == "stt"
    assert received[0].previous == ComponentState.OFFLINE
    assert received[0].current == ComponentState.STARTING


def test_no_direct_state_mutation_allowed(state):
    with pytest.raises(AttributeError):
        state.runtime_mode = RuntimeMode.ACTIVE
```

- [ ] **Step 2: Run test to verify it fails**

```
python -m pytest tests/core/test_runtime_state.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# Skynet/core/runtime_state.py
from __future__ import annotations

import logging
import time
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from Skynet.core.event_bus import EventBus

from Skynet.core.events import ComponentStateChangedEvent, RuntimeModeChangedEvent

logger = logging.getLogger(__name__)


class RuntimeMode(str, Enum):
    IDLE = "idle"
    INITIALIZING = "initializing"
    ACTIVE = "active"
    DEGRADED = "degraded"
    SHUTDOWN = "shutdown"
    MAINTENANCE = "maintenance"


class ComponentState(str, Enum):
    OFFLINE = "offline"
    STARTING = "starting"
    IDLE = "idle"
    BUSY = "busy"
    DEGRADED = "degraded"
    FAILED = "failed"


_RUNTIME_TRANSITIONS: dict[RuntimeMode, set[RuntimeMode]] = {
    RuntimeMode.IDLE:         {RuntimeMode.INITIALIZING, RuntimeMode.MAINTENANCE},
    RuntimeMode.INITIALIZING: {RuntimeMode.ACTIVE, RuntimeMode.SHUTDOWN, RuntimeMode.MAINTENANCE},
    RuntimeMode.ACTIVE:       {RuntimeMode.DEGRADED, RuntimeMode.SHUTDOWN, RuntimeMode.MAINTENANCE},
    RuntimeMode.DEGRADED:     {RuntimeMode.ACTIVE, RuntimeMode.SHUTDOWN, RuntimeMode.MAINTENANCE},
    RuntimeMode.SHUTDOWN:     {RuntimeMode.MAINTENANCE},
    RuntimeMode.MAINTENANCE:  set(RuntimeMode),
}

_COMPONENT_TRANSITIONS: dict[ComponentState, set[ComponentState]] = {
    ComponentState.OFFLINE:   {ComponentState.STARTING},
    ComponentState.STARTING:  {ComponentState.IDLE, ComponentState.FAILED},
    ComponentState.IDLE:      {ComponentState.BUSY, ComponentState.DEGRADED, ComponentState.FAILED},
    ComponentState.BUSY:      {ComponentState.IDLE, ComponentState.DEGRADED, ComponentState.FAILED},
    ComponentState.DEGRADED:  {ComponentState.IDLE, ComponentState.FAILED},
    ComponentState.FAILED:    {ComponentState.OFFLINE},
}


class RuntimeState:
    __slots__ = ("_runtime_mode", "_component_states", "_bus")

    def __init__(self, bus: EventBus) -> None:
        object.__setattr__(self, "_runtime_mode", RuntimeMode.IDLE)
        object.__setattr__(self, "_component_states", {})
        object.__setattr__(self, "_bus", bus)

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("Direct mutation of RuntimeState is forbidden — use transition methods")

    @property
    def runtime_mode(self) -> RuntimeMode:
        return self._runtime_mode

    def get_component_state(self, component: str) -> ComponentState:
        return self._component_states.get(component, ComponentState.OFFLINE)

    def set_runtime_mode(self, new_mode: RuntimeMode, *, source: str) -> None:
        current = self._runtime_mode
        allowed = _RUNTIME_TRANSITIONS.get(current, set())
        if new_mode not in allowed:
            raise ValueError(
                f"Invalid transition: RuntimeMode {current!r} → {new_mode!r} (source={source!r})"
            )
        logger.info("RuntimeMode %s → %s [source=%s]", current, new_mode, source)
        object.__setattr__(self, "_runtime_mode", new_mode)
        self._bus.publish(RuntimeModeChangedEvent(previous=current, current=new_mode))

    def set_component_state(self, component: str, new_state: ComponentState, *, source: str) -> None:
        current = self.get_component_state(component)
        allowed = _COMPONENT_TRANSITIONS.get(current, set())
        if new_state not in allowed:
            raise ValueError(
                f"Invalid transition: {component!r} {current!r} → {new_state!r} (source={source!r})"
            )
        logger.info("Component[%s] %s → %s [source=%s]", component, current, new_state, source)
        self._component_states[component] = new_state
        self._bus.publish(ComponentStateChangedEvent(
            component=component, previous=current, current=new_state,
        ))
```

- [ ] **Step 4: Run test to verify it passes**

```
python -m pytest tests/core/test_runtime_state.py -v
```

Expected: all 9 tests PASS

- [ ] **Step 5: Commit**

```
rtk git add Skynet/core/runtime_state.py tests/core/test_runtime_state.py
rtk git commit -m "feat(core): RuntimeState — state machine with validated transitions, no direct mutation"
```

---

## Group 3: Component Contract

### Task 4: component.py — Component ABC

**Files:**
- Create: `Skynet/core/component.py`
- Create: `tests/core/test_component.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/core/test_component.py
import asyncio
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
    await c.stop()
```

- [ ] **Step 2: Run test to verify it fails**

```
python -m pytest tests/core/test_component.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

```
python -m pytest tests/core/test_component.py -v
```

Expected: all 4 tests PASS

- [ ] **Step 5: Commit**

```
rtk git add Skynet/core/component.py tests/core/test_component.py
rtk git commit -m "feat(core): Component ABC — start/stop/health contract"
```

---

## Group 4: Registry + Manager

### Task 5: component_registry.py — dependency graph + cascaded state

**Files:**
- Create: `Skynet/core/component_registry.py`
- Create: `tests/core/test_component_registry.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/core/test_component_registry.py
import pytest
from Skynet.core.component_registry import ComponentRegistry
from Skynet.core.runtime_state import RuntimeState, ComponentState
from Skynet.core.event_bus import EventBus


@pytest.fixture
def setup():
    bus = EventBus()
    state = RuntimeState(bus)
    registry = ComponentRegistry(state)
    return bus, state, registry


def test_register_component_no_deps(setup):
    _, _, registry = setup
    registry.register("audio_device", deps=[])
    assert "audio_device" in registry.components


def test_register_with_dependency(setup):
    _, _, registry = setup
    registry.register("audio_device", deps=[])
    registry.register("stt", deps=["audio_device"])
    assert "audio_device" in registry.deps_of("stt")


def test_register_missing_dep_raises(setup):
    _, _, registry = setup
    with pytest.raises(ValueError, match="unknown dependency"):
        registry.register("stt", deps=["audio_device"])


def test_topological_start_order(setup):
    _, _, registry = setup
    registry.register("audio_device", deps=[])
    registry.register("stt", deps=["audio_device"])
    registry.register("tts", deps=["audio_device"])
    registry.register("llm1_provider", deps=[])
    registry.register("orchestrator", deps=["llm1_provider"])
    order = registry.start_order()
    assert order.index("audio_device") < order.index("stt")
    assert order.index("audio_device") < order.index("tts")
    assert order.index("llm1_provider") < order.index("orchestrator")


def test_cascade_failure_to_dependents(setup):
    _, state, registry = setup
    registry.register("audio_device", deps=[])
    registry.register("stt", deps=["audio_device"])
    # Advance states so cascade transition is valid
    state.set_component_state("audio_device", ComponentState.STARTING, source="test")
    state.set_component_state("audio_device", ComponentState.IDLE, source="test")
    state.set_component_state("stt", ComponentState.STARTING, source="test")
    state.set_component_state("stt", ComponentState.IDLE, source="test")
    # Simulate audio_device failing
    state.set_component_state("audio_device", ComponentState.DEGRADED, source="test")
    state.set_component_state("audio_device", ComponentState.FAILED, source="test")
    registry.cascade_failure("audio_device")
    assert state.get_component_state("stt") == ComponentState.FAILED
```

- [ ] **Step 2: Run test to verify it fails**

```
python -m pytest tests/core/test_component_registry.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
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
                    self._state.set_component_state(dependent, ComponentState.FAILED, source="cascade")
                except ValueError:
                    pass
                self.cascade_failure(dependent)
```

- [ ] **Step 4: Run test to verify it passes**

```
python -m pytest tests/core/test_component_registry.py -v
```

Expected: all 5 tests PASS

- [ ] **Step 5: Commit**

```
rtk git add Skynet/core/component_registry.py tests/core/test_component_registry.py
rtk git commit -m "feat(core): ComponentRegistry — topological ordering + cascaded failure propagation"
```

---

### Task 6: tasks.py — BackgroundRunner

**Files:**
- Create: `Skynet/core/tasks.py`

- [ ] **Step 1: Write the test**

```python
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
    await asyncio.sleep(0.05)
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

    await r.enqueue(low(), priority=TaskPriority.LOW, task_type=TaskType.IO)
    await r.enqueue(high(), priority=TaskPriority.HIGH, task_type=TaskType.COMPUTE)
    await r.start()
    await asyncio.sleep(0.1)
    await r.stop()
    assert order[0] == "high"
```

- [ ] **Step 2: Run test to verify it fails**

```
python -m pytest tests/core/test_tasks.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
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
        self._queue: asyncio.PriorityQueue[_QueueItem] = asyncio.PriorityQueue()
        self._worker_task: asyncio.Task | None = None
        self._seq = 0
        self._running = False

    async def start(self) -> None:
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
        self._seq += 1
        item = _QueueItem(priority=priority.value, seq=self._seq, coro=coro, task_type=task_type)
        await self._queue.put(item)

    async def _worker(self) -> None:
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
```

- [ ] **Step 4: Run test to verify it passes**

```
python -m pytest tests/core/test_tasks.py -v
```

Expected: all 2 tests PASS

- [ ] **Step 5: Commit**

```
rtk git add Skynet/core/tasks.py tests/core/test_tasks.py
rtk git commit -m "feat(core): BackgroundRunner with TaskPriority + TaskType — priority queue execution"
```

---

### Task 7: runtime_manager.py — lifecycle coordinator

**Files:**
- Create: `Skynet/core/runtime_manager.py`
- Create: `tests/core/test_runtime_manager.py`

- [ ] **Step 1: Write the failing test**

```python
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
async def test_shutdown_sets_runtime_shutdown(manager):
    comp = FakeComp("fake")
    manager.register("fake", comp, deps=[])
    await manager.initialize()
    await manager.shutdown()
    assert manager.state.runtime_mode == RuntimeMode.SHUTDOWN


def test_runtime_manager_has_no_cognitive_methods(manager):
    # Boundary test: RuntimeManager must not expose cognition
    forbidden = ["think", "respond", "chat", "transcribe", "speak", "route", "execute"]
    for method in forbidden:
        assert not hasattr(manager, method), f"RuntimeManager must not have method: {method!r}"
```

- [ ] **Step 2: Run test to verify it fails**

```
python -m pytest tests/core/test_runtime_manager.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# Skynet/core/runtime_manager.py
from __future__ import annotations

import asyncio
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

    async def initialize(self) -> None:
        self.state.set_runtime_mode(RuntimeMode.INITIALIZING, source="RuntimeManager.initialize")
        await self.runner.start()
        for name in self.registry.start_order():
            comp = self._components[name]
            self.state.set_component_state(name, ComponentState.STARTING, source="RuntimeManager")
            try:
                await comp.start()
                current_health = comp.health()
                self.state.set_component_state(name, current_health, source="RuntimeManager")
            except Exception:
                logger.exception("Component %r failed to start", name)
                self.state.set_component_state(name, ComponentState.FAILED, source="RuntimeManager")
                self.registry.cascade_failure(name)
        self.state.set_runtime_mode(RuntimeMode.ACTIVE, source="RuntimeManager.initialize")

    async def shutdown(self) -> None:
        self.state.set_runtime_mode(RuntimeMode.SHUTDOWN, source="RuntimeManager.shutdown")
        for name in reversed(self.registry.start_order()):
            comp = self._components[name]
            try:
                await comp.stop()
            except Exception:
                logger.exception("Component %r failed to stop cleanly", name)
        await self.runner.stop()
```

- [ ] **Step 4: Run test to verify it passes**

```
python -m pytest tests/core/test_runtime_manager.py -v
```

Expected: all 4 tests PASS

- [ ] **Step 5: Commit**

```
rtk git add Skynet/core/runtime_manager.py tests/core/test_runtime_manager.py
rtk git commit -m "feat(core): RuntimeManager — lifecycle coordination only, boundary-tested"
```

---

## Group 5: Architecture Verification

### Task 8: FakeComponent + full pipeline test

**Files:**
- Create: `Skynet/core/fake_component.py`
- Create: `tests/core/test_fake_pipeline.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/core/test_fake_pipeline.py
import asyncio
import pytest
from Skynet.core.fake_component import FakeSTT
from Skynet.core.runtime_manager import RuntimeManager
from Skynet.core.runtime_state import ComponentState, RuntimeMode
from Skynet.core.events import STTTranscribedEvent, ComponentStateChangedEvent


@pytest.mark.asyncio
async def test_fake_stt_emits_transcribed_event():
    manager = RuntimeManager()
    stt = FakeSTT(text="hello nexux", bus=manager.bus, state=manager.state)
    manager.register("audio_device", stt, deps=[])

    received: list[STTTranscribedEvent] = []
    manager.bus.subscribe(STTTranscribedEvent, received.append)

    await manager.initialize()
    await stt.emit_transcription()
    await manager.shutdown()

    assert len(received) == 1
    assert received[0].transcript == "hello nexux"


@pytest.mark.asyncio
async def test_component_state_changes_propagate_to_event_bus():
    manager = RuntimeManager()
    stt = FakeSTT(text="test", bus=manager.bus, state=manager.state)
    manager.register("audio_device", stt, deps=[])

    state_events: list[ComponentStateChangedEvent] = []
    manager.bus.subscribe(ComponentStateChangedEvent, state_events.append)

    await manager.initialize()
    await manager.shutdown()

    names = [e.component for e in state_events]
    assert "audio_device" in names
    # STARTING and then IDLE should appear
    audio_events = [e for e in state_events if e.component == "audio_device"]
    states = [e.current for e in audio_events]
    assert ComponentState.STARTING in states
    assert ComponentState.IDLE in states


@pytest.mark.asyncio
async def test_runtime_mode_events_emitted_on_initialize_and_shutdown():
    from Skynet.core.events import RuntimeModeChangedEvent
    manager = RuntimeManager()
    stt = FakeSTT(text="x", bus=manager.bus, state=manager.state)
    manager.register("audio_device", stt, deps=[])

    mode_events: list[RuntimeModeChangedEvent] = []
    manager.bus.subscribe(RuntimeModeChangedEvent, mode_events.append)

    await manager.initialize()
    await manager.shutdown()

    modes = [(e.previous, e.current) for e in mode_events]
    from Skynet.core.runtime_state import RuntimeMode
    assert (RuntimeMode.IDLE, RuntimeMode.INITIALIZING) in modes
    assert (RuntimeMode.INITIALIZING, RuntimeMode.ACTIVE) in modes
    assert (RuntimeMode.ACTIVE, RuntimeMode.SHUTDOWN) in modes
```

- [ ] **Step 2: Run test to verify it fails**

```
python -m pytest tests/core/test_fake_pipeline.py -v
```

Expected: `ModuleNotFoundError: No module named 'Skynet.core.fake_component'`

- [ ] **Step 3: Write FakeSTT**

```python
# Skynet/core/fake_component.py
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from Skynet.core.event_bus import EventBus
    from Skynet.core.runtime_state import RuntimeState

from Skynet.core.component import Component
from Skynet.core.events import STTTranscribedEvent
from Skynet.core.runtime_state import ComponentState


class FakeSTT(Component):
    """Test double — returns hardcoded text without touching hardware or AI."""

    def __init__(self, *, text: str, bus: EventBus, state: RuntimeState) -> None:
        super().__init__(name="audio_device")
        self._text = text
        self._bus = bus
        self._state = state
        self._health = ComponentState.OFFLINE

    async def start(self) -> None:
        self._health = ComponentState.IDLE

    async def stop(self) -> None:
        self._health = ComponentState.OFFLINE

    def health(self) -> ComponentState:
        return self._health

    async def emit_transcription(self) -> None:
        self._bus.publish(STTTranscribedEvent(transcript=self._text))
```

- [ ] **Step 4: Run test to verify it passes**

```
python -m pytest tests/core/test_fake_pipeline.py -v
```

Expected: all 3 tests PASS

- [ ] **Step 5: Commit**

```
rtk git add Skynet/core/fake_component.py tests/core/test_fake_pipeline.py
rtk git commit -m "feat(core): FakeSTT + full pipeline tests — events, state, runtime modes verified"
```

---

## Group 6: Dashboard

### Task 9: FastAPI server + WebSocket stream

**Files:**
- Create: `Skynet/ui/__init__.py`
- Create: `Skynet/ui/ws/__init__.py`
- Create: `Skynet/ui/ws/stream.py`
- Create: `Skynet/ui/server.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/ui/test_websocket_stream.py
import asyncio
import pytest
from Skynet.core.event_bus import EventBus
from Skynet.core.events import ComponentStateChangedEvent
from Skynet.core.runtime_state import ComponentState
from Skynet.ui.ws.stream import EventStreamBroadcaster


@pytest.fixture
def bus():
    return EventBus()


@pytest.mark.asyncio
async def test_broadcaster_buffers_events(bus):
    broadcaster = EventStreamBroadcaster(bus)
    broadcaster.start()
    bus.publish(ComponentStateChangedEvent(
        component="stt",
        previous=ComponentState.OFFLINE,
        current=ComponentState.STARTING,
    ))
    await asyncio.sleep(0.01)
    msgs = broadcaster.drain()
    assert len(msgs) == 1
    assert msgs[0]["type"] == "component_state"
    assert msgs[0]["component"] == "stt"
    broadcaster.stop()
```

- [ ] **Step 2: Run test to verify it fails**

```
python -m pytest tests/ui/test_websocket_stream.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Implement stream + server**

```python
# Skynet/ui/ws/stream.py
from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from Skynet.core.event_bus import EventBus

from Skynet.core.events import (
    ComponentStateChangedEvent, RuntimeModeChangedEvent,
    STTTranscribedEvent, OrchestratorResponseEvent,
)

logger = logging.getLogger(__name__)


class EventStreamBroadcaster:
    def __init__(self, bus: EventBus) -> None:
        self._bus = bus
        self._buffer: list[dict] = []
        self._tokens: list[str] = []

    def start(self) -> None:
        self._tokens = [
            self._bus.subscribe(ComponentStateChangedEvent, self._on_component_state),
            self._bus.subscribe(RuntimeModeChangedEvent, self._on_runtime_mode),
            self._bus.subscribe(STTTranscribedEvent, self._on_stt),
            self._bus.subscribe(OrchestratorResponseEvent, self._on_response),
        ]

    def stop(self) -> None:
        for token in self._tokens:
            self._bus.unsubscribe(token)
        self._tokens = []

    def drain(self) -> list[dict]:
        msgs, self._buffer = self._buffer, []
        return msgs

    def _on_component_state(self, event: ComponentStateChangedEvent) -> None:
        self._buffer.append({
            "type": "component_state",
            "component": event.component,
            "previous": event.previous,
            "current": event.current,
            "timestamp": event.timestamp,
        })

    def _on_runtime_mode(self, event: RuntimeModeChangedEvent) -> None:
        self._buffer.append({
            "type": "runtime_mode",
            "previous": event.previous,
            "current": event.current,
            "timestamp": event.timestamp,
        })

    def _on_stt(self, event: STTTranscribedEvent) -> None:
        self._buffer.append({
            "type": "stt_transcript",
            "transcript": event.transcript,
            "timestamp": event.timestamp,
        })

    def _on_response(self, event: OrchestratorResponseEvent) -> None:
        self._buffer.append({
            "type": "orchestrator_response",
            "response": event.response,
            "timestamp": event.timestamp,
        })
```

```python
# Skynet/ui/server.py
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

if TYPE_CHECKING:
    from Skynet.core.runtime_manager import RuntimeManager

from Skynet.ui.ws.stream import EventStreamBroadcaster

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"


def build_app(manager: RuntimeManager) -> FastAPI:
    app = FastAPI(title="Nexux Dashboard")
    broadcaster = EventStreamBroadcaster(manager.bus)
    broadcaster.start()
    active_connections: list[WebSocket] = []

    @app.websocket("/ws/stream")
    async def ws_stream(ws: WebSocket) -> None:
        await ws.accept()
        active_connections.append(ws)
        try:
            while True:
                msgs = broadcaster.drain()
                for msg in msgs:
                    await ws.send_text(json.dumps(msg))
                await asyncio.sleep(0.1)
        except WebSocketDisconnect:
            active_connections.remove(ws)

    @app.get("/api/status")
    async def get_status():
        return {
            "runtime_mode": manager.state.runtime_mode,
            "components": {
                name: manager.state.get_component_state(name)
                for name in manager.registry.components
            },
        }

    if STATIC_DIR.exists():
        app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")

    return app


def start_server(manager: RuntimeManager, host: str = "127.0.0.1", port: int = 7799) -> None:
    app = build_app(manager)
    uvicorn.run(app, host=host, port=port, log_level="warning")
```

- [ ] **Step 4: Run test to verify it passes**

```
python -m pytest tests/ui/test_websocket_stream.py -v
```

Expected: 1 test PASS

- [ ] **Step 5: Commit**

```
rtk git add Skynet/ui/ tests/ui/
rtk git commit -m "feat(ui): FastAPI server + EventBus WebSocket stream"
```

---

### Task 10: Dashboard HTML + modular JS

**Files:**
- Create: `Skynet/ui/static/index.html`
- Create: `Skynet/ui/static/js/api.js`
- Create: `Skynet/ui/static/js/websocket.js`
- Create: `Skynet/ui/static/js/dashboard.js`
- Create: `Skynet/ui/static/js/runtime.js`

- [ ] **Step 1: Create index.html**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Nexux</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    :root {
      --bg: #0a0a0f;
      --surface: #12121a;
      --border: #1e1e2e;
      --accent: #7c3aed;
      --accent-dim: rgba(124, 58, 237, 0.15);
      --text: #e2e8f0;
      --text-dim: #64748b;
      --green: #22c55e;
      --yellow: #eab308;
      --red: #ef4444;
      --blue: #3b82f6;
    }
    body { background: var(--bg); color: var(--text); font-family: 'JetBrains Mono', monospace; font-size: 13px; }
    header { display: flex; align-items: center; justify-content: space-between; padding: 16px 24px; border-bottom: 1px solid var(--border); }
    .logo { font-size: 18px; font-weight: 700; letter-spacing: 0.05em; color: var(--accent); }
    .runtime-badge { padding: 4px 12px; border-radius: 4px; font-size: 11px; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; background: var(--surface); border: 1px solid var(--border); }
    .runtime-badge[data-mode="active"] { border-color: var(--green); color: var(--green); }
    .runtime-badge[data-mode="degraded"] { border-color: var(--yellow); color: var(--yellow); }
    .runtime-badge[data-mode="shutdown"] { border-color: var(--red); color: var(--red); }
    main { padding: 24px; display: flex; flex-direction: column; gap: 24px; }
    .section-label { font-size: 11px; letter-spacing: 0.1em; text-transform: uppercase; color: var(--text-dim); margin-bottom: 12px; }
    .hardware-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
    .hw-card { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 16px; }
    .hw-label { font-size: 11px; color: var(--text-dim); margin-bottom: 6px; }
    .hw-value { font-size: 20px; font-weight: 700; }
    .hw-sub { font-size: 11px; color: var(--text-dim); margin-top: 4px; }
    .components-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
    .comp-card { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 16px; }
    .comp-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
    .comp-name { font-weight: 600; }
    .comp-state { font-size: 11px; font-weight: 600; padding: 3px 8px; border-radius: 3px; text-transform: uppercase; }
    .comp-state[data-state="idle"]     { background: rgba(34,197,94,0.15); color: var(--green); }
    .comp-state[data-state="busy"]     { background: rgba(59,130,246,0.15); color: var(--blue); }
    .comp-state[data-state="starting"] { background: rgba(234,179,8,0.15); color: var(--yellow); }
    .comp-state[data-state="degraded"] { background: rgba(234,179,8,0.15); color: var(--yellow); }
    .comp-state[data-state="failed"]   { background: rgba(239,68,68,0.15); color: var(--red); }
    .comp-state[data-state="offline"]  { background: rgba(100,116,139,0.15); color: var(--text-dim); }
    .controls { display: flex; gap: 12px; }
    .btn { padding: 10px 24px; border-radius: 6px; border: none; cursor: pointer; font-family: inherit; font-size: 13px; font-weight: 600; letter-spacing: 0.03em; }
    .btn-primary { background: var(--accent); color: #fff; }
    .btn-primary:hover { background: #6d28d9; }
    .btn-secondary { background: var(--surface); color: var(--text); border: 1px solid var(--border); }
    .btn-secondary:hover { border-color: var(--accent); color: var(--accent); }
  </style>
</head>
<body>
  <header>
    <span class="logo">NEXUX</span>
    <span class="runtime-badge" id="runtime-badge" data-mode="idle">IDLE</span>
  </header>
  <main>
    <section>
      <div class="section-label">System</div>
      <div class="hardware-row" id="hardware-row"></div>
    </section>
    <section>
      <div class="section-label">Components</div>
      <div class="components-grid" id="components-grid"></div>
    </section>
    <section>
      <div class="controls">
        <button class="btn btn-primary" id="btn-initialize">Initialize Nexux</button>
        <button class="btn btn-secondary" id="btn-shutdown">Shutdown</button>
      </div>
    </section>
  </main>
  <script src="/js/api.js"></script>
  <script src="/js/websocket.js"></script>
  <script src="/js/dashboard.js"></script>
  <script src="/js/runtime.js"></script>
</body>
</html>
```

- [ ] **Step 2: Create api.js — all fetch() calls**

```javascript
// Skynet/ui/static/js/api.js
const Api = {
  async getStatus() {
    const res = await fetch('/api/status');
    if (!res.ok) throw new Error('status fetch failed');
    return res.json();
  },

  async initialize() {
    const res = await fetch('/api/runtime/initialize', { method: 'POST' });
    if (!res.ok) throw new Error('initialize failed');
    return res.json();
  },

  async shutdown() {
    const res = await fetch('/api/runtime/shutdown', { method: 'POST' });
    if (!res.ok) throw new Error('shutdown failed');
    return res.json();
  },

  async getHardware() {
    const res = await fetch('/api/hardware');
    if (!res.ok) throw new Error('hardware fetch failed');
    return res.json();
  },
};
```

- [ ] **Step 3: Create websocket.js — WS + reconnect**

```javascript
// Skynet/ui/static/js/websocket.js
const WS = (() => {
  let socket = null;
  let handlers = {};
  let retryDelay = 1000;

  function connect() {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    socket = new WebSocket(`${proto}://${location.host}/ws/stream`);

    socket.onmessage = (ev) => {
      let msg;
      try { msg = JSON.parse(ev.data); } catch { return; }
      const fn = handlers[msg.type];
      if (fn) fn(msg);
    };

    socket.onclose = () => {
      setTimeout(() => { retryDelay = Math.min(retryDelay * 2, 16000); connect(); }, retryDelay);
    };

    socket.onopen = () => { retryDelay = 1000; };
  }

  return {
    on(type, fn) { handlers[type] = fn; },
    start() { connect(); },
  };
})();
```

- [ ] **Step 4: Create dashboard.js — card rendering without innerHTML**

```javascript
// Skynet/ui/static/js/dashboard.js
const Dashboard = (() => {
  const componentCards = {};

  function makeHwCard(label, valueId, sub) {
    const card = document.createElement('div');
    card.className = 'hw-card';

    const labelEl = document.createElement('div');
    labelEl.className = 'hw-label';
    labelEl.textContent = label;

    const valueEl = document.createElement('div');
    valueEl.className = 'hw-value';
    valueEl.id = valueId;
    valueEl.textContent = '—';

    card.appendChild(labelEl);
    card.appendChild(valueEl);

    if (sub) {
      const subEl = document.createElement('div');
      subEl.className = 'hw-sub';
      subEl.textContent = sub;
      card.appendChild(subEl);
    }

    return card;
  }

  function makeCompCard(name) {
    const card = document.createElement('div');
    card.className = 'comp-card';

    const header = document.createElement('div');
    header.className = 'comp-header';

    const nameEl = document.createElement('span');
    nameEl.className = 'comp-name';
    nameEl.textContent = name.replace(/_/g, ' ').toUpperCase();

    const stateEl = document.createElement('span');
    stateEl.className = 'comp-state';
    stateEl.dataset.state = 'offline';
    stateEl.textContent = 'OFFLINE';

    header.appendChild(nameEl);
    header.appendChild(stateEl);
    card.appendChild(header);

    componentCards[name] = stateEl;
    return card;
  }

  function initHardwareRow() {
    const row = document.getElementById('hardware-row');
    if (!row) return;
    row.appendChild(makeHwCard('CPU', 'hw-cpu', null));
    row.appendChild(makeHwCard('RAM', 'hw-ram', null));
    row.appendChild(makeHwCard('MIC', 'hw-mic', null));
    row.appendChild(makeHwCard('AUDIO OUT', 'hw-audio', null));
  }

  function initComponentCards(componentNames) {
    const grid = document.getElementById('components-grid');
    if (!grid) return;
    componentNames.forEach((name) => grid.appendChild(makeCompCard(name)));
  }

  function updateComponentState(component, state) {
    const el = componentCards[component];
    if (!el) return;
    el.dataset.state = state;
    el.textContent = state.toUpperCase();
  }

  function updateRuntimeBadge(mode) {
    const badge = document.getElementById('runtime-badge');
    if (!badge) return;
    badge.dataset.mode = mode;
    badge.textContent = mode.toUpperCase();
  }

  function updateHw(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
  }

  async function loadInitialStatus() {
    try {
      const status = await Api.getStatus();
      updateRuntimeBadge(status.runtime_mode);
      const names = Object.keys(status.components);
      initComponentCards(names);
      names.forEach((n) => updateComponentState(n, status.components[n]));
    } catch (e) {
      console.error('Failed to load status:', e);
    }
  }

  function wireWebSocket() {
    WS.on('component_state', (msg) => updateComponentState(msg.component, msg.current));
    WS.on('runtime_mode', (msg) => updateRuntimeBadge(msg.current));
  }

  function init() {
    initHardwareRow();
    wireWebSocket();
    WS.start();
    loadInitialStatus();
  }

  return { init, updateComponentState, updateRuntimeBadge, updateHw };
})();

document.addEventListener('DOMContentLoaded', () => Dashboard.init());
```

- [ ] **Step 5: Create runtime.js — initialize/shutdown buttons**

```javascript
// Skynet/ui/static/js/runtime.js
document.addEventListener('DOMContentLoaded', () => {
  const btnInit = document.getElementById('btn-initialize');
  const btnShutdown = document.getElementById('btn-shutdown');

  if (btnInit) {
    btnInit.addEventListener('click', async () => {
      btnInit.disabled = true;
      try {
        await Api.initialize();
      } catch (e) {
        console.error('Initialize failed:', e);
        btnInit.disabled = false;
      }
    });
  }

  if (btnShutdown) {
    btnShutdown.addEventListener('click', async () => {
      btnShutdown.disabled = true;
      try {
        await Api.shutdown();
      } catch (e) {
        console.error('Shutdown failed:', e);
        btnShutdown.disabled = false;
      }
    });
  }
});
```

- [ ] **Step 6: Add runtime routes to server.py**

Add to `Skynet/ui/server.py` inside `build_app()`:

```python
    @app.post("/api/runtime/initialize")
    async def api_initialize():
        asyncio.create_task(manager.initialize())
        return {"status": "initializing"}

    @app.post("/api/runtime/shutdown")
    async def api_shutdown():
        asyncio.create_task(manager.shutdown())
        return {"status": "shutting_down"}
```

- [ ] **Step 7: Create static directory structure and commit**

```
mkdir Skynet\ui\static\js
```

```
rtk git add Skynet/ui/static/ Skynet/ui/server.py
rtk git commit -m "feat(ui): dashboard HTML + modular JS — safe DOM construction, no innerHTML"
```

---

### Task 11: API routes (settings, hardware, status, models)

**Files:**
- Create: `Skynet/ui/routes/__init__.py`
- Create: `Skynet/ui/routes/settings.py`
- Create: `Skynet/ui/routes/hardware.py`
- Create: `Skynet/ui/routes/status.py`
- Create: `Skynet/ui/routes/models.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/ui/test_routes.py
import pytest
from fastapi.testclient import TestClient
from Skynet.core.runtime_manager import RuntimeManager
from Skynet.ui.server import build_app


@pytest.fixture
def client(tmp_path):
    import yaml
    settings_file = tmp_path / "settings.yaml"
    settings_file.write_text(yaml.dump({
        "stt": {"backend": "whisper", "model": "base", "enabled": True},
        "llm1": {"backend": "ollama", "model": "llama3.2", "enabled": True},
        "llm2": {"backend": None, "enabled": False},
        "tts": {"backend": "pyttsx3", "enabled": True},
        "memory": {"enabled": False},
    }))
    manager = RuntimeManager()
    app = build_app(manager)
    return TestClient(app), str(settings_file)


def test_get_status(client):
    c, _ = client
    r = c.get("/api/status")
    assert r.status_code == 200
    data = r.json()
    assert "runtime_mode" in data
    assert "components" in data
```

- [ ] **Step 2: Run test to verify it passes (status route already exists)**

```
python -m pytest tests/ui/test_routes.py::test_get_status -v
```

Expected: PASS

- [ ] **Step 3: Create settings route**

```python
# Skynet/ui/routes/settings.py
from __future__ import annotations

from pathlib import Path

import yaml
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/settings", tags=["settings"])
_SETTINGS_PATH = Path("config/settings.yaml")


@router.get("")
def get_settings():
    if not _SETTINGS_PATH.exists():
        raise HTTPException(status_code=404, detail="settings.yaml not found")
    with open(_SETTINGS_PATH) as f:
        return yaml.safe_load(f)


@router.post("")
def save_settings(data: dict):
    _SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_SETTINGS_PATH, "w") as f:
        yaml.dump(data, f, default_flow_style=False)
    return {"status": "saved"}
```

- [ ] **Step 4: Create hardware route**

```python
# Skynet/ui/routes/hardware.py
from __future__ import annotations

import platform

import psutil
from fastapi import APIRouter

router = APIRouter(prefix="/api/hardware", tags=["hardware"])


@router.get("")
def get_hardware():
    mem = psutil.virtual_memory()
    cpu = psutil.cpu_percent(interval=0.1)
    return {
        "cpu_percent": cpu,
        "ram_total_gb": round(mem.total / (1024 ** 3), 1),
        "ram_used_gb": round(mem.used / (1024 ** 3), 1),
        "ram_percent": mem.percent,
        "platform": platform.system(),
    }
```

- [ ] **Step 5: Create status route (component connectivity checks)**

```python
# Skynet/ui/routes/status.py
from __future__ import annotations

import requests
from fastapi import APIRouter

router = APIRouter(prefix="/api/component-status", tags=["status"])


@router.get("")
def get_component_status():
    ollama_ok = False
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=2)
        ollama_ok = r.status_code == 200
    except Exception:
        pass

    return {
        "ollama": "reachable" if ollama_ok else "unreachable",
    }
```

- [ ] **Step 6: Create models route**

```python
# Skynet/ui/routes/models.py
from __future__ import annotations

import requests
from fastapi import APIRouter

router = APIRouter(prefix="/api/models", tags=["models"])


@router.get("")
def list_ollama_models():
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=3)
        if r.status_code == 200:
            data = r.json()
            return {"models": [m["name"] for m in data.get("models", [])]}
    except Exception:
        pass
    return {"models": []}
```

- [ ] **Step 7: Register routes in server.py**

Update `build_app()` in `Skynet/ui/server.py` to include:

```python
    from Skynet.ui.routes import settings, hardware, status, models
    app.include_router(settings.router)
    app.include_router(hardware.router)
    app.include_router(status.router)
    app.include_router(models.router)
```

- [ ] **Step 8: Run all UI tests**

```
python -m pytest tests/ui/ -v
```

Expected: all tests PASS

- [ ] **Step 9: Commit**

```
rtk git add Skynet/ui/routes/ Skynet/ui/server.py tests/ui/
rtk git commit -m "feat(ui): settings, hardware, status, models API routes"
```

---

## Group 7: Voice + AI

### Task 12: STT adapted to Component ABC

**Files:**
- Modify: `Skynet/voice/stt.py`
- Create: `tests/voice/test_stt_component.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/voice/test_stt_component.py
import asyncio
import pytest
from unittest.mock import patch, MagicMock
from Skynet.voice.stt import STTComponent
from Skynet.core.runtime_state import ComponentState
from Skynet.core.event_bus import EventBus
from Skynet.core.events import STTTranscribedEvent


@pytest.fixture
def bus():
    return EventBus()


@pytest.mark.asyncio
async def test_stt_starts_and_reaches_idle(bus):
    with patch("Skynet.voice.stt.WhisperModel") as MockModel:
        MockModel.return_value = MagicMock()
        stt = STTComponent(bus=bus, model_name="base")
        await stt.start()
        assert stt.health() == ComponentState.IDLE
        await stt.stop()


@pytest.mark.asyncio
async def test_stt_emits_transcribed_event(bus):
    received = []
    bus.subscribe(STTTranscribedEvent, received.append)

    mock_model = MagicMock()
    mock_seg = MagicMock()
    mock_seg.text = "hello"
    mock_model.transcribe.return_value = ([mock_seg], None)

    with patch("Skynet.voice.stt.WhisperModel", return_value=mock_model):
        stt = STTComponent(bus=bus, model_name="base")
        await stt.start()
        stt._emit_transcript("hello")
        assert len(received) == 1
        assert received[0].transcript == "hello"
        await stt.stop()
```

- [ ] **Step 2: Run test to verify it fails**

```
python -m pytest tests/voice/test_stt_component.py -v
```

Expected: `ImportError` (STTComponent not defined yet)

- [ ] **Step 3: Rewrite Skynet/voice/stt.py**

```python
# Skynet/voice/stt.py
from __future__ import annotations

import logging
import os
import tempfile
import wave
from typing import TYPE_CHECKING

import pyaudio
from faster_whisper import WhisperModel

if TYPE_CHECKING:
    from Skynet.core.event_bus import EventBus

from Skynet.core.component import Component
from Skynet.core.events import STTTranscribedEvent
from Skynet.core.runtime_state import ComponentState

logger = logging.getLogger(__name__)

_RATE = 16000
_CHANNELS = 1
_CHUNK = 1024
_FORMAT = pyaudio.paInt16
_SILENCE_DB = 500
_SILENCE_S = 1.5


class STTComponent(Component):
    def __init__(self, *, bus: EventBus, model_name: str = "base") -> None:
        super().__init__(name="stt")
        self._bus = bus
        self._model_name = model_name
        self._model: WhisperModel | None = None
        self._health = ComponentState.OFFLINE

    async def start(self) -> None:
        self._model = WhisperModel(self._model_name, device="cpu", compute_type="int8")
        self._health = ComponentState.IDLE

    async def stop(self) -> None:
        self._model = None
        self._health = ComponentState.OFFLINE

    def health(self) -> ComponentState:
        return self._health

    def _emit_transcript(self, text: str) -> None:
        self._bus.publish(STTTranscribedEvent(transcript=text))

    def listen_and_emit(self) -> None:
        audio_bytes = self._listen()
        if not audio_bytes:
            return
        text = self._transcribe(audio_bytes)
        if text:
            self._emit_transcript(text)

    def _listen(self) -> bytes:
        audio = pyaudio.PyAudio()
        stream = audio.open(
            format=_FORMAT, channels=_CHANNELS, rate=_RATE,
            input=True, frames_per_buffer=_CHUNK,
        )
        frames = []
        silent_chunks = 0
        silence_limit = int(_SILENCE_S * _RATE / _CHUNK)
        recording = False
        try:
            while True:
                data = stream.read(_CHUNK, exception_on_overflow=False)
                amplitude = max(
                    abs(int.from_bytes(data[i:i+2], "little", signed=True))
                    for i in range(0, len(data), 2)
                )
                if amplitude > _SILENCE_DB:
                    recording = True
                    silent_chunks = 0
                    frames.append(data)
                elif recording:
                    frames.append(data)
                    silent_chunks += 1
                    if silent_chunks >= silence_limit:
                        break
        finally:
            stream.stop_stream()
            stream.close()
            audio.terminate()
        return b"".join(frames)

    def _transcribe(self, audio_bytes: bytes) -> str:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            tmp = f.name
            _write_wav(tmp, audio_bytes)
        try:
            segments, _ = self._model.transcribe(tmp, language="en")
            return " ".join(s.text.strip() for s in segments).strip()
        finally:
            os.unlink(tmp)


def _write_wav(path: str, pcm: bytes) -> None:
    with wave.open(path, "wb") as wf:
        wf.setnchannels(_CHANNELS)
        wf.setsampwidth(2)
        wf.setframerate(_RATE)
        wf.writeframes(pcm)
```

- [ ] **Step 4: Run test to verify it passes**

```
python -m pytest tests/voice/test_stt_component.py -v
```

Expected: all 2 tests PASS

- [ ] **Step 5: Commit**

```
rtk git add Skynet/voice/stt.py tests/voice/test_stt_component.py
rtk git commit -m "feat(voice): STT adapted to Component ABC — emits STTTranscribedEvent"
```

---

### Task 13: TTS component

**Files:**
- Create: `Skynet/voice/tts.py`
- Create: `tests/voice/test_tts_component.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/voice/test_tts_component.py
import asyncio
import pytest
from unittest.mock import patch, MagicMock
from Skynet.voice.tts import TTSComponent
from Skynet.core.runtime_state import ComponentState
from Skynet.core.event_bus import EventBus
from Skynet.core.events import OrchestratorResponseEvent


@pytest.fixture
def bus():
    return EventBus()


@pytest.mark.asyncio
async def test_tts_starts_and_reaches_idle(bus):
    with patch("Skynet.voice.tts.pyttsx3") as mock_tts:
        mock_engine = MagicMock()
        mock_tts.init.return_value = mock_engine
        tts = TTSComponent(bus=bus)
        await tts.start()
        assert tts.health() == ComponentState.IDLE
        await tts.stop()


@pytest.mark.asyncio
async def test_tts_speaks_on_orchestrator_event(bus):
    with patch("Skynet.voice.tts.pyttsx3") as mock_tts:
        mock_engine = MagicMock()
        mock_tts.init.return_value = mock_engine
        tts = TTSComponent(bus=bus)
        await tts.start()
        bus.publish(OrchestratorResponseEvent(response="Hello there"))
        await asyncio.sleep(0.01)
        mock_engine.say.assert_called_once_with("Hello there")
        await tts.stop()
```

- [ ] **Step 2: Run test to verify it fails**

```
python -m pytest tests/voice/test_tts_component.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Implement TTSComponent**

```python
# Skynet/voice/tts.py
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pyttsx3

if TYPE_CHECKING:
    from Skynet.core.event_bus import EventBus

from Skynet.core.component import Component
from Skynet.core.events import OrchestratorResponseEvent
from Skynet.core.runtime_state import ComponentState

logger = logging.getLogger(__name__)


class TTSComponent(Component):
    def __init__(self, *, bus: EventBus) -> None:
        super().__init__(name="tts")
        self._bus = bus
        self._engine = None
        self._health = ComponentState.OFFLINE
        self._token: str | None = None

    async def start(self) -> None:
        self._engine = pyttsx3.init()
        self._token = self._bus.subscribe(OrchestratorResponseEvent, self._on_response)
        self._health = ComponentState.IDLE

    async def stop(self) -> None:
        if self._token:
            self._bus.unsubscribe(self._token)
            self._token = None
        self._engine = None
        self._health = ComponentState.OFFLINE

    def health(self) -> ComponentState:
        return self._health

    def _on_response(self, event: OrchestratorResponseEvent) -> None:
        if self._engine and event.response:
            try:
                self._engine.say(event.response)
                self._engine.runAndWait()
            except Exception:
                logger.exception("TTS failed to speak")
```

- [ ] **Step 4: Run test to verify it passes**

```
python -m pytest tests/voice/test_tts_component.py -v
```

Expected: all 2 tests PASS

- [ ] **Step 5: Commit**

```
rtk git add Skynet/voice/tts.py tests/voice/test_tts_component.py
rtk git commit -m "feat(voice): TTSComponent — subscribes to OrchestratorResponseEvent, speaks on event"
```

---

### Task 14: orchestrator.py + TaskRouter (rename brain.py)

**Files:**
- Create: `Skynet/core/orchestrator.py`
- Create: `Skynet/task/__init__.py`
- Create: `Skynet/task/task_router.py`
- Create: `Skynet/task/workflow_executor.py`
- Create: `tests/core/test_orchestrator.py`
- Delete: `Skynet/core/brain.py` (if it exists)

- [ ] **Step 1: Write the failing test**

```python
# tests/core/test_orchestrator.py
import asyncio
import pytest
from unittest.mock import MagicMock, patch
from Skynet.core.orchestrator import Orchestrator
from Skynet.core.runtime_state import ComponentState
from Skynet.core.event_bus import EventBus
from Skynet.core.events import STTTranscribedEvent, OrchestratorResponseEvent


@pytest.fixture
def bus():
    return EventBus()


@pytest.fixture
def mock_provider():
    p = MagicMock()
    p.complete.return_value = "I can help with that."
    return p


@pytest.mark.asyncio
async def test_orchestrator_starts_and_reaches_idle(bus, mock_provider):
    orc = Orchestrator(bus=bus, provider=mock_provider)
    await orc.start()
    assert orc.health() == ComponentState.IDLE
    await orc.stop()


@pytest.mark.asyncio
async def test_orchestrator_responds_to_stt_event(bus, mock_provider):
    responses = []
    bus.subscribe(OrchestratorResponseEvent, responses.append)

    orc = Orchestrator(bus=bus, provider=mock_provider)
    await orc.start()
    bus.publish(STTTranscribedEvent(transcript="what can you do?"))
    await asyncio.sleep(0.05)
    await orc.stop()

    assert len(responses) == 1
    assert responses[0].response == "I can help with that."


@pytest.mark.asyncio
async def test_rolling_window_limits_context(bus, mock_provider):
    orc = Orchestrator(bus=bus, provider=mock_provider)
    await orc.start()

    for i in range(5):
        bus.publish(STTTranscribedEvent(transcript=f"turn {i}"))
        await asyncio.sleep(0.05)

    # After 5 turns, only last 3 turns (6 messages) should be in context
    last_call_msgs = mock_provider.complete.call_args[0][0]
    user_msgs = [m for m in last_call_msgs if m["role"] == "user"]
    assert len(user_msgs) <= 3, f"Expected ≤3 user msgs in context, got {len(user_msgs)}"

    # Turn 0 transcript must NOT be in context
    content_texts = [m["content"] for m in last_call_msgs]
    assert not any("turn 0" in t for t in content_texts)

    await orc.stop()
```

- [ ] **Step 2: Run test to verify it fails**

```
python -m pytest tests/core/test_orchestrator.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Create TaskRouter and WorkflowExecutor stubs**

```python
# Skynet/task/task_router.py
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class TaskRouter:
    """V0.1: passthrough — all intents go to Orchestrator directly."""

    def route(self, transcript: str) -> str:
        return transcript
```

```python
# Skynet/task/workflow_executor.py
from __future__ import annotations


class WorkflowExecutor:
    """Stub V0.1 — interface exists, does nothing."""

    async def execute(self, workflow_id: str, context: dict) -> None:
        pass
```

- [ ] **Step 4: Create orchestrator.py**

```python
# Skynet/core/orchestrator.py
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from Skynet.core.event_bus import EventBus
    from Skynet.providers.base import LLMProvider

from Skynet.core.component import Component
from Skynet.core.events import OrchestratorResponseEvent, STTTranscribedEvent
from Skynet.core.runtime_state import ComponentState
from Skynet.task.task_router import TaskRouter

logger = logging.getLogger(__name__)

_WINDOW = 3  # rolling turns
_SYSTEM_PROMPT = (
    "You are Nexux, a persistent desktop AI companion. "
    "Be concise, direct, and helpful."
)


class Orchestrator(Component):
    def __init__(self, *, bus: EventBus, provider: LLMProvider) -> None:
        super().__init__(name="orchestrator")
        self._bus = bus
        self._provider = provider
        self._router = TaskRouter()
        self._history: list[tuple[str, str]] = []  # (user, assistant) pairs
        self._health = ComponentState.OFFLINE
        self._token: str | None = None

    async def start(self) -> None:
        self._token = self._bus.subscribe(STTTranscribedEvent, self._on_stt)
        self._health = ComponentState.IDLE

    async def stop(self) -> None:
        if self._token:
            self._bus.unsubscribe(self._token)
            self._token = None
        self._health = ComponentState.OFFLINE

    def health(self) -> ComponentState:
        return self._health

    def _on_stt(self, event: STTTranscribedEvent) -> None:
        asyncio.create_task(self._handle(event.transcript))

    async def _handle(self, transcript: str) -> None:
        self._health = ComponentState.BUSY
        try:
            routed = self._router.route(transcript)
            messages = self._build_messages(routed)
            response = self._provider.complete(messages)
            self._history.append((transcript, response))
            self._bus.publish(OrchestratorResponseEvent(response=response))
        except Exception:
            logger.exception("Orchestrator failed to handle transcript")
        finally:
            self._health = ComponentState.IDLE

    def _build_messages(self, transcript: str) -> list[dict]:
        msgs: list[dict] = [{"role": "system", "content": _SYSTEM_PROMPT}]
        for user_text, asst_text in self._history[-_WINDOW:]:
            msgs.append({"role": "user", "content": user_text})
            msgs.append({"role": "assistant", "content": asst_text})
        msgs.append({"role": "user", "content": transcript})
        return msgs
```

- [ ] **Step 5: Delete brain.py if it exists**

```
if (Test-Path Skynet\core\brain.py) { Remove-Item Skynet\core\brain.py }
```

- [ ] **Step 6: Run test to verify it passes**

```
python -m pytest tests/core/test_orchestrator.py -v
```

Expected: all 3 tests PASS

- [ ] **Step 7: Commit**

```
rtk git add Skynet/core/orchestrator.py Skynet/task/ tests/core/test_orchestrator.py
rtk git commit -m "feat(core): Orchestrator + TaskRouter — rolling window context, brain.py removed"
```

---

### Task 15: main.py — thin launcher

**Files:**
- Modify: `Skynet/main.py`

- [ ] **Step 1: Write the test**

```python
# tests/test_main_boot.py
import subprocess
import sys
import time
import requests


def test_dashboard_boots_and_responds():
    proc = subprocess.Popen(
        [sys.executable, "-m", "Skynet.main"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    time.sleep(3)
    try:
        r = requests.get("http://127.0.0.1:7799/api/status", timeout=3)
        assert r.status_code == 200
        data = r.json()
        assert "runtime_mode" in data
    finally:
        proc.terminate()
        proc.wait(timeout=5)
```

- [ ] **Step 2: Run test to verify it fails**

```
python -m pytest tests/test_main_boot.py -v
```

Expected: connection refused or import error

- [ ] **Step 3: Rewrite main.py**

```python
# Skynet/main.py
"""
Nexux runtime entry point.
Three responsibilities only:
  1. Load config
  2. Create and wire RuntimeManager
  3. Start UI server (blocks)
"""
from __future__ import annotations

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s — %(message)s")

from Skynet.core.config import load_config
from Skynet.core.runtime_manager import RuntimeManager
from Skynet.core.orchestrator import Orchestrator
from Skynet.voice.stt import STTComponent
from Skynet.voice.tts import TTSComponent
from Skynet.providers.registry import get_provider
from Skynet.ui.server import start_server


def main() -> None:
    cfg = load_config()

    manager = RuntimeManager()

    # Wire components — dependency order matches registry
    stt = STTComponent(bus=manager.bus, model_name=cfg["stt"]["model"])
    tts = TTSComponent(bus=manager.bus)
    provider = get_provider("llm1", cfg)
    orc = Orchestrator(bus=manager.bus, provider=provider)

    manager.register("audio_device", stt, deps=[])
    manager.register("tts", tts, deps=["audio_device"])
    manager.register("llm1_provider", orc, deps=[])

    start_server(manager, host="127.0.0.1", port=7799)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

```
python -m pytest tests/test_main_boot.py -v
```

Expected: PASS — dashboard responds at localhost:7799

- [ ] **Step 5: Verify dashboard loads in browser**

Open `http://localhost:7799` and confirm:
- Dashboard renders
- Runtime badge shows `IDLE`
- Component cards visible
- No JS errors in console

- [ ] **Step 6: Commit**

```
rtk git add Skynet/main.py tests/test_main_boot.py
rtk git commit -m "feat: main.py — thin launcher wiring config + manager + UI server"
```

---

### Task 16: Full pipeline test — 5 turns + rolling window

**Files:**
- Create: `tests/test_full_pipeline.py`

- [ ] **Step 1: Write the test**

```python
# tests/test_full_pipeline.py
import asyncio
import pytest
from unittest.mock import MagicMock, patch
from Skynet.core.runtime_manager import RuntimeManager
from Skynet.core.orchestrator import Orchestrator
from Skynet.core.events import STTTranscribedEvent, OrchestratorResponseEvent
from Skynet.core.runtime_state import RuntimeMode


@pytest.mark.asyncio
async def test_five_turns_without_crash():
    manager = RuntimeManager()

    mock_provider = MagicMock()
    mock_provider.complete.return_value = "acknowledged"

    orc = Orchestrator(bus=manager.bus, provider=mock_provider)
    manager.register("orchestrator", orc, deps=[])

    responses = []
    manager.bus.subscribe(OrchestratorResponseEvent, responses.append)

    await manager.initialize()

    for i in range(5):
        manager.bus.publish(STTTranscribedEvent(transcript=f"user turn {i}"))
        await asyncio.sleep(0.05)

    await manager.shutdown()

    assert len(responses) == 5
    assert manager.state.runtime_mode == RuntimeMode.SHUTDOWN


@pytest.mark.asyncio
async def test_turn_5_excludes_turn_1_from_context():
    manager = RuntimeManager()
    call_messages = []

    def capture_complete(msgs):
        call_messages.append(msgs)
        return "ok"

    mock_provider = MagicMock()
    mock_provider.complete.side_effect = capture_complete

    orc = Orchestrator(bus=manager.bus, provider=mock_provider)
    manager.register("orchestrator", orc, deps=[])

    await manager.initialize()

    for i in range(5):
        manager.bus.publish(STTTranscribedEvent(transcript=f"turn {i}"))
        await asyncio.sleep(0.05)

    await manager.shutdown()

    # Check the 5th call's messages
    fifth_call = call_messages[4]
    user_contents = [m["content"] for m in fifth_call if m["role"] == "user"]
    assert not any("turn 0" in c for c in user_contents), (
        "Turn 0 must NOT appear in turn 5 context — rolling window violated"
    )
    assert not any("turn 1" in c for c in user_contents), (
        "Turn 1 must NOT appear in turn 5 context — rolling window violated"
    )
```

- [ ] **Step 2: Run test to verify it passes**

```
python -m pytest tests/test_full_pipeline.py -v
```

Expected: both tests PASS

- [ ] **Step 3: Run full test suite**

```
python -m pytest tests/ -v
```

Expected: all tests PASS

- [ ] **Step 4: Final commit**

```
rtk git add tests/test_full_pipeline.py
rtk git commit -m "test: full pipeline — 5 turns without crash + rolling window assertion"
```

---

## Done When

- [ ] `python -m Skynet.main` starts and opens `localhost:7799`
- [ ] Dashboard renders with real data from `settings.yaml`
- [ ] Component cards show real connectivity status
- [ ] Hardware row shows real CPU, RAM readings
- [ ] WebSocket streams live component state changes
- [ ] "Initialize Nexux" button triggers runtime initialization
- [ ] Voice in → STT → Orchestrator → LLM1 → TTS → Voice out
- [ ] 5 turns without crash
- [ ] Turn 5 does NOT include turns 1-2 in LLM1 context (rolling window)
- [ ] Ollama going down → dashboard card flips to UNREACHABLE without page refresh

---

## Self-Review

**Spec coverage check:**
- EventBus typed pub/sub ✓ Task 1–2
- RuntimeState transition methods, no direct mutation ✓ Task 3
- Component ABC ✓ Task 4
- ComponentRegistry dependency graph + cascade ✓ Task 5
- BackgroundRunner with TaskPriority/TaskType ✓ Task 6
- RuntimeManager lifecycle coordination only, boundary test ✓ Task 7
- FakeComponent architecture verification ✓ Task 8
- WebSocket stream ✓ Task 9
- Dashboard HTML + modular JS ✓ Task 10
- Settings/hardware/status/models routes ✓ Task 11
- STT Component ABC ✓ Task 12
- TTS Component ✓ Task 13
- Orchestrator + TaskRouter + brain.py deletion ✓ Task 14
- main.py thin launcher ✓ Task 15
- 5-turn + rolling window test ✓ Task 16

**Placeholder scan:** None found. All steps contain actual code.

**Type consistency:** `ComponentState`, `RuntimeMode`, `BaseEvent` used consistently throughout. `EventBus.subscribe()` returns `SubscriptionToken` (str) used in `unsubscribe()` calls. `Component.health()` returns `ComponentState` everywhere.
