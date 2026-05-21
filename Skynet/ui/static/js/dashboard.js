const Dashboard = (() => {
  const componentRows = {};
  let currentTurnEl = null;   // the .turn div for the current exchange
  let currentNexuxBody = null; // the .msg-body span being streamed into

  // ── Helpers ────────────────────────────────────────────────

  function esc(s) {
    return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  function fmt(unixTs) {
    return new Date(unixTs * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }

  function scrollFeed() {
    const feed = document.getElementById('chat-feed');
    if (feed) feed.scrollTop = feed.scrollHeight;
  }

  function hideEmpty() {
    const el = document.getElementById('empty-state');
    if (el) el.remove();
  }

  // ── Hardware ───────────────────────────────────────────────

  function makeHwCard(label, valueId, subId) {
    const card = document.createElement('div');
    card.className = 'hw-card';
    card.innerHTML = `
      <div class="hw-label">${label}</div>
      <div class="hw-value" id="${valueId}">—</div>
      ${subId ? `<div class="hw-sub" id="${subId}"></div>` : ''}
    `;
    return card;
  }

  function initHardwareRow() {
    const row = document.getElementById('hardware-row');
    if (!row) return;
    row.appendChild(makeHwCard('CPU', 'hw-cpu', null));
    row.appendChild(makeHwCard('GPU', 'hw-gpu', null));
    row.appendChild(makeHwCard('RAM', 'hw-ram', 'hw-ram-sub'));
    row.appendChild(makeHwCard('VRAM', 'hw-vram', 'hw-vram-sub'));
  }

  function setHw(id, val) {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
  }

  async function refreshHardware() {
    try {
      const hw = await Api.getHardware();
      setHw('hw-cpu',  hw.cpu_percent  != null ? `${hw.cpu_percent}%`            : '—');
      setHw('hw-gpu',  hw.gpu_percent  != null ? `${hw.gpu_percent}%`            : '—');
      setHw('hw-ram',  hw.ram_used_gb  != null ? `${hw.ram_used_gb} GB`          : '—');
      setHw('hw-ram-sub', hw.ram_total_gb != null ? `of ${hw.ram_total_gb} GB`   : '');
      setHw('hw-vram', hw.vram_used_gb != null ? `${hw.vram_used_gb} GB`         : '—');
      setHw('hw-vram-sub', hw.vram_total_gb != null ? `of ${hw.vram_total_gb} GB`: '');
    } catch (_) {}
  }

  // ── Components ─────────────────────────────────────────────

  function makeCompRow(name) {
    const row = document.createElement('div');
    row.className = 'comp-row';
    const nameEl = document.createElement('span');
    nameEl.className = 'comp-name';
    nameEl.textContent = name.replace(/_/g, ' ');
    const stateEl = document.createElement('span');
    stateEl.className = 'comp-state';
    stateEl.dataset.state = 'offline';
    stateEl.textContent = 'OFFLINE';
    row.appendChild(nameEl);
    row.appendChild(stateEl);
    componentRows[name] = stateEl;
    return row;
  }

  function initComponentCards(names) {
    const grid = document.getElementById('components-grid');
    if (!grid) return;
    names.forEach(n => grid.appendChild(makeCompRow(n)));
  }

  function updateComponentState(component, state) {
    const el = componentRows[component];
    if (!el) return;
    el.dataset.state = state;
    el.textContent = state.toUpperCase();
  }

  // ── Runtime badge + listen status ─────────────────────────

  function updateRuntimeBadge(mode) {
    const badge = document.getElementById('runtime-badge');
    if (badge) { badge.dataset.mode = mode; badge.textContent = mode.toUpperCase(); }

    const status = document.getElementById('listen-status');
    const label  = document.getElementById('listen-label');
    const active = mode === 'active';
    if (status) status.dataset.active = active;
    if (label)  label.textContent = active ? 'LISTENING' : mode.toUpperCase();
  }

  // ── Conversation ───────────────────────────────────────────

  function onUserMessage(transcript, ts) {
    hideEmpty();
    currentNexuxBody = null;  // next orchestrator_response starts a new NEXUX block

    const turn = document.createElement('div');
    turn.className = 'turn';
    turn.innerHTML = `<div class="turn-time">${fmt(ts)}</div>`;

    const msg = document.createElement('div');
    msg.className = 'msg user';
    msg.innerHTML = `
      <span class="msg-label">YOU</span>
      <div class="msg-body">${esc(transcript)}</div>
    `;
    turn.appendChild(msg);
    document.getElementById('chat-feed').appendChild(turn);
    currentTurnEl = turn;
    scrollFeed();
  }

  function onNexuxChunk(response) {
    if (!currentTurnEl) {
      // Edge case: response arrived without a preceding user turn
      currentTurnEl = document.createElement('div');
      currentTurnEl.className = 'turn';
      document.getElementById('chat-feed').appendChild(currentTurnEl);
    }

    if (!currentNexuxBody) {
      const msg = document.createElement('div');
      msg.className = 'msg nexux';
      msg.innerHTML = `<span class="msg-label">NEXUX</span><div class="msg-body"></div>`;
      currentTurnEl.appendChild(msg);
      currentNexuxBody = msg.querySelector('.msg-body');
    }

    // Append sentence (space-separated)
    if (currentNexuxBody.textContent) currentNexuxBody.textContent += ' ';
    currentNexuxBody.textContent += response;
    scrollFeed();
  }

  // ── STT Mode (synced between chat tab and config tab) ──────

  let _currentSttMode = 'continuous';

  function _applyModeToButtons(mode) {
    document.querySelectorAll('[data-mode],[data-stt-mode]').forEach(btn => {
      const m = btn.dataset.mode || btn.dataset.sttMode;
      btn.classList.toggle('active', m === mode);
    });
    const pttRow = document.getElementById('ptt-row');
    const status = document.getElementById('listen-status');
    const label  = document.getElementById('listen-label');
    if (pttRow) pttRow.style.display = mode === 'push_to_talk' ? '' : 'none';
    if (mode === 'disabled') {
      if (status) status.dataset.active = 'false';
      if (label)  label.textContent = 'VOICE OFF';
    } else if (mode === 'push_to_talk') {
      if (status) status.dataset.active = 'false';
      if (label)  label.textContent = 'PUSH-TO-TALK';
    }
    // continuous: listen-status active state driven by runtime mode WS event
    const savedEl = document.getElementById('input-saved');
    if (savedEl) {
      savedEl.style.opacity = '1';
      setTimeout(() => { savedEl.style.opacity = '0'; }, 1500);
    }
  }

  async function setSttMode(mode) {
    _currentSttMode = mode;
    _applyModeToButtons(mode);
    try { await Api.patchSttMode(mode); } catch (_) {}
  }

  function initSttModeButtons() {
    // chat tab buttons (data-mode)
    document.querySelectorAll('#chat-stt-modes [data-mode]').forEach(btn => {
      btn.addEventListener('click', () => setSttMode(btn.dataset.mode));
    });
    // config tab buttons (data-stt-mode)
    document.querySelectorAll('#cfg-stt-modes [data-stt-mode]').forEach(btn => {
      btn.addEventListener('click', () => setSttMode(btn.dataset.sttMode));
    });
  }

  async function loadSttMode() {
    try {
      const data = await Api.getSttMode();
      _currentSttMode = data.mode || 'continuous';
      _applyModeToButtons(_currentSttMode);
    } catch (_) { _applyModeToButtons('continuous'); }
  }

  // ── PTT button ─────────────────────────────────────────────

  function initPttButton() {
    const btn = document.getElementById('btn-ptt');
    if (!btn) return;
    const startRec = async () => {
      if (_currentSttMode !== 'push_to_talk') return;
      btn.classList.add('recording');
      btn.textContent = '🔴 RECORDING… RELEASE TO SEND';
      try { await Api.pttStart(); } catch (_) {}
    };
    const stopRec = async () => {
      if (!btn.classList.contains('recording')) return;
      btn.classList.remove('recording');
      btn.textContent = '⏺ HOLD TO SPEAK';
      try { await Api.pttStop(); } catch (_) {}
    };
    btn.addEventListener('mousedown',  startRec);
    btn.addEventListener('mouseup',    stopRec);
    btn.addEventListener('mouseleave', stopRec);
    btn.addEventListener('touchstart', (e) => { e.preventDefault(); startRec(); }, { passive: false });
    btn.addEventListener('touchend',   (e) => { e.preventDefault(); stopRec();  }, { passive: false });
  }

  // ── Text chat input ────────────────────────────────────────

  function initChatInput() {
    const textarea = document.getElementById('chat-input');
    const sendBtn  = document.getElementById('btn-send');
    if (!textarea || !sendBtn) return;

    // Auto-grow textarea
    textarea.addEventListener('input', () => {
      textarea.style.height = 'auto';
      textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
    });

    async function sendText() {
      const text = textarea.value.trim();
      if (!text) return;
      textarea.value = '';
      textarea.style.height = 'auto';
      sendBtn.disabled = true;
      try {
        await Api.sendChatMessage(text);
      } catch (_) {}
      sendBtn.disabled = false;
      textarea.focus();
    }

    textarea.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendText();
      }
    });
    sendBtn.addEventListener('click', sendText);
  }

  // ── Tools config list ──────────────────────────────────────

  async function loadToolsList() {
    const container = document.getElementById('tools-list');
    if (!container) return;
    try {
      const tools = await Api.getTools();
      container.innerHTML = '';
      tools.forEach(tool => {
        const row = document.createElement('div');
        row.className = 'tool-row';
        row.dataset.enabled = tool.enabled;
        row.innerHTML = `
          <span class="tool-name">${tool.name}</span>
          <input type="checkbox" class="toggle-ctrl" ${tool.enabled ? 'checked' : ''}
                 title="${tool.description}">
        `;
        const cb = row.querySelector('input');
        cb.addEventListener('change', async () => {
          row.dataset.enabled = cb.checked;
          try { await Api.patchTool(tool.name, cb.checked); } catch (_) {
            cb.checked = !cb.checked;
            row.dataset.enabled = cb.checked;
          }
        });
        container.appendChild(row);
      });
    } catch (_) {
      container.innerHTML = '<div style="font-size:11px;color:var(--text-dim)">Failed to load tools</div>';
    }
  }

  // ── Init ───────────────────────────────────────────────────

  async function loadInitialStatus() {
    try {
      const status = await Api.getStatus();
      updateRuntimeBadge(status.runtime_mode);
      const names = Object.keys(status.components);
      initComponentCards(names);
      names.forEach(n => updateComponentState(n, status.components[n]));
    } catch (_) {}
  }

  function updateContextStats(m) {
    const pct  = m.turns_total > 0 ? (m.turns_used / m.turns_total) * 100 : 0;
    const left = m.turns_total - m.turns_used;
    const fill  = document.getElementById('ctx-bar-fill');
    const label = document.getElementById('ctx-label');
    const tokens = document.getElementById('ctx-tokens');
    if (fill) {
      fill.style.width = pct + '%';
      fill.dataset.warn = pct >= 67 && pct < 84 ? 'true' : 'false';
      fill.dataset.crit = pct >= 84 ? 'true' : 'false';
    }
    if (label) label.textContent = `${m.turns_used} / ${m.turns_total} turns`;
    if (tokens) tokens.textContent = `~${m.tokens_est.toLocaleString()} tokens · ${left} turn${left !== 1 ? 's' : ''} left`;
  }

  function wireWebSocket() {
    WS.on('component_state',      (m) => updateComponentState(m.component, m.current));
    WS.on('runtime_mode',         (m) => updateRuntimeBadge(m.current));
    WS.on('stt_transcript',       (m) => onUserMessage(m.transcript, m.timestamp));
    WS.on('orchestrator_response',(m) => onNexuxChunk(m.response));
    WS.on('context_stats',        (m) => updateContextStats(m));
  }

  async function loadPromptInspector() {
    try {
      const data = await Api.getPromptDebug();
      const sys = document.getElementById('pi-system');
      const hist = document.getElementById('pi-history');
      if (sys) sys.textContent = data.system || '(empty)';
      if (hist) {
        if (!data.history?.length) {
          hist.textContent = '(no history yet)';
        } else {
          hist.innerHTML = '';
          data.history.forEach(m => {
            const div = document.createElement('div');
            div.className = 'pi-msg';
            const role = document.createElement('div');
            role.className = `pi-role ${m.role}`;
            role.textContent = m.role.toUpperCase();
            const content = document.createElement('div');
            content.className = 'pi-content';
            content.textContent = m.content;
            div.appendChild(role);
            div.appendChild(content);
            hist.appendChild(div);
          });
        }
      }
      const panel = document.getElementById('prompt-inspector');
      if (panel) panel.style.display = 'flex';
    } catch (_) {}
  }

  // ── Tab switching ──────────────────────────────────────────────────────

  function initTabs() {
    document.querySelectorAll('.tab-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const tab = btn.dataset.tab;
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.toggle('active', b.dataset.tab === tab));
        document.querySelectorAll('.tab-panel').forEach(p => p.classList.toggle('active', p.id === `tab-${tab}`));
      });
    });
  }

  function init() {
    initTabs();
    initHardwareRow();
    wireWebSocket();
    WS.start();
    loadInitialStatus();
    refreshHardware();
    setInterval(refreshHardware, 3000);
    Settings.init();
    Voices.init();
    initSttModeButtons();
    initPttButton();
    initChatInput();
    loadSttMode();
    loadToolsList();
    document.getElementById('btn-load-prompt')
      ?.addEventListener('click', loadPromptInspector);
  }

  return { init, updateComponentState, updateRuntimeBadge, setSttMode };
})();

document.addEventListener('DOMContentLoaded', () => Dashboard.init());
