"""Adaptive power states for the camera pipeline (Phase 11)."""

from __future__ import annotations

import math
import time
from typing import Optional


class EcoPowerManager:
    """Three-state framerate governor for CameraTracker.

    ACTIVE keeps the normal camera cadence, PAUSED_ECO samples at 10 FPS
    while the HUD is resting, and AWAY_DEEP_SLEEP drops to 2 FPS after ten
    seconds without a face. A detected face always wakes the pipeline at once.
    """

    ACTIVE = "ACTIVE"
    PAUSED_ECO = "PAUSED_ECO"
    AWAY_DEEP_SLEEP = "AWAY_DEEP_SLEEP"

    ACTIVE_FPS = 30.0
    PAUSED_FPS = 10.0
    AWAY_FPS = 2.0
    AWAY_AFTER_SEC = 10.0

    def __init__(
        self,
        enabled: bool = True,
        away_after_sec: float = AWAY_AFTER_SEC,
        clock=None,
    ) -> None:
        self.enabled = bool(enabled)
        self.away_after_sec = max(0.0, float(away_after_sec))
        self._clock = clock or time.monotonic
        self.current_power_state = self.ACTIVE
        self.paused = False
        self._last_face_seen = float(self._clock())
        self._last_now = self._last_face_seen

    @property
    def fps(self) -> float:
        if self.current_power_state == self.PAUSED_ECO:
            return self.PAUSED_FPS
        if self.current_power_state == self.AWAY_DEEP_SLEEP:
            return self.AWAY_FPS
        return self.ACTIVE_FPS

    @property
    def frame_interval(self) -> float:
        return 1.0 / max(1.0, self.fps)

    @property
    def sleep_seconds(self) -> float:
        return self.frame_interval

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = bool(enabled)
        if not self.enabled:
            self.current_power_state = self.ACTIVE

    def set_paused(self, paused: bool, now: Optional[float] = None) -> str:
        self.paused = bool(paused)
        if not self.paused:
            self._last_face_seen = self._now(now)
        return self.update(detected=False, paused=self.paused, now=now, _paused_only=True)

    def observe_face(self, detected: bool, now: Optional[float] = None) -> str:
        return self.update(detected=detected, now=now)

    def update(
        self,
        detected: bool,
        paused: Optional[bool] = None,
        now: Optional[float] = None,
        _paused_only: bool = False,
    ) -> str:
        timestamp = self._now(now)
        if paused is not None:
            self.paused = bool(paused)
        if not self.enabled:
            self.current_power_state = self.ACTIVE
        elif self.paused:
            self.current_power_state = self.PAUSED_ECO
        elif detected:
            self._last_face_seen = timestamp
            self.current_power_state = self.ACTIVE
        else:
            if timestamp < self._last_face_seen:
                self._last_face_seen = timestamp
            elapsed = max(0.0, timestamp - self._last_face_seen)
            if elapsed >= self.away_after_sec:
                self.current_power_state = self.AWAY_DEEP_SLEEP
            else:
                self.current_power_state = self.ACTIVE
        if _paused_only and not self.paused and self.current_power_state == self.PAUSED_ECO:
            self.current_power_state = self.ACTIVE
        return self.current_power_state

    def reset(self, now: Optional[float] = None) -> None:
        timestamp = self._now(now)
        self.current_power_state = self.ACTIVE
        self.paused = False
        self._last_face_seen = timestamp
        self._last_now = timestamp

    def _now(self, now: Optional[float]) -> float:
        try:
            value = float(self._clock() if now is None else now)
        except (TypeError, ValueError, OverflowError):
            value = float(self._clock())
        if not math.isfinite(value):
            value = float(self._clock())
        return value
