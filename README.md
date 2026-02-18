# DriveSight — AI-Powered Road Safety Intelligence

Real-time impaired and dangerous driving detection using California highway cameras, with live heat-map visualization.

## Architecture

```
┌─────────────┐     ┌──────────────────┐     ┌───────────────┐
│  Caltrans    │────▶│  Camera Ingester  │────▶│  Detection    │
│  CCTV Feeds  │     │  (poll + stream)  │     │  Engine (CV)  │
└─────────────┘     └──────────────────┘     └──────┬────────┘
                                                     │
                         ┌───────────────────────────┘
                         ▼
                  ┌──────────────┐     ┌──────────────┐
                  │  Incident DB │────▶│  Heat Map    │
                  │  (SQLite)    │     │  Aggregator  │
                  └──────────────┘     └──────┬───────┘
                                              │
                         ┌────────────────────┘
                         ▼
                  ┌──────────────┐     ┌──────────────┐
                  │  WebSocket   │────▶│  Dashboard   │
                  │  Server      │     │  (Frontend)  │
                  └──────────────┘     └──────────────┘
```

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Initialize database
python -c "from backend.app import create_app; app = create_app(); app.app_context().push(); from backend.database import db; db.create_all()"

# 3. Seed camera data from Caltrans
python -m backend.seed_cameras

# 4. Start the server
python run.py
```

Open http://localhost:5000 in your browser.

## Project Structure

```
├── backend/
│   ├── app.py                 # Flask app factory
│   ├── config.py              # Configuration
│   ├── database.py            # SQLAlchemy setup
│   ├── models.py              # DB models (Camera, Incident, Alert)
│   ├── routes/
│   │   ├── api.py             # REST API endpoints
│   │   └── websocket.py       # Real-time WebSocket events
│   ├── services/
│   │   ├── camera_ingester.py # Caltrans feed polling
│   │   ├── detection.py       # CV-based driving analysis
│   │   ├── heatmap.py         # Geographic heat aggregation
│   │   └── alerting.py        # Alert dispatch & cooldowns
│   ├── seed_cameras.py        # Populate DB from Caltrans API
│   └── scheduler.py           # Background job scheduling
├── frontend/
│   ├── index.html             # Main dashboard
│   ├── css/
│   │   └── styles.css         # All styles
│   └── js/
│       ├── app.js             # Main application
│       ├── heatmap.js         # Leaflet heat map
│       ├── alerts.js          # Real-time alert panel
│       ├── cameras.js         # Camera feed viewer
│       └── websocket.js       # Socket.IO client
├── .env                       # Environment config
├── requirements.txt
├── run.py                     # Entry point
└── README.md
```

## API Endpoints

| Method | Path                             | Description                                        |
| ------ | -------------------------------- | -------------------------------------------------- |
| GET    | `/api/cameras`                   | List all monitored cameras                         |
| GET    | `/api/cameras/:id`               | Camera detail + recent incidents                   |
| GET    | `/api/incidents`                 | Query incidents (filter by time, region, severity) |
| GET    | `/api/heatmap`                   | Heat map data (aggregated incident density)        |
| GET    | `/api/alerts`                    | Active alerts                                      |
| GET    | `/api/stats`                     | Dashboard statistics                               |
| POST   | `/api/incidents/:id/acknowledge` | Acknowledge an alert                               |

## WebSocket Events

| Event            | Direction       | Description           |
| ---------------- | --------------- | --------------------- |
| `new_incident`   | Server → Client | New detection event   |
| `alert_update`   | Server → Client | Alert status change   |
| `heatmap_update` | Server → Client | Heat map data refresh |
| `stats_update`   | Server → Client | Live stats update     |

## Detection Capabilities

- **Swerving / Lane Departure** — Lateral movement analysis across frames
- **Erratic Speed Changes** — Velocity variance above threshold
- **Wrong-Way Driving** — Direction-of-travel vs expected flow
- **Stopped Vehicle in Lane** — Stationary object in active lane
- **Aggressive Driving** — Rapid acceleration / hard braking patterns
