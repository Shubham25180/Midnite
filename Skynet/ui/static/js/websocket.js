const WS = (() => {
  let socket = null;
  let handlers = {};
  let retryDelay = 1000;

  function connect() {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    socket = new WebSocket(`${proto}://${location.host}/ws/stream`);
    socket.onmessage = (ev) => {
      let msg;
      try { msg = JSON.parse(ev.data); } catch { return; }
      const fn = handlers[msg.type];
      if (fn) fn(msg);
    };
    socket.onclose = () => {
      setTimeout(() => { retryDelay = Math.min(retryDelay * 2, 16000); connect(); }, retryDelay);
    };
    socket.onopen = () => { retryDelay = 1000; };
  }

  return {
    on(type, fn) { handlers[type] = fn; },
    start() { connect(); },
  };
})();
