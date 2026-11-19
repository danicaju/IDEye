"""
Calibration UI Module for IDEye (Phase 2)
Full-screen interactive 5-Point Gaze Calibration Window.

Guides the user through 5 sequential calibration points:
1. Centro (0.5, 0.5)
2. Arriba-Izquierda (0.1, 0.1)
3. Arriba-Derecha (0.9, 0.1)
4. Abajo-Izquierda (0.1, 0.9)
5. Abajo-Derecha (0.9, 0.9)

User looks at each point and triggers capture by opening mouth (MAR "MOUTH_CLICK")
or pressing SPACE. Averages multiple samples to eliminate jitter, calculates bilinear
mapping via GazeEstimator, and saves calibration_profile.json.
"""

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

from ideye.ui.calibration_mar import CalibrationMarMixin, compute_auto_mar_threshold  # noqa: F401
from ideye.ui.calibration_paint import CalibrationPaintMixin

class CalibrationUI(CalibrationMarMixin, CalibrationPaintMixin, QWidget):
    """
    Full-screen 5-point calibration interface for IDEye.
    """

    calibration_finished = pyqtSignal(bool)  # Emits True if succeeded, False if cancelled
    mar_threshold_calibrated = pyqtSignal(float)

    def __init__(
        self,
        gaze_estimator: Optional[GazeEstimator] = None,
        profile_path: str = config.CALIBRATION_PROFILE_PATH,
        samples_per_point: int = config.CALIBRATION_SAMPLES_PER_POINT,
        parent: Optional[QWidget] = None,
        auto_mar_enabled: bool = False,
        settings_manager: Optional[Any] = None,
        sound_feedback: Optional[Any] = None,
    ):
        super().__init__(parent)

        self.gaze_estimator = gaze_estimator or GazeEstimator()
        self.profile_path = profile_path
        self.samples_per_point = max(3, samples_per_point)
        self.auto_mar_enabled = bool(auto_mar_enabled)
        self.settings_manager = settings_manager
        self.sound_feedback = sound_feedback

        # Step 6 biometric MAR state
        self._calibration_step: int = 1
        self._mar_phase: str = "gaze"
        self._rest_mar_samples: List[float] = []
        self._peak_mar_samples: List[float] = []
        self._rest_mar: float = float(config.MAR_THRESHOLD)
        self._last_mar: float = 0.0
        self._mouth_open: bool = False
        self._current_peak: float = 0.0
        self._auto_mar_threshold: Optional[float] = None

        # Calibration points configuration
        self.points: List[Dict[str, Any]] = list(config.CALIBRATION_POINTS)
        self.current_pt_idx: int = 0
        self.collected_data: List[Dict[str, Any]] = []

        # Current sampling state
        self.is_sampling: bool = False
        self.samples_buffer: List[Tuple[float, float]] = []
        self.latest_raw_gaze: Tuple[float, float] = (0.5, 0.5)
        self.latest_raw_components: Tuple[float, float, float, float] = (0.5, 0.5, 0.5, 0.5)
        self.is_completed: bool = False
        self._finished_emitted: bool = False
        self.status_message: str = "Mire al punto central y abra la boca para registrar"

        # Pre-flight Posture & Illumination Assistant state
        self.current_distance_cm: float = float(getattr(config, "POSTURE_OPTIMAL_DISTANCE_CM", 60.0))
        self.current_luma: float = 120.0
        self.posture_optimal: bool = True
        self.lighting_optimal: bool = True

        # Animation timer for target pulsing
        self._pulse_phase: float = 0.0
        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._on_anim_tick)
        self._anim_timer.start(30)

        # Sampling timer
        self._sample_timer = QTimer(self)
        self._sample_timer.timeout.connect(self._collect_sample_tick)

        # Owned completion timers: stopped automatically on close, preventing
        # callbacks on a closed widget or double-completion races.
        self._completion_timer = QTimer(self)
        self._completion_timer.setSingleShot(True)
        self._completion_timer.timeout.connect(self._complete_calibration)
        self._finish_timer = QTimer(self)
        self._finish_timer.setSingleShot(True)
        self._finish_timer.timeout.connect(self._on_finish_timeout)
        self._mar_timeout_timer = QTimer(self)
        self._mar_timeout_timer.setSingleShot(True)
        self._mar_timeout_timer.timeout.connect(self._on_mar_timeout)
        self._finish_success: bool = True
        self._completion_started: bool = False
        self._auto_mar_done: bool = False
        self._completed_reps: int = 0

        # UI configuration
        self.setWindowTitle("IDEye - Calibración Visual de 5 Puntos")
        app_icon = IconManager.instance().get_app_icon()
        if not app_icon.isNull():
            self.setWindowIcon(app_icon)
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint)
        self.setStyleSheet("background-color: #12151c;")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def _on_anim_tick(self) -> None:
        """Updates animation pulse phase and requests repaint."""
        if self._finished_emitted or self.is_completed:
            return
        self._pulse_phase = (self._pulse_phase + 0.08) % (2 * np.pi)
        self.update()

    @property
    def completed_reps(self) -> int:
        return int(self._completed_reps)

    def on_raw_gaze_updated(self, rx: float, ry: float) -> None:
        """Slot for uncalibrated raw gaze coordinates from tracker."""
        self._has_raw_signal = True
        self.latest_raw_gaze = (rx, ry)

    def on_raw_components_updated(self, hx: float, hy: float, ix: float, iy: float) -> None:
        """Captures head and iris raw vectors from the same calibration frame."""
        self.latest_raw_components = (float(hx), float(hy), float(ix), float(iy))

    def on_gaze_updated(self, gx: float, gy: float) -> None:
        """Slot for incoming gaze coordinates from tracker."""
        # Only fallback to (gx, gy) if raw_gaze_updated hasn't set latest_raw_gaze
        if not getattr(self, "_has_raw_signal", False):
            self.latest_raw_gaze = (gx, gy)

    @pyqtSlot(float)
    def on_distance_updated(self, dist_cm: float) -> None:
        """Updates pre-flight head distance in cm."""
        try:
            val = float(dist_cm)
            if np.isfinite(val):
                self.current_distance_cm = max(20.0, min(150.0, val))
                self.posture_optimal = (50.0 <= self.current_distance_cm <= 70.0)
                self.update()
        except (TypeError, ValueError):
            pass

    @pyqtSlot(float)
    def on_lighting_updated(self, luma: float) -> None:
        """Updates pre-flight lighting luma level (0-255)."""
        try:
            val = float(luma)
            if np.isfinite(val):
                self.current_luma = max(0.0, min(255.0, val))
                self.lighting_optimal = (80.0 <= self.current_luma <= 220.0)
                self.update()
        except (TypeError, ValueError):
            pass

    def on_landmarks_updated(self, landmarks: Any) -> None:
        """Calculates pre-flight posture distance directly from landmarks."""
        if landmarks is None:
            return
        try:
            lm = getattr(landmarks, "landmark", landmarks)
            p1 = lm[33]
            p2 = lm[263]
            dx = float(p1.x - p2.x)
            dy = float(p1.y - p2.y)
            span = math.hypot(dx, dy)
            dist_cm = GazeEstimator.calculate_posture_distance_cm(span)
            self.on_distance_updated(dist_cm)
        except Exception:
            pass

    def on_gesture_triggered(self, gesture_name: str) -> None:
        """Slot for facial gestures from tracker."""
        if (
            gesture_name == "MOUTH_CLICK"
            and self._calibration_step != 6
            and not self.is_sampling
            and not self.is_completed
        ):
            self.start_sampling()

    def start_sampling(self) -> None:
        """Begins collecting samples for the active calibration point."""
        if self.is_sampling or self.is_completed:
            return
        self.is_sampling = True
        self.samples_buffer = []
        self.status_message = f"Registrando muestras... ({len(self.samples_buffer)}/{self.samples_per_point})"
        self._sample_timer.start(int(config.CALIBRATION_SAMPLE_DELAY_SEC * 1000))

    def _collect_sample_tick(self) -> None:
        """Timer callback that captures one sample into buffer."""
        if self.is_completed or self._finished_emitted:
            return
        raw_x, raw_y = self.latest_raw_gaze
        hx, hy, ix, iy = self.latest_raw_components
        self.samples_buffer.append((raw_x, raw_y, hx, hy, ix, iy))
        self.status_message = f"Registrando muestras... ({len(self.samples_buffer)}/{self.samples_per_point})"

        if len(self.samples_buffer) >= self.samples_per_point:
            self._sample_timer.stop()
            self._finish_point_sampling()

    def _finish_point_sampling(self) -> None:
        """Averages samples for the current point with outlier rejection and advances to next."""
        self.is_sampling = False
        if not self.samples_buffer:
            avg_x, avg_y = self.latest_raw_gaze
        elif len(self.samples_buffer) < 4:
            avg_x = float(np.median([s[0] for s in self.samples_buffer]))
            avg_y = float(np.median([s[1] for s in self.samples_buffer]))
        else:
            # Outlier rejection:
            # If buffer >= 6 samples, discard first 2 samples (transient movement during mouth opening)
            valid_samples = self.samples_buffer[2:] if len(self.samples_buffer) >= 6 else self.samples_buffer
            xs = np.array([s[0] for s in valid_samples], dtype=np.float64)
            ys = np.array([s[1] for s in valid_samples], dtype=np.float64)

            med_x = float(np.median(xs))
            med_y = float(np.median(ys))

            # Filter samples deviating significantly from median
            dists = np.sqrt((xs - med_x) ** 2 + (ys - med_y) ** 2)
            med_dist = float(np.median(dists))
            mad = float(np.median(np.abs(dists - med_dist)))
            cutoff = med_dist + 2.5 * max(mad, 1e-4)

            inliers_mask = dists <= cutoff
            if np.sum(inliers_mask) >= 2:
                avg_x = float(np.mean(xs[inliers_mask]))
                avg_y = float(np.mean(ys[inliers_mask]))
            else:
                avg_x = med_x
                avg_y = med_y

        valid_for_components = self.samples_buffer[2:] if len(self.samples_buffer) >= 6 else self.samples_buffer
        raw_head = raw_iris = None
        if valid_for_components and len(valid_for_components[0]) >= 6:
            raw_head = (
                float(np.median([s[2] for s in valid_for_components])),
                float(np.median([s[3] for s in valid_for_components])),
            )
            raw_iris = (
                float(np.median([s[4] for s in valid_for_components])),
                float(np.median([s[5] for s in valid_for_components])),
            )

        current_pt = self.points[self.current_pt_idx]
        point_data = {
            "id": current_pt["id"],
            "name": current_pt["name"],
            "screen": current_pt["screen"],
            "raw": (avg_x, avg_y),
        }
        if raw_head is not None and raw_iris is not None:
            point_data["raw_head"] = raw_head
            point_data["raw_iris"] = raw_iris
        self.collected_data.append(point_data)


        self.current_pt_idx += 1
        if self.current_pt_idx < len(self.points):
            next_pt = self.points[self.current_pt_idx]
            self.status_message = f"Mire hacia '{next_pt['name']}' y abra la boca para registrar"
        else:
            if self.auto_mar_enabled:
                self._start_auto_mar_calibration()
            else:
                self._complete_calibration()

    def _complete_calibration(self) -> None:
        """Solves 5-point calibration model, saves JSON profile, and closes."""
        if self._completion_started or self._finished_emitted:
            return
        self._completion_started = True
        self._completion_timer.stop()
        self.is_completed = True
        self.update()

        # Fit model. A malformed landmark/profile must never abort the Qt event loop.
        try:
            success = self.gaze_estimator.calibrate_5_points(self.collected_data)
        except Exception as exc:
            logger.warning(f"[CalibrationUI] Warning: calibration fit failed: {exc}")
            success = False
        if success:
            saved = self.gaze_estimator.save_calibration_profile(self.profile_path)
            self._persist_mar_threshold()
            if saved:
                self.status_message = "¡Calibración completada con éxito! Guardando perfil..."
            else:
                self.status_message = "Calibración activa (no se pudo escribir el archivo JSON)."
            self.update()
            self._finish_success = True
            self._finish_timer.start(700)
        else:
            self.status_message = "Calibración fallida: datos degenerados. Usando perfil previo o por defecto."
            self.update()
            self._finish_success = False
            self._finish_timer.start(1200)

    def _on_finish_timeout(self) -> None:
        self._finish_and_emit(self._finish_success)

    def _finish_and_emit(self, succeeded: bool) -> None:
        if self._finished_emitted:
            return
        self._finished_emitted = True
        self.is_completed = True
        self._completion_timer.stop()
        self._finish_timer.stop()
        self._mar_timeout_timer.stop()
        self._anim_timer.stop()
        self._sample_timer.stop()
        self.calibration_finished.emit(succeeded)
        self.close()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Keyboard shortcuts: Space samples/skips, Esc cancels or skips Step 6."""
        if self._calibration_step == 6 and event.key() in (Qt.Key.Key_Space, Qt.Key.Key_Escape):
            if not self._completion_started:
                self._skip_auto_mar()
            return
        if event.key() == Qt.Key.Key_Space:
            if not self.is_sampling and not self.is_completed:
                self.start_sampling()
        elif event.key() == Qt.Key.Key_Escape:
            self._finish_and_emit(False)
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event) -> None:
        """Ensures animation timers stop and signals calibration termination on window close."""
        self._anim_timer.stop()
        self._sample_timer.stop()
        self._completion_timer.stop()
        self._finish_timer.stop()
        self._mar_timeout_timer.stop()
        if not self._finished_emitted:
            self._finished_emitted = True
            self.calibration_finished.emit(False)
        super().closeEvent(event)

    def mousePressEvent(self, event) -> None:
        """Mouse click also triggers sampling for active calibration point."""
        if not self.is_sampling and not self.is_completed:
            self.start_sampling()
