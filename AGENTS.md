# Nexux — Codex Configuration

## Project

**Nexux by Klyx** — persistent desktop AI operating companion (internal runtime: Skynet).

```
C:\Work\Nexux\
├── Skynet\           ← all runtime source code lives here
│   ├── core\         orchestrator, event bus, runtime loop
│   ├── voice\        STT (faster-whisper), TTS (VibeVoice)
│   ├── memory\       ChromaDB, embeddings, LLM2 compression
│   ├── skills\       browser_skill, excel_skill, pdf_skill, etc.
│   ├── vision\       OCR, screenshot analysis, UI detection
│   ├── providers\    LLM provider abstraction (Ollama, Codex, OpenRouter)
│   ├── tools\        terminal, filesystem, browser tools
│   ├── automation\   desktop + browser automation runtime
│   ├── permissions\  risk classifier, trust tiers, approval gate
│   ├── state\        workflow, task, session state machines
│   └── observability structured logging, event correlation
├── tests\            test suite
├── config\           config files (not code)
└── docs\             architecture specs (read-only reference)
```

**Stack**: Python, FastAPI, faster-whisper, ChromaDB, Ollama, Playwright  
**Spec docs**: `docs/` — read these before making architectural decisions

## Rules

- **ALWAYS brainstorm before coding** — if the user is talking about a feature or design, invoke the brainstorming skill FIRST. Do NOT start writing code while the user is still thinking out loud.
- Do what has been asked; nothing more, nothing less
- NEVER create files unless absolutely necessary — prefer editing existing files
- NEVER create documentation files unless explicitly requested
- NEVER save working files or tests to root — all code goes in `Skynet/`, tests in `tests/`
- ALWAYS read a file before editing it
- NEVER commit secrets, credentials, or .env files
- Keep files under 500 lines
- Validate input at system boundaries

## Architecture Decisions (locked — do not violate)

**Approved spec:** `docs/superpowers/specs/2026-05-11-nexux-v01-architecture-design.md`

### The 3 Contracts

**Component lifecycle** — every component implements:
```python
async def start(self) -> None
async def stop(self) -> None
def health(self) -> ComponentState
```

**Event contract** — all events extend `BaseEvent(timestamp, sequence_id)`. No string events. `EventBus.publish(event)` is the only publish path.

**State transitions** — only via `runtime_state.set_component_state()` and `runtime_state.set_runtime_mode()`. Direct field mutation is forbidden.

### Hard Boundaries

| Layer | Owns | Never |
|-------|------|-------|
| `main.py` | config load + RuntimeManager init + UI server start | anything else |
| `RuntimeManager` | lifecycle coordination | cognition, workflows, events |
| `Orchestrator` | cognitive flow → TaskRouter | tool execution, memory, state mutation |
| `FastAPI routes` | serialize request → call runtime_manager | business logic |
| `EventBus` | pub/sub routing | direct component calls |

### Component States
`offline → starting → idle → busy → degraded → failed → offline`

### Runtime Modes
`idle → initializing → active → degraded → shutdown`

### Key Renames
- `brain.py` → `orchestrator.py` (names shape architecture)

### Deferred (do not implement until explicitly unlocked)
LLM2, WorkflowExecutor (real), ToolInvocation, Memory, Vision, Permissions, VRAM arbitration, Process isolation

## V0.1 Status — COMPLETE (2026-05-11)

All 16 implementation tasks done. 54 tests passing. Server boots at localhost:7799.

**What's implemented:**
- `Skynet/core/` — EventBus, RuntimeState, Component ABC, ComponentRegistry, BackgroundRunner, RuntimeManager, Orchestrator (rolling window=3)
- `Skynet/voice/` — STTComponent (faster-whisper), TTSComponent (pyttsx3, thread-pool non-blocking)
- `Skynet/providers/` — OllamaProvider, ClaudeProvider, registry
- `Skynet/task/` — TaskRouter (passthrough), WorkflowExecutor (stub)
- `Skynet/ui/` — FastAPI server, WebSocket broadcaster, HTML dashboard, api.js/websocket.js/dashboard.js/runtime.js, routes: settings/hardware/status/models
- `Skynet/main.py` — thin launcher
- `config/settings.yaml` — runtime config

**Next milestone:** V0.2 — unlock Memory, Skills, or Vision (brainstorm first)

## Agent Comms (SendMessage-First Coordination)

Named agents coordinate via `SendMessage`, not polling or shared state.

```
Lead (you) ←→ architect ←→ developer ←→ tester ←→ reviewer
              (named agents message each other directly)
```

### Spawning a Coordinated Team

```javascript
// ALL agents in ONE message, each knows WHO to message next
Agent({ prompt: "Research the codebase. SendMessage findings to 'architect'.",
  subagent_type: "researcher", name: "researcher", run_in_background: true })
Agent({ prompt: "Wait for 'researcher'. Design solution. SendMessage to 'coder'.",
  subagent_type: "system-architect", name: "architect", run_in_background: true })
Agent({ prompt: "Wait for 'architect'. Implement it. SendMessage to 'tester'.",
  subagent_type: "coder", name: "coder", run_in_background: true })
Agent({ prompt: "Wait for 'coder'. Write tests. SendMessage results to 'reviewer'.",
  subagent_type: "tester", name: "tester", run_in_background: true })
Agent({ prompt: "Wait for 'tester'. Review code quality and security.",
  subagent_type: "reviewer", name: "reviewer", run_in_background: true })

// Kick off the pipeline
SendMessage({ to: "researcher", summary: "Start", message: "[task context]" })
```

### Patterns

| Pattern | Flow | Use When |
|---------|------|----------|
| **Pipeline** | A → B → C → D | Sequential dependencies (feature dev) |
| **Fan-out** | Lead → A, B, C → Lead | Independent parallel work (research) |
| **Supervisor** | Lead ↔ workers | Ongoing coordination (complex refactor) |

### Rules

- ALWAYS name agents — `name: "role"` makes them addressable
- ALWAYS include comms instructions in prompts — who to message, what to send
- Spawn ALL agents in ONE message with `run_in_background: true`
- After spawning: STOP, tell user what's running, wait for results
- NEVER poll status — agents message back or complete automatically

## Swarm & Routing

### Config
- **Topology**: hierarchical-mesh (anti-drift)
- **Max Agents**: 15
- **Memory**: hybrid
- **HNSW**: Enabled
- **Neural**: Enabled

```bash
npx @Codex-flow/cli@latest swarm init --topology hierarchical --max-agents 8 --strategy specialized
```

### Agent Routing

| Task | Agents | Topology |
|------|--------|----------|
| Bug Fix | researcher, coder, tester | hierarchical |
| Feature | architect, coder, tester, reviewer | hierarchical |
| Refactor | architect, coder, reviewer | hierarchical |
| Performance | perf-engineer, coder | hierarchical |
| Security | security-architect, auditor | hierarchical |

### When to Swarm
- **YES**: 3+ files, new features, cross-module refactoring, API changes, security, performance
- **NO**: single file edits, 1-2 line fixes, docs updates, config changes, questions

### 3-Tier Model Routing

| Tier | Handler | Use Cases |
|------|---------|-----------|
| 1 | Agent Booster (WASM) | Simple transforms — skip LLM, use Edit directly |
| 2 | Haiku | Simple tasks, low complexity |
| 3 | Sonnet/Opus | Architecture, security, complex reasoning |

## Memory & Learning

### Before Any Task
```bash
npx @Codex-flow/cli@latest memory search --query "[task keywords]" --namespace patterns
npx @Codex-flow/cli@latest hooks route --task "[task description]"
```

### After Success
```bash
npx @Codex-flow/cli@latest memory store --namespace patterns --key "[name]" --value "[what worked]"
npx @Codex-flow/cli@latest hooks post-task --task-id "[id]" --success true --store-results true
```

### MCP Tools (use `ToolSearch("keyword")` to discover)

| Category | Key Tools |
|----------|-----------|
| **Memory** | `memory_store`, `memory_search`, `memory_search_unified` |
| **Bridge** | `memory_import_claude`, `memory_bridge_status` |
| **Swarm** | `swarm_init`, `swarm_status`, `swarm_health` |
| **Agents** | `agent_spawn`, `agent_list`, `agent_status` |
| **Hooks** | `hooks_route`, `hooks_post-task`, `hooks_worker-dispatch` |
| **Security** | `aidefence_scan`, `aidefence_is_safe`, `aidefence_has_pii` |
| **Hive-Mind** | `hive-mind_init`, `hive-mind_consensus`, `hive-mind_spawn` |

### Background Workers

| Worker | When |
|--------|------|
| `audit` | After security changes |
| `optimize` | After performance work |
| `testgaps` | After adding features |
| `map` | Every 5+ file changes |
| `document` | After API changes |

```bash
npx @Codex-flow/cli@latest hooks worker dispatch --trigger audit
```

## Agents

**Core**: `coder`, `reviewer`, `tester`, `planner`, `researcher`
**Architecture**: `system-architect`, `backend-dev`, `mobile-dev`
**Security**: `security-architect`, `security-auditor`
**Performance**: `performance-engineer`, `perf-analyzer`
**Coordination**: `hierarchical-coordinator`, `mesh-coordinator`, `adaptive-coordinator`
**GitHub**: `pr-manager`, `code-review-swarm`, `issue-tracker`, `release-manager`

Any string works as a custom agent type.

## Build & Test (Python — not npm)

- ALWAYS run tests after code changes
- ALWAYS verify build succeeds before committing

```bash
python -m pytest tests/        # run from C:\Work\Nexux\
python -m Skynet.main          # boots server at localhost:7799
```

## CLI Quick Reference

```bash
npx @Codex-flow/cli@latest init --wizard           # Setup
npx @Codex-flow/cli@latest swarm init --v3-mode     # Start swarm
npx @Codex-flow/cli@latest memory search --query "" # Vector search
npx @Codex-flow/cli@latest hooks route --task ""    # Route to agent
npx @Codex-flow/cli@latest doctor --fix             # Diagnostics
npx @Codex-flow/cli@latest security scan            # Security scan
npx @Codex-flow/cli@latest performance benchmark    # Benchmarks
```

26 commands, 140+ subcommands. Use `--help` on any command for details.

## Setup

```bash
Codex mcp add Codex-flow -- npx -y @Codex-flow/cli@latest
npx @Codex-flow/cli@latest daemon start
npx @Codex-flow/cli@latest doctor --fix
```

**Agent tool** handles execution (agents, files, code, git). **MCP tools** handle coordination (swarm, memory, hooks). **CLI** is the same via Bash.

## graphify

This project has a graphify knowledge graph at graphify-out/.

Rules:
- Before answering architecture or codebase questions, read graphify-out/GRAPH_REPORT.md for god nodes and community structure
- If graphify-out/wiki/index.md exists, navigate it instead of reading raw files
- After modifying code files in this session, run `python3 -c "from graphify.watch import _rebuild_code; from pathlib import Path; _rebuild_code(Path('.'))"` to keep the graph current
