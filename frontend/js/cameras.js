/**
 * DriveSight — Camera list management.
 */

const DriveSightCameras = (() => {
  let cameras = [];
  let filteredCameras = [];
  const container = () => document.getElementById('cameras-container');
  const countText = () => document.getElementById('camera-count-text');
  const dashCamerasOnline = () => document.getElementById('dash-cameras-online');

  function init() {
    fetchCameras();

    // Camera search
    const searchInput = document.getElementById('camera-search');
    if (searchInput) {
      searchInput.addEventListener('input', _debounce((e) => {
        _filterCameras(e.target.value);
      }, 250));
    }
  }

  async function fetchCameras() {
    try {
      const resp = await fetch('/api/cameras?active=true');
      const data = await resp.json();
      cameras = data.cameras || [];
      filteredCameras = cameras;
      _render();

      // Update stat displays
      if (countText()) countText().textContent = `${cameras.length} active`;
      if (dashCamerasOnline()) dashCamerasOnline().textContent = cameras.length;

      // Update hero mockup stat
      const mockupCameras = document.getElementById('mockup-cameras');
      if (mockupCameras) mockupCameras.textContent = cameras.length;

      // Update stats section
      const statCameras = document.getElementById('stat-cameras');
      if (statCameras) statCameras.textContent = cameras.length;

      // Add camera markers to map
      DriveSightMap.addCameraMarkers(cameras);
    } catch (err) {
      console.error('[Cameras] Fetch error:', err);
      _renderError();
    }
  }

  function _filterCameras(query) {
    if (!query.trim()) {
      filteredCameras = cameras;
    } else {
      const q = query.toLowerCase();
      filteredCameras = cameras.filter(cam =>
        cam.name.toLowerCase().includes(q) ||
        (cam.route || '').toLowerCase().includes(q) ||
        (cam.district || '').toLowerCase().includes(q) ||
        (cam.caltrans_id || '').toLowerCase().includes(q)
      );
    }
    _render();
  }

  function _render() {
    const el = container();
    if (!el) return;

    if (filteredCameras.length === 0) {
      el.innerHTML = `<div class="dash-loading">No cameras found</div>`;
      return;
    }

    // Show max 50 in the list
    const displayed = filteredCameras.slice(0, 50);

    el.innerHTML = displayed.map(cam => `
      <div class="dash-camera-item"
           onclick="DriveSightCameras.focusCamera(${cam.latitude}, ${cam.longitude}, ${cam.id})">
        <div class="dash-camera-status ${cam.is_active ? 'online' : 'offline'}"></div>
        <div class="dash-camera-info">
          <div class="dash-camera-name">${_escapeHtml(cam.name)}</div>
          <div class="dash-camera-route">${cam.route || ''} ${cam.direction || ''}</div>
        </div>
        <div class="dash-camera-district">${cam.district || ''}</div>
      </div>
    `).join('');

    if (filteredCameras.length > 50) {
      el.innerHTML += `
        <div class="dash-loading" style="font-size:0.75rem;">
          +${filteredCameras.length - 50} more cameras
        </div>
      `;
    }
  }

  function _renderError() {
    const el = container();
    if (el) {
      el.innerHTML = `<div class="dash-loading">Failed to load cameras.</div>`;
    }
  }

  function focusCamera(lat, lng, cameraId) {
    DriveSightMap.flyTo(lat, lng, 14);

    // Optionally load recent incidents for this camera
    _loadCameraDetail(cameraId);
  }

  async function _loadCameraDetail(cameraId) {
    try {
      const resp = await fetch(`/api/cameras/${cameraId}`);
      const data = await resp.json();

      const panel = document.getElementById('map-info-panel');
      if (panel && data.camera) {
        panel.style.display = 'block';
        document.getElementById('info-panel-title').textContent = data.camera.name;

        const recentIncidents = data.recent_incidents || [];
        document.getElementById('info-panel-body').innerHTML = `
          <div class="info-row">
            <span class="info-label">Route</span>
            <span class="info-value">${data.camera.route || 'N/A'} ${data.camera.direction || ''}</span>
          </div>
          <div class="info-row">
            <span class="info-label">District</span>
            <span class="info-value">${data.camera.district || 'N/A'}</span>
          </div>
          <div class="info-row">
            <span class="info-label">Status</span>
            <span class="info-value safe">${data.camera.is_active ? 'Active' : 'Offline'}</span>
          </div>
          <div class="info-row">
            <span class="info-label">Recent Incidents</span>
            <span class="info-value ${recentIncidents.length > 3 ? 'critical' : recentIncidents.length > 0 ? 'warning' : 'safe'}">${recentIncidents.length}</span>
          </div>
          ${recentIncidents.slice(0, 3).map(inc => `
            <div style="margin-top:8px;padding:8px;background:rgba(255,255,255,0.03);border-radius:8px;">
              <div style="font-size:0.7rem;color:${
                inc.severity === 'critical' ? '#e63946' :
                inc.severity === 'warning' ? '#ffa500' : '#ffcb6b'
              };font-weight:600;text-transform:uppercase;">${inc.severity} · ${inc.incident_type}</div>
              <div style="font-size:0.75rem;color:rgba(248,249,250,0.6);margin-top:2px;">${inc.description || ''}</div>
            </div>
          `).join('')}
        `;
      }
    } catch (err) {
      console.error('[Cameras] Detail fetch error:', err);
    }
  }

  function _escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  function _debounce(fn, delay) {
    let timer;
    return (...args) => {
      clearTimeout(timer);
      timer = setTimeout(() => fn(...args), delay);
    };
  }

  return { init, fetchCameras, focusCamera };
})();
