"""FreeLook safety: top reach, reliable clicks and flicker-free lens capture."""

import os
import sys
import time
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QRectF
from PyQt6.QtWidgets import QApplication

from ideye.ui.overlay_window import OverlayWindow

_APP = QApplication.instance() or QApplication(sys.argv if hasattr(sys, "argv") else [])


class TestFreeLookSafety(unittest.TestCase):
    def setUp(self):
        self.overlay = OverlayWindow(start_in_mode_selector=False)
        self.overlay.mouse_controller = MagicMock()
        self.overlay.current_context_mode_id = "sniper"
        self.overlay.current_node_id = "ROOT"
        self.overlay.mar_threshold = 0.45
        self.overlay.current_mar = 0.0
        self.overlay._freelook_last_pos = (300, 400)
        self.overlay._jaw_lock_pos = None
        self.overlay._jaw_locked = False
        self.overlay._mouth_active = False
        self.overlay._hold_started = False
        self.overlay._last_freelook_click_ts = 0.0

    def tearDown(self):
        self.overlay.close()
        _APP.processEvents()

    def test_calibration_threshold_updates_freelook_trigger(self):
        self.overlay.set_mar_threshold(0.36)
        self.assertEqual(self.overlay.mar_threshold, 0.36)
        for _ in range(40):
            self.overlay.on_mar_updated(None, 0.20)
        self.overlay._freelook_last_pos = (300, 400)
        self.overlay.on_gaze_updated(0.8, 0.8)
        self.overlay.on_mar_updated(None, 0.32)
        self.assertTrue(self.overlay._mouth_active)
        self.overlay._mouth_start = time.time() - 0.05
        self.overlay.on_mar_updated(None, 0.22)
        self.overlay.mouse_controller.left_click.assert_called_once_with(
            *self.overlay._freelook_last_pos
        )

    def test_high_resting_mouth_still_allows_click(self):
        for _ in range(40):
            self.overlay.on_mar_updated(None, 0.25)
        self.assertFalse(self.overlay._jaw_locked)
        self.overlay._freelook_last_pos = (300, 400)
        self.overlay.on_gaze_updated(0.8, 0.8)
        self.overlay.mouse_controller.move_direct.assert_called()
        self.overlay.on_mar_updated(None, 0.40)
        self.assertTrue(self.overlay._mouth_active)
        self.overlay._mouth_start = time.time() - 0.05
        self.overlay.on_mar_updated(None, 0.28)
        self.overlay.mouse_controller.left_click.assert_called_once_with(
            *self.overlay._freelook_last_pos
        )

    def test_comfortable_upward_gaze_reaches_command_bar(self):
        y = self.overlay._freelook_screen_coords(0.5, 0.10, 1920, 1080)[1]
        self.assertLessEqual(y, 48, "FreeLook must reach the 38px header plus its top margin")
        self.assertEqual(self.overlay._freelook_screen_coords(0.5, 0.04, 1920, 1080)[1], 0)

    def test_freelook_header_hit_uses_mapped_cursor_coordinates(self):
        self.overlay.resize(1920, 1080)
        self.overlay.header_exit_rect = QRectF(100.0, 10.0, 80.0, 38.0)
        for attr in (
            "header_help_rect",
            "header_mode_rect",
            "header_lang_rect",
            "header_screen_rect",
            "_sniper_action_pill_rect",
            "_gaming_toggle_rect",
        ):
            setattr(self.overlay, attr, QRectF())
        with patch.object(self.overlay, "_get_screen_size", return_value=(1920, 1080)), patch.object(
            self.overlay, "_freelook_screen_coords", return_value=(140, 29)
        ) as mapped:
            self.overlay.on_gaze_updated(0.5, 0.10)
        mapped.assert_called()
        self.assertTrue(self.overlay.hovered_header_exit)

    def test_relaxed_mouth_does_not_lock_pointer(self):
        self.overlay.current_mar = 0.25
        self.overlay.on_gaze_updated(0.8, 0.8)
        self.assertFalse(self.overlay._jaw_locked)

    def test_intentional_mouth_click_fires_at_locked_pointer(self):
        self.overlay.current_mar = 0.40
        self.overlay._freelook_last_pos = (300, 400)
        self.overlay.on_gaze_updated(0.8, 0.8)
        self.assertTrue(self.overlay._jaw_locked)
        self.assertEqual(self.overlay._jaw_lock_pos, (300, 400))

        self.overlay._mouth_active = False
        self.overlay._hold_started = False
        self.overlay._last_freelook_click_ts = 0.0
        self.overlay.current_mar = 0.40
        self.overlay._update_freelook_mouth(0.40)
        self.assertTrue(self.overlay._mouth_active)
        self.overlay._mouth_start = time.time() - 0.05
        self.overlay._update_freelook_mouth(0.28)
        self.overlay.mouse_controller.left_click.assert_called_once_with(300, 400)

    def test_confirmed_mouth_gesture_is_a_click_fallback(self):
        self.overlay._mouth_active = False
        self.overlay._hold_started = False
        self.overlay._last_freelook_click_ts = 0.0
        self.overlay._jaw_lock_pos = None
        self.overlay.on_gesture_triggered("MOUTH_CLICK")
        self.overlay.mouse_controller.left_click.assert_called_once_with(300, 400)

    def test_lens_capture_does_not_toggle_window_opacity(self):
        fake_screen = MagicMock()
        fake_screen.grabWindow.return_value = None
        self.overlay.sniper_lens.activate(500.0, 500.0)
        self.overlay._lens_capture_target = None
        self.overlay.setWindowOpacity = MagicMock()
        with patch(
            "ideye.ui.overlay_window.QGuiApplication.primaryScreen",
            return_value=fake_screen,
        ):
            self.overlay._capture_sniper_lens()
        self.overlay.setWindowOpacity.assert_not_called()
        fake_screen.grabWindow.assert_called_once()

    def test_brow_raise_does_not_open_lens_in_freelook(self):
        self.overlay.on_gesture_triggered("BROW_RAISE")
        self.assertFalse(self.overlay.sniper_lens.active)

    def test_jaw_lock_watchdog_releases_stuck_pointer(self):
        self.overlay._jaw_locked = True
        self.overlay._jaw_lock_pos = (100, 100)
        self.overlay._jaw_lock_since = time.time() - 5.0
        self.overlay.current_mar = 0.20
        self.overlay.on_gaze_updated(0.5, 0.5)
        self.assertFalse(self.overlay._jaw_locked)
        self.assertIsNone(self.overlay._jaw_lock_pos)
        self.overlay.mouse_controller.move_direct.assert_called()

    def test_face_loss_recenters_freelook_pointer(self):
        self.overlay._freelook_last_pos = (100, 100)
        self.overlay.current_gaze = (1.0, 0.0)
        self.overlay._jaw_locked = True
        self.overlay._jaw_lock_pos = (100, 100)
        self.overlay.reset_freelook_pointer()
        self.assertEqual(self.overlay.current_gaze, (0.5, 0.5))
        self.assertFalse(self.overlay._jaw_locked)
        self.overlay.mouse_controller.move_direct.assert_called()

    def test_nan_gaze_does_not_crash_or_move_pointer(self):
        self.overlay.on_gaze_updated(float("nan"), float("inf"))
        self.overlay.mouse_controller.move_direct.assert_not_called()


if __name__ == "__main__":
    unittest.main()
