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
_IDEYE_DIR = os.path.join(_ROOT_DIR, "ideye")
for p in (_ROOT_DIR, _IDEYE_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

from ideye.core.gaze_estimator import GazeEstimator, OneEuroFilter
from ideye.core.gesture_detector import GestureDetector, GestureState
from ideye.core.camera_tracker import CameraTracker


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
