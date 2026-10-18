"""
Hybrid Gaze Estimator Module for EyeDE (Phase 1)
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
            raw_target_x = 0.5 + combined_delta_x
            raw_target_y = 0.5 + combined_delta_y

            if self.has_5_point_calibration:
                mapped_x, mapped_y = self.apply_5_point_mapping(raw_target_x, raw_target_y)
                target_x = max(0.0, min(1.0, mapped_x))
                target_y = max(0.0, min(1.0, mapped_y))
            else:
                target_x = max(0.0, min(1.0, raw_target_x))
                target_y = max(0.0, min(1.0, raw_target_y))

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
                "target_raw": (raw_target_x, raw_target_y),
                "target_calibrated": (target_x, target_y),
                "raw_head": (head_x, head_y),
                "raw_iris": (iris_x, iris_y),
                "is_blinking": self.is_blinking,
                "has_5_point_calibration": self.has_5_point_calibration,
                "calibration_rmse": self.calibration_rmse,
            })

            return self.smoothed_x, self.smoothed_y, True, debug_info

        except (IndexError, AttributeError, TypeError, ValueError):
            return self.smoothed_x, self.smoothed_y, False, debug_info

    def get_raw_gaze(self, face_landmarks: Any) -> Optional[Tuple[float, float]]:
        """
        Extracts raw uncalibrated normalized gaze (X, Y) prior to 5-point mapping and EMA smoothing.
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
            combined_delta_x = (self.head_weight * delta_head_x) + (self.iris_weight * delta_iris_x)
            combined_delta_y = (self.head_weight * delta_head_y) + (self.iris_weight * delta_iris_y)
            return 0.5 + combined_delta_x, 0.5 + combined_delta_y
        except Exception:
            return None

    def apply_5_point_mapping(self, u: float, v: float) -> Tuple[float, float]:
        """
        Applies bilinear / matrix transform learned from 5-point calibration.
        Maps raw input (u, v) -> screen (x, y).
        """
        with self._lock:
            if not self.has_5_point_calibration or not self.calib_weights_x or not self.calib_weights_y:
                return u, v
            try:
                a0, a1, a2, a3 = self.calib_weights_x
                b0, b1, b2, b3 = self.calib_weights_y
                mx = a0 + a1 * u + a2 * v + a3 * (u * v)
                my = b0 + b1 * u + b2 * v + b3 * (u * v)
                return float(mx), float(my)
            except Exception:
                return u, v

    def calibrate_5_points(self, points_data: List[Dict[str, Any]]) -> bool:
        """
        Calibrates the 2D gaze mapping using a 5-point dataset.
        Each item in points_data must contain:
          - 'screen': (sx, sy) tuple or list of normalized screen target coords.
          - 'raw': (rx, ry) tuple or list of observed raw gaze coords.

        Solves the bilinear regression system:
          x_screen = a0 + a1 * u + a2 * v + a3 * (u * v)
          y_screen = b0 + b1 * u + b2 * v + b3 * (u * v)
        via Ordinary Least Squares (OLS).
        """
        if not points_data or len(points_data) < 4:
            return False

        try:
            phi_rows = []
            targets_x = []
            targets_y = []

            for pt in points_data:
                sx, sy = pt["screen"]
                rx, ry = pt["raw"]
                phi_rows.append([1.0, float(rx), float(ry), float(rx * ry)])
                targets_x.append(float(sx))
                targets_y.append(float(sy))

            phi_mat = np.array(phi_rows, dtype=np.float64)
            tx_mat = np.array(targets_x, dtype=np.float64)
            ty_mat = np.array(targets_y, dtype=np.float64)

            # Defensive check for degenerate/identical coordinates
            # Requires variation in both horizontal and vertical axes
            if np.std(phi_mat[:, 1]) < 1e-4 or np.std(phi_mat[:, 2]) < 1e-4:
                return False
            if np.linalg.matrix_rank(phi_mat) < 3:
                return False

            weights_x, _, _, _ = np.linalg.lstsq(phi_mat, tx_mat, rcond=None)
            weights_y, _, _, _ = np.linalg.lstsq(phi_mat, ty_mat, rcond=None)

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
        Returns True on success, False if file is missing or invalid.
        """
        if not os.path.exists(filepath):
            return False
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                profile = json.load(f)

            if not isinstance(profile, dict):
                return False

            with self._lock:
                weights_x = profile.get("weights_x")
                weights_y = profile.get("weights_y")
                if weights_x and weights_y and len(weights_x) == 4 and len(weights_y) == 4:
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

                if "points" in profile:
                    self.calibration_points_data = profile["points"]

            return True
        except Exception:
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
            self._has_first_sample = False
            self.has_5_point_calibration = False
            self.calib_weights_x = None
            self.calib_weights_y = None
            self.calibration_points_data = None
            self.calibration_rmse = 0.0
