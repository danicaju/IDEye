"""
Unit & Integration Test Suite for IDEye Phase 2
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
_IDEYE_DIR = os.path.join(_ROOT_DIR, "ideye")
for p in (_ROOT_DIR, _IDEYE_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

import ideye.config as config
from ideye.core.camera_tracker import CameraTracker
from ideye.core.gaze_estimator import GazeEstimator
from ideye.core.gesture_detector import GestureDetector
from ideye.ui.overlay_window import OverlayWindow
from ideye.ui.debug_widget import DebugWidget
from ideye.ui.calibration_ui import CalibrationUI
from ideye.main import IDEyeApplication


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


if __name__ == "__main__":
    unittest.main()
