"""Wink state machine and per-frame processing for GestureDetector."""

import math
import time
from collections import deque
from enum import Enum
from typing import Optional, Any, Tuple, List, Union

from ideye.core.gesture_types import GestureResult, GestureState  # noqa: F401


class GestureWinkMixin:
    """Wink detection and frame processing."""

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

    def set_cap_mode(self, enabled: bool) -> None:
        """Toggles cap mode, which suppresses brow-raise micro-gestures to prevent visor artifacts."""
        self.cap_mode = bool(enabled)

    def compute_brow_raise(self, face_landmarks: Any) -> float:
        """Scale-invariant eyebrow height relative to the eye line."""
        if self.cap_mode:
            return 0.0
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
