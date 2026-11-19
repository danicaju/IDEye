"""Tracking modes, static pinning and combined deltas."""

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



class GazeMappingMixin:
    """Tracking modes, static pinning and combined deltas."""

    def _extract_head_yaw(self, landmarks: Any) -> float:
        """Rough yaw in degrees from nose vs. left/right ear landmarks."""
        try:
            left = self._safe_coord(landmarks[234])
            right = self._safe_coord(landmarks[454])
            nose = self._safe_coord(landmarks[self.nose_tip_idx])
            ear_span = math.hypot(right[0] - left[0], right[1] - left[1])
            if ear_span < 1e-6:
                return 0.0
            center_x = (left[0] + right[0]) * 0.5
            return self.head_yaw_sign * float(math.degrees(math.atan2(nose[0] - center_x, ear_span * 0.5)))
        except (IndexError, KeyError, TypeError, ValueError):
            return 0.0

    def set_tracking_mode(self, mode: str) -> None:
        """
        Switches the active gaze tracking mode:
        - 'PURE_IRIS': 100% iris tracking, 0% head influence, with non-linear horizontal edge reach.
        - 'HYBRID': Head + Iris fusion with VOR (Vestibulo-Ocular Reflex) counter-rotation compensation.
        - 'HEAD_PRIMARY': 95% head pose, 5% iris for users with ocular mobility restrictions.
        """
        mode_upper = str(mode).upper()
        previous = getattr(self, "tracking_mode", None)
        if mode_upper in ("PURE_IRIS", "HYBRID", "HEAD_PRIMARY"):
            self.tracking_mode = mode_upper
        else:
            self.tracking_mode = "HYBRID"

        # A hot mode change must not inherit filter history from another
        # biological source. Reset the 1-Euro filters, iris median queue and
        # hysteresis pin, then continue from the last stable position.
        try:
            now = time.perf_counter()
            self.one_euro_x.reset(now, self.smoothed_x)
            self.one_euro_y.reset(now, self.smoothed_y)
            self._iris_history.clear()
            self._last_filtered_iris = None
            self._effective_iris_weight = self.iris_weight
            self._iris_velocity = 0.0
            self._is_pinned = False
            self._pinned_pos = None
            self._static_target = None
            self._static_last_filtered = None
            self._static_quiet_frames = 0
            self._pin_release_ramp = 1.0
            self.fixation_anchor_x = self.smoothed_x
            self.fixation_anchor_y = self.smoothed_y
        except Exception:
            pass

    def _apply_static_pinning(self, x: float, y: float) -> Tuple[float, float]:
        """Schmitt-trigger static pinning: exact zero drift while at rest."""
        cx = self._finite_unit(x)
        cy = self._finite_unit(y)

        if self._is_pinned:
            if self._pinned_pos is None:
                self._pinned_pos = (cx, cy)
                self._static_last_filtered = (cx, cy)
                return cx, cy
            px, py = self._pinned_pos
            ref = self._static_target if self._static_target is not None else (cx, cy)
            dist = math.hypot(ref[0] - px, ref[1] - py)
            if dist < self.static_breakout_radius:
                return px, py
            # Intentional breakout: snap for large excursions, short ramp for small ones.
            self._is_pinned = False
            self._static_quiet_frames = 0
            self._static_last_filtered = (cx, cy)
            if dist > 3.0 * self.static_breakout_radius:
                self._pin_release_ramp = 1.0
                self._pinned_pos = None
                return cx, cy
            self._pin_release_ramp = 0.35
            ox = px + (cx - px) * self._pin_release_ramp
            oy = py + (cy - py) * self._pin_release_ramp
            return float(np.clip(ox, 0.0, 1.0)), float(np.clip(oy, 0.0, 1.0))

        # In motion: continue a short ramp from the old pinned position.
        if self._pinned_pos is not None and self._pin_release_ramp < 1.0:
            px, py = self._pinned_pos
            if math.hypot(cx - px, cy - py) > 3.0 * self.static_breakout_radius:
                self._pin_release_ramp = 1.0
                self._pinned_pos = None
                self._static_last_filtered = (cx, cy)
                return cx, cy
            self._pin_release_ramp = min(1.0, self._pin_release_ramp + 0.35)
            ox = px + (cx - px) * self._pin_release_ramp
            oy = py + (cy - py) * self._pin_release_ramp
            if self._pin_release_ramp >= 1.0:
                self._pinned_pos = None
            self._static_last_filtered = (cx, cy)
            return float(np.clip(ox, 0.0, 1.0)), float(np.clip(oy, 0.0, 1.0))

        if self._static_last_filtered is not None:
            dx = cx - self._static_last_filtered[0]
            dy = cy - self._static_last_filtered[1]
            velocity = math.hypot(dx, dy)
        else:
            velocity = 0.0
        target = self._static_target
        target_gap = (
            math.hypot(cx - target[0], cy - target[1]) if target is not None else 0.0
        )
        if velocity < self.static_lock_radius and target_gap < self.static_lock_radius:
            self._static_quiet_frames += 1
        else:
            self._static_quiet_frames = 0
        self._static_last_filtered = (cx, cy)

        if self._static_quiet_frames >= self.static_lock_frames:
            # Snap the pin to the filtered target (not the asymptotically
            # approaching filter output) so extreme targets reach 0.0/1.0.
            target = self._static_target
            if target is not None and math.hypot(cx - target[0], cy - target[1]) < self.static_breakout_radius:
                self._pinned_pos = (float(target[0]), float(target[1]))
            else:
                self._pinned_pos = (cx, cy)
            self._is_pinned = True
            self._static_quiet_frames = 0
            self._pin_release_ramp = 1.0
            return self._pinned_pos
        return cx, cy

    def _compute_effective_iris_weight(self, iris_x: float, iris_y: float) -> float:
        """Saccade-gated HYBRID weight: 0.08 at rest, up to 0.55 during saccades."""
        if self._last_filtered_iris is None:
            self._iris_velocity = 0.0
        else:
            self._iris_velocity = math.hypot(
                iris_x - self._last_filtered_iris[0],
                iris_y - self._last_filtered_iris[1],
            )
        self._last_filtered_iris = (iris_x, iris_y)
        norm = min(1.0, self._iris_velocity / max(self.iris_saccade_threshold, 1e-6))
        target = self.hybrid_iris_weight_rest + (
            self.hybrid_iris_weight_saccade - self.hybrid_iris_weight_rest
        ) * norm
        # Smooth the weight so the transition is not perceptible.
        self._effective_iris_weight += 0.25 * (target - self._effective_iris_weight)
        return self._effective_iris_weight

    def _compute_combined_deltas(
        self,
        delta_head_x: float,
        delta_head_y: float,
        delta_iris_x: float,
        delta_iris_y: float,
    ) -> Tuple[float, float]:
        """
        Combines head and iris offset vectors based on active tracking mode,
        and applies non-linear ergonomic expansion curves for full-screen reach.
        Protected against non-finite values (NaN/inf).
        """
        # Non-finite protection
        dh_x = float(delta_head_x) if math.isfinite(delta_head_x) else 0.0
        dh_y = float(delta_head_y) if math.isfinite(delta_head_y) else 0.0
        di_x = float(delta_iris_x) if math.isfinite(delta_iris_x) else 0.0
        di_y = float(delta_iris_y) if math.isfinite(delta_iris_y) else 0.0

        if self.tracking_mode == "PURE_IRIS":
            combined_x = di_x
            combined_y = di_y
        elif self.tracking_mode == "HEAD_PRIMARY":
            # Ergonomic head pose optimization:
            # Cervical pitch has a naturally restricted anatomical range compared to yaw.
            # Applying a balanced 1.4x vertical head pitch multiplier (softened from aggressive 2.8x)
            # ensures gentle, fatigue-free head tilts smoothly reach top and bottom rows
            # without exaggerated jumps or ceiling/floor clipping.
            combined_x = 0.95 * dh_x + 0.05 * di_x
            combined_y = (2.8 * dh_y) + (0.05 * di_y)
        else:  # "HYBRID"
            # VOR Decoupling / Compensation:
            # When user turns head left (dh_x < 0) and eyes counter-rotate right (di_x > 0),
            # they have opposite signs. The eye counter-rotation stifles the user's intended
            # head turn. We compensate for this counter-rotation by nudging the effective iris
            # vector in the direction of the head yaw so they do not cancel out.
            if dh_x * di_x < 0:
                vor_correction = self.vor_compensation_factor * dh_x
                effective_iris_x = di_x + vor_correction
            else:
                effective_iris_x = di_x

            if self._dynamic_fusion_active:
                iris_w = max(0.0, min(1.0, self._effective_iris_weight))
                head_w = 1.0 - iris_w
            else:
                iris_w = self.iris_weight
                head_w = self.head_weight
            combined_x = (head_w * dh_x) + (iris_w * effective_iris_x)
            combined_y = (head_w * dh_y) + (iris_w * di_y)

        expanded_x = self._apply_horizontal_expansion_curve(combined_x)
        expanded_y = self._apply_ergonomic_vertical_curve(combined_y)
        return expanded_x, expanded_y

    def calibrate_center(self, face_landmarks: Any, nominal_interocular: float = 0.28) -> bool:
        """
        Quick one-key calibration:
        - Fixes current eye/head position as screen center (0.5, 0.5).
        - Calibrates gain / sensitivity based on user distance from camera (face scale).
        Returns True if calibration succeeded, False if face is missing.
        """
        if face_landmarks is None:
            return False

        try:
            landmarks = getattr(face_landmarks, "landmark", face_landmarks)
            if not landmarks:
                return False

            head_x, head_y = self._extract_head_pos(landmarks)
            iris_x, iris_y = self._extract_iris_ratio(landmarks)

            # Measure interocular distance between outer eye corners (33 and 263)
            p_out_l = landmarks[self.left_eye_outer_idx]
            p_out_r = landmarks[self.right_eye_outer_idx]
            ox_l, oy_l = self._safe_coord(p_out_l)
            ox_r, oy_r = self._safe_coord(p_out_r)
            dx = ox_l - ox_r
            dy = oy_l - oy_r
            face_span = math.sqrt(dx * dx + dy * dy)

            # Adapt sensitivity based on distance scale
            if face_span > 0.05:
                scale = min(2.5, max(0.5, nominal_interocular / face_span))
                self.distance_scale = scale
                self.head_sensitivity_x = self.base_head_sensitivity_x * scale
                self.head_sensitivity_y = self.base_head_sensitivity_y * scale
                self.iris_sensitivity_x = self.base_iris_sensitivity_x * scale
                self.iris_sensitivity_y = self.base_iris_sensitivity_y * scale

            self.neutral_head_x = head_x
            self.neutral_head_y = head_y
            self.neutral_iris_x = iris_x
            self.neutral_iris_y = iris_y
            self.head_center = (float(head_x), float(head_y))
            self.iris_center = (float(iris_x), float(iris_y))
            if self.head_bounds is None:
                self.head_bounds = (head_x - 0.12, head_x + 0.12, head_y - 0.12, head_y + 0.12)
            if self.iris_bounds is None:
                self.iris_bounds = (iris_x - 0.12, iris_x + 0.12, iris_y - 0.12, iris_y + 0.12)
            self.is_calibrated = True

            # Snap smoothed pointer straight to center and reset filters
            self.smoothed_x = 0.5
            self.smoothed_y = 0.5
            self.fixation_anchor_x = 0.5
            self.fixation_anchor_y = 0.5
            now = time.perf_counter()
            self.one_euro_x.reset(now, 0.5)
            self.one_euro_y.reset(now, 0.5)
            self._has_first_sample = True
            self._pinned_pos = (0.5, 0.5)
            self._is_pinned = True
            self._static_quiet_frames = 0
            self._static_last_filtered = None
            self._static_target = None
            self._pin_release_ramp = 1.0
            self._iris_history.clear()
            self._last_filtered_iris = None
            self._effective_iris_weight = self.iris_weight
            return True

        except (IndexError, AttributeError, TypeError):
            return False
