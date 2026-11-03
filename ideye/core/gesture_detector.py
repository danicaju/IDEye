"""
Gesture Detector Module for IDEye (Phase 1 & Asymmetric Winks)
Detects intentional facial triggers:
1. Mouth Aspect Ratio (MAR) for hands-free clicking with debouncing & cooldown.
2. Scale-invariant Eye Aspect Ratio (EAR) for left and right eyes to detect
   asymmetric eye-winks (WINK_LEFT, WINK_RIGHT) while cleanly discriminating
   involuntary bilateral blinks and prolonged squint closures.
"""

import math
import time
from collections import deque
from enum import Enum
from typing import Optional, Any, Tuple, List, Union


class GestureState(Enum):
    """Internal states for the mouth trigger state machine."""
    IDLE_CLOSED = "IDLE_CLOSED"      # Mouth is closed, ready for action
    HOLDING_OPEN = "HOLDING_OPEN"    # Mouth is open, counting dwell/hold duration
    TRIGGERED = "TRIGGERED"          # Click event fired, waiting for release & cooldown


class GestureResult(tuple):
    """
    Backwards-compatible 3-tuple subclass for gesture detection results.
    Unpacks as (clicked, current_mar, hold_progress) while exposing rich attributes:
        .clicked (bool): True if mouth click triggered
        .mar (float): Mouth Aspect Ratio
        .progress (float): Mouth click hold progress [0.0, 1.0]
        .gestures (List[str]): List of gestures triggered in this frame (e.g. ["WINK_LEFT"])
        .last_gesture (Optional[str]): Latest gesture name
    """

    def __new__(
        cls,
        clicked: bool,
        mar: float,
        progress: float,
        gestures: Optional[List[str]] = None,
        last_gesture: Optional[str] = None,
    ):
        return super().__new__(cls, (bool(clicked), float(mar), float(progress)))

    def __init__(
        self,
        clicked: bool,
        mar: float,
        progress: float,
        gestures: Optional[List[str]] = None,
        last_gesture: Optional[str] = None,
    ):
        self.clicked: bool = bool(clicked)
        self.mar: float = float(mar)
        self.progress: float = float(progress)
        self.gestures: List[str] = gestures if gestures is not None else []
        self.last_gesture: Optional[str] = last_gesture


class GestureDetector:
    """
    Detects facial triggers:
    1. Mouth-open click using inner lip landmarks from MediaPipe FaceMesh.
    2. Left and right eye winks using 6-point scale-invariant Eye Aspect Ratio (EAR)
       with debounce (150ms-450ms hold) and cooldown (400ms).

    Formula (MAR):
        MAR = ||p_top - p_bottom|| / (||p_left - p_right|| + eps)

    Formula (EAR):
        EAR = (||p_top1 - p_bot1|| + ||p_top2 - p_bot2||) / (2.0 * ||p_corner1 - p_corner2|| + eps)
    """

    def __init__(
        self,
        mar_threshold: float = 0.45,
        release_threshold: float = 0.35,
        hold_time_sec: float = 0.15,
        cooldown_sec: float = 0.35,
        top_lip_idx: int = 13,
        bottom_lip_idx: int = 14,
        left_corner_idx: int = 78,
        right_corner_idx: int = 308,
        ear_close_threshold: float = 0.16,
        ear_open_threshold: float = 0.22,
        wink_min_hold_sec: float = 0.15,
        wink_max_hold_sec: float = 0.45,
        wink_cooldown_sec: float = 0.40,
        wink_trigger_on_release: bool = True,
        wink_opposite_margin: float = 0.035,
        wink_enabled: bool = True,
        wink_mouth_only: bool = False,
        wink_difficulty: str = "normal",
        wink_distance_compensation: bool = True,
        wink_min_interocular_dist: float = 0.075,
        wink_max_roll_deg: float = 28.0,
        wink_max_yaw_ratio: float = 0.55,
        wink_double_window_sec: float = 0.90,
        wink_double_enabled: bool = False,
        left_eye_indices: Tuple[int, ...] = (33, 160, 158, 133, 153, 144),
        right_eye_indices: Tuple[int, ...] = (362, 385, 387, 263, 373, 380),
        micro_gestures_enabled: bool = True,
        brow_raise_ratio: float = 1.28,
        brow_hold_sec: float = 0.20,
        brow_cooldown_sec: float = 1.20,
        head_tilt_deg: float = 18.0,
        head_tilt_hold_sec: float = 0.30,
        head_tilt_cooldown_sec: float = 0.90,
    ):
        self.mar_threshold = float(mar_threshold)
        self.release_threshold = float(release_threshold)
        self.hold_time_sec = float(hold_time_sec)
        self.cooldown_sec = float(cooldown_sec)

        self.top_lip_idx = top_lip_idx
        self.bottom_lip_idx = bottom_lip_idx
        self.left_corner_idx = left_corner_idx
        self.right_corner_idx = right_corner_idx

        # Wink detection parameters
        self.ear_close_threshold = float(ear_close_threshold)
        self.ear_open_threshold = float(ear_open_threshold)
        self.wink_min_hold_sec = float(wink_min_hold_sec)
        self.wink_max_hold_sec = float(wink_max_hold_sec)
        self.wink_cooldown_sec = float(wink_cooldown_sec)
        self.wink_trigger_on_release = bool(wink_trigger_on_release)
        self.wink_opposite_margin = max(0.0, float(wink_opposite_margin))
        self.wink_enabled = bool(wink_enabled)
        self.wink_mouth_only = bool(wink_mouth_only)
        self.wink_difficulty = str(wink_difficulty or "normal").lower()
        self.wink_distance_compensation = bool(wink_distance_compensation)
        self.wink_min_interocular_dist = max(0.0, float(wink_min_interocular_dist))
        self.wink_max_roll_deg = max(1.0, float(wink_max_roll_deg))
        self.wink_max_yaw_ratio = max(0.05, float(wink_max_yaw_ratio))
        self.wink_double_window_sec = max(0.1, float(wink_double_window_sec))
        self.wink_double_enabled = bool(wink_double_enabled)
        self._wink_base_min_hold = self.wink_min_hold_sec
        self._wink_base_max_hold = self.wink_max_hold_sec
        self._wink_base_cooldown = self.wink_cooldown_sec
        self._wink_base_margin = self.wink_opposite_margin
        self.left_eye_indices = left_eye_indices
        self.right_eye_indices = right_eye_indices

        # Per-eye adaptive EAR calibration. The fixed thresholds above remain
        # the fallback and the values exposed to existing callers.
        self.ear_auto_calibrate = True
        self.left_ear_baseline: Optional[float] = None
        self.right_ear_baseline: Optional[float] = None
        self.left_ear_close_threshold = self.ear_close_threshold
        self.right_ear_close_threshold = self.ear_close_threshold
        self.left_ear_open_threshold = self.ear_open_threshold
        self.right_ear_open_threshold = self.ear_open_threshold
        self._left_open_ear_samples: deque = deque(maxlen=45)
        self._right_open_ear_samples: deque = deque(maxlen=45)
        self.last_left_double_wink_time: float = 0.0
        self.last_right_double_wink_time: float = 0.0
        self._apply_wink_difficulty()

        # Mouth state tracking & adaptive resting baseline (Anti-Midas protection)
        self.mar_auto_calibrate: bool = True
        self.mar_calibrated: bool = False
        self.mar_baseline: Optional[float] = None
        self._mar_samples: deque = deque(maxlen=90)
        self.state: GestureState = GestureState.IDLE_CLOSED
        self.open_start_time: Optional[float] = None
        self.last_trigger_time: float = 0.0
        self.released_since_trigger: bool = True
        self.current_mar: float = 0.0
        self.hold_progress: float = 0.0  # Normalized progress [0.0, 1.0] towards trigger
        self.total_clicks: int = 0

        # Wink state tracking
        self.current_left_ear: float = 0.0
        self.current_right_ear: float = 0.0
        self.left_wink_start_time: Optional[float] = None
        self.left_wink_invalid: bool = False
        self.left_wink_triggered: bool = False
        self.last_left_wink_time: float = 0.0

        self.right_wink_start_time: Optional[float] = None
        self.right_wink_invalid: bool = False
        self.right_wink_triggered: bool = False
        self.last_right_wink_time: float = 0.0

        self.last_wink_time: float = 0.0
        self.triggered_gestures: List[str] = []
        self.last_gesture: Optional[str] = None
        self.micro_gestures_enabled = bool(micro_gestures_enabled)
        self.brow_raise_ratio = float(brow_raise_ratio)
        self.brow_hold_sec = float(brow_hold_sec)
        self.brow_cooldown_sec = float(brow_cooldown_sec)
        self.head_tilt_deg = float(head_tilt_deg)
        self.head_tilt_hold_sec = float(head_tilt_hold_sec)
        self.head_tilt_cooldown_sec = float(head_tilt_cooldown_sec)
        self.brow_baseline: Optional[float] = None
        self.brow_start_time: Optional[float] = None
        self.last_brow_time: float = 0.0
        self.tilt_start_time: Optional[float] = None
        self.tilt_direction: int = 0
        self.last_tilt_time: float = 0.0

    @staticmethod
    def _euclidean_distance_2d(p1: Any, p2: Any) -> float:
        """
        Computes 2D euclidean distance with safety checks against None/NaN.
        """
        try:
            dx = float(p1.x - p2.x)
            dy = float(p1.y - p2.y)
            if math.isnan(dx) or math.isnan(dy) or math.isinf(dx) or math.isinf(dy):
                return 0.0
            return math.sqrt(dx * dx + dy * dy)
        except (AttributeError, TypeError, ValueError):
            return 0.0

    def compute_mar(self, face_landmarks: Any) -> float:
        """
        Calculates Mouth Aspect Ratio (MAR) using MediaPipe landmarks safely.
        Guarantees NO ZeroDivisionError if landmarks overlap.
        """
        if face_landmarks is None:
            return 0.0

        try:
            landmarks = getattr(face_landmarks, "landmark", face_landmarks)
            if not landmarks:
                return 0.0

            p_top = landmarks[self.top_lip_idx]
            p_bottom = landmarks[self.bottom_lip_idx]
            p_left = landmarks[self.left_corner_idx]
            p_right = landmarks[self.right_corner_idx]

            d_vertical = self._euclidean_distance_2d(p_top, p_bottom)
            d_horizontal = self._euclidean_distance_2d(p_left, p_right)

            if d_horizontal < 1e-4:
                return 0.0
            mar = d_vertical / d_horizontal

            if math.isnan(mar) or math.isinf(mar):
                return 0.0
            return max(0.0, min(float(mar), 5.0))

        except (IndexError, AttributeError, TypeError, ValueError):
            return 0.0

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

    def get_effective_mar_thresholds(self) -> Tuple[float, float]:
        """
        Calculates dynamic trigger and release thresholds relative to the user's
        adaptive resting baseline (Anti-Midas protection).

        Guarantees:
        1. When mouth is at rest (even with high natural MAR 0.30-0.45), trigger
           is always safely above rest (at least baseline + 0.14 and baseline * 1.40).
        2. Strict hysteresis prevents noise jitter from causing click loops.
        """
        base = (
            self.mar_baseline
            if self.mar_baseline is not None
            else 0.20
        )

        if self.mar_calibrated:
            # Calibrated explicitly in Step 6
            trigger = max(self.mar_threshold, base + 0.12, 0.30)
            release = min(trigger - 0.08, max(self.release_threshold, base + 0.04))
        else:
            # Uncalibrated / auto-adaptive baseline
            adaptive_trigger = max(base + 0.14, base * 1.40, 0.38)
            trigger = max(self.mar_threshold, adaptive_trigger)
            adaptive_release = max(base + 0.04, base * 1.15)
            release = min(trigger - 0.08, max(self.release_threshold, adaptive_release))

        # Enforce minimum hysteresis of 0.06
        release = min(release, trigger - 0.06)
        return float(trigger), float(release)

    def _learn_mar_baseline(self, mar: float) -> None:
        """
        Learns the resting MAR of the user in real time from closed/relaxed mouth samples.
        Prevents open mouth holds or intentional clicks from corrupting the baseline.
        """
        if not self.mar_auto_calibrate:
            return
        if mar <= 0.0 or not math.isfinite(mar):
            return

        # Determine if mouth is currently in an open/trigger state
        curr_thresh = (
            self.mar_threshold
            if self.mar_baseline is None
            else max(self.mar_threshold, self.mar_baseline + 0.12)
        )

        if mar < curr_thresh:
            self._mar_samples.append(float(mar))
            if len(self._mar_samples) >= 8:
                sorted_samples = sorted(self._mar_samples)
                # 15th percentile accurately isolates relaxed resting state
                idx = max(0, int(len(sorted_samples) * 0.15))
                candidate = sorted_samples[idx]
                if self.mar_baseline is None:
                    self.mar_baseline = max(0.08, min(0.60, float(candidate)))
                else:
                    if candidate < self.mar_baseline:
                        self.mar_baseline = max(0.08, 0.80 * self.mar_baseline + 0.20 * candidate)
                    else:
                        self.mar_baseline = max(0.08, min(0.60, 0.96 * self.mar_baseline + 0.04 * candidate))

    def set_mar_calibration(
        self,
        threshold: float,
        baseline: Optional[float] = None,
        release_threshold: Optional[float] = None,
    ) -> bool:
        """Applies explicit MAR threshold and baseline from calibration or user settings."""
        try:
            t = float(threshold)
            if not math.isfinite(t) or t <= 0.0:
                return False
            self.mar_threshold = max(0.25, min(0.85, t))
            if baseline is not None and math.isfinite(float(baseline)):
                self.mar_baseline = max(0.08, min(0.60, float(baseline)))
            if release_threshold is not None and math.isfinite(float(release_threshold)):
                self.release_threshold = max(0.15, min(self.mar_threshold - 0.05, float(release_threshold)))
            else:
                base = self.mar_baseline if self.mar_baseline is not None else 0.20
                self.release_threshold = max(0.15, min(self.mar_threshold - 0.08, base + 0.05))
            self.mar_calibrated = True
            return True
        except (TypeError, ValueError, OverflowError):
            return False

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

    def _wink_quality_ok(self, face_landmarks: Any) -> bool:
        """Rejects winks when the face is too far, tilted or turned away."""
        try:
            landmarks = getattr(face_landmarks, "landmark", face_landmarks)
            if not landmarks:
                return False
            interocular = self._euclidean_distance_2d(landmarks[33], landmarks[263])
            if interocular <= 1e-4:
                return False
            if self.wink_distance_compensation and interocular < self.wink_min_interocular_dist:
                return False
            roll = self.compute_head_roll(face_landmarks)
            if abs(roll) > self.wink_max_roll_deg:
                return False
            nose_x = float(landmarks[1].x)
            mid_x = (float(landmarks[33].x) + float(landmarks[263].x)) * 0.5
            yaw_ratio = abs(nose_x - mid_x) / interocular
            if not math.isfinite(yaw_ratio) or yaw_ratio > self.wink_max_yaw_ratio:
                return False
            return True
        except (AttributeError, IndexError, TypeError, ValueError, OverflowError):
            return False

    def _wink_trigger_allowed(self, side: str, now: float) -> bool:
        if now - self.last_wink_time >= self.wink_cooldown_sec:
            return True
        if self.wink_double_enabled:
            last_side = self.last_left_wink_time if side == "left" else self.last_right_wink_time
            elapsed = now - last_side
            return 0.0 < elapsed <= self.wink_double_window_sec
        return False

    def _emit_wink(self, side: str, now: float) -> None:
        side_upper = side.upper()
        last_side = self.last_left_wink_time if side == "left" else self.last_right_wink_time
        is_double = bool(
            self.wink_double_enabled
            and last_side > 0.0
            and 0.0 < now - last_side <= self.wink_double_window_sec
        )
        gesture = f"WINK_{side_upper}_DOUBLE" if is_double else f"WINK_{side_upper}"
        self.triggered_gestures.append(gesture)
        self.last_gesture = gesture
        self.last_wink_time = now
        if side == "left":
            self.last_left_wink_time = 0.0 if is_double else now
        else:
            self.last_right_wink_time = 0.0 if is_double else now

    def _update_wink_candidate(self, side: str, now: float, closed: bool) -> None:
        start_attr = f"{side}_wink_start_time"
        invalid_attr = f"{side}_wink_invalid"
        triggered_attr = f"{side}_wink_triggered"
        start = getattr(self, start_attr)
        if closed:
            if start is None:
                if self._wink_trigger_allowed(side, now):
                    setattr(self, start_attr, now)
                    setattr(self, invalid_attr, False)
                    setattr(self, triggered_attr, False)
                else:
                    setattr(self, invalid_attr, True)
                return
            if getattr(self, invalid_attr):
                return
            duration = now - start
            if duration > self.wink_max_hold_sec:
                setattr(self, invalid_attr, True)
            if (
                not self.wink_trigger_on_release
                and self.wink_min_hold_sec <= duration <= self.wink_max_hold_sec
                and not getattr(self, triggered_attr)
                and self._wink_trigger_allowed(side, now)
            ):
                self._emit_wink(side, now)
                setattr(self, triggered_attr, True)
            return
        if start is not None:
            duration = now - start
            if (
                self.wink_trigger_on_release
                and self.wink_min_hold_sec <= duration <= self.wink_max_hold_sec
                and not getattr(self, invalid_attr)
                and self._wink_trigger_allowed(side, now)
            ):
                self._emit_wink(side, now)
            setattr(self, start_attr, None)
            setattr(self, invalid_attr, False)
            setattr(self, triggered_attr, False)
        else:
            setattr(self, invalid_attr, False)

    def _process_winks(self, now: float, face_landmarks: Any) -> None:
        if not self.wink_enabled or self.wink_mouth_only:
            self.left_wink_start_time = None
            self.right_wink_start_time = None
            self.left_wink_invalid = True
            self.right_wink_invalid = True
            return
        if not self._wink_quality_ok(face_landmarks):
            self.left_wink_start_time = None
            self.right_wink_start_time = None
            self.left_wink_invalid = True
            self.right_wink_invalid = True
            return

        self._learn_ear_baseline(self.current_left_ear, self.current_right_ear)
        left_closed = self.current_left_ear <= self.left_ear_close_threshold
        right_closed = self.current_right_ear <= self.right_ear_close_threshold
        left_open = self.current_left_ear >= (
            self.left_ear_open_threshold + self.wink_opposite_margin
        )
        right_open = self.current_right_ear >= (
            self.right_ear_open_threshold + self.wink_opposite_margin
        )

        if left_closed and right_closed:
            self.left_wink_start_time = None
            self.left_wink_invalid = True
            self.right_wink_start_time = None
            self.right_wink_invalid = True
            return

        self._update_wink_candidate("left", now, left_closed and right_open)
        self._update_wink_candidate("right", now, right_closed and left_open)

    def compute_brow_raise(self, face_landmarks: Any) -> float:
        """Scale-invariant eyebrow height relative to the eye line."""
        if face_landmarks is None:
            return 0.0
        try:
            landmarks = getattr(face_landmarks, "landmark", face_landmarks)
            eye_span = self._euclidean_distance_2d(landmarks[33], landmarks[263])
            if eye_span < 1e-4:
                return 0.0
            brow_y = sum(float(landmarks[i].y) for i in (65, 105, 295, 334)) / 4.0
            eye_y = sum(float(landmarks[i].y) for i in (33, 133, 362, 263)) / 4.0
            ratio = abs(eye_y - brow_y) / eye_span
            if math.isnan(ratio) or math.isinf(ratio):
                return 0.0
            return max(0.0, min(float(ratio), 5.0))
        except (AttributeError, IndexError, TypeError, ValueError):
            return 0.0

    def compute_head_roll(self, face_landmarks: Any) -> float:
        """Interocular roll in degrees (positive = right side lower)."""
        if face_landmarks is None:
            return 0.0
        try:
            landmarks = getattr(face_landmarks, "landmark", face_landmarks)
            left = landmarks[33]
            right = landmarks[263]
            dx = float(right.x) - float(left.x)
            dy = float(right.y) - float(left.y)
            if not math.isfinite(dx) or not math.isfinite(dy):
                return 0.0
            return float(math.degrees(math.atan2(dy, dx)))
        except (AttributeError, IndexError, TypeError, ValueError, OverflowError):
            return 0.0

    def process(
        self,
        face_landmarks: Any,
        current_time: Optional[float] = None,
    ) -> GestureResult:
        """
        Processes current frame landmarks and updates state machines for:
        1. Mouth click gesture (MAR)
        2. Eye wink gestures (WINK_LEFT, WINK_RIGHT)

        Args:
            face_landmarks: MediaPipe FaceMesh landmarks for a detected face.
            current_time: Optional timestamp (defaults to time.perf_counter()).

        Returns:
            GestureResult tuple (click_event, current_mar, hold_progress)
            with .gestures list attribute containing triggered gestures.
        """
        now = time.perf_counter() if current_time is None else current_time
        self.current_mar = self.compute_mar(face_landmarks)
        self.current_left_ear, self.current_right_ear = self.compute_ear(face_landmarks)
        self.triggered_gestures = []
        click_event = False

        # If face is lost, reset holding states to avoid ghost triggers
        if face_landmarks is None:
            if self.state == GestureState.HOLDING_OPEN:
                self.state = GestureState.IDLE_CLOSED
                self.open_start_time = None
                self.hold_progress = 0.0
            self.left_wink_start_time = None
            self.left_wink_invalid = False
            self.left_wink_triggered = False
            self.right_wink_start_time = None
            self.right_wink_invalid = False
            self.right_wink_triggered = False
            self.brow_start_time = None
            self.tilt_start_time = None
            return GestureResult(False, self.current_mar, self.hold_progress, [], self.last_gesture)

        # ----------------------------------------------------------------------
        # 1. Mouth Aspect Ratio (MAR) State Machine with Adaptive Baseline
        # ----------------------------------------------------------------------
        if self.state != GestureState.HOLDING_OPEN:
            self._learn_mar_baseline(self.current_mar)

        trigger_thresh, release_thresh = self.get_effective_mar_thresholds()
        is_open = self.current_mar >= trigger_thresh
        is_closed = self.current_mar <= release_thresh
        time_since_trigger = now - self.last_trigger_time

        if self.state == GestureState.IDLE_CLOSED:
            self.hold_progress = 0.0
            if is_closed:
                self.released_since_trigger = True
            if is_open:
                if time_since_trigger >= self.cooldown_sec and self.released_since_trigger:
                    self.state = GestureState.HOLDING_OPEN
                    self.open_start_time = now

        elif self.state == GestureState.HOLDING_OPEN:
            if not is_open:
                self.state = GestureState.IDLE_CLOSED
                self.open_start_time = None
                self.hold_progress = 0.0
                if is_closed:
                    self.released_since_trigger = True
            else:
                elapsed = now - (self.open_start_time or now)
                self.hold_progress = min(1.0, max(0.0, elapsed / max(self.hold_time_sec, 1e-6)))

                if elapsed >= self.hold_time_sec:
                    click_event = True
                    self.total_clicks += 1
                    self.last_trigger_time = now
                    self.released_since_trigger = False
                    self.state = GestureState.TRIGGERED
                    self.hold_progress = 1.0
                    self.triggered_gestures.append("MOUTH_CLICK")
                    self.last_gesture = "MOUTH_CLICK"

        elif self.state == GestureState.TRIGGERED:
            if is_closed:
                self.released_since_trigger = True
                self.hold_progress = 0.0
            else:
                self.hold_progress = 0.0

            if time_since_trigger >= self.cooldown_sec and self.released_since_trigger:
                if is_open:
                    self.state = GestureState.HOLDING_OPEN
                    self.open_start_time = now
                    self.hold_progress = 0.0
                else:
                    self.state = GestureState.IDLE_CLOSED
                    self.open_start_time = None
                    self.hold_progress = 0.0

        # ----------------------------------------------------------------------
        # 2. Eye Wink Detection State Machine (EAR)
        # ----------------------------------------------------------------------
        self._process_winks(now, face_landmarks)

        # ------------------------------------------------------------------
        # 3. Optional expressive micro-gestures (brow raise + head tilt)
        # ------------------------------------------------------------------
        if self.micro_gestures_enabled and self.current_mar < self.release_threshold:
            brow = self.compute_brow_raise(face_landmarks)
            if brow > 0.0:
                if self.brow_baseline is None:
                    self.brow_baseline = brow
                elif brow > self.brow_baseline * self.brow_raise_ratio:
                    if self.brow_start_time is None:
                        self.brow_start_time = now
                    elif (
                        now - self.brow_start_time >= self.brow_hold_sec
                        and now - self.last_brow_time >= self.brow_cooldown_sec
                    ):
                        self.triggered_gestures.append("BROW_RAISE")
                        self.last_gesture = "BROW_RAISE"
                        self.last_brow_time = now
                        self.brow_start_time = None
                else:
                    self.brow_start_time = None
                    self.brow_baseline = 0.98 * self.brow_baseline + 0.02 * brow

            roll = self.compute_head_roll(face_landmarks)
            direction = 1 if roll > self.head_tilt_deg else -1 if roll < -self.head_tilt_deg else 0
            if direction == 0:
                self.tilt_start_time = None
                self.tilt_direction = 0
            elif direction != self.tilt_direction:
                self.tilt_direction = direction
                self.tilt_start_time = now
            elif (
                self.tilt_start_time is not None
                and now - self.tilt_start_time >= self.head_tilt_hold_sec
                and now - self.last_tilt_time >= self.head_tilt_cooldown_sec
            ):
                gesture = "HEAD_TILT_RIGHT" if direction > 0 else "HEAD_TILT_LEFT"
                self.triggered_gestures.append(gesture)
                self.last_gesture = gesture
                self.last_tilt_time = now
                self.tilt_start_time = None
        else:
            self.brow_start_time = None
            self.tilt_start_time = None

        return GestureResult(
            click_event,
            self.current_mar,
            self.hold_progress,
            self.triggered_gestures,
            self.last_gesture,
        )

    def reset(self) -> None:
        """Resets the state machines and tracking metrics."""
        self.state = GestureState.IDLE_CLOSED
        self.open_start_time = None
        self.last_trigger_time = 0.0
        self.released_since_trigger = True
        self.current_mar = 0.0
        self.hold_progress = 0.0
        self.current_left_ear = 0.0
        self.current_right_ear = 0.0
        self.left_wink_start_time = None
        self.left_wink_invalid = False
        self.left_wink_triggered = False
        self.right_wink_start_time = None
        self.right_wink_invalid = False
        self.right_wink_triggered = False
        self.last_wink_time = 0.0
        self.last_left_wink_time = 0.0
        self.last_right_wink_time = 0.0
        self.last_left_double_wink_time = 0.0
        self.last_right_double_wink_time = 0.0
        try:
            self._left_open_ear_samples.clear()
            self._right_open_ear_samples.clear()
        except Exception:
            pass
        self.triggered_gestures = []
        self.last_gesture = None
        self.brow_baseline = None
        self.brow_start_time = None
        self.last_brow_time = 0.0
        self.tilt_start_time = None
        self.tilt_direction = 0
        self.last_tilt_time = 0.0
