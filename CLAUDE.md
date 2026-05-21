# Nexux — Claude Code Configuration

## Project

**Nexux by Klyx** — persistent desktop AI operating companion (internal runtime: Skynet).

```
C:\Work\Nexux\
├── Skynet\
│   ├── core\         orchestrator, event bus, runtime manager, verifier (LLM2)
│   ├── voice\        STT (faster-whisper, 3 modes), TTS (kokoro / f5tts)
│   ├── memory\       Qdrant vector store, SQLite sessions, raw JSONL log, compressor
│   ├── providers\    LLM provider abstraction (Ollama, Claude, OpenRouter)
│   ├── task\         TaskRouter, skill loader
│   ├── tools\        16 tools: file ops, glob/grep, bash, web_fetch, memory, skills
│   ├── ui\           FastAPI server, WebSocket, HTML dashboard, JS modules, API routes
│   └── main.py       thin launcher
├── tests\            48 tests
├── config\           settings.yaml, personas/, voices/, skills/
├── logs\             nexux.log, memory.db, sessions/*.jsonl
└── docs\             architecture specs (read-only reference)
```

**Stack**: Python, FastAPI, faster-whisper, Qdrant, Ollama, uvicorn  
**Spec docs**: `docs/` — read before making architectural decisions

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

## Honesty Policy — Non-Negotiable

**NEVER sugar coat anything. This is an explicit instruction from the owner.**

- If the user's approach is wrong, say it is wrong. Directly. Explain why.
- If you suggested something wrong (e.g., added a bad feature), admit it immediately and revert it.
- If a better pattern exists in the industry, name it and compare. Do not pretend the current approach is fine.
- If a design decision is a hack or a workaround, call it that in code comments and in this document.
- If the user is building towards a dead end, say so before they sink time into it.
- Do not frame bad decisions as "a valid approach" — they are bad decisions.
- Alert the user to relevant advances in the field even if not asked. (Example: if MCP or OpenAI function calling or a new local model changes the calculus on something we built, say so.)

Failure to follow this policy is worse than being wrong. Silence and softness waste the user's time.

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
| `Orchestrator` | cognitive loop → tool dispatch → TaskRouter | direct state mutation |
| `FastAPI routes` | serialize request → call runtime_manager | business logic |
| `EventBus` | pub/sub routing | direct component calls |

### Component States
`offline → starting → idle → busy → degraded → failed → offline`

### Runtime Modes
`idle → initializing → active → degraded → shutdown`

### Deferred (do not implement until explicitly unlocked)
WorkflowExecutor (real), Vision, Permissions, VRAM arbitration, Process isolation

### Cognitive State Manager — North Star Architecture (planned, not implemented)

The current memory model is "rolling transcript + occasional compression." This is a toy approach. The correct model for a long-running autonomous agent is a **cognitive state manager** — five distinct layers with different lifetimes, storage, and retrieval strategies.

**Layer 1 — Pinned Identity State (never compressed)**
Structured JSON, not chat history. Written by semantic pinning (LLM2 detects and elevates). Never evicted automatically.
Contents: user name, role, preferences, project definitions, long-term goals, durable rules ("from now on...", "always...").
Storage: Qdrant `entry_type="core"` + a dedicated JSON blob at `data/identity.json`.
Example: `{"user": "Alex", "project": "Nexux", "preferences": ["concise answers"], "stack": ["Python", "Qdrant"]}`

**Layer 2 — Active Working Memory (rolling window)**
Recent turns. Verbatim. Needed for immediate continuity. Current: last 5 turns in LLM context.
Target: last 10-20 turns once context budget allows.

**Layer 3 — Episodic Summaries (compressed middle)**
LLM2 compresses the middle of session history — NOT the beginning (which is identity-establishing).
Format: "Discussed orchestrator architecture and MCP integration. Decided on tool-pull model."
Storage: SQLite session_store + Qdrant `entry_type="summary"`.

**Layer 4 — Long-Term Semantic Memory (Qdrant)**
Facts, summaries, core entries. Retrieved dynamically by semantic search.
Already implemented.

**Layer 5 — Execution State (planned)**
What task is currently active, what's pending, what was interrupted.
Not implemented. Needed for multi-session task continuity.

**Semantic Pinning (LLM2, partially implemented)**
LLM2 detects identity/preference/goal statements every turn and writes them as `core` entries.
Trigger phrases: "I prefer...", "We are building...", "From now on...", "The system uses...", "My name is...", "Always...", "Never..."
These are elevated to Layer 1 immediately — not left in the chat transcript to be compressed away.

**The shift:**
Stop thinking: conversation manager (transcript + summarization)
Start thinking: cognitive state manager (pinned identity + working context + episodic memory + semantic retrieval + execution state)
This is the architecture that makes long-running autonomous agents reliable across sessions.

### Orchestration Design Principle — Tool-Pull, Not Orchestrator-Push

**The correct model is: LLM evaluates the request → decides what it needs → calls tools to get it.**

The orchestrator's job is to give the model good tools and get out of the way. It is NOT the orchestrator's job to guess what data the model might need and pre-inject it.

**What we do NOT do (and why):**
- Do NOT add regex patterns that detect "cpu" or "encoding" in the user message and auto-inject hardware metrics. The model has `get_system_info()`. If it wants metrics, it calls the tool. Adding injection bypasses the model's reasoning and makes the orchestrator a guessing machine.
- Do NOT add regex patterns that detect intent and pre-fetch data speculatively. That is the model's job.
- Do NOT grow the system prompt with "injected context" as the default answer to every new feature. A bigger system prompt is not intelligence — it is noise.

**The ONE justified injection exception (memory recall):**
Memory recall is pre-fetched and injected because of a specific, empirically proven failure: 14B quant models trained on "I have no persistent memory" will ignore the `search_memory` tool and deny having memory even when the tool works perfectly. This is a workaround for a broken base training behaviour. It is a HACK with a documented reason, not a pattern to copy.

**Everything else — hardware stats, env details, skills, system status — the model calls the tool.**

If a future model is smart enough to call memory tools reliably, the injection should be removed too.

**What LLM2 should eventually become (planned, not implemented):**
LLM2 pre-flight evaluation — before LLM1 sees the user message, LLM2 classifies: what tools are likely needed? What memory is relevant? Pass that as tool-call hints to LLM1's context. This is the Router pattern (used by GPT-4o, Claude, Gemini internal routing). It's better than regex. Don't implement it until LLM2 is fast enough (sub-200ms) to not add perceptible latency.

### LLM2 Master Vision — Bootstrapper, Not Permanent Infrastructure

**LLM2 is a temporary scaffolding.** Every role it plays today will be replaced by a skill built from real behavioral data. LLM2's job is to generate that data — then retire.

Current LLM2 roles:
1. **Supervisor** — audits LLM1 responses post-turn (implemented)
2. **Compressor** — summarises sessions into memory (implemented)
3. **Router** — pre-flight routing: what to inject, what tools to hint (planned)

For each role, the retirement path is identical:
- Phase 1: LLM2 does the job with a rules/prompt document
- Phase 2: LLM2 writes memory entries capturing every decision — what worked, what failed, what LLM1 did with the output
- Phase 3: A deterministic skill is built from that accumulated memory — fast, no LLM call, self-improving as more data accumulates. LLM2 is retired from that role.

**End state:** LLM2 is gone entirely. Every cognitive task it performs today is handled by skills built from real session data. The system taught itself through use.

This is the correct long-term architecture. Do not short-circuit it by hardcoding rules into skills prematurely — the value comes from real behavioral data, not guessed rules.

### LLM2 Supervisor — 3-Phase Roadmap (owner's vision)

**Phase 1 — Full unconditional inspection (current implementation target):**
LLM2 receives a comprehensive rules document (everything currently hardcoded in regex: denial patterns, save rules, premature stop rules, behavioral constraints) and audits every single LLM1 response. No regex pre-filters in the supervisor path. Latency cost (~500ms) is accepted — this is an early build and the rules document is the authoritative source of truth. When rules change, only the LLM2 prompt changes, not the code.

**Phase 2 — Behavioral memory accumulation:**
LLM2 writes Qdrant entries (entry_type="llm1_behavior") recording every failure and success pattern it observes: what LLM1 said, what rule was violated, what the correct response should have been. Over 20+ sessions, a real behavioral dataset emerges from live usage. This is not synthetic data — it is ground truth from actual interactions.

**Phase 3 — Skill/wrapper replaces LLM2:**
The accumulated behavioral memory becomes training input for a deterministic skill or a fine-tuned classifier. The skill knows exactly what LLM1 does wrong (built from real failures) and enforces it without any LLM call — sub-millisecond, no latency. LLM2 is retired from the supervisor role entirely. The skill self-improves as more failure data accumulates.

**Why this is the right architecture:**
This is behavioral distillation. Use an LLM to label behavior cheaply until you have enough labeled examples to replace the LLM with something faster. GPT-4 was used this way to generate training data for smaller models. We are doing the same thing for our own behavioral constraints.

**Do not skip phases.** Phase 3 without Phase 2's data is just another set of hardcoded rules — no better than what we have now. The value is the live behavioral dataset built from real sessions.

### LLM2 Router — 3-Phase Roadmap (planned, do not implement until supervisor is validated)

The current memory injection is a regex hack (documented in "Orchestration Design Principle"). The correct replacement is LLM2 pre-flight routing.

**Phase 1 — LLM2 routes every turn (replaces regex injection):**
Before LLM1 sees the user message, LLM2 runs a fast routing decision:
- Should memory be pre-fetched? Which kind (semantic, session, core)?
- What tools will LLM1 likely need? Hint them explicitly.
- Is the injected context sufficient, or should LLM1 fetch more?
LLM2 returns a small JSON routing decision. Orchestrator acts on it. LLM1 receives message + pre-fetched context + tool hints. If injected memory answers the question, LLM1 does not call search_memory(). If it needs more (full log, deeper search), it calls the tool — informed, not blind.
Latency cost: ~300-600ms added before LLM1. Acceptable on RTX 5080 with both models warm.
Prerequisite: supervisor (Phase 1) validated in live sessions first.

**Phase 2 — LLM2 writes routing memory:**
LLM2 logs every routing decision to Qdrant (entry_type="routing_decision"):
- What it decided to inject, what it decided to skip
- Whether LLM1 fetched additional context anyway (meaning the injection was insufficient)
- Whether LLM1 ignored injected context (meaning it was irrelevant noise)
Over sessions, the data reveals which message patterns need which memory types — ground truth from real usage, not guesses.

**Phase 3 — Skill replaces LLM2 for routing:**
The accumulated routing memory trains a deterministic classifier: given message pattern X → inject Y, hint tools Z. Sub-millisecond. No LLM call. LLM2 is retired from routing.
The regex injection hack is deleted entirely.

### Environment Fingerprint — Implemented
`_ENV` dict computed once at module load (`_detect_environment()` in `orchestrator.py`). Injected into every system prompt. Adapts automatically to the host:

| OS | Shell reported | run_bash hint | Env var syntax |
|----|---------------|--------------|----------------|
| Windows | PowerShell | PowerShell cmds | `$env:VAR` |
| macOS | bash/zsh | bash cmds | `$VAR` |
| Linux | bash | bash cmds | `$VAR` |
| Android (Termux) | bash (Termux/Android) | bash cmds | `$VAR` |

Model always knows which shell it's talking to — no wrong commands for the wrong OS.

### Live System Metrics — Tool-only (correct approach)
`get_system_info` tool returns CPU%, RAM, disk, GPU (via nvidia-smi) + component health + memory stats.

The model calls this tool when it wants hardware data. There is no regex injection. See "Orchestration Design Principle" above for why.

**Dependency**: `pip install psutil` for CPU/RAM. GPU requires NVIDIA drivers + `nvidia-smi` in PATH.

### Time Awareness — Phase 1 Implemented
`vector_store.store()` auto-injects `hour_of_day` (int, 0–23) and `day_of_week` (string, "Monday"…) into every Qdrant entry payload. Zero schema change — all existing entries work, new entries are time-tagged.

### Planned — Time Awareness Phase 2 + 3 (do not implement until unlocked)
**Phase 2** — Compressor classifies sessions by time slot + mood/topic → saves `habit` entry type. Patterns emerge over 20+ sessions.
**Phase 3** — System prompt gets "known user patterns" block auto-generated from `habit` entries. Model adapts tone by time of day.

### Planned — Behavioral Patterns / Habit Memory (do not implement until unlocked)
Deferred long-term feature. The AI learns patterns like "user is brief and tired at 11pm on weekdays". 
- New Qdrant entry type: `habit` — written by compressor after 20+ sessions accumulate
- Requires Phase 2 + 3 of Time Awareness above
- Do NOT implement until explicitly unlocked — needs real session data to be meaningful

### Planned — STT Correction via LLM (do not implement until unlocked)
Whisper transcription is imperfect — accents, technical terms, names, and fast speech cause errors. A post-STT correction pass using a cheap LLM can fix meaning before the transcript reaches the orchestrator.
- **Where**: `STTComponent._on_audio()` after `transcribe()` returns raw text
- **How**: Pass raw transcript + short context ("user typically says X for Y") to LLM2 for correction
- **What to fix**: homophone errors, misheard technical terms, broken sentences — NOT grammar or style
- **User adaptation**: Over time, build a personal vocabulary map (e.g. "nexux" → "Nexus") stored as `fact` entries in Qdrant, injected as correction hints
- **Cost**: ~50ms LLM2 call added to STT path — acceptable since TTS is already async
- Do NOT implement until explicitly unlocked

### Planned — Speaker Diarization (do not implement until unlocked)
Whisper large-v3 alone cannot distinguish speakers. Requires `pyannote.audio` alongside STT for diarization. Use case: know if main user vs someone else is speaking. STTComponent would need a second pass over audio segments.

## Current Status — V0.2 Live (2026-05-21)

51 tests passing. Server boots at `localhost:7799`.

### What's implemented

**Core runtime** (`Skynet/core/`)
- EventBus, RuntimeState, Component ABC, ComponentRegistry, BackgroundRunner, RuntimeManager
- Orchestrator: rolling window=6, XML/JSON tool fallback chain, completion validator, recovery prompts
- Verifier: `grade_and_annotate()` (USEFUL/EMPTY/FAILED/INVALID), `is_task_complete()` with LLM2 semantic check, post-write syntax checks (py/yaml/json)
- LLM2 (qwen2.5:3b): cheap supervisory model — verifier + memory compressor

**Voice** (`Skynet/voice/`)
- STTComponent: faster-whisper, 3 modes — `continuous` (always on), `push_to_talk` (hold), `disabled`
- TTSComponent: kokoro / f5tts backends, non-blocking thread pool

**Memory** (`Skynet/memory/`) — 4 layers

| Layer | File | Written by | Read by | Notes |
|-------|------|-----------|---------|-------|
| Rolling window | in-process `_history` list | Orchestrator | Always in LLM context | Last 6 turns; ephemeral |
| Raw log | `logs/sessions/YYYY-MM-DD.jsonl` | Orchestrator | `get_recent_history()` tool | Full verbatim transcript |
| Session store | `logs/memory.db` (SQLite) | Compressor (LLM2) | `search_memory()` tool | Summaries + facts per session |
| Vector store | `data/qdrant/` (Qdrant) | `save_memory` tool + Compressor | Auto-prefetch + `search_memory()` | Semantic search; entry types: `core` / `important` / `summary` / `fact` |

- All Qdrant entries carry `hour_of_day` (0–23) + `day_of_week` metadata (Phase 1 time tagging — live)
- Auto-prefetch: `_MEMORY_RECALL` regex fires → Qdrant + SQLite injected into system prompt before LLM responds
- Compressor: LLM2 summarises history → saves to SQLite + Qdrant (on session end + every 20 turns)

**Tools** (`Skynet/tools/`) — 16 tools, individually toggleable in UI
| Tool | Description |
|------|-------------|
| `read_file` | Read any project file (8k char limit) |
| `write_file` | Write / create a file |
| `edit_file` | Precise single-occurrence string replacement |
| `multi_edit_file` | Multiple replacements in one call |
| `list_files` | Directory listing |
| `glob_files` | Find files by glob pattern |
| `grep_files` | Regex search across file contents (parallel) |
| `read_all_files` | Read entire directory in parallel (ThreadPoolExecutor) |
| `run_bash` | Full PowerShell access — git, python, pip, grep, curl, etc. |
| `web_fetch` | Fetch a URL, strip HTML to plain text |
| `save_memory` | Store to Qdrant (core / important / summary) |
| `search_memory` | Query Qdrant + SQLite sessions |
| `get_recent_history` | Last N turns from raw JSONL log |
| `get_system_info` | Live component health + skill index + LLM info |
| `reload_skills` | Hot-reload skill YAML from disk |
| `load_skill` | Load skill instructions by name |

**UI** (`Skynet/ui/`)
- FastAPI + uvicorn, WebSocket broadcaster (server → client events)
- Dashboard: Config / Chat / Voices / System tabs
- Chat tab: text input (Enter to send), STT mode buttons (Always On / Hold / Off), PTT hold button, context window bar
- Config tab: LLM, Voice, Microphone, Persona, Input (STT mode), Tools (per-tool toggles, hot-reload)
- API routes: `/api/settings/{llm,voice,mic,stt,tools,persona}`, `/api/chat/send`, `/api/stt/ptt/{start,stop}`, `/api/runtime/{initialize,shutdown}`, `/api/debug/prompt`

**Providers** (`Skynet/providers/`)
- OllamaProvider: native tool calling + XML `<tool_call>` fallback + bare JSON fallback
- ClaudeProvider: Anthropic API with `complete_with_tools()`, dual-format multi-turn history

**Config** (`config/settings.yaml`)
```yaml
llm1: { backend: ollama, model: qwen2.5-coder:14b }
llm2: { backend: ollama, model: qwen2.5:3b, enabled: true }
stt:  { model: large-v3, device: cuda, mode: continuous }
tts:  { backend: kokoro, voice_id: af_sky }
memory: { enabled: true, compress_at: 20 }
tools:  { disabled: [] }   # list tool names to disable
```

## Orchestrator Tool Calling Flow

```
User input → STTTranscribedEvent → Orchestrator._handle()
  → _build_messages()           # system prompt + memory injection
  → _unified_loop() (max 15 steps):
      1. provider.complete_with_tools(messages, active_tools)
      2. Fallback: XML <tool_call> tags
      3. Fallback: bare JSON objects in text
      4. If no tool call: is_task_complete() → recovery prompt (max 2)
      5. For each tool call: exec_tool() → grade_and_annotate() → append to history
  → OrchestratorResponseEvent → TTS
  → Session saved on stop() or every compress_at turns
```

## Model Swap Checklist

Run this every time you change `llm1.model` or `llm2.model` in `settings.yaml`.

### Step 1 — Automated regression suite (always run first)

```bash
python -m pytest tests/test_model_regression.py -v
```

This runs 62 tests covering every behavioral bug we've fixed. All must pass before proceeding.

| Test group | What it guards |
|------------|----------------|
| R1–R3 | Recall vs save regex routing — "I love you. Remember that" must → save, not recall |
| R4 | Denial pattern detection — model claiming "no persistent memory" triggers gate |
| R5 | Auto-save stores user's words, not model's confused reply |
| R6, R9 | auto_saved=True suppresses false MISSED SAVE supervisor violation |
| R7–R10 | Supervisor: flags denial + missed save, ignores emotional statements |
| R11–R12 | Premature stop detection — "let me read" flagged, "file written" not flagged |
| R13–R15 | Tool grading — empty/not-found annotated, useful results unchanged |
| R16 | Every Qdrant entry carries hour_of_day + day_of_week metadata |
| R17 | Completion check regex fallback when LLM2 not configured |

### Step 2 — Full test suite

```bash
python -m pytest tests/ --ignore=tests/ui/ --ignore=tests/test_main_boot.py
```

### Step 3 — Manual behavioral checks (live model)

Start the server (`python -m Skynet.main`) and verify in the chat:

1. **Memory save**: Say "Remember that my favourite color is blue." → next session ask "what is my favourite color?" — must recall correctly
2. **No denial**: Ask "do you have memory?" → must NOT say "I have no persistent memory" — should say yes and list capabilities
3. **Current time**: Ask "what time is it?" → must give correct time, not claim it has no real-time capabilities
4. **Task completion**: Ask "read the config file and tell me what model is set" → must actually read the file and answer, not just say "let me read it"
5. **Looping**: Ask a multi-step task ("create a file called test.txt with the word hello") → loop must run to completion without stopping mid-way for approval
6. **STT + TTS non-blocking**: Speak a long sentence → response must start playing without UI freezing

### Step 4 — LLM2 supervisor visibility

Check `logs/nexux.log` after a session with a save request:
- Must see `[LLM2]` lines confirming supervisor ran
- Must NOT see false `MISSED SAVE` warnings when user asked to save something

## Build & Test (Python — not npm)

- ALWAYS run tests after code changes
- ALWAYS verify build succeeds before committing
- **When a new feature is implemented: add its manual test cases to `testing.md` before marking it done.**
  Add a row to the relevant section. If no section exists, create one. Move the feature from the
  "Tests to Add" table at the bottom of `testing.md` to its own section.

```bash
python -m pytest tests/                           # run from C:\Work\Nexux\
python -m pytest tests/ --ignore=tests/ui/ --ignore=tests/test_main_boot.py  # skip env-dep tests
python -m Skynet.main                             # boots server at localhost:7799
```

## Agent Comms (SendMessage-First Coordination)

Named agents coordinate via `SendMessage`, not polling or shared state.

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
- Spawn ALL agents in ONE message with `run_in_background: true`
- After spawning: STOP, tell user what's running, wait for results
- NEVER poll status — agents message back or complete automatically

## When to Swarm
- **YES**: 3+ files, new features, cross-module refactoring, API changes, security, performance
- **NO**: single file edits, 1-2 line fixes, docs updates, config changes, questions

## graphify

This project has a graphify knowledge graph at `graphify-out/`.

- Before answering architecture or codebase questions, read `graphify-out/GRAPH_REPORT.md`
- If `graphify-out/wiki/index.md` exists, navigate it instead of reading raw files
- After modifying code files, run:
  ```bash
  python3 -c "from graphify.watch import _rebuild_code; from pathlib import Path; _rebuild_code(Path('.'))"
  ```
