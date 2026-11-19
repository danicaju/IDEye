"""
Camera Tracker Module for IDEye (Phase 2)
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
    import ideye.config as config
    from ideye.core.gaze_estimator import GazeEstimator
    from ideye.core.gesture_detector import GestureDetector
    from ideye.core.health_guard import HealthGuard
    from ideye.core.lighting_compensator import LightingCompensator
    from ideye.core.eco_power_manager import EcoPowerManager
except ImportError:
    import config
    from core.gaze_estimator import GazeEstimator
    from core.gesture_detector import GestureDetector
    from core.health_guard import HealthGuard
    from core.lighting_compensator import LightingCompensator
    from core.eco_power_manager import EcoPowerManager


from ideye.core.camera_device import CameraDeviceMixin
from ideye.core.camera_debug import CameraDebugMixin



def _ensure_qt_app():
    """Ensures a QCoreApplication exists so QThread and signals operate safely."""
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication(sys.argv if hasattr(sys, 'argv') else [])
    return app


class CameraTracker(CameraDeviceMixin, CameraDebugMixin, QThread):
    """
    Manages OpenCV video capture and MediaPipe FaceMesh inference on a dedicated QThread.

    Signals:
        - gaze_updated(float, float): Normalized screen coordinates (x, y) in [0.0, 1.0].
        - gesture_triggered(str): Facial trigger event (e.g. "MOUTH_CLICK").
        - frame_ready(object, float): Annotated frame (or QImage) and current MAR value.
    """

    gaze_updated = pyqtSignal(float, float)
    raw_gaze_updated = pyqtSignal(float, float)
    raw_components_updated = pyqtSignal(float, float, float, float)
    face_lost = pyqtSignal()
    health_alert = pyqtSignal(str)
    gesture_triggered = pyqtSignal(str)
    frame_ready = pyqtSignal(object, float)
    power_state_changed = pyqtSignal(str)

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
        self._paused = False
        self.eco_manager = EcoPowerManager(
            enabled=bool(getattr(config, "ECO_SLEEP_ENABLED", True))
        )
        self._last_power_state = self.eco_manager.current_power_state
        self.mirror = mirror
        self.threaded = threaded

        # Initialize GazeEstimator and GestureDetector
        if gaze_estimator is not None:
            self.gaze_estimator = gaze_estimator
            if hasattr(self.gaze_estimator, "head_yaw_sign"):
                self.gaze_estimator.head_yaw_sign = 1.0 if self.mirror else -1.0
        else:
            self.gaze_estimator = GazeEstimator(
                head_weight=config.HEAD_WEIGHT,
                iris_weight=config.IRIS_WEIGHT,
                head_sensitivity_x=config.DEFAULT_HEAD_SENSITIVITY_X,
                head_sensitivity_y=config.DEFAULT_HEAD_SENSITIVITY_Y,
                iris_sensitivity_x=config.DEFAULT_IRIS_SENSITIVITY_X,
                iris_sensitivity_y=config.DEFAULT_IRIS_SENSITIVITY_Y,
                ema_alpha=config.EMA_ALPHA,
                tracking_mode=getattr(config, "DEFAULT_TRACKING_MODE", "PURE_IRIS"),
                mirror=self.mirror,
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
                wink_min_hold_sec=config.WINK_MIN_HOLD_SEC,
                wink_max_hold_sec=config.WINK_MAX_HOLD_SEC,
                wink_cooldown_sec=config.WINK_COOLDOWN_SEC,
                wink_opposite_margin=config.WINK_OPPOSITE_EYE_MARGIN,
                wink_enabled=config.WINK_ENABLED,
                wink_mouth_only=config.WINK_MOUTH_ONLY,
                wink_difficulty=config.WINK_DIFFICULTY,
                wink_distance_compensation=config.WINK_DISTANCE_COMPENSATION,
                wink_min_interocular_dist=config.WINK_MIN_INTEROCULAR_DIST,
                wink_max_roll_deg=config.WINK_MAX_ROLL_DEG,
                wink_max_yaw_ratio=config.WINK_MAX_YAW_RATIO,
                wink_double_window_sec=config.WINK_DOUBLE_WINDOW_SEC,
                wink_double_enabled=config.WINK_CONFIRM_DANGEROUS,
            )

        self.health_guard = HealthGuard(
            enabled=bool(getattr(config, "HEALTH_GUARD_ENABLED", True))
        )
        self.lighting = LightingCompensator(
            enabled=bool(getattr(config, "AUTO_LOW_LIGHT_CLAHE", True))
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
        self._empty_frame_count: int = 0
        self._last_face_lost_emit: float = 0.0
        self._last_reconnect_attempt: float = 0.0

    @property
    def _worker_thread(self):
        """Phase 1 compatibility property."""
        return self

    def set_paused(self, paused: bool) -> None:
        """Pauses the HUD and puts the camera into the 10 FPS eco state."""
        self._paused = bool(paused)
        self.eco_manager.set_paused(self._paused)
        self._emit_power_state()

    def set_eco_enabled(self, enabled: bool) -> None:
        """Enables or disables adaptive framerate scaling at runtime."""
        self.eco_manager.set_enabled(bool(enabled))
        self._emit_power_state()

    @property
    def current_power_state(self) -> str:
        return self.eco_manager.current_power_state

    def _target_delay(self) -> float:
        if self.eco_manager.current_power_state == EcoPowerManager.ACTIVE:
            return 1.0 / max(1.0, float(self.fps))
        return self.eco_manager.frame_interval

    def _emit_power_state(self) -> None:
        state = self.eco_manager.current_power_state
        if state != getattr(self, "_last_power_state", ""):
            self._last_power_state = state
            self.power_state_changed.emit(state)

    def set_cap_mode(self, enabled: bool) -> None:
        """Propagates cap-safe mode to gaze estimator, gesture detector, and lighting compensator."""
        self._cap_mode = bool(enabled)
        if hasattr(self.gaze_estimator, "set_cap_mode"):
            self.gaze_estimator.set_cap_mode(self._cap_mode)
        if hasattr(self.gesture_detector, "set_cap_mode"):
            self.gesture_detector.set_cap_mode(self._cap_mode)
        if hasattr(self.lighting, "set_cap_mode"):
            self.lighting.set_cap_mode(self._cap_mode)

    def is_alive(self) -> bool:
        """Phase 1 compatibility method."""
        return self.isRunning()

    def join(self, timeout: Optional[float] = None) -> None:
        """Phase 1 compatibility method."""
        ms = int((timeout or 2.0) * 1000)
        self.wait(ms)

    def _process_one_frame(self) -> Tuple[Optional[np.ndarray], Optional[Any]]:
        """Internal helper to capture and process a single frame."""
        if self.is_synthetic:
            return self._generate_synthetic_frame()

        if self.cap is None or not self.cap.isOpened():
            return None, None

        try:
            ret, frame = self.cap.read()
        except Exception:
            return None, None
        if not ret or frame is None:
            return None, None

        frame = self._ensure_bgr(frame)
        if frame is None:
            return None, None
        if self.mirror:
            frame = cv2.flip(frame, 1)
        if self.lighting is not None:
            frame = self.lighting.process(frame, landmarks=self._latest_landmarks)
            frame = self._ensure_bgr(frame)
        if frame is None:
            return None, None

        landmarks = None
        if self.face_mesh is not None and frame is not None:
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
        while self._running and not self._stop_requested:
            t_start = time.perf_counter()

            frame, landmarks = self._process_one_frame()
            if frame is None:
                self._empty_frame_count += 1
                self.eco_manager.update(detected=False, paused=self._paused)
                self._emit_power_state()
                now = time.time()
                if now - self._last_face_lost_emit >= 0.5:
                    self._last_face_lost_emit = now
                    self.face_lost.emit()
                if (
                    not self.is_synthetic
                    and self._empty_frame_count >= 10
                    and now - self._last_reconnect_attempt >= 2.0
                ):
                    self._last_reconnect_attempt = now
                    self._safe_reconnect()
                time.sleep(max(0.01, min(0.5, self._target_delay())))
                continue

            self._empty_frame_count = 0
            self._last_reconnect_attempt = 0.0

            with self._lock:
                self._latest_frame = frame
                self._latest_landmarks = landmarks
                self._has_new_frame = True

            # Gaze estimation
            gx, gy, detected, debug_info = self.gaze_estimator.estimate(landmarks)
            self.eco_manager.update(detected=bool(detected), paused=self._paused)
            self._emit_power_state()

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
            if detected:
                self._last_face_lost_emit = 0.0
                self.raw_components_updated.emit(
                    float(self.gaze_estimator.last_raw_head_x),
                    float(self.gaze_estimator.last_raw_head_y),
                    float(self.gaze_estimator.last_raw_iris_x),
                    float(self.gaze_estimator.last_raw_iris_y),
                )
            else:
                now = time.time()
                if now - self._last_face_lost_emit >= 0.5:
                    self._last_face_lost_emit = now
                    self.face_lost.emit()

            if self.health_guard is not None:
                alert = self.health_guard.process(landmarks, tracking_active=bool(detected))
                if alert:
                    self.health_alert.emit(alert)

            # Emit all triggered gestures (MOUTH_CLICK, WINK_LEFT, WINK_RIGHT)
            gestures = getattr(self.gesture_detector, "triggered_gestures", [])
            if not gestures and clicked:
                gestures = ["MOUTH_CLICK"]
            for gesture in gestures:
                self.gesture_triggered.emit(gesture)

            self.frame_ready.emit(annotated_frame, float(current_mar))

            elapsed = time.perf_counter() - t_start
            sleep_time = max(0.001, self._target_delay() - elapsed)
            time.sleep(sleep_time)

    def get_latest_landmarks(self) -> Optional[Any]:
        """Returns the most recent MediaPipe landmarks under the tracker lock."""
        with self._lock:
            return self._latest_landmarks

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

