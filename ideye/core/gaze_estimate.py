"""Per-frame gaze estimation."""

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



class GazeEstimateMixin:
    """Per-frame gaze estimation."""

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
            "head_yaw": self.last_head_yaw,
        }

        # 1. Face loss check: maintain last valid coordinates gracefully (strictly clipped)
        if face_landmarks is None:
            self.last_head_yaw = 0.0
            cx = self._finite_unit(self.smoothed_x)
            cy = self._finite_unit(self.smoothed_y)
            return cx, cy, False, debug_info

        try:
            landmarks = getattr(face_landmarks, "landmark", face_landmarks)
            if not landmarks:
                self.last_head_yaw = 0.0
                cx = self._finite_unit(self.smoothed_x)
                cy = self._finite_unit(self.smoothed_y)
                return cx, cy, False, debug_info

            # 2. Extract raw signals
            head_x, head_y = self._extract_head_pos(landmarks)
            iris_x, iris_y = self._extract_iris_ratio(landmarks)
            self.last_head_yaw = self._extract_head_yaw(landmarks)

            self.last_raw_head_x = head_x
            self.last_raw_head_y = head_y
            self.last_raw_iris_x = iris_x
            self.last_raw_iris_y = iris_y

            # 3. Calculate deviations from neutral calibration point
            delta_head_x = (head_x - self.neutral_head_x) * self.head_sensitivity_x
            delta_head_y = (head_y - self.neutral_head_y) * self.head_sensitivity_y

            delta_iris_x = (iris_x - self.neutral_iris_x) * self.iris_sensitivity_x
            delta_iris_y = (iris_y - self.neutral_iris_y) * self.iris_sensitivity_y

            # 4/5. Normalize each biological source independently when the
            # profile captured both head and iris references. This keeps the
            # three tracking modes centered on the same calibration geometry.
            if self.has_dual_calibration:
                head_screen_x, head_screen_y = self._map_dual_source(
                    head_x, head_y,
                    self.head_bounds,
                    self.calib_head_linear_x,
                    self.calib_head_linear_y,
                    center=self.head_center,
                )
                iris_screen_x, iris_screen_y = self._map_dual_source(
                    iris_x, iris_y,
                    self.iris_bounds,
                    self.calib_iris_linear_x,
                    self.calib_iris_linear_y,
                    center=self.iris_center,
                )
                if self.tracking_mode == "HEAD_PRIMARY":
                    target_x, target_y = head_screen_x, head_screen_y
                elif self.tracking_mode == "PURE_IRIS":
                    target_x, target_y = iris_screen_x, iris_screen_y
                else:
                    self._dynamic_fusion_active = True
                    iris_w = max(0.0, min(1.0, self._compute_effective_iris_weight(iris_x, iris_y)))
                    self._dynamic_fusion_active = False
                    head_w = 1.0 - iris_w
                    target_x = head_w * head_screen_x + iris_w * iris_screen_x
                    target_y = head_w * head_screen_y + iris_w * iris_screen_y
                raw_target_x, raw_target_y = target_x, target_y
                target_x = float(np.clip(target_x, 0.0, 1.0))
                target_y = float(np.clip(target_y, 0.0, 1.0))
            else:
                delta_head_x = (head_x - self.neutral_head_x) * self.head_sensitivity_x
                delta_head_y = (head_y - self.neutral_head_y) * self.head_sensitivity_y
                delta_iris_x = (iris_x - self.neutral_iris_x) * self.iris_sensitivity_x
                delta_iris_y = (iris_y - self.neutral_iris_y) * self.iris_sensitivity_y

                self._dynamic_fusion_active = self.tracking_mode == "HYBRID"
                if self._dynamic_fusion_active:
                    self._compute_effective_iris_weight(iris_x, iris_y)
                try:
                    expanded_delta_x, expanded_delta_y = self._compute_combined_deltas(
                        delta_head_x, delta_head_y, delta_iris_x, delta_iris_y
                    )
                finally:
                    self._dynamic_fusion_active = False

                raw_target_x = 0.5 + expanded_delta_x
                raw_target_y = 0.5 + expanded_delta_y

                if self.has_5_point_calibration:
                    mapped_x, mapped_y = self.apply_5_point_mapping(raw_target_x, raw_target_y)
                    target_x = float(np.clip(mapped_x, 0.0, 1.0))
                    target_y = float(np.clip(mapped_y, 0.0, 1.0))
                else:
                    target_x = float(np.clip(raw_target_x, 0.0, 1.0))
                    target_y = float(np.clip(raw_target_y, 0.0, 1.0))

            # Apply 1-point micro-recalibration offset ("Snap to Caret" / drift correction)
            if self.micro_offset_x != 0.0 or self.micro_offset_y != 0.0:
                target_x = float(np.clip(target_x + self.micro_offset_x, 0.0, 1.0))
                target_y = float(np.clip(target_y + self.micro_offset_y, 0.0, 1.0))

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

            # 8. Static hysteresis pinning (zero drift at rest).
            self._static_target = (target_x, target_y)
            self.smoothed_x, self.smoothed_y = self._apply_static_pinning(
                self.smoothed_x, self.smoothed_y
            )

            debug_info.update({
                "target_raw": (raw_target_x, raw_target_y),
                "target_calibrated": (target_x, target_y),
                "raw_head": (head_x, head_y),
                "raw_iris": (iris_x, iris_y),
                "is_blinking": self.is_blinking,
                "is_fixated": self.is_fixated,
                "stability_score": self.stability_score,
                "is_static_pinned": self._is_pinned,
                "static_pin": self._pinned_pos,
                "iris_velocity": self._iris_velocity,
                "effective_iris_weight": self._effective_iris_weight,
                "has_5_point_calibration": self.has_5_point_calibration,
                "calibration_rmse": self.calibration_rmse,
                "micro_offset": (self.micro_offset_x, self.micro_offset_y),
            })

            return self._finite_unit(self.smoothed_x), self._finite_unit(self.smoothed_y), True, debug_info

        except (IndexError, AttributeError, TypeError, ValueError):
            return self._finite_unit(self.smoothed_x), self._finite_unit(self.smoothed_y), False, debug_info

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
            raw_x = 0.5 + expanded_delta_x
            raw_y = 0.5 + expanded_delta_y
            if not (math.isfinite(raw_x) and math.isfinite(raw_y)):
                return None
            return max(0.0, min(1.0, float(raw_x))), max(0.0, min(1.0, float(raw_y)))
        except Exception:
            return None
