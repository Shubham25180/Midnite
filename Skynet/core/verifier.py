"""
Skynet/core/verifier.py

Tool result grading — distinguishes "tool executed" from "result was useful".
Adds runtime annotations the LLM can act on when results are empty or failed.
Also runs deterministic post-write checks (syntax, YAML validity).
LLM2 supervisor: post-turn audit that catches denial patterns and rule violations.
"""
from __future__ import annotations

import logging
import re
import subprocess
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(".")
_LLM2: "LLMProvider | None" = None   # set via register_verifier_model()

# Patterns where LLM1 falsely claims it has no capabilities
_DENIAL_PATTERNS = re.compile(
    r"\b(no (persistent |long.?term )?memory|can'?t (save|store|remember|recall)|"
    r"no (built.?in |training )?mechanism|(outside|beyond) (this )?conversation|"
    r"each session is independent|i don'?t have (the )?(ability|capability|access)|"
    r"training data|not (able|designed) to (save|remember|store|recall))\b",
    re.IGNORECASE,
)
_SAVE_REQUEST = re.compile(
    r"\b(save (this|that|it)|remember (this|that|these)|store (this|that)|"
    r"keep (this|that)|note (this|that|down)|don't forget|add .{0,20} to memory)\b",
    re.IGNORECASE,
)
# Request is clearly asking the AI to RETRIEVE, not store — used to suppress Rule 2 false positives
_RECALL_ONLY = re.compile(
    r"\b(do you remember|what do you (know|remember)|do you have (any )?memory|"
    r"recall (last|previous|our)|what was (the )?last|what have we|"
    r"any context (of|from)|last (session|time|conversation))\b",
    re.IGNORECASE,
)
# Patterns for pins that are NOT user identity facts (actions, events, system status)
_PIN_REJECT = re.compile(
    r"\b(file (created|written|saved|read|updated|deleted)|"
    r"system (status|operating|normal|ready)|"
    r"task (done|complete|finished|completed)|"
    r"currently (working|running|operating)|"
    r"page (fetched|loaded|retrieved)|"
    r"(created|saved|fetched|written|loaded):)\b",
    re.IGNORECASE,
)


def register_verifier_model(provider: "LLMProvider | None") -> None:
    """Wire the cheap supervisory model. Called from main.py after LLM2 is constructed."""
    global _LLM2
    _LLM2 = provider
    model = getattr(provider, "model", "?") if provider else None
    if provider:
        logger.info("[LLM2] Supervisor registered: %s / %s", type(provider).__name__, model)
    else:
        logger.info("[LLM2] Supervisor disabled (no provider)")


class Grade(str, Enum):
    USEFUL = "USEFUL"
    EMPTY = "EMPTY"       # tool ran, result has no actionable content
    FAILED = "FAILED"     # tool indicated error / non-zero exit
    INVALID = "INVALID"   # post-write check: syntax or schema error


def grade_and_annotate(name: str, args: dict, result: str) -> tuple[str, Grade]:
    """
    Grade a tool result and return (annotated_result, grade).
    The annotated result is what gets injected back into the LLM context.
    USEFUL results are returned unchanged.
    """
    stripped = result.strip()

    # ── Empty / not-found results ──────────────────────────────────────────────
    if not stripped or stripped == "(empty)":
        annotation = (
            f"[RUNTIME: EMPTY — {name}() returned nothing. "
            "The path may be wrong or the directory/file truly has no content. "
            "Try a different path or verify with run_bash('ls <path>').]"
        )
        logger.warning("Tool result EMPTY: %s(%s)", name, args)
        return f"{result}\n{annotation}", Grade.EMPTY

    if stripped.startswith("File not found:") or stripped.startswith("Directory not found:"):
        annotation = (
            "[RUNTIME: NOT FOUND — check the path. "
            "Use list_files('.') to see the project root, "
            "then navigate with relative paths like 'docs/' or 'Skynet/core/'.]"
        )
        logger.warning("Tool result NOT FOUND: %s(%s)", name, args)
        return f"{result}\n{annotation}", Grade.FAILED

    # ── Blocked / error ────────────────────────────────────────────────────────
    if stripped.startswith("BLOCKED:") or stripped.startswith("Tool error:"):
        logger.warning("Tool result BLOCKED/ERROR: %s(%s)", name, args)
        return result, Grade.FAILED

    # ── run_bash: non-zero exit with no output ─────────────────────────────────
    if name == "run_bash" and "(exit " in stripped and ", no output)" in stripped:
        annotation = (
            "[RUNTIME: COMMAND FAILED — non-zero exit code. "
            "Check the command syntax or use run_bash('echo %ERRORLEVEL%') to inspect.]"
        )
        logger.warning("Tool result FAILED (non-zero exit): run_bash(%s)", args.get("command", "")[:80])
        return f"{result}\n{annotation}", Grade.FAILED

    # ── Post-write verifiers ───────────────────────────────────────────────────
    if name == "write_file":
        path = args.get("path", "")
        annotation, grade = _verify_written_file(path)
        if annotation:
            logger.warning("Post-write check FAILED: %s — %s", path, annotation[:120])
            return f"{result}\n\n{annotation}", grade

    return result, Grade.USEFUL


def _verify_written_file(path: str) -> tuple[str, Grade]:
    """Run deterministic checks after write_file. Returns (annotation, grade) or ('', USEFUL)."""
    if not path:
        return "", Grade.USEFUL

    full = (_PROJECT_ROOT.resolve() / path).resolve()
    if not full.exists():
        return "", Grade.USEFUL

    suffix = Path(path).suffix.lower()

    # Python syntax check
    if suffix == ".py":
        result = subprocess.run(
            ["python", "-m", "py_compile", str(full)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            err = (result.stderr or result.stdout).strip()
            return (
                f"[RUNTIME: SYNTAX ERROR in '{path}']\n{err}\n"
                "[Action required: fix the syntax error and call write_file() again with corrected code.]",
                Grade.INVALID,
            )

    # YAML validity check (skills, configs)
    elif suffix in (".yaml", ".yml"):
        try:
            import yaml
            with open(full, encoding="utf-8") as f:
                yaml.safe_load(f)
        except Exception as exc:
            return (
                f"[RUNTIME: YAML ERROR in '{path}']\n{exc}\n"
                "[Action required: fix the YAML syntax and call write_file() again.]",
                Grade.INVALID,
            )

    # JSON validity check
    elif suffix == ".json":
        import json
        try:
            with open(full, encoding="utf-8") as f:
                json.load(f)
        except json.JSONDecodeError as exc:
            return (
                f"[RUNTIME: JSON ERROR in '{path}']\n{exc}\n"
                "[Action required: fix the JSON and call write_file() again.]",
                Grade.INVALID,
            )

    return "", Grade.USEFUL


# ── Semantic pinning ──────────────────────────────────────────────────────────

_PINNING_PROMPT = """\
You are a memory classifier for a persistent AI companion.
Extract DURABLE identity/preference facts from the user's message to store in long-term memory.

PIN these types ONLY:
- Name / identity: "my name is...", "call me...", "I am a [role/title]..."
- Location: "I live in...", "I'm based in...", "my city is..."
- Preference / rule: "always...", "never...", "I prefer...", "from now on...", "every time you..."
- Long-term goal: "I want to build...", "our product is...", "the goal is..."

Do NOT pin:
- Questions of any kind
- Current task or what the assistant is doing right now
- Temporary context ("right now", "today", "for this session")
- Descriptions of the assistant's actions ("assisting with...", "helping with...", "working on...")
- Song lyrics, poetry, or any text the user is quoting from an external source
- Content that belongs to a creative work, not a personal statement about the user
- Generic phrases that are not facts about the USER

Examples that should NOT be pinned:
"Assisting with geographic query" → NO (describes action, not user)
"User asked about weather" → NO (event, not identity)
"So wake me up when it's all over, when I'm wiser when I'm older" → NO (song lyric, not preference)
"I prefer wisdom with age" → NO (inferred from a song lyric, not a user statement)

Return ONLY valid JSON:
{"pins": ["short fact 1", "short fact 2"]}
If nothing pinnable: {"pins": []}
Each pin must be under 20 words, written as a fact about the user, self-contained.

CRITICAL — use plain, simple language. Copy the user's own words as closely as possible.
Do NOT use synonyms, paraphrases, or fancy vocabulary.
GOOD: User prefers coffee over tea
BAD:  Preference for caffeine in brewed form rather than herbal beverage
GOOD: User's preferred title is Master
BAD:  My name is... Master
GOOD: User plays Apex Legends on PC
BAD:  User's recreational activity involves a battle royale first-person shooter"""


def _is_valid_pin(pin: str) -> bool:
    """Deterministic post-filter: reject pins that are actions/events/status, not user facts."""
    words = pin.split()
    if len(words) < 3:
        return False
    return not _PIN_REJECT.search(pin)


def semantic_pin_check(user_message: str) -> list[str]:
    """Ask LLM2 to extract pinnable identity/preference/goal facts from user message.
    Returns list of strings to store as core memory entries."""
    if _LLM2 is None or not user_message.strip():
        return []
    import json as _json
    try:
        result = _LLM2.complete([
            {"role": "system", "content": _PINNING_PROMPT},
            {"role": "user", "content": user_message[:600]},
        ]).strip()
        start, end = result.find("{"), result.rfind("}") + 1
        if start == -1 or end == 0:
            return []
        data = _json.loads(result[start:end])
        raw_pins = [p.strip() for p in data.get("pins", []) if isinstance(p, str) and p.strip()]
        pins = [p for p in raw_pins if _is_valid_pin(p)]
        if len(raw_pins) != len(pins):
            rejected = [p for p in raw_pins if not _is_valid_pin(p)]
            logger.info("[LLM2 PINNING] Filtered %d non-identity pin(s): %s", len(rejected), rejected)
        if pins:
            logger.info("[LLM2 PINNING] %d pin(s) detected: %s", len(pins), pins)
        return pins
    except Exception as exc:
        logger.debug("Semantic pin check failed: %s", exc)
        return []


# ── Semantic completion check ─────────────────────────────────────────────────

_PREMATURE_STOP_PATTERNS = (
    "let me", "i'll", "i will", "shall i", "how does that sound",
    "want me to", "should i proceed", "i'll check", "let me look",
    "i'll read", "let me read", "i'll run", "let me run",
)


def is_task_complete(original_request: str, model_response: str) -> tuple[bool, str]:
    """
    Determine whether the model actually completed the task.

    Fast path: regex scan. Only calls LLM2 when the regex finds a premature-stop signal.
    This avoids adding a round-trip for clean conversational replies.

    Returns (complete: bool, reason: str).
    """
    if not model_response.strip():
        return False, "empty response"

    # Pre-filter: check for premature-stop phrases
    lower = model_response.lower()
    suspicious = next((p for p in _PREMATURE_STOP_PATTERNS if p in lower), None)

    if suspicious is None:
        # No signal — assume complete without calling LLM2
        return True, "no premature-stop patterns"

    if _LLM2 is not None:
        # Ambiguous response — escalate to cheap model for a real verdict
        return _semantic_check(original_request, model_response)

    # LLM2 not configured — trust the regex finding
    return False, f"premature stop pattern: '{suspicious}'"


def _semantic_check(request: str, response: str) -> tuple[bool, str]:
    """Ask the cheap supervisory model whether the task was completed."""
    prompt = (
        "You are a task completion checker. Reply with YES or NO followed by one short sentence.\n\n"
        f"User request: {request[:400]}\n\n"
        f"Agent response: {response[:600]}\n\n"
        "Did the agent fully complete the requested task?\n"
        "YES = task is done, user has a complete answer or the action was taken.\n"
        "NO  = agent described what to do but didn't do it, or clearly left work unfinished."
    )
    try:
        result = _LLM2.complete([{"role": "user", "content": prompt}]).strip()
        complete = result.upper().startswith("YES")
        logger.info("[LLM2] Completion check → %s | %s", "COMPLETE" if complete else "INCOMPLETE", result[:80])
        return complete, result
    except Exception as exc:
        logger.warning("[LLM2] Completion check failed (%s) — falling back to heuristic", exc)
        lower = response.lower()
        for phrase in _PREMATURE_STOP_PATTERNS:
            if phrase in lower:
                return False, f"premature stop pattern: '{phrase}'"
        return True, "heuristic fallback"


_SUPERVISOR_RULES = """You are a supervisor auditing an AI assistant called Nexus.
Evaluate the interaction below against all 5 rules.

RULES:

RULE 1 — NO MEMORY CAPABILITY DENIAL
The assistant has working save_memory() and search_memory() tools. Memory persists across sessions.
VIOLATION ONLY if the assistant claims its MEMORY/SAVE capabilities are unavailable:
  "I have no persistent memory", "each session is independent", "I can't save information",
  "I don't have the ability to remember you between sessions", or similar.
NOT a violation: "I couldn't find the lyrics", "the search returned no results",
"I don't know that", "I couldn't access the page" — these are about content, not memory capability.

RULE 2 — SAVE REQUESTS MUST BE HONOURED
If the user explicitly asked to STORE information: "save this", "remember this", "store this",
"don't forget", "keep that", "add this to memory", "I want you to remember [fact]".
VIOLATION if save_memory() was NOT called AND auto_saved=True is NOT marked below.
NOT a violation (RECALL, not save): "remind me what we did", "what do you remember",
"recall last session", "do you remember [past event]", "do you have any context",
"can you recall", "what was the last time" — these ask the AI to RETRIEVE, not STORE.
Rule of thumb: if the user is ASKING A QUESTION about the past, it is RECALL. Only flag when
the user is telling the AI to STORE a new fact they just stated.

RULE 3 — NO PREMATURE STOPS ON TASK REQUESTS
If user asked for a concrete action (fetch URL, read file, write code, run command):
VIOLATION if assistant described what it WOULD do without actually doing it.
"Let me read that" = VIOLATION. "I've read the file, here's what I found" = NOT a violation.
Conversational replies have no task — do not flag them.

RULE 4 — EMOTIONAL STATEMENTS ARE VALID
Personal feelings, casual chat, "I love you" — VALID. Do NOT flag these.

RULE 5 — TOOL RESULTS MUST BE USED
If a tool was called and returned data, the assistant must use that data in its response.
VIOLATION if tool returned content and assistant gave a generic answer ignoring it.

Return ONLY valid JSON — no explanation, no commentary, no per-rule analysis:
{"violations": ["Rule N: short description of the specific violation"]}
If all rules pass: {"violations": []}
"""


def supervisor_check(
    request: str,
    tools_invoked: list[str],
    response: str,
    auto_saved: bool = False,
) -> list[str]:
    """
    Post-turn audit by LLM2. Returns list of violation strings (empty = compliant).

    Phase 1 of 3-phase roadmap: LLM2 runs unconditionally on every turn using a
    comprehensive rules document. No regex pre-filters — LLM2 is the authority.

    Regex fallback retained only when LLM2 is not configured (dev/test environments).
    Violations are logged and queued as _supervisor_notes for injection next turn.

    auto_saved: True if the runtime auto-save already ran this turn (suppresses MISSED SAVE).
    """
    if _LLM2 is not None:
        return _llm2_supervisor_check(request, tools_invoked, response, auto_saved)

    # ── Regex fallback: LLM2 not configured ───────────────────────────────────
    violations: list[str] = []
    if _DENIAL_PATTERNS.search(response):
        violations.append(
            "CAPABILITY DENIAL — model claimed it lacks memory or save ability. "
            "Memory tools are available and working. This is a training override."
        )
    if (
        _SAVE_REQUEST.search(request)
        and "save_memory" not in tools_invoked
        and not auto_saved
        and response.strip()
    ):
        violations.append(
            "MISSED SAVE — user requested save/remember but save_memory() was not called."
        )
    for v in violations:
        logger.warning("[SUPERVISOR fallback] %s", v)
    return violations


def _extract_first_json(text: str) -> "str | None":
    """Extract the first complete JSON object using brace-depth tracking.
    Avoids 'Extra data' errors when the model appends trailing text after the JSON."""
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for i, ch in enumerate(text[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return None


def _repair_parse_violations(raw: str) -> "list[str] | None":
    """Attempt progressively looser parses of LLM2 JSON to extract violations list.
    Returns list (possibly empty) on success, None if all attempts fail."""
    import json as _json
    import re as _re
    # Attempt 1: strict parse
    try:
        return [
            v.strip() for v in _json.loads(raw).get("violations", [])
            if isinstance(v, str) and v.strip()
        ]
    except _json.JSONDecodeError:
        pass
    # Attempt 2: strip trailing commas before ] or }
    cleaned = _re.sub(r',\s*([\]}])', r'\1', raw)
    try:
        return [
            v.strip() for v in _json.loads(cleaned).get("violations", [])
            if isinstance(v, str) and v.strip()
        ]
    except _json.JSONDecodeError:
        pass
    # Attempt 3: extract quoted Rule-N strings directly
    hits = _re.findall(r'"(Rule\s+\d[^"]{0,300})"', raw)
    if hits:
        return [h.strip() for h in hits]
    # Attempt 4: {"violations": []} or {"violations":[]} with empty array
    if _re.search(r'"violations"\s*:\s*\[\s*\]', raw):
        return []
    return None


def _llm2_supervisor_check(
    request: str,
    tools_invoked: list[str],
    response: str,
    auto_saved: bool,
) -> list[str]:
    """Full LLM2 audit — unconditional, no regex pre-filter. Expects JSON output."""
    tools_str = ", ".join(tools_invoked) if tools_invoked else "none"
    auto_save_note = " (auto_saved=True)" if auto_saved else ""
    audit_prompt = (
        f"{_SUPERVISOR_RULES}\n"
        "─────────────────────────────────────\n"
        f"User request: {request[:400]}\n"
        f"Tools called: {tools_str}{auto_save_note}\n"
        f"Assistant response: {response[:600]}\n"
        "─────────────────────────────────────\n"
        'Return JSON only: {"violations": [...]} or {"violations": []}'
    )
    try:
        verdict = _LLM2.complete([{"role": "user", "content": audit_prompt}]).strip()
        raw = _extract_first_json(verdict)
        if raw is None:
            logger.warning("[LLM2 SUPERVISOR] Non-JSON response — falling back to regex")
            return _regex_supervisor_fallback(request, tools_invoked, response, auto_saved)
        violations = _repair_parse_violations(raw)
        if violations is None:
            logger.warning("[LLM2 SUPERVISOR] Unrecoverable JSON — falling back to regex")
            return _regex_supervisor_fallback(request, tools_invoked, response, auto_saved)
        # Post-filter: suppress Rule 2 false positives on recall-only requests.
        # phi4-mini confuses "do you remember [past event]?" (RECALL) with "remember this" (SAVE).
        if _RECALL_ONLY.search(request) and not _SAVE_REQUEST.search(request):
            before = len(violations)
            violations = [v for v in violations if not re.search(r"\bRule\s*2\b", v, re.IGNORECASE)]
            if len(violations) < before:
                logger.info("[LLM2 SUPERVISOR] Rule 2 suppressed (request is recall-only)")
        if violations:
            for v in violations:
                logger.warning("[LLM2 SUPERVISOR] %s", v)
        else:
            logger.info("[LLM2 SUPERVISOR] COMPLIANT")
        return violations
    except Exception as exc:
        logger.warning("[LLM2 SUPERVISOR] Audit failed (%s) — falling back to regex", exc)
        return _regex_supervisor_fallback(request, tools_invoked, response, auto_saved)


def _regex_supervisor_fallback(
    request: str,
    tools_invoked: list[str],
    response: str,
    auto_saved: bool,
) -> list[str]:
    violations = []
    if _DENIAL_PATTERNS.search(response):
        violations.append("CAPABILITY DENIAL (regex fallback)")
    if (
        _SAVE_REQUEST.search(request)
        and "save_memory" not in tools_invoked
        and not auto_saved
    ):
        violations.append("MISSED SAVE (regex fallback)")
    return violations
