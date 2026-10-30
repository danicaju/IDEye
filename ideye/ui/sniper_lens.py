"""Sub-pixel Sniper Zoom Lens state machine."""

from __future__ import annotations

import math
import time
from typing import Optional


class SniperLens:
    """Tracks micro-fixation and exposes the slow-mo cursor multiplier."""

    def __init__(
        self,
        zoom: float = 3.5,
        slowmo_factor: float = 0.28,
        fixation_radius_px: float = 28.0,
        fixation_hold_sec: float = 0.55,
        saccade_breakout_px: float = 70.0,
        auto_fixation: bool = False,
    ) -> None:
        self.zoom = float(zoom)
        self.slowmo_factor = float(slowmo_factor)
        self.fixation_radius_px = float(fixation_radius_px)
        self.fixation_hold_sec = float(fixation_hold_sec)
        self.saccade_breakout_px = float(saccade_breakout_px)
        self.auto_fixation = bool(auto_fixation)
        self.active = False
        self.target: Optional[tuple[float, float]] = None
        self._anchor: Optional[tuple[float, float]] = None
        self._anchor_since: Optional[float] = None
        self._last_active_time = 0.0

    @property
    def movement_multiplier(self) -> float:
        return self.slowmo_factor if self.active else 1.0

    def activate(self, x: float, y: float) -> None:
        self.active = True
        self.target = (float(x), float(y))
        self._anchor = (float(x), float(y))
        self._anchor_since = time.perf_counter()
        self._last_active_time = time.perf_counter()

    def deactivate(self) -> None:
        self.active = False
        self._anchor = None
        self._anchor_since = None

    def toggle(self, x: Optional[float] = None, y: Optional[float] = None) -> bool:
        if self.active:
            self.deactivate()
        else:
            px, py = (x, y) if x is not None and y is not None else (self.target or (0.0, 0.0))
            self.activate(px, py)
        return self.active

    def update_gaze(self, x: float, y: float, now: Optional[float] = None, reading: bool = False) -> bool:
        """Updates micro-fixation; returns True when the lens is active."""
        timestamp = time.time() if now is None else float(now)
        point = (float(x), float(y))
        if reading:
            self._anchor = point
            self._anchor_since = None
            if self.active:
                self.deactivate()
            return False
        if self.active:
            if self.target is not None and math.hypot(point[0] - self.target[0], point[1] - self.target[1]) > self.saccade_breakout_px:
                self.deactivate()
                return False
            self.target = point
            return True
        if self._anchor is None:
            self._anchor = point
            self._anchor_since = timestamp
            return False
        distance = math.hypot(point[0] - self._anchor[0], point[1] - self._anchor[1])
        if distance > self.fixation_radius_px:
            self._anchor = point
            self._anchor_since = timestamp
            return False
        if self._anchor_since is not None and timestamp - self._anchor_since >= self.fixation_hold_sec:
            if self.auto_fixation:
                self.activate(point[0], point[1])
                return True
            return False
        return False

    def on_gesture(self, gesture: str) -> bool:
        """Returns True when the gesture changed lens state."""
        if gesture == "BROW_RAISE":
            if not self.active and self.target is not None:
                self.activate(*self.target)
                return True
        elif gesture in ("MOUTH_CLICK", "LEFT_WINK", "WINK_LEFT"):
            if self.active:
                self.deactivate()
                return True
        return False
