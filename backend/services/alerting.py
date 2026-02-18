"""Alert dispatch service.

Manages alert creation, cooldowns, and CHP notification logic.
"""

import logging
from datetime import datetime, timedelta, timezone

from backend.database import db
from backend.models import Incident, Alert, Camera
from backend.config import Config

logger = logging.getLogger(__name__)


def create_alert_for_incident(incident: Incident) -> Alert | None:
    """
    Create an alert for a detected incident if warranted.

    Applies cooldown logic to avoid alert fatigue — won't create a new alert
    if a recent alert exists for the same camera and incident type.
    """
    # Check cooldown
    cooldown_since = datetime.now(timezone.utc) - timedelta(seconds=Config.ALERT_COOLDOWN_SECONDS)

    recent_alert = (
        Alert.query.join(Incident)
        .filter(
            Incident.camera_id == incident.camera_id,
            Incident.incident_type == incident.incident_type,
            Alert.created_at >= cooldown_since,
            Alert.is_active == True,  # noqa: E712
        )
        .first()
    )

    if recent_alert:
        logger.debug(
            f"Alert cooldown active for camera {incident.camera_id} / {incident.incident_type}"
        )
        return None

    # Determine alert type and title
    alert_type = "critical" if incident.severity == "critical" else "warning"

    camera = Camera.query.get(incident.camera_id)
    camera_name = camera.name if camera else f"Camera #{incident.camera_id}"

    type_labels = {
        "swerving": "Swerving Detected",
        "speed_variance": "Speed Anomaly",
        "wrong_way": "Wrong-Way Driver",
        "stopped_vehicle": "Stopped Vehicle",
        "aggressive": "Aggressive Driving",
    }

    title = f"{type_labels.get(incident.incident_type, 'Incident')} — {camera_name}"

    # Determine if CHP should be notified (critical incidents)
    notify_chp = incident.severity == "critical" and incident.confidence >= 0.85

    alert = Alert(
        incident_id=incident.id,
        alert_type=alert_type,
        title=title,
        message=incident.description or f"{incident.incident_type} detected with {incident.confidence:.0%} confidence.",
        latitude=incident.latitude,
        longitude=incident.longitude,
        is_active=True,
        notified_chp=notify_chp,
    )

    db.session.add(alert)
    db.session.commit()

    logger.info(f"Alert created: {title} (CHP notify: {notify_chp})")
    return alert


def resolve_stale_alerts(max_age_minutes: int = 30):
    """Auto-resolve alerts older than max_age_minutes."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=max_age_minutes)

    stale_alerts = Alert.query.filter(
        Alert.is_active == True,  # noqa: E712
        Alert.created_at < cutoff,
    ).all()

    for alert in stale_alerts:
        alert.is_active = False
        alert.resolved_at = datetime.now(timezone.utc)

    if stale_alerts:
        db.session.commit()
        logger.info(f"Auto-resolved {len(stale_alerts)} stale alerts")

    return len(stale_alerts)


def get_alert_summary() -> dict:
    """Get alert statistics for the dashboard."""
    active_alerts = Alert.query.filter_by(is_active=True).all()

    return {
        "total_active": len(active_alerts),
        "critical": sum(1 for a in active_alerts if a.alert_type == "critical"),
        "warning": sum(1 for a in active_alerts if a.alert_type == "warning"),
        "chp_notified": sum(1 for a in active_alerts if a.notified_chp),
    }
