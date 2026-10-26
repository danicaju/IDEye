"""Biometric health guard: blink/stare and posture distance warnings."""

from __future__ import annotations

import math
import time
from collections import deque
from typing import Any, Deque, Optional


class HealthGuard:
    """Cheap landmark-only guard for eye strain and cervical posture."""

    def __init__(
        self,
        enabled: bool = True,
        no_blink_sec: float = 28.0,
        near_ratio: float = 1.38,
        near_sec: float = 5.0,
        alert_cooldown_sec: float = 4.0,
        blink_ear: float = 0.16,
    ) -> None:
        self.enabled = bool(enabled)
        self.no_blink_sec = float(no_blink_sec)
        self.near_ratio = float(near_ratio)
        self.near_sec = float(near_sec)
        self.alert_cooldown_sec = float(alert_cooldown_sec)
        self.blink_ear = float(blink_ear)
        self.baseline_eye_span: Optional[float] = None
        self.last_blink_time: Optional[float] = None
        self.last_alert_time: float = 0.0
        self.blink_times: Deque[float] = deque(maxlen=120)
        self._eyes_closed: bool = False
        self._near_since: Optional[float] = None
        self._baseline_samples: list[float] = []

    @staticmethod
    def _pt(landmarks: Any, index: int) -> Optional[tuple[float, float]]:
        try:
            points = getattr(landmarks, "landmark", landmarks)
            point = points[index]
            return float(point.x), float(point.y)
        except (AttributeError, IndexError, TypeError, ValueError):
            return None

    def _eye_span(self, landmarks: Any) -> Optional[float]:
        left = self._pt(landmarks, 33)
        right = self._pt(landmarks, 263)
        if left is None or right is None:
            return None
        return math.hypot(right[0] - left[0], right[1] - left[1])

    def _ears(self, landmarks: Any) -> tuple[float, float]:
        def ear(indices: tuple[int, ...]) -> float:
            points = [self._pt(landmarks, idx) for idx in indices]
            if any(point is None for point in points):
                return 0.0
            p = points  # type: ignore[assignment]
            v1 = math.hypot(p[1][0] - p[5][0], p[1][1] - p[5][1])
            v2 = math.hypot(p[2][0] - p[4][0], p[2][1] - p[4][1])
            h = math.hypot(p[0][0] - p[3][0], p[0][1] - p[3][1])
            return (v1 + v2) / (2.0 * h) if h > 1e-4 else 0.0

        return ear((33, 160, 158, 133, 153, 144)), ear((362, 385, 387, 263, 373, 380))

    def set_baseline(self, landmarks: Any) -> bool:
        span = self._eye_span(landmarks)
        if span is None or span <= 1e-4:
            return False
        self.baseline_eye_span = float(span)
        self._baseline_samples = [span]
        return True

    def reset(self) -> None:
        self.last_blink_time = None
        self.blink_times.clear()
        self._eyes_closed = False
        self._near_since = None
        self.last_alert_time = 0.0
        self.baseline_eye_span = None
        self._baseline_samples = []

    def process(self, landmarks: Any, now: Optional[float] = None, tracking_active: bool = True) -> Optional[str]:
        """Returns a user-facing warning or None. Never raises on bad landmarks."""
        if not self.enabled or not tracking_active or landmarks is None:
            self._near_since = None
            self._eyes_closed = False
            return None
        timestamp = time.time() if now is None else float(now)
        try:
            span = self._eye_span(landmarks)
            if span is not None and span > 1e-4:
                if self.baseline_eye_span is None:
                    self._baseline_samples.append(span)
                    if len(self._baseline_samples) >= 45:
                        self.baseline_eye_span = float(sorted(self._baseline_samples)[len(self._baseline_samples) // 2])
                elif span > self.baseline_eye_span * self.near_ratio:
                    if self._near_since is None:
                        self._near_since = timestamp
                    elif timestamp - self._near_since >= self.near_sec:
                        alert = "Demasiado cerca del monitor: Relaja la postura"
                        if timestamp - self.last_alert_time >= self.alert_cooldown_sec:
                            self.last_alert_time = timestamp
                            return alert
                else:
                    self._near_since = None

            left_ear, right_ear = self._ears(landmarks)
            eyes_closed = left_ear < self.blink_ear and right_ear < self.blink_ear
            if eyes_closed and not self._eyes_closed:
                self._eyes_closed = True
            elif not eyes_closed and self._eyes_closed:
                self._eyes_closed = False
                self.last_blink_time = timestamp
                self.blink_times.append(timestamp)

            if self.last_blink_time is None:
                self.last_blink_time = timestamp
            elif timestamp - self.last_blink_time > self.no_blink_sec:
                alert = "Vista fija detectada: Recuerda parpadear"
                if timestamp - self.last_alert_time >= self.alert_cooldown_sec:
                    self.last_alert_time = timestamp
                    return alert
        except Exception:
            return None
        return None

    def blink_rate_per_minute(self, now: Optional[float] = None) -> float:
        timestamp = time.time() if now is None else float(now)
        recent = [t for t in self.blink_times if timestamp - t <= 60.0]
        return float(len(recent))
