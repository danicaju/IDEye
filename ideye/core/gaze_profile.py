"""Calibration profile persistence."""

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



class GazeProfileMixin:
    """Calibration profile persistence."""

    def save_calibration_profile(self, filepath: str = "calibration_profile.json") -> bool:
        """Saves the base profile and a per-monitor copy when calibrated."""
        self._profile_path = filepath
        with self._lock:
            profile = {
                "version": 2,
                "type": "5_point_bilinear",
                "timestamp": time.time(),
                "has_5_point_calibration": self.has_5_point_calibration,
                "weights_x": self.calib_weights_x,
                "weights_y": self.calib_weights_y,
                "rmse": self.calibration_rmse,
                "neutral_head": [self.neutral_head_x, self.neutral_head_y],
                "neutral_iris": [self.neutral_iris_x, self.neutral_iris_y],
                "distance_scale": self.distance_scale,
                "head_sensitivities": [self.head_sensitivity_x, self.head_sensitivity_y],
                "iris_sensitivities": [self.iris_sensitivity_x, self.iris_sensitivity_y],
                "tracking_mode": self.tracking_mode,
                "screen_aspect": self.calibration_screen_aspect,
                "screen_size": self.target_screen_size,
                "head_bounds": list(self.head_bounds) if self.head_bounds else None,
                "iris_bounds": list(self.iris_bounds) if self.iris_bounds else None,
                "head_center": list(self.head_center),
                "iris_center": list(self.iris_center),
                "calib_head_linear_x": list(self.calib_head_linear_x) if self.calib_head_linear_x else None,
                "calib_head_linear_y": list(self.calib_head_linear_y) if self.calib_head_linear_y else None,
                "calib_iris_linear_x": list(self.calib_iris_linear_x) if self.calib_iris_linear_x else None,
                "calib_iris_linear_y": list(self.calib_iris_linear_y) if self.calib_iris_linear_y else None,
                "has_dual_calibration": self.has_dual_calibration,
                "monitor_key": self.active_monitor_key,
                "monitor_physical_mm": list(self.active_monitor_physical_mm),
                "monitor_dpi": self.active_monitor_dpi,
                "points": self.calibration_points_data or [],
            }
            monitor_key = self.active_monitor_key
            monitor_calibrated = self.active_monitor_calibrated

        ok = self._write_profile(filepath, profile)
        if ok and monitor_key and monitor_calibrated:
            monitor_path = self._monitor_profile_path(monitor_key)
            if monitor_path:
                self._write_profile(monitor_path, profile)
        return ok

    def load_calibration_profile(self, filepath: str = "calibration_profile.json") -> bool:
        """Loads the base profile and remembers its path for per-monitor files."""
        ok = self._load_profile_file(filepath)
        if ok:
            self._profile_path = filepath
            self.active_monitor_calibrated = False
        return ok

    def _load_profile_file(self, filepath: str = "calibration_profile.json") -> bool:
        """
        Loads calibration profile from JSON, restoring weights and anchors.
        Returns True on success, False if file is missing, corrupt, empty, or degenerate.
        Recovers safely by resetting to default baselines and logging an informative warning.
        """
        if not os.path.exists(filepath):
            return False
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read().strip()

            if not content:
                logger.warning(f"[GazeEstimator] Warning: Calibration file '{filepath}' is empty. Restoring safe defaults.")
                self.reset()
                return False

            profile = json.loads(content)

            if not isinstance(profile, dict):
                logger.warning(f"[GazeEstimator] Warning: Calibration file '{filepath}' is not a valid JSON object. Restoring safe defaults.")
                self.reset()
                return False

            with self._lock:
                weights_x = profile.get("weights_x")
                weights_y = profile.get("weights_y")
                points = profile.get("points")

                # Check for degenerate points where min == max (which causes ZeroDivisionError during interpolation/fitting)
                if points and isinstance(points, list) and len(points) >= 2:
                    raw_pts = [p.get("raw") for p in points if isinstance(p, dict) and "raw" in p]
                    screen_pts = [p.get("screen") for p in points if isinstance(p, dict) and "screen" in p]

                    if raw_pts:
                        raw_xs = [r[0] for r in raw_pts if isinstance(r, (list, tuple)) and len(r) >= 2]
                        raw_ys = [r[1] for r in raw_pts if isinstance(r, (list, tuple)) and len(r) >= 2]
                        if raw_xs and (min(raw_xs) == max(raw_xs)):
                            logger.warning(f"[GazeEstimator] Warning: Calibration points degenerate (raw min_x == max_x). Restoring safe defaults.")
                            self.reset()
                            return False
                        if raw_ys and (min(raw_ys) == max(raw_ys)):
                            logger.warning(f"[GazeEstimator] Warning: Calibration points degenerate (raw min_y == max_y). Restoring safe defaults.")
                            self.reset()
                            return False

                    if screen_pts:
                        screen_xs = [s[0] for s in screen_pts if isinstance(s, (list, tuple)) and len(s) >= 2]
                        screen_ys = [s[1] for s in screen_pts if isinstance(s, (list, tuple)) and len(s) >= 2]
                        if screen_xs and (min(screen_xs) == max(screen_xs)):
                            logger.warning(f"[GazeEstimator] Warning: Calibration points degenerate (screen min_x == max_x). Restoring safe defaults.")
                            self.reset()
                            return False
                        if screen_ys and (min(screen_ys) == max(screen_ys)):
                            logger.warning(f"[GazeEstimator] Warning: Calibration points degenerate (screen min_y == max_y). Restoring safe defaults.")
                            self.reset()
                            return False

                if weights_x is not None or weights_y is not None:
                    if (
                        not weights_x
                        or not weights_y
                        or len(weights_x) != 4
                        or len(weights_y) != 4
                        or any(math.isnan(float(w)) or math.isinf(float(w)) for w in weights_x + weights_y)
                    ):
                        logger.warning(f"[GazeEstimator] Warning: Calibration weights corrupt or invalid. Restoring safe defaults.")
                        self.reset()
                        return False

                    max_weight_mag = max(abs(float(w)) for w in weights_x + weights_y)
                    if max_weight_mag > 10.0:
                        logger.warning(f"[GazeEstimator] Warning: Stored calibration weights excessive (max={max_weight_mag:.1f}). Attempting robust re-fit from points.")
                        refit_ok = False
                        if points and isinstance(points, list) and len(points) >= 4:
                            if self.calibrate_5_points(points):
                                logger.info("[GazeEstimator] Successfully re-fitted robust regularized calibration model from profile points.")
                                refit_ok = True
                        if not refit_ok:
                            logger.warning(f"[GazeEstimator] Warning: Could not re-fit safely. Restoring safe defaults.")
                            self.reset()
                            return False
                    else:
                        self.calib_weights_x = [float(w) for w in weights_x]
                        self.calib_weights_y = [float(w) for w in weights_y]
                        self.has_5_point_calibration = bool(profile.get("has_5_point_calibration", True))
                        self.is_calibrated = True

                if "neutral_head" in profile and len(profile["neutral_head"]) == 2:
                    self.neutral_head_x = float(profile["neutral_head"][0])
                    self.neutral_head_y = float(profile["neutral_head"][1])

                if "neutral_iris" in profile and len(profile["neutral_iris"]) == 2:
                    self.neutral_iris_x = float(profile["neutral_iris"][0])
                    self.neutral_iris_y = float(profile["neutral_iris"][1])

                if "distance_scale" in profile:
                    self.distance_scale = float(profile["distance_scale"])

                if "rmse" in profile:
                    self.calibration_rmse = float(profile["rmse"])

                if "tracking_mode" in profile:
                    self.set_tracking_mode(profile["tracking_mode"])

                if "points" in profile:
                    self.calibration_points_data = profile["points"]

                if "screen_aspect" in profile:
                    self.calibration_screen_aspect = (
                        float(profile["screen_aspect"]) if profile["screen_aspect"] is not None else None
                    )
                if profile.get("head_bounds"):
                    self.head_bounds = tuple(float(v) for v in profile["head_bounds"])
                if profile.get("iris_bounds"):
                    self.iris_bounds = tuple(float(v) for v in profile["iris_bounds"])
                if profile.get("head_center"):
                    self.head_center = tuple(float(v) for v in profile["head_center"])
                if profile.get("iris_center"):
                    self.iris_center = tuple(float(v) for v in profile["iris_center"])
                for attr in ("calib_head_linear_x", "calib_head_linear_y", "calib_iris_linear_x", "calib_iris_linear_y"):
                    value = profile.get(attr)
                    if value:
                        setattr(self, attr, tuple(float(v) for v in value))
                self.has_dual_calibration = bool(profile.get("has_dual_calibration", False))

            return True
        except Exception as e:
            logger.warning(f"[GazeEstimator] Warning: Failed to load calibration profile '{filepath}': {e}. Restoring safe defaults.")
            self.reset()
            return False
