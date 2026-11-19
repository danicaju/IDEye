"""Sensitivity, curves, target screen and monitor profiles."""

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


try:
    import ideye.config as config
except ImportError:
    try:
        import config
    except ImportError:
        config = None

TRACKING_MODE_PURE_IRIS = getattr(config, "TRACKING_MODE_PURE_IRIS", "PURE_IRIS") if config else "PURE_IRIS"
TRACKING_MODE_HYBRID = getattr(config, "TRACKING_MODE_HYBRID", "HYBRID") if config else "HYBRID"
TRACKING_MODE_HEAD_PRIMARY = getattr(config, "TRACKING_MODE_HEAD_PRIMARY", "HEAD_PRIMARY") if config else "HEAD_PRIMARY"
DEFAULT_TRACKING_MODE = getattr(config, "DEFAULT_TRACKING_MODE", TRACKING_MODE_HEAD_PRIMARY) if config else TRACKING_MODE_HEAD_PRIMARY


from ideye.core.logging_config import get_logger

logger = get_logger(__name__)



class GazeTuningMixin:
    """Sensitivity, curves, target screen and monitor profiles."""

    def _extract_head_pos(self, landmarks: Any) -> Tuple[float, float]:
        """Weighted centroid of six rigid nasal/glabellar landmarks.

        Falls back to the legacy nose anchor when the synthetic/test landmarks do
        not populate the rigid anchor set.
        """
        try:
            points = [self._safe_coord(landmarks[idx]) for idx in self.head_anchor_indices]
            populated = sum(1 for p in points if p != (0.5, 0.5))
            if populated < 4:
                return self._safe_coord(landmarks[self.nose_tip_idx])
            weights = self.head_anchor_weights
            if not self.cap_mode and points[3] == (0.5, 0.5):
                weights = self._cap_safe_head_anchor_weights
            total = max(sum(weights), 1e-6)
            x = sum(p[0] * w for p, w in zip(points, weights)) / total
            y = sum(p[1] * w for p, w in zip(points, weights)) / total
            return float(x), float(y)
        except (IndexError, AttributeError, TypeError):
            return 0.5, 0.5

    def set_sensitivity(
        self,
        head_x: Optional[float] = None,
        head_y: Optional[float] = None,
        iris_x: Optional[float] = None,
        iris_y: Optional[float] = None,
    ) -> None:
        """Manually sets gain / sensitivity multipliers."""
        if head_x is not None:
            self.head_sensitivity_x = max(0.5, min(15.0, float(head_x)))
        if head_y is not None:
            self.head_sensitivity_y = max(0.5, min(20.0, float(head_y)))
        if iris_x is not None:
            self.iris_sensitivity_x = max(0.5, min(15.0, float(iris_x)))
        if iris_y is not None:
            self.iris_sensitivity_y = max(0.5, min(25.0, float(iris_y)))

    def adjust_sensitivity(self, multiplier: float) -> None:
        """Scales all sensitivities by a relative multiplier (e.g. 1.1 for +10%)."""
        mult = max(0.5, min(2.0, float(multiplier)))
        self.set_sensitivity(
            head_x=self.head_sensitivity_x * mult,
            head_y=self.head_sensitivity_y * mult,
            iris_x=self.iris_sensitivity_x * mult,
            iris_y=self.iris_sensitivity_y * mult,
        )

    def set_anti_jitter_damping(self, level: float) -> None:
        """
        Adjusts anti-jitter damping level (1.0 to 10.0).
        Higher level = heavier damping at resting (lower min_cutoff, larger deadzone).
        Lower level = lighter damping, more raw response.
        """
        clamped = max(1.0, min(10.0, float(level)))
        t = (clamped - 1.0) / 9.0
        min_cutoff = 1.0 - t * 0.82    # Level 1: 1.0 Hz -> Level 10: 0.18 Hz
        deadzone = 0.010 + t * 0.024  # Level 1: 0.010 -> Level 10: 0.034
        self.one_euro_x.min_cutoff = min_cutoff
        self.one_euro_y.min_cutoff = min_cutoff
        self.fixation_deadzone = deadzone

    def _apply_ergonomic_vertical_curve(self, delta_y: float) -> float:
        """
        Ergonomic non-linear vertical expansion curve with independent vertical multiplier
        and smooth micro-damped centering curve around resting neutral position.
        Compensates for the reduced human vertical ocular/cervical span (~30% of horizontal).
        Applies progressive expansion so gentle head pitch or looking up/down comfortably
        hits top row (Y < 0.20) and bottom row (Y > 0.80), while remaining rock-solid at center.
        """
        if not math.isfinite(delta_y) or abs(delta_y) < 1e-6:
            return 0.0
        sign = 1.0 if delta_y >= 0.0 else -1.0
        u = abs(delta_y)
        cz = 0.040
        if u <= cz:
            expanded = u * (u / cz) ** 2
        else:
            excess = u - cz
            expanded = cz + self.vertical_multiplier * excess * (1.0 + self.vertical_expansion_gain * excess)
        return sign * expanded

    def _apply_horizontal_expansion_curve(self, delta_x: float) -> float:
        """
        Ergonomic non-linear horizontal expansion curve for effortless edge reach.
        Compensates for the limited natural horizontal range of the iris relative to the canthi.
        Dampens micro-movements near center for rock-solid reading, while progressively
        expanding lateral glances so user effortlessly reaches lateral borders (columns 0 and 2)
        purely by moving eyes, without twisting the head.
        """
        if not math.isfinite(delta_x) or abs(delta_x) < 1e-6:
            return 0.0
        sign = 1.0 if delta_x >= 0.0 else -1.0
        u = abs(delta_x)
        cz = 0.050
        if u <= cz:
            expanded = u
        else:
            excess = u - cz
            expanded = cz + self.horizontal_multiplier * excess * (1.0 + self.horizontal_expansion_gain * excess)
        return sign * expanded

    def set_target_screen(self, width: int, height: int) -> None:
        """Re-anchors the normalized mapping to the active monitor bounds."""
        self.target_screen_size = (max(1, int(width)), max(1, int(height)))
        self.target_screen_aspect = self.target_screen_size[0] / float(self.target_screen_size[1])

    def get_target_screen(self) -> Tuple[int, int]:
        return self.target_screen_size

    def _monitor_profile_path(self, monitor_key: str) -> Optional[str]:
        """Returns the per-monitor profile path next to the base profile."""
        if not self._profile_path:
            return None
        base_dir = os.path.dirname(os.path.abspath(self._profile_path))
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(monitor_key))[:140]
        if not safe:
            safe = "unknown_monitor"
        return os.path.join(base_dir, "calibration_profiles", f"{safe}.json")

    def set_active_monitor(
        self,
        monitor_key: str,
        width: int,
        height: int,
        physical_width_mm: float = 0.0,
        physical_height_mm: float = 0.0,
        dpi: float = 1.0,
    ) -> bool:
        """Binds to a physical monitor and loads its calibration when present.

        Returns True when a per-monitor profile was found and applied. When no
        profile exists, the current weights remain as a fallback and
        ``active_monitor_calibrated`` becomes False so a later save does not
        mislabel the fallback as a calibration of this monitor.
        """
        self.set_target_screen(width, height)
        key = str(monitor_key)
        if self.active_monitor_key == key and self.active_monitor_calibrated:
            self.active_monitor_physical_mm = (float(physical_width_mm), float(physical_height_mm))
            self.active_monitor_dpi = float(dpi)
            return True
        self.active_monitor_key = key
        self.active_monitor_physical_mm = (float(physical_width_mm), float(physical_height_mm))
        self.active_monitor_dpi = float(dpi)
        path = self._monitor_profile_path(self.active_monitor_key)
        if path and os.path.isfile(path):
            if self._load_profile_file(path):
                self.active_monitor_calibrated = True
                return True
        self.active_monitor_calibrated = False
        return False

    def clear_monitor_profiles(self, backup: bool = True) -> bool:
        """Removes (or backs up) the per-monitor calibration directory."""
        if not self._profile_path:
            return False
        base_dir = os.path.dirname(os.path.abspath(self._profile_path))
        profiles_dir = os.path.join(base_dir, "calibration_profiles")
        if not os.path.isdir(profiles_dir):
            return False
        try:
            if backup:
                bak_dir = profiles_dir + ".bak"
                if os.path.isdir(bak_dir):
                    shutil.rmtree(bak_dir, ignore_errors=True)
                os.rename(profiles_dir, bak_dir)
            else:
                shutil.rmtree(profiles_dir, ignore_errors=True)
            self.active_monitor_calibrated = False
            return True
        except Exception as exc:
            logger.warning("Could not clear per-monitor profiles: %s", exc)
            return False

    def get_active_monitor_state(self) -> Dict[str, Any]:
        return {
            "key": self.active_monitor_key,
            "calibrated": self.active_monitor_calibrated,
            "size": self.target_screen_size,
            "physical_mm": self.active_monitor_physical_mm,
            "dpi": self.active_monitor_dpi,
        }

    def _write_profile(self, filepath: str, profile: Dict[str, Any]) -> bool:
        try:
            parent = os.path.dirname(os.path.abspath(filepath))
            if parent:
                os.makedirs(parent, exist_ok=True)
            tmp_path = filepath + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(profile, f, indent=2)
            if os.path.exists(filepath):
                os.replace(tmp_path, filepath)
            else:
                os.rename(tmp_path, filepath)
            return True
        except Exception as exc:
            logger.warning(f"[GazeEstimator] Warning: Could not write profile '{filepath}': {exc}")
            return False
