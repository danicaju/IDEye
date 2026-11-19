"""Gesture state enum and result tuple."""

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
