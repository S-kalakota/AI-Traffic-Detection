/**
 * DriveSight — WebSocket client for real-time updates.
 */

const DriveSightSocket = (() => {
  let socket = null;
  const listeners = {
    new_incident: [],
    alert_update: [],
    heatmap_update: [],
    stats_update: [],
    connection_change: [],
  };

  function connect() {
    socket = io(window.location.origin, {
      reconnection: true,
      reconnectionDelay: 2000,
      reconnectionAttempts: 20,
    });

    socket.on('connect', () => {
      console.log('[WS] Connected to DriveSight server');
      socket.emit('subscribe_alerts');
      socket.emit('subscribe_heatmap');
      _notify('connection_change', { connected: true });
      _updateConnectionUI(true);
    });

    socket.on('disconnect', () => {
      console.log('[WS] Disconnected');
      _notify('connection_change', { connected: false });
      _updateConnectionUI(false);
    });

    socket.on('connection_ack', (data) => {
      console.log('[WS] Server acknowledged:', data.message);
    });

    // Real-time events
    socket.on('new_incident', (data) => {
      console.log('[WS] New incident:', data);
      _notify('new_incident', data);
    });

    socket.on('alert_update', (data) => {
      console.log('[WS] Alert update:', data);
      _notify('alert_update', data);
    });

    socket.on('heatmap_update', (data) => {
      console.log('[WS] Heatmap update');
      _notify('heatmap_update', data);
    });

    socket.on('stats_update', (data) => {
      _notify('stats_update', data);
    });

    return socket;
  }

  function on(event, callback) {
    if (listeners[event]) {
      listeners[event].push(callback);
    }
  }

  function off(event, callback) {
    if (listeners[event]) {
      listeners[event] = listeners[event].filter(cb => cb !== callback);
    }
  }

  function emit(event, data) {
    if (socket && socket.connected) {
      socket.emit(event, data);
    }
  }

  function _notify(event, data) {
    if (listeners[event]) {
      listeners[event].forEach(cb => {
        try { cb(data); } catch (e) { console.error(`[WS] Listener error for ${event}:`, e); }
      });
    }
  }

  function _updateConnectionUI(connected) {
    let indicator = document.querySelector('.connection-status');
    if (!indicator) {
      indicator = document.createElement('div');
      indicator.className = 'connection-status';
      indicator.innerHTML = `
        <span class="connection-dot"></span>
        <span class="connection-text"></span>
      `;
      document.body.appendChild(indicator);
    }

    const dot = indicator.querySelector('.connection-dot');
    const text = indicator.querySelector('.connection-text');

    if (connected) {
      dot.className = 'connection-dot connected';
      text.textContent = 'Live';
      indicator.style.borderColor = 'rgba(46, 196, 182, 0.2)';
    } else {
      dot.className = 'connection-dot disconnected';
      text.textContent = 'Reconnecting...';
      indicator.style.borderColor = 'rgba(230, 57, 70, 0.2)';
    }
  }

  return { connect, on, off, emit };
})();
