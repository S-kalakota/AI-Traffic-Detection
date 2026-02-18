/**
 * DriveSight — Main application controller.
 *
 * Initializes all modules, handles scroll animations, loads data, renders charts.
 */

(function () {
  'use strict';

  // ===== SCROLL REVEAL =====
  const revealObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('visible');
        revealObserver.unobserve(entry.target);
      }
    });
  }, { threshold: 0.15, rootMargin: '0px 0px -60px 0px' });

  document.querySelectorAll('.reveal').forEach(el => revealObserver.observe(el));

  const lineObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('visible');
        lineObserver.unobserve(entry.target);
      }
    });
  }, { threshold: 0.5 });

  document.querySelectorAll('.line-reveal').forEach(el => lineObserver.observe(el));

  // ===== NAV SCROLL EFFECT =====
  const nav = document.querySelector('nav');
  window.addEventListener('scroll', () => {
    if (window.scrollY > 50) {
      nav.classList.add('scrolled');
    } else {
      nav.classList.remove('scrolled');
    }
  }, { passive: true });

  // ===== HERO PARALLAX =====
  const heroContent = document.querySelector('.hero-content');
  const sunGlow = document.querySelector('.sun-glow');
  const mountains = document.querySelector('.mountains');
  let ticking = false;

  window.addEventListener('scroll', () => {
    if (!ticking) {
      requestAnimationFrame(() => {
        const scrollY = window.scrollY;
        const vh = window.innerHeight;

        if (heroContent) {
          const progress = Math.min(scrollY / (vh * 0.5), 1);
          heroContent.style.opacity = 1 - progress;
          heroContent.style.transform = `translateY(${scrollY * -0.3}px) scale(${1 - progress * 0.05})`;
        }

        if (sunGlow) {
          sunGlow.style.transform = `translateX(-50%) translateY(${scrollY * -0.15}px) scale(${1 + scrollY * 0.0005})`;
        }

        if (mountains) {
          mountains.style.transform = `translateY(${scrollY * 0.08}px)`;
        }

        ticking = false;
      });
      ticking = true;
    }
  }, { passive: true });

  // ===== ANIMATED NUMBER COUNTING =====
  const statObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        const numEl = entry.target.querySelector('.big-num');
        if (numEl && !numEl.dataset.counted) {
          numEl.dataset.counted = 'true';
          animateNumber(numEl);
        }
        statObserver.unobserve(entry.target);
      }
    });
  }, { threshold: 0.4 });

  document.querySelectorAll('.stat-item').forEach(el => statObserver.observe(el));

  function animateNumber(el) {
    const finalText = el.textContent;
    const numMatch = finalText.match(/[\d,]+/);
    if (!numMatch) return;

    const finalNum = parseInt(numMatch[0].replace(/,/g, ''));
    const prefix = finalText.substring(0, finalText.indexOf(numMatch[0]));
    const suffix = finalText.substring(finalText.indexOf(numMatch[0]) + numMatch[0].length);
    const duration = 1200;
    const start = performance.now();

    function step(now) {
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      const current = Math.round(eased * finalNum);
      el.textContent = prefix + current.toLocaleString() + suffix;
      if (progress < 1) requestAnimationFrame(step);
      else el.textContent = finalText;
    }

    requestAnimationFrame(step);
  }

  // ===== FEATURE CARD 3D HOVER =====
  document.querySelectorAll('.feature-card').forEach(card => {
    card.addEventListener('mousemove', (e) => {
      if (!card.classList.contains('visible')) return;
      const rect = card.getBoundingClientRect();
      const x = (e.clientX - rect.left) / rect.width - 0.5;
      const y = (e.clientY - rect.top) / rect.height - 0.5;
      card.style.transform = `translateY(-6px) perspective(600px) rotateY(${x * 6}deg) rotateX(${y * -6}deg)`;
    });
    card.addEventListener('mouseleave', () => {
      if (!card.classList.contains('visible')) return;
      card.style.transform = 'translateY(0)';
    });
  });

  // ===== HEATMAP DOTS ANIMATION =====
  const heatmapObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      const dots = entry.target.querySelectorAll('.heatmap-dot');
      dots.forEach((dot, i) => {
        if (entry.isIntersecting) {
          dot.style.animationPlayState = 'running';
          dot.style.transition = `opacity 0.6s ease ${i * 0.1}s`;
          dot.style.opacity = '1';
        }
      });
    });
  }, { threshold: 0.2 });

  const heatmapEl = document.querySelector('.heatmap-container');
  if (heatmapEl) {
    heatmapEl.querySelectorAll('.heatmap-dot').forEach(dot => {
      dot.style.opacity = '0';
      dot.style.animationPlayState = 'paused';
    });
    heatmapObserver.observe(heatmapEl);
  }

  // ===== INFO PANEL CLOSE =====
  const infoPanelClose = document.getElementById('info-panel-close');
  if (infoPanelClose) {
    infoPanelClose.addEventListener('click', () => {
      document.getElementById('map-info-panel').style.display = 'none';
    });
  }

  // ===== INITIALIZE DASHBOARD ON SCROLL INTO VIEW =====
  let dashboardInitialized = false;

  const dashboardObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting && !dashboardInitialized) {
        dashboardInitialized = true;
        initDashboard();
        dashboardObserver.unobserve(entry.target);
      }
    });
  }, { threshold: 0.1 });

  const dashSection = document.getElementById('dashboard');
  if (dashSection) {
    dashboardObserver.observe(dashSection);
  }

  // Also init if user clicks the dashboard link
  document.querySelectorAll('a[href="#dashboard"]').forEach(link => {
    link.addEventListener('click', () => {
      if (!dashboardInitialized) {
        dashboardInitialized = true;
        setTimeout(initDashboard, 300);
      }
    });
  });

  // ===== DASHBOARD INITIALIZATION =====
  async function initDashboard() {
    console.log('[App] Initializing dashboard...');

    // Initialize the Leaflet map
    DriveSightMap.init('heatmap');

    // Connect WebSocket
    DriveSightSocket.connect();

    // Initialize modules
    DriveSightAlerts.init();
    DriveSightCameras.init();

    // Load heat map data
    await loadHeatmapData();

    // Load incidents for markers
    await loadIncidents();

    // Load stats
    await loadStats();

    // Initialize charts
    initCharts();

    // Set up auto-refresh
    setupAutoRefresh();

    // Refresh button
    const refreshBtn = document.getElementById('refresh-btn');
    if (refreshBtn) {
      refreshBtn.addEventListener('click', refreshAll);
    }

    // Time range selector
    const timeSelect = document.getElementById('timerange-select');
    if (timeSelect) {
      timeSelect.addEventListener('change', () => {
        refreshAll();
      });
    }

    // Listen for real-time heatmap updates
    DriveSightSocket.on('heatmap_update', (data) => {
      if (data.heatmap) {
        DriveSightMap.updateHeatmap(data.heatmap);
      }
    });

    // Listen for real-time stats updates
    DriveSightSocket.on('stats_update', (data) => {
      updateStatDisplays(data);
    });

    // Listen for new incidents
    DriveSightSocket.on('new_incident', (data) => {
      if (data.incident) {
        DriveSightMap.addIncidentMarkers([data.incident]);
      }
    });
  }

  async function loadHeatmapData() {
    const hours = getSelectedHours();
    try {
      const resp = await fetch(`/api/heatmap?hours=${hours}`);
      const data = await resp.json();
      DriveSightMap.updateHeatmap(data.heatmap || []);
    } catch (err) {
      console.error('[App] Heatmap load error:', err);
    }
  }

  async function loadIncidents() {
    const hours = getSelectedHours();
    try {
      const resp = await fetch(`/api/incidents?hours=${hours}&limit=200`);
      const data = await resp.json();
      DriveSightMap.addIncidentMarkers(data.incidents || []);

      // Update incidents today count
      const dashIncidents = document.getElementById('dash-incidents-today');
      if (dashIncidents) dashIncidents.textContent = data.total || 0;
    } catch (err) {
      console.error('[App] Incidents load error:', err);
    }
  }

  async function loadStats() {
    try {
      const resp = await fetch('/api/stats');
      const data = await resp.json();
      updateStatDisplays(data);
      updateCharts(data);
    } catch (err) {
      console.error('[App] Stats load error:', err);
    }
  }

  function updateStatDisplays(data) {
    const updates = {
      'dash-active-alerts': data.active_alerts,
      'dash-cameras-online': data.cameras_active,
      'dash-incidents-today': data.incidents_today,
      'mockup-alerts': data.incidents_today,
    };

    for (const [id, value] of Object.entries(updates)) {
      const el = document.getElementById(id);
      if (el && value !== undefined) el.textContent = value;
    }
  }

  function getSelectedHours() {
    const select = document.getElementById('timerange-select');
    return select ? parseInt(select.value) : 24;
  }

  async function refreshAll() {
    const refreshBtn = document.getElementById('refresh-btn');
    if (refreshBtn) refreshBtn.classList.add('spinning');

    await Promise.all([
      loadHeatmapData(),
      loadIncidents(),
      loadStats(),
      DriveSightAlerts.fetchAlerts(),
    ]);

    if (refreshBtn) {
      setTimeout(() => refreshBtn.classList.remove('spinning'), 800);
    }
  }

  function setupAutoRefresh() {
    // Refresh data every 30 seconds
    setInterval(refreshAll, 30000);
  }

  // ===== CHARTS =====
  let incidentTypeChart = null;
  let severityChart = null;
  let trendChart = null;

  function initCharts() {
    // Set Chart.js defaults for dark theme
    Chart.defaults.color = 'rgba(248, 249, 250, 0.5)';
    Chart.defaults.borderColor = 'rgba(255, 255, 255, 0.06)';

    // Incident type doughnut chart
    const typeCtx = document.getElementById('incident-type-chart');
    if (typeCtx) {
      incidentTypeChart = new Chart(typeCtx, {
        type: 'doughnut',
        data: {
          labels: ['Swerving', 'Speed', 'Aggressive', 'Stopped', 'Wrong-Way'],
          datasets: [{
            data: [0, 0, 0, 0, 0],
            backgroundColor: [
              '#e63946',
              '#ffa500',
              '#ffcb6b',
              '#2ec4b6',
              '#c0392b',
            ],
            borderWidth: 0,
            hoverOffset: 6,
          }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: true,
          cutout: '65%',
          plugins: {
            legend: {
              position: 'bottom',
              labels: {
                boxWidth: 8,
                padding: 12,
                font: { size: 10, family: 'DM Sans' },
              },
            },
          },
        },
      });
    }

    // Severity bar chart
    const sevCtx = document.getElementById('severity-chart');
    if (sevCtx) {
      severityChart = new Chart(sevCtx, {
        type: 'bar',
        data: {
          labels: ['Critical', 'Warning', 'Moderate', 'Low'],
          datasets: [{
            data: [0, 0, 0, 0],
            backgroundColor: [
              'rgba(230, 57, 70, 0.6)',
              'rgba(255, 165, 0, 0.6)',
              'rgba(255, 203, 107, 0.6)',
              'rgba(46, 196, 182, 0.6)',
            ],
            borderRadius: 6,
            borderSkipped: false,
          }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: true,
          indexAxis: 'y',
          plugins: { legend: { display: false } },
          scales: {
            x: {
              grid: { display: false },
              ticks: { font: { size: 10 } },
            },
            y: {
              grid: { display: false },
              ticks: { font: { size: 10 } },
            },
          },
        },
      });
    }

    // Trend line chart
    const trendCtx = document.getElementById('trend-chart');
    if (trendCtx) {
      trendChart = new Chart(trendCtx, {
        type: 'line',
        data: {
          labels: [],
          datasets: [{
            label: 'Incidents',
            data: [],
            borderColor: '#e63946',
            backgroundColor: 'rgba(230, 57, 70, 0.1)',
            fill: true,
            tension: 0.4,
            borderWidth: 2,
            pointRadius: 4,
            pointBackgroundColor: '#e63946',
            pointBorderColor: '#0b1120',
            pointBorderWidth: 2,
          }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
          },
          scales: {
            x: {
              grid: { display: false },
              ticks: { font: { size: 10 } },
            },
            y: {
              grid: { color: 'rgba(255,255,255,0.04)' },
              ticks: { font: { size: 10 } },
              beginAtZero: true,
            },
          },
          interaction: {
            intersect: false,
            mode: 'index',
          },
        },
      });
    }
  }

  function updateCharts(data) {
    // Update incident type chart
    if (incidentTypeChart && data.type_counts) {
      incidentTypeChart.data.datasets[0].data = [
        data.type_counts.swerving || 0,
        data.type_counts.speed_variance || 0,
        data.type_counts.aggressive || 0,
        data.type_counts.stopped_vehicle || 0,
        data.type_counts.wrong_way || 0,
      ];
      incidentTypeChart.update();
    }

    // Update severity chart
    if (severityChart && data.severity_counts) {
      severityChart.data.datasets[0].data = [
        data.severity_counts.critical || 0,
        data.severity_counts.warning || 0,
        data.severity_counts.moderate || 0,
        data.severity_counts.low || 0,
      ];
      severityChart.update();
    }

    // Update trend chart
    if (trendChart && data.daily_trend) {
      trendChart.data.labels = data.daily_trend.map(d => {
        const date = new Date(d.date);
        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
      });
      trendChart.data.datasets[0].data = data.daily_trend.map(d => d.count);
      trendChart.update();
    }
  }
})();
