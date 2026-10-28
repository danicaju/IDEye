"""Proportional, inertial gaze scrolling for long-form reading (Phase 11)."""

from __future__ import annotations

import math
from typing import Optional, Tuple


class GazeScroller:
    """Maps vertical gaze to a smooth wheel velocity with a comfortable deadzone.

    The central 44% of the screen is a reading deadzone. Outside it, speed grows
    quadratically (exponent 1.8) toward the top/bottom edge. When the gaze
    returns to the deadzone, velocity decays geometrically instead of stopping
    abruptly.
    """

    DEADZONE_Y: Tuple[float, float] = (0.28, 0.72)
    MAX_SCROLL_RATE: float = 8.0
    DECAY: float = 0.82
    EXPONENT: float = 1.8
    HORIZONTAL_DEADZONE: Tuple[float, float] = (0.20, 0.80)
    MAX_HORIZONTAL_RATE: float = 4.0

    def __init__(
        self,
        max_scroll_rate: float = MAX_SCROLL_RATE,
        decay: float = DECAY,
        deadzone_y: Tuple[float, float] = DEADZONE_Y,
    ) -> None:
        self.max_scroll_rate = max(0.0, float(max_scroll_rate))
        self.decay = min(0.999, max(0.0, float(decay)))
        self.deadzone_y = (
            max(0.0, min(float(deadzone_y[0]), float(deadzone_y[1]))),
            min(1.0, max(float(deadzone_y[0]), float(deadzone_y[1]))),
        )
        self.active: bool = False
        self.velocity: float = 0.0
        self.horizontal_velocity: float = 0.0
        self._accumulator: float = 0.0
        self._horizontal_accumulator: float = 0.0
        self.last_steps: int = 0
        self.last_horizontal_steps: int = 0

    # ------------------------------------------------------------------
    @staticmethod
    def _finite(value: float, default: float = 0.5) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError, OverflowError):
            return default
        if not math.isfinite(number):
            return default
        return max(0.0, min(1.0, number))

    def target_speed(self, norm_y: float) -> float:
        """Returns the ideal wheel speed for the current vertical gaze."""
        y = self._finite(norm_y)
        low, high = self.deadzone_y
        if low <= y <= high:
            return 0.0
        if y > high:
            span = max(1e-6, 1.0 - high)
            intensity = min(1.0, (y - high) / span)
            return float((intensity ** self.EXPONENT) * self.max_scroll_rate)
        span = max(1e-6, low)
        intensity = min(1.0, (low - y) / span)
        return -float((intensity ** self.EXPONENT) * self.max_scroll_rate)

    def target_horizontal_speed(self, norm_x: float) -> float:
        """Returns the ideal horizontal wheel/trackpad speed for gaze X."""
        x = self._finite(norm_x)
        low, high = self.HORIZONTAL_DEADZONE
        if low <= x <= high:
            return 0.0
        if x > high:
            intensity = min(1.0, (x - high) / max(1e-6, 1.0 - high))
            return float((intensity ** self.EXPONENT) * self.MAX_HORIZONTAL_RATE)
        intensity = min(1.0, (low - x) / max(1e-6, low))
        return -float((intensity ** self.EXPONENT) * self.MAX_HORIZONTAL_RATE)

    # ------------------------------------------------------------------
    def activate(self) -> None:
        self.active = True

    def deactivate(self) -> None:
        self.active = False
        self.reset()

    def toggle(self) -> bool:
        self.active = not self.active
        if not self.active:
            self.reset()
        return self.active

    def reset(self) -> None:
        self.velocity = 0.0
        self.horizontal_velocity = 0.0
        self._accumulator = 0.0
        self._horizontal_accumulator = 0.0
        self.last_steps = 0
        self.last_horizontal_steps = 0

    def stop(self) -> None:
        """Safety stop used by gestures, pause and face loss."""
        self.deactivate()

    # ------------------------------------------------------------------
    def update(
        self,
        norm_y: float,
        dt: float = 1.0 / 60.0,
        active: Optional[bool] = None,
    ) -> float:
        """Updates vertical velocity and returns it in wheel units per second."""
        if active is not None:
            self.active = bool(active)
        if not self.active:
            self.reset()
            return 0.0
        try:
            delta = float(dt)
        except (TypeError, ValueError, OverflowError):
            delta = 1.0 / 60.0
        if not math.isfinite(delta) or delta <= 0.0:
            delta = 1.0 / 60.0
        delta = min(0.25, delta)

        target = self.target_speed(norm_y)
        if target == 0.0:
            self.velocity *= self.decay
            if abs(self.velocity) < 1e-4:
                self.velocity = 0.0
        else:
            self.velocity = target

        self._accumulator += self.velocity * delta
        steps = int(self._accumulator)
        if steps:
            self._accumulator -= steps
        self.last_steps = steps
        return float(self.velocity)

    def update_horizontal(
        self,
        norm_x: float,
        dt: float = 1.0 / 60.0,
        active: Optional[bool] = None,
    ) -> float:
        """Updates horizontal velocity; opt-in for pan/trackpad style scrolling."""
        if active is not None:
            self.active = bool(active)
        if not self.active:
            self.horizontal_velocity = 0.0
            self._horizontal_accumulator = 0.0
            self.last_horizontal_steps = 0
            return 0.0
        try:
            delta = float(dt)
        except (TypeError, ValueError, OverflowError):
            delta = 1.0 / 60.0
        if not math.isfinite(delta) or delta <= 0.0:
            delta = 1.0 / 60.0
        delta = min(0.25, delta)

        target = self.target_horizontal_speed(norm_x)
        if target == 0.0:
            self.horizontal_velocity *= self.decay
            if abs(self.horizontal_velocity) < 1e-4:
                self.horizontal_velocity = 0.0
        else:
            self.horizontal_velocity = target
        self._horizontal_accumulator += self.horizontal_velocity * delta
        steps = int(self._horizontal_accumulator)
        if steps:
            self._horizontal_accumulator -= steps
        self.last_horizontal_steps = steps
        return float(self.horizontal_velocity)

    def speed(self) -> float:
        return float(self.velocity)

    def horizontal_speed(self) -> float:
        return float(self.horizontal_velocity)
