# Nexux V0.1 — Cognitive Core Prototype

Goal: voice in → STT → brain thinks → LLM1 responds → TTS → voice out.
Nothing else. No tools. No memory. No LLM2. Just the core loop working.

---

## PHASE 1 — Settings & Boot Foundation

- [ ] Create `config/settings.yaml` — all runtime config lives here
  ```yaml
  stt:
    backend: whisper
    model: base
    enabled: true

  llm1:
    backend: ollama       # swap to: claude, openrouter, etc.
    model: llama3.2
    enabled: true

  llm2:
    backend: ~
    enabled: false        # not V0.1

  tts:
    backend: vibevoice
    enabled: true

  memory:
    enabled: false        # not V0.1
  ```

- [ ] Create `Skynet/core/config.py` — loads + validates settings.yaml at boot
- [ ] Create `Skynet/main.py` — entry point
  - Loads config
  - Shows boot status screen (what is enabled / disabled / not configured)
  - Starts the runtime loop after user confirms
  - Boot screen example:
    ```
    SKYNET — BOOT STATUS
    ═══════════════════════════════
      STT      [✓] whisper / base
      LLM1     [✓] ollama / llama3.2
      LLM2     [✗] not configured
      TTS      [✓] vibevoice
      Memory   [✗] not configured
    ═══════════════════════════════
    Press ENTER to start...
    ```

---

## PHASE 2 — Provider Abstraction

brain.py never calls Ollama or Claude directly. It calls a provider.
Switching providers = changing settings.yaml. No code changes.

- [ ] Create `Skynet/providers/base.py` — abstract interface
  ```python
  class LLMProvider:
      def complete(self, messages: list[dict]) -> str: ...
      def stream(self, messages: list[dict]) -> Iterator[str]: ...
  ```

- [ ] Create `Skynet/providers/ollama.py` — implements LLMProvider via Ollama REST
- [ ] Create `Skynet/providers/claude.py` — implements LLMProvider via Anthropic API
- [ ] Create `Skynet/providers/registry.py` — reads settings, returns the right provider
  ```python
  def get_provider(role: str) -> LLMProvider:
      # role = "llm1" or "llm2"
      # reads settings.yaml, returns OllamaProvider or ClaudeProvider etc.
  ```

---

## PHASE 3 — brain.py (Context Controller)

brain.py owns context. LLM1 only sees what brain.py decides to give it.

- [ ] Create `Skynet/core/brain.py`
  - Receives transcribed user message
  - Builds messages array: [system_prompt] + [last N turns] + [new message]
  - V0.1 context strategy: rolling window, last 3 turns only
  - Calls `get_provider("llm1").complete(messages)`
  - Returns LLM1 response
  - Stores exchange in session history (for next turn's rolling window)

- [ ] Write LLM1 system prompt (what it knows, how it should respond, its role)

Context flow:
```
new message
    → brain.py builds fresh messages array (never sends full history)
    → get_provider("llm1").complete(messages)
    → LLM1 responds
    → brain.py stores exchange
    → returns response text
```

---

## PHASE 4 — Voice: STT (Whisper)

- [ ] Create `Skynet/voice/stt.py`
  - Uses faster-whisper
  - Records from microphone (push-to-talk or VAD)
  - Returns transcribed text
  - Must be non-blocking (async or threaded)

- [ ] Test: speak a sentence, get text back correctly

---

## PHASE 5 — Voice: TTS (VibeVoice)

- [ ] Create `Skynet/voice/tts.py`
  - Uses VibeVoice (Microsoft GitHub)
  - Takes text string
  - Speaks it out loud
  - Streaming preferred (start speaking before full response is ready)

- [ ] Test: pass a string, hear it spoken back

---

## PHASE 6 — Runtime Loop

- [ ] Create `Skynet/core/runtime.py` — the main loop
  ```
  while running:
      audio = stt.listen()          # wait for voice input
      text  = stt.transcribe(audio) # convert to text
      reply = brain.think(text)     # brain calls LLM1
      tts.speak(reply)              # speak the response
  ```
  - Handles boot → loop → graceful shutdown
  - Handles interrupt (Ctrl+C or voice "stop")

---

## PHASE 7 — Smoke Tests

- [ ] `tests/test_config.py` — settings.yaml loads, all keys validated
- [ ] `tests/test_providers.py` — OllamaProvider connects, returns a string response
- [ ] `tests/test_brain.py` — given a message, brain builds correct messages array and returns response
- [ ] `tests/test_brain_context.py` — brain sends only last 3 turns, not full history
- [ ] `tests/test_stt.py` — Whisper transcribes a test audio file correctly
- [ ] `tests/test_tts.py` — VibeVoice speaks a test string without error
- [ ] `tests/test_runtime.py` — full loop: text in → brain → response → no crash

---

## DONE when

- [ ] `main.py` boots and shows correct status screen
- [ ] Speak into mic → Whisper transcribes it
- [ ] brain.py sends controlled context (not full history) to LLM1
- [ ] LLM1 responds
- [ ] VibeVoice speaks the response aloud
- [ ] Run 5 turns in a row without crash
- [ ] Turn 5 does NOT include turns 1-2 in LLM1 context (rolling window working)

That is V0.1. Nothing else.

---

## Deferred (not V0.1)

- LLM2 (memory summarizer) — Phase 5 in version roadmap
- Tools (terminal, browser, filesystem) — Phase 4 in version roadmap
- Permissions system — Phase 4 in version roadmap
- ChromaDB / long-term memory — Phase 5 in version roadmap
- Desktop cognition / OCR / vision — Phase 3 in version roadmap
