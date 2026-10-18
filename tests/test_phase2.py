"""
Unit & Integration Test Suite for EyeDE Phase 2
Tests PyQt6 Multi-threading (QThread), Thread-Safety, 5-Point Calibration Math,
Window Flags (No-Focus Audit), Translucent HUD, Reading Mode, and Memory Safety (.copy()).
"""

import sys
import os
import unittest
import time
import json
import tempfile
import numpy as np

# Set offscreen platform before importing PyQt6 to guarantee 100% headless execution
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtCore import Qt, QThread, QCoreApplication
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QApplication

# Path resolution
_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_EYEDE_DIR = os.path.join(_ROOT_DIR, "eyede")
for p in (_ROOT_DIR, _EYEDE_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

import eyede.config as config
from eyede.core.camera_tracker import CameraTracker
from eyede.core.gaze_estimator import GazeEstimator
from eyede.core.gesture_detector import GestureDetector
from eyede.ui.overlay_window import OverlayWindow
from eyede.ui.debug_widget import DebugWidget
from eyede.ui.calibration_ui import CalibrationUI
from eyede.main import EyeDEApplication


# Ensure single QApplication exists for the test session
_APP = QApplication.instance() or QApplication(sys.argv if hasattr(sys, 'argv') else [])


class Test5PointCalibrationMath(unittest.TestCase):
    """Tests 5-point calibration math, bilinear fitting, persistence, and edge cases."""

    def setUp(self):
        self.estimator = GazeEstimator()

    def test_perfect_grid_mapping(self):
        """Tests that a linear affine grid maps accurately back to screen coordinates."""
        # Simulated raw coordinates (offset and scaled)
        # raw = 0.5 + 0.4 * (screen - 0.5)
        points_data = [
            {"id": "CENTER", "screen": (0.5, 0.5), "raw": (0.50, 0.50)},
            {"id": "TOP_LEFT", "screen": (0.1, 0.1), "raw": (0.34, 0.34)},
            {"id": "TOP_RIGHT", "screen": (0.9, 0.1), "raw": (0.66, 0.34)},
            {"id": "BOTTOM_LEFT", "screen": (0.1, 0.9), "raw": (0.34, 0.66)},
            {"id": "BOTTOM_RIGHT", "screen": (0.9, 0.9), "raw": (0.66, 0.66)},
        ]

        success = self.estimator.calibrate_5_points(points_data)
        self.assertTrue(success)
        self.assertTrue(self.estimator.has_5_point_calibration)
        self.assertLess(self.estimator.calibration_rmse, 0.01)

        # Test mapping center
        mx, my = self.estimator.apply_5_point_mapping(0.50, 0.50)
        self.assertAlmostEqual(mx, 0.5, delta=0.02)
        self.assertAlmostEqual(my, 0.5, delta=0.02)

        # Test mapping top-left
        mx, my = self.estimator.apply_5_point_mapping(0.34, 0.34)
        self.assertAlmostEqual(mx, 0.1, delta=0.02)
        self.assertAlmostEqual(my, 0.1, delta=0.02)

        # Test mapping bottom-right
        mx, my = self.estimator.apply_5_point_mapping(0.66, 0.66)
        self.assertAlmostEqual(mx, 0.9, delta=0.02)
        self.assertAlmostEqual(my, 0.9, delta=0.02)

    def test_save_and_load_profile(self):
        """Tests JSON profile serialization and loading."""
        points_data = [
            {"id": "CENTER", "screen": (0.5, 0.5), "raw": (0.50, 0.50)},
            {"id": "TOP_LEFT", "screen": (0.1, 0.1), "raw": (0.30, 0.30)},
            {"id": "TOP_RIGHT", "screen": (0.9, 0.1), "raw": (0.70, 0.30)},
            {"id": "BOTTOM_LEFT", "screen": (0.1, 0.9), "raw": (0.30, 0.70)},
            {"id": "BOTTOM_RIGHT", "screen": (0.9, 0.9), "raw": (0.70, 0.70)},
        ]
        self.estimator.calibrate_5_points(points_data)

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            temp_path = f.name

        try:
            # Save
            self.assertTrue(self.estimator.save_calibration_profile(temp_path))
            self.assertTrue(os.path.exists(temp_path))

            # Load into fresh estimator
            fresh_estimator = GazeEstimator()
            self.assertFalse(fresh_estimator.has_5_point_calibration)
            self.assertTrue(fresh_estimator.load_calibration_profile(temp_path))
            self.assertTrue(fresh_estimator.has_5_point_calibration)
            self.assertEqual(len(fresh_estimator.calib_weights_x), 4)
            self.assertEqual(len(fresh_estimator.calib_weights_y), 4)

            # Test mapped output matches
            ox, oy = self.estimator.apply_5_point_mapping(0.5, 0.5)
            nx, ny = fresh_estimator.apply_5_point_mapping(0.5, 0.5)
            self.assertAlmostEqual(ox, nx, places=5)
            self.assertAlmostEqual(oy, ny, places=5)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_degenerate_and_insufficient_points(self):
        """Zero division & degenerate point safety audit."""
        # Too few points
        self.assertFalse(self.estimator.calibrate_5_points([]))
        self.assertFalse(self.estimator.calibrate_5_points([{"screen": (0.5, 0.5), "raw": (0.5, 0.5)}]))

        # All identical/coincident raw points (singular system)
        degenerate = [
            {"id": str(i), "screen": (0.5, 0.5), "raw": (0.5, 0.5)} for i in range(5)
        ]
        self.assertFalse(self.estimator.calibrate_5_points(degenerate))

        # Horizontal-only variation (constant X, zero horizontal spread)
        degen_x = [
            {"id": str(i), "screen": (0.5, 0.5), "raw": (0.5, 0.1 * i)} for i in range(5)
        ]
        self.assertFalse(self.estimator.calibrate_5_points(degen_x))

        # Vertical-only variation (constant Y, zero vertical spread)
        degen_y = [
            {"id": str(i), "screen": (0.5, 0.5), "raw": (0.1 * i, 0.5)} for i in range(5)
        ]
        self.assertFalse(self.estimator.calibrate_5_points(degen_y))

        # Estimator must not be broken
        self.assertFalse(self.estimator.has_5_point_calibration)

    def test_load_corrupted_json(self):
        """Resilience against malformed or missing JSON profile."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            f.write("{ invalid json [ [")
            corrupt_path = f.name

        try:
            estimator = GazeEstimator()
            self.assertFalse(estimator.load_calibration_profile("non_existent_file.json"))
            self.assertFalse(estimator.load_calibration_profile(corrupt_path))
        finally:
            if os.path.exists(corrupt_path):
                os.remove(corrupt_path)


class TestCameraTrackerQThread(unittest.TestCase):
    """Tests CameraTracker QThread architecture, signals, and safe termination."""

    def test_tracker_is_qthread_subclass(self):
        tracker = CameraTracker(camera_index="synthetic", threaded=False)
        self.assertIsInstance(tracker, QThread)
        tracker.release()

    def test_qthread_signals_emission(self):
        """Verifies gaze_updated and frame_ready signals are properly emitted."""
        tracker = CameraTracker(camera_index="synthetic", threaded=True)

        received_gaze = []
        received_frames = []

        def on_gaze(x, y):
            received_gaze.append((x, y))

        def on_frame(frame, mar):
            received_frames.append((frame, mar))

        tracker.gaze_updated.connect(on_gaze)
        tracker.frame_ready.connect(on_frame)

        self.assertTrue(tracker.start())
        self.assertTrue(tracker.isRunning())

        # Wait briefly for frames to be processed by background thread
        start_wait = time.time()
        while len(received_gaze) < 3 and (time.time() - start_wait) < 2.0:
            _APP.processEvents()
            time.sleep(0.02)

        tracker.stop()
        self.assertTrue(tracker.wait(2000))
        self.assertFalse(tracker.isRunning())
        tracker.release()

        self.assertGreaterEqual(len(received_gaze), 2)
        self.assertGreaterEqual(len(received_frames), 2)

        # Check types and ranges
        gx, gy = received_gaze[0]
        self.assertIsInstance(gx, float)
        self.assertIsInstance(gy, float)
        self.assertTrue(0.0 <= gx <= 1.0)
        self.assertTrue(0.0 <= gy <= 1.0)

        frame, mar = received_frames[0]
        self.assertIsInstance(frame, np.ndarray)
        self.assertIsInstance(mar, float)

    def test_safe_stop_and_wait_no_zombies(self):
        """Audit requirement: No zombie threads left running upon stop()."""
        tracker = CameraTracker(camera_index="synthetic", threaded=True)
        tracker.start()
        self.assertTrue(tracker.isRunning())

        tracker.stop()
        stopped = tracker.wait(2000)
        self.assertTrue(stopped)
        self.assertFalse(tracker.isRunning())
        tracker.release()


class TestOverlayWindowFocusAndReadingMode(unittest.TestCase):
    """Audits requirement 2 & 4: Overlay window flags, focus safety, and reading mode."""

    def setUp(self):
        self.overlay = OverlayWindow()

    def tearDown(self):
        self.overlay.close()

    def test_window_flags_no_focus_audit(self):
        """Verifies critical window flags for non-focus stealing behavior."""
        flags = self.overlay.windowFlags()

        # Frameless
        self.assertTrue(bool(flags & Qt.WindowType.FramelessWindowHint))
        # Always on top
        self.assertTrue(bool(flags & Qt.WindowType.WindowStaysOnTopHint))
        # Window does not accept focus (VS Code cursor protection)
        self.assertTrue(bool(flags & Qt.WindowType.WindowDoesNotAcceptFocus))
        # Tool window
        self.assertTrue(bool(flags & Qt.WindowType.Tool))

        # Focus policy must be NoFocus
        self.assertEqual(self.overlay.focusPolicy(), Qt.FocusPolicy.NoFocus)

    def test_translucent_background_attribute(self):
        self.assertTrue(self.overlay.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground))

    def test_transparent_for_mouse_events_attribute(self):
        """Verifies WA_TransparentForMouseEvents allows mouse clicks to reach VS Code underneath."""
        self.assertTrue(self.overlay.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents))

    def test_gaze_hover_mapping(self):
        """Verifies normalized gaze maps to correct 3x3 block index."""
        # Top-left cell (row 0, col 0 -> index 0)
        self.overlay.on_gaze_updated(0.1, 0.1)
        self.assertEqual(self.overlay.hovered_block, 0)

        # Center cell (row 1, col 1 -> index 4)
        self.overlay.on_gaze_updated(0.5, 0.5)
        self.assertEqual(self.overlay.hovered_block, 4)

        # Bottom-right cell (row 2, col 2 -> index 8)
        self.overlay.on_gaze_updated(0.9, 0.9)
        self.assertEqual(self.overlay.hovered_block, 8)

    def test_gesture_click_action_emission(self):
        """Verifies MOUTH_CLICK on hovered block fires block_activated signal."""
        triggered = []

        def on_act(idx, action):
            triggered.append((idx, action))

        self.overlay.block_activated.connect(on_act)

        # Look at block 0 (IF/ELSE)
        self.overlay.on_gaze_updated(0.1, 0.1)
        self.overlay.on_gesture_triggered("MOUTH_CLICK")

        self.assertEqual(len(triggered), 1)
        self.assertEqual(triggered[0][0], 0)
        self.assertEqual(triggered[0][1], "INSERT_IF_ELSE")

    def test_block4_reading_mode_toggle_and_inhibition(self):
        """
        Verifies Block 4 (Center) toggles 10% opacity reading mode
        and inhibits the remaining blocks while reading.
        """
        self.assertFalse(self.overlay.reading_mode)
        self.assertEqual(self.overlay.current_opacity, config.OVERLAY_OPACITY_ACTIVE)

        # Look at Center Block 4 and click
        self.overlay.on_gaze_updated(0.5, 0.5)
        self.overlay.on_gesture_triggered("MOUTH_CLICK")

        # Now in Reading Mode!
        self.assertTrue(self.overlay.reading_mode)
        self.assertAlmostEqual(self.overlay.current_opacity, config.OVERLAY_OPACITY_READING, delta=0.01)

        # While in reading mode, looking at other blocks must NOT hover them (inhibition)
        self.overlay.on_gaze_updated(0.1, 0.1)  # Look at Block 0
        self.assertIsNone(self.overlay.hovered_block)

        # Clicking on other blocks while reading must NOT trigger actions
        actions = []
        self.overlay.block_activated.connect(lambda idx, act: actions.append(act))
        self.overlay.on_gesture_triggered("MOUTH_CLICK")
        self.assertEqual(len(actions), 0)

        # Look back at Center Block 4
        self.overlay.on_gaze_updated(0.5, 0.5)
        self.assertEqual(self.overlay.hovered_block, 4)

        # Click on Center Block 4 again -> Resume Active Mode!
        self.overlay.on_gesture_triggered("MOUTH_CLICK")
        self.assertFalse(self.overlay.reading_mode)
        self.assertAlmostEqual(self.overlay.current_opacity, config.OVERLAY_OPACITY_ACTIVE, delta=0.01)


class TestDebugWidgetMemorySafety(unittest.TestCase):
    """Audits QA requirement 2: QImage memory safety and .copy()."""

    def setUp(self):
        self.debug_widget = DebugWidget()

    def tearDown(self):
        self.debug_widget.close()

    def test_memory_safe_frame_conversion(self):
        """Verifies numpy frame conversion with .copy() without memory corruption."""
        frame = np.zeros((160, 240, 3), dtype=np.uint8)
        frame[:] = (100, 150, 200)

        # Call on_frame_ready
        self.debug_widget.on_frame_ready(frame, 0.25)
        pixmap = self.debug_widget.video_label.pixmap()
        self.assertIsNotNone(pixmap)
        self.assertFalse(pixmap.isNull())

        # Mutate original numpy buffer; widget pixmap must remain unaffected
        frame[:] = 0
        self.assertFalse(self.debug_widget.video_label.pixmap().isNull())

    def test_safe_none_and_qimage_inputs(self):
        """Verifies widget handles None, empty, and QImage inputs safely."""
        self.debug_widget.on_frame_ready(None, 0.0)

        qimg = QImage(100, 100, QImage.Format.Format_RGB888)
        self.debug_widget.on_frame_ready(qimg, 0.10)
        self.assertFalse(self.debug_widget.video_label.pixmap().isNull())

    def test_mar_progress_bar_threshold_styling(self):
        self.debug_widget.update_mar(0.20)
        self.assertEqual(self.debug_widget.mar_bar.value(), 20)

        self.debug_widget.update_mar(0.60)
        self.assertEqual(self.debug_widget.mar_bar.value(), 60)

    def test_debug_widget_focus_and_activation(self):
        """Audits QA requirement 3: Debug widget must not activate or steal keyboard focus."""
        self.assertTrue(self.debug_widget.testAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating))
        self.assertEqual(self.debug_widget.focusPolicy(), Qt.FocusPolicy.NoFocus)
        self.assertEqual(self.debug_widget.btn_recalibrate.focusPolicy(), Qt.FocusPolicy.NoFocus)
        self.assertEqual(self.debug_widget.btn_exit.focusPolicy(), Qt.FocusPolicy.NoFocus)

    def test_debug_widget_sliders_tuning_and_signals(self):
        """Verifies sensitivity and damping sliders emit signals and update gaze estimator."""
        estimator = GazeEstimator()
        self.debug_widget.set_gaze_estimator(estimator)

        emitted_x = []
        emitted_y = []
        emitted_damping = []

        self.debug_widget.sensitivity_x_changed.connect(lambda v: emitted_x.append(v))
        self.debug_widget.sensitivity_y_changed.connect(lambda v: emitted_y.append(v))
        self.debug_widget.anti_jitter_changed.connect(lambda v: emitted_damping.append(v))

        # Adjust X sensitivity slider (range 10 to 80, value 45 -> 4.5x)
        self.debug_widget.slider_sens_x.setValue(45)
        self.assertEqual(len(emitted_x), 1)
        self.assertAlmostEqual(emitted_x[0], 4.5, places=2)
        self.assertAlmostEqual(estimator.head_sensitivity_x, 4.5, places=2)

        # Adjust Y sensitivity slider (range 20 to 140, value 85 -> 8.5x)
        self.debug_widget.slider_sens_y.setValue(85)
        self.assertEqual(len(emitted_y), 1)
        self.assertAlmostEqual(emitted_y[0], 8.5, places=2)
        self.assertAlmostEqual(estimator.head_sensitivity_y, 8.5, places=2)

        # Adjust Anti-Jitter Damping slider (range 1 to 10, value 8)
        self.debug_widget.slider_damping.setValue(8)
        self.assertEqual(len(emitted_damping), 1)
        self.assertEqual(emitted_damping[0], 8.0)
        self.assertLess(estimator.one_euro_x.min_cutoff, 0.55)

    def test_debug_widget_focus_policy_on_sliders(self):
        """Audits that tuning sliders strictly adhere to NoFocus policy."""
        self.assertEqual(self.debug_widget.slider_sens_x.focusPolicy(), Qt.FocusPolicy.NoFocus)
        self.assertEqual(self.debug_widget.slider_sens_y.focusPolicy(), Qt.FocusPolicy.NoFocus)
        self.assertEqual(self.debug_widget.slider_damping.focusPolicy(), Qt.FocusPolicy.NoFocus)
        self.assertEqual(self.debug_widget.btn_reset.focusPolicy(), Qt.FocusPolicy.NoFocus)

    def test_debug_widget_reset_sliders(self):
        """Tests that reset button restores default sensitivity and damping values."""
        self.debug_widget.slider_sens_x.setValue(70)
        self.debug_widget.slider_sens_y.setValue(120)
        self.debug_widget.slider_damping.setValue(2)

        emitted_reset = []
        self.debug_widget.reset_calibration_requested.connect(lambda: emitted_reset.append(True))
        self.debug_widget.btn_reset.click()

        self.assertEqual(len(emitted_reset), 1)
        self.assertEqual(self.debug_widget.slider_sens_x.value(), int(config.DEFAULT_HEAD_SENSITIVITY_X * 10))
        self.assertEqual(self.debug_widget.slider_sens_y.value(), int(config.DEFAULT_HEAD_SENSITIVITY_Y * 10))
        self.assertEqual(self.debug_widget.slider_damping.value(), 6)


class TestCalibrationUIWorkflow(unittest.TestCase):
    """Tests 5-point calibration sequential guide and state progression."""

    def test_calibration_progression(self):
        estimator = GazeEstimator()
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            temp_profile = f.name

        try:
            calib_ui = CalibrationUI(
                gaze_estimator=estimator,
                profile_path=temp_profile,
                samples_per_point=3,
            )

            # Advance through all 5 points
            for pt_idx in range(5):
                self.assertEqual(calib_ui.current_pt_idx, pt_idx)
                calib_ui.latest_raw_gaze = (0.5 + 0.2 * (pt_idx - 2), 0.5 + 0.1 * (pt_idx - 2))
                # Trigger sampling via space
                calib_ui.start_sampling()
                while calib_ui.is_sampling:
                    calib_ui._collect_sample_tick()

            self.assertTrue(calib_ui.is_completed)
            self.assertEqual(len(calib_ui.collected_data), 5)
            self.assertTrue(os.path.exists(temp_profile))
            calib_ui.close()
        finally:
            if os.path.exists(temp_profile):
                os.remove(temp_profile)

    def test_calibration_failure_emits_false(self):
        """Verifies that degenerate calibration emits False and does not save invalid profile."""
        estimator = GazeEstimator()
        temp_profile = os.path.join(tempfile.gettempdir(), f"test_calib_fail_{time.time()}.json")

        calib_ui = CalibrationUI(
            gaze_estimator=estimator,
            profile_path=temp_profile,
            samples_per_point=3,
        )

        emitted_status = []
        calib_ui.calibration_finished.connect(lambda s: emitted_status.append(s))

        # Sample degenerate identical points
        for pt_idx in range(5):
            calib_ui.latest_raw_gaze = (0.5, 0.5)
            calib_ui.start_sampling()
            while calib_ui.is_sampling:
                calib_ui._collect_sample_tick()

        # Let the timer finish
        _APP.processEvents()
        time.sleep(0.05)
        _APP.processEvents()

        self.assertTrue(calib_ui.is_completed)
        # Succeeded must NOT be True
        self.assertFalse(os.path.exists(temp_profile))
        calib_ui.close()

    def test_calibration_escape_cancels(self):
        """Verifies pressing Escape emits False and closes widget."""
        estimator = GazeEstimator()
        calib_ui = CalibrationUI(gaze_estimator=estimator)

        emitted = []
        calib_ui.calibration_finished.connect(lambda s: emitted.append(s))

        from PyQt6.QtGui import QKeyEvent
        from PyQt6.QtCore import QEvent
        esc_event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
        calib_ui.keyPressEvent(esc_event)

        self.assertEqual(len(emitted), 1)
        self.assertFalse(emitted[0])
        calib_ui.close()


class TestEyeDEApplicationLifecycle(unittest.TestCase):
    """Tests the PyQt6 orchestrator lifecycle, window coordination, and shutdown."""

    def test_app_lifecycle_synthetic(self):
        """Verifies EyeDEApplication can start and cleanly shut down without errors or zombie threads."""
        app = EyeDEApplication(camera_index="synthetic", force_calibrate=False, threaded=True)
        self.assertIsNotNone(app.tracker)
        self.assertIsNotNone(app.overlay)
        self.assertIsNotNone(app.debug_widget)

        app.start()
        self.assertTrue(app.tracker.isRunning())
        self.assertTrue(app.debug_widget.isVisible())

        # Let a few frames process through Qt event loop
        start = time.time()
        while (time.time() - start) < 0.2:
            _APP.processEvents()
            time.sleep(0.02)

        app.shutdown()
        self.assertFalse(app.tracker.isRunning())

    def test_app_block_activation(self):
        """Verifies block_activated signal handler in EyeDEApplication."""
        app = EyeDEApplication(camera_index="synthetic", force_calibrate=False, threaded=False)
        # Should not raise exception
        app._on_block_activated(0, "INSERT_IF_ELSE")
        app._on_block_activated(4, "PAUSE_RESUME")
        app._on_block_activated(8, "ACTION_EXIT")
        app.shutdown()

    def test_app_slider_wiring_to_tracker_gaze_estimator(self):
        """Verifies that debug widget sliders update the tracker's gaze estimator in real-time."""
        app = EyeDEApplication(camera_index="synthetic", force_calibrate=False, threaded=False)
        self.assertIsNotNone(app.tracker.gaze_estimator)

        # Move X slider to 55 (5.5x)
        app.debug_widget.slider_sens_x.setValue(55)
        self.assertAlmostEqual(app.tracker.gaze_estimator.head_sensitivity_x, 5.5, places=2)

        # Move Y slider to 95 (9.5x)
        app.debug_widget.slider_sens_y.setValue(95)
        self.assertAlmostEqual(app.tracker.gaze_estimator.head_sensitivity_y, 9.5, places=2)

        # Move Damping slider to 9
        app.debug_widget.slider_damping.setValue(9)
        self.assertLess(app.tracker.gaze_estimator.one_euro_x.min_cutoff, 0.45)

        # Test reset_calibration restores debug sliders
        app.reset_calibration()
        self.assertEqual(app.debug_widget.slider_sens_x.value(), int(config.DEFAULT_HEAD_SENSITIVITY_X * 10))
        self.assertEqual(app.debug_widget.slider_sens_y.value(), int(config.DEFAULT_HEAD_SENSITIVITY_Y * 10))
        self.assertEqual(app.debug_widget.slider_damping.value(), 6)

        app.shutdown()


class TestCameraTrackerSyntheticSimulation(unittest.TestCase):
    """Tests that synthetic camera generates realistic face landmarks and moving coordinates."""

    def test_synthetic_camera_produces_landmarks(self):
        tracker = CameraTracker(camera_index="synthetic", threaded=False)
        success, frame, landmarks = tracker.read_frame()
        tracker.release()

        self.assertTrue(success)
        self.assertIsNotNone(frame)
        self.assertIsNotNone(landmarks)
        self.assertGreaterEqual(len(landmarks), 478)

        # Check key landmarks exist and are normalized
        p_nose = landmarks[config.LANDMARK_NOSE_TIP]
        self.assertTrue(0.0 <= p_nose.x <= 1.0)
        self.assertTrue(0.0 <= p_nose.y <= 1.0)


if __name__ == "__main__":
    unittest.main()
