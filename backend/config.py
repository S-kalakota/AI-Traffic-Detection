"""Application configuration."""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-secret-key")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///drivesight.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Caltrans
    CALTRANS_CCTV_URL = os.getenv(
        "CALTRANS_CCTV_URL",
        "https://cwwp2.dot.ca.gov/data/d7/cctv/cctvStatusD07.json",
    )

    # All Caltrans district endpoints for statewide coverage
    CALTRANS_DISTRICTS = {
        "D1": "https://cwwp2.dot.ca.gov/data/d1/cctv/cctvStatusD01.json",
        "D2": "https://cwwp2.dot.ca.gov/data/d2/cctv/cctvStatusD02.json",
        "D3": "https://cwwp2.dot.ca.gov/data/d3/cctv/cctvStatusD03.json",
        "D4": "https://cwwp2.dot.ca.gov/data/d4/cctv/cctvStatusD04.json",
        "D5": "https://cwwp2.dot.ca.gov/data/d5/cctv/cctvStatusD05.json",
        "D6": "https://cwwp2.dot.ca.gov/data/d6/cctv/cctvStatusD06.json",
        "D7": "https://cwwp2.dot.ca.gov/data/d7/cctv/cctvStatusD07.json",
        "D8": "https://cwwp2.dot.ca.gov/data/d8/cctv/cctvStatusD08.json",
        "D9": "https://cwwp2.dot.ca.gov/data/d9/cctv/cctvStatusD09.json",
        "D10": "https://cwwp2.dot.ca.gov/data/d10/cctv/cctvStatusD10.json",
        "D11": "https://cwwp2.dot.ca.gov/data/d11/cctv/cctvStatusD11.json",
        "D12": "https://cwwp2.dot.ca.gov/data/d12/cctv/cctvStatusD12.json",
    }

    # Detection
    SWERVE_THRESHOLD = float(os.getenv("SWERVE_THRESHOLD", "0.35"))
    SPEED_VARIANCE_THRESHOLD = float(os.getenv("SPEED_VARIANCE_THRESHOLD", "20"))
    WRONG_WAY_CONFIDENCE = float(os.getenv("WRONG_WAY_CONFIDENCE", "0.80"))
    MIN_DETECTION_CONFIDENCE = float(os.getenv("MIN_DETECTION_CONFIDENCE", "0.60"))

    # Alerting
    ALERT_COOLDOWN_SECONDS = int(os.getenv("ALERT_COOLDOWN_SECONDS", "300"))
    CRITICAL_INCIDENT_THRESHOLD = int(os.getenv("CRITICAL_INCIDENT_THRESHOLD", "3"))

    # Processing
    CAMERA_POLL_INTERVAL_SECONDS = int(os.getenv("CAMERA_POLL_INTERVAL_SECONDS", "30"))
    FRAME_ANALYSIS_INTERVAL = int(os.getenv("FRAME_ANALYSIS_INTERVAL", "5"))
    MAX_CONCURRENT_STREAMS = int(os.getenv("MAX_CONCURRENT_STREAMS", "50"))
