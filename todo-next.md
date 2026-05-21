# Nexux — Next Implementation Targets

Current status: **V0.2 live** (110 tests passing, 2026-05-21)
Next milestone: **V0.3 — Desktop Cognition Layer**

Items are ordered by impact. Do not start a section until the previous one is stable.

---

## SECTION 1 — Close V0.2 Gaps (finish what was promised)

V0.2 shipped the provider and skill architecture but left three skills unbuilt.
These block V0.3 and are prerequisites for browser automation.

---

### [N1] Playwright web_browse tool
**Priority:** CRITICAL — blocks V0.3, fixes current web scraping failures
**What:** A `web_browse(url, extract)` tool backed by Playwright (headless Chromium).
Executes JS, waits for page render, extracts text/HTML. Replaces web_fetch for dynamic sites.
**Why:** web_fetch is a plain HTTP GET. Every JS-rendered site (lyrics, dashboards, SPAs) returns
empty content. Playwright fixes this permanently.
**Implementation:**
- `pip install playwright && playwright install chromium`
- New tool: `web_browse(url: str, selector: str = None) -> str`
- Returns rendered page text, optionally filtered by CSS selector
- web_fetch stays for simple/static fetches (faster, no browser overhead)
- Add to TOOL_DEFINITIONS and executor.py
**Complexity:** Medium (2-3 hours)

---

### [N2] PDF reading tool
**Priority:** HIGH — v0.2 spec item, high daily utility
**What:** `read_pdf(path: str, pages: str = "all") -> str` tool.
Extracts text from local PDF files. Handles multi-page, returns clean text.
**Why:** V0.2 promised pdf_skill. Common real use: invoices, reports, manuals.
**Implementation:**
- `pip install pymupdf` (fitz) — fastest, best quality PDF text extraction
- New tool: `read_pdf(path, pages="all")` — pages can be "all", "1-5", "3"
- Add to TOOL_DEFINITIONS and executor.py
- Add pdf_skill.yaml that instructs model to use read_pdf then summarize
**Complexity:** Low (1-2 hours)

---

### [N3] Excel/CSV skill + tool
**Priority:** MEDIUM — v0.2 spec item
**What:** `read_spreadsheet(path: str, sheet: str = None) -> str` tool.
Reads .xlsx, .xls, .csv and returns structured text (table preview + stats).
**Why:** V0.2 promised excel_skill. Needed for v0.4 workflow automation.
**Implementation:**
- `pip install openpyxl` (already likely installed)
- New tool: `read_spreadsheet(path, sheet=None, max_rows=100)`
- Returns: column names + first N rows as text + row/column count
- Add excel_skill.yaml for analysis and editing instructions
**Complexity:** Low (1-2 hours)

---

## SECTION 2 — V0.3 Desktop Cognition Layer

After N1-N3 are stable, this is the next major milestone.
V0.3 makes Nexux visually aware of the desktop.

---

### [N4] Screenshot capture + vision tool
**Priority:** HIGH — core of V0.3
**What:** `take_screenshot(region: str = "full") -> str` tool that captures the screen
and passes it to a vision-capable model for description/analysis.
**Why:** "Read this error", "what's on my screen", "fill this form" — all require vision.
Without it, Nexux is blind to the desktop.
**Implementation:**
- `pip install mss` for fast screen capture
- Screenshot saved to temp file, passed to vision model
- If LLM1 is a local model without vision: route screenshot to cloud (Claude/GPT-4o)
- This is the first point where the cloud escalation path becomes necessary
- Add vision_tool.yaml skill with instructions for screen reading tasks
**Complexity:** Medium-High (3-5 hours, more if cloud routing is needed first)
**Blocker:** Requires cloud provider path (see N7) OR a local vision model

---

### [N5] Browser automation tool (Playwright — extend N1)
**Priority:** HIGH — V0.3 browser awareness
**What:** Extend Playwright tool from N1 to support interaction, not just reading.
`browser_action(action: str, selector: str = None, value: str = None) -> str`
Actions: click, type, scroll, wait, get_text, fill_form
**Why:** "Fill this form", "click the submit button", "navigate to X" require interaction.
web_browse (N1) only reads — this adds writes.
**Implementation:**
- Reuse the Playwright browser instance from N1 (persistent session)
- New tool: `browser_action(action, selector, value, url=None)`
- Implement: click, type, navigate, wait_for_selector, get_page_text
- Add browser_skill.yaml with instructions for automation tasks
**Complexity:** High (4-6 hours)
**Blocker:** N1 must be done first

---

## SECTION 3 — Cognitive State Manager Completion (V0.5 memory work)

The 5-layer cognitive state manager is the architecture vision in CLAUDE.md.
Layer 2-4 are partially implemented. Layers 1 and 5 are missing.

---

### [N6] Identity JSON blob — complete Layer 1
**Priority:** HIGH — pins are in Qdrant but no structured identity file
**What:** `data/identity.json` — a structured JSON blob that holds pinned identity state.
Written by semantic pinning, read at every session start, injected before system prompt.
**Why:** Currently pins go to Qdrant as "core" entries and have to be searched.
Identity should be instant-access at startup — name, location, preferences, rules.
It should never be compressed or evicted.
**Implementation:**
- Schema: `{"user": "Shubham", "alias": "Master", "location": "Vikas Nagar, Dehradun", "preferences": [], "rules": []}`
- `vector_store.store()` for "core" entries: also write to identity.json
- Orchestrator reads identity.json at start and prepends to system prompt as structured block
- UI: show identity.json contents in a new "Identity" card on dashboard
**Complexity:** Medium (2-3 hours)

---

### [N7] Cloud LLM path — runtime provider switching
**Priority:** HIGH — needed for N4 (vision) and V0.8 cloud escalation
**What:** The ability to switch LLM1 to a cloud provider (Claude API / OpenRouter)
at runtime, not just at config restart. Also: per-request cloud escalation.
**Why:** Vision requires a multimodal model. Local qwen2.5:14b has no vision.
Cloud escalation (V0.8) requires routing logic to decide local vs cloud per request.
**Implementation:**
- ClaudeProvider already exists — wire it to the provider registry properly
- Add `escalate_to_cloud(reason: str)` as an internal orchestrator signal
- Settings UI: "Cloud LLM" section with API key input + model selector
- Routing logic: if request requires vision OR complexity_score > threshold → cloud
- Cost guard: log every cloud call with token count to prevent runaway spend
**Complexity:** Medium (3-4 hours for basic routing, more for smart routing)

---

### [N8] LLM2 Router Phase 1 — replace _MEMORY_RECALL regex
**Priority:** MEDIUM — eliminates the biggest documented hack in the codebase
**What:** Before LLM1 sees the user message, LLM2 runs a fast routing decision:
should memory be pre-fetched? What type? What tools will likely be needed?
Returns a small JSON. Orchestrator injects the result. Replaces _MEMORY_RECALL regex.
**Why:** The regex is documented as a hack. It fires false positives, misses non-obvious
recall requests, and has to be maintained manually. LLM2 understands intent.
**Prerequisite:** LLM2 supervisor must be stable across 10+ sessions first.
**Complexity:** Medium (3-4 hours)

---

### [N9] Execution state — Layer 5
**Priority:** LOW — deferred until Layers 1-4 are solid
**What:** What task is currently active, what's pending, what was interrupted.
Survives session end — if Nexux is restarted mid-task, it knows where it stopped.
**Why:** Needed for multi-session task continuity.
**Implementation:** `data/execution_state.json` — written on every task start/end,
read at session start, injected as context if an active task exists.
**Complexity:** Medium

---

## SECTION 4 — Code Cleanup (from todo-fixes.md)

These are pending from the original audit. Do them between sections, not as a block.

---

### [N10] Remove XML + JSON fallback parsers (F1)
**Status:** Safe to do now — qwen2.5:14b confirmed native tool calling across multiple sessions.
**What:** Delete `_parse_xml_tool_calls()`, `_parse_text_tool_calls()`, Python fallback.
Keep only native API tool calling.
**Risk:** If model regresses, tool calls will silently fail. Run full regression suite first.
**Gate:** Needs 5+ more sessions of clean native tool calling in logs before removing.

---

### [N11] Remove denial gate + supervisor compensating code (F2)
**Status:** Not ready — needs more live sessions to validate qwen2.5:14b behavior.
**Gate:** After N10 is done and stable across 10+ sessions.

---

### [N12] Replace _MEMORY_RECALL regex with LLM2 Router (F3)
**Status:** Same as N8 above.

---

## SECTION 5 — V0.8 Cloud Escalation Path

Partially covered by N7. Full V0.8 requires:

- [ ] Cost-aware routing (track token spend, set per-session budget)
- [ ] Privacy-aware routing (flag local-only requests, never send to cloud)
- [ ] Complexity classifier (LLM2 rates request complexity → route decision)
- [ ] Fallback logic (cloud unavailable → degrade gracefully to local)
- [ ] OpenRouter integration (multi-provider cloud access via one API key)

This is a standalone milestone, not a single feature. Don't start until N4 proves
the cloud path works end-to-end for vision.

---

## Order of Attack

```
N2  → PDF tool         (1-2h, quick win, v0.2 closure)
N3  → Excel tool       (1-2h, quick win, v0.2 closure)
N1  → Playwright       (2-3h, critical capability unblock)
N6  → Identity JSON    (2-3h, Layer 1 completion)
N5  → Browser actions  (4-6h, needs N1)
N7  → Cloud path       (3-4h, needed for vision)
N4  → Screenshot+vision (3-5h, needs N7)
N8  → LLM2 Router      (3-4h, needs supervisor stable)
N10 → Remove fallbacks  (1h, needs session validation)
N9  → Execution state  (medium, after Layer 1-4 solid)
N11 → Remove guards     (after N10)
```

---

## What NOT to do next

- Do NOT start v0.4 (Workflow Engine) before v0.3 (Desktop Cognition) is solid.
- Do NOT add MCP client support yet — our tool system already covers the use cases.
  Revisit when there are specific MCP servers worth integrating.
- Do NOT build habit memory / behavioral patterns yet — needs 20+ real sessions of data first.
- Do NOT attempt N11 before multiple sessions confirm model stability.
