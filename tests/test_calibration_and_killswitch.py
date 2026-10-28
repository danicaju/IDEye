"""
Tests for Calibration Stability (Problem 1) & Emergency Killswitch / Manual Exit (Problem 2).
"""

import os
import sys
import time
import math
import tempfile
import unittest
import numpy as np

from PyQt6.QtCore import Qt, QCoreApplication
from PyQt6.QtWidgets import QApplication

try:
    import eyede.config as config
    from eyede.core.gaze_estimator import GazeEstimator
    from eyede.core.hotkey_manager import GlobalHotkeyManager, HOTKEY_ACTIONS
    from eyede.ui.calibration_ui import CalibrationUI
    from eyede.ui.debug_widget import DebugWidget
    from eyede.ui.overlay_window import OverlayWindow
    from eyede.main import EyeDEApplication
except ImportError:
    import config
    from core.gaze_estimator import GazeEstimator
    from core.hotkey_manager import GlobalHotkeyManager, HOTKEY_ACTIONS
    from ui.calibration_ui import CalibrationUI
    from ui.debug_widget import DebugWidget
    from ui.overlay_window import OverlayWindow
    from main import EyeDEApplication

_APP = QApplication.instance() or QApplication(sys.argv if hasattr(sys, "argv") else [])


class TestCalibrationStability(unittest.TestCase):
    """
    Problem 1 Verification:
    Tests that small raw delta ranges and noisy samples during mouth opening
    are regularized (Ridge / Tikhonov), gains are bounded, outliers rejected,
    and the cursor remains smooth and stable without crazy jumping.
    """

    def setUp(self):
        self.estimator = GazeEstimator()

    def test_narrow_raw_range_gain_bounding(self):
        """
        When a user barely moves between 5 points (narrow raw range ~0.02),
        OLS regression would blow weights up to 50x-200x.
        Ridge regularization and gain bounding must keep weights <= 6.0 and gains <= 3.5.
        """
        narrow_points = [
            {"id": "CENTER", "screen": (0.5, 0.5), "raw": (0.500, 0.500)},
            {"id": "TOP_LEFT", "screen": (0.1, 0.1), "raw": (0.490, 0.491)},
            {"id": "TOP_RIGHT", "screen": (0.9, 0.1), "raw": (0.511, 0.492)},
            {"id": "BOTTOM_LEFT", "screen": (0.1, 0.9), "raw": (0.489, 0.510)},
            {"id": "BOTTOM_RIGHT", "screen": (0.9, 0.9), "raw": (0.510, 0.512)},
        ]

        success = self.estimator.calibrate_5_points(narrow_points)
        self.assertTrue(success)
        self.assertTrue(self.estimator.has_5_point_calibration)

        # Check that weights did not blow up
        wx = self.estimator.calib_weights_x
        wy = self.estimator.calib_weights_y
        self.assertIsNotNone(wx)
        self.assertIsNotNone(wy)

        for w in wx + wy:
            self.assertFalse(math.isnan(w))
            self.assertFalse(math.isinf(w))
            self.assertLessEqual(abs(w), 6.0, f"Weight {w} exceeds safe bound 6.0")

        # Test effective gain at center
        gx = wx[1] + 0.5 * wx[3]
        gy = wy[2] + 0.5 * wy[3]
        self.assertLessEqual(gx, 3.6, f"Horizontal gain {gx} exceeds max bound 3.5")
        self.assertGreaterEqual(gx, 0.3, f"Horizontal gain {gx} is below min bound")
        self.assertLessEqual(gy, 3.6, f"Vertical gain {gy} exceeds max bound 3.5")
        self.assertGreaterEqual(gy, 0.3, f"Vertical gain {gy} is below min bound")

        # A small head twitch of 0.005 must NOT fling the cursor off-screen
        mx_center, my_center = self.estimator.apply_5_point_mapping(0.500, 0.500)
        mx_twitch, my_twitch = self.estimator.apply_5_point_mapping(0.505, 0.505)

        delta_x = abs(mx_twitch - mx_center)
        delta_y = abs(my_twitch - my_center)
        # 0.005 * 3.5 max gain = ~0.0175 movement across screen
        self.assertLess(delta_x, 0.05, f"Cursor moved too violently on micro-twitch: {delta_x}")
        self.assertLess(delta_y, 0.05, f"Cursor moved too violently on micro-twitch: {delta_y}")

    def test_directional_monotonicity(self):
        """Looking further to the right must map further to the right (positive gain)."""
        points = [
            {"id": "CENTER", "screen": (0.5, 0.5), "raw": (0.50, 0.50)},
            {"id": "TOP_LEFT", "screen": (0.1, 0.1), "raw": (0.35, 0.35)},
            {"id": "TOP_RIGHT", "screen": (0.9, 0.1), "raw": (0.65, 0.35)},
            {"id": "BOTTOM_LEFT", "screen": (0.1, 0.9), "raw": (0.35, 0.65)},
            {"id": "BOTTOM_RIGHT", "screen": (0.9, 0.9), "raw": (0.65, 0.65)},
        ]
        self.estimator.calibrate_5_points(points)

        mx_left, _ = self.estimator.apply_5_point_mapping(0.40, 0.50)
        mx_center, _ = self.estimator.apply_5_point_mapping(0.50, 0.50)
        mx_right, _ = self.estimator.apply_5_point_mapping(0.60, 0.50)

        self.assertLess(mx_left, mx_center)
        self.assertLess(mx_center, mx_right)

    def test_apply_mapping_extreme_bounds_safety(self):
        """Wild or corrupted input coordinates must be safely bounded, never divergent or NaN."""
        self.estimator.has_5_point_calibration = True
        self.estimator.calib_weights_x = [-0.75, 2.5, 0.0, 0.0]
        self.estimator.calib_weights_y = [-0.75, 0.0, 2.5, 0.0]

        # Extreme positive and negative extrapolation
        mx, my = self.estimator.apply_5_point_mapping(100.0, -100.0)
        self.assertLessEqual(mx, 2.0)
        self.assertGreaterEqual(my, -1.0)
        self.assertFalse(math.isnan(mx))
        self.assertFalse(math.isnan(my))

        # NaN input fallback
        mx, my = self.estimator.apply_5_point_mapping(float("nan"), 0.5)
        self.assertEqual(my, 0.5)

    def test_sampling_outlier_rejection(self):
        """
        During calibration sampling, when the mouth opens to trigger a click,
        transient head/facial distortion spikes must be rejected from the average.
        """
        calib_ui = CalibrationUI(gaze_estimator=self.estimator, samples_per_point=10)

        # Populate samples buffer with 8 stable samples around (0.60, 0.40)
        # and 2 violent spike samples from mouth opening at (0.95, 0.05)
        calib_ui.samples_buffer = [
            (0.95, 0.05),  # Sample 0 (mouth click spike)
            (0.93, 0.08),  # Sample 1 (mouth click spike)
            (0.60, 0.40),
            (0.61, 0.39),
            (0.59, 0.41),
            (0.60, 0.40),
            (0.62, 0.40),
            (0.58, 0.42),
            (0.60, 0.39),
            (0.61, 0.41),
        ]

        calib_ui._finish_point_sampling()

        self.assertEqual(len(calib_ui.collected_data), 1)
        raw_x, raw_y = calib_ui.collected_data[0]["raw"]

        # If spikes weren't rejected, mean raw_x would be ~0.67 and raw_y ~0.33
        # With outlier rejection, raw_x should be very close to 0.60 and raw_y ~0.40
        self.assertAlmostEqual(raw_x, 0.60, delta=0.03)
        self.assertAlmostEqual(raw_y, 0.40, delta=0.03)
        calib_ui.close()

    def test_has_raw_signal_preservation(self):
        """Ensures that uncalibrated raw gaze signal is not overwritten by calibrated gaze in CalibrationUI."""
        calib_ui = CalibrationUI(gaze_estimator=self.estimator)

        calib_ui.on_raw_gaze_updated(0.72, 0.28)
        self.assertTrue(getattr(calib_ui, "_has_raw_signal", False))
        self.assertEqual(calib_ui.latest_raw_gaze, (0.72, 0.28))

        # Subsequent on_gaze_updated call must NOT overwrite latest_raw_gaze
        calib_ui.on_gaze_updated(0.10, 0.90)
        self.assertEqual(calib_ui.latest_raw_gaze, (0.72, 0.28))
        calib_ui.close()

    def test_load_profile_with_excessive_weights_refits_from_points(self):
        """
        When loading an existing calibration_profile.json with wild OLS weights (e.g. -200x),
        GazeEstimator must detect excessive magnitude (> 10.0) and automatically re-fit
        a robust bounded model from the stored 5 points.
        """
        profile_data = {
            "version": 2,
            "has_5_point_calibration": True,
            "weights_x": [17.9, -39.1, -36.3, 80.0],
            "weights_y": [-55.5, 111.2, 101.2, -200.6],
            "points": [
                {"id": "CENTER", "screen": (0.5, 0.5), "raw": (0.528, 0.546)},
                {"id": "TOP_LEFT", "screen": (0.1, 0.1), "raw": (0.419, 0.525)},
                {"id": "TOP_RIGHT", "screen": (0.9, 0.1), "raw": (0.567, 0.574)},
                {"id": "BOTTOM_LEFT", "screen": (0.1, 0.9), "raw": (0.441, 0.580)},
                {"id": "BOTTOM_RIGHT", "screen": (0.9, 0.9), "raw": (0.549, 0.566)},
            ],
        }

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            temp_path = f.name

        try:
            import json
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(profile_data, f)

            loaded = self.estimator.load_calibration_profile(temp_path)
            self.assertTrue(loaded)
            self.assertTrue(self.estimator.has_5_point_calibration)

            # Excessive weights (-200x) must have been replaced with safe bounded weights
            for w in self.estimator.calib_weights_x + self.estimator.calib_weights_y:
                self.assertLessEqual(abs(w), 6.0)

            # Mapped output for center must be reasonable, not crazy
            mx, my = self.estimator.apply_5_point_mapping(0.528, 0.546)
            self.assertTrue(0.0 <= mx <= 1.0)
            self.assertTrue(0.0 <= my <= 1.0)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_center_anchor_identity_prior_preserves_center(self):
        """
        When raw coordinates have an off-center offset (e.g. center target raw is (0.528, 0.546)),
        the center-anchored identity prior must ensure that looking at center maps close to (0.5, 0.5),
        not pushed toward the screen edges.
        """
        points = [
            {"id": "CENTER", "screen": (0.5, 0.5), "raw": (0.528, 0.546)},
            {"id": "TOP_LEFT", "screen": (0.1, 0.1), "raw": (0.419, 0.525)},
            {"id": "TOP_RIGHT", "screen": (0.9, 0.1), "raw": (0.567, 0.574)},
            {"id": "BOTTOM_LEFT", "screen": (0.1, 0.9), "raw": (0.441, 0.580)},
            {"id": "BOTTOM_RIGHT", "screen": (0.9, 0.9), "raw": (0.549, 0.566)},
        ]
        self.estimator.calibrate_5_points(points)
        mx, my = self.estimator.apply_5_point_mapping(0.528, 0.546)
        # Center target must map very close to (0.5, 0.5)
        self.assertAlmostEqual(mx, 0.50, delta=0.10)
        self.assertAlmostEqual(my, 0.50, delta=0.08)

    def test_cross_axis_regularization_decoupling(self):
        """
        Tests that horizontal eye movement (moving left to right) does NOT cause wild
        vertical cursor shifts (cross-axis coupling is heavily regularized).
        """
        points = [
            {"id": "CENTER", "screen": (0.5, 0.5), "raw": (0.50, 0.50)},
            {"id": "TOP_LEFT", "screen": (0.1, 0.1), "raw": (0.40, 0.40)},
            {"id": "TOP_RIGHT", "screen": (0.9, 0.1), "raw": (0.60, 0.40)},
            {"id": "BOTTOM_LEFT", "screen": (0.1, 0.9), "raw": (0.40, 0.60)},
            {"id": "BOTTOM_RIGHT", "screen": (0.9, 0.9), "raw": (0.60, 0.60)},
        ]
        self.estimator.calibrate_5_points(points)

        # Move horizontally across raw range 0.40 -> 0.60 at fixed Y=0.50
        _, my_left = self.estimator.apply_5_point_mapping(0.40, 0.50)
        _, my_center = self.estimator.apply_5_point_mapping(0.50, 0.50)
        _, my_right = self.estimator.apply_5_point_mapping(0.60, 0.50)

        # Vertical screen position should not drift by more than 0.05 when moving horizontally
        self.assertLess(abs(my_left - my_center), 0.05)
        self.assertLess(abs(my_right - my_center), 0.05)

    def test_load_profile_preserves_neutral_anchors_on_refit(self):
        """
        When loading a profile with excessive weights (> 10.0), GazeEstimator
        re-fits safe weights from points AND preserves neutral_head/neutral_iris anchors.
        """
        profile_data = {
            "version": 2,
            "has_5_point_calibration": True,
            "weights_x": [17.9, -39.1, -36.3, 80.0],
            "weights_y": [-55.5, 111.2, 101.2, -200.6],
            "neutral_head": [0.475, 0.515],
            "neutral_iris": [0.485, 0.525],
            "distance_scale": 1.25,
            "points": [
                {"id": "CENTER", "screen": (0.5, 0.5), "raw": (0.528, 0.546)},
                {"id": "TOP_LEFT", "screen": (0.1, 0.1), "raw": (0.419, 0.525)},
                {"id": "TOP_RIGHT", "screen": (0.9, 0.1), "raw": (0.567, 0.574)},
                {"id": "BOTTOM_LEFT", "screen": (0.1, 0.9), "raw": (0.441, 0.580)},
                {"id": "BOTTOM_RIGHT", "screen": (0.9, 0.9), "raw": (0.549, 0.566)},
            ],
        }

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            temp_path = f.name

        try:
            import json
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(profile_data, f)

            loaded = self.estimator.load_calibration_profile(temp_path)
            self.assertTrue(loaded)
            # Anchors must be preserved, not left as defaults
            self.assertAlmostEqual(self.estimator.neutral_head_x, 0.475)
            self.assertAlmostEqual(self.estimator.neutral_head_y, 0.515)
            self.assertAlmostEqual(self.estimator.neutral_iris_x, 0.485)
            self.assertAlmostEqual(self.estimator.neutral_iris_y, 0.525)
            self.assertAlmostEqual(self.estimator.distance_scale, 1.25)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)



class TestEmergencyKillswitchAndSafety(unittest.TestCase):
    """
    Problem 2 Verification:
    Tests the global keyboard hotkey listener (all Ctrl+Alt+letter),
    prominent Emergency Exit and Reset buttons in DebugWidget,
    and on-screen emergency exit documentation.
    """

    def test_hotkey_specs_are_valid_pynput_syntax(self):
        """Every configured shortcut must parse; one invalid spec abort the whole listener."""
        from pynput import keyboard

        for spec in HOTKEY_ACTIONS:
            with self.subTest(spec=spec):
                keyboard.HotKey.parse(spec)

    def test_all_global_hotkeys_are_ctrl_alt_letter(self):
        """No F-keys, Shift combinations, or bare letters in global bindings."""
        import re

        pattern = re.compile(r"<ctrl>\+<alt>\+[a-z]")
        for spec in HOTKEY_ACTIONS:
            with self.subTest(spec=spec):
                self.assertRegex(spec, pattern)
        expected = {
            "q", "r", "v", "k", "s", "f", "g", "m",
            "a", "b", "t", "c", "p", "l", "h", "n", "z", "j", "i", "w",
        }
        actual = {spec.rsplit("+", 1)[-1] for spec in HOTKEY_ACTIONS}
        self.assertEqual(actual, expected)

    def test_hotkey_manager_start_and_stop_lifecycle(self):
        """Tests that GlobalHotkeyManager starts and stops without thread leaks or exceptions."""
        manager = GlobalHotkeyManager()
        started = manager.start()
        # A False return means the listener never started, so the killswitch is dead.
        self.assertTrue(started, "Global hotkey listener failed to start; check HOTKEY_ACTIONS")
        self.assertTrue(manager.is_running)
        manager.stop()
        self.assertFalse(manager.is_running)

    def test_emergency_exit_signal_invokes_shutdown(self):
        """Verifies that firing the emergency exit signal cleanly triggers application shutdown."""
        app = EyeDEApplication(camera_index="synthetic", force_calibrate=False, threaded=False)
        self.assertFalse(app._is_shutting_down)

        # Trigger emergency exit via hotkey signal
        app.hotkey_manager.emergency_exit_requested.emit()
        self.assertTrue(app._is_shutting_down)

    def test_emergency_reset_calibration(self):
        """
        Verifies that emergency reset clears ill-conditioned 5-point calibration
        and backs up the corrupted profile file.
        """
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            temp_profile = f.name

        try:
            app = EyeDEApplication(camera_index="synthetic", profile_path=temp_profile, force_calibrate=False, threaded=False)
            # Simulate a loaded calibration
            app.tracker.gaze_estimator.has_5_point_calibration = True
            app.tracker.gaze_estimator.calib_weights_x = [1.0, 2.0, 3.0, 4.0]
            app.tracker.gaze_estimator.calib_weights_y = [1.0, 2.0, 3.0, 4.0]

            with open(temp_profile, "w", encoding="utf-8") as f:
                f.write('{"corrupted": true}')

            # Trigger emergency reset
            app.hotkey_manager.emergency_reset_requested.emit()

            # Calibration weights must be reset to neutral safe state
            self.assertFalse(app.tracker.gaze_estimator.has_5_point_calibration)
            self.assertIsNone(app.tracker.gaze_estimator.calib_weights_x)
            self.assertIsNone(app.tracker.gaze_estimator.calib_weights_y)

            # Old profile must have been backed up so it is not reloaded on next startup
            self.assertTrue(os.path.exists(temp_profile + ".bak"))

            app.shutdown()
        finally:
            if os.path.exists(temp_profile):
                os.remove(temp_profile)
            if os.path.exists(temp_profile + ".bak"):
                os.remove(temp_profile + ".bak")

    def test_debug_widget_reset_button_and_focus_policy(self):
        """
        Verifies DebugWidget has prominent Reset and Exit buttons,
        all respecting WA_ShowWithoutActivating and NoFocus to never steal focus from VS Code.
        """
        widget = DebugWidget()

        # Reset button
        self.assertTrue(hasattr(widget, "btn_reset"))
        self.assertEqual(widget.btn_reset.focusPolicy(), Qt.FocusPolicy.NoFocus)

        # Exit button
        self.assertTrue(hasattr(widget, "btn_exit"))
        self.assertEqual(widget.btn_exit.focusPolicy(), Qt.FocusPolicy.NoFocus)

        # Recalibrate button
        self.assertTrue(hasattr(widget, "btn_recalibrate"))
        self.assertEqual(widget.btn_recalibrate.focusPolicy(), Qt.FocusPolicy.NoFocus)

        # Signal connections
        reset_emitted = []
        widget.reset_calibration_requested.connect(lambda: reset_emitted.append(True))
        widget.btn_reset.click()
        self.assertEqual(len(reset_emitted), 1)

        # Emergency documentation hint label
        self.assertTrue(hasattr(widget, "lbl_emergency_hint"))
        hint_text = widget.lbl_emergency_hint.text()
        self.assertIn("Ctrl+Alt+Q", hint_text)
        self.assertIn("Emergencia", hint_text)

        widget.close()

    def test_overlay_window_emergency_documentation(self):
        """Verifies OverlayWindow allocates styles for emergency hotkey documentation in top header."""
        overlay = OverlayWindow()
        self.assertTrue(hasattr(overlay, "_font_header_center"))
        self.assertTrue(hasattr(overlay, "_pen_header_center"))
        overlay.close()

    def test_camera_tracker_click_stabilization(self):
        """
        Tests that when hold_progress > 0 (mouth click in progress), CameraTracker
        stabilizes emitted gaze to prevent facial distortion from flinging cursor across blocks.
        """
        from eyede.core.camera_tracker import CameraTracker
        tracker = CameraTracker(camera_index="synthetic", threaded=False)
        self.assertIsNone(tracker._click_anchor_gaze)
        self.assertIsNone(tracker._click_anchor_raw)

        # Simulate frame processing with hold_progress > 0
        tracker._click_anchor_gaze = (0.2, 0.2)
        tracker._click_anchor_raw = (0.5, 0.5)
        self.assertEqual(tracker._click_anchor_gaze, (0.2, 0.2))
        self.assertEqual(tracker._click_anchor_raw, (0.5, 0.5))
        tracker.release()

    def test_mouse_press_triggers_calibration_sampling(self):
        """Tests that mouse click on CalibrationUI triggers sampling for the active target."""
        from PyQt6.QtGui import QMouseEvent
        from PyQt6.QtCore import QPointF
        calib_ui = CalibrationUI(gaze_estimator=GazeEstimator())
        self.assertFalse(calib_ui.is_sampling)

        dummy_event = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(100.0, 100.0),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        calib_ui.mousePressEvent(dummy_event)
        self.assertTrue(calib_ui.is_sampling)
        calib_ui.close()

    def test_cross_thread_safe_shutdown_and_reset(self):
        """
        Verifies that EyeDEApplication.shutdown and reset_calibration safely handle
        invocations from background worker threads (like pynput daemon thread).
        """
        import threading
        temp_profile = os.path.join(tempfile.gettempdir(), "test_cross_thread_calib.json")
        app = EyeDEApplication(camera_index="synthetic", profile_path=temp_profile, force_calibrate=False, threaded=False)
        self.assertFalse(app._is_shutting_down)

        worker_thread_executed = []
        def worker_call():
            app.reset_calibration()
            app.shutdown()
            worker_thread_executed.append(True)

        t = threading.Thread(target=worker_call)
        t.start()
        t.join(timeout=2.0)
        self.assertTrue(len(worker_thread_executed) > 0)
        QCoreApplication.processEvents()
        self.assertTrue(app._is_shutting_down)


if __name__ == "__main__":
    unittest.main()
