/**
 * DriveSight — Alert panel management.
 */

const DriveSightAlerts = (() => {
  let alerts = [];
  const container = () => document.getElementById('alerts-container');
  const badge = () => document.getElementById('alert-count-badge');
  const dashActiveAlerts = () => document.getElementById('dash-active-alerts');

  function init() {
    fetchAlerts();

    // Listen for real-time alert updates
    DriveSightSocket.on('new_incident', (data) => {
      if (data.alert) {
        _prependAlert(data.alert);
      }
    });

    DriveSightSocket.on('alert_update', (data) => {
      fetchAlerts(); // Refresh full list
    });
  }

  async function fetchAlerts() {
    try {
      const resp = await fetch('/api/alerts?active=true');
      const data = await resp.json();
      alerts = data.alerts || [];
      _render();
    } catch (err) {
      console.error('[Alerts] Fetch error:', err);
      _renderError();
    }
  }

  function _prependAlert(alert) {
    // Add to front of list
    alerts.unshift(alert);
    // Keep max 30
    if (alerts.length > 30) alerts = alerts.slice(0, 30);
    _render();

    // Flash effect
    const firstItem = container()?.querySelector('.dash-alert-item');
    if (firstItem) {
      firstItem.style.animation = 'alertFlash 1s ease-out';
      setTimeout(() => { firstItem.style.animation = ''; }, 1000);
    }
  }

  function _render() {
    const el = container();
    if (!el) return;

    if (badge()) badge().textContent = alerts.length;
    if (dashActiveAlerts()) dashActiveAlerts().textContent = alerts.length;

    if (alerts.length === 0) {
      el.innerHTML = `
        <div class="dash-loading" style="color:rgba(46,196,182,0.7);">
          ✓ No active alerts — all clear
        </div>
      `;
      return;
    }

    el.innerHTML = alerts.map(alert => `
      <div class="dash-alert-item ${alert.alert_type === 'warning' ? 'warning-alert' : ''}"
           data-lat="${alert.latitude}" data-lng="${alert.longitude}"
           onclick="DriveSightAlerts.focusAlert(${alert.latitude}, ${alert.longitude})">
        <div class="dash-alert-type ${alert.alert_type}">
          <span class="dash-alert-type-dot"></span>
          ${alert.alert_type === 'critical' ? 'Critical Alert' : 'Warning'}
          ${alert.notified_chp ? ' · CHP Notified' : ''}
        </div>
        <div class="dash-alert-title">${_escapeHtml(alert.title)}</div>
        <div class="dash-alert-message">${_escapeHtml(alert.message)}</div>
        <div class="dash-alert-meta">
          <span class="dash-alert-time">${_formatTime(alert.created_at)}</span>
        </div>
      </div>
    `).join('');
  }

  function _renderError() {
    const el = container();
    if (el) {
      el.innerHTML = `<div class="dash-loading">Failed to load alerts. Retrying...</div>`;
    }
  }

  function focusAlert(lat, lng) {
    DriveSightMap.flyTo(lat, lng, 13);

    // Show info panel
    const panel = document.getElementById('map-info-panel');
    if (panel) {
      panel.style.display = 'block';
      const alert = alerts.find(a => a.latitude === lat && a.longitude === lng);
      if (alert) {
        document.getElementById('info-panel-title').textContent = alert.title;
        document.getElementById('info-panel-body').innerHTML = `
          <div class="info-row">
            <span class="info-label">Type</span>
            <span class="info-value ${alert.alert_type}">${alert.alert_type.toUpperCase()}</span>
          </div>
          <div class="info-row">
            <span class="info-label">Message</span>
            <span class="info-value" style="max-width:180px;text-align:right;">${_escapeHtml(alert.message).substring(0, 100)}...</span>
          </div>
          <div class="info-row">
            <span class="info-label">Location</span>
            <span class="info-value">${lat.toFixed(4)}, ${lng.toFixed(4)}</span>
          </div>
          <div class="info-row">
            <span class="info-label">CHP Notified</span>
            <span class="info-value">${alert.notified_chp ? 'Yes' : 'No'}</span>
          </div>
          <div class="info-row">
            <span class="info-label">Time</span>
            <span class="info-value">${_formatTime(alert.created_at)}</span>
          </div>
        `;
      }
    }
  }

  function _formatTime(isoString) {
    if (!isoString) return '';
    const date = new Date(isoString);
    const now = new Date();
    const diff = (now - date) / 1000;
    if (diff < 60) return 'Just now';
    if (diff < 3600) return `${Math.floor(diff / 60)} min ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return date.toLocaleString();
  }

  function _escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  // Inject flash animation
  const style = document.createElement('style');
  style.textContent = `
    @keyframes alertFlash {
      0% { background: rgba(230, 57, 70, 0.3); transform: translateX(-10px); }
      100% { background: rgba(230, 57, 70, 0.08); transform: translateX(0); }
    }
  `;
  document.head.appendChild(style);

  return { init, fetchAlerts, focusAlert };
})();
