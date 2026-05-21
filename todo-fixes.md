# Nexux — Audit Fix List

Ordered by impact. Each fix gets brainstormed before any code is written.

---

## CRITICAL

### [F1] Three fallback parsers — wrong model symptom
**Status:** partial ✓ (added Fallback 3: Python `funcname({...})` syntax; F1 full removal still gated on live validation)
**Problem:** Native API → XML `<tool_call>` → bare JSON → Python `funcname({...})`. Four parsers now. qwen2.5:14b confirmed to use native API reliably, but fallbacks retained until multiple sessions validate this.
**Risk:** High. Removing parsers before fixing model = broken tool calling.

### [F2] Denial gate + auto-save + supervisor — all compensating for bad model
**Status:** pending
**Problem:** Entire `verifier.py`, denial rewrite, auto-save, `_supervisor_notes` injection — all exist to compensate for `qwen2.5-coder:14b` not following instructions reliably. If model is fixed, half this code disappears.
**Risk:** High. Don't remove before model is validated.

### [F3] `_MEMORY_RECALL` regex for intent detection — fundamentally unreliable
**Status:** pending
**Problem:** Regex can't detect intent. "What do you know about last Friday's meeting?" won't match. "Remember what I said last time?" might match `_MEMORY_SAVE` too. False positives + false negatives guaranteed at scale.
**Right fix:** LLM2 pre-flight classification (Router pattern). Deferred until LLM2 is fast enough.

### [F4] `qwen2.5-coder:14b` — wrong model variant for a companion app
**Status:** done ✓ (LLM1 → qwen2.5:14b, LLM2 → phi4-mini)
**Problem:** Coder variant is fine-tuned for code generation. Companion app needs general reasoning, instruction-following, conversation. Coder variant has weaker instruction-following for non-code tasks.
**Right fix:** Switch to `qwen2.5:14b` (base instruct). Or test `qwen2.5:32b` if VRAM allows.

---

## MEDIUM

### [F5] Auto-save creates model/reality sync gap
**Status:** skipped — eliminated entirely by LLM2 router (pre-flight save before LLM1 runs, result in context naturally). Adding synthetic injection now would be deleted in weeks.
**Problem:** Runtime saves to memory behind the model's back. Model's mental state is wrong — it thinks it didn't save, leading to double-saves or confused responses when user asks "did you save that?"
**Right fix:** After auto-save, inject a synthetic tool result message into the conversation so the model knows the save happened.

### [F6] `_PREMATURE_STOP` patterns too broad — false positives on valid responses
**Status:** done ✓ (via LLM2 supervisor rewrite — LLM2 now audits every turn with full rules document; regex is fallback only)
**Problem:** "Let me check that" flagged as premature stop. Valid mid-task narration triggers recovery loop. Adds a wasted LLM call and a confusing recovery prompt.
**Right fix:** Narrow patterns. Only flag cases where model is clearly announcing FUTURE intent without having done it, not mid-task commentary.

### [F7] Compression destroys early-session context — wrong compression target
**Status:** done ✓ (compress middle only; head=2 identity turns + tail=_WINDOW recent turns preserved)
**Problem:** Compressor summarises the OLDEST turns (turns 1-10). These are identity-establishing: user name, preferences, what the session is about. Should compress the MIDDLE (turns 11-N-6), preserve head + tail.
**Right fix:** Compress turns `[context_start : -_WINDOW]` — keep the first few turns and the rolling window. Discard the middle.

### [F8] Rolling window = 6 vs enormous system prompt — context budget problem
**Status:** done ✓
**Problem:** System prompt is ~1200 tokens. Rolling window = 6 pairs. On a 32k context model, 6 turns is fine. On an 8k model, 1200-token system prompt + 6 turns leaves almost nothing for tool results.
**Right fix:** Measure actual token budget. Raise window to 10-12 if context allows, or shrink system prompt.

---

## MINOR

### [F9] Memory duplication on recall requests
**Status:** pending
**Problem:** When `_MEMORY_RECALL` fires, memory is injected into the user message AND the model can call `search_memory()` tool — returning the same results twice. Wastes context.
**Right fix:** If memory was pre-injected, add a note to system prompt: "Memory already pre-fetched above. Do NOT call search_memory for this turn."

### [F10] Supervisor notes orphaned on final session turn
**Status:** done ✓ (flushed to Qdrant entry_type="llm1_behavior" on stop() — seeds Phase 2 behavioral memory)
**Problem:** `_supervisor_notes` are queued for the NEXT turn's system prompt. On the last turn of a session (before shutdown), notes are generated but never delivered — they vanish.
**Right fix:** On session end, flush pending supervisor notes to the session log or SQLite so they can be reviewed.

### [F11] Hardcoded Windows path example in system prompt
**Status:** done ✓  
**Problem:** FILE PATH RULES section still has a hardcoded Windows example even though `_ENV` now detects OS at runtime. Confuses the model on Linux/macOS.
**Right fix:** Generate the path example dynamically from `_ENV['os']` in `_build_system_awareness()`.

---

## Order of Attack

1. F11 — trivial, 5 min, pure win, good warm-up
2. F8 — measure context budget first, then adjust window
3. F6 — narrow premature stop patterns, run regression tests
4. F9 — suppress duplicate memory call with one line
5. F7 — fix compression target
6. F10 — flush supervisor notes on session end
7. F5 — inject synthetic tool result after auto-save
8. F4 — model swap (needs F1 fixed first or done together)
9. F1 — remove fallback parsers (requires F4 done + tested)
10. F2 — remove compensating guards (requires F1 + F4 validated)
11. F3 — LLM2 Router pattern (long-term, requires LLM2 speed improvement)
