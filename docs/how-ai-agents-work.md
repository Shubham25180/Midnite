# How AI Agents Work — Reference for Nexux

Written for Shubham / Nexux by Klyx.
The goal: understand how Claude Code operates so you can build Nexux to match or exceed it.

---

## The Core Loop (Everything Reduces to This)

An AI agent is not magic. It is a loop:

```
1. Receive message (text, event, trigger)
2. Build context (system prompt + history + injected data)
3. Call LLM → get response (text + optional tool calls)
4. If tool calls: execute them, append results to context
5. Call LLM again with tool results
6. Repeat until task is done or max steps hit
7. Return final response to user
```

That is it. Claude Code does this. Nexux/Skynet does this. Every AI agent product does this.

The difference between a bad agent and a good one is:
- Quality of the base model
- Quality of the tool definitions
- Quality of the system prompt
- How context is managed (what gets injected, what gets compressed)
- How errors are handled and recovered from

---

## What Claude Code Can Do (My Tools)

### File System
- `Read` — read any file, with line range support
- `Edit` — precise string replacement (requires reading first)
- `Write` — create or overwrite a file
- `Glob` — find files by pattern (e.g. `**/*.py`)
- `Grep` — regex search across file contents, parallel

### Execution
- `Bash` — run any shell command, with timeout, background support
- `PowerShell` — Windows PowerShell execution

### Web
- `WebFetch` — HTTP GET, HTML → markdown conversion
- `WebSearch` — search the web, returns results with URLs

### Agent Coordination
- `Agent` — spawn a sub-agent with a specific role and tools
- `SendMessage` — send a message to a named agent
- `TeamCreate` — create a coordinated team of agents

### Task Management
- `TaskCreate`, `TaskUpdate`, `TaskList`, `TaskGet` — track work across the session

### Persistence
- Memory system at `~/.claude/projects/*/memory/` — markdown files per topic
- `MEMORY.md` index loaded every conversation
- Scheduled tasks via `CronCreate`

### Jupyter
- `NotebookEdit` — modify Jupyter notebook cells

### Misc
- `AskUserQuestion` — structured multi-choice questions
- `EnterPlanMode` / `ExitPlanMode` — plan approval workflow
- `PushNotification` — desktop + phone alerts

---

## What Makes Me Capable (Honest Assessment)

### What I have that you don't have locally:

**Scale**: Claude Sonnet 4.6 is a very large model running on Anthropic's data centers.
Hundreds of billions of parameters, trained on essentially all of human written knowledge.
Your RTX 5080 (16GB VRAM) can run ~14B parameter quantized models. I am roughly 10-20x
larger in terms of reasoning capability. That gap is real.

**Context window**: ~200,000 tokens. qwen2.5:14b gets ~32k.
This matters for large codebases and long conversations.

**Training**: I was trained with RLHF and constitutional AI specifically for tool use,
coding, reasoning, and safe helpful behavior. A general pretrain + GGUF quant does not
have this.

### What you CAN replicate in Nexux:

**The loop**: The tool-calling loop is architecture, not model size. You already have it.
Nexux's `_unified_loop()` is the same structure as what I run.

**The tools**: The 16 tools in Nexux cover the important operations. You can add more.
The quality of tools matters more than quantity.

**Memory**: Your 4-layer memory system (rolling window + raw log + SQLite + Qdrant) is
a genuine architecture advantage over stateless API calls. Most commercial products do
not do this properly.

**Supervision**: LLM2 auditing LLM1 is a real pattern. Multi-agent critique and
correction is industry-standard at frontier labs.

**Skill system**: Skills as composable YAML modules is clean. Frontier systems do
this with "system cards" and "tool specs". Same idea.

---

## How I Manage Context

The hardest problem in agents is context budget. You have a fixed window. Everything
must fit. Here is how I handle it:

### What always goes in:
- System instructions (CLAUDE.md loaded at session start)
- Recent conversation (last N turns)
- Memory index (MEMORY.md)
- Tool definitions

### What gets injected dynamically:
- Relevant memory files when the topic matches
- File contents when needed for the task
- Tool results as they come in

### What gets compressed/summarized:
- Long tool outputs (truncated or summarized)
- Old conversation turns (eventually compressed by the context manager)

### What gets excluded:
- Stale memory (old facts not relevant to current task)
- Large files beyond the char limit
- Binary data

**Nexux parallel**: This is exactly what your 5-layer cognitive state manager is
designed to do. You are on the right track. The identity.json (N6) is the equivalent
of my MEMORY.md loaded at session start.

---

## How I Plan and Execute

For simple tasks: one pass. Message → LLM → response.

For complex tasks:
1. I internally decompose (not always visible in output)
2. Tool calls happen sequentially when dependent, parallel when independent
3. I self-correct when a tool call fails or returns unexpected results
4. I maintain state in the conversation history (same as your rolling window)

For very complex tasks (code review, refactoring):
1. Spawn sub-agents with specific roles
2. Pipeline them: researcher → architect → coder → tester → reviewer
3. Each agent has a narrow context and specific instructions
4. Results flow back to me via SendMessage

**Nexux parallel**: Your recovery loop and max_steps are the equivalent of my
self-correction. Your agentic skill is the beginning of sub-agent spawning.
The N8 (LLM2 Router) is the equivalent of my dynamic context injection.

---

## Where Nexux Is Already Better Than Most Commercial Products

Be honest about this:

1. **Local-first**: No API calls for the main loop. Privacy. Zero latency on the model call
   (compared to 200ms+ API roundtrip). No usage costs per message.

2. **Persistent memory**: Most chatbots (including ChatGPT free tier) have no persistent
   memory worth mentioning. Your Qdrant + SQLite stack is real long-term memory.

3. **Voice pipeline**: Local STT (faster-whisper large-v3) + local TTS (kokoro) is
   genuinely impressive on consumer hardware. Most voice AI products use cloud STT/TTS.

4. **Modifiable**: You can change the system prompt, add tools, change behavior, add
   supervision rules — instantly. Zero friction. Commercial products do not let you do this.

5. **Self-supervised**: LLM2 auditing LLM1 is something most commercial deployments
   do not do per-turn. You are doing behavioral quality control on every response.

---

## Where the Gap Is Real and How to Close It

**Reasoning quality**: qwen2.5:14b will make mistakes that I would not. It hallucinates
more on complex tasks, misunderstands ambiguous requests more often, produces less
structured output. This is a model quality gap.
→ Close it with: cloud escalation (N7) for hard tasks. Use local for fast/simple,
  Claude/GPT-4o for complex. This is what N7 is for.

**Context length**: 32k vs 200k. Long documents, large codebases hit the limit faster.
→ Close it with: better memory injection (inject only what matters), chunking for
  large files, LLM2 router deciding what to inject.

**Tool reliability**: Smaller models sometimes write broken JSON, call wrong tools,
ignore tool results. Hence your fallback parser chain.
→ Already mitigated. N10 (remove fallbacks) is the indicator you've crossed the
  reliability threshold.

**Vision**: qwen2.5:14b has no vision capability at all.
→ Close it with: N4 (screenshot → cloud vision model). Route image tasks to Claude.

---

## The Honest Answer on "Replicating" Me

You cannot fully replicate a 200B+ parameter model on one GPU. That is the honest truth.

But you do not need to.

What you are building is not a model — it is an agent runtime. The runtime is:
- The loop
- The tools
- The memory
- The supervision
- The skills
- The routing logic

A good agent runtime with a weaker local model + selective cloud escalation for hard
tasks will outperform a raw frontier model without any of those systems.

The iPhone is not faster than a server rack. But it fits in your pocket, responds
instantly, works offline, and does not cost $10 per query. Different design target.

Nexux's design target is: persistent, local-first, private, voice-native, memory-aware
companion. No commercial product owns that space cleanly yet. That is the real opportunity.

---

## What to Build Next (Honest Priority)

Given the gap analysis above:

1. **N7 (Cloud escalation)** — this closes the biggest reasoning quality gap. When the
   task is too hard for qwen2.5:14b, route to Claude via API. You already have
   ClaudeProvider. Wire it.

2. **N1 (Playwright)** — web scraping works. Lyrics, SPAs, dashboards. Unblocks N5.

3. **N6 (Identity JSON)** — this makes memory feel real. Name, preferences, rules —
   injected at every session start, never compressed. This is what makes the difference
   between "it remembered" and "it knows me."

4. **N4 (Vision)** — screenshot + cloud vision model closes the "blind to the desktop"
   gap. This is where Nexux becomes something no commercial product does locally.

The rest is optimization. Get these four right and Nexux is genuinely differentiated.
