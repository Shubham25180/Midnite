const Settings = (() => {
  const INTIMACY_LABELS = ['PRO', 'FRIEND', 'CLOSE', 'ROMANTIC', 'EXPLICIT'];
  let _saveTimer = null;

  function el(id) { return document.getElementById(id); }

  function showSaved(toastId = 'settings-saved') {
    const t = el(toastId);
    if (!t) return;
    t.style.opacity = '1';
    setTimeout(() => { t.style.opacity = '0'; }, 1600);
  }

  function debounce(fn, ms = 350) {
    return (...args) => {
      clearTimeout(_saveTimer);
      _saveTimer = setTimeout(() => fn(...args), ms);
    };
  }

  // ── LLM2 (Supervisor) ────────────────────────────────────────────────────

  async function saveLLM2() {
    const enabledEl = el('set-llm2-enabled');
    const backendEl = el('set-llm2-backend');
    const modelEl   = el('set-llm2-model');
    if (!backendEl) return;
    try {
      await Api.patchLLM2({
        enabled: enabledEl ? enabledEl.checked : true,
        backend: backendEl.value,
        model:   modelEl?.value || '',
      });
      showSaved('llm2-saved');
    } catch (_) {}
  }

  function applyLLM2(llm2) {
    const enabledEl = el('set-llm2-enabled');
    if (enabledEl) enabledEl.checked = llm2.enabled !== false;
    const backendEl = el('set-llm2-backend');
    if (backendEl) backendEl.value = llm2.backend || 'ollama';
    const modelEl = el('set-llm2-model');
    if (modelEl) modelEl.value = llm2.model || '';
  }

  // ── LLM1 ─────────────────────────────────────────────────────────────────

  async function loadOllamaModels() {
    try {
      const { models } = await Api.getOllamaModels();
      const sel = el('set-llm-model-select');
      if (!sel || !models.length) return;
      const current = el('set-llm-model')?.value || '';
      sel.innerHTML = '';
      models.forEach(m => {
        const opt = document.createElement('option');
        opt.value = m;
        opt.textContent = m;
        if (m === current) opt.selected = true;
        sel.appendChild(opt);
      });
      sel.style.display = 'block';
      const input = el('set-llm-model');
      if (input) input.style.display = 'none';
    } catch (_) {}
  }

  async function saveLLM() {
    const backendEl = el('set-llm-backend');
    const modelEl = el('set-llm-model-select')?.style.display !== 'none'
      ? el('set-llm-model-select')
      : el('set-llm-model');
    if (!backendEl) return;
    try {
      await Api.patchLLM({
        backend: backendEl.value,
        model: modelEl?.value || '',
      });
      showSaved('llm-saved');
    } catch (_) {}
  }

  function applyLLM(llm) {
    const backendEl = el('set-llm-backend');
    if (backendEl) backendEl.value = llm.backend || 'ollama';
    const modelEl = el('set-llm-model');
    if (modelEl) modelEl.value = llm.model || '';
    if ((llm.backend || 'ollama') === 'ollama') loadOllamaModels();
  }

  // ── Persona ──────────────────────────────────────────────────────────────

  function readPersonaForm() {
    return {
      intimacy_level: parseInt(el('set-intimacy')?.value ?? 3),
      response_style: {
        max_sentences:      parseInt(el('set-maxsen')?.value ?? 4),
        no_roleplay_prefix: el('set-noroleplay')?.checked ?? true,
        asks_questions:     el('set-askq')?.checked ?? true,
        expresses_feelings: el('set-feelings')?.checked ?? true,
      },
    };
  }

  async function savePersona() {
    try {
      await Api.patchPersona(readPersonaForm());
      showSaved('persona-saved');
    } catch (_) {}
  }

  function applyPersona(p) {
    const intEl = el('set-intimacy');
    if (intEl) {
      intEl.value = p.intimacy_level ?? 3;
      const lbl = el('set-intimacy-val');
      if (lbl) lbl.textContent = INTIMACY_LABELS[intEl.value] ?? '';
    }
    const rs = p.response_style || {};
    const maxEl = el('set-maxsen');
    if (maxEl) maxEl.value = rs.max_sentences ?? 4;
    const nrEl = el('set-noroleplay');
    if (nrEl) nrEl.checked = rs.no_roleplay_prefix !== false;
    const aqEl = el('set-askq');
    if (aqEl) aqEl.checked = rs.asks_questions !== false;
    const feEl = el('set-feelings');
    if (feEl) feEl.checked = rs.expresses_feelings !== false;
  }

  // ── Voice ────────────────────────────────────────────────────────────────

  function batchLabel(n) { return n === 0 ? 'ALL' : String(n); }

  function updateEngineUI(backend) {
    const f5Panel = el('voice-f5-panel');
    const kokoroPanel = el('voice-kokoro-panel');
    if (f5Panel) f5Panel.style.display = backend === 'f5tts' ? 'block' : 'none';
    if (kokoroPanel) kokoroPanel.style.display = backend === 'kokoro' ? 'block' : 'none';
    document.querySelectorAll('.engine-btn').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.engine === backend);
    });
  }

  async function saveVoice() {
    const speedEl  = el('set-speed');
    const batchEl  = el('set-tts-batch');
    if (!speedEl) return;
    try {
      await Api.patchVoice({
        speed: parseFloat(speedEl.value),
        tts_batch: batchEl ? parseInt(batchEl.value) : 0,
      });
      showSaved('voice-saved');
    } catch (_) {}
  }

  async function switchEngine(backend) {
    updateEngineUI(backend);
    try {
      await Api.patchVoice({ backend });
      showSaved('voice-saved');
      if (backend === 'kokoro') loadKokoroVoiceSelect();
    } catch (_) {}
  }

  async function loadKokoroVoiceSelect() {
    try {
      const { voices, active } = await Api.getKokoroVoices();
      const sel = el('set-kokoro-voice');
      if (!sel) return;
      sel.innerHTML = '';
      const downloaded = voices.filter(v => v.downloaded);
      if (!downloaded.length) {
        const opt = document.createElement('option');
        opt.value = '';
        opt.textContent = 'No voices downloaded — go to VOICES tab';
        sel.appendChild(opt);
        return;
      }
      downloaded.forEach(v => {
        const opt = document.createElement('option');
        opt.value = v.id;
        opt.textContent = `${v.name} · ${v.accent} · ${v.style}`;
        if (v.id === active) opt.selected = true;
        sel.appendChild(opt);
      });
    } catch (_) {}
  }

  async function saveKokoroVoice() {
    const sel = el('set-kokoro-voice');
    if (!sel?.value) return;
    try {
      await Api.patchVoice({ voice_id: sel.value });
      showSaved('voice-saved');
    } catch (_) {}
  }

  function applyVoice(v) {
    const speedEl = el('set-speed');
    if (speedEl) {
      speedEl.value = v.speed ?? 1.0;
      const lbl = el('set-speed-val');
      if (lbl) lbl.textContent = Number(speedEl.value).toFixed(1) + '×';
    }
    const batchEl = el('set-tts-batch');
    if (batchEl) {
      batchEl.value = v.tts_batch ?? 0;
      const lbl = el('set-tts-batch-val');
      if (lbl) lbl.textContent = batchLabel(parseInt(batchEl.value));
    }
    updateEngineUI(v.backend || 'f5tts');
    if (v.backend === 'kokoro') loadKokoroVoiceSelect();
  }

  // ── Mic ──────────────────────────────────────────────────────────────────

  async function loadMicDevices() {
    try {
      const devices = await Api.getMicDevices();
      const sel = el('set-mic-device');
      if (!sel) return;
      sel.innerHTML = '<option value="">System default</option>';
      devices.forEach(d => {
        const opt = document.createElement('option');
        opt.value = d.name;
        opt.textContent = d.name;
        sel.appendChild(opt);
      });
    } catch (_) {}
  }

  async function saveMic() {
    const devEl = el('set-mic-device');
    const dbEl  = el('set-silence-db');
    try {
      await Api.patchMic({
        mic_device: devEl ? devEl.value : '',
        silence_db: dbEl  ? parseInt(dbEl.value) : 500,
      });
      showSaved('mic-saved');
    } catch (_) {}
  }

  function applyMic(m) {
    const devEl = el('set-mic-device');
    if (devEl && m.mic_device) {
      const found = [...devEl.options].some(o => o.value === m.mic_device);
      if (found) devEl.value = m.mic_device;
    }
    const dbEl = el('set-silence-db');
    if (dbEl) {
      dbEl.value = m.silence_db ?? 500;
      const lbl = el('set-silence-db-val');
      if (lbl) lbl.textContent = dbEl.value;
    }
  }

  // ── Wire controls ─────────────────────────────────────────────────────────

  const savePersonaDebounced = debounce(savePersona);
  const saveVoiceDebounced   = debounce(saveVoice);
  const saveMicDebounced     = debounce(saveMic);
  const saveLLMDebounced     = debounce(saveLLM);
  const saveLLM2Debounced    = debounce(saveLLM2);

  function wire() {
    // LLM2 (Supervisor)
    el('set-llm2-enabled')?.addEventListener('change', saveLLM2Debounced);
    el('set-llm2-backend')?.addEventListener('change', saveLLM2Debounced);
    el('set-llm2-model')?.addEventListener('change', saveLLM2Debounced);

    // LLM1
    el('set-llm-backend')?.addEventListener('change', () => {
      const backend = el('set-llm-backend')?.value;
      if (backend === 'ollama') loadOllamaModels();
      saveLLMDebounced();
    });
    el('set-llm-model')?.addEventListener('change', saveLLMDebounced);
    el('set-llm-model-select')?.addEventListener('change', () => {
      const sel = el('set-llm-model-select');
      const inp = el('set-llm-model');
      if (inp && sel) inp.value = sel.value;
      saveLLMDebounced();
    });

    // Engine switcher
    document.querySelectorAll('.engine-btn').forEach(btn => {
      btn.addEventListener('click', () => switchEngine(btn.dataset.engine));
    });

    // Kokoro voice selector
    el('set-kokoro-voice')?.addEventListener('change', saveKokoroVoice);

    // Speed
    el('set-speed')?.addEventListener('input', (e) => {
      const lbl = el('set-speed-val');
      if (lbl) lbl.textContent = Number(e.target.value).toFixed(1) + '×';
    });
    el('set-speed')?.addEventListener('change', saveVoiceDebounced);

    // TTS batch
    el('set-tts-batch')?.addEventListener('input', (e) => {
      const lbl = el('set-tts-batch-val');
      if (lbl) lbl.textContent = batchLabel(parseInt(e.target.value));
    });
    el('set-tts-batch')?.addEventListener('change', saveVoiceDebounced);

    // Persona
    el('set-intimacy')?.addEventListener('input', (e) => {
      const lbl = el('set-intimacy-val');
      if (lbl) lbl.textContent = INTIMACY_LABELS[e.target.value] ?? '';
    });
    el('set-intimacy')?.addEventListener('change', savePersonaDebounced);
    el('set-maxsen')?.addEventListener('change', savePersonaDebounced);
    ['set-noroleplay', 'set-askq', 'set-feelings'].forEach(id => {
      el(id)?.addEventListener('change', savePersonaDebounced);
    });

    // Mic
    el('set-mic-device')?.addEventListener('change', saveMicDebounced);
    el('set-silence-db')?.addEventListener('input', (e) => {
      const lbl = el('set-silence-db-val');
      if (lbl) lbl.textContent = e.target.value;
    });
    el('set-silence-db')?.addEventListener('change', saveMicDebounced);
    el('btn-refresh-mics')?.addEventListener('click', loadMicDevices);
  }

  // ── Init ─────────────────────────────────────────────────────────────────

  async function init() {
    wire();
    try {
      const [persona, voice, mic, llm, llm2] = await Promise.all([
        Api.getPersona(), Api.getVoice(), Api.getMic(), Api.getLLM(), Api.getLLM2(),
      ]);
      applyPersona(persona);
      applyVoice(voice);
      applyMic(mic);
      applyLLM(llm);
      applyLLM2(llm2);
      loadMicDevices().then(() => applyMic(mic));
    } catch (_) {}
  }

  return { init };
})();
