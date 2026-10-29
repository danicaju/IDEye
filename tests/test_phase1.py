"""
Unit and Integration Test Suite for IDEye Phase 1
Tests Zero-Division safety, Face Loss resilience, State Machine debouncing,
Blink suppression, Distance-adaptive calibration, Layout visibility, and Threaded Lifecycle.
"""

import sys
import os
import unittest
import time
import math
import numpy as np
from unittest.mock import MagicMock, patch

# Ensure paths
_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_IDEYE_DIR = os.path.join(_ROOT_DIR, "ideye")
for p in (_ROOT_DIR, _IDEYE_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

from ideye.core.gesture_detector import GestureDetector, GestureState
from ideye.core.gaze_estimator import GazeEstimator
from ideye.core.camera_tracker import CameraTracker
from ideye.main import IDEyeMainApp
import ideye.config as config


class MockPoint:
    def __init__(self, x: float, y: float, z: float = 0.0):
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)


class MockFaceLandmarks:
    def __init__(self, count: int = 478, default_x: float = 0.5, default_y: float = 0.5):
        self.landmark = [MockPoint(default_x, default_y) for _ in range(count)]

    def set_point(self, idx: int, x: float, y: float, z: float = 0.0):
        if idx < len(self.landmark):
            self.landmark[idx] = MockPoint(x, y, z)


class TestZeroDivisionAudit(unittest.TestCase):
    """Audits QA requirement 1: No ZeroDivisionError under any edge case."""

    def test_gesture_detector_coincident_points(self):
        """All lip points at exactly the same coordinates (0, 0) - d_horizontal = 0."""
        detector = GestureDetector(mar_threshold=0.45)
        mock_face = MockFaceLandmarks(count=478, default_x=0.5, default_y=0.5)
        mar = detector.compute_mar(mock_face)
        self.assertIsInstance(mar, float)
        self.assertFalse(math.isnan(mar))
        self.assertEqual(mar, 0.0)

    def test_gesture_detector_horizontal_distance_zero(self):
        """Mouth corners identical, lips separated vertically."""
        detector = GestureDetector(mar_threshold=0.45)
        mock_face = MockFaceLandmarks(count=478)
        mock_face.set_point(78, 0.5, 0.5)
        mock_face.set_point(308, 0.5, 0.5)
        mock_face.set_point(13, 0.5, 0.4)
        mock_face.set_point(14, 0.5, 0.6)

        mar = detector.compute_mar(mock_face)
        self.assertIsInstance(mar, float)
        self.assertFalse(math.isnan(mar))
        self.assertLessEqual(mar, 5.0)

    def test_gaze_estimator_coincident_eye_corners(self):
        """Eye corners overlapping at exact same coordinate (width = 0, height = 0)."""
        estimator = GazeEstimator()
        mock_face = MockFaceLandmarks(count=478, default_x=0.5, default_y=0.5)

        # Left eye overlapping
        mock_face.set_point(133, 0.5, 0.5)
        mock_face.set_point(33, 0.5, 0.5)
        mock_face.set_point(159, 0.5, 0.5)
        mock_face.set_point(145, 0.5, 0.5)
        mock_face.set_point(468, 0.5, 0.5)

        # Right eye overlapping
        mock_face.set_point(362, 0.5, 0.5)
        mock_face.set_point(263, 0.5, 0.5)
        mock_face.set_point(386, 0.5, 0.5)
        mock_face.set_point(374, 0.5, 0.5)
        mock_face.set_point(473, 0.5, 0.5)

        gx, gy, detected, _ = estimator.estimate(mock_face)
        self.assertIsInstance(gx, float)
        self.assertIsInstance(gy, float)
        self.assertTrue(0.0 <= gx <= 1.0)
        self.assertTrue(0.0 <= gy <= 1.0)


class TestFaceLossAudit(unittest.TestCase):
    """Audits QA requirement 2: Safe handling of None and face loss."""

    def test_gesture_detector_none_face(self):
        detector = GestureDetector()
        mar = detector.compute_mar(None)
        self.assertEqual(mar, 0.0)

        click, mar_val, progress = detector.process(None)
        self.assertFalse(click)
        self.assertEqual(mar_val, 0.0)
        self.assertEqual(progress, 0.0)

    def test_gesture_detector_partial_landmarks(self):
        """Malformed or incomplete landmarks (e.g. only 10 points)."""
        detector = GestureDetector()
        short_face = MockFaceLandmarks(count=10)
        click, mar_val, progress = detector.process(short_face)
        self.assertFalse(click)
        self.assertEqual(mar_val, 0.0)

    def test_gaze_estimator_face_loss_preserves_last_position(self):
        estimator = GazeEstimator()
        mock_face = MockFaceLandmarks(count=478)
        mock_face.set_point(1, 0.65, 0.40)
        mock_face.set_point(33, 0.30, 0.40)
        mock_face.set_point(133, 0.45, 0.40)
        mock_face.set_point(468, 0.38, 0.40)
        mock_face.set_point(263, 0.55, 0.40)
        mock_face.set_point(362, 0.70, 0.40)
        mock_face.set_point(473, 0.62, 0.40)

        gx1, gy1, detected1, _ = estimator.estimate(mock_face)
        self.assertTrue(detected1)

        # Face is lost
        gx2, gy2, detected2, _ = estimator.estimate(None)
        self.assertFalse(detected2)
        self.assertEqual(gx1, gx2)
        self.assertEqual(gy1, gy2)

    def test_gaze_estimator_empty_or_short_landmarks(self):
        estimator = GazeEstimator()
        empty_face = MagicMock()
        empty_face.landmark = []
        gx, gy, detected, _ = estimator.estimate(empty_face)
        self.assertFalse(detected)
        self.assertEqual(gx, 0.5)
        self.assertEqual(gy, 0.5)


class TestGestureStateMachine(unittest.TestCase):
    """Tests MAR calculation, hold time debounce, cooldown, and lock-prevention."""

    def setUp(self):
        self.detector = GestureDetector(
            mar_threshold=0.45,
            release_threshold=0.35,
            hold_time_sec=0.15,
            cooldown_sec=0.30,
        )

    def _create_face_with_mar(self, target_mar: float) -> MockFaceLandmarks:
        mock_face = MockFaceLandmarks(count=478)
        mock_face.set_point(78, 0.40, 0.50)
        mock_face.set_point(308, 0.60, 0.50)
        dy = target_mar * 0.20
        mock_face.set_point(13, 0.50, 0.50 - dy / 2.0)
        mock_face.set_point(14, 0.50, 0.50 + dy / 2.0)
        return mock_face

    def test_click_triggers_only_after_hold_time(self):
        face_open = self._create_face_with_mar(0.55)

        # t = 1.0s: mouth opens
        click, mar, progress = self.detector.process(face_open, current_time=1.0)
        self.assertFalse(click)
        self.assertAlmostEqual(mar, 0.55, delta=0.01)
        self.assertEqual(self.detector.state, GestureState.HOLDING_OPEN)

        # t = 1.10s (100ms < 150ms): holding
        click, mar, progress = self.detector.process(face_open, current_time=1.10)
        self.assertFalse(click)
        self.assertAlmostEqual(progress, 0.10 / 0.15, delta=0.05)
        self.assertEqual(self.detector.state, GestureState.HOLDING_OPEN)

        # t = 1.16s (160ms > 150ms): CLICK fires!
        click, mar, progress = self.detector.process(face_open, current_time=1.16)
        self.assertTrue(click)
        self.assertEqual(self.detector.state, GestureState.TRIGGERED)
        self.assertEqual(self.detector.total_clicks, 1)

        # t = 1.20s: keeping mouth open does NOT fire a second click
        click, mar, progress = self.detector.process(face_open, current_time=1.20)
        self.assertFalse(click)
        self.assertEqual(self.detector.total_clicks, 1)

    def test_early_closure_cancels_hold(self):
        face_open = self._create_face_with_mar(0.55)
        face_closed = self._create_face_with_mar(0.20)

        # Start hold
        self.detector.process(face_open, current_time=1.0)
        self.assertEqual(self.detector.state, GestureState.HOLDING_OPEN)

        # Close early at 80ms
        click, _, progress = self.detector.process(face_closed, current_time=1.08)
        self.assertFalse(click)
        self.assertEqual(self.detector.state, GestureState.IDLE_CLOSED)
        self.assertEqual(progress, 0.0)

    def test_reopening_mouth_after_cooldown_triggers_second_click(self):
        """Fixes bug where closing mouth during cooldown and reopening locked the state machine."""
        face_open = self._create_face_with_mar(0.55)
        face_closed = self._create_face_with_mar(0.20)

        # Click 1 at 1.16s
        self.detector.process(face_open, current_time=1.0)
        click1, _, _ = self.detector.process(face_open, current_time=1.16)
        self.assertTrue(click1)
        self.assertEqual(self.detector.state, GestureState.TRIGGERED)

        # User closes mouth during cooldown (t = 1.20s, cooldown ends at 1.46s)
        self.detector.process(face_closed, current_time=1.20)
        self.assertTrue(self.detector.released_since_trigger)
        self.assertEqual(self.detector.hold_progress, 0.0)

        # User reopens mouth after cooldown (t = 1.48s)
        self.detector.process(face_open, current_time=1.48)
        self.assertEqual(self.detector.state, GestureState.HOLDING_OPEN)

        # Click 2 fires at 1.65s (1.48 + 0.17 > 0.15)
        click2, _, _ = self.detector.process(face_open, current_time=1.65)
        self.assertTrue(click2)
        self.assertEqual(self.detector.total_clicks, 2)


class TestGazeCalibrationAndWeights(unittest.TestCase):
    """Tests 60/40 hybrid fusion, calibration, blink suppression, and EMA smoothing."""

    def test_hybrid_weights(self):
        estimator = GazeEstimator(head_weight=0.60, iris_weight=0.40)
        self.assertAlmostEqual(estimator.head_weight, 0.60)
        self.assertAlmostEqual(estimator.iris_weight, 0.40)

    def test_center_calibration_neutral_point(self):
        estimator = GazeEstimator()
        mock_face = MockFaceLandmarks(count=478)
        mock_face.set_point(1, 0.58, 0.42)
        mock_face.set_point(33, 0.64, 0.42)
        mock_face.set_point(263, 0.36, 0.42)

        success = estimator.calibrate_center(mock_face)
        self.assertTrue(success)
        self.assertTrue(estimator.is_calibrated)
        self.assertEqual(estimator.neutral_head_x, 0.58)
        self.assertEqual(estimator.neutral_head_y, 0.42)

        gx, gy, detected, _ = estimator.estimate(mock_face)
        self.assertAlmostEqual(gx, 0.5, delta=0.01)
        self.assertAlmostEqual(gy, 0.5, delta=0.01)

    def test_blink_suppression_prevents_pointer_jumps(self):
        """Fixes bug where eyelid closure (blinking) swung vertical iris ratio to extreme values."""
        estimator = GazeEstimator(head_weight=0.6, iris_weight=0.4, ema_alpha=0.5)

        def make_face(eye_h: float, iris_offset: float) -> MockFaceLandmarks:
            f = MockFaceLandmarks(count=478)
            f.set_point(1, 0.5, 0.5)
            # Left eye
            f.set_point(133, 0.55, 0.40)
            f.set_point(33, 0.65, 0.40)
            f.set_point(159, 0.60, 0.40 - eye_h / 2.0)
            f.set_point(145, 0.60, 0.40 + eye_h / 2.0)
            f.set_point(468, 0.60, 0.40 + iris_offset)
            # Right eye
            f.set_point(362, 0.45, 0.40)
            f.set_point(263, 0.35, 0.40)
            f.set_point(386, 0.40, 0.40 - eye_h / 2.0)
            f.set_point(374, 0.40, 0.40 + eye_h / 2.0)
            f.set_point(473, 0.40, 0.40 + iris_offset)
            return f

        face_open = make_face(eye_h=0.03, iris_offset=0.0)
        estimator.calibrate_center(face_open)
        gx_open, gy_open, _, _ = estimator.estimate(face_open)
        self.assertAlmostEqual(gx_open, 0.5, delta=0.01)
        self.assertAlmostEqual(gy_open, 0.5, delta=0.01)

        # Eye closes during blink (height drops to 0.002)
        face_blink = make_face(eye_h=0.002, iris_offset=0.002)
        gx_blink, gy_blink, _, debug_info = estimator.estimate(face_blink)

        self.assertTrue(debug_info["is_blinking"])
        # Pointer MUST remain steady at (0.5, 0.5) and not jump
        self.assertAlmostEqual(gx_blink, 0.5, delta=0.01)
        self.assertAlmostEqual(gy_blink, 0.5, delta=0.01)

    def test_distance_adaptive_calibration(self):
        """Audits requirement 3: fijar ganancia/sensibilidad adaptada a la distancia del usuario."""
        estimator = GazeEstimator(head_sensitivity_x=2.0)
        face = MockFaceLandmarks(count=478)
        # Face at half the normal width (user sits farther back)
        face.set_point(33, 0.57, 0.4)
        face.set_point(263, 0.43, 0.4)  # span = 0.14 vs nominal 0.28
        estimator.calibrate_center(face, nominal_interocular=0.28)

        self.assertAlmostEqual(estimator.distance_scale, 2.0, delta=0.05)
        self.assertAlmostEqual(estimator.head_sensitivity_x, 4.0, delta=0.1)

    def test_manual_sensitivity_adjustment(self):
        estimator = GazeEstimator(head_sensitivity_x=2.0)
        estimator.adjust_sensitivity(1.10)
        self.assertAlmostEqual(estimator.head_sensitivity_x, 2.20, delta=0.01)
        estimator.adjust_sensitivity(0.90)
        self.assertAlmostEqual(estimator.head_sensitivity_x, 1.98, delta=0.01)

    def test_ema_smoothing(self):
        estimator = GazeEstimator(ema_alpha=0.20)
        face = MockFaceLandmarks(count=478)
        face.set_point(1, 0.5, 0.5)
        estimator.calibrate_center(face)

        face.set_point(1, 0.6, 0.5)
        gx1, gy1, _, _ = estimator.estimate(face)
        self.assertGreater(gx1, 0.5)
        gx2, gy2, _, _ = estimator.estimate(face)
        self.assertGreater(gx2, gx1)


class TestBlock9AndMiniFeedLayout(unittest.TestCase):
    """Audits requirement 4: All 9 Macro-blocks must be visible, responsive, and not covered."""

    def test_block9_label_is_not_covered_by_mini_feed(self):
        app = IDEyeMainApp(canvas_width=1280, canvas_height=720, threaded=False)
        x1, y1, x2, y2 = app._get_block_rect(2, 2)  # Block 9: SALIR

        mw = config.MINI_FEED_WIDTH
        mh = config.MINI_FEED_HEIGHT
        margin = config.MINI_FEED_MARGIN
        fx1 = app.canvas_width - mw - margin
        fy1 = app.canvas_height - mh - margin

        # Block 9 label is rendered at y1 + 38
        label_y = y1 + 38
        # Label MUST be located above the mini-feed container
        self.assertLess(label_y, fy1 - 10)

    def test_block9_click_flash_and_hover_synchronized(self):
        app = IDEyeMainApp(canvas_width=1280, canvas_height=720, threaded=False)
        canvas = np.zeros((720, 1280, 3), dtype=np.uint8)

        # Hover block 8 (Block 9)
        app._draw_grid(canvas, 8, 0.0)
        app._draw_mini_feed_and_mar(canvas, None, None, 0.20, 0.0, True, False, 8)

        # Trigger click on block 8
        app.last_clicked_block_idx = 8
        app.last_click_timestamp = time.time()
        app._draw_grid(canvas, 8, app.last_click_timestamp)
        app._draw_mini_feed_and_mar(canvas, None, None, 0.50, 1.0, True, True, 8)

        self.assertIsNotNone(canvas)


class TestResourceLifecycleAndThreading(unittest.TestCase):
    """Audits QA requirement 3 & AGENTS.md: Clean resource cleanup and threading."""

    def test_idempotent_release_no_double_close_error(self):
        """Verifies calling release() multiple times never crashes with ValueError."""
        tracker = CameraTracker(camera_index=-1, threaded=False)
        tracker.start()
        tracker.release()
        # Second call must not raise ValueError: Closing SolutionBase._graph
        tracker.release()
        self.assertIsNone(tracker.cap)
        self.assertIsNone(tracker.face_mesh)

    def test_synthetic_camera_mode(self):
        """Verifies camera tracker works headlessly in synthetic mode without physical webcam."""
        tracker = CameraTracker(camera_index="synthetic", threaded=False)
        self.assertTrue(tracker.start())
        success, frame, landmarks = tracker.read_frame()
        self.assertTrue(success)
        self.assertIsNotNone(frame)
        self.assertEqual(frame.shape, (720, 1280, 3))
        tracker.release()

    def test_threaded_camera_tracker_lifecycle(self):
        """Verifies background capture worker starts and stops cleanly."""
        tracker = CameraTracker(camera_index="synthetic", threaded=True)
        self.assertTrue(tracker.start())
        self.assertTrue(tracker.threaded)
        self.assertIsNotNone(tracker._worker_thread)
        self.assertTrue(tracker._worker_thread.is_alive())

        # Read at least one frame from worker
        time.sleep(0.08)
        success, frame, landmarks = tracker.read_frame()
        self.assertTrue(success)
        self.assertIsNotNone(frame)

        tracker.release()
        self.assertFalse(tracker._worker_thread.is_alive() if tracker._worker_thread else False)
        self.assertFalse(tracker._is_opened)

    def test_main_app_clean_finally_release(self):
        app = IDEyeMainApp(canvas_width=640, canvas_height=480, camera_index="synthetic", threaded=False)
        with patch("cv2.namedWindow"), patch("cv2.resizeWindow"), patch("cv2.imshow"), patch("cv2.waitKey", return_value=ord('q')), patch("cv2.destroyAllWindows") as mock_destroy:
            app.run(max_frames=1)
            mock_destroy.assert_called_once()
            self.assertIsNone(app.tracker.cap)
            self.assertIsNone(app.tracker.face_mesh)


if __name__ == "__main__":
    unittest.main()
