const Voices = (() => {
  let _recorder  = null;
  let _chunks    = [];
  let _stream    = null;
  let _timer     = null;
  let _elapsed   = 0;
  let _recording = false;

  function el(id) { return document.getElementById(id); }

  // ── Toast ─────────────────────────────────────────────────────────────────

  let _toastTimer = null;
  function toast(msg, ms = 4000) {
    const t = el('toast');
    if (!t) return;
    clearTimeout(_toastTimer);
    t.textContent = msg;
    t.classList.add('show');
    _toastTimer = setTimeout(() => t.classList.remove('show'), ms);
  }

  // ── Sub-tab switching ─────────────────────────────────────────────────────

  function switchSubtab(name) {
    document.querySelectorAll('.subnav-btn').forEach(b => b.classList.toggle('active', b.dataset.subtab === name));
    document.querySelectorAll('.voices-subpanel').forEach(p => p.classList.toggle('active', p.id === `voices-${name}`));
  }

  // ── F5-TTS Library ────────────────────────────────────────────────────────

  async function loadVoices() {
    try {
      const data = await Api.getVoices();
      renderLibrary(data);
    } catch (_) {}
  }

  function normPath(p) { return (p || '').replace(/\\/g, '/'); }

  function renderLibrary({ voices = [], active = '', active_extra = null }) {
    const list = el('voice-list');
    if (!list) return;
    list.innerHTML = '';

    const all = active_extra ? [active_extra, ...voices] : [...voices];
    if (all.length === 0) {
      list.innerHTML = '<div style="color:var(--text-dim);font-size:11px;padding:6px 0">No voices yet — record or upload one.</div>';
      return;
    }

    all.forEach(v => {
      const isActive = normPath(v.file) === normPath(active);
      const dur      = v.duration ? `${v.duration}s` : '';
      const row      = document.createElement('div');
      row.className  = 'voice-row' + (isActive ? ' v-active' : '');

      const useLabel = isActive ? 'ACTIVE' : 'USE';
      const useDis   = isActive || v.builtin ? ' disabled' : '';
      const delBtn   = v.builtin
        ? ''
        : `<button class="voice-btn v-del" data-action="del" data-name="${v.name}">✕</button>`;

      row.innerHTML = `
        <span class="voice-name">${v.name}${v.builtin ? ' <span style="color:var(--text-dim);font-size:9px">(current)</span>' : ''}</span>
        <span class="voice-dur">${dur}</span>
        <button class="voice-btn"${useDis} data-action="use" data-name="${v.name}">${useLabel}</button>
        ${delBtn}
      `;
      list.appendChild(row);
    });

    list.querySelectorAll('[data-action]').forEach(btn => {
      btn.addEventListener('click', async () => {
        const { action, name } = btn.dataset;
        if (action === 'use') await activateVoice(name);
        else if (action === 'del' && confirm(`Delete voice "${name}"?`)) await deleteVoice(name);
      });
    });
  }

  async function activateVoice(name) {
    toast('Switching voice…');
    try {
      await Api.activateVoice(name);
      toast('Voice activated — next speech uses the new voice');
      await loadVoices();
    } catch (_) { toast('Activation failed'); }
  }

  async function deleteVoice(name) {
    try {
      await Api.deleteVoice(name);
      toast(`"${name}" deleted`);
      await loadVoices();
    } catch (_) { toast('Delete failed'); }
  }

  // ── Kokoro Library ────────────────────────────────────────────────────────

  async function loadKokoroVoices() {
    try {
      const { voices, active } = await Api.getKokoroVoices();
      renderKokoroGrid(voices, active);
    } catch (_) {}
  }

  function renderKokoroGrid(voices, active) {
    const grid = el('kokoro-grid');
    if (!grid) return;
    grid.innerHTML = '';

    voices.forEach(v => {
      const isActive = v.id === active;
      const card = document.createElement('div');
      card.className = 'kokoro-card' + (isActive ? ' active' : '');

      const genderIcon = v.gender === 'F' ? '♀' : '♂';
      const dlBtn = v.downloaded
        ? `<button class="voice-btn" disabled style="opacity:0.4;cursor:default">✓ DL</button>`
        : `<button class="voice-btn v-dl" data-id="${v.id}">↓</button>`;
      const useBtn = isActive
        ? `<button class="voice-btn" disabled style="color:var(--accent);border-color:var(--accent)">ACTIVE</button>`
        : `<button class="voice-btn v-use" data-id="${v.id}"${!v.downloaded ? ' disabled' : ''}>USE</button>`;

      card.innerHTML = `
        <div class="kokoro-name">${v.name} <span style="color:var(--text-dim);font-size:10px">${genderIcon}</span></div>
        <div class="kokoro-meta">${v.accent} · ~1MB</div>
        <div class="kokoro-style">${v.style}</div>
        <div class="kokoro-actions">${useBtn}${dlBtn}</div>
      `;
      grid.appendChild(card);
    });

    grid.querySelectorAll('.v-use').forEach(btn => {
      btn.addEventListener('click', () => activateKokoroVoice(btn.dataset.id));
    });
    grid.querySelectorAll('.v-dl').forEach(btn => {
      btn.addEventListener('click', () => downloadKokoroVoice(btn.dataset.id, btn));
    });
  }

  async function activateKokoroVoice(id) {
    toast('Switching to Kokoro voice…');
    try {
      await Api.activateKokoroVoice(id);
      toast(`Kokoro voice activated — hot reloading`);
      await loadKokoroVoices();
    } catch (_) { toast('Activation failed'); }
  }

  async function downloadKokoroVoice(id, btn) {
    toast(`Downloading ${id}… (~1MB)`, 30000);
    if (btn) { btn.textContent = '…'; btn.disabled = true; }
    try {
      await Api.downloadKokoroVoice(id);
      toast(`${id} downloaded`);
      await loadKokoroVoices();
    } catch (e) {
      toast(`Download failed: ${e.message}`);
      if (btn) { btn.textContent = '↓'; btn.disabled = false; }
    }
  }

  async function downloadAll() {
    const btn = el('btn-dl-all');
    if (btn) { btn.textContent = 'DOWNLOADING…'; btn.disabled = true; }
    toast('Downloading all Kokoro voices (~11MB)…', 120000);
    try {
      const { downloaded, failed } = await Api.downloadAllKokoroVoices();
      const msg = `Downloaded ${downloaded.length} voices${failed.length ? ` · ${failed.length} failed` : ''}`;
      toast(msg);
      await loadKokoroVoices();
    } catch (e) {
      toast(`Download failed: ${e.message}`);
    } finally {
      if (btn) { btn.textContent = '↓ DOWNLOAD ALL'; btn.disabled = false; }
    }
  }

  // ── Recording ─────────────────────────────────────────────────────────────

  function mimeToExt(mt) {
    if (mt.includes('webm')) return 'webm';
    if (mt.includes('ogg'))  return 'ogg';
    if (mt.includes('mp4'))  return 'mp4';
    return 'audio';
  }

  function setRecordBtn(label, danger = false) {
    const btn = el('btn-record');
    if (!btn) return;
    btn.textContent = label;
    btn.style.borderColor = danger ? 'var(--red)' : '';
    btn.style.color       = danger ? 'var(--red)' : '';
  }

  async function startRecording() {
    try {
      _stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (_) { toast('Microphone access denied'); return; }

    _chunks = []; _elapsed = 0; _recording = true;
    _recorder = new MediaRecorder(_stream);
    _recorder.ondataavailable = e => { if (e.data.size > 0) _chunks.push(e.data); };
    _recorder.start(500);

    setRecordBtn('STOP (0s)', true);
    _timer = setInterval(() => {
      _elapsed++;
      setRecordBtn(`STOP (${_elapsed}s)`, true);
      if (_elapsed >= 60) stopAndSubmit();
    }, 1000);
  }

  async function stopAndSubmit() {
    clearInterval(_timer); _timer = null; _recording = false;
    setRecordBtn('● RECORD', false);

    if (!_recorder || _recorder.state === 'inactive') return;

    const mime = _recorder.mimeType;
    const blob = await new Promise(resolve => {
      _recorder.onstop = () => resolve(new Blob(_chunks, { type: mime }));
      _recorder.stop();
    });
    _stream?.getTracks().forEach(t => t.stop());
    _stream = null;

    if (_elapsed < 15) { toast('Recording too short — need at least 15 seconds'); return; }

    const name = voiceName() || `rec_${Date.now()}`;
    await submitAudio(blob, name, mimeToExt(mime));
  }

  // ── Upload ────────────────────────────────────────────────────────────────

  async function handleUpload(file) {
    const name = voiceName() || file.name.replace(/\.[^.]+$/, '');
    const ext  = file.name.split('.').pop() || 'audio';
    await submitAudio(file, name, ext);
  }

  async function submitAudio(blob, name, ext) {
    toast('Processing voice — transcribing, please wait…', 30000);
    try {
      await Api.uploadVoice(blob, name, ext);
      if (el('voice-name-input')) el('voice-name-input').value = '';
      toast('Voice saved!');
      await loadVoices();
    } catch (e) {
      toast('Failed to save voice — see console');
      console.error(e);
    }
  }

  function voiceName() { return (el('voice-name-input')?.value || '').trim(); }

  // ── Wire ──────────────────────────────────────────────────────────────────

  function wire() {
    // Sub-tab nav
    document.querySelectorAll('.subnav-btn').forEach(btn => {
      btn.addEventListener('click', () => switchSubtab(btn.dataset.subtab));
    });

    // Download all
    el('btn-dl-all')?.addEventListener('click', downloadAll);

    // F5-TTS recording
    el('btn-record')?.addEventListener('click', () => {
      if (_recording) stopAndSubmit();
      else startRecording();
    });

    // F5-TTS upload
    const input = el('upload-voice-input');
    el('btn-upload-voice')?.addEventListener('click', () => input?.click());
    input?.addEventListener('change', () => {
      if (input.files[0]) { handleUpload(input.files[0]); input.value = ''; }
    });
  }

  async function init() {
    wire();
    await Promise.all([loadVoices(), loadKokoroVoices()]);
  }

  return { init };
})();
