"""EAR computation, wink tuning and EAR calibration for GestureDetector."""

import math
import time
from collections import deque
from enum import Enum
from typing import Optional, Any, Tuple, List, Union

from ideye.core.gesture_types import GestureResult, GestureState  # noqa: F401


class GestureEarMixin:
    """Eye aspect ratio methods."""

    def compute_ear(self, face_landmarks: Any) -> Tuple[float, float]:
        """
        Calculates scale-invariant Eye Aspect Ratio (EAR) for left and right eyes safely.
        Guarantees NO ZeroDivisionError if landmarks overlap.

        Formula:
            EAR = (||p_top1 - p_bot1|| + ||p_top2 - p_bot2||) / (2.0 * max(||p_corner1 - p_corner2||, eps))
        Returns:
            Tuple of (left_ear, right_ear).
        """
        if face_landmarks is None:
            return 0.0, 0.0

        try:
            landmarks = getattr(face_landmarks, "landmark", face_landmarks)
            if not landmarks:
                return 0.0, 0.0

            # Left eye
            p_l_outer = landmarks[self.left_eye_indices[0]]   # 33
            p_l_top1 = landmarks[self.left_eye_indices[1]]    # 160
            p_l_top2 = landmarks[self.left_eye_indices[2]]    # 158
            p_l_inner = landmarks[self.left_eye_indices[3]]   # 133
            p_l_bot2 = landmarks[self.left_eye_indices[4]]    # 153
            p_l_bot1 = landmarks[self.left_eye_indices[5]]    # 144

            d_v_l1 = self._euclidean_distance_2d(p_l_top1, p_l_bot1)
            d_v_l2 = self._euclidean_distance_2d(p_l_top2, p_l_bot2)
            d_h_l = self._euclidean_distance_2d(p_l_outer, p_l_inner)
            if d_h_l < 1e-4:
                left_ear = 0.0
            else:
                ear_l = (d_v_l1 + d_v_l2) / (2.0 * d_h_l)
                if math.isnan(ear_l) or math.isinf(ear_l):
                    left_ear = 0.0
                else:
                    left_ear = max(0.0, min(float(ear_l), 5.0))

            # Right eye
            p_r_inner = landmarks[self.right_eye_indices[0]]  # 362
            p_r_top1 = landmarks[self.right_eye_indices[1]]   # 385
            p_r_top2 = landmarks[self.right_eye_indices[2]]   # 387
            p_r_outer = landmarks[self.right_eye_indices[3]]  # 263
            p_r_bot2 = landmarks[self.right_eye_indices[4]]   # 373
            p_r_bot1 = landmarks[self.right_eye_indices[5]]   # 380

            d_v_r1 = self._euclidean_distance_2d(p_r_top1, p_r_bot1)
            d_v_r2 = self._euclidean_distance_2d(p_r_top2, p_r_bot2)
            d_h_r = self._euclidean_distance_2d(p_r_inner, p_r_outer)
            if d_h_r < 1e-4:
                right_ear = 0.0
            else:
                ear_r = (d_v_r1 + d_v_r2) / (2.0 * d_h_r)
                if math.isnan(ear_r) or math.isinf(ear_r):
                    right_ear = 0.0
                else:
                    right_ear = max(0.0, min(float(ear_r), 5.0))

            return left_ear, right_ear

        except (IndexError, AttributeError, TypeError, ValueError):
            return 0.0, 0.0

    def compute_left_ear(self, face_landmarks: Any) -> float:
        """Returns scale-invariant Eye Aspect Ratio (EAR) for the left eye."""
        return self.compute_ear(face_landmarks)[0]

    def compute_right_ear(self, face_landmarks: Any) -> float:
        """Returns scale-invariant Eye Aspect Ratio (EAR) for the right eye."""
        return self.compute_ear(face_landmarks)[1]

    @staticmethod
    def _median(values: List[float]) -> Optional[float]:
        cleaned = sorted(float(v) for v in values if math.isfinite(float(v)))
        if not cleaned:
            return None
        mid = len(cleaned) // 2
        if len(cleaned) % 2:
            return cleaned[mid]
        return (cleaned[mid - 1] + cleaned[mid]) / 2.0

    def _apply_wink_difficulty(self) -> None:
        """Scales hold/cooldown/margin from the selected difficulty preset."""
        difficulty = str(getattr(self, "wink_difficulty", "normal")).lower()
        if difficulty == "relaxed":
            factor_min, factor_max, factor_cd, factor_margin = 0.82, 1.20, 0.85, 0.80
        elif difficulty == "strict":
            factor_min, factor_max, factor_cd, factor_margin = 1.18, 0.82, 1.18, 1.25
        else:
            factor_min = factor_max = factor_cd = factor_margin = 1.0
        self.wink_min_hold_sec = max(0.10, self._wink_base_min_hold * factor_min)
        self.wink_max_hold_sec = max(self.wink_min_hold_sec + 0.05, self._wink_base_max_hold * factor_max)
        self.wink_cooldown_sec = max(0.20, self._wink_base_cooldown * factor_cd)
        self.wink_opposite_margin = max(0.0, self._wink_base_margin * factor_margin)

    def configure_wink(self, **settings: Any) -> None:
        """Applies runtime wink settings without rebuilding the detector."""
        base_keys = {
            "wink_min_hold_sec": "_wink_base_min_hold",
            "wink_max_hold_sec": "_wink_base_max_hold",
            "wink_cooldown_sec": "_wink_base_cooldown",
            "wink_opposite_margin": "_wink_base_margin",
        }
        for key, attr in base_keys.items():
            if key in settings and settings[key] is not None:
                try:
                    setattr(self, attr, max(0.0, float(settings[key])))
                except (TypeError, ValueError):
                    pass
        if "wink_enabled" in settings:
            self.wink_enabled = bool(settings["wink_enabled"])
        if "wink_mouth_only" in settings:
            self.wink_mouth_only = bool(settings["wink_mouth_only"])
        if "wink_distance_compensation" in settings:
            self.wink_distance_compensation = bool(settings["wink_distance_compensation"])
        if "wink_difficulty" in settings and settings["wink_difficulty"] is not None:
            self.wink_difficulty = str(settings["wink_difficulty"]).lower()
        self._apply_wink_difficulty()

    def set_ear_calibration(self, profile: Optional[dict] = None) -> bool:
        """Applies per-eye open/closed EAR values from calibration or profile."""
        if not isinstance(profile, dict):
            return False
        left_open = profile.get("left_open", profile.get("left_ear_open"))
        right_open = profile.get("right_open", profile.get("right_ear_open"))
        try:
            if left_open is not None and math.isfinite(float(left_open)):
                self.left_ear_baseline = max(0.05, min(1.0, float(left_open)))
            if right_open is not None and math.isfinite(float(right_open)):
                self.right_ear_baseline = max(0.05, min(1.0, float(right_open)))
        except (TypeError, ValueError, OverflowError):
            return False
        if self.left_ear_baseline is None and self.right_ear_baseline is None:
            return False
        self.ear_auto_calibrate = False
        self._rebuild_ear_thresholds()
        return True

    def calibrate_ear_from_samples(
        self,
        left_open_samples: Optional[List[float]] = None,
        right_open_samples: Optional[List[float]] = None,
    ) -> bool:
        """Derives per-eye open baselines from explicit open-eye samples."""
        left = self._median(list(left_open_samples or []))
        right = self._median(list(right_open_samples or []))
        if left is None and right is None:
            return False
        if left is not None:
            self.left_ear_baseline = max(0.05, min(1.0, left))
        if right is not None:
            self.right_ear_baseline = max(0.05, min(1.0, right))
        self.ear_auto_calibrate = False
        self._rebuild_ear_thresholds()
        return True

    def _rebuild_ear_thresholds(self) -> None:
        for side in ("left", "right"):
            baseline = getattr(self, f"{side}_ear_baseline")
            if baseline is None:
                close = self.ear_close_threshold
                open_threshold = self.ear_open_threshold
            else:
                close = max(float(getattr(self, "ear_close_threshold", 0.16)), baseline * 0.55)
                open_threshold = max(close + 0.04, baseline * 0.75)
            setattr(self, f"{side}_ear_close_threshold", close)
            setattr(self, f"{side}_ear_open_threshold", open_threshold)

    def _learn_ear_baseline(self, left_ear: float, right_ear: float) -> None:
        if not self.ear_auto_calibrate:
            return
        if left_ear <= 0.0 or right_ear <= 0.0:
            return
        if left_ear < self.left_ear_open_threshold or right_ear < self.right_ear_open_threshold:
            return
        self._left_open_ear_samples.append(float(left_ear))
        self._right_open_ear_samples.append(float(right_ear))
        if len(self._left_open_ear_samples) < 12:
            return
        left = self._median(list(self._left_open_ear_samples))
        right = self._median(list(self._right_open_ear_samples))
        if left is not None:
            self.left_ear_baseline = max(0.05, min(1.0, left))
        if right is not None:
            self.right_ear_baseline = max(0.05, min(1.0, right))
        self._rebuild_ear_thresholds()
