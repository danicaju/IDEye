"""Phase 8.3: multi-monitor handover and screen-aware calibration bounds."""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

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

    def test_bezel_cooldown_uses_the_supplied_clock(self):
        self.assertFalse(self.manager.update_head_yaw(22.0, timestamp=10.0))
        self.assertFalse(self.manager.update_head_yaw(22.0, timestamp=10.2))
        self.assertTrue(self.manager.update_head_yaw(22.0, timestamp=10.5))
        self.assertEqual(self.manager.current_index, 1)
        # Look left to return; the 1 s cooldown must still block at t=11.0.
        self.assertFalse(self.manager.update_head_yaw(-22.0, timestamp=10.6))
        self.assertFalse(self.manager.update_head_yaw(-22.0, timestamp=11.0))
        self.assertTrue(self.manager.update_head_yaw(-22.0, timestamp=11.6))
        self.assertEqual(self.manager.current_index, 0)

    def test_cycle_wraps_between_screens(self):
        self.assertTrue(self.manager.cycle_next_screen())
        self.assertEqual(self.manager.current_index, 1)
        self.assertTrue(self.manager.cycle_next_screen())
        self.assertEqual(self.manager.current_index, 0)


class TestGazeYawAndAspect(unittest.TestCase):
    def test_face_loss_resets_head_yaw(self):
        estimator = GazeEstimator()
        estimator.last_head_yaw = 28.0
        estimator.estimate(None)
        self.assertEqual(estimator.last_head_yaw, 0.0)
        estimator.last_head_yaw = 28.0
        estimator.estimate([])
        self.assertEqual(estimator.last_head_yaw, 0.0)

    def test_mirror_sign_inverts_head_yaw(self):
        landmarks = [(0.5, 0.5)] * 468
        landmarks[234] = (0.4, 0.5)
        landmarks[454] = (0.6, 0.5)
        landmarks[1] = (0.55, 0.5)
        mirrored = GazeEstimator(mirror=True)
        unmirrored = GazeEstimator(mirror=False)
        self.assertGreater(mirrored._extract_head_yaw(landmarks), 20.0)
        self.assertLess(unmirrored._extract_head_yaw(landmarks), -20.0)

    def test_aspect_correction_scales_horizontal_gaze(self):
        estimator = GazeEstimator()
        estimator.set_target_screen(1920, 1080)
        estimator.calibration_screen_aspect = 16.0 / 9.0
        estimator.has_5_point_calibration = True
        estimator.calib_weights_x = [0.0, 1.0, 0.0, 0.0]
        estimator.calib_weights_y = [0.0, 0.0, 1.0, 0.0]
        estimator.set_target_screen(2520, 1080)  # 21:9
        x, y = estimator.apply_5_point_mapping(0.75, 0.5)
        self.assertAlmostEqual(x, 0.5 + 0.25 * (16.0 / 21.0), places=5)
        self.assertAlmostEqual(y, 0.5, places=5)


class TestCrossPlatformBuildCommand(unittest.TestCase):
    def test_command_bundles_assets_screen_manager_and_pynput(self):
        import build_app

        cmd = build_app.build_command()
        joined = " ".join(cmd)
        self.assertIn("eyede/assets", joined)
        self.assertIn("eyede.core.screen_manager", joined)
        self.assertIn("pynput.", joined)
        self.assertIn("--onedir", cmd)
        if build_app.IS_WINDOWS or build_app.IS_MACOS:
            self.assertIn("--windowed", cmd)

    def test_defaults_do_not_bundle_live_root_user_data(self):
        import build_app

        joined = " ".join(build_app.build_command())
        self.assertNotIn(os.path.join(build_app.ROOT_DIR, "user_settings.json"), joined)
        self.assertNotIn(os.path.join(build_app.ROOT_DIR, "custom_macros.json"), joined)
        self.assertNotIn(os.path.join(build_app.ROOT_DIR, "calibration_profile.json"), joined)
        self.assertIn(os.path.join(build_app.DEFAULTS_DIR, "user_settings.json"), joined)

    def test_linux_command_omits_windowed_flag(self):
        import build_app

        with patch.object(build_app, "IS_WINDOWS", False), \
                patch.object(build_app, "IS_MACOS", False), \
                patch.object(build_app, "IS_LINUX", True), \
                patch.object(build_app, "DATA_SEP", ":"):
            cmd = build_app.build_command()
        self.assertNotIn("--windowed", cmd)
        self.assertIn("--hidden-import=pynput.keyboard._xorg", cmd)


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

    def test_screen_index_is_clamped(self):
        overlay = OverlayWindow(start_in_mode_selector=False)
        overlay.resize(1920, 1080)
        overlay.set_screen_info(9, 2)
        self.assertEqual(overlay.screen_index, 1)
        overlay.set_screen_info(-4, 2)
        self.assertEqual(overlay.screen_index, 0)
        overlay.close()

    def test_screen_button_is_hidden_in_sniper_mode(self):
        overlay = OverlayWindow(start_in_mode_selector=False)
        overlay.resize(1920, 1080)
        overlay.set_screen_info(0, 2)
        overlay.current_context_mode_id = "sniper"
        overlay._update_header_exit_rect()
        self.assertFalse(overlay.header_screen_rect.isValid())
        self.assertFalse(overlay.hovered_header_screen)
        overlay.close()


if __name__ == "__main__":
    unittest.main()
