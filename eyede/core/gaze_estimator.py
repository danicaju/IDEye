"""
Hybrid Gaze Estimator Module for IDEye (Phase 1)
Combines relative iris offset with head pose (nose tip anchor),
applies neutral center calibration, and smoothes with an Exponential Moving Average (EMA).
"""

from typing import Any, Optional, Tuple, Dict, List, Union
import math
import os
import json
import time
import threading
import numpy as np


try:
    import eyede.config as config
except ImportError:
    try:
        import config
    except ImportError:
        config = None

TRACKING_MODE_PURE_IRIS = getattr(config, "TRACKING_MODE_PURE_IRIS", "PURE_IRIS") if config else "PURE_IRIS"
TRACKING_MODE_HYBRID = getattr(config, "TRACKING_MODE_HYBRID", "HYBRID") if config else "HYBRID"
TRACKING_MODE_HEAD_PRIMARY = getattr(config, "TRACKING_MODE_HEAD_PRIMARY", "HEAD_PRIMARY") if config else "HEAD_PRIMARY"
DEFAULT_TRACKING_MODE = getattr(config, "DEFAULT_TRACKING_MODE", TRACKING_MODE_HEAD_PRIMARY) if config else TRACKING_MODE_HEAD_PRIMARY


class OneEuroFilter:
    """
    One Euro Filter (1€ Filter) with adaptive cutoff frequency:
    - High smoothing / low cutoff at low velocity (eliminates resting tremor and webcam jitter).
    - Low smoothing / high cutoff at high velocity (eliminates lag during saccades).
    Reference: Casiez, Roussel, Vogel (CHI 2012) - 1€ Filter: A Simple Speed-based Low-pass Filter.
    """
    def __init__(
        self,
        t0: float = 0.0,
        x0: float = 0.5,
        min_cutoff: float = 0.55,
        beta: float = 0.28,
        d_cutoff: float = 1.0,
    ):
        self.min_cutoff = float(min_cutoff)
        self.beta = float(beta)
        self.d_cutoff = float(d_cutoff)
        self.x_prev = float(x0)
        self.dx_prev = 0.0
        self.t_prev = float(t0)

    @staticmethod
    def smoothing_factor(dt: float, cutoff: float) -> float:
        r = 2.0 * math.pi * cutoff * dt
        return r / (r + 1.0)

    def filter(self, t: float, x: float) -> float:
        if self.t_prev <= 0.0:
            self.t_prev = float(t)
            self.x_prev = float(x)
            self.dx_prev = 0.0
            return float(x)

        dt = float(t) - self.t_prev
        # If dt is less than realistic frame interval or excessive (pause/gap), fallback to nominal 1/30s
        if dt < 0.001 or dt > 0.5:
            dt = 1.0 / 30.0
        self.t_prev = float(t)

        # 1. Estimate filtered derivative (velocity)
        dx = (float(x) - self.x_prev) / dt
        edx = self.smoothing_factor(dt, self.d_cutoff)
        dx_hat = edx * dx + (1.0 - edx) * self.dx_prev

        # 2. Compute dynamic cutoff frequency
        cutoff = self.min_cutoff + self.beta * abs(dx_hat)
        a = self.smoothing_factor(dt, cutoff)

        # 3. Filter position
        x_hat = a * float(x) + (1.0 - a) * self.x_prev

        self.x_prev = x_hat
        self.dx_prev = dx_hat
        return x_hat

    def reset(self, t0: float = 0.0, x0: float = 0.5) -> None:
        self.x_prev = float(x0)
        self.dx_prev = 0.0
        self.t_prev = float(t0)


class GazeEstimator:
    """
    Estimates normalized screen gaze coordinates (X, Y) in [0.0, 1.0] using a
    hybrid fusion of head movement (nose tip) and iris gaze direction.
    
    Guarantees:
    - ZeroDivisionError prevention with defensive epsilon bounds.
    - Face loss safety: maintains last valid position without crashing.
    - One-key center calibration (sets neutral anchor point).
    - Jitter removal via One Euro Filter (1€ Filter) and adaptive fixation deadzone.
    - Ergonomic non-linear vertical expansion curve for full vertical screen reach.
    """

    def __init__(
        self,
        head_weight: float = 0.60,
        iris_weight: float = 0.40,
        head_sensitivity_x: float = 2.6,
        head_sensitivity_y: float = 3.0,
        iris_sensitivity_x: float = 3.2,
        iris_sensitivity_y: float = 8.5,
        ema_alpha: float = 0.22,
        # Landmark indices
        nose_tip_idx: int = 1,
        iris_left_center_idx: int = 468,
        iris_right_center_idx: int = 473,
        left_eye_inner_idx: int = 133,
        left_eye_outer_idx: int = 33,
        left_eye_top_idx: int = 159,
        left_eye_bottom_idx: int = 145,
        right_eye_inner_idx: int = 362,
        right_eye_outer_idx: int = 263,
        right_eye_top_idx: int = 386,
        right_eye_bottom_idx: int = 374,
        tracking_mode: Optional[str] = None,
    ):
        # Weights (normalized so sum == 1.0)
        total_w = max(head_weight + iris_weight, 1e-6)
        self.head_weight = head_weight / total_w
        self.iris_weight = iris_weight / total_w

        # Tracking Mode (PURE_IRIS, HYBRID, HEAD_PRIMARY)
        if tracking_mode is not None:
            self.tracking_mode = str(tracking_mode).upper()
        else:
            self.tracking_mode = DEFAULT_TRACKING_MODE

        # Base sensitivity multipliers
        self.base_head_sensitivity_x = float(head_sensitivity_x)
        self.base_head_sensitivity_y = float(head_sensitivity_y)
        self.base_iris_sensitivity_x = float(iris_sensitivity_x)
        self.base_iris_sensitivity_y = float(iris_sensitivity_y)

        # Active sensitivities (calibrated/adapted dynamically)
        self.head_sensitivity_x = self.base_head_sensitivity_x
        self.head_sensitivity_y = self.base_head_sensitivity_y
        self.iris_sensitivity_x = self.base_iris_sensitivity_x
        self.iris_sensitivity_y = self.base_iris_sensitivity_y
        self.distance_scale: float = 1.0

        self.ema_alpha = max(0.01, min(1.0, float(ema_alpha)))

        # Ergonomic reach curves & expansion gains (softened for natural pitch control)
        self.vertical_multiplier: float = float(getattr(config, "VERTICAL_MULTIPLIER", 2.35))
        self.vertical_expansion_gain: float = float(getattr(config, "VERTICAL_EXPANSION_GAIN", 1.6))
        self.horizontal_multiplier: float = float(getattr(config, "HORIZONTAL_MULTIPLIER", 1.45))
        self.horizontal_expansion_gain: float = float(getattr(config, "HORIZONTAL_EXPANSION_GAIN", 1.75))
        self.vor_compensation_factor: float = float(getattr(config, "VOR_COMPENSATION_FACTOR", 0.40))

        # One Euro Filter (1€ Filter) for adaptive anti-jitter & zero-lag saccades
        oe_min_cutoff = float(getattr(config, "ONE_EURO_MIN_CUTOFF", 0.55))
        oe_beta = float(getattr(config, "ONE_EURO_BETA", 0.28))
        oe_d_cutoff = float(getattr(config, "ONE_EURO_D_CUTOFF", 1.0))
        self.one_euro_x = OneEuroFilter(min_cutoff=oe_min_cutoff, beta=oe_beta, d_cutoff=oe_d_cutoff)
        self.one_euro_y = OneEuroFilter(min_cutoff=oe_min_cutoff, beta=oe_beta, d_cutoff=oe_d_cutoff)
        self.use_one_euro: bool = True

        # Adaptive Fixation Deadzone (I-VT velocity/distance filtering with sliding leash)
        self.fixation_deadzone: float = float(getattr(config, "FIXATION_DEADZONE", 0.022))
        self.fixation_anchor_x: float = 0.5
        self.fixation_anchor_y: float = 0.5
        self.is_fixated: bool = False
        self.stability_score: float = 1.0

        # Blink suppression parameters (scale-invariant EAR + absolute height fallback)
        self.ear_blink_threshold: float = float(getattr(config, "EAR_BLINK_THRESHOLD", 0.14))
        self.blink_threshold: float = float(getattr(config, "MIN_EYE_HEIGHT_RATIO", 0.008))
        self.is_blinking: bool = False
        self.last_valid_iris_x: float = 0.5
        self.last_valid_iris_y: float = 0.5

        # Landmark configuration
        self.nose_tip_idx = nose_tip_idx
        self.iris_left_center_idx = iris_left_center_idx
        self.iris_right_center_idx = iris_right_center_idx
        self.left_eye_inner_idx = left_eye_inner_idx
        self.left_eye_outer_idx = left_eye_outer_idx
        self.left_eye_top_idx = left_eye_top_idx
        self.left_eye_bottom_idx = left_eye_bottom_idx
        self.right_eye_inner_idx = right_eye_inner_idx
        self.right_eye_outer_idx = right_eye_outer_idx
        self.right_eye_top_idx = right_eye_top_idx
        self.right_eye_bottom_idx = right_eye_bottom_idx

        # Neutral calibration baseline (defaults to center 0.5, 0.5)
        self.neutral_head_x: float = 0.5
        self.neutral_head_y: float = 0.5
        self.neutral_iris_x: float = 0.5
        self.neutral_iris_y: float = 0.5
        self.is_calibrated: bool = False

        # Raw state
        self.last_raw_head_x: float = 0.5
        self.last_raw_head_y: float = 0.5
        self.last_raw_iris_x: float = 0.5
        self.last_raw_iris_y: float = 0.5

        # Smoothed state
        self.smoothed_x: float = 0.5
        self.smoothed_y: float = 0.5
        self._has_first_sample: bool = False

        # Phase 2: 5-Point Calibration & Matrix / Bilinear Model State
        self.has_5_point_calibration: bool = False
        self.calib_weights_x: Optional[List[float]] = None
        self.calib_weights_y: Optional[List[float]] = None
        self.calibration_points_data: Optional[List[Dict[str, Any]]] = None
        self.calibration_rmse: float = 0.0
        self._lock = threading.RLock()

    @staticmethod
    def _safe_coord(point: Any) -> Tuple[float, float]:
        """Safely extracts x and y from landmark object or tuple/list."""
        try:
            return float(point.x), float(point.y)
        except (AttributeError, TypeError):
            try:
                return float(point[0]), float(point[1])
            except (IndexError, TypeError, ValueError):
                return 0.5, 0.5

    def _extract_iris_ratio(self, landmarks: Any) -> Tuple[float, float]:
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

    def _extract_head_pos(self, landmarks: Any) -> Tuple[float, float]:
        """Extracts normalized nose tip position as the head pose anchor."""
        try:
            p_nose = landmarks[self.nose_tip_idx]
            return self._safe_coord(p_nose)
        except (IndexError, AttributeError, TypeError):
            return 0.5, 0.5

    def set_sensitivity(
        self,
        head_x: Optional[float] = None,
        head_y: Optional[float] = None,
        iris_x: Optional[float] = None,
        iris_y: Optional[float] = None,
    ) -> None:
        """Manually sets gain / sensitivity multipliers."""
        if head_x is not None:
            self.head_sensitivity_x = max(0.5, min(15.0, float(head_x)))
        if head_y is not None:
            self.head_sensitivity_y = max(0.5, min(20.0, float(head_y)))
        if iris_x is not None:
            self.iris_sensitivity_x = max(0.5, min(15.0, float(iris_x)))
        if iris_y is not None:
            self.iris_sensitivity_y = max(0.5, min(25.0, float(iris_y)))

    def adjust_sensitivity(self, multiplier: float) -> None:
        """Scales all sensitivities by a relative multiplier (e.g. 1.1 for +10%)."""
        mult = max(0.5, min(2.0, float(multiplier)))
        self.set_sensitivity(
            head_x=self.head_sensitivity_x * mult,
            head_y=self.head_sensitivity_y * mult,
            iris_x=self.iris_sensitivity_x * mult,
            iris_y=self.iris_sensitivity_y * mult,
        )

    def set_anti_jitter_damping(self, level: float) -> None:
        """
        Adjusts anti-jitter damping level (1.0 to 10.0).
        Higher level = heavier damping at resting (lower min_cutoff, larger deadzone).
        Lower level = lighter damping, more raw response.
        """
        clamped = max(1.0, min(10.0, float(level)))
        t = (clamped - 1.0) / 9.0
        min_cutoff = 1.0 - t * 0.82    # Level 1: 1.0 Hz -> Level 10: 0.18 Hz
        deadzone = 0.010 + t * 0.024  # Level 1: 0.010 -> Level 10: 0.034
        self.one_euro_x.min_cutoff = min_cutoff
        self.one_euro_y.min_cutoff = min_cutoff
        self.fixation_deadzone = deadzone

    def _apply_ergonomic_vertical_curve(self, delta_y: float) -> float:
        """
        Ergonomic non-linear vertical expansion curve with independent vertical multiplier
        and smooth micro-damped centering curve around resting neutral position.
        Compensates for the reduced human vertical ocular/cervical span (~30% of horizontal).
        Applies progressive expansion so gentle head pitch or looking up/down comfortably
        hits top row (Y < 0.20) and bottom row (Y > 0.80), while remaining rock-solid at center.
        """
        if not math.isfinite(delta_y) or abs(delta_y) < 1e-6:
            return 0.0
        sign = 1.0 if delta_y >= 0.0 else -1.0
        u = abs(delta_y)
        cz = 0.040
        if u <= cz:
            expanded = u * (u / cz) ** 2
        else:
            excess = u - cz
            expanded = cz + self.vertical_multiplier * excess * (1.0 + self.vertical_expansion_gain * excess)
        return sign * expanded

    def _apply_horizontal_expansion_curve(self, delta_x: float) -> float:
        """
        Ergonomic non-linear horizontal expansion curve for effortless edge reach.
        Compensates for the limited natural horizontal range of the iris relative to the canthi.
        Dampens micro-movements near center for rock-solid reading, while progressively
        expanding lateral glances so user effortlessly reaches lateral borders (columns 0 and 2)
        purely by moving eyes, without twisting the head.
        """
        if not math.isfinite(delta_x) or abs(delta_x) < 1e-6:
            return 0.0
        sign = 1.0 if delta_x >= 0.0 else -1.0
        u = abs(delta_x)
        cz = 0.050
        if u <= cz:
            expanded = u
        else:
            excess = u - cz
            expanded = cz + self.horizontal_multiplier * excess * (1.0 + self.horizontal_expansion_gain * excess)
        return sign * expanded

    def set_tracking_mode(self, mode: str) -> None:
        """
        Switches the active gaze tracking mode:
        - 'PURE_IRIS': 100% iris tracking, 0% head influence, with non-linear horizontal edge reach.
        - 'HYBRID': Head + Iris fusion with VOR (Vestibulo-Ocular Reflex) counter-rotation compensation.
        - 'HEAD_PRIMARY': 95% head pose, 5% iris for users with ocular mobility restrictions.
        """
        mode_upper = str(mode).upper()
        if mode_upper in ("PURE_IRIS", "HYBRID", "HEAD_PRIMARY"):
            self.tracking_mode = mode_upper
        else:
            self.tracking_mode = "HYBRID"

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

            combined_x = (self.head_weight * dh_x) + (self.iris_weight * effective_iris_x)
            combined_y = (self.head_weight * dh_y) + (self.iris_weight * di_y)

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
            return True

        except (IndexError, AttributeError, TypeError):
            return False

    def estimate(
        self,
        face_landmarks: Any,
        timestamp: Optional[float] = None,
    ) -> Tuple[float, float, bool, Dict[str, Any]]:
        """
        Estimates the normalized gaze coordinates (X, Y) in range [0.0, 1.0].

        Returns:
            Tuple of:
                - smoothed_x (float): Filtered gaze X in [0.0, 1.0]
                - smoothed_y (float): Filtered gaze Y in [0.0, 1.0]
                - face_detected (bool): True if face was tracked, False if lost.
                - debug_info (dict): Raw vectors, calibration state, etc.
        """
        debug_info = {
            "tracking_mode": self.tracking_mode,
            "is_calibrated": self.is_calibrated,
            "is_blinking": self.is_blinking,
            "distance_scale": self.distance_scale,
            "head_sensitivity": (self.head_sensitivity_x, self.head_sensitivity_y),
            "iris_sensitivity": (self.iris_sensitivity_x, self.iris_sensitivity_y),
            "raw_head": (self.last_raw_head_x, self.last_raw_head_y),
            "raw_iris": (self.last_raw_iris_x, self.last_raw_iris_y),
            "neutral_head": (self.neutral_head_x, self.neutral_head_y),
            "neutral_iris": (self.neutral_iris_x, self.neutral_iris_y),
            "is_fixated": self.is_fixated,
            "stability_score": self.stability_score,
        }

        # 1. Face loss check: maintain last valid coordinates gracefully (strictly clipped)
        if face_landmarks is None:
            cx = float(np.clip(self.smoothed_x, 0.0, 1.0))
            cy = float(np.clip(self.smoothed_y, 0.0, 1.0))
            return cx, cy, False, debug_info

        try:
            landmarks = getattr(face_landmarks, "landmark", face_landmarks)
            if not landmarks:
                cx = float(np.clip(self.smoothed_x, 0.0, 1.0))
                cy = float(np.clip(self.smoothed_y, 0.0, 1.0))
                return cx, cy, False, debug_info

            # 2. Extract raw signals
            head_x, head_y = self._extract_head_pos(landmarks)
            iris_x, iris_y = self._extract_iris_ratio(landmarks)

            self.last_raw_head_x = head_x
            self.last_raw_head_y = head_y
            self.last_raw_iris_x = iris_x
            self.last_raw_iris_y = iris_y

            # 3. Calculate deviations from neutral calibration point
            delta_head_x = (head_x - self.neutral_head_x) * self.head_sensitivity_x
            delta_head_y = (head_y - self.neutral_head_y) * self.head_sensitivity_y

            delta_iris_x = (iris_x - self.neutral_iris_x) * self.iris_sensitivity_x
            delta_iris_y = (iris_y - self.neutral_iris_y) * self.iris_sensitivity_y

            # 4. Mode-based delta computation (PURE_IRIS, HYBRID, HEAD_PRIMARY)
            expanded_delta_x, expanded_delta_y = self._compute_combined_deltas(
                delta_head_x, delta_head_y, delta_iris_x, delta_iris_y
            )

            # 5. Screen coordinate mapping centered at (0.5, 0.5)
            raw_target_x = 0.5 + expanded_delta_x
            raw_target_y = 0.5 + expanded_delta_y

            if self.has_5_point_calibration:
                mapped_x, mapped_y = self.apply_5_point_mapping(raw_target_x, raw_target_y)
                target_x = float(np.clip(mapped_x, 0.0, 1.0))
                target_y = float(np.clip(mapped_y, 0.0, 1.0))
            else:
                target_x = float(np.clip(raw_target_x, 0.0, 1.0))
                target_y = float(np.clip(raw_target_y, 0.0, 1.0))

            # 6. Adaptive Fixation Deadzone (I-VT velocity/distance filtering with sliding leash)
            dist_to_anchor = math.hypot(target_x - self.fixation_anchor_x, target_y - self.fixation_anchor_y)
            if dist_to_anchor <= self.fixation_deadzone:
                self.is_fixated = True
                self.stability_score = max(0.0, min(1.0, 1.0 - (dist_to_anchor / max(self.fixation_deadzone, 1e-6))))
                # Inside deadzone: damp micro-jitter cubically towards fixation anchor
                damping_ratio = (dist_to_anchor / max(self.fixation_deadzone, 1e-6)) ** 3
                filtered_target_x = self.fixation_anchor_x + (target_x - self.fixation_anchor_x) * damping_ratio
                filtered_target_y = self.fixation_anchor_y + (target_y - self.fixation_anchor_y) * damping_ratio
            else:
                self.is_fixated = False
                self.stability_score = max(0.0, 0.5 - min(0.5, dist_to_anchor))
                # Outside deadzone: sliding leash prevents limit-cycle side-to-side oscillation.
                # Head movement is continuous/anatomical rather than ballistic saccades, so HEAD_PRIMARY
                # uses a 4.0x leash multiplier to prevent stick-slip freezing during intentional head shifts.
                snap_multiplier = 4.0 if self.tracking_mode == "HEAD_PRIMARY" else 2.5
                if dist_to_anchor > snap_multiplier * self.fixation_deadzone:
                    # Saccade / large intentional movement: snap anchor to target
                    self.fixation_anchor_x = target_x
                    self.fixation_anchor_y = target_y
                else:
                    # Smooth pursuit / small departure: smoothly drag anchor along displacement vector
                    excess = dist_to_anchor - self.fixation_deadzone
                    slide_step = excess * 0.70
                    dir_x = (target_x - self.fixation_anchor_x) / dist_to_anchor
                    dir_y = (target_y - self.fixation_anchor_y) / dist_to_anchor
                    self.fixation_anchor_x += dir_x * slide_step
                    self.fixation_anchor_y += dir_y * slide_step
                filtered_target_x = target_x
                filtered_target_y = target_y

            # 7. One Euro Filter (1€ Filter) & EMA convergence
            now = timestamp if timestamp is not None else time.perf_counter()
            if not self._has_first_sample:
                self.smoothed_x = target_x
                self.smoothed_y = target_y
                self.fixation_anchor_x = target_x
                self.fixation_anchor_y = target_y
                self.one_euro_x.reset(now, target_x)
                self.one_euro_y.reset(now, target_y)
                self._has_first_sample = True
            else:
                if self.use_one_euro:
                    filtered_x = self.one_euro_x.filter(now, filtered_target_x)
                    filtered_y = self.one_euro_y.filter(now, filtered_target_y)
                    self.smoothed_x = float(np.clip(filtered_x, 0.0, 1.0))
                    self.smoothed_y = float(np.clip(filtered_y, 0.0, 1.0))
                else:
                    alpha = self.ema_alpha
                    self.smoothed_x = alpha * target_x + (1.0 - alpha) * self.smoothed_x
                    self.smoothed_y = alpha * target_y + (1.0 - alpha) * self.smoothed_y
                    self.smoothed_x = float(np.clip(self.smoothed_x, 0.0, 1.0))
                    self.smoothed_y = float(np.clip(self.smoothed_y, 0.0, 1.0))

            debug_info.update({
                "target_raw": (raw_target_x, raw_target_y),
                "target_calibrated": (target_x, target_y),
                "raw_head": (head_x, head_y),
                "raw_iris": (iris_x, iris_y),
                "is_blinking": self.is_blinking,
                "is_fixated": self.is_fixated,
                "stability_score": self.stability_score,
                "has_5_point_calibration": self.has_5_point_calibration,
                "calibration_rmse": self.calibration_rmse,
            })

            return self.smoothed_x, self.smoothed_y, True, debug_info

        except (IndexError, AttributeError, TypeError, ValueError):
            cx = float(np.clip(self.smoothed_x, 0.0, 1.0))
            cy = float(np.clip(self.smoothed_y, 0.0, 1.0))
            return cx, cy, False, debug_info

    def get_raw_gaze(self, face_landmarks: Any) -> Optional[Tuple[float, float]]:
        """
        Extracts raw uncalibrated normalized gaze (X, Y) prior to 5-point mapping and filtering.
        Returns (raw_x, raw_y) or None if face is lost.
        """
        if face_landmarks is None:
            return None
        try:
            landmarks = getattr(face_landmarks, "landmark", face_landmarks)
            if not landmarks:
                return None
            head_x, head_y = self._extract_head_pos(landmarks)
            iris_x, iris_y = self._extract_iris_ratio(landmarks)
            delta_head_x = (head_x - self.neutral_head_x) * self.head_sensitivity_x
            delta_head_y = (head_y - self.neutral_head_y) * self.head_sensitivity_y
            delta_iris_x = (iris_x - self.neutral_iris_x) * self.iris_sensitivity_x
            delta_iris_y = (iris_y - self.neutral_iris_y) * self.iris_sensitivity_y
            expanded_delta_x, expanded_delta_y = self._compute_combined_deltas(
                delta_head_x, delta_head_y, delta_iris_x, delta_iris_y
            )
            return 0.5 + expanded_delta_x, 0.5 + expanded_delta_y
        except Exception:
            return None

    def apply_5_point_mapping(self, u: float, v: float) -> Tuple[float, float]:
        """
        Applies bilinear / matrix transform learned from 5-point calibration.
        Maps raw input (u, v) -> screen (x, y).
        Safeguarded against NaN, Inf, and erratic out-of-screen extrapolation.
        """
        with self._lock:
            if not self.has_5_point_calibration or not self.calib_weights_x or not self.calib_weights_y:
                return u, v
            try:
                a0, a1, a2, a3 = self.calib_weights_x
                b0, b1, b2, b3 = self.calib_weights_y
                mx = a0 + a1 * u + a2 * v + a3 * (u * v)
                my = b0 + b1 * u + b2 * v + b3 * (u * v)
                if math.isnan(mx) or math.isinf(mx):
                    mx = u
                if math.isnan(my) or math.isinf(my):
                    my = v
                # Bounded safety guard: prevent non-linear warping from launching cursor into infinity
                mx = max(-1.0, min(2.0, float(mx)))
                my = max(-1.0, min(2.0, float(my)))
                return float(mx), float(my)
            except Exception:
                return u, v

    def calibrate_5_points(self, points_data: List[Dict[str, Any]]) -> bool:
        """
        Calibrates the 2D gaze mapping using a 5-point dataset.
        Each item in points_data must contain:
          - 'screen': (sx, sy) tuple or list of normalized screen target coords.
          - 'raw': (rx, ry) tuple or list of observed raw gaze coords.

        Solves the regularized bilinear regression system:
          x_screen = a0 + a1 * u + a2 * v + a3 * (u * v)
          y_screen = b0 + b1 * u + b2 * v + b3 * (u * v)
        via Ridge / Tikhonov regularization with prior towards identity mapping,
        coefficient clamping, and bounded gains to prevent ill-conditioned blowups.
        """
        if not points_data or len(points_data) < 4:
            return False

        try:
            phi_rows = []
            targets_x = []
            targets_y = []
            raw_xs = []
            raw_ys = []

            for pt in points_data:
                sx, sy = pt["screen"]
                rx, ry = pt["raw"]
                phi_rows.append([1.0, float(rx), float(ry), float(rx * ry)])
                targets_x.append(float(sx))
                targets_y.append(float(sy))
                raw_xs.append(float(rx))
                raw_ys.append(float(ry))

            phi_mat = np.array(phi_rows, dtype=np.float64)
            tx_mat = np.array(targets_x, dtype=np.float64)
            ty_mat = np.array(targets_y, dtype=np.float64)

            # Defensive check for degenerate/identical coordinates
            # Requires variation in both horizontal and vertical axes
            if np.std(phi_mat[:, 1]) < 1e-4 or np.std(phi_mat[:, 2]) < 1e-4:
                return False
            if np.linalg.matrix_rank(phi_mat) < 3:
                return False

            range_x = float(np.ptp(phi_mat[:, 1]))
            range_y = float(np.ptp(phi_mat[:, 2]))
            min_range = min(range_x, range_y)
            if min_range < 0.015:
                # Range too narrow to compute meaningful calibration without extreme noise amplification
                return False

            # Determine raw center anchor (from CENTER point or centroid of points)
            center_raw_candidates = [
                pt["raw"] for pt in points_data
                if pt.get("id") == "CENTER" or pt.get("screen") == (0.5, 0.5)
            ]
            if center_raw_candidates:
                uc, vc = float(center_raw_candidates[0][0]), float(center_raw_candidates[0][1])
            else:
                uc = float(np.mean(raw_xs))
                vc = float(np.mean(raw_ys))

            # Identity prior targets centered at (0.5, 0.5):
            # x_prior(u) = 0.5 + 1.0 * (u - uc) = (0.5 - uc) + 1.0 * u
            # y_prior(v) = 0.5 + 1.0 * (v - vc) = (0.5 - vc) + 1.0 * v
            w0_x = np.array([0.5 - uc, 1.0, 0.0, 0.0], dtype=np.float64)
            w0_y = np.array([0.5 - vc, 0.0, 1.0, 0.0], dtype=np.float64)

            # Adaptive regularization parameter lambda (Tikhonov regularization)
            # When range is healthy (>= 0.15), lambda is small (0.0005) for high fidelity.
            # When range is narrow, lambda scales up quadratically to prevent matrix blowup.
            base_lambda = 0.0005
            if min_range < 0.15:
                adaptive_lambda = base_lambda * ((0.15 / max(min_range, 0.02)) ** 2)
            else:
                adaptive_lambda = base_lambda
            adaptive_lambda = min(adaptive_lambda, 0.5)

            # Tikhonov penalty matrices:
            # For X: parameter vector is [a0, a1 (main u), a2 (cross v), a3 (bilinear uv)]
            # For Y: parameter vector is [b0, b1 (cross u), b2 (main v), b3 (bilinear uv)]
            # Cross terms and bilinear interaction are heavily penalized to decouple axes,
            # preventing horizontal eye movements from skewing vertical screen coordinates.
            reg_weights_x = np.array([0.005, 0.02, 2.0, 5.0], dtype=np.float64) * adaptive_lambda
            reg_weights_y = np.array([0.005, 2.0, 0.02, 5.0], dtype=np.float64) * adaptive_lambda
            Gamma_x = np.diag(reg_weights_x)
            Gamma_y = np.diag(reg_weights_y)

            Ax = phi_mat.T @ phi_mat + Gamma_x
            bx = phi_mat.T @ tx_mat + Gamma_x @ w0_x
            Ay = phi_mat.T @ phi_mat + Gamma_y
            by = phi_mat.T @ ty_mat + Gamma_y @ w0_y

            try:
                weights_x = np.linalg.solve(Ax, bx)
            except np.linalg.LinAlgError:
                weights_x, _, _, _ = np.linalg.lstsq(phi_mat, tx_mat, rcond=None)

            try:
                weights_y = np.linalg.solve(Ay, by)
            except np.linalg.LinAlgError:
                weights_y, _, _, _ = np.linalg.lstsq(phi_mat, ty_mat, rcond=None)

            # Gain bounding and shrinkage towards identity:
            # Prevent excessive speed or inverted directions
            min_gain = 0.4
            max_gain = 3.5

            # Effective gain in X at center v=vc: gx = a1 + vc * a3
            gx = float(weights_x[1] + vc * weights_x[3])
            if gx > max_gain or gx < min_gain:
                target_g = max_gain if gx > max_gain else min_gain
                if abs(gx - 1.0) > 1e-4:
                    beta = float(np.clip((gx - target_g) / (gx - 1.0), 0.0, 1.0))
                    weights_x = (1.0 - beta) * weights_x + beta * w0_x

            # Effective gain in Y at center u=uc: gy = b2 + uc * b3
            gy = float(weights_y[2] + uc * weights_y[3])
            if gy > max_gain or gy < min_gain:
                target_g = max_gain if gy > max_gain else min_gain
                if abs(gy - 1.0) > 1e-4:
                    beta = float(np.clip((gy - target_g) / (gy - 1.0), 0.0, 1.0))
                    weights_y = (1.0 - beta) * weights_y + beta * w0_y

            # Coefficient clamping to prevent extreme polynomial warping
            weights_x[0] = np.clip(weights_x[0], -4.0, 4.0)
            weights_x[1] = np.clip(weights_x[1], 0.2, 5.0)
            weights_x[2] = np.clip(weights_x[2], -1.5, 1.5)
            weights_x[3] = np.clip(weights_x[3], -2.5, 2.5)

            weights_y[0] = np.clip(weights_y[0], -4.0, 4.0)
            weights_y[1] = np.clip(weights_y[1], -1.5, 1.5)
            weights_y[2] = np.clip(weights_y[2], 0.2, 5.0)
            weights_y[3] = np.clip(weights_y[3], -2.5, 2.5)

            # Defensive sanity check for finite values
            if (
                any(math.isnan(float(w)) or math.isinf(float(w)) for w in weights_x)
                or any(math.isnan(float(w)) or math.isinf(float(w)) for w in weights_y)
            ):
                return False

            # Calculate RMSE
            pred_x = phi_mat @ weights_x
            pred_y = phi_mat @ weights_y
            rmse = float(np.sqrt(np.mean((pred_x - tx_mat) ** 2 + (pred_y - ty_mat) ** 2)))

            with self._lock:
                self.calib_weights_x = weights_x.tolist()
                self.calib_weights_y = weights_y.tolist()
                self.has_5_point_calibration = True
                self.is_calibrated = True
                self.calibration_rmse = rmse
                self.calibration_points_data = points_data
            return True
        except Exception:
            return False


    def save_calibration_profile(self, filepath: str = "calibration_profile.json") -> bool:
        """
        Saves current calibration parameters (5-point weights, neutral anchors) to JSON.
        """
        try:
            with self._lock:
                profile = {
                    "version": 2,
                    "type": "5_point_bilinear",
                    "timestamp": time.time(),
                    "has_5_point_calibration": self.has_5_point_calibration,
                    "weights_x": self.calib_weights_x,
                    "weights_y": self.calib_weights_y,
                    "rmse": self.calibration_rmse,
                    "neutral_head": [self.neutral_head_x, self.neutral_head_y],
                    "neutral_iris": [self.neutral_iris_x, self.neutral_iris_y],
                    "distance_scale": self.distance_scale,
                    "head_sensitivities": [self.head_sensitivity_x, self.head_sensitivity_y],
                    "iris_sensitivities": [self.iris_sensitivity_x, self.iris_sensitivity_y],
                    "tracking_mode": self.tracking_mode,
                    "points": self.calibration_points_data or []
                }
            tmp_path = filepath + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(profile, f, indent=2)
            if os.path.exists(filepath):
                os.replace(tmp_path, filepath)
            else:
                os.rename(tmp_path, filepath)
            return True
        except Exception:
            return False

    def load_calibration_profile(self, filepath: str = "calibration_profile.json") -> bool:
        """
        Loads calibration profile from JSON, restoring weights and anchors.
        Returns True on success, False if file is missing, corrupt, empty, or degenerate.
        Recovers safely by resetting to default baselines and logging an informative warning.
        """
        if not os.path.exists(filepath):
            return False
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read().strip()

            if not content:
                print(f"[GazeEstimator] Warning: Calibration file '{filepath}' is empty. Restoring safe defaults.")
                self.reset()
                return False

            profile = json.loads(content)

            if not isinstance(profile, dict):
                print(f"[GazeEstimator] Warning: Calibration file '{filepath}' is not a valid JSON object. Restoring safe defaults.")
                self.reset()
                return False

            with self._lock:
                weights_x = profile.get("weights_x")
                weights_y = profile.get("weights_y")
                points = profile.get("points")

                # Check for degenerate points where min == max (which causes ZeroDivisionError during interpolation/fitting)
                if points and isinstance(points, list) and len(points) >= 2:
                    raw_pts = [p.get("raw") for p in points if isinstance(p, dict) and "raw" in p]
                    screen_pts = [p.get("screen") for p in points if isinstance(p, dict) and "screen" in p]

                    if raw_pts:
                        raw_xs = [r[0] for r in raw_pts if isinstance(r, (list, tuple)) and len(r) >= 2]
                        raw_ys = [r[1] for r in raw_pts if isinstance(r, (list, tuple)) and len(r) >= 2]
                        if raw_xs and (min(raw_xs) == max(raw_xs)):
                            print(f"[GazeEstimator] Warning: Calibration points degenerate (raw min_x == max_x). Restoring safe defaults.")
                            self.reset()
                            return False
                        if raw_ys and (min(raw_ys) == max(raw_ys)):
                            print(f"[GazeEstimator] Warning: Calibration points degenerate (raw min_y == max_y). Restoring safe defaults.")
                            self.reset()
                            return False

                    if screen_pts:
                        screen_xs = [s[0] for s in screen_pts if isinstance(s, (list, tuple)) and len(s) >= 2]
                        screen_ys = [s[1] for s in screen_pts if isinstance(s, (list, tuple)) and len(s) >= 2]
                        if screen_xs and (min(screen_xs) == max(screen_xs)):
                            print(f"[GazeEstimator] Warning: Calibration points degenerate (screen min_x == max_x). Restoring safe defaults.")
                            self.reset()
                            return False
                        if screen_ys and (min(screen_ys) == max(screen_ys)):
                            print(f"[GazeEstimator] Warning: Calibration points degenerate (screen min_y == max_y). Restoring safe defaults.")
                            self.reset()
                            return False

                if weights_x is not None or weights_y is not None:
                    if (
                        not weights_x
                        or not weights_y
                        or len(weights_x) != 4
                        or len(weights_y) != 4
                        or any(math.isnan(float(w)) or math.isinf(float(w)) for w in weights_x + weights_y)
                    ):
                        print(f"[GazeEstimator] Warning: Calibration weights corrupt or invalid. Restoring safe defaults.")
                        self.reset()
                        return False

                    max_weight_mag = max(abs(float(w)) for w in weights_x + weights_y)
                    if max_weight_mag > 10.0:
                        print(f"[GazeEstimator] Warning: Stored calibration weights excessive (max={max_weight_mag:.1f}). Attempting robust re-fit from points.")
                        refit_ok = False
                        if points and isinstance(points, list) and len(points) >= 4:
                            if self.calibrate_5_points(points):
                                print("[GazeEstimator] Successfully re-fitted robust regularized calibration model from profile points.")
                                refit_ok = True
                        if not refit_ok:
                            print(f"[GazeEstimator] Warning: Could not re-fit safely. Restoring safe defaults.")
                            self.reset()
                            return False
                    else:
                        self.calib_weights_x = [float(w) for w in weights_x]
                        self.calib_weights_y = [float(w) for w in weights_y]
                        self.has_5_point_calibration = bool(profile.get("has_5_point_calibration", True))
                        self.is_calibrated = True

                if "neutral_head" in profile and len(profile["neutral_head"]) == 2:
                    self.neutral_head_x = float(profile["neutral_head"][0])
                    self.neutral_head_y = float(profile["neutral_head"][1])

                if "neutral_iris" in profile and len(profile["neutral_iris"]) == 2:
                    self.neutral_iris_x = float(profile["neutral_iris"][0])
                    self.neutral_iris_y = float(profile["neutral_iris"][1])

                if "distance_scale" in profile:
                    self.distance_scale = float(profile["distance_scale"])

                if "rmse" in profile:
                    self.calibration_rmse = float(profile["rmse"])

                if "tracking_mode" in profile:
                    self.set_tracking_mode(profile["tracking_mode"])

                if "points" in profile:
                    self.calibration_points_data = profile["points"]

            return True
        except Exception as e:
            print(f"[GazeEstimator] Warning: Failed to load calibration profile '{filepath}': {e}. Restoring safe defaults.")
            self.reset()
            return False

    def reset(self) -> None:
        """Resets filter and calibration baselines to default."""
        with self._lock:
            self.neutral_head_x = 0.5
            self.neutral_head_y = 0.5
            self.neutral_iris_x = 0.5
            self.neutral_iris_y = 0.5
            self.is_calibrated = False
            self.distance_scale = 1.0
            self.head_sensitivity_x = self.base_head_sensitivity_x
            self.head_sensitivity_y = self.base_head_sensitivity_y
            self.iris_sensitivity_x = self.base_iris_sensitivity_x
            self.iris_sensitivity_y = self.base_iris_sensitivity_y
            self.last_valid_iris_x = 0.5
            self.last_valid_iris_y = 0.5
            self.is_blinking = False
            self.smoothed_x = 0.5
            self.smoothed_y = 0.5
            self.fixation_anchor_x = 0.5
            self.fixation_anchor_y = 0.5
            self.is_fixated = False
            self.stability_score = 1.0
            self.one_euro_x.reset(0.0, 0.5)
            self.one_euro_y.reset(0.0, 0.5)
            self._has_first_sample = False
            self.has_5_point_calibration = False
            self.calib_weights_x = None
            self.calib_weights_y = None
            self.calibration_points_data = None
            self.calibration_rmse = 0.0
