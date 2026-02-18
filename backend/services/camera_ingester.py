"""Camera ingestion service — pulls frames from Caltrans CCTV feeds."""

import logging
import requests
import time
from io import BytesIO
from datetime import datetime, timezone

import cv2
import numpy as np
from PIL import Image

from backend.database import db
from backend.models import Camera

logger = logging.getLogger(__name__)


def fetch_camera_image(camera: Camera) -> np.ndarray | None:
    """Download the latest snapshot from a Caltrans camera and return as OpenCV frame."""
    if not camera.image_url:
        return None

    try:
        response = requests.get(camera.image_url, timeout=15)
        response.raise_for_status()

        img = Image.open(BytesIO(response.content)).convert("RGB")
        frame = np.array(img)
        # Convert RGB to BGR for OpenCV
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

        # Update last polled timestamp
        camera.last_polled = datetime.now(timezone.utc)
        db.session.commit()

        return frame
    except requests.RequestException as e:
        logger.warning(f"Failed to fetch image from camera {camera.caltrans_id}: {e}")
        return None
    except Exception as e:
        logger.error(f"Error processing image from camera {camera.caltrans_id}: {e}")
        return None


def fetch_caltrans_camera_list(url: str) -> list[dict]:
    """Fetch the camera metadata list from a Caltrans district endpoint.

    Caltrans API returns JSON in this structure:
    { "data": [ { "cctv": { "index": "1", "location": { "latitude": ..., "longitude": ..., ... }, "imageData": { ... } } }, ... ] }
    """
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()

        cameras = []

        # Extract the list of camera entries
        raw_list = data if isinstance(data, list) else data.get("data", [])
        if not isinstance(raw_list, list):
            logger.warning(f"Unexpected data structure from {url}")
            return []

        for entry in raw_list:
            try:
                # Each entry wraps the camera data under a "cctv" key
                cam = entry.get("cctv", entry) if isinstance(entry, dict) else entry
                if not isinstance(cam, dict):
                    continue

                # Location info is nested under "location"
                location = cam.get("location", {})
                if not isinstance(location, dict):
                    location = {}

                lat = float(location.get("latitude", 0))
                lng = float(location.get("longitude", 0))

                if lat == 0 or lng == 0:
                    continue

                # Image and stream URLs are nested under "imageData"
                image_data = cam.get("imageData", {})
                if not isinstance(image_data, dict):
                    image_data = {}

                static_data = image_data.get("static", {})
                if not isinstance(static_data, dict):
                    static_data = {}

                image_url = static_data.get("currentImageURL", "")
                stream_url = image_data.get("streamingVideoURL", "")

                cameras.append({
                    "caltrans_id": str(cam.get("index", "")),
                    "name": location.get("locationName", "Unknown"),
                    "district": str(location.get("district", "")),
                    "route": location.get("route", ""),
                    "direction": location.get("direction", ""),
                    "latitude": lat,
                    "longitude": lng,
                    "image_url": image_url,
                    "stream_url": stream_url,
                })
            except (ValueError, TypeError, KeyError) as e:
                logger.debug(f"Skipping camera entry: {e}")
                continue

        return cameras
    except requests.RequestException as e:
        logger.error(f"Failed to fetch camera list from {url}: {e}")
        return []
    except Exception as e:
        logger.error(f"Error parsing camera list from {url}: {e}")
        return []


def sync_cameras_to_db(camera_list: list[dict], district: str = ""):
    """Upsert camera records from Caltrans data."""
    added = 0
    updated = 0

    for cam_data in camera_list:
        if not cam_data.get("latitude") or not cam_data.get("longitude"):
            continue
        if cam_data["latitude"] == 0 or cam_data["longitude"] == 0:
            continue

        caltrans_id = f"{district}_{cam_data['caltrans_id']}" if district else cam_data["caltrans_id"]

        existing = Camera.query.filter_by(caltrans_id=caltrans_id).first()
        if existing:
            existing.name = cam_data["name"] or existing.name
            existing.image_url = cam_data["image_url"] or existing.image_url
            existing.stream_url = cam_data["stream_url"] or existing.stream_url
            existing.is_active = True
            updated += 1
        else:
            camera = Camera(
                caltrans_id=caltrans_id,
                name=cam_data["name"] or f"Camera {caltrans_id}",
                district=cam_data.get("district", district),
                route=cam_data.get("route", ""),
                direction=cam_data.get("direction", ""),
                latitude=cam_data["latitude"],
                longitude=cam_data["longitude"],
                image_url=cam_data.get("image_url", ""),
                stream_url=cam_data.get("stream_url", ""),
                is_active=True,
            )
            db.session.add(camera)
            added += 1

    db.session.commit()
    logger.info(f"Camera sync [{district}]: {added} added, {updated} updated")
    return added, updated


def poll_all_cameras(app, max_cameras: int = 50) -> list[tuple]:
    """
    Poll a batch of cameras for new frames.
    Returns list of (camera, frame) tuples.
    """
    with app.app_context():
        cameras = (
            Camera.query.filter_by(is_active=True)
            .order_by(Camera.last_polled.asc().nullsfirst())
            .limit(max_cameras)
            .all()
        )

        results = []
        for camera in cameras:
            frame = fetch_camera_image(camera)
            if frame is not None:
                results.append((camera, frame))
            # Small delay to be respectful of Caltrans servers
            time.sleep(0.2)

        return results
