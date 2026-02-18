"""Flask application factory."""

import os
from flask import Flask, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO

from backend.config import Config
from backend.database import db

socketio = SocketIO(cors_allowed_origins="*", async_mode="threading")


def create_app(config_class=Config):
    app = Flask(
        __name__,
        static_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend"),
        static_url_path="/static",
    )
    app.config.from_object(config_class)

    # Extensions
    db.init_app(app)
    CORS(app)
    socketio.init_app(app)

    # Create tables
    with app.app_context():
        from backend import models  # noqa: F401

        db.create_all()

    # Register blueprints
    from backend.routes.api import api_bp

    app.register_blueprint(api_bp, url_prefix="/api")

    # Register websocket handlers
    from backend.routes.websocket import register_socket_events

    register_socket_events(socketio)

    # Serve frontend
    @app.route("/")
    def index():
        return send_from_directory(app.static_folder, "index.html")

    @app.route("/css/<path:filename>")
    def css(filename):
        return send_from_directory(os.path.join(app.static_folder, "css"), filename)

    @app.route("/js/<path:filename>")
    def js(filename):
        return send_from_directory(os.path.join(app.static_folder, "js"), filename)

    # Start background scheduler
    from backend.scheduler import start_scheduler

    with app.app_context():
        start_scheduler(app, socketio)

    return app
