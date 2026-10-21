"""Phase 8.1: persistent settings and automatic biometric MAR calibration."""

import json
import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from eyede.core.settings_manager import SettingsManager
from eyede.core.gaze_estimator import GazeEstimator
from eyede.ui.calibration_ui import CalibrationUI, compute_auto_mar_threshold
from eyede.ui.debug_widget import DebugWidget

_APP = QApplication.instance() or QApplication(sys.argv if hasattr(sys, "argv") else [])


class TestSettingsManager(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmpdir.name, "user_settings.json")

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_round_trip_persists_exact_values(self):
        manager = SettingsManager(self.path)
        manager.set("sensitivity_x", 4.2)
        manager.set("sensitivity_y", 5.1)
        manager.set("tracking_mode", "PURE_IRIS")
        manager.set("sound_enabled", False)
        manager.set("mar_threshold", 0.36)
        self.assertTrue(manager.save_now())

        loaded = SettingsManager(self.path)
        self.assertAlmostEqual(loaded.get("sensitivity_x"), 4.2)
        self.assertAlmostEqual(loaded.get("sensitivity_y"), 5.1)
        self.assertEqual(loaded.get("tracking_mode"), "PURE_IRIS")
        self.assertFalse(loaded.get("sound_enabled"))
        self.assertAlmostEqual(loaded.get("mar_threshold"), 0.36)
        self.assertFalse(os.path.exists(self.path + ".tmp"))

    def test_corrupt_json_falls_back_to_defaults(self):
        with open(self.path, "w", encoding="utf-8") as fh:
            fh.write("{ this is not json")
        manager = SettingsManager(self.path)
        defaults = manager.as_dict()
        self.assertIn("tracking_mode", defaults)
        self.assertIn("mar_threshold", defaults)
        self.assertTrue(0.25 <= defaults["mar_threshold"] <= 0.70)

    def test_partial_json_keeps_defaults_for_missing_keys(self):
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump({"sensitivity_x": 3.3}, fh)
        manager = SettingsManager(self.path)
        self.assertAlmostEqual(manager.get("sensitivity_x"), 3.3)
        self.assertIn("sound_enabled", manager.as_dict())

    def test_reset_restores_factory_defaults(self):
        manager = SettingsManager(self.path)
        manager.set("sensitivity_x", 8.0)
        manager.set("mar_threshold", 0.65)
        manager.reset_to_defaults()
        loaded = SettingsManager(self.path)
        self.assertAlmostEqual(loaded.get("sensitivity_x"), 2.6, places=3)
        self.assertAlmostEqual(loaded.get("mar_threshold"), 0.45, places=3)


class TestAutoMarMath(unittest.TestCase):
    def test_60_percent_trigger_point(self):
        threshold = compute_auto_mar_threshold(
            [0.05, 0.05, 0.05],
            [0.55, 0.58, 0.56],
        )
        self.assertAlmostEqual(threshold, 0.356, places=3)

    def test_clamps_extreme_outliers(self):
        high = compute_auto_mar_threshold([0.05], [3.0, 4.0, 5.0])
        low = compute_auto_mar_threshold([0.50], [-1.0, -2.0, -3.0])
        self.assertEqual(high, 0.70)
        self.assertEqual(low, 0.25)

    def test_empty_samples_use_config_fallback(self):
        threshold = compute_auto_mar_threshold([], [])
        self.assertTrue(0.25 <= threshold <= 0.70)


class TestDoubleClickExitInEveryMode(unittest.TestCase):
    def test_header_exit_requires_two_clicks_in_terminal_mode(self):
        from eyede.ui.overlay_window import OverlayWindow

        overlay = OverlayWindow(start_in_mode_selector=False)
        overlay.mode_manager.set_mode("terminal", emit=False)
        overlay._on_context_mode_changed("terminal", "Terminal", "#A855F7")
        overlay.resize(1280, 720)
        overlay._update_header_exit_rect()
        emitted = []
        overlay.exit_requested.connect(lambda: emitted.append(True))
        rect = overlay.header_exit_rect
        nx = rect.center().x() / overlay.width()
        ny = rect.center().y() / overlay.height()

        overlay.on_gaze_updated(nx, ny)
        overlay.on_gesture_triggered("MOUTH_CLICK")
        self.assertEqual(emitted, [])
        self.assertNotEqual(overlay.current_node_id, "EXIT_CONFIRM")
        self.assertGreater(overlay._exit_armed_until, 0.0)

        overlay.on_gaze_updated(nx, ny)
        overlay.on_gesture_triggered("MOUTH_CLICK")
        self.assertEqual(emitted, [True])
        overlay.close()


class TestLanguageAutoDetectRegression(unittest.TestCase):
    def test_lang_auto_uses_context_reader_api(self):
        from eyede.actions.menu_trees import MenuAction
        from eyede.ui.overlay_window import OverlayWindow

        overlay = OverlayWindow(start_in_mode_selector=False)
        action = MenuAction(id="LANG_AUTO_TEST", label="Auto", action_type="LANG_AUTO")
        overlay.execute_action(action, 0)
        self.assertIn(overlay.current_language, ("PYTHON", "TYPESCRIPT", "RUST", "CPP", "GO"))
        overlay.close()


class TestCalibrationHudIsolation(unittest.TestCase):
    def test_suspend_and_resume_hud_input(self):
        from eyede.main import EyeDEApplication

        app = EyeDEApplication(camera_index="synthetic", threaded=False)
        app._suspend_hud_input_for_calibration()
        self.assertTrue(app._hud_input_suspended)
        app._resume_hud_input_after_calibration()
        self.assertFalse(app._hud_input_suspended)
        app.shutdown()


class TestStep6AndMarSlider(unittest.TestCase):
    def test_step6_collects_rest_and_three_peaks(self):
        ui = CalibrationUI(gaze_estimator=GazeEstimator(), auto_mar_enabled=True)
        captured = []
        ui.mar_threshold_calibrated.connect(lambda v: captured.append(v))
        ui._start_auto_mar_calibration()
        for _ in range(45):
            ui.on_mar_updated(0.05)
        self.assertEqual(ui._mar_phase, "peaks")
        for peak in (0.55, 0.58, 0.56):
            ui.on_mar_updated(peak)
            ui.on_mar_updated(0.05)
        self.assertAlmostEqual(ui._auto_mar_threshold, 0.356, places=3)
        self.assertEqual(len(captured), 1)
        self.assertAlmostEqual(captured[0], 0.356, places=3)
        ui.close()

    def test_step6_skip_cancels_pending_completion(self):
        ui = CalibrationUI(gaze_estimator=GazeEstimator(), auto_mar_enabled=True)
        ui.collected_data = [
            {"id": str(i), "name": str(i), "screen": (0.5, 0.5), "raw": (0.5, 0.5)}
            for i in range(5)
        ]
        finished = []
        ui.calibration_finished.connect(lambda ok: finished.append(ok))
        ui._start_auto_mar_calibration()
        for _ in range(45):
            ui.on_mar_updated(0.05)
        for peak in (0.55, 0.58, 0.56):
            ui.on_mar_updated(peak)
            ui.on_mar_updated(0.05)
        ui._skip_auto_mar()
        for _ in range(30):
            _APP.processEvents()
        self.assertLessEqual(len(finished), 1)
        ui.close()

    def test_close_stops_completion_timers(self):
        ui = CalibrationUI(gaze_estimator=GazeEstimator(), auto_mar_enabled=True)
        ui._start_auto_mar_calibration()
        ui._completion_timer.start(500)
        ui._finish_timer.start(700)
        ui.close()
        self.assertFalse(ui._completion_timer.isActive())
        self.assertFalse(ui._finish_timer.isActive())

    def test_debug_mar_slider_updates_threshold_and_signal(self):
        widget = DebugWidget()
        received = []
        widget.mar_threshold_changed.connect(lambda v: received.append(v))
        widget.set_mar_threshold(0.60)
        self.assertAlmostEqual(widget.mar_threshold, 0.60)
        self.assertEqual(widget.slider_mar_threshold.value(), 60)
        widget.slider_mar_threshold.setValue(55)
        self.assertAlmostEqual(widget.mar_threshold, 0.55)
        self.assertTrue(received)
        widget.close()


if __name__ == "__main__":
    unittest.main()
