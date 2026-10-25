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
import numpy as np

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, pyqtSlot, QRectF, QPointF
from PyQt6.QtGui import QPainter, QColor, QFont, QPen, QBrush, QKeyEvent
from PyQt6.QtWidgets import QWidget, QApplication

try:
    import eyede.config as config
    from eyede.core.gaze_estimator import GazeEstimator
    from eyede.ui.icon_manager import IconManager
except ImportError:
    import config
    from core.gaze_estimator import GazeEstimator
    from ui.icon_manager import IconManager


from eyede.core.logging_config import get_logger

logger = get_logger(__name__)

def compute_auto_mar_threshold(
    rest_samples: List[float],
    peak_samples: List[float],
) -> float:
    """Computes the 60% ergonomic MAR trigger point, clamped to [0.25, 0.70]."""
    try:
        rest = float(np.median(rest_samples)) if rest_samples else float(config.MAR_THRESHOLD)
        peaks = [float(p) for p in peak_samples if np.isfinite(float(p))]
        peak = float(np.median(peaks)) if peaks else rest + 0.20
        threshold = rest + 0.60 * (peak - rest)
        return float(np.clip(threshold, 0.25, 0.70))
    except (TypeError, ValueError):
        return float(config.MAR_THRESHOLD)


class CalibrationUI(QWidget):
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

    def on_gesture_triggered(self, gesture_name: str) -> None:
        """Slot for facial gestures from tracker."""
        if (
            gesture_name == "MOUTH_CLICK"
            and self._calibration_step != 6
            and not self.is_sampling
            and not self.is_completed
        ):
            self.start_sampling()

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
                self.status_message = "Abre la boca cómodamente 3 veces como para hacer clic (1/3)"
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
                count = self._completed_reps
                if count < 3:
                    self.status_message = (
                        f"Abre la boca c\u00f3modamente 3 veces como para hacer clic ({count + 1}/3)"
                    )
                    self.update()
                    QApplication.processEvents()
                else:
                    self._mar_phase = "complete"
                    self.status_message = "\u00a13/3 Completado! Umbral calibrado correctamente"
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
        self.mar_threshold_calibrated.emit(threshold)
        if self.settings_manager is not None:
            try:
                self.settings_manager.set("mar_threshold", threshold)
            except Exception:
                pass
        self._mar_phase = "done"
        self.status_message = "¡3/3 Completado! Umbral calibrado correctamente"
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

    def _paint_mar_step(self, painter: QPainter, w: int, h: int) -> None:
        """Step 6: resting baseline and three natural mouth-click peaks."""
        painter.setPen(QColor(230, 235, 245))
        painter.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        painter.drawText(0, 50, w, 40, Qt.AlignmentFlag.AlignCenter, "PASO 6: CALIBRACIÓN DE CLIC BUCAL")

        painter.setFont(QFont("Segoe UI", 12))
        painter.setPen(QColor(160, 170, 190))
        painter.drawText(0, 95, w, 30, Qt.AlignmentFlag.AlignCenter, self.status_message)

        cx, cy = w / 2.0, h / 2.0
        radius = 96.0
        ratio = max(0.0, min(1.0, self._last_mar / 0.70))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(55, 65, 85), 8))
        painter.drawEllipse(QPointF(cx, cy), radius, radius)
        painter.setPen(QPen(QColor(255, 195, 45), 8))
        painter.drawArc(
            QRectF(cx - radius, cy - radius, radius * 2, radius * 2),
            90 * 16,
            -int(360 * 16 * ratio),
        )
        painter.setPen(QColor(230, 235, 245))
        painter.setFont(QFont("Segoe UI", 26, QFont.Weight.Bold))
        painter.drawText(
            QRectF(cx - 80, cy - 24, 160, 48),
            Qt.AlignmentFlag.AlignCenter,
            f"MAR {self._last_mar:.2f}",
        )

        # Baseline and captured peaks.
        painter.setFont(QFont("Segoe UI", 10))
        painter.setPen(QColor(125, 211, 252))
        painter.drawText(
            int(cx - 180),
            int(cy + radius + 18),
            360,
            24,
            Qt.AlignmentFlag.AlignCenter,
            f"Reposo: {self._rest_mar:.2f}",
        )
        for i in range(3):
            dot_x = cx + (i - 1) * 34
            dot_y = cy + radius + 52
            painter.setBrush(QBrush(QColor(40, 210, 110) if i < len(self._peak_mar_samples) else QColor(50, 55, 70)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(dot_x, dot_y), 8, 8)

        painter.setPen(QColor(110, 120, 140))
        painter.setFont(QFont("Segoe UI", 10))
        painter.drawText(
            0,
            h - 50,
            w,
            30,
            Qt.AlignmentFlag.AlignCenter,
            "Cierra la boca entre cada apertura · ESPACIO/ESC para omitir este paso",
        )

    def paintEvent(self, event) -> None:
        """Renders calibration targets, animated progress ring, and instructions."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        # 1. Background fill
        painter.fillRect(0, 0, w, h, QColor(18, 21, 28))

        if self._calibration_step == 6:
            self._paint_mar_step(painter, w, h)
            painter.end()
            return

        # 2. Header and instructions
        painter.setPen(QColor(230, 235, 245))
        font_title = QFont("Segoe UI", 20, QFont.Weight.Bold)
        painter.setFont(font_title)
        title_text = "CALIBRACIÓN VISUAL DE 5 PUNTOS"
        painter.drawText(0, 50, w, 40, Qt.AlignmentFlag.AlignCenter, title_text)

        font_sub = QFont("Segoe UI", 12)
        painter.setFont(font_sub)
        painter.setPen(QColor(160, 170, 190))
        painter.drawText(0, 95, w, 30, Qt.AlignmentFlag.AlignCenter, self.status_message)

        font_hint = QFont("Segoe UI", 10)
        painter.setFont(font_hint)
        painter.setPen(QColor(110, 120, 140))
        painter.drawText(0, h - 50, w, 30, Qt.AlignmentFlag.AlignCenter, "Controles: Mirar + Abrir boca (o presionar ESPACIO / Clic) | ESC para cancelar")

        # 3. Step indicator dots at bottom
        dot_spacing = 30
        start_x = (w - (len(self.points) - 1) * dot_spacing) / 2
        dot_y = h - 80
        for i in range(len(self.points)):
            cx = start_x + i * dot_spacing
            if i < self.current_pt_idx:
                painter.setBrush(QBrush(QColor(40, 210, 110)))
                painter.setPen(Qt.PenStyle.NoPen)
            elif i == self.current_pt_idx:
                painter.setBrush(QBrush(QColor(255, 195, 45)))
                painter.setPen(QPen(QColor(255, 255, 255), 2))
            else:
                painter.setBrush(QBrush(QColor(50, 55, 70)))
                painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(cx, dot_y), 6, 6)

        # 4. Calibration Target rendering
        if self.current_pt_idx < len(self.points):
            pt = self.points[self.current_pt_idx]
            target_x = pt["screen"][0] * w
            target_y = pt["screen"][1] * h

            # Pulsing outer ring
            pulse_radius = 28 + 6 * np.sin(self._pulse_phase)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(255, 195, 45, 120), 2, Qt.PenStyle.DashLine))
            painter.drawEllipse(QPointF(target_x, target_y), pulse_radius, pulse_radius)

            # Solid target ring
            ring_color = QColor(40, 210, 110) if self.is_sampling else QColor(255, 195, 45)
            painter.setPen(QPen(ring_color, 3))
            painter.drawEllipse(QPointF(target_x, target_y), 20, 20)

            # Center bullseye
            painter.setBrush(QBrush(ring_color))
            painter.drawEllipse(QPointF(target_x, target_y), 6, 6)

            # Circular progress arc if sampling
            if self.is_sampling and self.samples_per_point > 0:
                progress_ratio = len(self.samples_buffer) / self.samples_per_point
                span_angle = int(progress_ratio * 360 * 16)
                painter.setPen(QPen(QColor(50, 255, 140), 5))
                rect = QRectF(target_x - 34, target_y - 34, 68, 68)
                painter.drawArc(rect, 90 * 16, -span_angle)

            # Point Name label below target
            painter.setPen(QColor(220, 225, 235))
            painter.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
            painter.drawText(int(target_x - 100), int(target_y + 35), 200, 25, Qt.AlignmentFlag.AlignCenter, pt["name"])

        painter.end()
