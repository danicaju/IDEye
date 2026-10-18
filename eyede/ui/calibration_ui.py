"""
Calibration UI Module for EyeDE (Phase 2)
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
import os
import sys
import time
import numpy as np

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QRectF, QPointF
from PyQt6.QtGui import QPainter, QColor, QFont, QPen, QBrush, QKeyEvent
from PyQt6.QtWidgets import QWidget, QApplication

try:
    import eyede.config as config
    from eyede.core.gaze_estimator import GazeEstimator
except ImportError:
    import config
    from core.gaze_estimator import GazeEstimator


class CalibrationUI(QWidget):
    """
    Full-screen 5-point calibration interface for EyeDE.
    """

    calibration_finished = pyqtSignal(bool)  # Emits True if succeeded, False if cancelled

    def __init__(
        self,
        gaze_estimator: Optional[GazeEstimator] = None,
        profile_path: str = config.CALIBRATION_PROFILE_PATH,
        samples_per_point: int = config.CALIBRATION_SAMPLES_PER_POINT,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)

        self.gaze_estimator = gaze_estimator or GazeEstimator()
        self.profile_path = profile_path
        self.samples_per_point = max(3, samples_per_point)

        # Calibration points configuration
        self.points: List[Dict[str, Any]] = list(config.CALIBRATION_POINTS)
        self.current_pt_idx: int = 0
        self.collected_data: List[Dict[str, Any]] = []

        # Current sampling state
        self.is_sampling: bool = False
        self.samples_buffer: List[Tuple[float, float]] = []
        self.latest_raw_gaze: Tuple[float, float] = (0.5, 0.5)
        self.is_completed: bool = False
        self.status_message: str = "Mire al punto central y abra la boca para registrar"

        # Animation timer for target pulsing
        self._pulse_phase: float = 0.0
        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._on_anim_tick)
        self._anim_timer.start(30)

        # Sampling timer
        self._sample_timer = QTimer(self)
        self._sample_timer.timeout.connect(self._collect_sample_tick)

        # UI configuration
        self.setWindowTitle("EyeDE - Calibración Visual de 5 Puntos")
        self.setStyleSheet("background-color: #12151c;")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def _on_anim_tick(self) -> None:
        """Updates animation pulse phase and requests repaint."""
        self._pulse_phase = (self._pulse_phase + 0.08) % (2 * np.pi)
        self.update()

    def on_raw_gaze_updated(self, rx: float, ry: float) -> None:
        """Slot for uncalibrated raw gaze coordinates from tracker."""
        self._has_raw_signal = True
        self.latest_raw_gaze = (rx, ry)

    def on_gaze_updated(self, gx: float, gy: float) -> None:
        """Slot for incoming gaze coordinates from tracker."""
        # Only fallback to (gx, gy) if raw_gaze_updated hasn't set latest_raw_gaze
        if not getattr(self, "_has_raw_signal", False):
            self.latest_raw_gaze = (gx, gy)

    def on_gesture_triggered(self, gesture_name: str) -> None:
        """Slot for facial gestures from tracker."""
        if gesture_name == "MOUTH_CLICK" and not self.is_sampling and not self.is_completed:
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
        self.samples_buffer.append(self.latest_raw_gaze)
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

        current_pt = self.points[self.current_pt_idx]
        self.collected_data.append({
            "id": current_pt["id"],
            "name": current_pt["name"],
            "screen": current_pt["screen"],
            "raw": (avg_x, avg_y),
        })


        self.current_pt_idx += 1
        if self.current_pt_idx < len(self.points):
            next_pt = self.points[self.current_pt_idx]
            self.status_message = f"Mire hacia '{next_pt['name']}' y abra la boca para registrar"
        else:
            self._complete_calibration()

    def _complete_calibration(self) -> None:
        """Solves 5-point calibration model, saves JSON profile, and closes."""
        self.is_completed = True
        self.update()

        # Fit model
        success = self.gaze_estimator.calibrate_5_points(self.collected_data)
        if success:
            saved = self.gaze_estimator.save_calibration_profile(self.profile_path)
            if saved:
                self.status_message = "¡Calibración completada con éxito! Guardando perfil..."
            else:
                self.status_message = "Calibración activa (no se pudo escribir el archivo JSON)."
            self.update()
            QTimer.singleShot(700, lambda: self._finish_and_emit(True))
        else:
            self.status_message = "⚠️ Calibración fallida: datos degenerados. Usando perfil previo o por defecto."
            self.update()
            QTimer.singleShot(1200, lambda: self._finish_and_emit(False))

    def _finish_and_emit(self, succeeded: bool) -> None:
        self._anim_timer.stop()
        self._sample_timer.stop()
        self.calibration_finished.emit(succeeded)
        self.close()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Keyboard shortcuts: Space triggers sample, Esc cancels."""
        if event.key() == Qt.Key.Key_Space:
            if not self.is_sampling and not self.is_completed:
                self.start_sampling()
        elif event.key() == Qt.Key.Key_Escape:
            self._anim_timer.stop()
            self._sample_timer.stop()
            self.calibration_finished.emit(False)
            self.close()
        else:
            super().keyPressEvent(event)

    def mousePressEvent(self, event) -> None:
        """Mouse click also triggers sampling for active calibration point."""
        if not self.is_sampling and not self.is_completed:
            self.start_sampling()

    def paintEvent(self, event) -> None:
        """Renders calibration targets, animated progress ring, and instructions."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        # 1. Background fill
        painter.fillRect(0, 0, w, h, QColor(18, 21, 28))

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
