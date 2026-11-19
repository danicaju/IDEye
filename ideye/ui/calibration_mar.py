"""Mouth-click (MAR) calibration step."""

from typing import Optional, List, Dict, Any, Tuple
import json
import os
import sys
import time
import math
import numpy as np

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, pyqtSlot, QRectF, QPointF
from PyQt6.QtGui import QPainter, QColor, QFont, QPen, QBrush, QKeyEvent
from PyQt6.QtWidgets import QWidget, QApplication

try:
    import ideye.config as config
    from ideye.core.gaze_estimator import GazeEstimator
    from ideye.ui.icon_manager import IconManager
except ImportError:
    import config
    from core.gaze_estimator import GazeEstimator
    from ui.icon_manager import IconManager


from ideye.core.logging_config import get_logger

logger = get_logger(__name__)


def compute_auto_mar_threshold(
    rest_samples: List[float],
    peak_samples: List[float],
) -> float:
    """Computes the 60% ergonomic MAR trigger point, clamped to [0.25, 0.70]."""
    try:
        rest = float(np.median(rest_samples)) if rest_samples else float(getattr(config, "MAR_REST_THRESHOLD", 0.20))
        peaks = [float(p) for p in peak_samples if np.isfinite(float(p))]
        peak = float(np.median(peaks)) if peaks else rest + 0.20
        threshold = rest + 0.60 * (peak - rest)
        return float(np.clip(threshold, 0.25, 0.70))
    except (TypeError, ValueError):
        return float(config.MAR_THRESHOLD)


class CalibrationMarMixin:
    """Mouth-click (MAR) calibration step."""

    @pyqtSlot(float)
    def on_mar_updated(self, mar: float) -> None:
        """Step 6 biometric MAR sampling from the tracker's frame signal."""
        if self._calibration_step != 6 or self.is_completed or self._finished_emitted:
            return
        try:
            value = float(mar)
        except (TypeError, ValueError):
            return
        if not np.isfinite(value):
            return
        self._last_mar = max(0.0, value)

        if self._mar_phase == "rest":
            self._rest_mar_samples.append(self._last_mar)
            if len(self._rest_mar_samples) >= 45:
                self._rest_mar = float(np.median(self._rest_mar_samples))
                self._mar_phase = "peaks"
                self.status_message = self._mar_status_text()
                self.update()
            return

        if self._mar_phase != "peaks":
            return

        open_threshold = max(0.22, self._rest_mar + 0.10)
        close_threshold = self._rest_mar + 0.05
        if not self._mouth_open and self._last_mar > open_threshold:
            self._mouth_open = True
            self._current_peak = self._last_mar
        elif self._mouth_open:
            self._current_peak = max(self._current_peak, self._last_mar)
            if self._last_mar < close_threshold:
                self._mouth_open = False
                self._peak_mar_samples.append(self._current_peak)
                self._completed_reps = len(self._peak_mar_samples)
                if self.sound_feedback is not None:
                    try:
                        self.sound_feedback.play("click")
                    except Exception:
                        pass
                count = min(3, len(self._peak_mar_samples))
                if count < 3:
                    self.status_message = self._mar_status_text()
                    self.update()
                    QApplication.processEvents()
                else:
                    self._mar_phase = "complete"
                    self.status_message = self._mar_status_text()
                    self.update()
                    QApplication.processEvents()
                    if self.sound_feedback is not None:
                        try:
                            self.sound_feedback.play("mode")
                        except Exception:
                            pass
                    QTimer.singleShot(650, self._finish_step6)

    def _start_auto_mar_calibration(self) -> None:
        self._calibration_step = 6
        self._mar_phase = "rest"
        self._rest_mar_samples = []
        self._peak_mar_samples = []
        self._mouth_open = False
        self._current_peak = 0.0
        self._last_mar = 0.0
        self._completion_started = False
        self._auto_mar_done = False
        self._completed_reps = 0
        self._completion_timer.stop()
        self._finish_timer.stop()
        self._mar_timeout_timer.stop()
        self.status_message = "Mantén la boca cerrada y relajada..."
        self.update()

    def _on_mar_timeout(self) -> None:
        """Step 6 never advances by timeout; ESC/Space is the only manual skip."""
        return

    def _finish_step6(self) -> None:
        """Commits the calibrated MAR threshold after the 3/3 confirmation delay."""
        if self._auto_mar_done or self._completion_started or self._finished_emitted:
            return
        self._auto_mar_done = True
        self._mar_timeout_timer.stop()
        threshold = compute_auto_mar_threshold(
            self._rest_mar_samples, self._peak_mar_samples
        )
        self._auto_mar_threshold = threshold
        rest_val = float(np.median(self._rest_mar_samples)) if self._rest_mar_samples else float(getattr(config, "MAR_REST_THRESHOLD", 0.20))
        self.mar_threshold_calibrated.emit(threshold)
        if self.settings_manager is not None:
            try:
                self.settings_manager.set("mar_threshold", threshold)
                self.settings_manager.set("mar_baseline", rest_val)
                self.settings_manager.set("mar_calibrated", True)
            except Exception:
                pass
        self._mar_phase = "done"
        self.status_message = self._mar_status_text()
        self.update()
        QApplication.processEvents()
        self._complete_calibration()

    def _finish_auto_mar_calibration(self) -> None:
        self._finish_step6()

    def _skip_auto_mar(self) -> None:
        if self._completion_started or self._finished_emitted:
            return
        self._completion_timer.stop()
        self._mar_timeout_timer.stop()
        self._auto_mar_threshold = None
        if self.settings_manager is not None:
            try:
                self.settings_manager.set("mar_calibrated", False)
                self.settings_manager.set("mar_baseline", None)
            except Exception:
                pass
        self._mar_phase = "done"
        self._calibration_step = 6
        self._complete_calibration()

    def _persist_mar_threshold(self) -> None:
        if self._auto_mar_threshold is None:
            return
        try:
            data: Dict[str, Any] = {}
            if os.path.isfile(self.profile_path):
                with open(self.profile_path, "r", encoding="utf-8") as fh:
                    loaded = json.load(fh)
                    if isinstance(loaded, dict):
                        data = loaded
            data["mar_threshold"] = float(self._auto_mar_threshold)
            tmp = self.profile_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2)
            os.replace(tmp, self.profile_path)
        except Exception as exc:
            logger.warning(f"[CalibrationUI] Warning: could not persist MAR threshold: {exc}")
