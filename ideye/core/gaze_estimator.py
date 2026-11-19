"""
Hybrid Gaze Estimator Module for IDEye (Phase 1)
Combines relative iris offset with head pose (nose tip anchor),
applies neutral center calibration, and smoothes with an Exponential Moving Average (EMA).
"""

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


from ideye.core.gaze_filter import OneEuroFilter  # noqa: F401
from ideye.core.gaze_geometry import GazeGeometryMixin
from ideye.core.gaze_tuning import GazeTuningMixin
from ideye.core.gaze_mapping import GazeMappingMixin
from ideye.core.gaze_estimate import GazeEstimateMixin
from ideye.core.gaze_calibration import GazeCalibrationMixin
from ideye.core.gaze_profile import GazeProfileMixin
class GazeEstimator(GazeGeometryMixin, GazeTuningMixin, GazeMappingMixin, GazeEstimateMixin, GazeCalibrationMixin, GazeProfileMixin):
    """
    Estimates normalized screen gaze coordinates (X, Y) in [0.0, 1.0] using a
    hybrid fusion of head movement (nose tip) and iris gaze direction.
    
    Guarantees:
    - ZeroDivisionError prevention with defensive epsilon bounds.
    - Face loss safety: maintains last valid position without crashing.
    - One-key center calibration (sets neutral anchor point).
    - Jitter removal via One Euro Filter (1€ Filter) and adaptive fixation deadzone.
    - Ergonomic non-linear vertical expansion curve for full vertical screen reach.
    """

    def __init__(
        self,
        head_weight: float = 0.60,
        iris_weight: float = 0.40,
        head_sensitivity_x: float = 2.6,
        head_sensitivity_y: float = 3.0,
        iris_sensitivity_x: float = 3.2,
        iris_sensitivity_y: float = 8.5,
        ema_alpha: float = 0.22,
        # Landmark indices
        nose_tip_idx: int = 1,
        iris_left_center_idx: int = 468,
        iris_right_center_idx: int = 473,
        left_eye_inner_idx: int = 133,
        left_eye_outer_idx: int = 33,
        left_eye_top_idx: int = 159,
        left_eye_bottom_idx: int = 145,
        right_eye_inner_idx: int = 362,
        right_eye_outer_idx: int = 263,
        right_eye_top_idx: int = 386,
        right_eye_bottom_idx: int = 374,
        tracking_mode: Optional[str] = None,
        mirror: bool = True,
    ):
        # Weights (normalized so sum == 1.0)
        total_w = max(head_weight + iris_weight, 1e-6)
        self.head_weight = head_weight / total_w
        self.iris_weight = iris_weight / total_w

        # Tracking Mode (PURE_IRIS, HYBRID, HEAD_PRIMARY)
        if tracking_mode is not None:
            self.tracking_mode = str(tracking_mode).upper()
        else:
            self.tracking_mode = DEFAULT_TRACKING_MODE

        # Base sensitivity multipliers
        self.base_head_sensitivity_x = float(head_sensitivity_x)
        self.base_head_sensitivity_y = float(head_sensitivity_y)
        self.base_iris_sensitivity_x = float(iris_sensitivity_x)
        self.base_iris_sensitivity_y = float(iris_sensitivity_y)

        # Active sensitivities (calibrated/adapted dynamically)
        self.head_sensitivity_x = self.base_head_sensitivity_x
        self.head_sensitivity_y = self.base_head_sensitivity_y
        self.iris_sensitivity_x = self.base_iris_sensitivity_x
        self.iris_sensitivity_y = self.base_iris_sensitivity_y
        self.distance_scale: float = 1.0
        self.target_screen_size: Tuple[int, int] = (1920, 1080)
        self.target_screen_aspect: float = 1920.0 / 1080.0
        self.last_head_yaw: float = 0.0
        self.head_yaw_sign: float = 1.0 if mirror else -1.0
        self._profile_path: Optional[str] = None
        self.active_monitor_key: Optional[str] = None
        self.active_monitor_calibrated: bool = False
        self.active_monitor_physical_mm: Tuple[float, float] = (0.0, 0.0)
        self.active_monitor_dpi: float = 1.0

        self.ema_alpha = max(0.01, min(1.0, float(ema_alpha)))

        # Ergonomic reach curves & expansion gains (softened for natural pitch control)
        self.vertical_multiplier: float = float(getattr(config, "VERTICAL_MULTIPLIER", 2.35))
        self.vertical_expansion_gain: float = float(getattr(config, "VERTICAL_EXPANSION_GAIN", 1.6))
        self.horizontal_multiplier: float = float(getattr(config, "HORIZONTAL_MULTIPLIER", 1.45))
        self.horizontal_expansion_gain: float = float(getattr(config, "HORIZONTAL_EXPANSION_GAIN", 1.75))
        self.vor_compensation_factor: float = float(getattr(config, "VOR_COMPENSATION_FACTOR", 0.40))

        # One Euro Filter (1€ Filter) for adaptive anti-jitter & zero-lag saccades
        oe_min_cutoff = float(getattr(config, "ONE_EURO_MIN_CUTOFF", 0.55))
        oe_beta = float(getattr(config, "ONE_EURO_BETA", 0.28))
        oe_d_cutoff = float(getattr(config, "ONE_EURO_D_CUTOFF", 1.0))
        self.one_euro_x = OneEuroFilter(min_cutoff=oe_min_cutoff, beta=oe_beta, d_cutoff=oe_d_cutoff)
        self.one_euro_y = OneEuroFilter(min_cutoff=oe_min_cutoff, beta=oe_beta, d_cutoff=oe_d_cutoff)
        self.use_one_euro: bool = True

        # Adaptive Fixation Deadzone (I-VT velocity/distance filtering with sliding leash)
        self.fixation_deadzone: float = float(getattr(config, "FIXATION_DEADZONE", 0.022))
        self.fixation_anchor_x: float = 0.5
        self.fixation_anchor_y: float = 0.5
        self.is_fixated: bool = False
        self.stability_score: float = 1.0

        # Phase 7.6: rigid 6-point cranial head anchor.
        self.head_anchor_indices: Tuple[int, ...] = (1, 4, 6, 168, 195, 197)
        self._default_head_anchor_weights: Tuple[float, ...] = (0.10, 0.10, 0.20, 0.20, 0.20, 0.20)
        self._cap_safe_head_anchor_weights: Tuple[float, ...] = getattr(
            config, "CAP_SAFE_ANCHOR_WEIGHTS", (0.35, 0.35, 0.05, 0.00, 0.15, 0.10)
        ) if config else (0.35, 0.35, 0.05, 0.00, 0.15, 0.10)
        self.cap_mode: bool = bool(getattr(config, "CAP_MODE_ENABLED", False)) if config else False
        self.head_anchor_weights: Tuple[float, ...] = (
            self._cap_safe_head_anchor_weights if self.cap_mode else self._default_head_anchor_weights
        )

        # Phase 7.6: static hysteresis pinning (Schmitt trigger).
        self.static_lock_radius: float = float(getattr(config, "STATIC_LOCK_RADIUS", 0.0035))
        self.static_breakout_radius: float = float(getattr(config, "STATIC_BREAKOUT_RADIUS", 0.0085))
        self.static_lock_frames: int = int(getattr(config, "STATIC_LOCK_FRAMES", 3))
        self._pinned_pos: Optional[Tuple[float, float]] = None
        self._is_pinned: bool = True
        self._static_quiet_frames: int = 0
        self._static_last_filtered: Optional[Tuple[float, float]] = None
        self._static_target: Optional[Tuple[float, float]] = None
        self._pin_release_ramp: float = 1.0

        # Phase 7.6: PURE_IRIS temporal median + orbital anchors.
        self.iris_median_window: int = int(getattr(config, "IRIS_MEDIAN_WINDOW", 5))
        self._iris_history: deque = deque(maxlen=max(1, self.iris_median_window))
        self._last_iris_roll: float = 0.0

        # Phase 7.6: saccade-gated dynamic HYBRID fusion.
        self.hybrid_iris_weight_rest: float = float(getattr(config, "HYBRID_IRIS_WEIGHT_REST", 0.08))
        self.hybrid_iris_weight_saccade: float = float(getattr(config, "HYBRID_IRIS_WEIGHT_SACCADE", 0.55))
        self.iris_saccade_threshold: float = float(getattr(config, "IRIS_SACCADE_THRESHOLD", 0.012))
        self._dynamic_fusion_active: bool = False
        self._effective_iris_weight: float = self.iris_weight
        self._iris_velocity: float = 0.0
        self._last_filtered_iris: Optional[Tuple[float, float]] = None

        # Blink suppression parameters (scale-invariant EAR + absolute height fallback)
        self.ear_blink_threshold: float = float(getattr(config, "EAR_BLINK_THRESHOLD", 0.14))
        self.blink_threshold: float = float(getattr(config, "MIN_EYE_HEIGHT_RATIO", 0.008))
        self.is_blinking: bool = False
        self.last_valid_iris_x: float = 0.5
        self.last_valid_iris_y: float = 0.5

        # Landmark configuration
        self.nose_tip_idx = nose_tip_idx
        self.iris_left_center_idx = iris_left_center_idx
        self.iris_right_center_idx = iris_right_center_idx
        self.left_eye_inner_idx = left_eye_inner_idx
        self.left_eye_outer_idx = left_eye_outer_idx
        self.left_eye_top_idx = left_eye_top_idx
        self.left_eye_bottom_idx = left_eye_bottom_idx
        self.right_eye_inner_idx = right_eye_inner_idx
        self.right_eye_outer_idx = right_eye_outer_idx
        self.right_eye_top_idx = right_eye_top_idx
        self.right_eye_bottom_idx = right_eye_bottom_idx

        # Neutral calibration baseline (defaults to center 0.5, 0.5)
        self.neutral_head_x: float = 0.5
        self.neutral_head_y: float = 0.5
        self.neutral_iris_x: float = 0.5
        self.neutral_iris_y: float = 0.5
        self.is_calibrated: bool = False

        # Raw state
        self.last_raw_head_x: float = 0.5
        self.last_raw_head_y: float = 0.5
        self.last_raw_iris_x: float = 0.5
        self.last_raw_iris_y: float = 0.5

        # Smoothed state
        self.smoothed_x: float = 0.5
        self.smoothed_y: float = 0.5
        self._has_first_sample: bool = False

        # Phase 2: 5-Point Calibration & Matrix / Bilinear Model State
        self.has_5_point_calibration: bool = False
        self.calib_weights_x: Optional[List[float]] = None
        self.calib_weights_y: Optional[List[float]] = None
        self.calibration_points_data: Optional[List[Dict[str, Any]]] = None
        self.calibration_rmse: float = 0.0
        self.calibration_screen_aspect: Optional[float] = None
        # Phase 8.5: simultaneous head/iris references captured during the
        # 5-point calibration so all tracking modes share the same geometry.
        self.head_bounds: Optional[Tuple[float, float, float, float]] = None
        self.iris_bounds: Optional[Tuple[float, float, float, float]] = None
        self.head_center: Tuple[float, float] = (0.5, 0.5)
        self.iris_center: Tuple[float, float] = (0.5, 0.5)
        self.calib_head_linear_x: Optional[Tuple[float, float]] = None
        self.calib_head_linear_y: Optional[Tuple[float, float]] = None
        self.calib_iris_linear_x: Optional[Tuple[float, float]] = None
        self.calib_iris_linear_y: Optional[Tuple[float, float]] = None
        self.has_dual_calibration: bool = False
        # 1-Point Micro-Recalibration ("Snap to Caret" / Offset Adjustment)
        self.micro_offset_x: float = 0.0
        self.micro_offset_y: float = 0.0
        self._lock = threading.RLock()

    def reset(self) -> None:
        """Resets filter and calibration baselines to default."""
        with self._lock:
            self.neutral_head_x = 0.5
            self.neutral_head_y = 0.5
            self.neutral_iris_x = 0.5
            self.neutral_iris_y = 0.5
            self.is_calibrated = False
            self.distance_scale = 1.0
            self.head_sensitivity_x = self.base_head_sensitivity_x
            self.head_sensitivity_y = self.base_head_sensitivity_y
            self.iris_sensitivity_x = self.base_iris_sensitivity_x
            self.iris_sensitivity_y = self.base_iris_sensitivity_y
            self.last_valid_iris_x = 0.5
            self.last_valid_iris_y = 0.5
            self.is_blinking = False
            self.smoothed_x = 0.5
            self.smoothed_y = 0.5
            self.fixation_anchor_x = 0.5
            self.fixation_anchor_y = 0.5
            self.is_fixated = False
            self.stability_score = 1.0
            self.one_euro_x.reset(0.0, 0.5)
            self.one_euro_y.reset(0.0, 0.5)
            self._has_first_sample = False
            self.has_5_point_calibration = False
            self.calib_weights_x = None
            self.calib_weights_y = None
            self.calibration_points_data = None
            self.calibration_rmse = 0.0
            self.calibration_screen_aspect = None
            self.head_bounds = None
            self.iris_bounds = None
            self.head_center = (0.5, 0.5)
            self.iris_center = (0.5, 0.5)
            self.calib_head_linear_x = None
            self.calib_head_linear_y = None
            self.calib_iris_linear_x = None
            self.calib_iris_linear_y = None
            self.has_dual_calibration = False
            self.last_head_yaw = 0.0
            self.active_monitor_calibrated = False
            self.micro_offset_x = 0.0
            self.micro_offset_y = 0.0

    def micro_recalibrate(
        self,
        target_x: float = 0.5,
        target_y: float = 0.5,
    ) -> Tuple[float, float]:
        """
        Micro-recalibration of 1 point ('Snap to Caret' / Snap to Center):
        Quickly re-centers gaze to the active editor caret or resting center without
        discarding or repeating the 5-point regularized polynomial mapping.
        """
        with self._lock:
            target_x = float(np.clip(target_x, 0.0, 1.0))
            target_y = float(np.clip(target_y, 0.0, 1.0))
            # Current unshifted estimated gaze before micro offset:
            current_x = self.smoothed_x - self.micro_offset_x
            current_y = self.smoothed_y - self.micro_offset_y
            self.micro_offset_x = float(np.clip(target_x - current_x, -0.40, 0.40))
            self.micro_offset_y = float(np.clip(target_y - current_y, -0.40, 0.40))
            self.smoothed_x = target_x
            self.smoothed_y = target_y
            self.fixation_anchor_x = target_x
            self.fixation_anchor_y = target_y
            now = time.perf_counter()
            self.one_euro_x.reset(now, target_x)
            self.one_euro_y.reset(now, target_y)
            return self.micro_offset_x, self.micro_offset_y

    def reset_micro_recalibration(self) -> None:
        """Resets the 1-point micro offset back to zero."""
        with self._lock:
            self.micro_offset_x = 0.0
            self.micro_offset_y = 0.0

    @staticmethod
    def calculate_posture_distance_cm(eye_span: float, nominal_interocular: float = 0.28) -> float:
        """Estimates head-to-screen distance in cm based on outer canthi landmark span."""
        try:
            span = float(eye_span)
        except (TypeError, ValueError):
            return 60.0
        if not np.isfinite(span) or span <= 1e-4:
            return 60.0
        dist_cm = (float(nominal_interocular) / span) * 60.0
        return float(np.clip(dist_cm, 20.0, 150.0))
