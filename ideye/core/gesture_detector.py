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


from ideye.core.gesture_ear import GestureEarMixin
from ideye.core.gesture_wink import GestureWinkMixin
from ideye.core.gesture_types import GestureResult, GestureState  # noqa: F401


class GestureDetector(GestureEarMixin, GestureWinkMixin):
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
        cap_mode: bool = False,
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
        self.cap_mode: bool = bool(cap_mode)
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

    def get_effective_mar_thresholds(self) -> Tuple[float, float]:
        """
        Calculates dynamic trigger and release thresholds relative to the user's
        adaptive resting baseline (Anti-Midas protection).

        Guarantees:
        1. When mouth is at rest (even with high natural MAR 0.30-0.50), trigger
           is always safely above rest (at least baseline + 0.15 and baseline * 1.50).
        2. Strict hysteresis prevents noise jitter from causing click loops.
        3. Enforces safe minimum floor so uncalibrated startup never produces ghost clicks.
        """
        base = (
            self.mar_baseline
            if self.mar_baseline is not None
            else 0.22
        )

        if self.mar_calibrated:
            # Calibrated explicitly in Step 6
            trigger = max(self.mar_threshold, base + 0.14, 0.36)
            release = min(trigger - 0.08, max(self.release_threshold, base + 0.05))
        else:
            # Uncalibrated / auto-adaptive baseline
            adaptive_trigger = max(base + 0.15, base * 1.50, 0.42)
            trigger = max(self.mar_threshold, adaptive_trigger)
            adaptive_release = max(base + 0.05, base * 1.15)
            release = min(trigger - 0.08, max(self.release_threshold, adaptive_release))

        # Enforce minimum hysteresis of 0.07
        release = min(release, trigger - 0.07)
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

        # Phase 1: Bootstrapping before initial baseline is established
        if self.mar_baseline is None:
            if mar < 0.52:
                self._mar_samples.append(float(mar))
                sorted_samples = sorted(self._mar_samples)
                idx = max(0, int(len(sorted_samples) * 0.15))
                candidate = sorted_samples[idx]
                self.mar_baseline = max(0.08, min(0.60, float(candidate)))
            return

        # Phase 2: Continual adaptation while baseline is established.
        # Only accept samples when mouth is relaxed/closed (at or below release threshold)
        # so open mouth postures, speech peaks, or intentional clicks do not elevate baseline.
        _, release_thresh = self.get_effective_mar_thresholds()
        if mar <= release_thresh:
            self._mar_samples.append(float(mar))
            if len(self._mar_samples) >= 8:
                sorted_samples = sorted(self._mar_samples)
                idx = max(0, int(len(sorted_samples) * 0.15))
                candidate = sorted_samples[idx]
                if candidate < self.mar_baseline:
                    # Responsive downward adaptation when user mouth is more closed
                    self.mar_baseline = max(0.08, 0.75 * self.mar_baseline + 0.25 * candidate)
                else:
                    # Slow, damped upward drift
                    self.mar_baseline = max(0.08, min(0.60, 0.97 * self.mar_baseline + 0.03 * candidate))

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
            elif self.mar_baseline is None:
                self.mar_baseline = max(0.12, min(0.55, self.mar_threshold - 0.18))

            if release_threshold is not None and math.isfinite(float(release_threshold)):
                self.release_threshold = max(0.15, min(self.mar_threshold - 0.05, float(release_threshold)))
            else:
                base = self.mar_baseline if self.mar_baseline is not None else 0.20
                self.release_threshold = max(0.15, min(self.mar_threshold - 0.08, base + 0.05))
            self.mar_calibrated = True
            return True
        except (TypeError, ValueError, OverflowError):
            return False

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

