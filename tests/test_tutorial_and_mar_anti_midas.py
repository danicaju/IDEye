"""
Deep verification tests for:
1. Guided Mini-Tutorial startup, paint rendering (crash-free), aliases, and close interaction.
2. Adaptive resting MAR baseline (Anti-Midas protection), avoiding ghost clicks for uncalibrated
   users with resting MAR near or above static thresholds.
"""

import time
import unittest
import numpy as np
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QImage, QPainter

from ideye.core.gesture_detector import GestureDetector, GestureState
from ideye.ui.overlay_window import OverlayWindow
from ideye.ui.calibration_ui import compute_auto_mar_threshold
import ideye.config as config


class MockPoint:
    def __init__(self, x: float, y: float):
        self.x = float(x)
        self.y = float(y)


class MockFace:
    def __init__(self, count: int = 478):
        self.landmark = [MockPoint(0.5, 0.5) for _ in range(count)]

    def set_lip(self, top_y: float, bot_y: float, left_x: float, right_x: float) -> None:
        self.landmark[13] = MockPoint(0.5, top_y)
        self.landmark[14] = MockPoint(0.5, bot_y)
        self.landmark[78] = MockPoint(left_x, (top_y + bot_y) * 0.5)
        self.landmark[308] = MockPoint(right_x, (top_y + bot_y) * 0.5)

    def set_eyes(self, left_ear: float = 0.28, right_ear: float = 0.28) -> None:
        # Standard open eyes
        self.landmark[33] = MockPoint(0.35, 0.40)
        self.landmark[133] = MockPoint(0.45, 0.40)
        self.landmark[160] = MockPoint(0.40, 0.40 - left_ear * 0.05)
        self.landmark[158] = MockPoint(0.40, 0.40 - left_ear * 0.05)
        self.landmark[153] = MockPoint(0.40, 0.40 + left_ear * 0.05)
        self.landmark[144] = MockPoint(0.40, 0.40 + left_ear * 0.05)

        self.landmark[362] = MockPoint(0.55, 0.40)
        self.landmark[263] = MockPoint(0.65, 0.40)
        self.landmark[385] = MockPoint(0.60, 0.40 - right_ear * 0.05)
        self.landmark[387] = MockPoint(0.60, 0.40 - right_ear * 0.05)
        self.landmark[373] = MockPoint(0.60, 0.40 + right_ear * 0.05)
        self.landmark[380] = MockPoint(0.60, 0.40 + right_ear * 0.05)


def create_face_with_mar(target_mar: float) -> MockFace:
    face = MockFace()
    face.set_eyes(0.28, 0.28)
    width = 0.12
    height = target_mar * width
    cy = 0.65
    face.set_lip(cy - height * 0.5, cy + height * 0.5, 0.5 - width * 0.5, 0.5 + width * 0.5)
    return face


class TestTutorialCrashFixAndLifecycle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.overlay = OverlayWindow()
        self.overlay.resize(1920, 1080)

    def tearDown(self):
        self.overlay.close()

    def test_start_tutorial_and_active_property(self):
        self.assertFalse(self.overlay._tutorial_active)
        self.overlay.start_tutorial()
        self.assertTrue(self.overlay._tutorial_active)
        self.assertTrue(self.overlay.show_tutorial_modal)
        self.assertEqual(self.overlay.tutorial_step, 1)

        self.overlay.close_tutorial()
        self.assertFalse(self.overlay._tutorial_active)
        self.assertFalse(self.overlay.show_tutorial_modal)

    def test_paint_event_does_not_crash_all_steps(self):
        """Renders the tutorial modal in paintEvent across all steps without raising any exception."""
        img = QImage(1920, 1080, QImage.Format.Format_ARGB32)
        p = QPainter(img)

        self.overlay.start_tutorial()
        for step in (1, 2, 3, 4, 5):
            self.overlay.tutorial_step = step
            self.overlay.tutorial_step_progress = 0.5
            # Must complete paintEvent cleanly without raising AttributeError (AlignmentFlag.TextWordWrap)
            self.overlay._paint_tutorial_modal(p, 1920.0, 1080.0)

        p.end()

    def test_tutorial_close_button_hit(self):
        """Clicking the [X] close button on the tutorial modal closes it."""
        self.overlay.start_tutorial()
        img = QImage(1920, 1080, QImage.Format.Format_ARGB32)
        p = QPainter(img)
        self.overlay._paint_tutorial_modal(p, 1920.0, 1080.0)
        p.end()

        close_rect = getattr(self.overlay, "tutorial_modal_close_rect", None)
        self.assertIsNotNone(close_rect)
        self.assertTrue(close_rect.isValid())

        # Simulate mouse click on the close button
        class DummyEvent:
            def __init__(self, pt):
                self._pt = pt
                self.accepted = False

            def pos(self):
                return self._pt

            def position(self):
                return self._pt

            def accept(self):
                self.accepted = True

        center = close_rect.center()
        evt = DummyEvent(center)
        self.overlay.mousePressEvent(evt)
        self.assertTrue(evt.accepted)
        self.assertFalse(self.overlay.show_tutorial_modal)


class TestAdaptiveMARAntiMidas(unittest.TestCase):
    def test_high_resting_mar_does_not_ghost_click(self):
        """
        Critical bug scenario: User with resting MAR 0.38 at uncalibrated startup.
        A static 0.35/0.45 threshold would produce an infinite click loop.
        Adaptive baseline must learn 0.38, elevate trigger to >= 0.52, and produce 0 clicks.
        """
        detector = GestureDetector(mar_threshold=0.45, release_threshold=0.35)
        self.assertFalse(detector.mar_calibrated)

        resting_face = create_face_with_mar(0.38)
        t = 1000.0

        clicks = 0
        for _ in range(60):  # 2 full seconds of relaxed resting face
            t += 0.033
            res = detector.process(resting_face, current_time=t)
            if res.clicked or "MOUTH_CLICK" in res.gestures:
                clicks += 1

        self.assertEqual(clicks, 0, "Resting mouth at MAR=0.38 MUST NOT trigger any ghost clicks!")
        self.assertIsNotNone(detector.mar_baseline)
        self.assertAlmostEqual(detector.mar_baseline, 0.38, delta=0.03)

        eff_trigger, eff_release = detector.get_effective_mar_thresholds()
        self.assertGreater(eff_trigger, 0.50, "Trigger threshold must be safely elevated above resting MAR")
        self.assertGreaterEqual(eff_release, 0.38, "Release threshold must accommodate resting MAR")

    def test_deliberate_mouth_open_triggers_click(self):
        """After establishing resting baseline at 0.36, opening mouth to 0.65 for 150ms fires click."""
        detector = GestureDetector(mar_threshold=0.45, release_threshold=0.35)
        resting_face = create_face_with_mar(0.36)
        t = 1000.0

        for _ in range(30):
            t += 0.033
            detector.process(resting_face, current_time=t)

        open_face = create_face_with_mar(0.65)
        clicks = 0
        for _ in range(6):  # ~200ms hold (> 150ms hold_time)
            t += 0.033
            res = detector.process(open_face, current_time=t)
            if res.clicked or "MOUTH_CLICK" in res.gestures:
                clicks += 1

        self.assertEqual(clicks, 1, "Deliberate mouth opening must trigger exactly one click!")

    def test_cooldown_and_release_rearm(self):
        """Holding mouth open continuously past one click does NOT fire repeated clicks without closing."""
        detector = GestureDetector(mar_threshold=0.45, release_threshold=0.35)
        resting_face = create_face_with_mar(0.20)
        t = 1000.0

        for _ in range(20):
            t += 0.033
            detector.process(resting_face, current_time=t)

        open_face = create_face_with_mar(0.60)
        clicks = 0
        for _ in range(30):  # 1 full second of continuous mouth open
            t += 0.033
            res = detector.process(open_face, current_time=t)
            if res.clicked or "MOUTH_CLICK" in res.gestures:
                clicks += 1

        self.assertEqual(clicks, 1, "Continuous open mouth must not re-trigger clicks without closing first!")

    def test_effective_thresholds_guarantee_safe_separation(self):
        """Effective threshold calculation guarantees safe separation from resting MAR."""
        detector = GestureDetector(mar_threshold=0.25, release_threshold=0.20)
        detector.mar_baseline = 0.22
        trigger, release = detector.get_effective_mar_thresholds()
        self.assertGreaterEqual(trigger, 0.22 + 0.12, "Trigger threshold must enforce safe margin above resting baseline!")
        self.assertLess(release, trigger)
        self.assertGreater(trigger - release, 0.05, "Hysteresis must be enforced!")


if __name__ == "__main__":
    unittest.main()
