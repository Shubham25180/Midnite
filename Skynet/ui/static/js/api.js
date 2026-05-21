const Api = {
  async getStatus() {
    const res = await fetch('/api/status');
    if (!res.ok) throw new Error('status fetch failed');
    return res.json();
  },
  async initialize() {
    const res = await fetch('/api/runtime/initialize', { method: 'POST' });
    if (!res.ok) throw new Error('initialize failed');
    return res.json();
  },
  async shutdown() {
    const res = await fetch('/api/runtime/shutdown', { method: 'POST' });
    if (!res.ok) throw new Error('shutdown failed');
    return res.json();
  },
  async getHardware() {
    const res = await fetch('/api/hardware');
    if (!res.ok) throw new Error('hardware fetch failed');
    return res.json();
  },

  // ── Persona ──────────────────────────────────────────────────────────────
  async getPersona() {
    const res = await fetch('/api/settings/persona');
    if (!res.ok) throw new Error('persona fetch failed');
    return res.json();
  },
  async patchPersona(data) {
    const res = await fetch('/api/settings/persona', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error('persona patch failed');
    return res.json();
  },

  // ── LLM1 ─────────────────────────────────────────────────────────────────
  async getLLM() {
    const res = await fetch('/api/settings/llm');
    if (!res.ok) throw new Error('llm fetch failed');
    return res.json();
  },
  async patchLLM(data) {
    const res = await fetch('/api/settings/llm', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error('llm patch failed');
    return res.json();
  },
  // ── LLM2 (Supervisor) ────────────────────────────────────────────────────
  async getLLM2() {
    const res = await fetch('/api/settings/llm2');
    if (!res.ok) throw new Error('llm2 fetch failed');
    return res.json();
  },
  async patchLLM2(data) {
    const res = await fetch('/api/settings/llm2', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error('llm2 patch failed');
    return res.json();
  },

  async getOllamaModels() {
    const res = await fetch('/api/models');
    if (!res.ok) return { models: [] };
    return res.json();
  },

  // ── Voice settings ────────────────────────────────────────────────────────
  async getVoice() {
    const res = await fetch('/api/settings/voice');
    if (!res.ok) throw new Error('voice fetch failed');
    return res.json();
  },
  async patchVoice(data) {
    const res = await fetch('/api/settings/voice', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error('voice patch failed');
    return res.json();
  },

  // ── Mic ───────────────────────────────────────────────────────────────────
  async getMicDevices() {
    const res = await fetch('/api/settings/mic/devices');
    if (!res.ok) throw new Error('mic devices fetch failed');
    return res.json();
  },
  async getMic() {
    const res = await fetch('/api/settings/mic');
    if (!res.ok) throw new Error('mic fetch failed');
    return res.json();
  },
  async patchMic(data) {
    const res = await fetch('/api/settings/mic', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error('mic patch failed');
    return res.json();
  },

  // ── F5-TTS voice library ─────────────────────────────────────────────────
  async getVoices() {
    const res = await fetch('/api/voices');
    if (!res.ok) throw new Error('voices fetch failed');
    return res.json();
  },
  async uploadVoice(blob, name, ext) {
    const form = new FormData();
    form.append('file', blob, `${name}.${ext}`);
    form.append('name', name);
    const res = await fetch('/api/voices/upload', { method: 'POST', body: form });
    if (!res.ok) throw new Error('voice upload failed');
    return res.json();
  },
  async activateVoice(name) {
    const res = await fetch(`/api/voices/${encodeURIComponent(name)}/activate`, { method: 'POST' });
    if (!res.ok) throw new Error('voice activate failed');
    return res.json();
  },
  async deleteVoice(name) {
    const res = await fetch(`/api/voices/${encodeURIComponent(name)}`, { method: 'DELETE' });
    if (!res.ok) throw new Error('voice delete failed');
    return res.json();
  },

  // ── Kokoro voices ─────────────────────────────────────────────────────────
  async getKokoroVoices() {
    const res = await fetch('/api/voices/kokoro');
    if (!res.ok) throw new Error('kokoro voices fetch failed');
    return res.json();
  },
  async activateKokoroVoice(id) {
    const res = await fetch(`/api/voices/kokoro/${encodeURIComponent(id)}/activate`, { method: 'POST' });
    if (!res.ok) throw new Error('kokoro activate failed');
    return res.json();
  },
  async downloadKokoroVoice(id) {
    const res = await fetch(`/api/voices/kokoro/${encodeURIComponent(id)}/download`, { method: 'POST' });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || 'download failed');
    }
    return res.json();
  },
  async downloadAllKokoroVoices() {
    const res = await fetch('/api/voices/kokoro/download-all', { method: 'POST' });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || 'download-all failed');
    }
    return res.json();
  },

  // ── Chat text input ───────────────────────────────────────────────────────
  async sendChatMessage(text) {
    const res = await fetch('/api/chat/send', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    });
    if (!res.ok) throw new Error('send failed');
    return res.json();
  },

  // ── STT mode ──────────────────────────────────────────────────────────────
  async getSttMode() {
    const res = await fetch('/api/settings/stt');
    if (!res.ok) throw new Error('stt fetch failed');
    return res.json();
  },
  async patchSttMode(mode) {
    const res = await fetch('/api/settings/stt', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode }),
    });
    if (!res.ok) throw new Error('stt patch failed');
    return res.json();
  },

  // ── PTT ───────────────────────────────────────────────────────────────────
  async pttStart() {
    await fetch('/api/stt/ptt/start', { method: 'POST' });
  },
  async pttStop() {
    await fetch('/api/stt/ptt/stop', { method: 'POST' });
  },

  // ── Tools config ─────────────────────────────────────────────────────────
  async getTools() {
    const res = await fetch('/api/settings/tools');
    if (!res.ok) throw new Error('tools fetch failed');
    return res.json();
  },
  async patchTool(name, enabled) {
    const res = await fetch('/api/settings/tools', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, enabled }),
    });
    if (!res.ok) throw new Error('tool patch failed');
    return res.json();
  },

  // ── Debug ─────────────────────────────────────────────────────────────────
  async getPromptDebug() {
    const res = await fetch('/api/debug/prompt');
    if (!res.ok) throw new Error('prompt debug fetch failed');
    return res.json();
  },
};
