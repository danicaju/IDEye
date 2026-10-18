"""
Gesture Detector Module for IDEye (Phase 1)
Detects intentional facial triggers, specifically the Mouth Aspect Ratio (MAR)
for hands-free clicking with debouncing, cooldown, and zero-division protection.
"""

import math
import time
from enum import Enum
from typing import Optional, Any, Tuple


class GestureState(Enum):
    """Internal states for the mouth trigger state machine."""
    IDLE_CLOSED = "IDLE_CLOSED"      # Mouth is closed, ready for action
    HOLDING_OPEN = "HOLDING_OPEN"    # Mouth is open, counting dwell/hold duration
    TRIGGERED = "TRIGGERED"          # Click event fired, waiting for release & cooldown


class GestureDetector:
    """
    Detects mouth-open trigger gestures using inner lip landmarks from MediaPipe FaceMesh.
    
    Formula:
        MAR = ||p_top - p_bottom|| / (||p_left - p_right|| + eps)
    
    A CLICK is dispatched only when the mouth remains open above `mar_threshold`
    for at least `hold_time_sec` (e.g., 150ms). A new click requires the mouth
    to be closed (`mar < release_threshold`) and `cooldown_sec` to elapse.
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
    ):
        self.mar_threshold = float(mar_threshold)
        self.release_threshold = float(release_threshold)
        self.hold_time_sec = float(hold_time_sec)
        self.cooldown_sec = float(cooldown_sec)

        self.top_lip_idx = top_lip_idx
        self.bottom_lip_idx = bottom_lip_idx
        self.left_corner_idx = left_corner_idx
        self.right_corner_idx = right_corner_idx

        # State tracking
        self.state: GestureState = GestureState.IDLE_CLOSED
        self.open_start_time: Optional[float] = None
        self.last_trigger_time: float = 0.0
        self.released_since_trigger: bool = True
        self.current_mar: float = 0.0
        self.hold_progress: float = 0.0  # Normalized progress [0.0, 1.0] towards trigger
        self.total_clicks: int = 0

    @staticmethod
    def _euclidean_distance_2d(p1: Any, p2: Any) -> float:
        """
        Computes 2D euclidean distance with safety checks against None/NaN.
        """
        try:
            dx = float(p1.x - p2.x)
            dy = float(p1.y - p2.y)
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
            # Handle both list/iterable of landmarks and protobuf RepeatedCompositeContainer
            landmarks = getattr(face_landmarks, "landmark", face_landmarks)
            if not landmarks:
                return 0.0

            p_top = landmarks[self.top_lip_idx]
            p_bottom = landmarks[self.bottom_lip_idx]
            p_left = landmarks[self.left_corner_idx]
            p_right = landmarks[self.right_corner_idx]

            d_vertical = self._euclidean_distance_2d(p_top, p_bottom)
            d_horizontal = self._euclidean_distance_2d(p_left, p_right)

            # Defensive zero-division protection: enforce minimum non-zero denominator
            eps = 1e-6
            safe_denom = max(d_horizontal, eps)
            mar = d_vertical / safe_denom

            # Clamp between 0.0 and 5.0 to guard against wild artifacts
            return max(0.0, min(float(mar), 5.0))

        except (IndexError, AttributeError, TypeError, ValueError):
            # Gracefully handle missing landmarks or unexpected format
            return 0.0

    def process(self, face_landmarks: Any, current_time: Optional[float] = None) -> Tuple[bool, float, float]:
        """
        Processes the current frame's landmarks and updates the state machine.

        Args:
            face_landmarks: MediaPipe FaceMesh landmarks for a detected face.
            current_time: Optional timestamp (defaults to time.perf_counter()).

        Returns:
            Tuple of:
                - click_event (bool): True ONLY on the single frame when CLICK triggers.
                - current_mar (float): The calculated Mouth Aspect Ratio.
                - hold_progress (float): Normalized [0.0, 1.0] completion towards click.
        """
        now = time.perf_counter() if current_time is None else current_time
        self.current_mar = self.compute_mar(face_landmarks)
        click_event = False

        # If face is lost, reset holding state to avoid ghost clicks
        if face_landmarks is None:
            if self.state == GestureState.HOLDING_OPEN:
                self.state = GestureState.IDLE_CLOSED
                self.open_start_time = None
                self.hold_progress = 0.0
            return False, self.current_mar, self.hold_progress

        is_open = self.current_mar >= self.mar_threshold
        is_closed = self.current_mar <= self.release_threshold
        time_since_trigger = now - self.last_trigger_time

        if self.state == GestureState.IDLE_CLOSED:
            self.hold_progress = 0.0
            if is_open:
                # Check cooldown before beginning a new hold cycle
                if time_since_trigger >= self.cooldown_sec and self.released_since_trigger:
                    self.state = GestureState.HOLDING_OPEN
                    self.open_start_time = now

        elif self.state == GestureState.HOLDING_OPEN:
            if not is_open:
                # User closed or twitched mouth before reaching threshold: abort hold
                self.state = GestureState.IDLE_CLOSED
                self.open_start_time = None
                self.hold_progress = 0.0
            else:
                elapsed = now - (self.open_start_time or now)
                self.hold_progress = min(1.0, max(0.0, elapsed / max(self.hold_time_sec, 1e-6)))

                if elapsed >= self.hold_time_sec:
                    # Trigger condition met!
                    click_event = True
                    self.total_clicks += 1
                    self.last_trigger_time = now
                    self.released_since_trigger = False
                    self.state = GestureState.TRIGGERED
                    self.hold_progress = 1.0

        elif self.state == GestureState.TRIGGERED:
            # Check if user closed mouth below release threshold
            if is_closed:
                self.released_since_trigger = True
                self.hold_progress = 0.0
            else:
                self.hold_progress = 0.0

            # Once cooldown has elapsed AND mouth was closed at least once:
            if time_since_trigger >= self.cooldown_sec and self.released_since_trigger:
                if is_open:
                    # Seamlessly initiate new hold if mouth was opened after valid release
                    self.state = GestureState.HOLDING_OPEN
                    self.open_start_time = now
                    self.hold_progress = 0.0
                else:
                    self.state = GestureState.IDLE_CLOSED
                    self.open_start_time = None
                    self.hold_progress = 0.0

        return click_event, self.current_mar, self.hold_progress

    def reset(self) -> None:
        """Resets the state machine and tracking metrics."""
        self.state = GestureState.IDLE_CLOSED
        self.open_start_time = None
        self.last_trigger_time = 0.0
        self.released_since_trigger = True
        self.current_mar = 0.0
        self.hold_progress = 0.0
