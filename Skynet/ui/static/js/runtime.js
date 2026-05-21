document.addEventListener('DOMContentLoaded', () => {
  const INIT_IDS     = ['btn-initialize', 'btn-initialize-sys'];
  const SHUTDOWN_IDS = ['btn-shutdown', 'btn-shutdown-sys'];

  function getAll(ids) { return ids.map(id => document.getElementById(id)).filter(Boolean); }

  function syncButtons(mode) {
    const running = mode === 'active' || mode === 'degraded' || mode === 'initializing';
    getAll(INIT_IDS).forEach(btn => btn.disabled = running);
    getAll(SHUTDOWN_IDS).forEach(btn => btn.disabled = !running);
  }

  WS.on('runtime_mode', (m) => syncButtons(m.current));

  getAll(INIT_IDS).forEach(btn => {
    btn.addEventListener('click', async () => {
      getAll(INIT_IDS).forEach(b => b.disabled = true);
      try {
        await Api.initialize();
      } catch (e) {
        console.error('Initialize failed:', e);
        getAll(INIT_IDS).forEach(b => b.disabled = false);
      }
    });
  });

  getAll(SHUTDOWN_IDS).forEach(btn => {
    btn.addEventListener('click', async () => {
      getAll(SHUTDOWN_IDS).forEach(b => b.disabled = true);
      try {
        await Api.shutdown();
      } catch (e) {
        console.error('Shutdown failed:', e);
        getAll(SHUTDOWN_IDS).forEach(b => b.disabled = false);
      }
    });
  });

  Api.getStatus().then(s => syncButtons(s.runtime_mode)).catch(() => {});
});
