"""One Euro adaptive low-pass filter."""

from typing import Any, Optional, Tuple, Dict, List, Union
from collections import deque
import math
import os
import json
import re
import shutil
import time
import threading
import numpy as np


class OneEuroFilter:
    """
    One Euro Filter (1€ Filter) with adaptive cutoff frequency:
    - High smoothing / low cutoff at low velocity (eliminates resting tremor and webcam jitter).
    - Low smoothing / high cutoff at high velocity (eliminates lag during saccades).
    Reference: Casiez, Roussel, Vogel (CHI 2012) - 1€ Filter: A Simple Speed-based Low-pass Filter.
    """
    def __init__(
        self,
        t0: float = 0.0,
        x0: float = 0.5,
        min_cutoff: float = 0.55,
        beta: float = 0.28,
        d_cutoff: float = 1.0,
    ):
        self.min_cutoff = float(min_cutoff)
        self.beta = float(beta)
        self.d_cutoff = float(d_cutoff)
        try:
            x0 = float(x0)
        except (TypeError, ValueError):
            x0 = 0.5
        try:
            t0 = float(t0)
        except (TypeError, ValueError):
            t0 = 0.0
        self.x_prev = x0 if math.isfinite(x0) else 0.5
        self.dx_prev = 0.0
        self.t_prev = t0 if math.isfinite(t0) else 0.0

    @staticmethod
    def smoothing_factor(dt: float, cutoff: float) -> float:
        try:
            dt = float(dt)
            cutoff = float(cutoff)
        except (TypeError, ValueError):
            return 0.0
        if not (math.isfinite(dt) and math.isfinite(cutoff)) or dt <= 0.0 or cutoff <= 0.0:
            return 0.0
        r = 2.0 * math.pi * cutoff * dt
        if not math.isfinite(r):
            return 0.0
        return r / (r + 1.0)

    def filter(self, t: float, x: float) -> float:
        try:
            t = float(t)
        except (TypeError, ValueError):
            t = self.t_prev + (1.0 / 30.0)
        try:
            x = float(x)
        except (TypeError, ValueError):
            x = self.x_prev
        if not math.isfinite(t):
            t = self.t_prev + (1.0 / 30.0)
        if not math.isfinite(x):
            return self.x_prev if math.isfinite(self.x_prev) else 0.5
        if self.t_prev <= 0.0:
            self.t_prev = t
            self.x_prev = x
            self.dx_prev = 0.0
            return x

        dt = t - self.t_prev
        # If dt is less than realistic frame interval or excessive (pause/gap), fallback to nominal 1/30s
        if dt < 0.001 or dt > 0.5:
            dt = 1.0 / 30.0
        self.t_prev = float(t)

        # 1. Estimate filtered derivative (velocity)
        previous = self.x_prev if math.isfinite(self.x_prev) else 0.5
        dx = (float(x) - previous) / dt
        edx = self.smoothing_factor(dt, self.d_cutoff)
        dx_hat = edx * dx + (1.0 - edx) * self.dx_prev

        # 2. Compute dynamic cutoff frequency
        cutoff = self.min_cutoff + self.beta * abs(dx_hat)
        a = self.smoothing_factor(dt, cutoff)

        # 3. Filter position
        x_hat = a * float(x) + (1.0 - a) * previous
        if not math.isfinite(dx_hat):
            dx_hat = 0.0
        if not math.isfinite(x_hat):
            x_hat = previous if math.isfinite(previous) else 0.5

        self.x_prev = float(x_hat)
        self.dx_prev = float(dx_hat)
        return float(x_hat)

    def reset(self, t0: float = 0.0, x0: float = 0.5) -> None:
        try:
            x0 = float(x0)
        except (TypeError, ValueError):
            x0 = 0.5
        try:
            t0 = float(t0)
        except (TypeError, ValueError):
            t0 = 0.0
        self.x_prev = x0 if math.isfinite(x0) else 0.5
        self.dx_prev = 0.0
        self.t_prev = t0 if math.isfinite(t0) else 0.0
