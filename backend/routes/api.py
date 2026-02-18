"""REST API endpoints for DriveSight."""

from datetime import datetime, timedelta, timezone
from flask import Blueprint, request, jsonify

from backend.database import db
from backend.models import Camera, Incident, Alert, HeatmapSnapshot
from backend.services.heatmap import compute_heatmap_data

api_bp = Blueprint("api", __name__)


# ---------- CAMERAS ----------

@api_bp.route("/cameras")
def list_cameras():
    """List all monitored cameras with optional filters."""
    district = request.args.get("district")
    route = request.args.get("route")
    active_only = request.args.get("active", "true").lower() == "true"

    query = Camera.query
    if active_only:
        query = query.filter_by(is_active=True)
    if district:
        query = query.filter_by(district=district)
    if route:
        query = query.filter(Camera.route.ilike(f"%{route}%"))

    cameras = query.order_by(Camera.name).all()
    return jsonify({
        "cameras": [c.to_dict() for c in cameras],
        "total": len(cameras),
    })


@api_bp.route("/cameras/<int:camera_id>")
def get_camera(camera_id):
    """Camera detail with recent incidents."""
    camera = Camera.query.get_or_404(camera_id)
    recent_incidents = (
        Incident.query.filter_by(camera_id=camera_id)
        .order_by(Incident.created_at.desc())
        .limit(20)
        .all()
    )
    return jsonify({
        "camera": camera.to_dict(),
        "recent_incidents": [i.to_dict() for i in recent_incidents],
    })


# ---------- INCIDENTS ----------

@api_bp.route("/incidents")
def list_incidents():
    """Query incidents with filters."""
    hours = int(request.args.get("hours", "24"))
    severity = request.args.get("severity")
    incident_type = request.args.get("type")
    limit = min(int(request.args.get("limit", "200")), 1000)

    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    query = Incident.query.filter(Incident.created_at >= since)

    if severity:
        query = query.filter_by(severity=severity)
    if incident_type:
        query = query.filter_by(incident_type=incident_type)

    incidents = query.order_by(Incident.created_at.desc()).limit(limit).all()
    return jsonify({
        "incidents": [i.to_dict() for i in incidents],
        "total": len(incidents),
        "since": since.isoformat(),
    })


@api_bp.route("/incidents/<int:incident_id>/acknowledge", methods=["POST"])
def acknowledge_incident(incident_id):
    """Mark an incident as acknowledged."""
    incident = Incident.query.get_or_404(incident_id)
    incident.acknowledged = True

    # Also resolve any linked alert
    alert = Alert.query.filter_by(incident_id=incident_id, is_active=True).first()
    if alert:
        alert.is_active = False
        alert.resolved_at = datetime.now(timezone.utc)

    db.session.commit()
    return jsonify({"status": "acknowledged", "incident_id": incident_id})


# ---------- HEATMAP ----------

@api_bp.route("/heatmap")
def get_heatmap():
    """Get heat map data — aggregated incident density."""
    hours = int(request.args.get("hours", "24"))
    heatmap_data = compute_heatmap_data(hours=hours)
    return jsonify({
        "heatmap": heatmap_data,
        "hours": hours,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    })


# ---------- ALERTS ----------

@api_bp.route("/alerts")
def list_alerts():
    """Get active alerts."""
    active_only = request.args.get("active", "true").lower() == "true"
    query = Alert.query
    if active_only:
        query = query.filter_by(is_active=True)

    alerts = query.order_by(Alert.created_at.desc()).limit(50).all()
    return jsonify({
        "alerts": [a.to_dict() for a in alerts],
        "total": len(alerts),
    })


# ---------- STATS ----------

@api_bp.route("/stats")
def get_stats():
    """Dashboard statistics."""
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    total_cameras = Camera.query.filter_by(is_active=True).count()
    incidents_today = Incident.query.filter(Incident.created_at >= today_start).count()
    active_alerts = Alert.query.filter_by(is_active=True).count()

    # Incidents by severity today
    severity_counts = {}
    for sev in ["critical", "warning", "moderate", "low"]:
        severity_counts[sev] = (
            Incident.query.filter(
                Incident.created_at >= today_start, Incident.severity == sev
            ).count()
        )

    # Incidents by type today
    type_counts = {}
    for t in ["swerving", "speed_variance", "wrong_way", "stopped_vehicle", "aggressive"]:
        type_counts[t] = (
            Incident.query.filter(
                Incident.created_at >= today_start, Incident.incident_type == t
            ).count()
        )

    # Average confidence
    from sqlalchemy import func

    avg_conf = (
        db.session.query(func.avg(Incident.confidence))
        .filter(Incident.created_at >= today_start)
        .scalar()
    )

    # Incidents last 7 days for trend chart
    daily_counts = []
    for i in range(7):
        day_start = (now - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        count = Incident.query.filter(
            Incident.created_at >= day_start, Incident.created_at < day_end
        ).count()
        daily_counts.append({
            "date": day_start.strftime("%Y-%m-%d"),
            "count": count,
        })

    return jsonify({
        "cameras_active": total_cameras,
        "incidents_today": incidents_today,
        "active_alerts": active_alerts,
        "avg_confidence": round(avg_conf * 100, 1) if avg_conf else 0,
        "severity_counts": severity_counts,
        "type_counts": type_counts,
        "daily_trend": list(reversed(daily_counts)),
    })


# ---------- CAMERA SNAPSHOT PROXY ----------

@api_bp.route("/cameras/<int:camera_id>/snapshot")
def camera_snapshot(camera_id):
    """Proxy a camera's latest snapshot image."""
    import requests as req

    camera = Camera.query.get_or_404(camera_id)
    if not camera.image_url:
        return jsonify({"error": "No image URL for this camera"}), 404

    try:
        resp = req.get(camera.image_url, timeout=10)
        resp.raise_for_status()
        from flask import Response

        return Response(
            resp.content,
            content_type=resp.headers.get("Content-Type", "image/jpeg"),
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 502
