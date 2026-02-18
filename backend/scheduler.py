"""Background job scheduler.

Runs periodic tasks:
1. Camera polling + detection
2. Heat map recomputation
3. Stale alert cleanup
4. Stats broadcast via WebSocket
"""

import logging
import threading
import time
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_scheduler_started = False
_scheduler_lock = threading.Lock()


def start_scheduler(app, socketio):
    """Start background processing threads."""
    global _scheduler_started

    with _scheduler_lock:
        if _scheduler_started:
            return
        _scheduler_started = True

    logger.info("Starting DriveSight background scheduler...")

    # Thread: Camera processing loop
    processing_thread = threading.Thread(
        target=_processing_loop, args=(app, socketio), daemon=True
    )
    processing_thread.start()

    # Thread: Housekeeping (stale alerts, stats broadcast)
    housekeeping_thread = threading.Thread(
        target=_housekeeping_loop, args=(app, socketio), daemon=True
    )
    housekeeping_thread.start()

    logger.info("Background scheduler started with 2 threads")


def _processing_loop(app, socketio):
    """Main processing loop — polls cameras and runs detection."""
    from backend.config import Config

    # Wait for app to fully start
    time.sleep(5)

    while True:
        try:
            with app.app_context():
                _process_camera_batch(app, socketio)
        except Exception as e:
            logger.error(f"Processing loop error: {e}", exc_info=True)

        time.sleep(Config.CAMERA_POLL_INTERVAL_SECONDS)


def _process_camera_batch(app, socketio):
    """Process a batch of cameras for detections.

    Primary path: download real JPEG from Caltrans → run through
    SnapshotAnalyzer (optical-flow based CV).
    Fallback: if no image URL or download fails, use simulate_detection().
    """
    from backend.database import db
    from backend.models import Camera, Incident
    from backend.services.camera_ingester import fetch_camera_image
    from backend.services.detection import CameraAnalysisManager, simulate_detection
    from backend.services.alerting import create_alert_for_incident
    from backend.services.heatmap import compute_heatmap_data
    from backend.routes.websocket import (
        broadcast_new_incident,
        broadcast_heatmap_update,
    )

    # Persistent across calls (module-level would be better, but this
    # avoids circular-import headaches — the global is set once below).
    global _analysis_manager
    if "_analysis_manager" not in globals() or _analysis_manager is None:
        _analysis_manager = CameraAnalysisManager()

    # Get active cameras, preferring those not recently polled
    cameras = (
        Camera.query.filter_by(is_active=True)
        .order_by(Camera.last_polled.asc().nullsfirst())
        .limit(50)
        .all()
    )

    if not cameras:
        logger.debug("No active cameras to process")
        return

    new_incidents = []
    real_analysis_count = 0
    sim_fallback_count = 0

    for camera in cameras:
        detection_results: list = []

        # ---- Primary: real frame analysis ----
        if camera.image_url:
            try:
                frame = fetch_camera_image(camera)
                if frame is not None:
                    detection_results = _analysis_manager.analyze(camera.id, frame)
                    real_analysis_count += 1
                else:
                    # Download failed — fall back
                    result = simulate_detection(camera.latitude, camera.longitude)
                    detection_results = [result] if result and result.has_detection else []
                    sim_fallback_count += 1
            except Exception as e:
                logger.warning(f"CV analysis failed for camera {camera.caltrans_id}: {e}")
                result = simulate_detection(camera.latitude, camera.longitude)
                detection_results = [result] if result and result.has_detection else []
                sim_fallback_count += 1
        else:
            # No image URL — simulation only
            result = simulate_detection(camera.latitude, camera.longitude)
            detection_results = [result] if result and result.has_detection else []
            sim_fallback_count += 1

        # ---- Record any detections ----
        for result in detection_results:
            if not result.has_detection:
                continue

            lat = result.details.get("latitude", camera.latitude)
            lng = result.details.get("longitude", camera.longitude)

            incident = Incident(
                camera_id=camera.id,
                incident_type=result.incident_type,
                severity=result.severity,
                confidence=result.confidence,
                latitude=lat,
                longitude=lng,
                description=result.description,
                details=result.details,
            )
            db.session.add(incident)
            db.session.flush()

            alert = create_alert_for_incident(incident)
            new_incidents.append(incident)

            broadcast_new_incident(socketio, {
                "incident": incident.to_dict(),
                "alert": alert.to_dict() if alert else None,
            })

        camera.last_polled = datetime.now(timezone.utc)

    if new_incidents:
        db.session.commit()
        logger.info(
            f"Processed {len(cameras)} cameras "
            f"({real_analysis_count} real CV, {sim_fallback_count} simulated), "
            f"{len(new_incidents)} new incidents"
        )

        heatmap_data = compute_heatmap_data(hours=24)
        broadcast_heatmap_update(socketio, {
            "heatmap": heatmap_data,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        })
    else:
        db.session.commit()  # still commit last_polled updates
        logger.debug(
            f"Processed {len(cameras)} cameras "
            f"({real_analysis_count} real CV, {sim_fallback_count} simulated), "
            f"0 incidents"
        )

_analysis_manager = None


def _housekeeping_loop(app, socketio):
    """Periodic housekeeping tasks."""
    time.sleep(15)  # Initial delay

    while True:
        try:
            with app.app_context():
                # Resolve stale alerts
                from backend.services.alerting import resolve_stale_alerts

                resolve_stale_alerts(max_age_minutes=30)

                # Broadcast stats update
                from backend.routes.websocket import broadcast_stats_update
                from backend.routes.api import get_stats

                # Simulate a request context to call the stats endpoint logic
                _broadcast_live_stats(app, socketio)

        except Exception as e:
            logger.error(f"Housekeeping loop error: {e}", exc_info=True)

        time.sleep(60)  # Run every minute


def _broadcast_live_stats(app, socketio):
    """Compute and broadcast live stats."""
    from datetime import timedelta
    from backend.models import Camera, Incident, Alert

    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    stats = {
        "cameras_active": Camera.query.filter_by(is_active=True).count(),
        "incidents_today": Incident.query.filter(Incident.created_at >= today_start).count(),
        "active_alerts": Alert.query.filter_by(is_active=True).count(),
        "timestamp": now.isoformat(),
    }

    from backend.routes.websocket import broadcast_stats_update
    broadcast_stats_update(socketio, stats)
