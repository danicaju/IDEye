"""Iris and eye geometry extraction."""

from typing import Any, Optional, Tuple, Dict, List, Union
from collections import deque
import math
import os
import json
import re
import shutil
import time
import threading
import numpy as np


try:
    import ideye.config as config
except ImportError:
    try:
        import config
    except ImportError:
        config = None

TRACKING_MODE_PURE_IRIS = getattr(config, "TRACKING_MODE_PURE_IRIS", "PURE_IRIS") if config else "PURE_IRIS"
TRACKING_MODE_HYBRID = getattr(config, "TRACKING_MODE_HYBRID", "HYBRID") if config else "HYBRID"
TRACKING_MODE_HEAD_PRIMARY = getattr(config, "TRACKING_MODE_HEAD_PRIMARY", "HEAD_PRIMARY") if config else "HEAD_PRIMARY"
DEFAULT_TRACKING_MODE = getattr(config, "DEFAULT_TRACKING_MODE", TRACKING_MODE_HEAD_PRIMARY) if config else TRACKING_MODE_HEAD_PRIMARY


from ideye.core.logging_config import get_logger

logger = get_logger(__name__)



class GazeGeometryMixin:
    """Iris and eye geometry extraction."""

    @staticmethod
    def _finite_unit(value: Any, default: float = 0.5) -> float:
        """Coerces a value to a finite normalized [0, 1] coordinate."""
        try:
            number = float(value)
        except (TypeError, ValueError, OverflowError):
            return float(default)
        if not math.isfinite(number):
            return float(default)
        return float(max(0.0, min(1.0, number)))

    @staticmethod
    def _safe_coord(point: Any) -> Tuple[float, float]:
        """Safely extracts finite x/y from a landmark object or tuple/list."""
        try:
            x, y = float(point.x), float(point.y)
        except (AttributeError, TypeError):
            try:
                x, y = float(point[0]), float(point[1])
            except (IndexError, TypeError, ValueError, OverflowError):
                return 0.5, 0.5
        except (ValueError, OverflowError):
            return 0.5, 0.5
        if not (math.isfinite(x) and math.isfinite(y)):
            return 0.5, 0.5
        return float(max(0.0, min(1.0, x))), float(max(0.0, min(1.0, y)))

    def _orbital_points(
        self, landmarks: Any, indices: Tuple[int, ...]
    ) -> List[Tuple[float, float]]:
        points: List[Tuple[float, float]] = []
        for idx in indices:
            try:
                point = self._safe_coord(landmarks[idx])
            except (IndexError, KeyError, TypeError):
                continue
            if point != (0.5, 0.5):
                points.append(point)
        return points

    def _eye_orbital_geometry(
        self, landmarks: Any, indices: Tuple[int, ...], iris_indices: Tuple[int, ...]
    ) -> Optional[Dict[str, float]]:
        """Returns multi-anchor orbital center, size, iris center and EAR."""
        orbital = self._orbital_points(landmarks, indices)
        if len(orbital) < 3:
            return None
        xs = [p[0] for p in orbital]
        ys = [p[1] for p in orbital]
        width = max(max(xs) - min(xs), 1e-6)
        height = max(max(ys) - min(ys), 1e-6)
        center_x = sum(xs) / len(xs)
        center_y = sum(ys) / len(ys)

        iris_points = self._orbital_points(landmarks, iris_indices)
        if not iris_points:
            try:
                iris_points = [self._safe_coord(landmarks[iris_indices[0]])]
            except (IndexError, KeyError, TypeError):
                return None
        iris_x = sum(p[0] for p in iris_points) / len(iris_points)
        iris_y = sum(p[1] for p in iris_points) / len(iris_points)
        return {
            "center_x": center_x,
            "center_y": center_y,
            "width": width,
            "height": height,
            "iris_x": iris_x,
            "iris_y": iris_y,
            "ear": height / width,
        }

    def _extract_iris_ratio(self, landmarks: Any) -> Tuple[float, float]:
        """PURE_IRIS: 6-point orbital normalization + 5-frame median + roll comp."""
        eps = 1e-6
        try:
            left = self._eye_orbital_geometry(
                landmarks,
                (33, 133, 159, 145, 158, 153),
                (468, 469, 470, 471, 472),
            )
            right = self._eye_orbital_geometry(
                landmarks,
                (362, 263, 386, 374, 385, 380),
                (473, 474, 475, 476, 477),
            )
            if left is None and right is None:
                return self.last_valid_iris_x, self.last_valid_iris_y

            closed_l = left is not None and (
                left["ear"] < self.ear_blink_threshold
                or left["height"] < self.blink_threshold
            )
            closed_r = right is not None and (
                right["ear"] < self.ear_blink_threshold
                or right["height"] < self.blink_threshold
            )
            if (left is None or closed_l) and (right is None or closed_r):
                self.is_blinking = True
                return self.last_valid_iris_x, self.last_valid_iris_y
            self.is_blinking = False

            if left is not None and right is not None:
                roll = math.atan2(
                    right["center_y"] - left["center_y"],
                    right["center_x"] - left["center_x"],
                )
            else:
                roll = 0.0
            self._last_iris_roll = roll
            cos_r, sin_r = math.cos(roll), math.sin(roll)

            ratios: List[Tuple[float, float]] = []
            for eye in (left, right):
                if eye is None:
                    continue
                if eye is left and closed_l:
                    continue
                if eye is right and closed_r:
                    continue
                dx = eye["iris_x"] - eye["center_x"]
                dy = eye["iris_y"] - eye["center_y"]
                # Rotate the relative iris vector back into screen axes.
                rx = dx * cos_r + dy * sin_r
                ry = -dx * sin_r + dy * cos_r
                ratio_x = 0.5 + rx / max(eye["width"], eps)
                ratio_y = 0.5 + ry / max(eye["height"], 0.70 * eye["width"], eps)
                ratios.append(
                    (
                        max(0.0, min(1.0, ratio_x)),
                        max(0.0, min(1.0, ratio_y)),
                    )
                )
            if not ratios:
                return self.last_valid_iris_x, self.last_valid_iris_y

            raw_x = sum(r[0] for r in ratios) / len(ratios)
            raw_y = sum(r[1] for r in ratios) / len(ratios)

            # Temporal median rejects single-frame corneal spikes.
            self._iris_history.append((raw_x, raw_y))
            if len(self._iris_history) >= 2:
                arr = np.asarray(self._iris_history, dtype=np.float64)
                median = np.median(arr, axis=0)
                clamped_x = float(median[0])
                clamped_y = float(median[1])
            else:
                clamped_x, clamped_y = raw_x, raw_y

            # Soft noise gate for residual micro-jitter.
            d_raw = math.hypot(
                clamped_x - self.last_valid_iris_x,
                clamped_y - self.last_valid_iris_y,
            )
            raw_gate = 0.035
            if d_raw < raw_gate:
                weight = (d_raw / raw_gate) ** 2
                clamped_x = (1.0 - weight) * self.last_valid_iris_x + weight * clamped_x
                clamped_y = (1.0 - weight) * self.last_valid_iris_y + weight * clamped_y

            self.last_valid_iris_x = float(np.clip(clamped_x, 0.0, 1.0))
            self.last_valid_iris_y = float(np.clip(clamped_y, 0.0, 1.0))
            return self.last_valid_iris_x, self.last_valid_iris_y
        except (IndexError, AttributeError, TypeError, ValueError):
            return self.last_valid_iris_x, self.last_valid_iris_y

    def _extract_iris_ratio_legacy(self, landmarks: Any) -> Tuple[float, float]:
        """
        Calculates relative normalized horizontal and vertical iris position within
        both eye contours, safe against ZeroDivisionError and eye closure blinks.
        Enhanced with asymmetric single-eye squint/blink handling and raw noise gating.
        """
        eps = 1e-6
        try:
            # Left eye
            p_iris_l = landmarks[self.iris_left_center_idx]
            p_inner_l = landmarks[self.left_eye_inner_idx]
            p_outer_l = landmarks[self.left_eye_outer_idx]
            p_top_l = landmarks[self.left_eye_top_idx]
            p_bottom_l = landmarks[self.left_eye_bottom_idx]

            ix_l, iy_l = self._safe_coord(p_iris_l)
            in_x_l, in_y_l = self._safe_coord(p_inner_l)
            out_x_l, out_y_l = self._safe_coord(p_outer_l)
            top_x_l, top_y_l = self._safe_coord(p_top_l)
            bot_x_l, bot_y_l = self._safe_coord(p_bottom_l)

            # Right eye
            p_iris_r = landmarks[self.iris_right_center_idx]
            p_inner_r = landmarks[self.right_eye_inner_idx]
            p_outer_r = landmarks[self.right_eye_outer_idx]
            p_top_r = landmarks[self.right_eye_top_idx]
            p_bottom_r = landmarks[self.right_eye_bottom_idx]

            ix_r, iy_r = self._safe_coord(p_iris_r)
            in_x_r, in_y_r = self._safe_coord(p_inner_r)
            out_x_r, out_y_r = self._safe_coord(p_outer_r)
            top_x_r, top_y_r = self._safe_coord(p_top_r)
            bot_x_r, bot_y_r = self._safe_coord(p_bottom_r)

            # Horizontal canthal eye widths
            min_x_l = min(in_x_l, out_x_l)
            max_x_l = max(in_x_l, out_x_l)
            width_l = max(max_x_l - min_x_l, eps)

            min_x_r = min(in_x_r, out_x_r)
            max_x_r = max(in_x_r, out_x_r)
            width_r = max(max_x_r - min_x_r, eps)

            # Vertical eyelid openings
            height_l = max(abs(top_y_l - bot_y_l), 0.0)
            height_r = max(abs(top_y_r - bot_y_r), 0.0)

            # Scale-invariant Eye Aspect Ratio (EAR)
            ear_l = height_l / width_l
            ear_r = height_r / width_r

            # True blink occurs when both eye aspect ratios collapse (or absolute height is tiny)
            is_closed_l = (ear_l < self.ear_blink_threshold) or (height_l < self.blink_threshold)
            is_closed_r = (ear_r < self.ear_blink_threshold) or (height_r < self.blink_threshold)

            if is_closed_l and is_closed_r:
                self.is_blinking = True
                return self.last_valid_iris_x, self.last_valid_iris_y

            self.is_blinking = False

            # Left eye ratios
            ratio_x_l = max(0.0, min(1.0, (ix_l - min_x_l) / width_l))
            nominal_h_l = max(height_l, 0.70 * width_l, eps)
            center_y_l = (top_y_l + bot_y_l) * 0.5
            ratio_y_l = max(0.0, min(1.0, 0.5 + (iy_l - center_y_l) / nominal_h_l))

            # Right eye ratios
            ratio_x_r = max(0.0, min(1.0, (ix_r - min_x_r) / width_r))
            nominal_h_r = max(height_r, 0.70 * width_r, eps)
            center_y_r = (top_y_r + bot_y_r) * 0.5
            ratio_y_r = max(0.0, min(1.0, 0.5 + (iy_r - center_y_r) / nominal_h_r))

            # Squint / asymmetric blink handling: if one eye is occluded, use the open one
            if is_closed_l and not is_closed_r:
                avg_x = ratio_x_r
                avg_y = ratio_y_r
            elif is_closed_r and not is_closed_l:
                avg_x = ratio_x_l
                avg_y = ratio_y_l
            else:
                avg_x = (ratio_x_l + ratio_x_r) * 0.5
                avg_y = (ratio_y_l + ratio_y_r) * 0.5

            clamped_x = max(0.0, min(1.0, float(avg_x)))
            clamped_y = max(0.0, min(1.0, float(avg_y)))

            # Soft quadratic noise gating for raw webcam micro-jitter (1-3 px flicker)
            d_raw = math.hypot(clamped_x - self.last_valid_iris_x, clamped_y - self.last_valid_iris_y)
            raw_gate = 0.035
            if d_raw < raw_gate:
                weight = (d_raw / raw_gate) ** 2
                clamped_x = (1.0 - weight) * self.last_valid_iris_x + weight * clamped_x
                clamped_y = (1.0 - weight) * self.last_valid_iris_y + weight * clamped_y

            self.last_valid_iris_x = clamped_x
            self.last_valid_iris_y = clamped_y

            return clamped_x, clamped_y

        except (IndexError, AttributeError, TypeError):
            return self.last_valid_iris_x, self.last_valid_iris_y

    def set_cap_mode(self, enabled: bool) -> None:
        """
        Toggles cap/visor-safe cranial head tracking.
        Shifts weights entirely to subnasal landmarks (nose tip & columella)
        eliminating dependence on the glabella/forehead.
        """
        self.cap_mode = bool(enabled)
        with self._lock:
            if self.cap_mode:
                self.head_anchor_weights = self._cap_safe_head_anchor_weights
            else:
                self.head_anchor_weights = self._default_head_anchor_weights
