/**
 * DriveSight — Interactive Leaflet heat map module.
 */

const DriveSightMap = (() => {
  let map = null;
  let heatLayer = null;
  let markerLayer = null;
  let cameraMarkers = {};

  // Custom icons
  const incidentIcons = {
    critical: _createIcon('#e63946', 12),
    warning: _createIcon('#ffa500', 10),
    moderate: _createIcon('#ffcb6b', 8),
    low: _createIcon('#2ec4b6', 7),
  };

  const cameraIcon = L.divIcon({
    className: 'camera-map-marker',
    html: `<div style="
      width: 10px; height: 10px; border-radius: 50%;
      background: rgba(46, 196, 182, 0.6);
      border: 2px solid rgba(46, 196, 182, 0.3);
      box-shadow: 0 0 6px rgba(46, 196, 182, 0.3);
    "></div>`,
    iconSize: [10, 10],
    iconAnchor: [5, 5],
  });

  function _createIcon(color, size) {
    return L.divIcon({
      className: 'incident-map-marker',
      html: `<div style="
        width: ${size}px; height: ${size}px; border-radius: 50%;
        background: ${color};
        box-shadow: 0 0 ${size}px ${color}80, 0 0 ${size * 2}px ${color}40;
        animation: markerPulse 2s ease-in-out infinite;
      "></div>`,
      iconSize: [size, size],
      iconAnchor: [size / 2, size / 2],
    });
  }

  function init(containerId = 'heatmap') {
    // California center
    map = L.map(containerId, {
      center: [36.7783, -119.4179],
      zoom: 6,
      minZoom: 5,
      maxZoom: 15,
      zoomControl: true,
      attributionControl: false,
    });

    // Dark map tiles (CartoDB Dark Matter)
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
      maxZoom: 19,
      subdomains: 'abcd',
    }).addTo(map);

    // Initialize empty heat layer
    heatLayer = L.heatLayer([], {
      radius: 35,
      blur: 25,
      maxZoom: 12,
      max: 1.0,
      gradient: {
        0.0: '#2ec4b6',
        0.25: '#2ec4b6',
        0.4: '#ffcb6b',
        0.6: '#ffa500',
        0.8: '#e63946',
        1.0: '#c0392b',
      },
    }).addTo(map);

    // Marker layer for incident markers
    markerLayer = L.layerGroup().addTo(map);

    // Add a pulse animation style
    const style = document.createElement('style');
    style.textContent = `
      @keyframes markerPulse {
        0%, 100% { transform: scale(1); opacity: 0.8; }
        50% { transform: scale(1.5); opacity: 1; }
      }
    `;
    document.head.appendChild(style);

    return map;
  }

  function updateHeatmap(heatmapData) {
    if (!heatLayer || !heatmapData) return;

    const points = heatmapData.map(point => [
      point.lat,
      point.lng,
      point.intensity || 0.5,
    ]);

    heatLayer.setLatLngs(points);
  }

  function addIncidentMarkers(incidents) {
    if (!markerLayer) return;
    markerLayer.clearLayers();

    incidents.forEach(incident => {
      const icon = incidentIcons[incident.severity] || incidentIcons.low;
      const marker = L.marker([incident.latitude, incident.longitude], { icon })
        .addTo(markerLayer);

      const typeLabel = {
        swerving: 'Swerving Detected',
        speed_variance: 'Speed Anomaly',
        wrong_way: 'Wrong-Way Driver',
        stopped_vehicle: 'Stopped Vehicle',
        aggressive: 'Aggressive Driving',
      }[incident.incident_type] || incident.incident_type;

      marker.bindPopup(`
        <div style="
          background: rgba(10,15,26,0.95);
          border: 1px solid rgba(255,255,255,0.1);
          border-radius: 10px;
          padding: 14px;
          color: #f8f9fa;
          font-family: 'DM Sans', sans-serif;
          min-width: 220px;
        ">
          <div style="font-size:0.65rem;text-transform:uppercase;letter-spacing:0.08em;color:${
            incident.severity === 'critical' ? '#e63946' :
            incident.severity === 'warning' ? '#ffa500' : '#ffcb6b'
          };font-weight:700;margin-bottom:6px;">
            ● ${incident.severity} — ${typeLabel}
          </div>
          <div style="font-size:0.85rem;font-weight:600;margin-bottom:6px;">
            ${incident.camera_name || 'Unknown Camera'}
          </div>
          <div style="font-size:0.78rem;color:rgba(248,249,250,0.7);line-height:1.5;margin-bottom:8px;">
            ${incident.description || 'No description available.'}
          </div>
          <div style="display:flex;justify-content:space-between;font-size:0.7rem;color:rgba(248,249,250,0.5);">
            <span>Confidence: ${(incident.confidence * 100).toFixed(0)}%</span>
            <span>${_formatTime(incident.created_at)}</span>
          </div>
        </div>
      `, {
        className: 'dark-popup',
        maxWidth: 280,
      });
    });
  }

  function addCameraMarkers(cameras) {
    cameras.forEach(camera => {
      if (cameraMarkers[camera.id]) return;

      const marker = L.marker([camera.latitude, camera.longitude], { icon: cameraIcon })
        .addTo(map);

      marker.bindPopup(`
        <div style="
          background: rgba(10,15,26,0.95);
          border: 1px solid rgba(255,255,255,0.1);
          border-radius: 10px;
          padding: 12px;
          color: #f8f9fa;
          font-family: 'DM Sans', sans-serif;
        ">
          <div style="font-size:0.65rem;text-transform:uppercase;letter-spacing:0.08em;color:#2ec4b6;font-weight:700;margin-bottom:4px;">
            📹 Camera
          </div>
          <div style="font-size:0.85rem;font-weight:600;">${camera.name}</div>
          <div style="font-size:0.75rem;color:rgba(248,249,250,0.6);margin-top:4px;">
            ${camera.route || ''} ${camera.direction || ''} · District ${camera.district || 'N/A'}
          </div>
        </div>
      `, { className: 'dark-popup', maxWidth: 240 });

      cameraMarkers[camera.id] = marker;
    });
  }

  function flyTo(lat, lng, zoom = 12) {
    if (map) {
      map.flyTo([lat, lng], zoom, { duration: 1.5 });
    }
  }

  function fitCalifornia() {
    if (map) {
      map.fitBounds([[32.5, -124.5], [42.0, -114.0]], { padding: [20, 20] });
    }
  }

  function _formatTime(isoString) {
    if (!isoString) return '';
    const date = new Date(isoString);
    const now = new Date();
    const diff = (now - date) / 1000;
    if (diff < 60) return 'Just now';
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return date.toLocaleDateString();
  }

  // Override Leaflet popup styling for dark theme
  const popupStyle = document.createElement('style');
  popupStyle.textContent = `
    .dark-popup .leaflet-popup-content-wrapper {
      background: transparent !important;
      box-shadow: none !important;
      border-radius: 10px !important;
      padding: 0 !important;
    }
    .dark-popup .leaflet-popup-content {
      margin: 0 !important;
    }
    .dark-popup .leaflet-popup-tip {
      background: rgba(10,15,26,0.95) !important;
      border: 1px solid rgba(255,255,255,0.1) !important;
    }
    .leaflet-popup-close-button {
      color: rgba(255,255,255,0.5) !important;
    }
    .leaflet-popup-close-button:hover {
      color: white !important;
    }
  `;
  document.head.appendChild(popupStyle);

  return { init, updateHeatmap, addIncidentMarkers, addCameraMarkers, flyTo, fitCalifornia };
})();
