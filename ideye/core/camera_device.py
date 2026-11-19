"""Capture device lifecycle for CameraTracker."""

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


import logging

logger = logging.getLogger(__name__)


class CameraDeviceMixin:
    """Open, reconnect, start/stop and release the capture device."""

    def _ensure_bgr(self, frame: Optional[np.ndarray]) -> Optional[np.ndarray]:
        """Normalizes grayscale/RGBA frames to a safe contiguous BGR image."""
        if frame is None or not isinstance(frame, np.ndarray) or frame.size == 0:
            return None
        try:
            if frame.ndim == 2:
                return cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
            if frame.ndim != 3:
                return None
            channels = int(frame.shape[2])
            if channels == 1:
                return cv2.cvtColor(frame[:, :, 0], cv2.COLOR_GRAY2BGR)
            if channels == 3:
                return frame
            if channels == 4:
                return cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
        except Exception:
            return None
        return None

    def _close_capture(self) -> None:
        """Releases the capture device without touching Qt thread state."""
        if self.cap is not None:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None
        self._is_opened = False

    def _safe_reconnect(self) -> bool:
        """Best-effort camera reopen after a hot-unplug, never raising."""
        if self.is_synthetic or self._stop_requested:
            return False
        try:
            self._close_capture()
            if self._open_device():
                self._empty_frame_count = 0
                return True
        except Exception as exc:
            logger.debug("[CameraTracker] Reconnect failed: %s", exc)
        return False

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
            self._close_capture()

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
