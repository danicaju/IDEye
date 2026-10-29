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
        self.left_eye_indices = left_eye_indices
        self.right_eye_indices = right_eye_indices

        # Mouth state tracking
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
        # 1. Mouth Aspect Ratio (MAR) State Machine
        # ----------------------------------------------------------------------
        is_open = self.current_mar >= self.mar_threshold
        is_closed = self.current_mar <= self.release_threshold
        time_since_trigger = now - self.last_trigger_time

        if self.state == GestureState.IDLE_CLOSED:
            self.hold_progress = 0.0
            if is_open:
                if time_since_trigger >= self.cooldown_sec and self.released_since_trigger:
                    self.state = GestureState.HOLDING_OPEN
                    self.open_start_time = now

        elif self.state == GestureState.HOLDING_OPEN:
            if not is_open:
                self.state = GestureState.IDLE_CLOSED
                self.open_start_time = None
                self.hold_progress = 0.0
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
        left_closed = self.current_left_ear < self.ear_close_threshold
        right_closed = self.current_right_ear < self.ear_close_threshold
        left_open = self.current_left_ear > self.ear_open_threshold
        right_open = self.current_right_ear > self.ear_open_threshold

        time_since_last_wink = now - self.last_wink_time

        if left_closed and right_closed:
            # Bilateral blink detected: invalidate active wink candidates
            self.left_wink_start_time = None
            self.left_wink_invalid = True
            self.right_wink_start_time = None
            self.right_wink_invalid = True
        else:
            # Evaluate Left Eye Wink Candidate (Left closed, Right open)
            if left_closed and right_open:
                if self.left_wink_start_time is None:
                    if time_since_last_wink >= self.wink_cooldown_sec:
                        self.left_wink_start_time = now
                        self.left_wink_invalid = False
                        self.left_wink_triggered = False
                    else:
                        # Attempted wink during active cooldown: mark invalid until full release
                        self.left_wink_invalid = True
                elif not self.left_wink_invalid:
                    duration = now - self.left_wink_start_time
                    if duration > self.wink_max_hold_sec:
                        self.left_wink_invalid = True
                    if not self.wink_trigger_on_release:
                        if (
                            (self.wink_min_hold_sec <= duration <= self.wink_max_hold_sec)
                            and not self.left_wink_triggered
                        ):
                            if time_since_last_wink >= self.wink_cooldown_sec:
                                self.triggered_gestures.append("WINK_LEFT")
                                self.last_gesture = "WINK_LEFT"
                                self.last_wink_time = now
                                self.last_left_wink_time = now
                                self.left_wink_triggered = True

            if self.left_wink_start_time is not None and not left_closed:
                # Left eye released / reopened
                duration = now - self.left_wink_start_time
                if self.wink_trigger_on_release:
                    if (self.wink_min_hold_sec <= duration <= self.wink_max_hold_sec) and not self.left_wink_invalid:
                        if time_since_last_wink >= self.wink_cooldown_sec:
                            self.triggered_gestures.append("WINK_LEFT")
                            self.last_gesture = "WINK_LEFT"
                            self.last_wink_time = now
                            self.last_left_wink_time = now
                self.left_wink_start_time = None
                self.left_wink_invalid = False
                self.left_wink_triggered = False
            elif not left_closed:
                self.left_wink_invalid = False

            # Evaluate Right Eye Wink Candidate (Right closed, Left open)
            if right_closed and left_open:
                if self.right_wink_start_time is None:
                    if time_since_last_wink >= self.wink_cooldown_sec:
                        self.right_wink_start_time = now
                        self.right_wink_invalid = False
                        self.right_wink_triggered = False
                    else:
                        # Attempted wink during active cooldown: mark invalid until full release
                        self.right_wink_invalid = True
                elif not self.right_wink_invalid:
                    duration = now - self.right_wink_start_time
                    if duration > self.wink_max_hold_sec:
                        self.right_wink_invalid = True
                    if not self.wink_trigger_on_release:
                        if (
                            (self.wink_min_hold_sec <= duration <= self.wink_max_hold_sec)
                            and not self.right_wink_triggered
                        ):
                            if time_since_last_wink >= self.wink_cooldown_sec:
                                self.triggered_gestures.append("WINK_RIGHT")
                                self.last_gesture = "WINK_RIGHT"
                                self.last_wink_time = now
                                self.last_right_wink_time = now
                                self.right_wink_triggered = True

            if self.right_wink_start_time is not None and not right_closed:
                # Right eye released / reopened
                duration = now - self.right_wink_start_time
                if self.wink_trigger_on_release:
                    if (self.wink_min_hold_sec <= duration <= self.wink_max_hold_sec) and not self.right_wink_invalid:
                        if time_since_last_wink >= self.wink_cooldown_sec:
                            self.triggered_gestures.append("WINK_RIGHT")
                            self.last_gesture = "WINK_RIGHT"
                            self.last_wink_time = now
                            self.last_right_wink_time = now
                self.right_wink_start_time = None
                self.right_wink_invalid = False
                self.right_wink_triggered = False
            elif not right_closed:
                self.right_wink_invalid = False

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
        self.triggered_gestures = []
        self.last_gesture = None
        self.brow_baseline = None
        self.brow_start_time = None
        self.last_brow_time = 0.0
        self.tilt_start_time = None
        self.tilt_direction = 0
        self.last_tilt_time = 0.0
