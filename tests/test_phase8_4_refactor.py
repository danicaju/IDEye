"""Phase 8.4: bezel detector, header layout, per-monitor calibration."""

import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QRectF
from PyQt6.QtWidgets import QApplication

from ideye.core.bezel_crossing import BezelCrossingDetector
from ideye.core.gaze_estimator import GazeEstimator
from ideye.ui.header_layout import HeaderLayout

_APP = QApplication.instance() or QApplication(sys.argv if hasattr(sys, "argv") else [])

CALIBRATION_POINTS = [
    {"id": "CENTER", "screen": (0.5, 0.5), "raw": (0.50, 0.50)},
    {"id": "TOP_LEFT", "screen": (0.1, 0.1), "raw": (0.34, 0.34)},
    {"id": "TOP_RIGHT", "screen": (0.9, 0.1), "raw": (0.66, 0.34)},
    {"id": "BOTTOM_LEFT", "screen": (0.1, 0.9), "raw": (0.34, 0.66)},
    {"id": "BOTTOM_RIGHT", "screen": (0.9, 0.9), "raw": (0.66, 0.66)},
]


class TestBezelCrossingDetector(unittest.TestCase):
    def test_configurable_threshold_hold_and_cooldown(self):
        detector = BezelCrossingDetector(
            yaw_threshold_deg=15.0, hold_sec=0.2, cooldown_sec=0.5
        )
        self.assertEqual(detector.update(20.0, True, True, timestamp=0.0), 0)
        self.assertEqual(detector.update(20.0, True, True, timestamp=0.1), 0)
        self.assertEqual(detector.update(20.0, True, True, timestamp=0.21), 1)
        self.assertEqual(detector.update(20.0, True, True, timestamp=0.50), 0)
        self.assertEqual(detector.update(20.0, True, True, timestamp=0.72), 1)

    def test_edge_without_neighbour_does_not_fire(self):
        detector = BezelCrossingDetector(yaw_threshold_deg=10.0, hold_sec=0.0)
        self.assertEqual(detector.update(30.0, False, False, timestamp=1.0), 0)
        self.assertEqual(detector.update(-30.0, False, False, timestamp=1.1), 0)

    def test_disabled_detector_never_fires(self):
        detector = BezelCrossingDetector(enabled=False)
        self.assertEqual(detector.update(90.0, True, True, timestamp=1.0), 0)
        self.assertEqual(detector.update(90.0, True, True, timestamp=2.0), 0)


class TestHeaderLayout(unittest.TestCase):
    def test_standard_layout_does_not_overlap(self):
        layout = HeaderLayout.compute(
            width=1920,
            margin=12,
            header_height=52,
            right_margin=364,
            grid_left=12,
            show_last_action=True,
            screen_count=1,
            mode_id="coding",
            brand_text_width=42,
            ws_full_width=62,
        )
        self.assertTrue(layout.header.isValid())
        self.assertTrue(layout.exit.isValid())
        self.assertLessEqual(layout.exit.right(), layout.header.right())
        self.assertLess(layout.help.right(), layout.exit.left())
        self.assertLess(layout.mode.right(), layout.lang.left())
        self.assertLess(layout.lang.right(), layout.help.left())
        self.assertIn("QRectF", str(type(layout.header)))

    def test_screen_and_sniper_slots(self):
        screens = HeaderLayout.compute(
            width=1920, margin=12, header_height=52, right_margin=0, grid_left=12,
            show_last_action=False, screen_count=2, mode_id="coding",
            brand_text_width=42, ws_full_width=62,
        )
        self.assertTrue(screens.screen.isValid())
        self.assertFalse(screens.last_action.isValid())

        sniper = HeaderLayout.compute(
            width=1920, margin=12, header_height=52, right_margin=0, grid_left=12,
            show_last_action=True, screen_count=2, mode_id="sniper",
            brand_text_width=42, ws_full_width=62,
        )
        self.assertFalse(sniper.screen.isValid())
        self.assertTrue(sniper.sniper_action.isValid())

    def test_narrow_layout_hides_optional_pill(self):
        layout = HeaderLayout.compute(
            width=600, margin=12, header_height=52, right_margin=0, grid_left=12,
            show_last_action=True, screen_count=2, mode_id="coding",
            brand_text_width=42, ws_full_width=62,
        )
        self.assertFalse(layout.last_action.isValid())
        self.assertFalse(layout.screen.isValid())
        self.assertGreaterEqual(layout.mode_w, 120.0)


class TestPerMonitorCalibration(unittest.TestCase):
    def test_calibration_is_saved_and_restored_per_monitor(self):
        source = GazeEstimator()
        source.set_active_monitor("monA", 1920, 1080, 527.0, 296.0, 96.0)
        self.assertTrue(source.calibrate_5_points(CALIBRATION_POINTS))
        self.assertTrue(source.active_monitor_calibrated)

        with tempfile.TemporaryDirectory() as tmp:
            base = os.path.join(tmp, "calibration_profile.json")
            self.assertTrue(source.save_calibration_profile(base))
            monitor_files = list(Path(tmp, "calibration_profiles").glob("*.json"))
            self.assertEqual(len(monitor_files), 1)

            restored = GazeEstimator()
            self.assertTrue(restored.load_calibration_profile(base))
            self.assertFalse(restored.active_monitor_calibrated)
            self.assertTrue(restored.set_active_monitor("monA", 1920, 1080, 527.0, 296.0, 96.0))
            self.assertTrue(restored.active_monitor_calibrated)
            self.assertTrue(restored.has_5_point_calibration)

            self.assertFalse(restored.set_active_monitor("monB", 3840, 2160, 600.0, 340.0, 160.0))
            self.assertFalse(restored.active_monitor_calibrated)
            self.assertEqual(restored.get_target_screen(), (3840, 2160))

            self.assertTrue(restored.set_active_monitor("monA", 1920, 1080, 527.0, 296.0, 96.0))
            self.assertTrue(restored.active_monitor_calibrated)

    def test_clear_monitor_profiles_backs_up_directory(self):
        estimator = GazeEstimator()
        estimator.set_active_monitor("monA", 1920, 1080, 527.0, 296.0, 96.0)
        self.assertTrue(estimator.calibrate_5_points(CALIBRATION_POINTS))
        with tempfile.TemporaryDirectory() as tmp:
            base = os.path.join(tmp, "calibration_profile.json")
            self.assertTrue(estimator.save_calibration_profile(base))
            profiles = Path(tmp, "calibration_profiles")
            self.assertTrue(profiles.is_dir())
            self.assertTrue(estimator.clear_monitor_profiles(backup=True))
            self.assertFalse(profiles.is_dir())
            self.assertTrue(Path(tmp, "calibration_profiles.bak").is_dir())

    def test_monitor_state_exposes_physical_metadata(self):
        estimator = GazeEstimator()
        estimator.set_active_monitor("monC", 2560, 1440, 600.0, 340.0, 144.0)
        state = estimator.get_active_monitor_state()
        self.assertEqual(state["key"], "monC")
        self.assertEqual(state["size"], (2560, 1440))
        self.assertEqual(state["physical_mm"], (600.0, 340.0))
        self.assertEqual(state["dpi"], 144.0)


if __name__ == "__main__":
    unittest.main()
