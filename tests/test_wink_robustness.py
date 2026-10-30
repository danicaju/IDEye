"""Robust wink detection: calibration, gates, timing and double-wink confirmation."""

import math
import unittest
from types import SimpleNamespace

from ideye.core.gesture_detector import GestureDetector


class Point:
    def __init__(self, x, y):
        self.x = float(x)
        self.y = float(y)


class Face:
    def __init__(self):
        self.landmark = [Point(0.5, 0.5) for _ in range(468)]
        self.set_eye("left", open_eye=True)
        self.set_eye("right", open_eye=True)
        self.landmark[1] = Point(0.5, 0.5)
        self.landmark[13] = Point(0.5, 0.50)
        self.landmark[14] = Point(0.5, 0.52)
        self.landmark[78] = Point(0.44, 0.51)
        self.landmark[308] = Point(0.56, 0.51)
        for idx in (65, 105, 295, 334):
            self.landmark[idx] = Point(0.5, 0.30)

    def set_eye(self, side, open_eye=True):
        if side == "left":
            outer, top1, top2, inner, bot2, bot1 = 33, 160, 158, 133, 153, 144
            x1, x2 = 0.35, 0.45
        else:
            inner, top1, top2, outer, bot2, bot1 = 362, 385, 387, 263, 373, 380
            x1, x2 = 0.55, 0.65
        mid = (x1 + x2) / 2.0
        y = 0.40
        delta = 0.02 if open_eye else 0.0
        self.landmark[outer] = Point(x1, y)
        self.landmark[inner] = Point(x2, y)
        self.landmark[top1] = Point(mid - 0.02, y - delta)
        self.landmark[bot1] = Point(mid - 0.02, y + delta)
        self.landmark[top2] = Point(mid + 0.02, y - delta)
        self.landmark[bot2] = Point(mid + 0.02, y + delta)


def make_detector(**kwargs):
    defaults = dict(
        ear_close_threshold=0.16,
        ear_open_threshold=0.22,
        wink_min_hold_sec=0.18,
        wink_max_hold_sec=0.30,
        wink_cooldown_sec=0.65,
        wink_trigger_on_release=True,
        wink_opposite_margin=0.035,
        wink_min_interocular_dist=0.075,
        wink_max_roll_deg=28.0,
        wink_max_yaw_ratio=0.55,
    )
    defaults.update(kwargs)
    return GestureDetector(**defaults)


class TestWinkRobustness(unittest.TestCase):
    def test_bilateral_blink_never_triggers_a_wink(self):
        detector = make_detector()
        face = Face()
        face.set_eye("left", False)
        face.set_eye("right", False)
        detector.process(face, current_time=1.0)
        detector.process(face, current_time=1.2)
        face.set_eye("left", True)
        face.set_eye("right", True)
        result = detector.process(face, current_time=1.25)
        self.assertNotIn("WINK_LEFT", result.gestures)
        self.assertNotIn("WINK_RIGHT", result.gestures)

    def test_opposite_eye_margin_rejects_barely_open_eye(self):
        detector = make_detector()
        face = Face()
        face.set_eye("left", False)
        # Right eye is technically above the open threshold but below open + margin.
        face.landmark[385] = Point(0.58, 0.392)
        face.landmark[387] = Point(0.62, 0.392)
        face.landmark[373] = Point(0.62, 0.408)
        face.landmark[380] = Point(0.58, 0.408)
        detector.process(face, current_time=2.0)
        detector.process(face, current_time=2.2)
        face.set_eye("left", True)
        result = detector.process(face, current_time=2.25)
        self.assertNotIn("WINK_LEFT", result.gestures)

    def test_adaptive_ear_baseline_uses_relative_thresholds(self):
        detector = make_detector()
        face = Face()
        for index in range(15):
            detector.process(face, current_time=3.0 + index * 0.02)
        self.assertIsNotNone(detector.left_ear_baseline)
        self.assertGreater(detector.left_ear_close_threshold, 0.16)
        self.assertGreater(detector.left_ear_open_threshold, 0.22)

    def test_distance_gate_rejects_far_face(self):
        detector = make_detector()
        face = Face()
        for idx in range(len(face.landmark)):
            face.landmark[idx] = Point(
                0.5 + (face.landmark[idx].x - 0.5) * 0.15,
                0.5 + (face.landmark[idx].y - 0.5) * 0.15,
            )
        face.set_eye("left", False)
        detector.process(face, current_time=4.0)
        detector.process(face, current_time=4.2)
        face.set_eye("left", True)
        result = detector.process(face, current_time=4.25)
        self.assertNotIn("WINK_LEFT", result.gestures)

    def test_roll_and_yaw_gates(self):
        detector = make_detector()
        face = Face()
        self.assertTrue(detector._wink_quality_ok(face))
        face.landmark[263] = Point(0.65, 0.62)
        self.assertFalse(detector._wink_quality_ok(face))
        face = Face()
        face.landmark[1] = Point(0.90, 0.50)
        self.assertFalse(detector._wink_quality_ok(face))

    def test_hold_window_and_cooldown(self):
        detector = make_detector()
        face = Face()
        face.set_eye("left", False)
        detector.process(face, current_time=5.0)
        detector.process(face, current_time=5.10)
        face.set_eye("left", True)
        result = detector.process(face, current_time=5.12)
        self.assertNotIn("WINK_LEFT", result.gestures)

        face.set_eye("left", False)
        detector.process(face, current_time=6.0)
        detector.process(face, current_time=6.22)
        face.set_eye("left", True)
        result = detector.process(face, current_time=6.24)
        self.assertIn("WINK_LEFT", result.gestures)

        face.set_eye("left", False)
        detector.process(face, current_time=6.35)
        detector.process(face, current_time=6.55)
        face.set_eye("left", True)
        result = detector.process(face, current_time=6.57)
        self.assertNotIn("WINK_LEFT", result.gestures)

    def test_double_wink_is_emitted_as_confirmation(self):
        detector = make_detector(wink_double_enabled=True)
        face = Face()
        face.set_eye("left", False)
        detector.process(face, current_time=7.0)
        detector.process(face, current_time=7.22)
        face.set_eye("left", True)
        first = detector.process(face, current_time=7.24)
        self.assertIn("WINK_LEFT", first.gestures)

        face.set_eye("left", False)
        detector.process(face, current_time=7.40)
        detector.process(face, current_time=7.62)
        face.set_eye("left", True)
        second = detector.process(face, current_time=7.64)
        self.assertIn("WINK_LEFT_DOUBLE", second.gestures)

    def test_disabled_and_mouth_only_suppress_winks(self):
        for kwargs in ({"wink_enabled": False}, {"wink_mouth_only": True}):
            detector = make_detector(**kwargs)
            face = Face()
            face.set_eye("left", False)
            detector.process(face, current_time=8.0)
            detector.process(face, current_time=8.22)
            face.set_eye("left", True)
            result = detector.process(face, current_time=8.24)
            self.assertNotIn("WINK_LEFT", result.gestures)

    def test_explicit_ear_calibration(self):
        detector = make_detector()
        self.assertTrue(
            detector.set_ear_calibration({"left_open": 0.40, "right_open": 0.42})
        )
        self.assertFalse(detector.ear_auto_calibrate)
        self.assertGreater(detector.left_ear_close_threshold, 0.16)
        self.assertTrue(math.isfinite(detector.right_ear_open_threshold))


if __name__ == "__main__":
    unittest.main()
