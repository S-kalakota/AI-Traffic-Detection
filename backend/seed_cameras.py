"""Seed the database with California highway cameras from Caltrans API.

Usage:
    python -m backend.seed_cameras
"""

import logging
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# Fallback camera data for when Caltrans API is unavailable
FALLBACK_CAMERAS = [
    # Los Angeles Area (District 7)
    {"caltrans_id": "D7_001", "name": "I-405 S at Wilshire Blvd", "district": "D7", "route": "I-405", "direction": "S", "latitude": 34.0622, "longitude": -118.4480, "image_url": ""},
    {"caltrans_id": "D7_002", "name": "I-405 N at Sunset Blvd", "district": "D7", "route": "I-405", "direction": "N", "latitude": 34.0760, "longitude": -118.4510, "image_url": ""},
    {"caltrans_id": "D7_003", "name": "I-10 W at La Brea Ave", "district": "D7", "route": "I-10", "direction": "W", "latitude": 34.0380, "longitude": -118.3440, "image_url": ""},
    {"caltrans_id": "D7_004", "name": "I-10 E at Robertson Blvd", "district": "D7", "route": "I-10", "direction": "E", "latitude": 34.0340, "longitude": -118.3830, "image_url": ""},
    {"caltrans_id": "D7_005", "name": "US-101 N at Hollywood Blvd", "district": "D7", "route": "US-101", "direction": "N", "latitude": 34.1015, "longitude": -118.3340, "image_url": ""},
    {"caltrans_id": "D7_006", "name": "US-101 S at Cahuenga Blvd", "district": "D7", "route": "US-101", "direction": "S", "latitude": 34.1120, "longitude": -118.3380, "image_url": ""},
    {"caltrans_id": "D7_007", "name": "I-110 N at Adams Blvd", "district": "D7", "route": "I-110", "direction": "N", "latitude": 34.0180, "longitude": -118.2790, "image_url": ""},
    {"caltrans_id": "D7_008", "name": "I-110 S at Manchester Ave", "district": "D7", "route": "I-110", "direction": "S", "latitude": 33.9580, "longitude": -118.2810, "image_url": ""},
    {"caltrans_id": "D7_009", "name": "I-5 S at Stadium Way", "district": "D7", "route": "I-5", "direction": "S", "latitude": 34.0730, "longitude": -118.2410, "image_url": ""},
    {"caltrans_id": "D7_010", "name": "I-5 N at Los Feliz Blvd", "district": "D7", "route": "I-5", "direction": "N", "latitude": 34.1070, "longitude": -118.2680, "image_url": ""},
    {"caltrans_id": "D7_011", "name": "I-105 E at Sepulveda Blvd", "district": "D7", "route": "I-105", "direction": "E", "latitude": 33.9310, "longitude": -118.3980, "image_url": ""},
    {"caltrans_id": "D7_012", "name": "SR-2 N at Colorado Blvd", "district": "D7", "route": "SR-2", "direction": "N", "latitude": 34.1470, "longitude": -118.1490, "image_url": ""},
    {"caltrans_id": "D7_013", "name": "I-710 S at Firestone Blvd", "district": "D7", "route": "I-710", "direction": "S", "latitude": 33.9460, "longitude": -118.1890, "image_url": ""},
    {"caltrans_id": "D7_014", "name": "I-605 N at Whittier Blvd", "district": "D7", "route": "I-605", "direction": "N", "latitude": 34.0210, "longitude": -118.0920, "image_url": ""},
    {"caltrans_id": "D7_015", "name": "SR-134 E at Forest Lawn Dr", "district": "D7", "route": "SR-134", "direction": "E", "latitude": 34.1510, "longitude": -118.2610, "image_url": ""},
    {"caltrans_id": "D7_016", "name": "I-405 N at Getty Center Dr", "district": "D7", "route": "I-405", "direction": "N", "latitude": 34.0830, "longitude": -118.4720, "image_url": ""},
    {"caltrans_id": "D7_017", "name": "I-10 W at Crenshaw Blvd", "district": "D7", "route": "I-10", "direction": "W", "latitude": 34.0310, "longitude": -118.3280, "image_url": ""},
    {"caltrans_id": "D7_018", "name": "I-405 S at LAX", "district": "D7", "route": "I-405", "direction": "S", "latitude": 33.9470, "longitude": -118.3920, "image_url": ""},
    {"caltrans_id": "D7_019", "name": "US-101 N at Barham Blvd", "district": "D7", "route": "US-101", "direction": "N", "latitude": 34.1300, "longitude": -118.3440, "image_url": ""},
    {"caltrans_id": "D7_020", "name": "I-5 S at Burbank Blvd", "district": "D7", "route": "I-5", "direction": "S", "latitude": 34.1820, "longitude": -118.3080, "image_url": ""},

    # San Francisco Bay Area (District 4)
    {"caltrans_id": "D4_001", "name": "I-80 W at Bay Bridge Toll", "district": "D4", "route": "I-80", "direction": "W", "latitude": 37.8170, "longitude": -122.3530, "image_url": ""},
    {"caltrans_id": "D4_002", "name": "US-101 N at Cesar Chavez St", "district": "D4", "route": "US-101", "direction": "N", "latitude": 37.7500, "longitude": -122.4030, "image_url": ""},
    {"caltrans_id": "D4_003", "name": "I-280 N at San Jose Ave", "district": "D4", "route": "I-280", "direction": "N", "latitude": 37.7250, "longitude": -122.4480, "image_url": ""},
    {"caltrans_id": "D4_004", "name": "I-580 E at Grand Ave", "district": "D4", "route": "I-580", "direction": "E", "latitude": 37.8110, "longitude": -122.2510, "image_url": ""},
    {"caltrans_id": "D4_005", "name": "I-880 S at Hegenberger Rd", "district": "D4", "route": "I-880", "direction": "S", "latitude": 37.7370, "longitude": -122.2000, "image_url": ""},
    {"caltrans_id": "D4_006", "name": "US-101 S at Candlestick", "district": "D4", "route": "US-101", "direction": "S", "latitude": 37.7100, "longitude": -122.3880, "image_url": ""},
    {"caltrans_id": "D4_007", "name": "I-680 N at Sunol Grade", "district": "D4", "route": "I-680", "direction": "N", "latitude": 37.5860, "longitude": -121.8820, "image_url": ""},
    {"caltrans_id": "D4_008", "name": "SR-237 E at Mathilda Ave", "district": "D4", "route": "SR-237", "direction": "E", "latitude": 37.4120, "longitude": -122.0260, "image_url": ""},
    {"caltrans_id": "D4_009", "name": "US-101 S at Palo Alto", "district": "D4", "route": "US-101", "direction": "S", "latitude": 37.4430, "longitude": -122.1640, "image_url": ""},
    {"caltrans_id": "D4_010", "name": "I-80 E at Emeryville", "district": "D4", "route": "I-80", "direction": "E", "latitude": 37.8340, "longitude": -122.2930, "image_url": ""},
    {"caltrans_id": "D4_011", "name": "I-880 N at Fremont", "district": "D4", "route": "I-880", "direction": "N", "latitude": 37.5560, "longitude": -122.0500, "image_url": ""},
    {"caltrans_id": "D4_012", "name": "I-580 W at Livermore", "district": "D4", "route": "I-580", "direction": "W", "latitude": 37.6820, "longitude": -121.7680, "image_url": ""},
    {"caltrans_id": "D4_013", "name": "SR-92 E at Half Moon Bay", "district": "D4", "route": "SR-92", "direction": "E", "latitude": 37.5040, "longitude": -122.3310, "image_url": ""},
    {"caltrans_id": "D4_014", "name": "US-101 N at Golden Gate", "district": "D4", "route": "US-101", "direction": "N", "latitude": 37.8080, "longitude": -122.4740, "image_url": ""},
    {"caltrans_id": "D4_015", "name": "I-280 S at Daly City", "district": "D4", "route": "I-280", "direction": "S", "latitude": 37.6880, "longitude": -122.4710, "image_url": ""},

    # Sacramento Area (District 3)
    {"caltrans_id": "D3_001", "name": "I-80 E at Capital City Fwy", "district": "D3", "route": "I-80", "direction": "E", "latitude": 38.6060, "longitude": -121.4930, "image_url": ""},
    {"caltrans_id": "D3_002", "name": "I-5 N at Sacramento", "district": "D3", "route": "I-5", "direction": "N", "latitude": 38.5800, "longitude": -121.5040, "image_url": ""},
    {"caltrans_id": "D3_003", "name": "US-50 E at Watt Ave", "district": "D3", "route": "US-50", "direction": "E", "latitude": 38.5740, "longitude": -121.4010, "image_url": ""},
    {"caltrans_id": "D3_004", "name": "SR-99 S at Elk Grove", "district": "D3", "route": "SR-99", "direction": "S", "latitude": 38.4180, "longitude": -121.3800, "image_url": ""},
    {"caltrans_id": "D3_005", "name": "I-80 W at Davis", "district": "D3", "route": "I-80", "direction": "W", "latitude": 38.5440, "longitude": -121.7400, "image_url": ""},
    {"caltrans_id": "D3_006", "name": "I-5 S at Woodland", "district": "D3", "route": "I-5", "direction": "S", "latitude": 38.6710, "longitude": -121.7420, "image_url": ""},
    {"caltrans_id": "D3_007", "name": "SR-99 N at Yuba City", "district": "D3", "route": "SR-99", "direction": "N", "latitude": 39.1250, "longitude": -121.6250, "image_url": ""},
    {"caltrans_id": "D3_008", "name": "I-80 E at Auburn", "district": "D3", "route": "I-80", "direction": "E", "latitude": 38.8990, "longitude": -121.0770, "image_url": ""},

    # San Diego (District 11)
    {"caltrans_id": "D11_001", "name": "I-5 S at La Jolla Village Dr", "district": "D11", "route": "I-5", "direction": "S", "latitude": 32.8710, "longitude": -117.2100, "image_url": ""},
    {"caltrans_id": "D11_002", "name": "I-15 N at Miramar Rd", "district": "D11", "route": "I-15", "direction": "N", "latitude": 32.8880, "longitude": -117.1460, "image_url": ""},
    {"caltrans_id": "D11_003", "name": "I-8 E at Mission Valley", "district": "D11", "route": "I-8", "direction": "E", "latitude": 32.7700, "longitude": -117.1500, "image_url": ""},
    {"caltrans_id": "D11_004", "name": "I-805 S at Balboa Ave", "district": "D11", "route": "I-805", "direction": "S", "latitude": 32.8210, "longitude": -117.1380, "image_url": ""},
    {"caltrans_id": "D11_005", "name": "SR-163 N at Friars Rd", "district": "D11", "route": "SR-163", "direction": "N", "latitude": 32.7690, "longitude": -117.1610, "image_url": ""},
    {"caltrans_id": "D11_006", "name": "I-5 N at Downtown San Diego", "district": "D11", "route": "I-5", "direction": "N", "latitude": 32.7190, "longitude": -117.1670, "image_url": ""},
    {"caltrans_id": "D11_007", "name": "I-5 S at Carlsbad", "district": "D11", "route": "I-5", "direction": "S", "latitude": 33.1360, "longitude": -117.3210, "image_url": ""},
    {"caltrans_id": "D11_008", "name": "I-15 S at Escondido", "district": "D11", "route": "I-15", "direction": "S", "latitude": 33.1230, "longitude": -117.0860, "image_url": ""},

    # Central Valley / Bakersfield (District 6)
    {"caltrans_id": "D6_001", "name": "SR-99 S at Fresno", "district": "D6", "route": "SR-99", "direction": "S", "latitude": 36.7470, "longitude": -119.7720, "image_url": ""},
    {"caltrans_id": "D6_002", "name": "SR-99 N at Bakersfield", "district": "D6", "route": "SR-99", "direction": "N", "latitude": 35.3730, "longitude": -119.0190, "image_url": ""},
    {"caltrans_id": "D6_003", "name": "SR-99 S at Modesto", "district": "D6", "route": "SR-99", "direction": "S", "latitude": 37.6390, "longitude": -120.9970, "image_url": ""},
    {"caltrans_id": "D6_004", "name": "SR-99 N at Stockton", "district": "D6", "route": "SR-99", "direction": "N", "latitude": 37.9580, "longitude": -121.2910, "image_url": ""},
    {"caltrans_id": "D6_005", "name": "I-5 S at Coalinga", "district": "D6", "route": "I-5", "direction": "S", "latitude": 36.1340, "longitude": -120.3610, "image_url": ""},
    {"caltrans_id": "D6_006", "name": "SR-41 N at Lemoore", "district": "D6", "route": "SR-41", "direction": "N", "latitude": 36.3000, "longitude": -119.7800, "image_url": ""},
    {"caltrans_id": "D6_007", "name": "I-5 N at Los Banos", "district": "D6", "route": "I-5", "direction": "N", "latitude": 37.0620, "longitude": -120.8500, "image_url": ""},

    # Inland Empire (District 8)
    {"caltrans_id": "D8_001", "name": "I-10 E at Ontario", "district": "D8", "route": "I-10", "direction": "E", "latitude": 34.0640, "longitude": -117.6500, "image_url": ""},
    {"caltrans_id": "D8_002", "name": "I-15 N at Rancho Cucamonga", "district": "D8", "route": "I-15", "direction": "N", "latitude": 34.1260, "longitude": -117.5730, "image_url": ""},
    {"caltrans_id": "D8_003", "name": "I-215 S at Riverside", "district": "D8", "route": "I-215", "direction": "S", "latitude": 33.9800, "longitude": -117.3750, "image_url": ""},
    {"caltrans_id": "D8_004", "name": "I-10 W at Redlands", "district": "D8", "route": "I-10", "direction": "W", "latitude": 34.0560, "longitude": -117.1830, "image_url": ""},
    {"caltrans_id": "D8_005", "name": "SR-91 E at Corona", "district": "D8", "route": "SR-91", "direction": "E", "latitude": 33.8810, "longitude": -117.5700, "image_url": ""},
    {"caltrans_id": "D8_006", "name": "I-15 S at Temecula", "district": "D8", "route": "I-15", "direction": "S", "latitude": 33.4940, "longitude": -117.1480, "image_url": ""},

    # Orange County (District 12)
    {"caltrans_id": "D12_001", "name": "I-5 S at Irvine", "district": "D12", "route": "I-5", "direction": "S", "latitude": 33.6850, "longitude": -117.8260, "image_url": ""},
    {"caltrans_id": "D12_002", "name": "I-405 N at Costa Mesa", "district": "D12", "route": "I-405", "direction": "N", "latitude": 33.6750, "longitude": -117.8870, "image_url": ""},
    {"caltrans_id": "D12_003", "name": "SR-55 S at Newport Beach", "district": "D12", "route": "SR-55", "direction": "S", "latitude": 33.6320, "longitude": -117.8680, "image_url": ""},
    {"caltrans_id": "D12_004", "name": "SR-91 W at Anaheim", "district": "D12", "route": "SR-91", "direction": "W", "latitude": 33.8250, "longitude": -117.9140, "image_url": ""},
    {"caltrans_id": "D12_005", "name": "I-5 N at Santa Ana", "district": "D12", "route": "I-5", "direction": "N", "latitude": 33.7460, "longitude": -117.8680, "image_url": ""},

    # Northern CA (Districts 1, 2)
    {"caltrans_id": "D2_001", "name": "I-5 N at Redding", "district": "D2", "route": "I-5", "direction": "N", "latitude": 40.5860, "longitude": -122.3920, "image_url": ""},
    {"caltrans_id": "D2_002", "name": "SR-299 E at Shasta", "district": "D2", "route": "SR-299", "direction": "E", "latitude": 40.6060, "longitude": -122.3380, "image_url": ""},
    {"caltrans_id": "D1_001", "name": "US-101 N at Eureka", "district": "D1", "route": "US-101", "direction": "N", "latitude": 40.8020, "longitude": -124.1640, "image_url": ""},
    {"caltrans_id": "D1_002", "name": "US-101 S at Ukiah", "district": "D1", "route": "US-101", "direction": "S", "latitude": 39.1500, "longitude": -123.2080, "image_url": ""},

    # Central Coast (District 5)
    {"caltrans_id": "D5_001", "name": "US-101 N at Santa Barbara", "district": "D5", "route": "US-101", "direction": "N", "latitude": 34.4210, "longitude": -119.6980, "image_url": ""},
    {"caltrans_id": "D5_002", "name": "US-101 S at San Luis Obispo", "district": "D5", "route": "US-101", "direction": "S", "latitude": 35.2830, "longitude": -120.6600, "image_url": ""},
    {"caltrans_id": "D5_003", "name": "SR-1 S at Monterey", "district": "D5", "route": "SR-1", "direction": "S", "latitude": 36.6000, "longitude": -121.8940, "image_url": ""},
    {"caltrans_id": "D5_004", "name": "US-101 N at Salinas", "district": "D5", "route": "US-101", "direction": "N", "latitude": 36.6780, "longitude": -121.6550, "image_url": ""},
    {"caltrans_id": "D5_005", "name": "US-101 S at Ventura", "district": "D5", "route": "US-101", "direction": "S", "latitude": 34.2790, "longitude": -119.2930, "image_url": ""},

    # Eastern Sierra / Desert (District 9)
    {"caltrans_id": "D9_001", "name": "I-15 N at Barstow", "district": "D9", "route": "I-15", "direction": "N", "latitude": 34.8960, "longitude": -117.0170, "image_url": ""},
    {"caltrans_id": "D9_002", "name": "US-395 N at Bishop", "district": "D9", "route": "US-395", "direction": "N", "latitude": 37.3640, "longitude": -118.3950, "image_url": ""},
]


def seed_cameras():
    """Seed the database with camera data."""
    from backend.app import create_app
    from backend.database import db
    from backend.models import Camera
    from backend.services.camera_ingester import fetch_caltrans_camera_list, sync_cameras_to_db

    app = create_app()

    with app.app_context():
        existing_count = Camera.query.count()
        logger.info(f"Current camera count: {existing_count}")

        # Try fetching from Caltrans API
        total_added = 0
        total_updated = 0

        from backend.config import Config

        for district, url in Config.CALTRANS_DISTRICTS.items():
            logger.info(f"Fetching cameras from {district}...")
            try:
                camera_list = fetch_caltrans_camera_list(url)
                if camera_list:
                    added, updated = sync_cameras_to_db(camera_list, district)
                    total_added += added
                    total_updated += updated
                    logger.info(f"  {district}: {len(camera_list)} found, {added} added, {updated} updated")
                else:
                    logger.warning(f"  {district}: No cameras returned from API")
            except Exception as e:
                logger.error(f"  {district}: Failed — {e}")

        # If we didn't get many cameras from API, use fallback data
        if Camera.query.count() < 50:
            logger.info("Using fallback camera data...")
            for cam_data in FALLBACK_CAMERAS:
                existing = Camera.query.filter_by(caltrans_id=cam_data["caltrans_id"]).first()
                if not existing:
                    camera = Camera(**cam_data, is_active=True)
                    db.session.add(camera)
                    total_added += 1

            db.session.commit()
            logger.info(f"Fallback cameras seeded: {total_added} added")

        final_count = Camera.query.count()
        logger.info(f"Done! Total cameras in database: {final_count}")


if __name__ == "__main__":
    seed_cameras()
