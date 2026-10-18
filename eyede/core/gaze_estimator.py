"""
Hybrid Gaze Estimator Module for EyeDE (Phase 1)
Combines relative iris offset with head pose (nose tip anchor),
applies neutral center calibration, and smoothes with an Exponential Moving Average (EMA).
"""

from typing import Any, Optional, Tuple, Dict
import math


class GazeEstimator:
    """
    Estimates normalized screen gaze coordinates (X, Y) in [0.0, 1.0] using a
    hybrid fusion of head movement (nose tip) and iris gaze direction.
    
    Guarantees:
    - ZeroDivisionError prevention with defensive epsilon bounds.
    - Face loss safety: maintains last valid position without crashing.
    - One-key center calibration (sets neutral anchor point).
    - Jitter removal via Exponential Moving Average (EMA) filtering.
    """

    def __init__(
        self,
        head_weight: float = 0.60,
        iris_weight: float = 0.40,
        head_sensitivity_x: float = 2.6,
        head_sensitivity_y: float = 2.6,
        iris_sensitivity_x: float = 3.5,
        iris_sensitivity_y: float = 3.5,
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
    ):
        # Weights (normalized so sum == 1.0)
        total_w = max(head_weight + iris_weight, 1e-6)
        self.head_weight = head_weight / total_w
        self.iris_weight = iris_weight / total_w

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

        # Blink suppression parameters
        self.blink_threshold: float = 0.012
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

        # Smoothed EMA state
        self.smoothed_x: float = 0.5
        self.smoothed_y: float = 0.5
        self._has_first_sample: bool = False

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

            # Vertical eyelid openings
            height_l = max(abs(top_y_l - bot_y_l), 0.0)
            height_r = max(abs(top_y_r - bot_y_r), 0.0)

            # Blink Detection: if both eyes are closed, freeze iris to avoid erratic pointer jumps
            if height_l < self.blink_threshold and height_r < self.blink_threshold:
                self.is_blinking = True
                return self.last_valid_iris_x, self.last_valid_iris_y

            self.is_blinking = False

            # Left eye ratios
            min_x_l = min(in_x_l, out_x_l)
            max_x_l = max(in_x_l, out_x_l)
            width_l = max(max_x_l - min_x_l, eps)
            safe_h_l = max(height_l, eps)
            min_y_l = min(top_y_l, bot_y_l)

            ratio_x_l = (ix_l - min_x_l) / width_l
            ratio_y_l = (iy_l - min_y_l) / safe_h_l

            # Right eye ratios
            min_x_r = min(in_x_r, out_x_r)
            max_x_r = max(in_x_r, out_x_r)
            width_r = max(max_x_r - min_x_r, eps)
            safe_h_r = max(height_r, eps)
            min_y_r = min(top_y_r, bot_y_r)

            ratio_x_r = (ix_r - min_x_r) / width_r
            ratio_y_r = (iy_r - min_y_r) / safe_h_r

            # Average both eyes
            avg_x = (ratio_x_l + ratio_x_r) * 0.5
            avg_y = (ratio_y_l + ratio_y_r) * 0.5

            clamped_x = max(0.0, min(1.0, float(avg_x)))
            clamped_y = max(0.0, min(1.0, float(avg_y)))

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
            self.head_sensitivity_x = max(0.5, min(10.0, float(head_x)))
        if head_y is not None:
            self.head_sensitivity_y = max(0.5, min(10.0, float(head_y)))
        if iris_x is not None:
            self.iris_sensitivity_x = max(0.5, min(10.0, float(iris_x)))
        if iris_y is not None:
            self.iris_sensitivity_y = max(0.5, min(10.0, float(iris_y)))

    def adjust_sensitivity(self, multiplier: float) -> None:
        """Scales all sensitivities by a relative multiplier (e.g. 1.1 for +10%)."""
        mult = max(0.5, min(2.0, float(multiplier)))
        self.set_sensitivity(
            head_x=self.head_sensitivity_x * mult,
            head_y=self.head_sensitivity_y * mult,
            iris_x=self.iris_sensitivity_x * mult,
            iris_y=self.iris_sensitivity_y * mult,
        )

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

            # Snap smoothed pointer straight to center
            self.smoothed_x = 0.5
            self.smoothed_y = 0.5
            self._has_first_sample = True
            return True

        except (IndexError, AttributeError, TypeError):
            return False

    def estimate(self, face_landmarks: Any) -> Tuple[float, float, bool, Dict[str, Any]]:
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
            "is_calibrated": self.is_calibrated,
            "is_blinking": self.is_blinking,
            "distance_scale": self.distance_scale,
            "head_sensitivity": (self.head_sensitivity_x, self.head_sensitivity_y),
            "iris_sensitivity": (self.iris_sensitivity_x, self.iris_sensitivity_y),
            "raw_head": (self.last_raw_head_x, self.last_raw_head_y),
            "raw_iris": (self.last_raw_iris_x, self.last_raw_iris_y),
            "neutral_head": (self.neutral_head_x, self.neutral_head_y),
            "neutral_iris": (self.neutral_iris_x, self.neutral_iris_y),
        }

        # 1. Face loss check: maintain last valid coordinates gracefully
        if face_landmarks is None:
            return self.smoothed_x, self.smoothed_y, False, debug_info

        try:
            landmarks = getattr(face_landmarks, "landmark", face_landmarks)
            if not landmarks:
                return self.smoothed_x, self.smoothed_y, False, debug_info

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

            # 4. Hybrid weighted fusion
            combined_delta_x = (self.head_weight * delta_head_x) + (self.iris_weight * delta_iris_x)
            combined_delta_y = (self.head_weight * delta_head_y) + (self.iris_weight * delta_iris_y)

            # 5. Screen coordinate mapping centered at (0.5, 0.5)
            target_x = max(0.0, min(1.0, 0.5 + combined_delta_x))
            target_y = max(0.0, min(1.0, 0.5 + combined_delta_y))

            # 6. Exponential Moving Average (EMA) filtering
            if not self._has_first_sample:
                self.smoothed_x = target_x
                self.smoothed_y = target_y
                self._has_first_sample = True
            else:
                alpha = self.ema_alpha
                self.smoothed_x = alpha * target_x + (1.0 - alpha) * self.smoothed_x
                self.smoothed_y = alpha * target_y + (1.0 - alpha) * self.smoothed_y

            # Ensure bounds [0.0, 1.0]
            self.smoothed_x = max(0.0, min(1.0, float(self.smoothed_x)))
            self.smoothed_y = max(0.0, min(1.0, float(self.smoothed_y)))

            debug_info.update({
                "target_raw": (target_x, target_y),
                "raw_head": (head_x, head_y),
                "raw_iris": (iris_x, iris_y),
                "is_blinking": self.is_blinking,
            })

            return self.smoothed_x, self.smoothed_y, True, debug_info

        except (IndexError, AttributeError, TypeError, ValueError):
            return self.smoothed_x, self.smoothed_y, False, debug_info

    def reset(self) -> None:
        """Resets filter and calibration baselines to default."""
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
        self._has_first_sample = False
