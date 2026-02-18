"""Database models for DriveSight."""

from datetime import datetime, timezone
from backend.database import db


class Camera(db.Model):
    """A Caltrans highway camera."""

    __tablename__ = "cameras"

    id = db.Column(db.Integer, primary_key=True)
    caltrans_id = db.Column(db.String(64), unique=True, nullable=False, index=True)
    name = db.Column(db.String(256), nullable=False)
    district = db.Column(db.String(8))
    route = db.Column(db.String(32))
    direction = db.Column(db.String(16))
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    image_url = db.Column(db.String(512))
    stream_url = db.Column(db.String(512))
    is_active = db.Column(db.Boolean, default=True)
    last_polled = db.Column(db.DateTime)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )

    incidents = db.relationship("Incident", backref="camera", lazy="dynamic")

    def to_dict(self):
        return {
            "id": self.id,
            "caltrans_id": self.caltrans_id,
            "name": self.name,
            "district": self.district,
            "route": self.route,
            "direction": self.direction,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "image_url": self.image_url,
            "stream_url": self.stream_url,
            "is_active": self.is_active,
            "last_polled": self.last_polled.isoformat() if self.last_polled else None,
        }


class Incident(db.Model):
    """A detected driving incident."""

    __tablename__ = "incidents"

    id = db.Column(db.Integer, primary_key=True)
    camera_id = db.Column(db.Integer, db.ForeignKey("cameras.id"), nullable=False, index=True)
    incident_type = db.Column(db.String(64), nullable=False)  # swerving, speed_variance, wrong_way, stopped_vehicle, aggressive
    severity = db.Column(db.String(16), nullable=False)  # critical, warning, moderate, low
    confidence = db.Column(db.Float, nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text)
    details = db.Column(db.JSON)  # Raw detection data
    frame_url = db.Column(db.String(512))  # Snapshot of the detection
    acknowledged = db.Column(db.Boolean, default=False)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), index=True
    )

    def to_dict(self):
        return {
            "id": self.id,
            "camera_id": self.camera_id,
            "camera_name": self.camera.name if self.camera else None,
            "incident_type": self.incident_type,
            "severity": self.severity,
            "confidence": self.confidence,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "description": self.description,
            "details": self.details,
            "frame_url": self.frame_url,
            "acknowledged": self.acknowledged,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @property
    def severity_score(self):
        """Numeric severity for sorting/aggregation."""
        return {"critical": 4, "warning": 3, "moderate": 2, "low": 1}.get(
            self.severity, 0
        )


class Alert(db.Model):
    """An active alert dispatched to the dashboard."""

    __tablename__ = "alerts"

    id = db.Column(db.Integer, primary_key=True)
    incident_id = db.Column(db.Integer, db.ForeignKey("incidents.id"), nullable=False)
    alert_type = db.Column(db.String(32), nullable=False)  # critical, warning
    title = db.Column(db.String(256), nullable=False)
    message = db.Column(db.Text, nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    is_active = db.Column(db.Boolean, default=True, index=True)
    notified_chp = db.Column(db.Boolean, default=False)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )
    resolved_at = db.Column(db.DateTime)

    incident = db.relationship("Incident", backref="alert")

    def to_dict(self):
        return {
            "id": self.id,
            "incident_id": self.incident_id,
            "alert_type": self.alert_type,
            "title": self.title,
            "message": self.message,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "is_active": self.is_active,
            "notified_chp": self.notified_chp,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }


class HeatmapSnapshot(db.Model):
    """Pre-computed heat map data, refreshed periodically."""

    __tablename__ = "heatmap_snapshots"

    id = db.Column(db.Integer, primary_key=True)
    time_bucket = db.Column(db.String(32), nullable=False, index=True)  # e.g. "2026-02-12T14:00"
    data = db.Column(db.JSON, nullable=False)  # [{lat, lng, intensity}, ...]
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )
