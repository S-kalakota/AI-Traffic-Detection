"""WebSocket event handlers for real-time updates."""

from flask_socketio import emit


def register_socket_events(socketio):
    """Register all Socket.IO event handlers."""

    @socketio.on("connect")
    def handle_connect():
        print("[WS] Client connected")
        emit("connection_ack", {"status": "connected", "message": "DriveSight real-time feed active"})

    @socketio.on("disconnect")
    def handle_disconnect():
        print("[WS] Client disconnected")

    @socketio.on("subscribe_alerts")
    def handle_subscribe_alerts(data=None):
        """Client subscribes to alert updates."""
        emit("subscribed", {"channel": "alerts"})

    @socketio.on("subscribe_heatmap")
    def handle_subscribe_heatmap(data=None):
        """Client subscribes to heatmap updates."""
        emit("subscribed", {"channel": "heatmap"})

    @socketio.on("request_snapshot")
    def handle_request_snapshot(data):
        """Client requests a fresh camera snapshot analysis."""
        camera_id = data.get("camera_id")
        if camera_id:
            emit("snapshot_queued", {"camera_id": camera_id})


def broadcast_new_incident(socketio, incident_data):
    """Broadcast a new incident to all connected clients."""
    socketio.emit("new_incident", incident_data)


def broadcast_alert_update(socketio, alert_data):
    """Broadcast an alert status change."""
    socketio.emit("alert_update", alert_data)


def broadcast_heatmap_update(socketio, heatmap_data):
    """Broadcast updated heat map data."""
    socketio.emit("heatmap_update", heatmap_data)


def broadcast_stats_update(socketio, stats_data):
    """Broadcast updated dashboard stats."""
    socketio.emit("stats_update", stats_data)
