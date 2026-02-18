"""Driving behavior detection engine using computer vision.

This module analyzes video frames from highway cameras to detect
impaired and dangerous driving patterns including:
- Swerving / erratic lane changes
- Abnormal speed variance
- Wrong-way driving
- Stopped vehicles in active lanes
- Aggressive driving patterns (rapid acceleration / hard braking)

Two analysis modes:
A) Multi-frame pipeline (DetectionPipeline)  — feeds consecutive frames
   into bg-subtraction → vehicle tracking → trajectory anomaly scoring.
   Best for video streams or rapid snapshot polling (< 5 s interval).

B) Snapshot pair analyzer (SnapshotAnalyzer) — compares two consecutive
   JPEG snapshots (~30 s apart) from Caltrans cameras.  Uses dense
   optical-flow, contour-delta, and statistical scoring to detect
   anomalous motion patterns in a single diff.  This is what the live
   scheduler uses since Caltrans cameras only update every ~5-30 s.

The detection pipeline:
1. Vehicle detection via background subtraction + contour analysis
2. Multi-frame tracking to build trajectories (mode A)
   -or- optical-flow + contour-delta analysis (mode B)
3. Trajectory / flow analysis for anomalous patterns
4. Confidence scoring and severity classification
"""

import logging
import math
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)


# ---------- Data Structures ----------

@dataclass
class TrackedVehicle:
    """A vehicle being tracked across frames."""
    track_id: int
    positions: list = field(default_factory=list)  # [(x, y, w, h, timestamp), ...]
    velocities: list = field(default_factory=list)  # [(vx, vy), ...]
    lateral_offsets: list = field(default_factory=list)  # lateral position deltas
    last_seen: float = 0.0
    lane_changes: int = 0
    is_anomalous: bool = False


@dataclass
class DetectionResult:
    """Result from analyzing a single camera frame or frame sequence."""
    incident_type: Optional[str] = None
    severity: Optional[str] = None
    confidence: float = 0.0
    description: str = ""
    details: dict = field(default_factory=dict)
    has_detection: bool = False


# ---------- Vehicle Detector ----------

class VehicleDetector:
    """Detects vehicles in a frame using background subtraction + contour analysis.

    For production, swap this with YOLO or a dedicated vehicle detection model.
    This implementation uses classical CV techniques that work without a GPU
    and without downloading model weights.
    """

    def __init__(self):
        self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(
            history=500, varThreshold=50, detectShadows=True
        )
        self.min_vehicle_area = 800  # Minimum contour area to be considered a vehicle
        self.frame_count = 0

    def detect(self, frame: np.ndarray) -> list[tuple]:
        """
        Detect vehicles in a frame.
        Returns list of (x, y, w, h) bounding boxes.
        """
        self.frame_count += 1

        # Apply background subtraction
        fg_mask = self.bg_subtractor.apply(frame)

        # Remove shadows (shadow pixels are marked as 127 by MOG2)
        _, fg_mask = cv2.threshold(fg_mask, 200, 255, cv2.THRESH_BINARY)

        # Morphological operations to clean up
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel, iterations=1)

        # Find contours
        contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        detections = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < self.min_vehicle_area:
                continue

            x, y, w, h = cv2.boundingRect(contour)
            aspect_ratio = w / h if h > 0 else 0

            # Filter for vehicle-like aspect ratios (roughly 1:1 to 3:1)
            if 0.3 < aspect_ratio < 4.0:
                detections.append((x, y, w, h))

        return detections


# ---------- Simple Tracker ----------

class SimpleTracker:
    """Simple centroid-based multi-object tracker."""

    def __init__(self, max_disappeared: int = 15):
        self.next_id = 0
        self.vehicles: dict[int, TrackedVehicle] = {}
        self.max_disappeared = max_disappeared
        self.disappeared: dict[int, int] = {}

    def update(self, detections: list[tuple], timestamp: float) -> dict[int, TrackedVehicle]:
        """Update tracker with new detections."""
        if not detections:
            # Mark all as disappeared
            for track_id in list(self.disappeared.keys()):
                self.disappeared[track_id] += 1
                if self.disappeared[track_id] > self.max_disappeared:
                    del self.vehicles[track_id]
                    del self.disappeared[track_id]
            return self.vehicles

        # Calculate centroids of new detections
        new_centroids = []
        for (x, y, w, h) in detections:
            cx = x + w // 2
            cy = y + h // 2
            new_centroids.append((cx, cy, x, y, w, h))

        if not self.vehicles:
            # Initialize new tracks
            for (cx, cy, x, y, w, h) in new_centroids:
                vehicle = TrackedVehicle(track_id=self.next_id)
                vehicle.positions.append((x, y, w, h, timestamp))
                vehicle.last_seen = timestamp
                self.vehicles[self.next_id] = vehicle
                self.disappeared[self.next_id] = 0
                self.next_id += 1
        else:
            # Match existing tracks to new detections using distance
            track_ids = list(self.vehicles.keys())
            existing_centroids = []
            for tid in track_ids:
                if self.vehicles[tid].positions:
                    lx, ly, lw, lh, _ = self.vehicles[tid].positions[-1]
                    existing_centroids.append((lx + lw // 2, ly + lh // 2))
                else:
                    existing_centroids.append((0, 0))

            # Compute distance matrix
            used_detections = set()
            used_tracks = set()

            pairs = []
            for i, (ecx, ecy) in enumerate(existing_centroids):
                for j, (ncx, ncy, _, _, _, _) in enumerate(new_centroids):
                    dist = math.sqrt((ecx - ncx) ** 2 + (ecy - ncy) ** 2)
                    pairs.append((dist, i, j))

            pairs.sort(key=lambda p: p[0])

            for dist, i, j in pairs:
                if i in used_tracks or j in used_detections:
                    continue
                if dist > 150:  # Max match distance
                    continue

                tid = track_ids[i]
                ncx, ncy, x, y, w, h = new_centroids[j]
                vehicle = self.vehicles[tid]
                vehicle.positions.append((x, y, w, h, timestamp))
                vehicle.last_seen = timestamp
                self.disappeared[tid] = 0

                # Calculate velocity if we have enough positions
                if len(vehicle.positions) >= 2:
                    prev = vehicle.positions[-2]
                    px, py = prev[0] + prev[2] // 2, prev[1] + prev[3] // 2
                    dt = timestamp - prev[4]
                    if dt > 0:
                        vx = (ncx - px) / dt
                        vy = (ncy - py) / dt
                        vehicle.velocities.append((vx, vy))
                        vehicle.lateral_offsets.append(abs(ncx - px))

                used_tracks.add(i)
                used_detections.add(j)

            # Handle disappeared tracks
            for i in range(len(track_ids)):
                if i not in used_tracks:
                    tid = track_ids[i]
                    self.disappeared[tid] = self.disappeared.get(tid, 0) + 1
                    if self.disappeared[tid] > self.max_disappeared:
                        del self.vehicles[tid]
                        del self.disappeared[tid]

            # Register new detections as new tracks
            for j in range(len(new_centroids)):
                if j not in used_detections:
                    ncx, ncy, x, y, w, h = new_centroids[j]
                    vehicle = TrackedVehicle(track_id=self.next_id)
                    vehicle.positions.append((x, y, w, h, timestamp))
                    vehicle.last_seen = timestamp
                    self.vehicles[self.next_id] = vehicle
                    self.disappeared[self.next_id] = 0
                    self.next_id += 1

        return self.vehicles


# ---------- Behavior Analyzer ----------

class BehaviorAnalyzer:
    """Analyzes vehicle trajectories for anomalous driving patterns."""

    def __init__(self, config=None):
        if config is None:
            from backend.config import Config
            config = Config

        self.swerve_threshold = config.SWERVE_THRESHOLD
        self.speed_variance_threshold = config.SPEED_VARIANCE_THRESHOLD
        self.wrong_way_confidence = config.WRONG_WAY_CONFIDENCE
        self.min_confidence = config.MIN_DETECTION_CONFIDENCE

    def analyze(self, vehicle: TrackedVehicle) -> Optional[DetectionResult]:
        """Analyze a single vehicle's trajectory for anomalous behavior."""
        if len(vehicle.positions) < 5:
            return None  # Need enough data

        results = []

        # Check for swerving
        swerve_result = self._check_swerving(vehicle)
        if swerve_result:
            results.append(swerve_result)

        # Check for speed variance
        speed_result = self._check_speed_variance(vehicle)
        if speed_result:
            results.append(speed_result)

        # Check for stopped vehicle
        stopped_result = self._check_stopped_vehicle(vehicle)
        if stopped_result:
            results.append(stopped_result)

        # Check for wrong-way driving
        wrong_way_result = self._check_wrong_way(vehicle)
        if wrong_way_result:
            results.append(wrong_way_result)

        # Check for aggressive driving
        aggressive_result = self._check_aggressive(vehicle)
        if aggressive_result:
            results.append(aggressive_result)

        # Return the highest-severity detection
        if results:
            results.sort(key=lambda r: {"critical": 4, "warning": 3, "moderate": 2, "low": 1}.get(r.severity, 0), reverse=True)
            return results[0]

        return None

    def _check_swerving(self, vehicle: TrackedVehicle) -> Optional[DetectionResult]:
        """Detect swerving / erratic lateral movement."""
        if len(vehicle.lateral_offsets) < 5:
            return None

        offsets = vehicle.lateral_offsets[-10:]
        avg_offset = np.mean(offsets)
        std_offset = np.std(offsets)

        # Count direction changes (sign changes in consecutive lateral movements)
        direction_changes = 0
        for i in range(1, len(offsets)):
            if offsets[i] > avg_offset and (i < 2 or offsets[i - 1] < avg_offset):
                direction_changes += 1

        swerve_score = (std_offset / max(avg_offset, 1)) * (1 + direction_changes * 0.3)

        if swerve_score > self.swerve_threshold:
            confidence = min(0.5 + swerve_score * 0.3 + direction_changes * 0.05, 0.99)

            if confidence < self.min_confidence:
                return None

            severity = "critical" if swerve_score > self.swerve_threshold * 2 else "warning"

            return DetectionResult(
                incident_type="swerving",
                severity=severity,
                confidence=round(confidence, 3),
                description=f"Erratic lane changes detected — {direction_changes} lateral shifts in recent frames. Possible impaired driver.",
                details={
                    "swerve_score": round(swerve_score, 3),
                    "direction_changes": direction_changes,
                    "avg_lateral_offset": round(avg_offset, 2),
                    "std_lateral_offset": round(std_offset, 2),
                },
                has_detection=True,
            )

        return None

    def _check_speed_variance(self, vehicle: TrackedVehicle) -> Optional[DetectionResult]:
        """Detect abnormal speed changes."""
        if len(vehicle.velocities) < 5:
            return None

        speeds = [math.sqrt(vx ** 2 + vy ** 2) for vx, vy in vehicle.velocities[-15:]]
        avg_speed = np.mean(speeds)
        std_speed = np.std(speeds)

        if avg_speed == 0:
            return None

        variance_ratio = (std_speed / avg_speed) * 100

        if variance_ratio > self.speed_variance_threshold:
            confidence = min(0.5 + variance_ratio * 0.01, 0.98)

            if confidence < self.min_confidence:
                return None

            severity = "critical" if variance_ratio > self.speed_variance_threshold * 2 else "warning"

            return DetectionResult(
                incident_type="speed_variance",
                severity=severity,
                confidence=round(confidence, 3),
                description=f"Speed variance of {variance_ratio:.0f}% detected — erratic acceleration/deceleration pattern.",
                details={
                    "variance_ratio": round(variance_ratio, 2),
                    "avg_speed_px": round(avg_speed, 2),
                    "std_speed_px": round(std_speed, 2),
                    "speed_count": len(speeds),
                },
                has_detection=True,
            )

        return None

    def _check_stopped_vehicle(self, vehicle: TrackedVehicle) -> Optional[DetectionResult]:
        """Detect a vehicle stopped in an active lane."""
        if len(vehicle.positions) < 8:
            return None

        recent = vehicle.positions[-8:]
        centroids = [(x + w // 2, y + h // 2) for x, y, w, h, _ in recent]

        total_movement = sum(
            math.sqrt((centroids[i][0] - centroids[i - 1][0]) ** 2 + (centroids[i][1] - centroids[i - 1][1]) ** 2)
            for i in range(1, len(centroids))
        )

        # If very little movement over many frames
        if total_movement < 10:
            time_span = recent[-1][4] - recent[0][4]
            if time_span < 2:
                return None  # Not enough time elapsed

            confidence = min(0.6 + (1 - total_movement / 10) * 0.3, 0.95)

            if confidence < self.min_confidence:
                return None

            return DetectionResult(
                incident_type="stopped_vehicle",
                severity="moderate",
                confidence=round(confidence, 3),
                description=f"Vehicle appears stationary in active lane for {time_span:.1f}s. Possible breakdown or obstruction.",
                details={
                    "total_movement_px": round(total_movement, 2),
                    "time_span_s": round(time_span, 2),
                    "frames_analyzed": len(recent),
                },
                has_detection=True,
            )

        return None

    def _check_wrong_way(self, vehicle: TrackedVehicle) -> Optional[DetectionResult]:
        """Detect wrong-way driving (requires knowledge of expected direction)."""
        if len(vehicle.velocities) < 5:
            return None

        recent_velocities = vehicle.velocities[-10:]
        avg_vy = np.mean([vy for _, vy in recent_velocities])

        # On most highway cameras, traffic flows in a consistent direction
        # If a vehicle moves against the dominant flow, flag it
        # This is a simplified check — in production, camera-specific expected
        # flow direction would be used
        all_vehicles_vy = avg_vy  # Placeholder — would aggregate across all tracks

        if avg_vy != 0 and abs(avg_vy) > 3:
            # Check if going opposite to expected direction
            # This is a heuristic that would need camera-specific calibration
            confidence = min(abs(avg_vy) * 0.05, 0.95)

            if confidence >= self.wrong_way_confidence:
                return DetectionResult(
                    incident_type="wrong_way",
                    severity="critical",
                    confidence=round(confidence, 3),
                    description="Possible wrong-way driver detected — vehicle moving against expected traffic flow.",
                    details={
                        "avg_vertical_velocity": round(avg_vy, 2),
                        "expected_direction": "downstream",
                    },
                    has_detection=True,
                )

        return None

    def _check_aggressive(self, vehicle: TrackedVehicle) -> Optional[DetectionResult]:
        """Detect aggressive driving patterns."""
        if len(vehicle.velocities) < 8:
            return None

        speeds = [math.sqrt(vx ** 2 + vy ** 2) for vx, vy in vehicle.velocities[-12:]]

        # Check for rapid acceleration / deceleration
        accelerations = [speeds[i] - speeds[i - 1] for i in range(1, len(speeds))]
        max_accel = max(accelerations) if accelerations else 0
        max_decel = min(accelerations) if accelerations else 0

        # Aggressive if large swings in speed
        aggression_score = max_accel - max_decel  # Range of acceleration

        if aggression_score > 15:
            confidence = min(0.5 + aggression_score * 0.02, 0.95)

            if confidence < self.min_confidence:
                return None

            severity = "warning" if aggression_score > 25 else "moderate"

            return DetectionResult(
                incident_type="aggressive",
                severity=severity,
                confidence=round(confidence, 3),
                description=f"Aggressive driving pattern — rapid acceleration/braking cycles detected.",
                details={
                    "aggression_score": round(aggression_score, 2),
                    "max_acceleration": round(max_accel, 2),
                    "max_deceleration": round(max_decel, 2),
                },
                has_detection=True,
            )

        return None


# ---------- Main Detection Pipeline ----------

class DetectionPipeline:
    """End-to-end detection pipeline for a camera feed."""

    def __init__(self, config=None):
        self.detector = VehicleDetector()
        self.tracker = SimpleTracker()
        self.analyzer = BehaviorAnalyzer(config)
        self.frame_count = 0

    def process_frame(self, frame: np.ndarray) -> list[DetectionResult]:
        """
        Process a single frame through the full pipeline.
        Returns a list of DetectionResults (may be empty).
        """
        self.frame_count += 1
        timestamp = time.time()

        # Step 1: Detect vehicles
        detections = self.detector.detect(frame)

        # Step 2: Update tracker
        vehicles = self.tracker.update(detections, timestamp)

        # Step 3: Analyze behavior (every N frames to reduce noise)
        results = []
        if self.frame_count % 3 == 0:
            for track_id, vehicle in vehicles.items():
                result = self.analyzer.analyze(vehicle)
                if result and result.has_detection:
                    results.append(result)

        return results

    def process_frame_sequence(self, frames: list[np.ndarray]) -> list[DetectionResult]:
        """
        Process a sequence of frames (e.g., extracted from a video clip).
        Returns aggregated detection results.
        """
        all_results = []
        for frame in frames:
            results = self.process_frame(frame)
            all_results.extend(results)

        # Deduplicate — keep highest confidence per incident type
        best_by_type: dict[str, DetectionResult] = {}
        for result in all_results:
            if result.incident_type not in best_by_type or result.confidence > best_by_type[result.incident_type].confidence:
                best_by_type[result.incident_type] = result

        return list(best_by_type.values())


# ---------- Snapshot Pair Analyzer (real Caltrans JPEG analysis) ----------

class SnapshotAnalyzer:
    """Analyzes pairs of consecutive camera snapshots using optical flow
    and contour differencing.  Works with the ~5-30 s refresh rate of
    Caltrans JPEG endpoints — no video stream required.

    Approach:
    1. Dense optical flow (Farneback) between frame_prev and frame_curr
       gives per-pixel motion vectors.
    2. We segment the flow field into moving regions (vehicle candidates)
       via magnitude thresholding + contour extraction.
    3. For each moving region we compute:
       - mean flow direction & magnitude (proxy for speed)
       - lateral vs longitudinal flow ratio (swerving indicator)
       - direction consistency (wrong-way indicator)
    4. We also look for large contour deltas between the two frames
       with near-zero flow — stopped vehicle candidates.
    5. Aggregate scores are mapped to incident types + severities.
    """

    # Tunable thresholds
    FLOW_MAG_THRESHOLD = 2.0        # min optical-flow magnitude (px) to count as motion
    SWERVE_LATERAL_RATIO = 0.55     # lateral/total flow ratio above which we flag swerve
    SPEED_STD_RATIO = 0.50          # std(mag)/mean(mag) above which speed-variance flagged
    STOPPED_MOTION_CEIL = 0.8       # max mean flow for a "stopped" contour
    MIN_CONTOUR_AREA = 600          # minimum contour area for a vehicle candidate
    MIN_MOVING_REGIONS = 1          # need at least this many moving blobs
    WRONG_WAY_ANGLE_DEV = 120       # degrees deviation from dominant direction → wrong-way

    def __init__(self):
        self._prev_gray: Optional[np.ndarray] = None
        self._prev_contours: list = []

    def feed(self, frame: np.ndarray) -> list[DetectionResult]:
        """Feed a new frame.  Returns detections (empty until 2nd frame)."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)

        if self._prev_gray is None:
            self._prev_gray = gray
            self._prev_contours = self._extract_contours(gray)
            return []

        results = self._analyze_pair(self._prev_gray, gray)

        # Shift
        self._prev_gray = gray
        self._prev_contours = self._extract_contours(gray)
        return results

    # ---- internal helpers ------------------------------------------------

    def _extract_contours(self, gray: np.ndarray) -> list:
        """Simple foreground contours via adaptive threshold."""
        thresh = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV, 25, 8,
        )
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel, iterations=2)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        return [c for c in contours if cv2.contourArea(c) >= self.MIN_CONTOUR_AREA]

    def _analyze_pair(self, prev_gray: np.ndarray, curr_gray: np.ndarray) -> list[DetectionResult]:
        """Core analysis: optical flow + contour diff."""
        h, w = prev_gray.shape[:2]

        # 1. Dense optical flow (Farneback)
        flow = cv2.calcOpticalFlowFarneback(
            prev_gray, curr_gray,
            None,  # output
            pyr_scale=0.5, levels=3, winsize=15,
            iterations=3, poly_n=5, poly_sigma=1.2, flags=0,
        )
        mag, ang = cv2.cartToPolar(flow[..., 0], flow[..., 1], angleInDegrees=True)

        # 2. Motion mask — regions with significant flow
        motion_mask = (mag > self.FLOW_MAG_THRESHOLD).astype(np.uint8) * 255
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
        motion_mask = cv2.morphologyEx(motion_mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        motion_mask = cv2.morphologyEx(motion_mask, cv2.MORPH_OPEN, kernel)

        contours, _ = cv2.findContours(motion_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        moving_regions = [c for c in contours if cv2.contourArea(c) >= self.MIN_CONTOUR_AREA]

        if len(moving_regions) < self.MIN_MOVING_REGIONS:
            # Check for stopped vehicles via frame differencing
            return self._check_stopped_only(prev_gray, curr_gray, mag)

        # 3. Per-region statistics
        region_stats = []
        for cnt in moving_regions:
            mask = np.zeros((h, w), dtype=np.uint8)
            cv2.drawContours(mask, [cnt], -1, 255, -1)

            region_mag = mag[mask > 0]
            region_ang = ang[mask > 0]
            fx = flow[..., 0][mask > 0]
            fy = flow[..., 1][mask > 0]

            if len(region_mag) < 20:
                continue

            mean_mag = float(np.mean(region_mag))
            std_mag = float(np.std(region_mag))
            mean_ang = float(np.mean(region_ang))
            mean_fx = float(np.mean(fx))
            mean_fy = float(np.mean(fy))
            lateral_ratio = abs(mean_fx) / (abs(mean_fx) + abs(mean_fy) + 1e-6)

            region_stats.append({
                "area": cv2.contourArea(cnt),
                "mean_mag": mean_mag,
                "std_mag": std_mag,
                "mean_ang": mean_ang,
                "mean_fx": mean_fx,
                "mean_fy": mean_fy,
                "lateral_ratio": lateral_ratio,
            })

        if not region_stats:
            return []

        # 4. Aggregate flow field direction (dominant traffic direction)
        global_fy = float(np.mean(flow[..., 1][mag > self.FLOW_MAG_THRESHOLD])) if np.any(mag > self.FLOW_MAG_THRESHOLD) else 0
        global_fx = float(np.mean(flow[..., 0][mag > self.FLOW_MAG_THRESHOLD])) if np.any(mag > self.FLOW_MAG_THRESHOLD) else 0
        dominant_angle = math.degrees(math.atan2(global_fy, global_fx)) % 360

        # 5. Score each anomaly type
        results: list[DetectionResult] = []

        for rs in region_stats:
            # --- Swerving ---
            if rs["lateral_ratio"] > self.SWERVE_LATERAL_RATIO and rs["mean_mag"] > self.FLOW_MAG_THRESHOLD * 1.5:
                conf = min(0.55 + rs["lateral_ratio"] * 0.4, 0.96)
                sev = "critical" if rs["lateral_ratio"] > 0.7 else "warning"
                results.append(DetectionResult(
                    incident_type="swerving",
                    severity=sev,
                    confidence=round(conf, 3),
                    description=(
                        f"Erratic lateral movement detected — lateral flow ratio "
                        f"{rs['lateral_ratio']:.0%}. Possible impaired driver."
                    ),
                    details={
                        "lateral_ratio": round(rs["lateral_ratio"], 3),
                        "mean_magnitude": round(rs["mean_mag"], 2),
                        "method": "optical_flow_snapshot",
                    },
                    has_detection=True,
                ))

            # --- Speed variance ---
            if rs["mean_mag"] > 0 and rs["std_mag"] / rs["mean_mag"] > self.SPEED_STD_RATIO:
                ratio = rs["std_mag"] / rs["mean_mag"]
                conf = min(0.50 + ratio * 0.3, 0.95)
                sev = "critical" if ratio > 1.0 else "warning"
                results.append(DetectionResult(
                    incident_type="speed_variance",
                    severity=sev,
                    confidence=round(conf, 3),
                    description=(
                        f"Speed variance {ratio:.0%} within detected vehicle region. "
                        f"Erratic acceleration/deceleration pattern."
                    ),
                    details={
                        "speed_variance_ratio": round(ratio, 3),
                        "mean_magnitude": round(rs["mean_mag"], 2),
                        "std_magnitude": round(rs["std_mag"], 2),
                        "method": "optical_flow_snapshot",
                    },
                    has_detection=True,
                ))

            # --- Wrong-way ---
            region_angle = math.degrees(math.atan2(rs["mean_fy"], rs["mean_fx"])) % 360
            angle_dev = abs(region_angle - dominant_angle)
            if angle_dev > 180:
                angle_dev = 360 - angle_dev
            if angle_dev > self.WRONG_WAY_ANGLE_DEV and rs["mean_mag"] > self.FLOW_MAG_THRESHOLD * 2:
                conf = min(0.60 + (angle_dev / 180) * 0.35, 0.97)
                results.append(DetectionResult(
                    incident_type="wrong_way",
                    severity="critical",
                    confidence=round(conf, 3),
                    description=(
                        f"Vehicle moving {angle_dev:.0f}° from dominant traffic flow. "
                        f"Possible wrong-way driver."
                    ),
                    details={
                        "angle_deviation": round(angle_dev, 1),
                        "dominant_angle": round(dominant_angle, 1),
                        "region_angle": round(region_angle, 1),
                        "method": "optical_flow_snapshot",
                    },
                    has_detection=True,
                ))

            # --- Aggressive (high magnitude + high variance) ---
            if rs["mean_mag"] > self.FLOW_MAG_THRESHOLD * 3 and rs["std_mag"] > self.FLOW_MAG_THRESHOLD * 2:
                conf = min(0.50 + rs["mean_mag"] * 0.02, 0.93)
                results.append(DetectionResult(
                    incident_type="aggressive",
                    severity="warning",
                    confidence=round(conf, 3),
                    description=(
                        f"High-speed erratic motion detected — mean flow "
                        f"{rs['mean_mag']:.1f} px with high variance."
                    ),
                    details={
                        "mean_magnitude": round(rs["mean_mag"], 2),
                        "std_magnitude": round(rs["std_mag"], 2),
                        "method": "optical_flow_snapshot",
                    },
                    has_detection=True,
                ))

        # Deduplicate: keep highest confidence per type
        best: dict[str, DetectionResult] = {}
        for r in results:
            if r.incident_type not in best or r.confidence > best[r.incident_type].confidence:
                best[r.incident_type] = r
        return list(best.values())

    def _check_stopped_only(
        self, prev_gray: np.ndarray, curr_gray: np.ndarray, mag: np.ndarray
    ) -> list[DetectionResult]:
        """When there's little optical flow, check for large stationary objects
        that appeared between frames — potential stopped vehicle."""
        diff = cv2.absdiff(prev_gray, curr_gray)
        _, diff_thresh = cv2.threshold(diff, 30, 255, cv2.THRESH_BINARY)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
        diff_thresh = cv2.morphologyEx(diff_thresh, cv2.MORPH_CLOSE, kernel, iterations=2)

        contours, _ = cv2.findContours(diff_thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        large = [c for c in contours if cv2.contourArea(c) >= self.MIN_CONTOUR_AREA * 2]

        results = []
        for cnt in large:
            mask = np.zeros_like(prev_gray)
            cv2.drawContours(mask, [cnt], -1, 255, -1)
            region_mag = mag[mask > 0]
            mean_mag = float(np.mean(region_mag)) if len(region_mag) > 0 else 0

            if mean_mag < self.STOPPED_MOTION_CEIL:
                area = cv2.contourArea(cnt)
                conf = min(0.55 + (area / 10000) * 0.2, 0.90)
                results.append(DetectionResult(
                    incident_type="stopped_vehicle",
                    severity="moderate" if conf < 0.75 else "warning",
                    confidence=round(conf, 3),
                    description=(
                        f"Stationary object (area {area:.0f} px²) detected in lane "
                        f"with near-zero motion. Possible stopped vehicle."
                    ),
                    details={
                        "contour_area": area,
                        "mean_flow_magnitude": round(mean_mag, 3),
                        "method": "frame_diff_snapshot",
                    },
                    has_detection=True,
                ))

        return results[:1]  # at most one stopped-vehicle per pair


# ---------- Camera Analysis Manager ----------

class CameraAnalysisManager:
    """Maintains per-camera SnapshotAnalyzer instances so that each camera
    accumulates its own prev-frame state across scheduler poll cycles.

    Usage in scheduler:
        manager = CameraAnalysisManager()
        # each cycle:
        results = manager.analyze(camera_id, frame)
    """

    def __init__(self):
        self._analyzers: dict[int, SnapshotAnalyzer] = {}
        self._max_analyzers = 500  # cap memory

    def analyze(self, camera_id: int, frame: np.ndarray) -> list[DetectionResult]:
        if camera_id not in self._analyzers:
            if len(self._analyzers) >= self._max_analyzers:
                # Evict oldest (first inserted)
                oldest = next(iter(self._analyzers))
                del self._analyzers[oldest]
            self._analyzers[camera_id] = SnapshotAnalyzer()

        return self._analyzers[camera_id].feed(frame)

    def reset(self, camera_id: int):
        self._analyzers.pop(camera_id, None)


# ---------- Simulated Detection (for demo/testing) ----------

def simulate_detection(camera_lat: float, camera_lng: float) -> Optional[DetectionResult]:
    """
    Generate a simulated detection for demo purposes.
    Uses realistic probability distributions based on time of day and location.
    """
    import random
    from datetime import datetime

    hour = datetime.now().hour

    # Higher incident probability during late night / early morning
    base_prob = 0.02
    if 0 <= hour < 5:
        base_prob = 0.08  # Late night — higher DUI probability
    elif 16 <= hour < 20:
        base_prob = 0.05  # Rush hour — more aggressive driving

    # Hotspot regions (LA, SF, Sacramento)
    la_dist = math.sqrt((camera_lat - 34.05) ** 2 + (camera_lng + 118.25) ** 2)
    sf_dist = math.sqrt((camera_lat - 37.77) ** 2 + (camera_lng + 122.42) ** 2)
    sac_dist = math.sqrt((camera_lat - 38.58) ** 2 + (camera_lng + 121.49) ** 2)

    min_dist = min(la_dist, sf_dist, sac_dist)
    if min_dist < 0.5:
        base_prob *= 2.5
    elif min_dist < 1.0:
        base_prob *= 1.5

    if random.random() > base_prob:
        return None

    # Pick incident type with realistic distribution
    incident_types = [
        ("swerving", 0.35, "Erratic lane changes detected. Lateral movement variance exceeds threshold. Possible impaired driver."),
        ("speed_variance", 0.30, "Abnormal speed fluctuations detected. Repeated acceleration/deceleration cycles observed."),
        ("aggressive", 0.20, "Aggressive driving pattern — tailgating and rapid lane changes."),
        ("stopped_vehicle", 0.10, "Vehicle appears stopped in active travel lane. Possible breakdown."),
        ("wrong_way", 0.05, "Vehicle direction inconsistent with expected traffic flow."),
    ]

    r = random.random()
    cumulative = 0
    chosen = incident_types[0]
    for it in incident_types:
        cumulative += it[1]
        if r <= cumulative:
            chosen = it
            break

    incident_type, _, description = chosen

    severity_map = {
        "swerving": random.choice(["critical", "critical", "warning"]),
        "speed_variance": random.choice(["critical", "warning", "warning"]),
        "aggressive": random.choice(["warning", "warning", "moderate"]),
        "stopped_vehicle": random.choice(["warning", "moderate", "moderate"]),
        "wrong_way": "critical",
    }

    confidence = round(random.uniform(0.65, 0.98), 3)

    # Add small random offset to position
    lat_offset = random.uniform(-0.02, 0.02)
    lng_offset = random.uniform(-0.02, 0.02)

    return DetectionResult(
        incident_type=incident_type,
        severity=severity_map[incident_type],
        confidence=confidence,
        description=description,
        details={
            "latitude": camera_lat + lat_offset,
            "longitude": camera_lng + lng_offset,
            "simulated": True,
        },
        has_detection=True,
    )
