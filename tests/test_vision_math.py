"""
Automated Forensic Test Suite: Vision & Mathematics (Phase Extra)
Tests GazeEstimator (EMA, coordinate clipping, degenerate zero-division calibration)
and GestureDetector (MAR computation, debouncing state machine, hold time, cooldown).
"""

import os
import sys
import json
import math
import tempfile
import unittest
import numpy as np

# Ensure project root is in sys.path
_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_EYEDE_DIR = os.path.join(_ROOT_DIR, "eyede")
for p in (_ROOT_DIR, _EYEDE_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

from eyede.core.gaze_estimator import GazeEstimator
from eyede.core.gesture_detector import GestureDetector, GestureState
from eyede.core.camera_tracker import CameraTracker


class MockLandmarkPoint:
    def __init__(self, x: float, y: float, z: float = 0.0):
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)


class MockFaceMesh:
    def __init__(self, count: int = 478, default_x: float = 0.5, default_y: float = 0.5):
        self.landmark = [MockLandmarkPoint(default_x, default_y) for _ in range(count)]

    def set_pt(self, idx: int, x: float, y: float, z: float = 0.0):
        self.landmark[idx] = MockLandmarkPoint(x, y, z)


def create_neutral_face() -> MockFaceMesh:
    """Returns a synthetic neutral face with canonical landmark locations."""
    face = MockFaceMesh()
    # Nose tip
    face.set_pt(1, 0.50, 0.50)

    # Left eye outer (33) and inner (133), top (159), bottom (145), iris (468)
    face.set_pt(33, 0.35, 0.40)
    face.set_pt(133, 0.45, 0.40)
    face.set_pt(159, 0.40, 0.38)
    face.set_pt(145, 0.40, 0.42)
    face.set_pt(468, 0.40, 0.40)

    # Right eye inner (362) and outer (263), top (386), bottom (374), iris (473)
    face.set_pt(362, 0.55, 0.40)
    face.set_pt(263, 0.65, 0.40)
    face.set_pt(386, 0.60, 0.38)
    face.set_pt(374, 0.60, 0.42)
    face.set_pt(473, 0.60, 0.40)

    # Mouth top (13), bottom (14), left (78), right (308)
    face.set_pt(13, 0.50, 0.65)
    face.set_pt(14, 0.50, 0.67)  # Closed mouth (small MAR)
    face.set_pt(78, 0.44, 0.66)
    face.set_pt(308, 0.56, 0.66)

    return face


class TestGazeEstimatorMath(unittest.TestCase):
    """Deep verification of GazeEstimator math, EMA, clipping, and calibration robustness."""

    def setUp(self):
        self.estimator = GazeEstimator(
            head_weight=0.5,
            iris_weight=0.5,
            head_sensitivity_x=2.0,
            head_sensitivity_y=2.0,
            iris_sensitivity_x=2.0,
            iris_sensitivity_y=2.0,
            ema_alpha=0.25,
        )

    def test_ema_smoothing_convergence(self):
        """EMA should smoothly interpolate from first sample towards target without sudden steps."""
        face = create_neutral_face()
        # First sample initializes smoothed coordinates directly
        gx1, gy1, det1, _ = self.estimator.estimate(face)
        self.assertTrue(det1)
        self.assertAlmostEqual(gx1, 0.5, delta=0.05)
        self.assertAlmostEqual(gy1, 0.5, delta=0.05)

        # Move nose tip drastically to simulate a shift to right
        face.set_pt(1, 0.70, 0.50)
        gx2, gy2, det2, _ = self.estimator.estimate(face)
        self.assertTrue(det2)
        # With alpha=0.25, change should be smoothed (less than full leap)
        self.assertGreater(gx2, gx1)
        self.assertLess(gx2, 1.0)

        # Repeating same input brings EMA closer to target
        for _ in range(30):
            gx_final, _, _, _ = self.estimator.estimate(face)
        self.assertGreater(gx_final, gx2)

    def test_coordinate_clipping_extreme_bounds(self):
        """Even with extreme head/eye movements, output coordinates must strictly remain in [0.0, 1.0]."""
        face = create_neutral_face()
        # Extreme right and bottom
        face.set_pt(1, 10.0, 50.0)
        face.set_pt(468, 10.0, 50.0)
        face.set_pt(473, 10.0, 50.0)

        for _ in range(30):
            gx, gy, det, _ = self.estimator.estimate(face)
            self.assertTrue(det)
            self.assertGreaterEqual(gx, 0.0)
            self.assertLessEqual(gx, 1.0)
            self.assertGreaterEqual(gy, 0.0)
            self.assertLessEqual(gy, 1.0)
        self.assertAlmostEqual(gx, 1.0, delta=1e-3)
        self.assertAlmostEqual(gy, 1.0, delta=1e-3)

        # Extreme left and top
        face.set_pt(1, -20.0, -100.0)
        face.set_pt(468, -20.0, -100.0)
        face.set_pt(473, -20.0, -100.0)

        for _ in range(30):
            gx, gy, det, _ = self.estimator.estimate(face)
            self.assertTrue(det)
            self.assertGreaterEqual(gx, 0.0)
            self.assertLessEqual(gx, 1.0)
            self.assertGreaterEqual(gy, 0.0)
            self.assertLessEqual(gy, 1.0)
        self.assertAlmostEqual(gx, 0.0, delta=1e-3)
        self.assertAlmostEqual(gy, 0.0, delta=1e-3)

    def test_face_loss_graceful_retention(self):
        """When face is lost (None or empty landmarks), estimator retains last valid position clipped."""
        face = create_neutral_face()
        gx_init, gy_init, det_init, _ = self.estimator.estimate(face)
        self.assertTrue(det_init)

        # Loss with None
        gx_lost, gy_lost, det_lost, _ = self.estimator.estimate(None)
        self.assertFalse(det_lost)
        self.assertAlmostEqual(gx_lost, gx_init)
        self.assertAlmostEqual(gy_lost, gy_init)
        self.assertGreaterEqual(gx_lost, 0.0)
        self.assertLessEqual(gx_lost, 1.0)

        # Loss with empty landmarks
        gx_empty, gy_empty, det_empty, _ = self.estimator.estimate([])
        self.assertFalse(det_empty)
        self.assertAlmostEqual(gx_empty, gx_init)

    def test_zero_division_protection_overlapping_landmarks(self):
        """Overlapping landmarks (width=0, height=0) must not trigger ZeroDivisionError."""
        face = MockFaceMesh()
        # Set all landmarks to the exact same point
        for i in range(478):
            face.set_pt(i, 0.5, 0.5)

        gx, gy, det, debug_info = self.estimator.estimate(face)
        self.assertTrue(det)
        self.assertGreaterEqual(gx, 0.0)
        self.assertLessEqual(gx, 1.0)
        self.assertGreaterEqual(gy, 0.0)
        self.assertLessEqual(gy, 1.0)

    def test_calibration_profile_corrupt_empty_safe_defaults(self):
        """Corrupt, empty, or missing calibration profiles must not crash and restore defaults."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 1. Non-existent file
            non_existent = os.path.join(tmpdir, "does_not_exist.json")
            self.assertFalse(self.estimator.load_calibration_profile(non_existent))

            # 2. Empty file
            empty_file = os.path.join(tmpdir, "empty.json")
            with open(empty_file, "w", encoding="utf-8") as f:
                f.write("")
            self.assertFalse(self.estimator.load_calibration_profile(empty_file))
            self.assertFalse(self.estimator.has_5_point_calibration)

            # 3. Corrupt syntax (not JSON)
            corrupt_file = os.path.join(tmpdir, "corrupt.json")
            with open(corrupt_file, "w", encoding="utf-8") as f:
                f.write("{invalid json syntax, missing quotes")
            self.assertFalse(self.estimator.load_calibration_profile(corrupt_file))

            # 4. JSON not a dictionary
            list_file = os.path.join(tmpdir, "array.json")
            with open(list_file, "w", encoding="utf-8") as f:
                json.dump([1, 2, 3], f)
            self.assertFalse(self.estimator.load_calibration_profile(list_file))

            # 5. Invalid weights (NaN or wrong length)
            bad_weights = os.path.join(tmpdir, "bad_weights.json")
            with open(bad_weights, "w", encoding="utf-8") as f:
                json.dump({
                    "weights_x": [float("nan"), 1.0, 2.0, 3.0],
                    "weights_y": [1.0, 2.0, 3.0, 4.0],
                }, f)
            self.assertFalse(self.estimator.load_calibration_profile(bad_weights))

    def test_calibration_profile_degenerate_min_equals_max(self):
        """Calibration points with min == max in raw or screen coords (zero variation) must be rejected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            degenerate_file = os.path.join(tmpdir, "degenerate.json")
            # All raw x coordinates are identical (0.5) -> min == max -> division by zero in interpolation
            payload = {
                "version": 2,
                "has_5_point_calibration": True,
                "weights_x": [0.0, 1.0, 0.0, 0.0],
                "weights_y": [0.0, 0.0, 1.0, 0.0],
                "points": [
                    {"screen": (0.1, 0.1), "raw": (0.5, 0.2)},
                    {"screen": (0.9, 0.1), "raw": (0.5, 0.4)},
                    {"screen": (0.5, 0.5), "raw": (0.5, 0.5)},
                    {"screen": (0.1, 0.9), "raw": (0.5, 0.6)},
                    {"screen": (0.9, 0.9), "raw": (0.5, 0.8)},
                ],
            }
            with open(degenerate_file, "w", encoding="utf-8") as f:
                json.dump(payload, f)

            self.assertFalse(self.estimator.load_calibration_profile(degenerate_file))
            self.assertFalse(self.estimator.has_5_point_calibration)

    def test_valid_calibration_profile_load_and_save_cycle(self):
        """A valid 5-point calibration dataset must save and reload with exact fidelity."""
        valid_points = [
            {"screen": (0.1, 0.1), "raw": (0.2, 0.2)},
            {"screen": (0.9, 0.1), "raw": (0.8, 0.2)},
            {"screen": (0.5, 0.5), "raw": (0.5, 0.5)},
            {"screen": (0.1, 0.9), "raw": (0.2, 0.8)},
            {"screen": (0.9, 0.9), "raw": (0.8, 0.8)},
        ]
        calib_ok = self.estimator.calibrate_5_points(valid_points)
        self.assertTrue(calib_ok)
        self.assertTrue(self.estimator.has_5_point_calibration)

        with tempfile.TemporaryDirectory() as tmpdir:
            prof_path = os.path.join(tmpdir, "valid_profile.json")
            saved = self.estimator.save_calibration_profile(prof_path)
            self.assertTrue(saved)
            self.assertTrue(os.path.exists(prof_path))

            fresh = GazeEstimator()
            loaded = fresh.load_calibration_profile(prof_path)
            self.assertTrue(loaded)
            self.assertTrue(fresh.has_5_point_calibration)
            self.assertEqual(len(fresh.calib_weights_x), 4)
            self.assertEqual(len(fresh.calib_weights_y), 4)

    def test_apply_5_point_mapping_non_finite_safety(self):
        """When inputs or weights produce NaN or Inf, apply_5_point_mapping must fallback safely."""
        self.estimator.has_5_point_calibration = True
        self.estimator.calib_weights_x = [0.0, 1.0, 0.0, 0.0]
        self.estimator.calib_weights_y = [0.0, 0.0, 1.0, 0.0]

        # Normal mapping
        mx, my = self.estimator.apply_5_point_mapping(0.3, 0.7)
        self.assertAlmostEqual(mx, 0.3)
        self.assertAlmostEqual(my, 0.7)

        # Corrupted weights with NaN
        self.estimator.calib_weights_x = [float("nan"), 1.0, 0.0, 0.0]
        mx_nan, my_nan = self.estimator.apply_5_point_mapping(0.4, 0.6)
        self.assertFalse(math.isnan(mx_nan))
        self.assertAlmostEqual(mx_nan, 0.4)

    def test_camera_tracker_frame_to_qimage_memory_safety(self):
        """CameraTracker.frame_to_qimage() must perform contiguous deep copy and handle None/empty safely."""
        self.assertIsNone(CameraTracker.frame_to_qimage(None))
        self.assertIsNone(CameraTracker.frame_to_qimage(np.array([])))

        # Valid frame
        frame = np.full((120, 160, 3), 128, dtype=np.uint8)
        qimg = CameraTracker.frame_to_qimage(frame)
        self.assertIsNotNone(qimg)
        self.assertEqual(qimg.width(), 160)
        self.assertEqual(qimg.height(), 120)

        # Mutate numpy source; QImage must remain unaffected
        frame[:] = 0
        self.assertFalse(qimg.isNull())


class TestGestureDetectorMath(unittest.TestCase):
    """Deep verification of GestureDetector MAR math, debouncing state machine, and cooldown."""

    def setUp(self):
        self.detector = GestureDetector(
            mar_threshold=0.45,
            release_threshold=0.30,
            hold_time_sec=0.15,
            cooldown_sec=0.35,
        )

    def test_compute_mar_basic_and_clamping(self):
        """MAR must accurately reflect mouth opening ratio and clamp between 0.0 and 5.0."""
        face = create_neutral_face()
        # Initially closed mouth: vertical=0.02, horizontal=0.12 -> MAR ~ 0.166
        mar_closed = self.detector.compute_mar(face)
        self.assertAlmostEqual(mar_closed, 0.02 / 0.12, delta=0.02)
        self.assertLess(mar_closed, self.detector.release_threshold)

        # Open mouth: vertical=0.08, horizontal=0.12 -> MAR ~ 0.666
        face.set_pt(14, 0.50, 0.73)
        mar_open = self.detector.compute_mar(face)
        self.assertAlmostEqual(mar_open, 0.08 / 0.12, delta=0.02)
        self.assertGreater(mar_open, self.detector.mar_threshold)

        # Extreme artifact (infinite vertical span) must clamp to 5.0
        face.set_pt(14, 0.50, 10.0)
        mar_extreme = self.detector.compute_mar(face)
        self.assertEqual(mar_extreme, 5.0)

    def test_compute_mar_zero_division_safety(self):
        """When mouth corners are completely collapsed (width=0), MAR must not raise ZeroDivisionError."""
        face = MockFaceMesh()
        for i in (13, 14, 78, 308):
            face.set_pt(i, 0.5, 0.5)

        mar = self.detector.compute_mar(face)
        self.assertEqual(mar, 0.0)

    def test_debouncing_state_machine_hold_and_trigger(self):
        """Click should trigger ONLY when held open for hold_time_sec, not on brief twitches."""
        face_closed = create_neutral_face()
        face_open = create_neutral_face()
        face_open.set_pt(14, 0.50, 0.74)  # MAR ~ 0.75 > 0.45

        t = 1000.0
        # 1. Start in IDLE_CLOSED
        clicked, mar, prog = self.detector.process(face_closed, current_time=t)
        self.assertFalse(clicked)
        self.assertEqual(self.detector.state, GestureState.IDLE_CLOSED)
        self.assertEqual(prog, 0.0)

        # 2. Open mouth: transitions to HOLDING_OPEN
        t += 0.03
        clicked, mar, prog = self.detector.process(face_open, current_time=t)
        self.assertFalse(clicked)
        self.assertEqual(self.detector.state, GestureState.HOLDING_OPEN)
        self.assertEqual(prog, 0.0)

        # Progress advances on subsequent frame
        t += 0.04
        clicked, mar, prog = self.detector.process(face_open, current_time=t)
        self.assertFalse(clicked)
        self.assertEqual(self.detector.state, GestureState.HOLDING_OPEN)
        self.assertGreater(prog, 0.0)
        self.assertLess(prog, 1.0)

        # 3. User closes mouth before hold_time_sec (twitch / chatter) -> aborts back to IDLE_CLOSED
        t += 0.04  # Total 40ms < 150ms hold_time
        clicked, mar, prog = self.detector.process(face_closed, current_time=t)
        self.assertFalse(clicked)
        self.assertEqual(self.detector.state, GestureState.IDLE_CLOSED)
        self.assertEqual(prog, 0.0)

        # 4. Open mouth again and hold for full 150ms -> CLICK triggers exactly once!
        t += 0.01
        clicked, _, _ = self.detector.process(face_open, current_time=t)
        self.assertFalse(clicked)
        self.assertEqual(self.detector.state, GestureState.HOLDING_OPEN)

        t += 0.16  # Hold time reached (160ms > 150ms)
        clicked, mar, prog = self.detector.process(face_open, current_time=t)
        self.assertTrue(clicked)
        self.assertEqual(self.detector.state, GestureState.TRIGGERED)
        self.assertEqual(self.detector.total_clicks, 1)

        # 5. Subsequent frames with mouth still open DO NOT trigger extra clicks
        t += 0.03
        clicked, _, _ = self.detector.process(face_open, current_time=t)
        self.assertFalse(clicked)
        self.assertEqual(self.detector.total_clicks, 1)

    def test_cooldown_and_release_requirement(self):
        """After a click, a new click CANNOT occur until mouth is closed AND cooldown elapses."""
        face_closed = create_neutral_face()
        face_open = create_neutral_face()
        face_open.set_pt(14, 0.50, 0.74)

        t = 2000.0
        # Trigger first click
        self.detector.process(face_open, current_time=t)
        t += 0.16
        clicked, _, _ = self.detector.process(face_open, current_time=t)
        self.assertTrue(clicked)

        # Keep mouth open past cooldown (0.50s > 0.35s cooldown): NO click without release!
        t += 0.50
        clicked, _, _ = self.detector.process(face_open, current_time=t)
        self.assertFalse(clicked)
        self.assertEqual(self.detector.total_clicks, 1)

        # Close mouth to fulfill release requirement
        t += 0.05
        clicked, _, _ = self.detector.process(face_closed, current_time=t)
        self.assertFalse(clicked)
        self.assertTrue(self.detector.released_since_trigger)

        # Now opening mouth again initiates a new hold cycle
        t += 0.05
        clicked, _, _ = self.detector.process(face_open, current_time=t)
        self.assertFalse(clicked)
        self.assertEqual(self.detector.state, GestureState.HOLDING_OPEN)

        # Complete second click
        t += 0.16
        clicked, _, _ = self.detector.process(face_open, current_time=t)
        self.assertTrue(clicked)
        self.assertEqual(self.detector.total_clicks, 2)


if __name__ == "__main__":
    unittest.main()
