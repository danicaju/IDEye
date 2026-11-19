"""Five-point calibration and dual-source mapping."""

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



from ideye.core.gaze_geometry import GazeGeometryMixin


class GazeCalibrationMixin:
    """Five-point calibration and dual-source mapping."""

    def apply_5_point_mapping(self, u: float, v: float) -> Tuple[float, float]:
        """
        Applies bilinear / matrix transform learned from 5-point calibration.
        Maps raw input (u, v) -> screen (x, y).
        Safeguarded against NaN, Inf, and erratic out-of-screen extrapolation.
        """
        with self._lock:
            u = self._finite_unit(u)
            v = self._finite_unit(v)
            if not self.has_5_point_calibration or not self.calib_weights_x or not self.calib_weights_y:
                return u, v
            try:
                a0, a1, a2, a3 = self.calib_weights_x
                b0, b1, b2, b3 = self.calib_weights_y
                mx = a0 + a1 * u + a2 * v + a3 * (u * v)
                my = b0 + b1 * u + b2 * v + b3 * (u * v)
                if not math.isfinite(mx):
                    mx = u
                if not math.isfinite(my):
                    my = v
                # Aspect-ratio correction: calibrating on one screen and handing
                # over to a screen with a different width/height ratio scales the
                # horizontal coordinate around the center (0.5) so the mapped
                # gaze still spans the new display edges.
                if (
                    self.calibration_screen_aspect is not None
                    and self.calibration_screen_aspect > 0.0
                    and self.target_screen_aspect > 0.0
                    and abs(self.calibration_screen_aspect - self.target_screen_aspect) > 1e-4
                ):
                    mx = 0.5 + (mx - 0.5) * (self.calibration_screen_aspect / self.target_screen_aspect)
                # Bounded safety guard: prevent non-linear warping from launching cursor into infinity
                mx = max(-1.0, min(2.0, float(mx)))
                my = max(-1.0, min(2.0, float(my)))
                return float(mx), float(my)
            except Exception:
                return u, v

    @staticmethod
    def _source_geometry(
        points_data: List[Dict[str, Any]], key: str
    ) -> Tuple[Optional[Tuple[float, float, float, float]], Tuple[float, float]]:
        values = []
        for pt in points_data:
            raw = pt.get(key)
            if raw is not None and len(raw) >= 2:
                values.append((float(raw[0]), float(raw[1])))
        if not values:
            return None, (0.5, 0.5)
        xs = [v[0] for v in values]
        ys = [v[1] for v in values]
        center_candidates = [
            pt.get(key) for pt in points_data
            if pt.get("id") == "CENTER" or tuple(pt.get("screen", ())) == (0.5, 0.5)
        ]
        if center_candidates:
            center = (float(center_candidates[0][0]), float(center_candidates[0][1]))
        else:
            center = (float(np.mean(xs)), float(np.mean(ys)))
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        if max_x - min_x < 1e-4:
            min_x, max_x = center[0] - 0.05, center[0] + 0.05
        if max_y - min_y < 1e-4:
            min_y, max_y = center[1] - 0.05, center[1] + 0.05
        return (min_x, max_x, min_y, max_y), center

    @staticmethod
    def _fit_linear_mapping(
        points_data: List[Dict[str, Any]],
        key: str,
        bounds: Tuple[float, float, float, float],
    ) -> Tuple[Tuple[float, float], Tuple[float, float]]:
        min_x, max_x, min_y, max_y = bounds
        span_x = max(max_x - min_x, 1e-4)
        span_y = max(max_y - min_y, 1e-4)
        us, vs, sx, sy = [], [], [], []
        for pt in points_data:
            raw = pt.get(key)
            if raw is None or len(raw) < 2:
                continue
            screen = pt.get("screen", (0.5, 0.5))
            us.append((float(raw[0]) - min_x) / span_x)
            vs.append((float(raw[1]) - min_y) / span_y)
            sx.append(float(screen[0]))
            sy.append(float(screen[1]))
        if len(us) < 3:
            return (0.0, 1.0), (0.0, 1.0)
        try:
            ax = np.linalg.lstsq(
                np.column_stack([np.ones(len(us)), us]), np.array(sx), rcond=None
            )[0]
            ay = np.linalg.lstsq(
                np.column_stack([np.ones(len(vs)), vs]), np.array(sy), rcond=None
            )[0]
            return (
                (float(ax[0]), float(ax[1])),
                (float(ay[0]), float(ay[1])),
            )
        except np.linalg.LinAlgError:
            return (0.0, 1.0), (0.0, 1.0)

    @staticmethod
    def _map_dual_source(
        x: float,
        y: float,
        bounds: Optional[Tuple[float, float, float, float]],
        linear_x: Optional[Tuple[float, float]],
        linear_y: Optional[Tuple[float, float]],
        center: Optional[Tuple[float, float]] = None,
    ) -> Tuple[float, float]:
        if bounds is None:
            return 0.5, 0.5
        x = GazeGeometryMixin._finite_unit(x)
        y = GazeGeometryMixin._finite_unit(y)
        min_x, max_x, min_y, max_y = bounds

        if center is not None:
            # Center-anchored piecewise mapping. A single least-squares line
            # cannot fit left target, center and right target when the raw
            # head/iris center is not exactly halfway between the extremes;
            # it compromises by leaving part of the left edge unreachable.
            cx = GazeGeometryMixin._finite_unit(center[0])
            cy = GazeGeometryMixin._finite_unit(center[1])
            left_span = max(cx - min_x, 1e-4)
            right_span = max(max_x - cx, 1e-4)
            lower_span = max(cy - min_y, 1e-4)
            upper_span = max(max_y - cy, 1e-4)
            u = (
                0.5 * (x - min_x) / left_span
                if x <= cx
                else 0.5 + 0.5 * (x - cx) / right_span
            )
            v = (
                0.5 * (y - min_y) / lower_span
                if y <= cy
                else 0.5 + 0.5 * (y - cy) / upper_span
            )
            u = max(0.0, min(1.0, u))
            v = max(0.0, min(1.0, v))
            # Calibration targets live at 10% and 90% of the screen.
            return (u, v)

        u = (x - min_x) / max(max_x - min_x, 1e-4)
        v = (y - min_y) / max(max_y - min_y, 1e-4)
        u = max(0.0, min(1.0, u))
        v = max(0.0, min(1.0, v))
        ax = linear_x or (0.0, 1.0)
        ay = linear_y or (0.0, 1.0)
        mapped_x = ax[0] + ax[1] * u
        mapped_y = ay[0] + ay[1] * v
        return GazeGeometryMixin._finite_unit(mapped_x), GazeGeometryMixin._finite_unit(mapped_y)

    def calibrate_5_points(self, points_data: List[Dict[str, Any]]) -> bool:
        """
        Calibrates the 2D gaze mapping using a 5-point dataset.
        Each item in points_data must contain:
          - 'screen': (sx, sy) tuple or list of normalized screen target coords.
          - 'raw': (rx, ry) tuple or list of observed raw gaze coords.

        Solves the regularized bilinear regression system:
          x_screen = a0 + a1 * u + a2 * v + a3 * (u * v)
          y_screen = b0 + b1 * u + b2 * v + b3 * (u * v)
        via Ridge / Tikhonov regularization with prior towards identity mapping,
        coefficient clamping, and bounded gains to prevent ill-conditioned blowups.
        """
        if not points_data or len(points_data) < 4:
            return False

        try:
            phi_rows = []
            targets_x = []
            targets_y = []
            raw_xs = []
            raw_ys = []

            for pt in points_data:
                sx, sy = pt["screen"]
                rx, ry = pt["raw"]
                phi_rows.append([1.0, float(rx), float(ry), float(rx * ry)])
                targets_x.append(float(sx))
                targets_y.append(float(sy))
                raw_xs.append(float(rx))
                raw_ys.append(float(ry))

            phi_mat = np.array(phi_rows, dtype=np.float64)
            tx_mat = np.array(targets_x, dtype=np.float64)
            ty_mat = np.array(targets_y, dtype=np.float64)

            # Defensive check for degenerate/identical coordinates
            # Requires variation in both horizontal and vertical axes
            if np.std(phi_mat[:, 1]) < 1e-4 or np.std(phi_mat[:, 2]) < 1e-4:
                return False
            if np.linalg.matrix_rank(phi_mat) < 3:
                return False

            range_x = float(np.ptp(phi_mat[:, 1]))
            range_y = float(np.ptp(phi_mat[:, 2]))
            min_range = min(range_x, range_y)
            if min_range < 0.015:
                # Range too narrow to compute meaningful calibration without extreme noise amplification
                return False

            # Determine raw center anchor (from CENTER point or centroid of points)
            center_raw_candidates = [
                pt["raw"] for pt in points_data
                if pt.get("id") == "CENTER" or pt.get("screen") == (0.5, 0.5)
            ]
            if center_raw_candidates:
                uc, vc = float(center_raw_candidates[0][0]), float(center_raw_candidates[0][1])
            else:
                uc = float(np.mean(raw_xs))
                vc = float(np.mean(raw_ys))

            # Identity prior targets centered at (0.5, 0.5):
            # x_prior(u) = 0.5 + 1.0 * (u - uc) = (0.5 - uc) + 1.0 * u
            # y_prior(v) = 0.5 + 1.0 * (v - vc) = (0.5 - vc) + 1.0 * v
            w0_x = np.array([0.5 - uc, 1.0, 0.0, 0.0], dtype=np.float64)
            w0_y = np.array([0.5 - vc, 0.0, 1.0, 0.0], dtype=np.float64)

            # Adaptive regularization parameter lambda (Tikhonov regularization)
            # When range is healthy (>= 0.15), lambda is small (0.0005) for high fidelity.
            # When range is narrow, lambda scales up quadratically to prevent matrix blowup.
            base_lambda = 0.0005
            if min_range < 0.15:
                adaptive_lambda = base_lambda * ((0.15 / max(min_range, 0.02)) ** 2)
            else:
                adaptive_lambda = base_lambda
            adaptive_lambda = min(adaptive_lambda, 0.5)

            # Tikhonov penalty matrices:
            # For X: parameter vector is [a0, a1 (main u), a2 (cross v), a3 (bilinear uv)]
            # For Y: parameter vector is [b0, b1 (cross u), b2 (main v), b3 (bilinear uv)]
            # Cross terms and bilinear interaction are heavily penalized to decouple axes,
            # preventing horizontal eye movements from skewing vertical screen coordinates.
            reg_weights_x = np.array([0.005, 0.02, 2.0, 5.0], dtype=np.float64) * adaptive_lambda
            reg_weights_y = np.array([0.005, 2.0, 0.02, 5.0], dtype=np.float64) * adaptive_lambda
            Gamma_x = np.diag(reg_weights_x)
            Gamma_y = np.diag(reg_weights_y)

            Ax = phi_mat.T @ phi_mat + Gamma_x
            bx = phi_mat.T @ tx_mat + Gamma_x @ w0_x
            Ay = phi_mat.T @ phi_mat + Gamma_y
            by = phi_mat.T @ ty_mat + Gamma_y @ w0_y

            try:
                weights_x = np.linalg.solve(Ax, bx)
            except np.linalg.LinAlgError:
                weights_x, _, _, _ = np.linalg.lstsq(phi_mat, tx_mat, rcond=None)

            try:
                weights_y = np.linalg.solve(Ay, by)
            except np.linalg.LinAlgError:
                weights_y, _, _, _ = np.linalg.lstsq(phi_mat, ty_mat, rcond=None)

            # Gain bounding and shrinkage towards identity:
            # Prevent excessive speed or inverted directions
            min_gain = 0.4
            max_gain = 3.5

            # Effective gain in X at center v=vc: gx = a1 + vc * a3
            gx = float(weights_x[1] + vc * weights_x[3])
            if gx > max_gain or gx < min_gain:
                target_g = max_gain if gx > max_gain else min_gain
                if abs(gx - 1.0) > 1e-4:
                    beta = float(np.clip((gx - target_g) / (gx - 1.0), 0.0, 1.0))
                    weights_x = (1.0 - beta) * weights_x + beta * w0_x

            # Effective gain in Y at center u=uc: gy = b2 + uc * b3
            gy = float(weights_y[2] + uc * weights_y[3])
            if gy > max_gain or gy < min_gain:
                target_g = max_gain if gy > max_gain else min_gain
                if abs(gy - 1.0) > 1e-4:
                    beta = float(np.clip((gy - target_g) / (gy - 1.0), 0.0, 1.0))
                    weights_y = (1.0 - beta) * weights_y + beta * w0_y

            # Coefficient clamping to prevent extreme polynomial warping
            weights_x[0] = np.clip(weights_x[0], -4.0, 4.0)
            weights_x[1] = np.clip(weights_x[1], 0.2, 5.0)
            weights_x[2] = np.clip(weights_x[2], -1.5, 1.5)
            weights_x[3] = np.clip(weights_x[3], -2.5, 2.5)

            weights_y[0] = np.clip(weights_y[0], -4.0, 4.0)
            weights_y[1] = np.clip(weights_y[1], -1.5, 1.5)
            weights_y[2] = np.clip(weights_y[2], 0.2, 5.0)
            weights_y[3] = np.clip(weights_y[3], -2.5, 2.5)

            # Defensive sanity check for finite values
            if (
                any(math.isnan(float(w)) or math.isinf(float(w)) for w in weights_x)
                or any(math.isnan(float(w)) or math.isinf(float(w)) for w in weights_y)
            ):
                return False

            # Calculate RMSE
            pred_x = phi_mat @ weights_x
            pred_y = phi_mat @ weights_y
            rmse = float(np.sqrt(np.mean((pred_x - tx_mat) ** 2 + (pred_y - ty_mat) ** 2)))

            head_bounds, head_center = self._source_geometry(points_data, "raw_head")
            iris_bounds, iris_center = self._source_geometry(points_data, "raw_iris")
            head_linear_x = head_linear_y = None
            iris_linear_x = iris_linear_y = None
            if head_bounds is not None:
                head_linear_x, head_linear_y = self._fit_linear_mapping(
                    points_data, "raw_head", head_bounds
                )
            if iris_bounds is not None:
                iris_linear_x, iris_linear_y = self._fit_linear_mapping(
                    points_data, "raw_iris", iris_bounds
                )

            with self._lock:
                self.calib_weights_x = weights_x.tolist()
                self.calib_weights_y = weights_y.tolist()
                self.has_5_point_calibration = True
                self.is_calibrated = True
                self.calibration_rmse = rmse
                self.calibration_points_data = points_data
                self.calibration_screen_aspect = self.target_screen_aspect
                self.active_monitor_calibrated = True
                self.head_bounds = head_bounds
                self.iris_bounds = iris_bounds
                self.head_center = head_center
                self.iris_center = iris_center
                self.calib_head_linear_x = head_linear_x
                self.calib_head_linear_y = head_linear_y
                self.calib_iris_linear_x = iris_linear_x
                self.calib_iris_linear_y = iris_linear_y
                self.has_dual_calibration = bool(head_bounds is not None and iris_bounds is not None)
            return True
        except Exception:
            return False
