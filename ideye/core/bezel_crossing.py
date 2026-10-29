"""IDEye - configurable bezel-crossing state machine.

The detector is deliberately free of Qt and screen APIs so it can be tested
deterministically with synthetic clocks.
"""

from __future__ import annotations

import math
import time
from typing import Optional

try:
    import ideye.config as config
except ImportError:  # pragma: no cover
    import config  # type: ignore


class BezelCrossingDetector:
    """Turns sustained head yaw into a left/right handover request."""

    def __init__(
        self,
        yaw_threshold_deg: Optional[float] = None,
        hold_sec: Optional[float] = None,
        cooldown_sec: Optional[float] = None,
        enabled: Optional[bool] = None,
    ) -> None:
        self.yaw_threshold_deg = abs(
            float(
                yaw_threshold_deg
                if yaw_threshold_deg is not None
                else getattr(config, "BEZEL_YAW_THRESHOLD_DEG", 21.0)
            )
        )
        self.hold_sec = max(
            0.0,
            float(
                hold_sec
                if hold_sec is not None
                else getattr(config, "BEZEL_HOLD_SEC", 0.40)
            ),
        )
        self.cooldown_sec = max(
            0.0,
            float(
                cooldown_sec
                if cooldown_sec is not None
                else getattr(config, "BEZEL_COOLDOWN_SEC", 1.0)
            ),
        )
        self.enabled = (
            bool(enabled)
            if enabled is not None
            else bool(getattr(config, "BEZEL_AUTO_HANDOVER_ENABLED", True))
        )
        self._yaw_since: Optional[float] = None
        self._last_trigger = -float("inf")

    def reset(self) -> None:
        self._yaw_since = None

    def note_handover(self, timestamp: Optional[float] = None) -> None:
        """Applies the cooldown after a manual or automatic handover."""
        self._last_trigger = timestamp if timestamp is not None else time.time()
        self._yaw_since = None

    def update(
        self,
        yaw_degrees: float,
        can_move_left: bool,
        can_move_right: bool,
        timestamp: Optional[float] = None,
    ) -> int:
        """Returns -1 for left, +1 for right, or 0 when no handover fires."""
        if not self.enabled:
            self._yaw_since = None
            return 0
        try:
            yaw = float(yaw_degrees)
        except (TypeError, ValueError):
            yaw = 0.0
        if not math.isfinite(yaw) or abs(yaw) <= self.yaw_threshold_deg:
            self._yaw_since = None
            return 0

        direction = 1 if yaw > 0 else -1
        if (direction > 0 and not can_move_right) or (direction < 0 and not can_move_left):
            self._yaw_since = None
            return 0

        now = timestamp if timestamp is not None else time.time()
        if self._yaw_since is None:
            self._yaw_since = now
            return 0
        if now - self._yaw_since < self.hold_sec:
            return 0
        if now - self._last_trigger < self.cooldown_sec:
            return 0

        self._last_trigger = now
        self._yaw_since = None
        return direction
