"""Phase 8.3: multi-monitor handover and screen-aware calibration bounds."""

import os
import sys
import unittest
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QRect
from PyQt6.QtWidgets import QApplication

from eyede.core.gaze_estimator import GazeEstimator
from eyede.core.screen_manager import ScreenManager
from eyede.ui.overlay_window import OverlayWindow

_APP = QApplication.instance() or QApplication(sys.argv if hasattr(sys, "argv") else [])


class FakeScreen:
    def __init__(self, width, height, name="Screen"):
        self._geo = QRect(0, 0, width, height)
        self._name = name

    def availableGeometry(self):
        return QRect(self._geo)

    def geometry(self):
        return QRect(self._geo)

    def isAvailable(self):
        return True

    def name(self):
        return self._name


class TestScreenManagerHandover(unittest.TestCase):
    def setUp(self):
        self.overlay = MagicMock()
        self.debug = MagicMock()
        self.estimator = GazeEstimator()
        self.screens = [FakeScreen(1920, 1080, "Primary"), FakeScreen(3840, 2160, "Secondary")]
        self.manager = ScreenManager(
            overlay=self.overlay,
            debug_widget=self.debug,
            gaze_estimator=self.estimator,
            screens_override=self.screens,
        )

    def test_screen_count_and_handover_to_secondary(self):
        self.assertEqual(self.manager.screen_count, 2)
        self.assertTrue(self.manager.handover_to_screen(1))
        self.assertEqual(self.manager.current_index, 1)
        self.overlay.setGeometry.assert_called()
        geometry = self.overlay.setGeometry.call_args[0][0]
        self.assertEqual(geometry.width(), 3840)
        self.assertEqual(geometry.height(), 2160)
        self.assertEqual(self.estimator.get_target_screen(), (3840, 2160))

    def test_calibration_bounds_follow_screen_resolution(self):
        self.estimator.set_target_screen(1920, 1080)
        self.assertEqual(self.estimator.get_target_screen(), (1920, 1080))
        self.manager.handover_to_screen(1)
        self.assertEqual(self.estimator.get_target_screen(), (3840, 2160))
        self.assertAlmostEqual(self.estimator.target_screen_aspect, 3840 / 2160, places=5)

    def test_invalid_screen_index_is_rejected(self):
        self.assertFalse(self.manager.handover_to_screen(7))
        self.assertFalse(self.manager.handover_to_screen(-1))
        self.assertEqual(self.manager.current_index, 0)

    def test_bezel_crossing_requires_400ms_and_direction(self):
        self.assertFalse(self.manager.update_head_yaw(22.0, timestamp=10.0))
        self.assertFalse(self.manager.update_head_yaw(22.0, timestamp=10.2))
        self.assertTrue(self.manager.update_head_yaw(22.0, timestamp=10.5))
        self.assertEqual(self.manager.current_index, 1)

    def test_cycle_wraps_between_screens(self):
        self.assertTrue(self.manager.cycle_next_screen())
        self.assertEqual(self.manager.current_index, 1)
        self.assertTrue(self.manager.cycle_next_screen())
        self.assertEqual(self.manager.current_index, 0)


class TestCrossPlatformBuildCommand(unittest.TestCase):
    def test_command_bundles_assets_screen_manager_and_pynput(self):
        import build_app

        cmd = build_app.build_command()
        joined = " ".join(cmd)
        self.assertIn("eyede/assets", joined)
        self.assertIn("eyede.core.screen_manager", joined)
        self.assertIn("pynput.", joined)
        self.assertIn("--windowed", cmd)
        self.assertIn("--onedir", cmd)


class TestOverlayScreenButton(unittest.TestCase):
    def test_screen_button_appears_with_multiple_monitors(self):
        overlay = OverlayWindow(start_in_mode_selector=False)
        overlay.resize(1920, 1080)
        overlay.set_screen_info(1, 2)
        overlay._update_header_exit_rect()
        self.assertTrue(overlay.header_screen_rect.isValid())
        self.assertEqual(overlay.screen_count, 2)
        self.assertEqual(overlay.screen_index, 1)
        overlay.close()


if __name__ == "__main__":
    unittest.main()
