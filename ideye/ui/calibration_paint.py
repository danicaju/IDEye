"""Painting of the calibration screen."""

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


class CalibrationPaintMixin:
    """Painting of the calibration screen."""

    def _mar_completed_count(self) -> int:
        """Number of completed mouth-click reps, capped at the target of 3."""
        return max(0, min(3, len(self._peak_mar_samples)))

    def _mar_status_text(self) -> str:
        """Single source of truth for the Step 6 counter shown above the ring."""
        count = self._mar_completed_count()
        if self._mar_phase in ("complete", "done") or count >= 3:
            return "3/3 Completado. Umbral calibrado correctamente"
        if self._mar_phase == "peaks":
            return f"Abre la boca c\u00f3modamente 3 veces como para hacer clic ({count}/3)"
        return self.status_message

    def _paint_mar_step(self, painter: QPainter, w: int, h: int) -> None:
        """Step 6: resting baseline and three natural mouth-click peaks."""
        painter.setPen(QColor(230, 235, 245))
        painter.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        painter.drawText(0, 50, w, 40, Qt.AlignmentFlag.AlignCenter, "PASO 6: CALIBRACIÓN DE CLIC BUCAL")

        painter.setFont(QFont("Segoe UI", 12))
        painter.setPen(QColor(160, 170, 190))
        painter.drawText(0, 95, w, 30, Qt.AlignmentFlag.AlignCenter, self._mar_status_text())

        cx, cy = w / 2.0, h / 2.0
        radius = 96.0
        ratio = max(0.0, min(1.0, self._last_mar / 0.70))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(30, 41, 59), 8))
        painter.drawEllipse(QPointF(cx, cy), radius, radius)
        is_done = self._mar_completed_count() >= 3 or self._mar_phase in ("complete", "done")
        arc_color = QColor(16, 185, 129) if is_done else QColor(59, 130, 246)
        painter.setPen(QPen(arc_color, 8))
        painter.drawArc(
            QRectF(cx - radius, cy - radius, radius * 2, radius * 2),
            90 * 16,
            -int(360 * 16 * ratio),
        )
        painter.setPen(QColor(248, 250, 252))
        painter.setFont(QFont("Segoe UI", 26, QFont.Weight.Bold))
        painter.drawText(
            QRectF(cx - 80, cy - 24, 160, 48),
            Qt.AlignmentFlag.AlignCenter,
            f"MAR {self._last_mar:.2f}",
        )

        # Baseline and captured peaks.
        painter.setFont(QFont("Segoe UI", 10))
        painter.setPen(QColor(96, 165, 250))
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
            painter.setBrush(QBrush(QColor(16, 185, 129) if i < len(self._peak_mar_samples) else QColor(30, 41, 59)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(dot_x, dot_y), 8, 8)

        painter.setPen(QColor(100, 116, 139))
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

        # 1. Background fill (Sleek Cyber-Glass dark graphite #0a0f1d)
        painter.fillRect(0, 0, w, h, QColor(10, 15, 29))

        if self._calibration_step == 6:
            self._paint_mar_step(painter, w, h)
            painter.end()
            return

        # 2. Header and instructions
        painter.setPen(QColor(248, 250, 252))
        font_title = QFont("Segoe UI", 20, QFont.Weight.Bold)
        painter.setFont(font_title)
        title_text = "CALIBRACIÓN VISUAL DE 5 PUNTOS"
        painter.drawText(0, 50, w, 40, Qt.AlignmentFlag.AlignCenter, title_text)

        font_sub = QFont("Segoe UI", 12)
        painter.setFont(font_sub)
        painter.setPen(QColor(148, 163, 184))
        painter.drawText(0, 95, w, 30, Qt.AlignmentFlag.AlignCenter, self.status_message)

        # Pre-flight Posture & Illumination assistant pills
        preflight_y = 132
        pill_w = 220
        pill_h = 28
        gap = 14
        total_pills_w = 2 * pill_w + gap
        pill_start_x = (w - total_pills_w) / 2

        # Posture Pill
        posture_rect = QRectF(pill_start_x, preflight_y, pill_w, pill_h)
        if self.posture_optimal:
            p_bg = QColor(10, 30, 20, 220)
            p_border = QColor(16, 185, 129)
            p_text = f"Distancia: {self.current_distance_cm:.0f} cm [Optima]"
        else:
            p_bg = QColor(30, 20, 10, 220)
            p_border = QColor(245, 158, 11)
            p_text = f"Distancia: {self.current_distance_cm:.0f} cm [50-70 cm]"

        painter.setBrush(QBrush(p_bg))
        painter.setPen(QPen(p_border, 1.0))
        painter.drawRoundedRect(posture_rect, 7.0, 7.0)
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
        painter.setPen(QColor(236, 253, 245) if self.posture_optimal else QColor(254, 243, 199))
        painter.drawText(posture_rect, Qt.AlignmentFlag.AlignCenter, p_text)

        # Lighting Pill
        light_rect = QRectF(pill_start_x + pill_w + gap, preflight_y, pill_w, pill_h)
        if self.lighting_optimal:
            l_bg = QColor(10, 30, 20, 220)
            l_border = QColor(16, 185, 129)
            l_text = f"Luz: {self.current_luma:.0f} lx [Optima]"
        elif self.current_luma < 80.0:
            l_bg = QColor(30, 20, 10, 220)
            l_border = QColor(245, 158, 11)
            l_text = f"Luz: {self.current_luma:.0f} lx [Baja luz]"
        else:
            l_bg = QColor(35, 15, 15, 220)
            l_border = QColor(239, 68, 68)
            l_text = f"Luz: {self.current_luma:.0f} lx [Alta]"

        painter.setBrush(QBrush(l_bg))
        painter.setPen(QPen(l_border, 1.0))
        painter.drawRoundedRect(light_rect, 7.0, 7.0)
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
        painter.setPen(QColor(236, 253, 245) if self.lighting_optimal else QColor(254, 226, 226))
        painter.drawText(light_rect, Qt.AlignmentFlag.AlignCenter, l_text)

        font_hint = QFont("Segoe UI", 10)
        painter.setFont(font_hint)
        painter.setPen(QColor(100, 116, 139))
        painter.drawText(0, h - 50, w, 30, Qt.AlignmentFlag.AlignCenter, "Controles: Mirar + Abrir boca (o presionar ESPACIO / Clic) | ESC para cancelar")

        # 3. Step indicator dots at bottom
        dot_spacing = 30
        start_x = (w - (len(self.points) - 1) * dot_spacing) / 2
        dot_y = h - 80
        for i in range(len(self.points)):
            cx = start_x + i * dot_spacing
            if i < self.current_pt_idx:
                painter.setBrush(QBrush(QColor(16, 185, 129)))
                painter.setPen(Qt.PenStyle.NoPen)
            elif i == self.current_pt_idx:
                painter.setBrush(QBrush(QColor(59, 130, 246)))
                painter.setPen(QPen(QColor(255, 255, 255), 2))
            else:
                painter.setBrush(QBrush(QColor(30, 41, 59)))
                painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(cx, dot_y), 6, 6)

        # 4. Calibration Target rendering (Pulsing sapphire concentric rings)
        if self.current_pt_idx < len(self.points):
            pt = self.points[self.current_pt_idx]
            target_x = pt["screen"][0] * w
            target_y = pt["screen"][1] * h

            # Outer pulsing halo ring
            pulse_radius = 32 + 8 * np.sin(self._pulse_phase)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(59, 130, 246, 120), 1.5, Qt.PenStyle.DashLine))
            painter.drawEllipse(QPointF(target_x, target_y), pulse_radius, pulse_radius)

            # Secondary concentric ring
            mid_radius = 24 + 4 * np.sin(self._pulse_phase + 0.5)
            painter.setPen(QPen(QColor(96, 165, 250, 90), 1.0))
            painter.drawEllipse(QPointF(target_x, target_y), mid_radius, mid_radius)

            # Solid target ring
            ring_color = QColor(16, 185, 129) if self.is_sampling else QColor(59, 130, 246)
            painter.setPen(QPen(ring_color, 2.5))
            painter.drawEllipse(QPointF(target_x, target_y), 18, 18)

            # Center bullseye
            painter.setBrush(QBrush(ring_color))
            painter.drawEllipse(QPointF(target_x, target_y), 5, 5)

            # Circular progress arc if sampling
            if self.is_sampling and self.samples_per_point > 0:
                progress_ratio = len(self.samples_buffer) / self.samples_per_point
                span_angle = int(progress_ratio * 360 * 16)
                painter.setPen(QPen(QColor(16, 185, 129), 4.0))
                rect = QRectF(target_x - 34, target_y - 34, 68, 68)
                painter.drawArc(rect, 90 * 16, -span_angle)

            # Point Name label below target
            painter.setPen(QColor(241, 245, 249))
            painter.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
            painter.drawText(int(target_x - 100), int(target_y + 35), 200, 25, Qt.AlignmentFlag.AlignCenter, pt["name"])

        painter.end()
