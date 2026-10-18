"""
Camera Tracker Module for EyeDE (Phase 2)
Handles OpenCV webcam capture and MediaPipe FaceMesh processing
with 478 refined 3D landmarks for iris and facial tracking.

Refactored to inherit from PyQt6.QtCore.QThread:
- Emits gaze_updated(float, float), gesture_triggered(str), frame_ready(object, float).
- Safe stop() and wait() methods to prevent zombie threads.
- Thread-safe architecture: OpenCV + MediaPipe CV inference executes exclusively
  in the QThread background worker, never blocking the main UI thread (<35ms budget).
- Full backwards compatibility with Phase 1 synchronous & threaded interfaces.
"""

from typing import Optional, Tuple, Any, List, Union
import sys
import os
import threading
import time
import math
import cv2
import numpy as np
import mediapipe as mp

from PyQt6.QtCore import QThread, pyqtSignal, QObject, QCoreApplication

# Internal imports with fallback
try:
    import eyede.config as config
    from eyede.core.gaze_estimator import GazeEstimator
    from eyede.core.gesture_detector import GestureDetector
except ImportError:
    import config
    from core.gaze_estimator import GazeEstimator
    from core.gesture_detector import GestureDetector


def _ensure_qt_app():
    """Ensures a QCoreApplication exists so QThread and signals operate safely."""
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication(sys.argv if hasattr(sys, 'argv') else [])
    return app


class CameraTracker(QThread):
    """
    Manages OpenCV video capture and MediaPipe FaceMesh inference on a dedicated QThread.

    Signals:
        - gaze_updated(float, float): Normalized screen coordinates (x, y) in [0.0, 1.0].
        - gesture_triggered(str): Facial trigger event (e.g. "MOUTH_CLICK").
        - frame_ready(object, float): Annotated frame (or QImage) and current MAR value.
    """

    gaze_updated = pyqtSignal(float, float)
    raw_gaze_updated = pyqtSignal(float, float)
    gesture_triggered = pyqtSignal(str)
    frame_ready = pyqtSignal(object, float)

    def __init__(
        self,
        camera_index: Union[int, str] = 0,
        frame_width: int = 1280,
        frame_height: int = 720,
        fps: int = 30,
        mirror: bool = True,
        max_num_faces: int = 1,
        refine_landmarks: bool = True,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
        threaded: bool = True,
        parent: Optional[QObject] = None,
        gaze_estimator: Optional[GazeEstimator] = None,
        gesture_detector: Optional[GestureDetector] = None,
    ):
        _ensure_qt_app()
        super().__init__(parent)

        self.camera_index = camera_index
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.fps = fps
        self.mirror = mirror
        self.threaded = threaded

        # Initialize GazeEstimator and GestureDetector
        if gaze_estimator is not None:
            self.gaze_estimator = gaze_estimator
        else:
            self.gaze_estimator = GazeEstimator(
                head_weight=config.HEAD_WEIGHT,
                iris_weight=config.IRIS_WEIGHT,
                head_sensitivity_x=config.DEFAULT_HEAD_SENSITIVITY_X,
                head_sensitivity_y=config.DEFAULT_HEAD_SENSITIVITY_Y,
                iris_sensitivity_x=config.DEFAULT_IRIS_SENSITIVITY_X,
                iris_sensitivity_y=config.DEFAULT_IRIS_SENSITIVITY_Y,
                ema_alpha=config.EMA_ALPHA,
            )
            # Auto-load calibration profile if present
            profile_path = getattr(config, "CALIBRATION_PROFILE_PATH", "calibration_profile.json")
            if os.path.exists(profile_path):
                self.gaze_estimator.load_calibration_profile(profile_path)

        if gesture_detector is not None:
            self.gesture_detector = gesture_detector
        else:
            self.gesture_detector = GestureDetector(
                mar_threshold=config.MAR_THRESHOLD,
                release_threshold=config.MAR_RELEASE_THRESHOLD,
                hold_time_sec=config.CLICK_HOLD_TIME_SEC,
                cooldown_sec=config.CLICK_COOLDOWN_SEC,
            )

        # MediaPipe FaceMesh initialization
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh: Optional[Any] = self.mp_face_mesh.FaceMesh(
            max_num_faces=max_num_faces,
            refine_landmarks=refine_landmarks,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )

        self.cap: Optional[cv2.VideoCapture] = None
        self._is_opened = False
        self.is_synthetic = (str(camera_index).lower() == "synthetic")

        # Threading infrastructure
        self._running: bool = False
        self._stop_requested = False
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._latest_frame: Optional[np.ndarray] = None
        self._latest_landmarks: Optional[Any] = None
        self._has_new_frame: bool = False
        self._synthetic_tick: float = 0.0
        self._click_anchor_gaze: Optional[Tuple[float, float]] = None
        self._click_anchor_raw: Optional[Tuple[float, float]] = None

    @property
    def _worker_thread(self):
        """Phase 1 compatibility property."""
        return self

    def is_alive(self) -> bool:
        """Phase 1 compatibility method."""
        return self.isRunning()

    def join(self, timeout: Optional[float] = None) -> None:
        """Phase 1 compatibility method."""
        ms = int((timeout or 2.0) * 1000)
        self.wait(ms)

    def _open_device(self) -> bool:
        """Opens capture device or initializes synthetic camera."""
        if self.is_synthetic:
            self._is_opened = True
            return True

        if self.cap is not None and self.cap.isOpened():
            self._is_opened = True
            return True

        if isinstance(self.camera_index, int) and self.camera_index < 0:
            self._is_opened = False
            return False

        cam_idx = int(self.camera_index) if isinstance(self.camera_index, (int, str)) and str(self.camera_index).isdigit() else 0
        self.cap = cv2.VideoCapture(cam_idx, cv2.CAP_DSHOW if cv2.os.name == "nt" else cv2.CAP_ANY)
        if not self.cap.isOpened():
            self.cap = cv2.VideoCapture(cam_idx)

        if not self.cap.isOpened():
            self._is_opened = False
            return False

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.frame_width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.frame_height)
        self.cap.set(cv2.CAP_PROP_FPS, self.fps)
        self._is_opened = True
        return True

    def start(self, priority: QThread.Priority = QThread.Priority.InheritPriority) -> bool:
        """
        Initializes capture device and starts QThread worker if threaded=True.
        Returns True on success, False otherwise.
        """
        if self._is_opened and self.isRunning():
            return True

        if not self._open_device():
            return False

        self._running = True
        self._stop_requested = False
        self._stop_event.clear()

        if self.threaded:
            super().start(priority)

        return True

    def stop(self) -> None:
        """Signals the QThread to stop using clean boolean flags."""
        self._running = False
        self._stop_requested = True
        self._stop_event.set()

    def wait(self, timeout_ms: int = 2000) -> bool:
        """Waits for the QThread worker to terminate cleanly."""
        if not self.isRunning():
            return True
        return super().wait(timeout_ms)

    def _generate_synthetic_frame(self) -> Tuple[np.ndarray, Optional[Any]]:
        """Generates a synthetic frame and simulated FaceMesh landmarks for testing without a physical camera."""
        frame = np.full((self.frame_height, self.frame_width, 3), (25, 27, 32), dtype=np.uint8)
        self._synthetic_tick += 0.05

        norm_center_x = 0.5 + 0.12 * math.sin(self._synthetic_tick)
        norm_center_y = 0.5 + 0.08 * math.cos(self._synthetic_tick)
        center_x = int(self.frame_width * norm_center_x)
        center_y = int(self.frame_height * norm_center_y)

        # Draw simulated head and facial features
        cv2.circle(frame, (center_x, center_y), 100, (120, 140, 160), -1)
        cv2.circle(frame, (center_x - 35, center_y - 20), 15, (240, 240, 240), -1)
        cv2.circle(frame, (center_x + 35, center_y - 20), 15, (240, 240, 240), -1)
        cv2.circle(frame, (center_x - 35, center_y - 20), 6, (40, 180, 220), -1)
        cv2.circle(frame, (center_x + 35, center_y - 20), 6, (40, 180, 220), -1)

        # Build synthetic 478-landmark object
        class _SyntheticLandmark:
            __slots__ = ("x", "y", "z")
            def __init__(self, x: float, y: float, z: float = 0.0):
                self.x = float(x)
                self.y = float(y)
                self.z = float(z)

        landmarks = [_SyntheticLandmark(norm_center_x, norm_center_y) for _ in range(478)]

        # Nose tip
        landmarks[config.LANDMARK_NOSE_TIP] = _SyntheticLandmark(norm_center_x, norm_center_y)

        # Eyes
        eye_span_y = 0.04
        iris_offset_x = 0.015 * math.sin(self._synthetic_tick * 1.5)
        iris_offset_y = 0.010 * math.cos(self._synthetic_tick * 1.5)

        # Left eye
        landmarks[config.LANDMARK_LEFT_EYE_OUTER] = _SyntheticLandmark(norm_center_x - 0.12, norm_center_y - eye_span_y)
        landmarks[config.LANDMARK_LEFT_EYE_INNER] = _SyntheticLandmark(norm_center_x - 0.04, norm_center_y - eye_span_y)
        landmarks[config.LANDMARK_LEFT_EYE_TOP] = _SyntheticLandmark(norm_center_x - 0.08, norm_center_y - eye_span_y - 0.02)
        landmarks[config.LANDMARK_LEFT_EYE_BOTTOM] = _SyntheticLandmark(norm_center_x - 0.08, norm_center_y - eye_span_y + 0.02)
        landmarks[config.LANDMARK_IRIS_LEFT_CENTER] = _SyntheticLandmark(norm_center_x - 0.08 + iris_offset_x, norm_center_y - eye_span_y + iris_offset_y)

        # Right eye
        landmarks[config.LANDMARK_RIGHT_EYE_INNER] = _SyntheticLandmark(norm_center_x + 0.04, norm_center_y - eye_span_y)
        landmarks[config.LANDMARK_RIGHT_EYE_OUTER] = _SyntheticLandmark(norm_center_x + 0.12, norm_center_y - eye_span_y)
        landmarks[config.LANDMARK_RIGHT_EYE_TOP] = _SyntheticLandmark(norm_center_x + 0.08, norm_center_y - eye_span_y - 0.02)
        landmarks[config.LANDMARK_RIGHT_EYE_BOTTOM] = _SyntheticLandmark(norm_center_x + 0.08, norm_center_y - eye_span_y + 0.02)
        landmarks[config.LANDMARK_IRIS_RIGHT_CENTER] = _SyntheticLandmark(norm_center_x + 0.08 + iris_offset_x, norm_center_y - eye_span_y + iris_offset_y)

        # Mouth (periodically open mouth to simulate facial click triggers)
        cycle = int(self._synthetic_tick * 10) % 80
        mouth_opening = 0.055 if cycle in (30, 31, 32, 33) else 0.020
        landmarks[config.LANDMARK_MOUTH_CORNER_LEFT] = _SyntheticLandmark(norm_center_x - 0.05, norm_center_y + 0.08)
        landmarks[config.LANDMARK_MOUTH_CORNER_RIGHT] = _SyntheticLandmark(norm_center_x + 0.05, norm_center_y + 0.08)
        landmarks[config.LANDMARK_MOUTH_LIP_TOP] = _SyntheticLandmark(norm_center_x, norm_center_y + 0.07)
        landmarks[config.LANDMARK_MOUTH_LIP_BOTTOM] = _SyntheticLandmark(norm_center_x, norm_center_y + 0.07 + mouth_opening)

        return frame, landmarks

    def _process_one_frame(self) -> Tuple[Optional[np.ndarray], Optional[Any]]:
        """Internal helper to capture and process a single frame."""
        if self.is_synthetic:
            return self._generate_synthetic_frame()

        if self.cap is None or not self.cap.isOpened():
            return None, None

        ret, frame = self.cap.read()
        if not ret or frame is None:
            return None, None

        if self.mirror:
            frame = cv2.flip(frame, 1)

        landmarks = None
        if self.face_mesh is not None:
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            rgb_frame.flags.writeable = False
            try:
                results = self.face_mesh.process(rgb_frame)
                if results.multi_face_landmarks and len(results.multi_face_landmarks) > 0:
                    landmarks = results.multi_face_landmarks[0]
            except Exception:
                landmarks = None

        return frame, landmarks

    def run(self) -> None:
        """
        QThread run loop.
        Executes OpenCV capture, MediaPipe inference, gaze estimation, and gesture detection.
        CRITICAL: Never touches PyQt6 widgets directly. All communication is via pyqtSignals.
        """
        target_delay = 1.0 / max(1, self.fps)

        while self._running and not self._stop_requested:
            t_start = time.perf_counter()

            frame, landmarks = self._process_one_frame()
            if frame is None:
                time.sleep(0.01)
                continue

            with self._lock:
                self._latest_frame = frame
                self._latest_landmarks = landmarks
                self._has_new_frame = True

            # Gaze estimation
            gx, gy, detected, debug_info = self.gaze_estimator.estimate(landmarks)

            # Gesture detection
            clicked, current_mar, hold_progress = self.gesture_detector.process(landmarks)

            # Annotated frame copy for debug monitor widget
            annotated_frame = frame.copy()
            if landmarks is not None:
                annotated_frame = self.draw_debug_landmarks(annotated_frame, landmarks)

            raw_target = debug_info.get("target_raw", (gx, gy)) if (detected and debug_info) else (gx, gy)

            # Stabilization during mouth-open click hold:
            # Anchors gaze coordinates to pre-click position so jaw drop / facial distortion
            # cannot fling the selector off the target button during confirmation!
            if hold_progress > 0.0:
                if self._click_anchor_gaze is None:
                    self._click_anchor_gaze = (float(gx), float(gy))
                if self._click_anchor_raw is None:
                    self._click_anchor_raw = (float(raw_target[0]), float(raw_target[1]))
                emit_gx, emit_gy = self._click_anchor_gaze
                emit_raw_x, emit_raw_y = self._click_anchor_raw
            else:
                self._click_anchor_gaze = None
                self._click_anchor_raw = None
                emit_gx, emit_gy = float(gx), float(gy)
                emit_raw_x, emit_raw_y = float(raw_target[0]), float(raw_target[1])

            # Thread-safe signal dispatching
            self.gaze_updated.emit(emit_gx, emit_gy)
            self.raw_gaze_updated.emit(emit_raw_x, emit_raw_y)
            if clicked:
                self.gesture_triggered.emit("MOUTH_CLICK")
            self.frame_ready.emit(annotated_frame, float(current_mar))

            elapsed = time.perf_counter() - t_start
            sleep_time = max(0.001, target_delay - elapsed)
            time.sleep(sleep_time)

    def read_frame(self) -> Tuple[bool, Optional[np.ndarray], Optional[Any]]:
        """
        Reads one frame and processes FaceMesh landmarks.
        Threaded mode: returns latest processed frame.
        Synchronous mode: captures directly.
        """
        if not self._is_opened:
            if not self.start():
                return False, None, None

        if self.threaded:
            with self._lock:
                if self._latest_frame is None:
                    return False, None, None
                return True, self._latest_frame.copy(), self._latest_landmarks

        frame, landmarks = self._process_one_frame()
        if frame is None:
            return False, None, None
        return True, frame, landmarks

    def draw_debug_landmarks(
        self,
        frame: np.ndarray,
        face_landmarks: Any,
        draw_iris: bool = True,
        draw_mouth: bool = True,
        draw_nose: bool = True,
    ) -> np.ndarray:
        """Renders key landmark points (iris, lips, nose) onto the frame."""
        if face_landmarks is None or frame is None:
            return frame

        landmarks = getattr(face_landmarks, "landmark", face_landmarks)
        h, w = frame.shape[:2]

        def get_pt(idx: int) -> Tuple[int, int]:
            p = landmarks[idx]
            return int(p.x * w), int(p.y * h)

        try:
            if draw_nose:
                nose_pt = get_pt(config.LANDMARK_NOSE_TIP)
                cv2.circle(frame, nose_pt, 4, (0, 255, 255), -1)

            if draw_iris:
                l_iris = get_pt(config.LANDMARK_IRIS_LEFT_CENTER)
                r_iris = get_pt(config.LANDMARK_IRIS_RIGHT_CENTER)
                cv2.circle(frame, l_iris, 3, (0, 220, 255), -1)
                cv2.circle(frame, r_iris, 3, (0, 220, 255), -1)

                for c_idx in (
                    config.LANDMARK_LEFT_EYE_OUTER,
                    config.LANDMARK_LEFT_EYE_INNER,
                    config.LANDMARK_RIGHT_EYE_OUTER,
                    config.LANDMARK_RIGHT_EYE_INNER,
                ):
                    cv2.circle(frame, get_pt(c_idx), 2, (180, 180, 180), -1)

            if draw_mouth:
                m_top = get_pt(config.LANDMARK_MOUTH_LIP_TOP)
                m_bot = get_pt(config.LANDMARK_MOUTH_LIP_BOTTOM)
                m_l = get_pt(config.LANDMARK_MOUTH_CORNER_LEFT)
                m_r = get_pt(config.LANDMARK_MOUTH_CORNER_RIGHT)
                cv2.circle(frame, m_top, 3, (0, 255, 0), -1)
                cv2.circle(frame, m_bot, 3, (0, 255, 0), -1)
                cv2.circle(frame, m_l, 3, (0, 165, 255), -1)
                cv2.circle(frame, m_r, 3, (0, 165, 255), -1)
                cv2.line(frame, m_top, m_bot, (0, 255, 120), 1)

        except (IndexError, AttributeError):
            pass

        return frame

    @staticmethod
    def frame_to_qimage(frame: Optional[np.ndarray]) -> Optional[Any]:
        """
        Converts an OpenCV BGR frame to a PyQt6 QImage safely.
        Enforces contiguous memory layout and deep copy (.copy()) to guarantee
        independent memory ownership and prevent memory leaks or segfaults.
        """
        if frame is None or frame.size == 0:
            return None
        try:
            from PyQt6.QtGui import QImage
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            rgb = np.ascontiguousarray(rgb)
            h, w, ch = rgb.shape
            bytes_per_line = ch * w
            return QImage(rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888).copy()
        except Exception:
            return None

    def release(self) -> None:
        """
        Releases capture device, stops QThread worker cleanly, and closes FaceMesh.
        Idempotent.
        """
        self.stop()
        if self.isRunning():
            try:
                self.wait(2000)
            except Exception:
                pass

        if self.cap is not None:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None

        if self.face_mesh is not None:
            try:
                self.face_mesh.close()
            except Exception:
                pass
            self.face_mesh = None

        self._is_opened = False

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
