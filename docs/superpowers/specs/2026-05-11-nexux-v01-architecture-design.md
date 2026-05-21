# Nexux V0.1 — Architecture Design Spec

**Date:** 2026-05-11  
**Status:** Approved for implementation  
**Scope:** Core runtime architecture + live dashboard UI

---

## What We Are Building

Nexux V0.1 cognitive core loop with a live web dashboard:

```
Voice in → STT → Orchestrator → LLM1 (via provider) → TTS → Voice out
```

Plus: a FastAPI-served dashboard (localhost:7799) with WebSocket streaming that shows real component status, allows settings configuration, and launches the runtime.

---

## The 3 Contracts

### Contract 1 — Component Lifecycle

Every runtime component (STT, TTS, Orchestrator, providers) implements this interface:

```python
class Component(ABC):
    @abstractmethod
    async def start(self) -> None: ...

    @abstractmethod
    async def stop(self) -> None: ...

    @abstractmethod
    def health(self) -> ComponentState: ...
```

- `start()` is async — components may need to load models, ping services
- `stop()` must be clean — no dangling threads, no open handles
- `health()` returns a `ComponentState`, not a boolean
- Components emit events via EventBus, never call other components directly

### Contract 2 — Event Contract

```python
@dataclass
class BaseEvent:
    timestamp: float = field(default_factory=time.time)
    sequence_id: int = field(default_factory=_next_seq)

# All events extend BaseEvent — no string-based events
# EventBus.publish(event: BaseEvent) is the only publish path
# Subscribers declare what they consume — no assumptions about who listens
```

Emitters do not know who subscribes. Subscribers do not know who emits.
EventBus is the only broker. Nothing else.

**V0.1 events (initial set):**
- `STTTranscribedEvent(transcript: str)`
- `OrchestratorResponseEvent(response: str)`
- `ComponentStateChangedEvent(component: str, previous: ComponentState, current: ComponentState)`
- `RuntimeModeChangedEvent(previous: RuntimeMode, current: RuntimeMode)`

### Contract 3 — State Transition Rules

**Runtime modes:**
```
idle → initializing → active
active → degraded
active → shutdown
degraded → active   (recovery)
degraded → shutdown
* → maintenance     (manual operator override only)
```

**Component states:**
```
offline → starting → idle
idle → busy → idle
idle → degraded
busy → degraded
degraded → idle     (recovery)
any → failed
failed → offline    (reset, requires explicit operator action)
```

**Rules:**
- State transitions ONLY via `runtime_state.set_runtime_mode()` and `runtime_state.set_component_state()`
- Direct mutation of state fields is forbidden
- Every transition logs: previous state, new state, timestamp, source
- Every transition emits the corresponding `*ChangedEvent` into EventBus

---

## Architecture

### Core Spine

```
main.py                     reads config, creates RuntimeManager, starts UI server
  ↓
RuntimeManager              lifecycle coordination ONLY — no cognition, no workflows
  ├── ComponentRegistry     dependency graph, cascaded state when dependencies fail
  ├── RuntimeState          state machine with transition methods, no direct mutation
  ├── EventBus              typed pub/sub — sequence IDs for ordering awareness
  └── BackgroundRunner      asyncio queue, tasks carry priority + type classification
```

### Cognitive Layer (separate from RuntimeManager)

```
Orchestrator (orchestrator.py)   renamed from brain.py
  ↓
TaskRouter                       V0.1: everything → Orchestrator → LLM1
  ↓
WorkflowExecutor                 stub V0.1 — interface exists, does nothing
  ↓
ToolInvocation                   stub V0.1
```

### UI Layer (transport only — no business logic)

```
FastAPI (ui/server.py)
  ├── REST routes             read/write settings, hardware info, model list
  ├── WebSocket /ws/stream    subscribes to EventBus, pushes live data to browser
  └── Static files            index.html + modular JS
```

FastAPI routes call `runtime_manager.*` methods only. Zero cognitive logic in routes.

### Component Dependency Graph (V0.1)

```
audio_device
  ├── stt
  └── tts
llm1_provider
  └── orchestrator
```

When a dependency fails → ComponentRegistry cascades state change to dependents.

---

## Folder Structure

```
Skynet/
  core/
    runtime_manager.py      lifecycle coordination only
    component_registry.py   dependency graph + cascaded state
    runtime_state.py        state machines, transition methods, event emission
    event_bus.py            typed pub/sub
    events.py               BaseEvent + all event dataclasses
    tasks.py                BackgroundRunner, TaskPriority, TaskType
    resource_manager.py     stub — interface only, does nothing V0.1
    orchestrator.py         cognitive flow (renamed from brain.py)
    config.py               exists
  task/
    task_router.py          routes intent → orchestrator (V0.1: passthrough)
    workflow_executor.py    stub V0.1
  ui/
    server.py               FastAPI app, transport only
    routes/
      settings.py           GET/POST settings.yaml
      hardware.py           mic, audio out, CPU, GPU, RAM
      status.py             component connectivity checks
      models.py             available Ollama models
    ws/
      stream.py             EventBus subscriber → WS push
    static/
      index.html            dashboard (adapted from approved design)
      js/
        api.js              all fetch() calls
        websocket.js        WS connection + reconnect
        dashboard.js        hardware row + component cards rendering
        runtime.js          initialize/shutdown actions
        components/         one file per card
  providers/                exists — OllamaProvider, ClaudeProvider, registry
  voice/                    exists — STT (stt.py)
```

---

## Known Risks (Logged, Not Solved Now)

| Risk | Status |
|------|--------|
| Event storm / explosion | Aware. Throttle if it appears. |
| Event ordering (async race) | Sequence IDs on BaseEvent. Good enough V0.1. |
| Orchestrator boundary creep | Strict: orchestrator calls TaskRouter only. |
| WorkflowExecutor underspecified | Intentional. Reality defines it. |
| State machine explosion (cross-state coordination) | Hierarchy discipline — runtime > component > task. |
| EventBus implicit coupling | Event contracts documented above. |
| Distributed consistency | We are local. V0.1 doesn't need distributed guarantees. |
| Resource management (VRAM) | ResourceManager stub exists. Interface ready. |

---

## Implementation Order (locked)

Build in this exact sequence. Do NOT reorder.

1. **EventBus** — core nervous system. Nothing else can work without it.
2. **RuntimeState** — state machine with transition methods. Without this debugging becomes hell.
3. **Component lifecycle base** — `Component` ABC: `start()` / `stop()` / `health()`
4. **RuntimeManager** — startup/shutdown ordering, coordinates components
5. **WebSocket stream** — observability early. Wire EventBus → WS. See system before adding AI.
6. **One fake component** — `FakeSTT` that returns hardcoded text. Test the full architecture WITHOUT real AI first. Confirm: events flow, state changes propagate to dashboard, WS streams correctly.
7. **STT + TTS integration** — only after runtime is verified working
8. **LLM provider integration** — last. Providers are the easiest part.

---

## Logged Future Concerns (do not implement now)

| # | Concern | When It Bites |
|---|---------|--------------|
| 1 | BackgroundRunner needs cancellation: cancel / interrupt / timeout / retry | First time STT or Ollama hangs |
| 2 | EventBus backpressure: buffered subscribers, dropped-event policy | When WS or logging becomes a slow subscriber |
| 3 | Graceful shutdown contract: what happens to active TTS / inference / queued tasks | First Ctrl+C during active inference |
| 4 | TaskRouter god-object risk: don't let it become orchestrator v2 | First time tools / memory / browser actions are added |
| 5 | Dashboard becomes core UX: operational debugger, workflow inspector, trust interface | V0.2 onwards |
| 6 | Recovery goals: Ollama disconnects → reconnect → state recovers | First resilience test |
| 7 | Orchestrator boundary discipline: memory / retries / permissions will want to move in | Every feature addition |

---

## What Is Explicitly Deferred

- LLM2 (memory manager)
- WorkflowExecutor (real implementation)
- ToolInvocation (browser, terminal, filesystem)
- Memory (ChromaDB, embeddings)
- Vision / OCR
- Permissions system
- Resource arbitration (VRAM tracking)
- Process isolation (workers in separate processes)
- Event filtering / throttling

---

## Done When

- `main.py` starts, opens `localhost:7799`
- Dashboard renders with real data from `settings.yaml`
- Component cards show real connectivity status (not hardcoded)
- Hardware row shows real mic, audio device, CPU, RAM
- LLM1 backend/model dropdown changes persist to `settings.yaml`
- WebSocket streams live: component state changes + hardware metrics
- "Initialize Nexux" button starts the runtime loop
- Voice in → STT → Orchestrator → LLM1 → TTS → Voice out
- 5 turns without crash
- Turn 5 does NOT include turns 1-2 in LLM1 context (rolling window)
- Ollama going down → dashboard card flips to UNREACHABLE without page refresh
