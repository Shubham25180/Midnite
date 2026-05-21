# Skynet/core/orchestrator.py
from __future__ import annotations

import asyncio
import json
import logging
import os
import platform
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from Skynet.core.event_bus import EventBus
    from Skynet.providers.base import LLMProvider

from Skynet.core.component import Component
from Skynet.core.events import OrchestratorResponseEvent, STTTranscribedEvent, ContextStatsEvent
from Skynet.core import persona as persona_mod
from Skynet.core.runtime_state import ComponentState
from Skynet.task.task_router import TaskRouter
from Skynet.task.skill import SkillResult
from Skynet.memory import raw_log, session_store, compressor as mem_compressor, vector_store

logger = logging.getLogger(__name__)

_WINDOW = 6          # verbatim turns kept in LLM context
_COMPRESS_AT = 20    # compress oldest half when history hits this
_PERSONA_PATH = "config/personas/nexux.yaml"
_SENTENCE_END = re.compile(r'(?<=[.!?])\s+')


def _split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_END.split(text) if s.strip()]


_JSON_BLOCK = re.compile(r'```(?:json)?\s*(\{.*?\})\s*```', re.DOTALL)
_CODE_BLOCK = re.compile(r'```[\s\S]*?```')
_INLINE_CODE = re.compile(r'`[^`\n]+`')
_XML_TOOL_CALL = re.compile(r'<tool_call>\s*(.*?)\s*</tool_call>', re.DOTALL | re.IGNORECASE)
# Catches funcname({"key": "val"}) written as Python syntax in response text
_PYTHON_TOOL_CALL = re.compile(r'\b([a-zA-Z_]\w*)\s*\(\s*(\{[^)]*\})\s*\)', re.DOTALL)
_MEMORY_RECALL = re.compile(
    r"\b(recall|last session|"
    r"we (made|created|built|discussed)|"
    r"you said|last time|remind me|"
    r"what did (we|you)|what was|history|"
    r"do you remember|what do you remember|can you recall|"
    r"any memory|from (last|previous|the last)|"
    r"previous(ly)?)\b",
    re.IGNORECASE,
)
_MEMORY_SAVE = re.compile(
    r"\b(save (this|that|it|the|to memory)|remember (this|that|these)|store (this|that)|"
    r"keep (this|that)|note (this|that|down)|don't forget|add (this|that|it) to memory)\b",
    re.IGNORECASE,
)
# Phrases that indicate the model described an action but didn't take it
_PREMATURE_STOP = re.compile(
    r"\b(let me|i'll|i will|shall i|how does that sound|want me to|should i proceed|"
    r"i'll check|let's check|i'll look|let me look|i'll read|let me read|i'll run|let me run)\b",
    re.IGNORECASE,
)
def _detect_environment() -> dict:
    """Detect OS, shell, architecture once at startup."""
    system = platform.system()   # "Windows", "Linux", "Darwin"
    machine = platform.machine() # "AMD64", "x86_64", "arm64"

    if system == "Windows":
        shell = "PowerShell"
        run_bash_hint = (
            "run_bash = PowerShell: git, python, pip, ls, cat, grep, curl, pytest, npm, cmd /c '...'"
        )
        env_var_syntax = "$env:VAR_NAME"
        path_note = "Use Windows paths with forward slashes: 'Skynet/core/file.py'"
    elif system == "Darwin":
        shell = "bash/zsh"
        run_bash_hint = "run_bash = bash/zsh: git, python3, pip, ls, cat, grep, curl, pytest, npm"
        env_var_syntax = "$VAR_NAME"
        path_note = "Use POSIX paths: 'Skynet/core/file.py'"
    elif system == "Linux":
        is_android = "ANDROID_ROOT" in os.environ or "TERMUX_VERSION" in os.environ
        shell = "bash (Termux/Android)" if is_android else "bash"
        run_bash_hint = "run_bash = bash: git, python3, pip, ls, cat, grep, curl, pytest, npm"
        env_var_syntax = "$VAR_NAME"
        path_note = "Use POSIX paths: 'Skynet/core/file.py'"
    else:
        shell = "shell"
        run_bash_hint = "run_bash = shell access"
        env_var_syntax = "$VAR"
        path_note = ""

    return {
        "os": system,
        "arch": machine,
        "shell": shell,
        "run_bash_hint": run_bash_hint,
        "env_var_syntax": env_var_syntax,
        "path_note": path_note,
        "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
    }


_ENV = _detect_environment()


def _prefetch_memory(query: str) -> str:
    """
    Eagerly fetch ALL memory stores and return an injection-ready string.
    Called before the LLM so the model reads memory directly — no tool call needed.
    Returns a non-empty string even when all stores are empty.
    """
    parts: list[str] = ["MEMORY STATUS (pre-fetched — do NOT say memory is disconnected):"]

    # 1. Core (never-forget) memories
    core_hits = vector_store.search(query, top_k=5, entry_type="core")
    if core_hits:
        parts.append("Core memories:")
        for h in core_hits:
            text = h["meta"].get("text", "")
            if text:
                parts.append(f"  [core] {text}")

    # 2. Recent session summaries (SQLite — fast)
    sessions = session_store.load_recent_summaries(n=3)
    if sessions:
        parts.append("Past sessions:")
        for s in reversed(sessions):
            ts = s["ts"][:10]
            parts.append(f"  [{ts}] {s['summary']}")
            if s["facts"]:
                parts.append("  Known facts: " + "; ".join(s["facts"]))

    # 3. Semantic hits (Qdrant — all types except core)
    hits = vector_store.search(query, top_k=5)
    non_core = [h for h in hits if h["meta"].get("type") != "core"]
    if non_core:
        parts.append("Relevant memories:")
        for h in non_core:
            text = h["meta"].get("text", "")
            kind = h["meta"].get("type", "?")
            ts = h["meta"].get("ts", "")[:10]
            if text:
                parts.append(f"  [{kind} {ts}] {text}")

    if len(parts) == 1:
        # All stores empty
        total = vector_store.count()
        parts.append(f"  No memories stored yet (Qdrant: {total} entries, Sessions: {len(sessions)}).")
        parts.append("  Memory is CONNECTED but empty — no past sessions have been summarised yet.")
        parts.append("  Answer honestly: no past session data is available. Do NOT say 'memory is not connected'.")

    return "\n".join(parts)


def _extract_json_objects(text: str) -> list[tuple[str, dict]]:
    """Find all top-level JSON objects in text via brace-depth tracking."""
    results: list[tuple[str, dict]] = []
    i = 0
    while i < len(text):
        if text[i] == '{':
            depth, j = 0, i
            while j < len(text):
                if text[j] == '{':
                    depth += 1
                elif text[j] == '}':
                    depth -= 1
                    if depth == 0:
                        candidate = text[i:j + 1]
                        try:
                            results.append((candidate, json.loads(candidate)))
                        except json.JSONDecodeError:
                            pass
                        i = j
                        break
                j += 1
        i += 1
    return results


def _parse_text_tool_calls(text: str) -> tuple[str, list[dict]]:
    """Fallback: extract tool calls the LLM wrote as JSON text instead of calling the API.
    Handles both ```json blocks``` and bare inline JSON objects."""
    tool_calls: list[dict] = []

    def _try_extract_block(m: re.Match) -> str:
        try:
            data = json.loads(m.group(1))
            if isinstance(data.get("name"), str) and isinstance(data.get("arguments"), dict):
                tool_calls.append({"name": data["name"], "arguments": data["arguments"]})
                return ""
        except (json.JSONDecodeError, AttributeError, KeyError):
            pass
        return m.group(0)

    # Phase 1: strip tool calls from ```json ... ``` blocks
    cleaned = _JSON_BLOCK.sub(_try_extract_block, text)

    # Phase 2: find inline JSON objects the model wrote bare in its response text
    for raw, data in _extract_json_objects(cleaned):
        if isinstance(data.get("name"), str) and isinstance(data.get("arguments"), dict):
            tool_calls.append({"name": data["name"], "arguments": data["arguments"]})
            cleaned = cleaned.replace(raw, "", 1)

    return cleaned.strip(), tool_calls


def _parse_xml_tool_calls(text: str) -> tuple[str, list[dict]]:
    """Extract <tool_call>JSON</tool_call> blocks — qwen2.5 native output format."""
    tool_calls: list[dict] = []
    cleaned = text
    for m in _XML_TOOL_CALL.finditer(text):
        try:
            data = json.loads(m.group(1))
            if isinstance(data.get("name"), str) and isinstance(data.get("arguments"), dict):
                tool_calls.append({"name": data["name"], "arguments": data["arguments"]})
                cleaned = cleaned.replace(m.group(0), "", 1)
        except json.JSONDecodeError:
            pass
    return cleaned.strip(), tool_calls


def _parse_python_tool_calls(text: str) -> tuple[str, list[dict]]:
    """Fallback: catch funcname({...}) Python-style tool calls written in response text."""
    from Skynet.tools.definitions import TOOL_NAMES
    tool_calls: list[dict] = []
    cleaned = text
    for m in _PYTHON_TOOL_CALL.finditer(text):
        name = m.group(1)
        if name not in TOOL_NAMES:
            continue
        try:
            args = json.loads(m.group(2))
            if isinstance(args, dict):
                tool_calls.append({"name": name, "arguments": args})
                cleaned = cleaned.replace(m.group(0), "", 1)
        except json.JSONDecodeError:
            pass
    return cleaned.strip(), tool_calls


def _is_premature_stop(text: str) -> bool:
    """True if the model described what it would do but didn't actually call a tool."""
    return bool(text and _PREMATURE_STOP.search(text))


def _is_memory_recall_request(transcript: str) -> bool:
    """True if the user is asking about past sessions or what was said/done before."""
    return bool(_MEMORY_RECALL.search(transcript))


def _strip_code_for_tts(text: str) -> str:
    """Remove code and JSON blocks so TTS doesn't read raw code aloud."""
    text = _CODE_BLOCK.sub('', text)
    text = _INLINE_CODE.sub('', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


class Orchestrator(Component):
    def __init__(self, *, bus: EventBus, provider: LLMProvider,
                 memory_provider: "LLMProvider | None" = None,
                 persona_path: str = _PERSONA_PATH,
                 tts_batch: int = 0,
                 compress_at: int = _COMPRESS_AT) -> None:
        super().__init__(name="orchestrator")
        self._bus = bus
        self._provider = provider
        self._memory_provider = memory_provider
        self._router = TaskRouter()
        self._history: list[tuple[str, str]] = []
        self._health = ComponentState.OFFLINE
        self._token: str | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._persona_path = persona_path
        self._tts_batch = max(0, int(tts_batch))
        self._compress_at = max(4, int(compress_at))
        self._persona = persona_mod.load(persona_path)
        self._supervisor_notes: list[str] = []   # LLM2 corrections injected next turn
        logger.info("Persona loaded: %s (intimacy=%d)",
                    self._persona.name, self._persona.intimacy_level)

    async def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._token = self._bus.subscribe(STTTranscribedEvent, self._on_stt)
        self._health = ComponentState.IDLE

    async def stop(self) -> None:
        if self._token:
            self._bus.unsubscribe(self._token)
            self._token = None
        # Flush orphaned supervisor notes — violations from the final turn that never
        # got injected into a next-turn prompt. Write as behavioral memory (Phase 2 seed).
        if self._supervisor_notes:
            for note in self._supervisor_notes:
                vector_store.store(
                    note, entry_type="llm1_behavior",
                    extra={"outcome": "violation", "session_end": True},
                )
            logger.info(
                "Flushed %d orphaned supervisor note(s) to behavioral memory",
                len(self._supervisor_notes),
            )
            self._supervisor_notes.clear()
        if self._history:
            provider = self._memory_provider or self._provider
            mem_compressor.compress_async(
                list(self._history), provider, turn_count=len(self._history)
            )
            logger.info("Memory: session-end compression triggered (%d turns)", len(self._history))
        self._health = ComponentState.OFFLINE

    def health(self) -> ComponentState:
        return self._health

    def set_provider(self, provider: "LLMProvider") -> None:
        self._provider = provider
        logger.info("LLM provider swapped → %s", type(provider).__name__)

    def set_tts_batch(self, n: int) -> None:
        self._tts_batch = max(0, int(n))
        label = "full response" if self._tts_batch == 0 else f"{self._tts_batch} sentence(s)"
        logger.info("TTS batch → %s", label)

    def _on_stt(self, event: STTTranscribedEvent) -> None:
        if self._health == ComponentState.BUSY:
            logger.debug("STT transcript dropped — orchestrator busy")
            return
        logger.info("USER: %s", event.transcript)
        self._loop.call_soon_threadsafe(
            lambda: self._loop.create_task(self._handle(event.transcript))
        )

    async def _handle(self, transcript: str) -> None:
        self._health = ComponentState.BUSY
        try:
            result = self._router.route(transcript)

            if result.direct is not None:
                logger.info("NEXUX (direct): %s", result.direct)
                self._bus.publish(OrchestratorResponseEvent(response=result.direct))
                self._history.append((transcript, result.direct))
                return

            messages = self._build_messages(result)
            logger.debug("LLM context: %d messages (%d history turns)",
                         len(messages), len(self._history))
            loop = asyncio.get_running_loop()
            t_start = loop.time()

            tools_invoked: list[str] = []
            full_response = await self._unified_loop(messages, loop, tools_invoked=tools_invoked)

            # Auto-save safety net: if user asked to save/remember but the model never
            # called save_memory, persist the user's own statement as the important fact.
            # We save what the USER said, not the model's response — the response may be
            # off-topic (e.g. the model got confused by unrelated injected memories).
            auto_saved = False
            if (
                full_response
                and _MEMORY_SAVE.search(transcript)
                and "save_memory" not in tools_invoked
            ):
                from Skynet.tools.executor import execute as _exec
                save_text = f"User stated (to be remembered): {transcript[:1800]}"
                _exec("save_memory", {"text": save_text, "entry_type": "important"})
                auto_saved = True
                logger.info(
                    "Auto-save: persisted user statement as important fact (%d chars)",
                    len(save_text),
                )

            total_ms = int((loop.time() - t_start) * 1000)
            logger.info("[T] total=%dms  %d chars", total_ms, len(full_response))

            if full_response:
                # Strip code blocks before TTS — speak prose, not raw code/JSON
                tts_text = _strip_code_for_tts(full_response)
                if not tts_text:
                    tts_text = full_response  # fallback: speak everything if nothing left
                if self._tts_batch == 0:
                    self._bus.publish(OrchestratorResponseEvent(response=tts_text))
                else:
                    sentences = _split_sentences(tts_text)
                    batch: list[str] = []
                    for s in sentences:
                        batch.append(s)
                        if len(batch) >= self._tts_batch:
                            self._bus.publish(OrchestratorResponseEvent(
                                response=" ".join(batch)
                            ))
                            batch = []
                    if batch:
                        self._bus.publish(OrchestratorResponseEvent(
                            response=" ".join(batch)
                        ))
            logger.info("NEXUX: %s", full_response)

            raw_log.append("user", transcript)
            raw_log.append("assistant", full_response)
            self._history.append((transcript, full_response))

            # LLM2 supervisor: fire-and-forget post-turn audit so BUSY clears immediately
            if full_response:
                asyncio.create_task(
                    self._run_supervisor(transcript, tools_invoked, full_response, auto_saved)
                )

            if len(self._history) >= self._compress_at:
                # Compress the MIDDLE — preserve head (identity turns) + tail (recent context).
                # The beginning of a session is identity-establishing (name, prefs, project).
                # The tail is the rolling window. Only the middle is expendable.
                _head_keep = 2
                head = self._history[:_head_keep]
                tail = self._history[-_WINDOW:]
                middle = self._history[_head_keep:-_WINDOW]
                if middle:
                    provider = self._memory_provider or self._provider
                    mem_compressor.compress_async(middle, provider, turn_count=len(middle))
                    self._history = head + tail
                    logger.info(
                        "Memory: mid-session compression (%d turns archived, "
                        "%d head + %d tail kept)",
                        len(middle), len(head), len(tail),
                    )

            turns_used = min(len(self._history), _WINDOW)
            tokens_est = sum(len(msg.get("content") or "") for msg in messages) // 4
            logger.info("CONTEXT: %d/%d turns used — ~%d tokens in window",
                        turns_used, _WINDOW, tokens_est)
            self._bus.publish(ContextStatsEvent(
                turns_used=turns_used,
                turns_total=_WINDOW,
                tokens_est=tokens_est,
            ))
        except Exception:
            logger.exception("Orchestrator failed to handle transcript")
        finally:
            self._health = ComponentState.IDLE

    async def _run_supervisor(
        self,
        transcript: str,
        tools_invoked: list[str],
        response: str,
        auto_saved: bool = False,
    ) -> None:
        """Background task: LLM2 audits turn + detects pinnable identity facts. Both run concurrently."""
        from Skynet.core.verifier import supervisor_check, semantic_pin_check
        loop = asyncio.get_running_loop()
        try:
            supervisor_fut = loop.run_in_executor(
                None,
                lambda: supervisor_check(transcript, tools_invoked, response, auto_saved),
            )
            pinning_fut = loop.run_in_executor(
                None,
                lambda: semantic_pin_check(transcript),
            )
            violations, pins = await asyncio.gather(supervisor_fut, pinning_fut)

            if violations:
                self._supervisor_notes.extend(violations)

            if pins:
                from Skynet.memory import vector_store as _vs
                for pin in pins:
                    _vs.store(pin, entry_type="core")
                    logger.info("Pinned to core memory: '%s'", pin[:80])
        except Exception:
            logger.debug("Supervisor/pinning task failed — skipping")

    async def _unified_loop(
        self,
        messages: list[dict],
        loop: asyncio.AbstractEventLoop,
        tools_invoked: list[str] | None = None,
    ) -> str:
        """
        Deterministic execution runtime — LLM is a planner, runtime enforces completion.

        Fallback chain per step:
          1. Provider native tool calling (Anthropic API / Ollama function calls)
          2. XML <tool_call> tags (qwen2.5 native output format)
          3. Bare JSON objects in text

        Recovery: if the model stops early with "I'll check..." and no tool call,
        runtime injects one continuation nudge and retries. One recovery per turn max.
        """
        from Skynet.tools.executor import execute as exec_tool
        from Skynet.core.verifier import grade_and_annotate, Grade, is_task_complete, _DENIAL_PATTERNS

        active_tools = self._get_active_tools()
        announced = False
        recovery_count = 0
        denial_count = 0
        MAX_RECOVERIES = 2
        MAX_DENIAL_RETRIES = 1   # one forced rewrite per turn is enough

        for step in range(15):
            text, tool_calls = await loop.run_in_executor(
                None,
                lambda: self._provider.complete_with_tools(messages, active_tools),
            )

            # Fallback 1: XML <tool_call> tags — qwen2.5 native
            if not tool_calls and text:
                cleaned_text, xml_calls = _parse_xml_tool_calls(text)
                if xml_calls:
                    logger.info("Fallback[XML]: parsed %d tool call(s)", len(xml_calls))
                    text, tool_calls = cleaned_text, xml_calls

            # Fallback 2: bare JSON objects / ```json blocks in text
            if not tool_calls and text:
                cleaned_text, json_calls = _parse_text_tool_calls(text)
                if json_calls:
                    logger.info("Fallback[JSON]: parsed %d tool call(s)", len(json_calls))
                    text, tool_calls = cleaned_text, json_calls

            # Fallback 3: Python-style funcname({...}) in response text
            if not tool_calls and text:
                cleaned_text, py_calls = _parse_python_tool_calls(text)
                if py_calls:
                    logger.info("Fallback[Python]: parsed %d tool call(s)", len(py_calls))
                    text, tool_calls = cleaned_text, py_calls

            if not tool_calls:
                # ── Pre-TTS denial gate ─────────────────────────────────────
                # Catches "I have no memory / can't save / each session is independent"
                # BEFORE the response reaches TTS — forces a rewrite with real data.
                if denial_count < MAX_DENIAL_RETRIES and text and _DENIAL_PATTERNS.search(text):
                    denial_count += 1
                    logger.warning(
                        "[DENIAL GATE] LLM1 denied capabilities (attempt %d) — forcing rewrite",
                        denial_count,
                    )
                    # Fetch real memory so LLM1 can see what actually exists
                    original_q = next(
                        (m["content"] for m in reversed(messages)
                         if isinstance(m.get("content"), str) and m.get("role") == "user"),
                        "",
                    )
                    mem_snapshot = await loop.run_in_executor(
                        None,
                        lambda: vector_store.build_relevant_context(original_q, top_k=4),
                    )
                    correction = (
                        "[RUNTIME CORRECTION — REWRITE REQUIRED]\n"
                        "Your previous response incorrectly stated you have no persistent memory "
                        "or cannot save information. This is false. You have:\n"
                        "  • Qdrant vector store (semantic memory)\n"
                        "  • SQLite session store (past session summaries)\n"
                        "  • save_memory() tool — call it to store anything\n"
                        "  • search_memory() tool — call it to recall anything\n"
                    )
                    if mem_snapshot:
                        correction += f"\nCurrent memory contents:\n{mem_snapshot}\n"
                    else:
                        correction += "\nMemory is connected and empty — no past sessions yet. "
                        correction += "Tell the user that honestly (empty, not unavailable).\n"
                    correction += (
                        "\nRewrite your response now. Do NOT say memory is unavailable, "
                        "disconnected, or that you lack capabilities. Use the facts above."
                    )
                    messages.append({"role": "assistant", "content": text})
                    messages.append({"role": "user", "content": correction})
                    continue

                # ── Completion validator ────────────────────────────────────
                if recovery_count < MAX_RECOVERIES:
                    original_request = next(
                        (m["content"] for m in reversed(messages)
                         if isinstance(m.get("content"), str) and m.get("role") == "user"),
                        ""
                    )
                    complete, reason = await loop.run_in_executor(
                        None, lambda: is_task_complete(original_request, text or "")
                    )
                    if not complete:
                        recovery_count += 1
                        logger.info("Recovery #%d [%s]: injecting continuation", recovery_count, reason)
                        if recovery_count == 1:
                            nudge = (
                                "You described what you would do but didn't do it. "
                                "Call the tool now and complete the task."
                            )
                        else:
                            nudge = (
                                "The task is still not finished. "
                                "If files haven't been read yet, call read_all_files(). "
                                "If the user asked to save something, call save_memory(). "
                                "Keep calling tools until every part of the request is done."
                            )
                        messages.append({"role": "assistant", "content": text or ""})
                        messages.append({"role": "user", "content": nudge})
                        continue
                logger.info("Response in %d step(s): %d chars", step + 1, len(text or ""))
                return (text or "").strip()

            for tc in tool_calls:
                name, args = tc["name"], tc["arguments"]
                logger.info("Tool: %s(%s)", name, list(args.keys()))
                if tools_invoked is not None:
                    tools_invoked.append(name)

                if name != "load_skill" and not announced:
                    self._bus.publish(OrchestratorResponseEvent(response="On it."))
                    announced = True

                tool_result = await loop.run_in_executor(None, lambda: exec_tool(name, args))
                tool_result, result_grade = grade_and_annotate(name, args, tool_result)
                logger.debug("Tool result [%s] (%d chars): %.200s",
                             result_grade.value, len(tool_result), tool_result)
                tool_use_id = tc.get("_tool_use_id")
                if tool_use_id:
                    # Claude/Anthropic native format
                    messages.append({
                        "role": "assistant",
                        "content": [{"type": "tool_use", "id": tool_use_id, "name": name, "input": args}],
                    })
                    messages.append({
                        "role": "user",
                        "content": [{"type": "tool_result", "tool_use_id": tool_use_id, "content": tool_result}],
                    })
                else:
                    # Ollama/OpenAI format
                    messages.append({
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [{"function": {"name": name, "arguments": args}}],
                    })
                    messages.append({"role": "tool", "content": tool_result})

        return "I reached the maximum number of steps. Something may need manual attention."

    def preview_messages(self) -> dict:
        """Return current system prompt + history for UI debugging."""
        self._persona = persona_mod.load(self._persona_path)
        system = self._persona.build_system_prompt()
        history = []
        for user_t, asst_t in self._history[-(_WINDOW - 1):]:
            history.append({"role": "user", "content": user_t})
            history.append({"role": "assistant", "content": asst_t})
        return {"system": system, "history": history, "window": _WINDOW}

    def _get_active_tools(self) -> list[dict]:
        """Return TOOL_DEFINITIONS filtered by tools.disabled in settings.yaml."""
        from Skynet.tools.definitions import TOOL_DEFINITIONS
        try:
            import yaml
            cfg = yaml.safe_load(Path("config/settings.yaml").read_text(encoding="utf-8"))
            disabled = set((cfg.get("tools") or {}).get("disabled") or [])
            if disabled:
                return [t for t in TOOL_DEFINITIONS if t["function"]["name"] not in disabled]
        except Exception:
            pass
        return TOOL_DEFINITIONS

    def _build_project_tree(self) -> str:
        """Lightweight top-level project tree for LLM orientation."""
        root = Path(".")
        lines: list[str] = []
        skip = {"__pycache__", ".git", ".claude", ".claude-flow", "node_modules", ".agents", ".codex"}
        try:
            for item in sorted(root.iterdir()):
                if item.name.startswith(".") or item.name in skip:
                    continue
                if item.is_dir():
                    lines.append(f"  {item.name}/")
                    if item.name in ("Skynet", "config", "tests"):
                        for child in sorted(item.iterdir()):
                            if child.name.startswith("_") or child.name.startswith(".") or child.name in skip:
                                continue
                            lines.append(f"    {child.name}{'/' if child.is_dir() else ''}")
                else:
                    lines.append(f"  {item.name}")
        except Exception:
            return ""
        return "\n".join(lines)

    def _build_system_awareness(self) -> str:
        """Live system state + skill index — injected into every prompt."""
        skill_index = self._router.skill_index
        model_name = getattr(self._provider, "model", "unknown")
        mem_count = vector_store.count()
        cwd = os.getcwd()

        from datetime import datetime as _dt
        _now = _dt.now()
        lines = [
            "RUNTIME FACTS (report these accurately when asked):",
            f"  Current date/time: {_now.strftime('%A %B %d %Y, %I:%M %p')}",
            f"  Model: {model_name}",
            f"  Working directory: {cwd}",
            f"  OS: {_ENV['os']}  arch: {_ENV['arch']}  shell: {_ENV['shell']}  Python: {_ENV['python']}",
            f"  Memory entries: {mem_count}  (use search_memory(query) to recall past sessions)",
            "  Tools always available: read_file, write_file, edit_file, multi_edit_file, list_files, glob_files, grep_files, read_all_files, run_bash, web_fetch, get_recent_history, save_memory, search_memory, get_system_info, reload_skills",
            f"  {_ENV['run_bash_hint']}",
            f"  Env vars: {_ENV['env_var_syntax']}  |  {_ENV['path_note']}  |  Dangerous cmds are blocked.",
        ]

        tree = self._build_project_tree()
        if tree:
            lines.append(f"  Project structure:\n{tree}")

        if skill_index:
            lines.append("  Skills (activate with load_skill(name)):")
            for entry in skill_index:
                lines.append(f"    - {entry['name']}: {entry.get('description', '')}")
        else:
            lines.append("  Skills: none loaded")

        lines.extend([
            "",
            "TOOL CALL FORMAT — use EXACTLY this when calling a tool:",
            "  <tool_call>",
            '  {"name": "tool_name", "arguments": {"arg": "value"}}',
            "  </tool_call>",
            "  This is the ONLY accepted format. Do not write JSON outside these tags.",
            "  Example: to read a file:",
            "  <tool_call>",
            '  {"name": "read_file", "arguments": {"path": "docs/architecture.md"}}',
            "  </tool_call>",
            "",
            "FILE PATH RULES:",
            "  - ALWAYS use relative paths: 'docs/arch.md', 'config/settings.yaml', 'Skynet/core/orchestrator.py'",
            f"  - NEVER use absolute paths like {cwd}{os.sep}... — they will be blocked.",
            "",
            "TOOL CALLING RULES — follow exactly:",
            "  1. To use a tool, make an ACTUAL function/tool call through the API.",
            "  2. NEVER write tool calls as JSON text in your response — that does NOT execute anything.",
            "  3. NEVER say 'let me check', 'how does that sound?', or 'shall I proceed?' — just call the tool.",
            "  4. After receiving a tool result: if the task needs more work, call the NEXT tool immediately.",
            "     Keep chaining tool calls until the full task is done. Only return text when you have a FINAL answer.",
            "  5. list_files() is NOT an answer — if the user asks to read/understand files, call read_all_files(dir) next.",
            "  6. When asked to read ALL files or an entire folder, call read_all_files(directory) — ONE call reads everything.",
            "  7. If the user says 'save to memory', 'remember this', or 'store this', you MUST call save_memory() BEFORE your final text response.",
            "  8. Never say you lack practical abilities — the tools above are real and functional.",
            "  9. MEMORY IS CONNECTED AND WORKING. When asked what you remember, read the MEMORY STATUS block",
            "     injected above — the results are already there. NEVER say 'memory is not connected' or",
            "     'memory is not set up'. Call search_memory() for deeper or follow-up searches.",
            " 10. To recall more than 6 turns back in this session, call get_recent_history(n_turns).",
        ])
        return "\n".join(lines)

    def _build_messages(self, result: SkillResult) -> list[dict]:
        # Hot reload — re-read persona file on every call so edits take effect immediately
        self._persona = persona_mod.load(self._persona_path)
        persona_prompt = result.prompt_override or self._persona.build_system_prompt()

        # Runtime awareness goes FIRST so factual capabilities override personality hedging
        system_prompt = self._build_system_awareness() + "\n\n" + persona_prompt

        # Non-recall turns: inject lightweight recent-session context only
        recent_ctx = session_store.build_memory_context(n_sessions=1)
        if recent_ctx:
            system_prompt += f"\n\n{recent_ctx}"

        # Supervisor notes: LLM2 corrections from the previous turn
        if self._supervisor_notes:
            system_prompt += "\n\n" + "─" * 52
            system_prompt += "\nSUPERVISOR NOTES (from last turn — read and self-correct):\n"
            for note in self._supervisor_notes:
                system_prompt += f"  ⚠ {note}\n"
            system_prompt += "─" * 52
            self._supervisor_notes.clear()

        msgs: list[dict] = [{"role": "system", "content": system_prompt}]
        for user_text, asst_text in self._history[-(_WINDOW - 1):]:
            msgs.append({"role": "user", "content": user_text})
            msgs.append({"role": "assistant", "content": asst_text})

        # Memory recall: inject results INSIDE the user message.
        # WHY THIS INJECTION EXISTS: empirically proven that 14B quant models will deny
        # having memory even when search_memory tool is available and working. The base
        # training override ("I have no persistent memory") is stronger than the tool
        # definition. Pre-fetching and placing results in the user turn makes them
        # undeniable. This is a workaround for a specific, documented model limitation —
        # NOT a general pattern. All other data (hardware, skills, env) must be fetched
        # by the model via tools when it decides it needs them.
        if _is_memory_recall_request(result.transcript):
            from Skynet.tools.executor import execute as _exec
            mem_result = _exec("search_memory", {"query": result.transcript})
            logger.info("Pre-fetched memory (%d chars) for recall request", len(mem_result))
            user_content = (
                f"[Memory search ran automatically — results below]\n"
                f"{'─'*52}\n"
                f"{mem_result}\n"
                f"{'─'*52}\n\n"
                f"{result.transcript}\n\n"
                f"(Answer using only the memory results shown above. "
                f"Do NOT say memory is unavailable or that you lack persistent memory — "
                f"it is connected and the results are above.)"
            )
            msgs.append({"role": "user", "content": user_content})
        else:
            msgs.append({"role": "user", "content": result.transcript})
        return msgs
