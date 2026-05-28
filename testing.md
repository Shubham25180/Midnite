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

## 18. PDF Reading (N2)

| # | What to say | Expected result | Log check | Status |
|---|------------|----------------|-----------|--------|
| PD1 | "Read this PDF: [path to text-based PDF]" | Returns extracted text, no OCR | `Tool call: read_pdf` + `method=text extraction` in output | 🔲 |
| PD2 | "Read this PDF: [path to scanned/image PDF]" | Falls back to vision OCR, returns readable text | `method=vision OCR` in output header | 🔲 |
| PD3 | "Read pages 1-3 of [PDF]" | Returns only those pages | `pages=1-3` in output | 🔲 |
| PD4 | "Summarize this PDF" | Reads and summarises content correctly | `read_pdf` called, summary makes sense | 🔲 |
| PD5 | "Read [non-existent.pdf]" | Graceful "File not found" | No crash | 🔲 |

---

## 19. Excel / CSV Reading (N3)

| # | What to say | Expected result | Log check | Status |
|---|------------|----------------|-----------|--------|
| XL1 | "Read this CSV: [path.csv]" | Returns columns + row count + data preview | `Tool call: read_spreadsheet` | 🔲 |
| XL2 | "Read this Excel file: [path.xlsx]" | Returns sheet name, columns, row count, preview | `Tool call: read_spreadsheet` | 🔲 |
| XL3 | "Read the 'Sales' sheet from [path.xlsx]" | Returns correct sheet, not default | correct sheet name in response | 🔲 |
| XL4 | "How many rows does this spreadsheet have?" | Reports correct total row count | Correct number | 🔲 |
| XL5 | "Read [non-existent.xlsx]" | Graceful "File not found" | No crash | 🔲 |

---

## 20. Playwright web_browse (N1)

| # | What to say | Expected result | Log check | Status |
|---|------------|----------------|-----------|--------|
| WB1 | "Fetch https://example.com using web_browse" | Returns "Example Domain" text | `Tool call: web_browse` | 🔲 |
| WB2 | "Get the lyrics for [song] from a lyrics site" | Returns actual lyrics (not empty content) | `web_browse` used, lyrics in response | 🔲 |
| WB3 | "Fetch [SPA or JS-heavy site]" | Returns rendered content (not blank) | `web_browse` returns text web_fetch wouldn't | 🔲 |
| WB4 | "Fetch https://example.com using the selector 'h1'" | Returns only the h1 text | `selector=h1` in response header | 🔲 |
| WB5 | "Fetch [invalid-url]" | Graceful error message | No crash | 🔲 |
| WB6 | Shut down Nexux after a web_browse call | No Chromium process left hanging | No orphan process in Task Manager | 🔲 |

---

## 21. Screenshot + Vision (N4)

| # | What to say | Expected result | Log check | Status |
|---|------------|----------------|-----------|--------|
| SC1 | "What's on my screen?" | Describes visible windows, text, content accurately | `Tool call: take_screenshot` | 🔲 |
| SC2 | "Read the error message on screen" | Returns the exact error text visible | Vision model output includes error text | 🔲 |
| SC3 | "What form fields are visible?" | Lists form inputs, labels, placeholders | Accurate field names returned | 🔲 |
| SC4 | "Describe what's on my screen" (nothing open) | Describes desktop/taskbar correctly | No crash on minimal screen content | 🔲 |
| SC5 | Check log after SC1 | Shows screenshot resolution and KB size | `Screenshot captured: WxH px (N KB)` in log | 🔲 |

---

## 22. Identity JSON — Layer 1 Cognitive State (N6)

| # | What to do | Expected result | Log check | Status |
|---|-----------|----------------|-----------|--------|
| ID1 | Say "My name is Shubham and I'm building Nexux." | LLM2 pins fact; `data/identity.json` contains the entry on disk | `Identity JSON updated` in log | 🔲 |
| ID2 | Say "From now on always respond concisely." | Rule pinned; `data/identity.json` gains a new entry | Log shows new pin + identity write | 🔲 |
| ID3 | Restart server; check first prompt | "PINNED IDENTITY" block appears in log's system prompt preview (`/api/debug/prompt`) | Block is at the TOP of the system prompt | 🔲 |
| ID4 | After ID1 + restart, ask "What is my name?" | Answers "Shubham" without calling `search_memory` — comes from identity block | No `search_memory` call in log | 🔲 |
| ID5 | Same fact said twice (e.g. "I'm Shubham" on two sessions) | `identity.json` still has only ONE entry for that fact (dedup working) | File has no duplicates | 🔲 |

---

## 23. Browser Action — Approach A + B (N5)

| # | What to say | Expected result | Log check | Status |
|---|-----------|----------------|-----------|--------|
| BA1 | "Go to https://example.com using browser_action" | Navigated; title returned | `browser_action navigate` in log | 🔲 |
| BA2 | After BA1: "Get a snapshot of the page" | Accessibility tree dumped — shows heading, link, paragraph roles | `Tool call: browser_action` with `get_snapshot` | 🔲 |
| BA3 | After BA1: "Click the 'More information...' link" | Link clicked via text match (Approach A). Page navigates. | `browser_action click [A/exact-text]` or `partial-text` | 🔲 |
| BA4 | "Type 'nexux' into the search box on https://duckduckgo.com" | Navigates → finds input → types text (Approach A css/role) | `browser_action type [A/...]` in log | 🔲 |
| BA5 | Navigate to a page with an element that has no accessible label → click it | Approach A fails, Approach B (vision) kicks in. Click lands at correct coordinates. | `Approach A click failed` then `Approach B click at` in log | 🔲 |
| BA6 | "Take a screenshot of the current browser page and describe it" | Browser page screenshotted (not desktop), analyzed by qwen2.5vl | `browser_action screenshot` + vision output in response | 🔲 |
| BA7 | "Scroll down on the current page" | Page scrolls down 400px | `browser_action scroll: down` | 🔲 |
| BA8 | "Wait for the element '.results' to appear" | Waits up to 15s for selector | `browser_action wait` returns "Element appeared" or timeout | 🔲 |
| BA9 | Shut down Nexux after browser_action use | Persistent page + browser closed cleanly, no orphan Chromium | No orphan process in Task Manager | 🔲 |

---

## 🔜 Tests to Add When Features Are Implemented

Add tests here as features are built. Move to the main table once implemented.

| Feature | Test to add |
|---------|-------------|
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