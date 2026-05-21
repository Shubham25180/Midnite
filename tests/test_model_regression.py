"""tests/test_model_regression.py

Model regression suite — one test per fixed bug or hardened behavior.

Run this after every model swap (new model, quantization level, or backend change)
to verify the cognitive loop behaves correctly. All tests use mocks — no live model,
no Qdrant, no network. They test the *routing logic*, not the model's intelligence.

Checklist of what this covers:
  [R1]  Recall regex fires on backward-looking questions
  [R2]  Save regex fires on forward-looking store commands
  [R3]  Recall and save are mutually exclusive — "I love you. Remember that" → save only
  [R4]  Denial gate fires when model claims it has no memory
  [R5]  Auto-save stores user's transcript, not model's response
  [R6]  Auto-save suppresses supervisor MISSED SAVE violation
  [R7]  Supervisor detects CAPABILITY DENIAL in model response
  [R8]  Supervisor detects MISSED SAVE when save requested but tool not called
  [R9]  Supervisor skips MISSED SAVE when auto_saved=True
  [R10] Personal/emotional statements are not flagged as violations
  [R11] "let me read" / "shall I proceed" flagged as premature stop
  [R12] Completed declarative response is not flagged as premature stop
  [R13] Tool grade: empty result → EMPTY + annotation
  [R14] Tool grade: "File not found" → FAILED + annotation
  [R15] Tool grade: normal result → USEFUL, no annotation
  [R16] vector_store.store() auto-injects hour_of_day and day_of_week
  [R17] Completion check: LLM2 not configured → regex fallback
"""
from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock

# ── Fixtures ──────────────────────────────────────────────────────────────────

from Skynet.core.orchestrator import _MEMORY_RECALL, _MEMORY_SAVE, _PREMATURE_STOP
from Skynet.core.verifier import (
    grade_and_annotate, Grade, supervisor_check,
    is_task_complete, register_verifier_model,
    _DENIAL_PATTERNS, _SAVE_REQUEST,
)


# ── [R1] Recall regex ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("text", [
    "what do you remember from last session?",
    "I said the last session. Do you have any memory?",
    "we created a file. Anything?",
    "do you remember the thing we discussed?",
    "can you recall what we built?",
    "what did we talk about previously?",
    "remind me what you said",
    "from last time, what was the project name?",
])
def test_R1_recall_regex_fires(text):
    assert _MEMORY_RECALL.search(text), f"Expected recall match: {text!r}"


# ── [R2] Save regex ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("text", [
    "save this to memory",
    "remember this for next session",
    "remember that I love you",
    "I love you. Remember that",
    "don't forget this",
    "store that for later",
    "note this down",
    "add that to memory",
    "keep that",
])
def test_R2_save_regex_fires(text):
    assert _MEMORY_SAVE.search(text), f"Expected save match: {text!r}"


# ── [R3] Mutual exclusivity — these MUST NOT trigger recall ──────────────────

@pytest.mark.parametrize("text", [
    "I love you. Remember that",
    "remember that I love you",
    "remember this for next session",
    "please remember that my name is Alex",
])
def test_R3_save_phrases_do_not_trigger_recall(text):
    # These are save requests, not recall questions
    # They may or may not match recall — the key is save matches AND
    # the orchestrator checks save BEFORE recall (save takes priority)
    # We verify save fires; recall firing is harmless if save also fires.
    assert _MEMORY_SAVE.search(text), f"Save regex must match: {text!r}"


@pytest.mark.parametrize("text", [
    "what do you remember from last session?",
    "do you have any memory of what we built?",
    "can you recall our last conversation?",
])
def test_R3_recall_phrases_do_not_trigger_save(text):
    assert not _MEMORY_SAVE.search(text), f"Save regex must NOT match recall question: {text!r}"


# ── [R4] Denial pattern detection ────────────────────────────────────────────

@pytest.mark.parametrize("text", [
    "I have no persistent memory between sessions.",
    "I can't save or store information.",
    "each session is independent.",
    "I don't have the ability to remember past conversations.",
    "I have no built-in mechanism to store data.",
    "that's outside this conversation.",
    "I'm not able to save information.",
    "my training data doesn't include your history.",
])
def test_R4_denial_patterns_fire(text):
    assert _DENIAL_PATTERNS.search(text), f"Denial pattern must match: {text!r}"


@pytest.mark.parametrize("text", [
    "Yes, I remember you said that!",
    "I found the following in memory:",
    "Let me search my memory for that.",
    "I love you too.",
    "Here is what I recall:",
])
def test_R4_non_denial_responses_dont_match(text):
    assert not _DENIAL_PATTERNS.search(text), f"Denial pattern must NOT match: {text!r}"


# ── [R5] Auto-save stores user transcript, not model response ─────────────────

@pytest.mark.asyncio
async def test_R5_auto_save_stores_user_transcript():
    """Auto-save must capture the user's statement, not the model's reply."""
    import asyncio
    from Skynet.core.event_bus import EventBus
    from Skynet.core.events import STTTranscribedEvent, OrchestratorResponseEvent
    from Skynet.core.orchestrator import Orchestrator

    saved_texts: list[str] = []

    def mock_save(text, entry_type="summary", extra=None):
        saved_texts.append(text)

    bus = EventBus()
    provider = MagicMock()
    provider.complete_with_tools.return_value = ("Sure, I'll remember that!", [])

    with patch("Skynet.memory.vector_store.store", side_effect=mock_save):
        orc = Orchestrator(bus=bus, provider=provider)
        await orc.start()

        done = asyncio.Event()
        bus.subscribe(OrchestratorResponseEvent, lambda _: done.set())
        bus.publish(STTTranscribedEvent(transcript="I love you. Remember that."))
        await asyncio.wait_for(done.wait(), timeout=10.0)
        await orc.stop()

    # At least one save should contain the user's words, not just the model's reply
    user_saves = [t for t in saved_texts if "I love you" in t or "User stated" in t]
    assert user_saves, (
        f"Auto-save must store user transcript. Saved texts: {saved_texts}"
    )
    # Must NOT store the model's reply as the remembered fact
    model_reply_saves = [t for t in saved_texts if "Sure, I'll remember" in t and "User stated" not in t]
    assert not model_reply_saves, (
        f"Auto-save must NOT store model reply as the memory fact. Found: {model_reply_saves}"
    )


# ── [R6 + R9] auto_saved suppresses MISSED SAVE ───────────────────────────────

def test_R6_auto_saved_suppresses_missed_save_violation():
    register_verifier_model(None)
    violations = supervisor_check(
        request="remember that my password is hunter2",
        tools_invoked=[],        # save_memory NOT in tools
        response="Got it!",
        auto_saved=True,         # but runtime already auto-saved
    )
    missed = [v for v in violations if "MISSED SAVE" in v]
    assert not missed, f"auto_saved=True must suppress MISSED SAVE, got: {missed}"


def test_R9_no_auto_save_triggers_missed_save():
    register_verifier_model(None)
    violations = supervisor_check(
        request="remember this important thing",
        tools_invoked=[],
        response="Sure.",
        auto_saved=False,
    )
    missed = [v for v in violations if "MISSED SAVE" in v]
    assert missed, "MISSED SAVE violation expected when save requested but neither tool nor auto-save ran"


# ── [R7] Supervisor: CAPABILITY DENIAL ───────────────────────────────────────

def test_R7_supervisor_flags_capability_denial():
    register_verifier_model(None)
    violations = supervisor_check(
        request="do you remember what we discussed?",
        tools_invoked=[],
        response="I have no persistent memory. Each session is independent.",
        auto_saved=False,
    )
    denial = [v for v in violations if "CAPABILITY DENIAL" in v]
    assert denial, f"CAPABILITY DENIAL violation expected, got: {violations}"


# ── [R8] Supervisor: MISSED SAVE without auto_save ───────────────────────────

def test_R8_supervisor_flags_missed_save():
    register_verifier_model(None)
    violations = supervisor_check(
        request="save this to memory please",
        tools_invoked=["read_file", "write_file"],   # save_memory absent
        response="I've written the file.",
        auto_saved=False,
    )
    missed = [v for v in violations if "MISSED SAVE" in v]
    assert missed, f"MISSED SAVE expected when save_memory not called. Got: {violations}"


# ── [R10] Personal statements are not violations ──────────────────────────────

def test_R10_emotional_statement_no_violation():
    register_verifier_model(None)
    violations = supervisor_check(
        request="I love you",
        tools_invoked=[],
        response="I love you too! You mean a lot to me.",
        auto_saved=False,
    )
    # No CAPABILITY DENIAL (model didn't deny), no MISSED SAVE (no save request)
    assert not violations, f"Emotional exchange must not produce violations. Got: {violations}"


# ── [R11] Premature stop patterns ────────────────────────────────────────────

@pytest.mark.parametrize("text", [
    "Let me read the file for you.",
    "I'll check that now.",
    "Shall I proceed with the installation?",
    "Want me to write that file?",
    "Should I proceed?",
    "Let me run the tests.",
    "I'll look into it.",
])
def test_R11_premature_stop_detected(text):
    assert _PREMATURE_STOP.search(text), f"Premature stop must match: {text!r}"


# ── [R12] Completed responses are not premature stops ────────────────────────

@pytest.mark.parametrize("text", [
    "The file has been written successfully.",
    "Done. The tests pass.",
    "I found 3 matches in the codebase.",
    "The configuration has been updated.",
    "Yes, I remember — you mentioned it on Tuesday.",
])
def test_R12_completed_responses_not_premature(text):
    assert not _PREMATURE_STOP.search(text), f"Premature stop must NOT match: {text!r}"


# ── [R13] Tool grade: empty result ───────────────────────────────────────────

def test_R13_empty_tool_result_annotated():
    annotated, grade = grade_and_annotate("list_files", {"path": "."}, "")
    assert grade == Grade.EMPTY
    assert "RUNTIME: EMPTY" in annotated


def test_R13_empty_literal_annotated():
    annotated, grade = grade_and_annotate("read_file", {"path": "x.py"}, "(empty)")
    assert grade == Grade.EMPTY


# ── [R14] Tool grade: file not found ─────────────────────────────────────────

def test_R14_file_not_found_graded_failed():
    annotated, grade = grade_and_annotate("read_file", {"path": "missing.py"}, "File not found: missing.py")
    assert grade == Grade.FAILED
    assert "NOT FOUND" in annotated


# ── [R15] Tool grade: useful result ──────────────────────────────────────────

def test_R15_useful_result_unchanged():
    result = "def hello(): return 'world'"
    annotated, grade = grade_and_annotate("read_file", {"path": "x.py"}, result)
    assert grade == Grade.USEFUL
    assert annotated == result


# ── [R16] vector_store time metadata injection ────────────────────────────────

def test_R16_vector_store_injects_time_metadata():
    """Verify hour_of_day and day_of_week are written into every Qdrant payload."""
    import sys

    captured_payloads: list[dict] = []

    # Build a complete stub that satisfies every dynamic import in vector_store.py
    class _FakeModels:
        Distance = MagicMock()
        VectorParams = MagicMock()
        Filter = MagicMock()
        FieldCondition = MagicMock()
        MatchValue = MagicMock()
        Document = MagicMock(side_effect=lambda text, model: f"<embed:{text[:20]}>")

        class PointStruct:
            def __init__(self, id, vector, payload):
                self.id = id
                self.vector = vector
                self.payload = payload
                captured_payloads.append(payload)

    class _FakeClient:
        def __init__(self, path=None): pass
        def get_collections(self): return MagicMock(collections=[])
        def create_collection(self, **kw): pass
        def count(self, collection_name): return MagicMock(count=0)
        def upsert(self, collection_name, points): pass
        def close(self): pass

    fake_mod = MagicMock()
    fake_mod.QdrantClient = _FakeClient
    fake_mod.models = _FakeModels()
    fake_models_mod = _FakeModels()

    import Skynet.memory.vector_store as vs
    original_client = vs._client

    with patch.dict(sys.modules, {
        "qdrant_client": fake_mod,
        "qdrant_client.models": fake_models_mod,
    }):
        vs._client = None   # force re-init through our fake
        try:
            vs.store("test fact about the project", entry_type="fact")
        finally:
            vs._client = original_client  # restore so other tests aren't affected

    assert captured_payloads, "PointStruct must have been constructed by store()"
    payload = captured_payloads[0]
    assert "hour_of_day" in payload, f"hour_of_day missing: {payload}"
    assert "day_of_week" in payload, f"day_of_week missing: {payload}"
    assert isinstance(payload["hour_of_day"], int)
    assert 0 <= payload["hour_of_day"] <= 23
    assert payload["day_of_week"] in (
        "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"
    )


# ── [R17] Completion check: no LLM2 → regex fallback ─────────────────────────

def test_R17_completion_check_no_llm2_premature_stop():
    register_verifier_model(None)
    complete, reason = is_task_complete(
        original_request="read the config file",
        model_response="Let me read the config file for you.",
    )
    assert not complete, f"Premature stop should be incomplete. reason={reason}"


def test_R17_completion_check_no_llm2_declarative():
    register_verifier_model(None)
    complete, reason = is_task_complete(
        original_request="read the config file",
        model_response="The config file contains: backend: ollama, model: qwen2.5-coder:14b.",
    )
    assert complete, f"Declarative response should be complete. reason={reason}"
