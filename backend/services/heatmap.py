"""Heat map aggregation service.

Aggregates detected incidents into geographic clusters with intensity values
for rendering on the frontend heat map.
"""

import logging
from datetime import datetime, timedelta, timezone
from collections import defaultdict

from backend.database import db
from backend.models import Incident, Camera

logger = logging.getLogger(__name__)

# Grid resolution for heat map (in degrees)
# ~0.01 degrees ≈ 1.1 km at California's latitude
GRID_RESOLUTION = 0.02


def compute_heatmap_data(hours: int = 24) -> list[dict]:
    """
    Compute heat map data from recent incidents.

    Returns a list of {lat, lng, intensity, severity, count} objects
    aggregated into a geographic grid.
    """
    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    incidents = (
        Incident.query.filter(Incident.created_at >= since)
        .all()
    )

    if not incidents:
        # Return camera-based baseline heat map with zero intensity
        return _get_baseline_heatmap()

    # Aggregate by grid cell
    grid: dict[tuple, dict] = defaultdict(lambda: {
        "count": 0,
        "total_severity": 0,
        "max_severity": "low",
        "total_confidence": 0,
        "types": defaultdict(int),
    })

    severity_order = {"critical": 4, "warning": 3, "moderate": 2, "low": 1}

    for incident in incidents:
        # Snap to grid
        grid_lat = round(incident.latitude / GRID_RESOLUTION) * GRID_RESOLUTION
        grid_lng = round(incident.longitude / GRID_RESOLUTION) * GRID_RESOLUTION
        cell = grid[(grid_lat, grid_lng)]

        cell["count"] += 1
        cell["total_severity"] += severity_order.get(incident.severity, 1)
        cell["total_confidence"] += incident.confidence

        if severity_order.get(incident.severity, 0) > severity_order.get(cell["max_severity"], 0):
            cell["max_severity"] = incident.severity

        cell["types"][incident.incident_type] += 1

    # Convert to output format
    heatmap = []
    max_count = max(cell["count"] for cell in grid.values()) if grid else 1

    for (lat, lng), cell in grid.items():
        # Intensity combines count, severity, and confidence
        count_factor = cell["count"] / max_count
        severity_factor = cell["total_severity"] / (cell["count"] * 4)
        confidence_factor = cell["total_confidence"] / cell["count"]

        intensity = round(
            (count_factor * 0.4 + severity_factor * 0.4 + confidence_factor * 0.2),
            3,
        )

        heatmap.append({
            "lat": round(lat, 5),
            "lng": round(lng, 5),
            "intensity": min(intensity, 1.0),
            "count": cell["count"],
            "max_severity": cell["max_severity"],
            "dominant_type": max(cell["types"], key=cell["types"].get) if cell["types"] else None,
        })

    # Sort by intensity descending
    heatmap.sort(key=lambda h: h["intensity"], reverse=True)

    return heatmap


def _get_baseline_heatmap() -> list[dict]:
    """
    Generate a baseline heat map from camera locations.
    Shows camera coverage even when no incidents are present.
    """
    cameras = Camera.query.filter_by(is_active=True).all()

    heatmap = []
    for cam in cameras:
        if cam.latitude and cam.longitude:
            heatmap.append({
                "lat": round(cam.latitude, 5),
                "lng": round(cam.longitude, 5),
                "intensity": 0.05,  # Minimal baseline intensity
                "count": 0,
                "max_severity": "none",
                "dominant_type": None,
            })

    return heatmap


def compute_region_summary(hours: int = 24) -> list[dict]:
    """
    Compute per-region summary statistics for the dashboard.
    Groups incidents by named regions of California.
    """
    regions = {
        "Greater Los Angeles": {"lat_range": (33.5, 34.5), "lng_range": (-118.8, -117.5)},
        "San Francisco Bay Area": {"lat_range": (37.2, 38.0), "lng_range": (-122.6, -121.5)},
        "Sacramento": {"lat_range": (38.3, 38.8), "lng_range": (-121.7, -121.2)},
        "San Diego": {"lat_range": (32.5, 33.1), "lng_range": (-117.4, -116.8)},
        "Central Valley": {"lat_range": (34.5, 37.2), "lng_range": (-121.0, -118.5)},
        "Inland Empire": {"lat_range": (33.7, 34.3), "lng_range": (-117.5, -116.5)},
        "Northern California": {"lat_range": (38.8, 42.0), "lng_range": (-124.5, -120.0)},
    }

    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    incidents = Incident.query.filter(Incident.created_at >= since).all()

    summaries = []
    for region_name, bounds in regions.items():
        region_incidents = [
            i for i in incidents
            if bounds["lat_range"][0] <= i.latitude <= bounds["lat_range"][1]
            and bounds["lng_range"][0] <= i.longitude <= bounds["lng_range"][1]
        ]

        if region_incidents:
            severity_counts = defaultdict(int)
            for i in region_incidents:
                severity_counts[i.severity] += 1

            summaries.append({
                "region": region_name,
                "total_incidents": len(region_incidents),
                "critical": severity_counts.get("critical", 0),
                "warning": severity_counts.get("warning", 0),
                "moderate": severity_counts.get("moderate", 0),
                "low": severity_counts.get("low", 0),
                "center_lat": (bounds["lat_range"][0] + bounds["lat_range"][1]) / 2,
                "center_lng": (bounds["lng_range"][0] + bounds["lng_range"][1]) / 2,
            })

    summaries.sort(key=lambda s: s["total_incidents"], reverse=True)
    return summaries
