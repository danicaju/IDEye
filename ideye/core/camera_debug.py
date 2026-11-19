"""Synthetic frames and debug drawing for CameraTracker."""

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



class CameraDebugMixin:
    """Synthetic gaze frames and landmark overlays."""

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
        eye_top_l = norm_center_y - eye_span_y - 0.02
        eye_bot_l = norm_center_y - eye_span_y + 0.02
        landmarks[config.LANDMARK_LEFT_EYE_OUTER] = _SyntheticLandmark(norm_center_x - 0.12, norm_center_y - eye_span_y)
        landmarks[config.LANDMARK_LEFT_EYE_INNER] = _SyntheticLandmark(norm_center_x - 0.04, norm_center_y - eye_span_y)
        landmarks[config.LANDMARK_LEFT_EYE_TOP] = _SyntheticLandmark(norm_center_x - 0.08, eye_top_l)
        landmarks[config.LANDMARK_LEFT_EYE_BOTTOM] = _SyntheticLandmark(norm_center_x - 0.08, eye_bot_l)
        landmarks[160] = _SyntheticLandmark(norm_center_x - 0.10, eye_top_l)
        landmarks[158] = _SyntheticLandmark(norm_center_x - 0.06, eye_top_l)
        landmarks[144] = _SyntheticLandmark(norm_center_x - 0.10, eye_bot_l)
        landmarks[153] = _SyntheticLandmark(norm_center_x - 0.06, eye_bot_l)
        landmarks[config.LANDMARK_IRIS_LEFT_CENTER] = _SyntheticLandmark(norm_center_x - 0.08 + iris_offset_x, norm_center_y - eye_span_y + iris_offset_y)

        # Right eye
        eye_top_r = norm_center_y - eye_span_y - 0.02
        eye_bot_r = norm_center_y - eye_span_y + 0.02
        landmarks[config.LANDMARK_RIGHT_EYE_INNER] = _SyntheticLandmark(norm_center_x + 0.04, norm_center_y - eye_span_y)
        landmarks[config.LANDMARK_RIGHT_EYE_OUTER] = _SyntheticLandmark(norm_center_x + 0.12, norm_center_y - eye_span_y)
        landmarks[config.LANDMARK_RIGHT_EYE_TOP] = _SyntheticLandmark(norm_center_x + 0.08, eye_top_r)
        landmarks[config.LANDMARK_RIGHT_EYE_BOTTOM] = _SyntheticLandmark(norm_center_x + 0.08, eye_bot_r)
        landmarks[385] = _SyntheticLandmark(norm_center_x + 0.06, eye_top_r)
        landmarks[387] = _SyntheticLandmark(norm_center_x + 0.10, eye_top_r)
        landmarks[380] = _SyntheticLandmark(norm_center_x + 0.06, eye_bot_r)
        landmarks[373] = _SyntheticLandmark(norm_center_x + 0.10, eye_bot_r)
        landmarks[config.LANDMARK_IRIS_RIGHT_CENTER] = _SyntheticLandmark(norm_center_x + 0.08 + iris_offset_x, norm_center_y - eye_span_y + iris_offset_y)

        # Mouth (periodically open mouth to simulate facial click triggers)
        cycle = int(self._synthetic_tick * 10) % 80
        mouth_opening = 0.055 if cycle in (30, 31, 32, 33) else 0.020
        landmarks[config.LANDMARK_MOUTH_CORNER_LEFT] = _SyntheticLandmark(norm_center_x - 0.05, norm_center_y + 0.08)
        landmarks[config.LANDMARK_MOUTH_CORNER_RIGHT] = _SyntheticLandmark(norm_center_x + 0.05, norm_center_y + 0.08)
        landmarks[config.LANDMARK_MOUTH_LIP_TOP] = _SyntheticLandmark(norm_center_x, norm_center_y + 0.07)
        landmarks[config.LANDMARK_MOUTH_LIP_BOTTOM] = _SyntheticLandmark(norm_center_x, norm_center_y + 0.07 + mouth_opening)

        return frame, landmarks

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
        if frame is None or not isinstance(frame, np.ndarray) or frame.size == 0:
            return None
        try:
            from PyQt6.QtGui import QImage
            if frame.dtype != np.uint8:
                frame = np.nan_to_num(frame, nan=0.0, posinf=255.0, neginf=0.0)
                frame = np.clip(frame, 0, 255).astype(np.uint8)
            if frame.ndim == 2:
                rgb = cv2.cvtColor(frame, cv2.COLOR_GRAY2RGB)
            elif frame.ndim == 3 and frame.shape[2] == 1:
                rgb = cv2.cvtColor(frame[:, :, 0], cv2.COLOR_GRAY2RGB)
            elif frame.ndim == 3 and frame.shape[2] == 3:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            elif frame.ndim == 3 and frame.shape[2] == 4:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGRA2RGB)
            else:
                return None
            rgb = np.ascontiguousarray(rgb)
            h, w, ch = rgb.shape
            bytes_per_line = ch * w
            return QImage(rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888).copy()
        except Exception:
            return None
