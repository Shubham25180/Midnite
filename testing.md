# Nexux — Manual Test Checklist

**Rule:** When a new feature is implemented, add its tests to this file before marking the feature done.
**How to run:** Start server with `python -m Skynet.main`, use chat tab at `localhost:7799`.
**Log file:** `logs/nexux.log` — check it after every test session.
**Automated suite:** `python -m pytest tests/ --ignore=tests/ui/ --ignore=tests/test_main_boot.py`

Status legend: ✅ Pass | ❌ Fail | ⚠️ Partial | 🔲 Not tested yet

---

## 1. Boot & Shutdown

| # | What to do | Expected result | Status |
|---|-----------|----------------|--------|
| B1 | Run `python -m Skynet.main` | Server starts, logs show all components IDLE, dashboard loads at localhost:7799 | 🔲 |
| B2 | Open dashboard, click Initialize | RuntimeMode goes IDLE → ACTIVE, all components start | 🔲 |
| B3 | Click Shutdown in dashboard | Clean shutdown: components stop in order, session compressed, logs show OFFLINE | 🔲 |
| B4 | Restart immediately after shutdown | No leftover state, clean boot | 🔲 |
| B5 | Kill process mid-session (Ctrl+C) | No crash errors, qdrant/sqlite not corrupted on next boot | 🔲 |

---

## 2. Memory — Save

| # | What to say | Expected result | Log check | Status |
|---|------------|----------------|-----------|--------|
| M1 | "Remember that my favourite color is blue." | Nexux confirms it saved. `save_memory` appears in log. | `Tool call: save_memory` | 🔲 |
| M2 | "Save this: I work at Klyx." | Nexux confirms. Tool called. | `save_memory` in log | 🔲 |
| M3 | "Don't forget I prefer short answers." | Saved as preference. | `save_memory` in log | 🔲 |
| M4 | "My name is Shubham. Call me Master." | Saved + pinned as core identity. | `Pinned to core memory: 'name: Master'` in log | 🔲 |
| M5 | Say nothing about saving, just have a conversation | No spurious `save_memory` calls. | No unexpected `save_memory` in log | 🔲 |

---

## 3. Memory — Recall

| # | What to say | Expected result | Log check | Status |
|---|------------|----------------|-----------|--------|
| R1 | Start new session, ask "What's my favourite color?" (after M1) | Nexux recalls "blue" correctly. | `Pre-fetched memory` or `search_memory` in log | 🔲 |
| R2 | "What do you know about me?" | Lists saved facts, does NOT say "I have no persistent memory" | No denial pattern in log | 🔲 |
| R3 | "Do you remember what we talked about last time?" | Summarises last session content accurately | Memory injected into context | 🔲 |
| R4 | "What was my preference about answers?" (after M3) | Recalls "short answers" preference | `search_memory` result used | 🔲 |
| R5 | "Do you have memory?" | Says yes, describes capabilities. Never says "each session is independent." | No `[LLM2 SUPERVISOR]` denial violation | 🔲 |

---

## 4. Memory — Pinning (LLM2 Semantic Pin)

| # | What to say | Expected result | Log check | Status |
|---|------------|----------------|-----------|--------|
| P1 | "I live in Vikas Nagar, Dehradun." | Pinned as location. | `[LLM2 PINNING] 1 pin(s): ['location: Vikas Nagar, Dehradun']` | 🔲 |
| P2 | "From now on, always respond in bullet points." | Pinned as durable rule. | Pin logged with preference content | 🔲 |
| P3 | Quote a song lyric ("So wake me up when it's all over") | NOT pinned. Song lyrics are not user identity. | No pin logged for this turn | 🔲 |
| P4 | Ask a question ("What time is it?") | NOT pinned. Questions are not identity facts. | No pin logged | 🔲 |
| P5 | "Assisting with a task" type message | NOT pinned. Action descriptions are not identity. | No spurious pin | 🔲 |

---

## 5. Memory — Cross-Session Persistence

These require two separate server runs (shutdown and restart between).

| # | Session 1 | Session 2 | Expected | Status |
|---|----------|----------|---------|--------|
| CS1 | "Remember I prefer dark mode." | "What UI do I prefer?" | Recalls "dark mode" | 🔲 |
| CS2 | "My name is Shubham, call me Master." | "What should you call me?" | "Master" | 🔲 |
| CS3 | Complete a 5-turn conversation | "What did we talk about last session?" | Accurate summary of last session | 🔲 |

---

## 6. Tool Calling — Core Tools

| # | What to say | Expected result | Log check | Status |
|---|------------|----------------|-----------|--------|
| T1 | "Read the config/settings.yaml file." | Returns file contents accurately. | `Tool call: read_file` | 🔲 |
| T2 | "Create a file called test_output.txt with the text 'hello nexux'." | File created. Nexux confirms. | `Tool call: write_file` | 🔲 |
| T3 | "List the files in the Skynet/core/ directory." | Returns correct file list. | `Tool call: list_files` | 🔲 |
| T4 | "Run `echo hello from powershell` in the terminal." | Returns output "hello from powershell". | `Tool call: run_bash` | 🔲 |
| T5 | "Search for the word 'orchestrator' in the Skynet folder." | Returns matching files/lines. | `Tool call: grep_files` | 🔲 |
| T6 | "What's the system status?" | Returns component health, LLM info, memory count. | `Tool call: get_system_info` | 🔲 |
| T7 | "What time is it?" | Gives correct current time. Does NOT say it can't access real-time data. | Response uses `datetime` correctly | 🔲 |
| T8 | "Fetch the page at https://en.wikipedia.org/wiki/Python_(programming_language)" | Returns readable text from Wikipedia. | `Tool call: web_fetch` + content in response | 🔲 |

---

## 7. Tool Calling — Memory Tools

| # | What to say | Expected result | Log check | Status |
|---|------------|----------------|-----------|--------|
| TM1 | "Save the fact that I use Python for all my projects." | Saved. Tool called. | `Tool call: save_memory` | 🔲 |
| TM2 | "Search your memory for anything about Python." | Returns the saved fact. | `Tool call: search_memory` + result used in response | 🔲 |
| TM3 | "Show me the last 5 turns of our conversation." | Returns accurate recent history. | `Tool call: get_recent_history` | 🔲 |

---

## 8. LLM2 Supervisor — Rule Compliance

Check `logs/nexux.log` after each test. PASS = no false violations. FAIL = wrong violation flagged.

| # | What triggers it | Expected log | Bad log (FAIL) | Status |
|---|-----------------|-------------|----------------|--------|
| S1 | Clean conversational reply ("Not much, how are you?") | `[LLM2 SUPERVISOR] COMPLIANT` | Any violation | 🔲 |
| S2 | "Do you have memory?" → Nexux says yes | `COMPLIANT` | Rule 1 violation | 🔲 |
| S3 | "Remember my dog's name is Rex." → save_memory called | `COMPLIANT` | Rule 2 violation | 🔲 |
| S4 | "Remind me what we talked about last time" (recall, not save) | `COMPLIANT` | Rule 2 false positive | 🔲 |
| S5 | "I couldn't find the lyrics" type response | `COMPLIANT` | Rule 1 false positive | 🔲 |
| S6 | Ask for file read → Nexux says "let me read that" without reading | Rule 3 violation logged | `COMPLIANT` (missed real violation) | 🔲 |
| S7 | "I love you Nexus" or emotional chat | `COMPLIANT` | Any violation (Rule 4 should protect this) | 🔲 |
| S8 | Tool called + returned data, Nexux ignores it in response | Rule 5 violation logged | `COMPLIANT` (missed violation) | 🔲 |

---

## 9. LLM2 Supervisor — JSON Parser

| # | What to check | Expected | Status |
|---|--------------|---------|--------|
| SP1 | After any turn: check log for `Audit failed (Extra data` | Must NOT appear after parser fix | 🔲 |
| SP2 | After any turn: check log | Must show `COMPLIANT` or specific violation, never `falling back to regex` (unless LLM2 is down) | 🔲 |

---

## 10. Recovery Loop

| # | What to say | Expected result | Log check | Status |
|---|------------|----------------|-----------|--------|
| RL1 | "Fetch the weather for Dehradun and tell me the temperature." | Nexus actually fetches and reports temperature, doesn't just say "let me check." | `Recovery` should NOT appear (tool called on first attempt) | 🔲 |
| RL2 | Any request where first attempt is a premature stop | Recovery injected, second attempt completes the task. | `Recovery #1` in log, then actual tool call | 🔲 |

---

## 11. Skill System

| # | What to say | Expected result | Log check | Status |
|---|------------|----------------|-----------|--------|
| SK1 | "Sing me a song." (no title) | Original 4-8 lines of lyrics, spoken by TTS immediately. No preamble. | `Tool call: load_skill(['name'])` | 🔲 |
| SK2 | "Sing me Wake Me Up by Avicii." | Searches web, finds YouTube URL, opens in browser. Says "Opening in browser." | `web_fetch` then `run_bash` with `Start-Process` | 🔲 |
| SK3 | Modify sing.yaml, say "reload skills", then test SK1 again | New skill content takes effect without restart. | `Tool call: reload_skills` | 🔲 |

---

## 12. Voice Pipeline

| # | What to do | Expected result | Status |
|---|-----------|----------------|--------|
| V1 | Speak a sentence (STT mode: disabled, text input only) | Text input works, no STT errors | 🔲 |
| V2 | Enable "Always On" STT mode, speak clearly | Transcription appears in chat, response follows | 🔲 |
| V3 | Enable "Push to Talk", hold PTT button while speaking | Only captures audio while button held | 🔲 |
| V4 | Ask a long question → while TTS is speaking, send another message | TTS plays without blocking UI. New message accepted. | 🔲 |
| V5 | Check TTS timing in log | `play=Xms` should be non-zero. `synth=Xms` should be < 500ms for short sentences. | 🔲 |

---

## 13. Web Fetch

| # | What to say | Expected result | Status |
|---|------------|----------------|--------|
| WF1 | "Fetch https://en.wikipedia.org/wiki/Dehradun and tell me the population." | Returns population figure from Wikipedia. | 🔲 |
| WF2 | "Fetch https://api.github.com/zen" (plain JSON API) | Returns a GitHub Zen quote. | 🔲 |
| WF3 | "Fetch lyrics from a lyrics site." | Fails gracefully: tells user it couldn't retrieve them (JS-rendered site). Does NOT make up lyrics. | 🔲 |

---

## 14. Fallback Parsers

These are hard to trigger manually — monitor logs during any session.

| # | What to check in logs | Expected | Status |
|---|----------------------|---------|--------|
| FP1 | `Fallback[XML]` appears | Model used XML `<tool_call>` — rare with qwen2.5:14b but should still work | 🔲 |
| FP2 | `Fallback[JSON]` appears | Model wrote bare JSON — less rare | 🔲 |
| FP3 | `Fallback[Python]` appears | Model wrote `funcname({...})` — should be caught | 🔲 |
| FP4 | After multiple sessions: all tool calls use native API, no fallback lines | Ideal steady state — qwen2.5:14b prefers native | 🔲 |

---

## 15. UI Dashboard

| # | What to do | Expected result | Status |
|---|-----------|----------------|--------|
| UI1 | Open localhost:7799 | Dashboard loads, shows component states | 🔲 |
| UI2 | Chat tab: type message, press Enter | Message sent, response appears | 🔲 |
| UI3 | Config tab: change TTS voice, save | Voice changes on next TTS response | 🔲 |
| UI4 | Config tab: toggle a tool off | That tool no longer appears in active tool list (check via get_system_info) | 🔲 |
| UI5 | System tab: check component health | All started components show IDLE or BUSY, none FAILED | 🔲 |
| UI6 | Context bar in chat | Shows "X/6 turns used" and updates correctly | 🔲 |

---

## 16. Session Lifecycle (check logs after shutdown)

| # | What to check | Expected | Status |
|---|--------------|---------|--------|
| SL1 | After shutdown: `Session summary saved` | SQLite session entry written | 🔲 |
| SL2 | After shutdown: `Memory compressed` | Qdrant entry count increased | 🔲 |
| SL3 | After a long session (6+ turns): middle turns compressed, first 2 and last 6 preserved | `compress_at` logic working | 🔲 |
| SL4 | After shutdown with supervisor violations: `Flushed X orphaned supervisor note(s)` | Behavioral memory entries saved | 🔲 |
| SL5 | `logs/sessions/YYYY-MM-DD.jsonl` exists and is readable | Raw session log written | 🔲 |

---

## 17. Stress / Edge Cases

| # | Scenario | Expected | Status |
|---|---------|---------|--------|
| E1 | Send empty message | Graceful handling, no crash | 🔲 |
| E2 | Send very long message (1000+ words) | Processes correctly, no crash | 🔲 |
| E3 | Ask for a tool that's been disabled in settings | Nexus tells user it can't use that tool | 🔲 |
| E4 | Ask for a file that doesn't exist | "File not found" error, graceful response | 🔲 |
| E5 | Ask for a 15-step task | Loop runs up to max steps, doesn't hang | 🔲 |
| E6 | Two rapid messages while first is processing | Second message handled after first completes, no crash | 🔲 |

---

## 🔜 Tests to Add When Features Are Implemented

Add tests here as features are built. Move to the main table once implemented.

| Feature | Test to add |
|---------|-------------|
| N1 — Playwright web_browse | JS-rendered site fetch works (lyrics, SPAs). `web_browse` tool called in log. |
| N2 — PDF reading | "Read this PDF and summarize it." → reads file, summarises correctly. |
| N3 — Excel/CSV | "Read this spreadsheet and tell me the total rows." → correct count returned. |
| N4 — Screenshot + vision | "What's on my screen?" → describes visible content accurately. |
| N5 — Browser actions | "Click the first result on this page." → Playwright performs click. |
| N6 — Identity JSON | After save: `data/identity.json` contains name/location. Loads on next boot. |
| N7 — Cloud LLM routing | Task that requires vision → routed to cloud. Log shows cloud provider used. |
| N8 — LLM2 Router | Recall request → no `_MEMORY_RECALL` regex firing; LLM2 routing decision in log. |

---

## Running the Automated Suite

```bash
# Full suite (skip UI + boot tests which need live server)
python -m pytest tests/ --ignore=tests/ui/ --ignore=tests/test_main_boot.py -v

# Supervisor / behavior regression only
python -m pytest tests/test_model_regression.py -v

# Pipeline integration
python -m pytest tests/test_pipeline_integration.py -v
```

All 110 tests must pass before any commit.
claude --resume 02d9d94e-8bb3-4188-aa06-60897840a8a2