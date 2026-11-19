"""Debug panel slots, setters and telemetry."""

import os
import time
from typing import Optional, Any
import cv2
import numpy as np

from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QFileDialog,
    QFrame,
    QSlider,
    QComboBox,
    QScrollArea,
    QSizePolicy,
    QCheckBox,
)

try:
    import ideye.config as config
    from ideye.ui.icon_manager import IconManager
    from ideye.actions.language_support import (
        LANG_PYTHON,
        LANG_TYPESCRIPT,
        LANG_RUST,
        LANG_CPP,
        LANG_GO,
        SUPPORTED_LANGUAGES,
        LANGUAGE_DISPLAY_NAMES,
        LANGUAGE_BADGES,
        normalize_language,
        get_language_display_name,
        get_language_badge,
    )
except ImportError:
    import config
    from ui.icon_manager import IconManager
    from actions.language_support import (
        LANG_PYTHON,
        LANG_TYPESCRIPT,
        LANG_RUST,
        LANG_CPP,
        LANG_GO,
        SUPPORTED_LANGUAGES,
        LANGUAGE_DISPLAY_NAMES,
        LANGUAGE_BADGES,
        normalize_language,
        get_language_display_name,
        get_language_badge,
    )


class DebugHandlersMixin:
    """Debug panel slots, setters and telemetry."""

    def toggle_collapse(self) -> None:
        """Toggles between expanded monitor window and sleek mini-bar mode."""
        self.is_collapsed = not getattr(self, "is_collapsed", False)
        if self.is_collapsed:
            self.content_container.hide()
            self.content_scroll.hide()
            self.setFixedHeight(48)
            self.btn_collapse.setText("Expandir")
            self.btn_collapse.setToolTip("Expandir monitor de depuración")
        else:
            self.content_container.show()
            self.content_scroll.show()
            self.setFixedSize(config.DEBUG_WINDOW_WIDTH, config.DEBUG_WINDOW_HEIGHT)
            self.btn_collapse.setText("Colapsar")
            self.btn_collapse.setToolTip("Colapsar a mini-barra")
        self.collapsed_toggled.emit(self.is_collapsed)

    def _on_slider_sens_x_changed(self, value: int) -> None:
        val = value / 10.0
        self.lbl_sens_x.setText(f"Sensibilidad X: {val:.1f}x")
        self.sensitivity_x_changed.emit(val)
        if self.gaze_estimator is not None:
            self.gaze_estimator.set_sensitivity(head_x=val, iris_x=val * 1.35)

    def _on_slider_sens_y_changed(self, value: int) -> None:
        val = value / 10.0
        self.lbl_sens_y.setText(f"Sensibilidad Y (Ergonómica): {val:.1f}x")
        self.sensitivity_y_changed.emit(val)
        if self.gaze_estimator is not None:
            self.gaze_estimator.set_sensitivity(head_y=val, iris_y=val * 1.30)

    def _on_slider_mar_changed(self, value: int) -> None:
        self.mar_threshold = max(0.25, min(0.70, value / 100.0))
        self.lbl_mar_threshold.setText(f"Umbral MAR: {self.mar_threshold:.2f}")
        self.mar_threshold_changed.emit(self.mar_threshold)
        self.update_mar(self._last_mar)

    def set_mar_threshold(self, value: float, emit: bool = False) -> None:
        value = max(0.25, min(0.70, float(value)))
        self.mar_threshold = value
        self.slider_mar_threshold.blockSignals(True)
        self.slider_mar_threshold.setValue(int(round(value * 100)))
        self.slider_mar_threshold.blockSignals(False)
        self.lbl_mar_threshold.setText(f"Umbral MAR: {value:.2f}")
        if emit:
            self.mar_threshold_changed.emit(value)

    def _on_slider_damping_changed(self, value: int) -> None:
        self.lbl_damping.setText(f"Anti-Temblor (Filtro 1€): Nivel {value}")
        self.anti_jitter_changed.emit(float(value))
        if self.gaze_estimator is not None and hasattr(self.gaze_estimator, "set_anti_jitter_damping"):
            self.gaze_estimator.set_anti_jitter_damping(float(value))

    def _on_reset_clicked(self) -> None:
        """Resets sliders to standard defaults and emits signal."""
        hx = getattr(config, "DEFAULT_HEAD_SENSITIVITY_X", 2.6)
        hy = getattr(config, "DEFAULT_HEAD_SENSITIVITY_Y", 3.0)
        self.slider_sens_x.setValue(int(hx * 10))
        self.slider_sens_y.setValue(int(hy * 10))
        self.slider_damping.setValue(6)
        self.reset_calibration_requested.emit()

    def _on_link_file_clicked(self) -> None:
        """Opens file dialog for user to select an active source code file."""
        initial_dir = getattr(config, "DEFAULT_WORKSPACE_DIR", ".")
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Vincular Archivo de Código",
            initial_dir,
            "Archivos de Código (*.py *.ts *.tsx *.js *.jsx *.rs *.cpp *.hpp *.c *.h *.go);;Python (*.py);;TypeScript/JS (*.ts *.tsx *.js *.jsx);;Rust (*.rs);;C/C++ (*.cpp *.hpp *.c *.h);;Go (*.go);;Todos (*.*)",
        )
        if file_path:
            self.set_linked_file(file_path)
            self.file_linked.emit(file_path)

    @pyqtSlot(bool)
    def set_health_guard_enabled(self, enabled: bool) -> None:
        if hasattr(self, "chk_health_guard"):
            self.chk_health_guard.blockSignals(True)
            self.chk_health_guard.setChecked(bool(enabled))
            self.chk_health_guard.blockSignals(False)

    def set_micro_gestures_enabled(self, enabled: bool) -> None:
        if hasattr(self, "chk_micro_gestures"):
            self.chk_micro_gestures.blockSignals(True)
            self.chk_micro_gestures.setChecked(bool(enabled))
            self.chk_micro_gestures.blockSignals(False)

    def set_cap_mode_enabled(self, enabled: bool) -> None:
        if hasattr(self, "chk_cap_mode"):
            self.chk_cap_mode.blockSignals(True)
            self.chk_cap_mode.setChecked(bool(enabled))
            self.chk_cap_mode.blockSignals(False)

    def set_low_light_enabled(self, enabled: bool) -> None:
        if hasattr(self, "chk_low_light"):
            self.chk_low_light.blockSignals(True)
            self.chk_low_light.setChecked(bool(enabled))
            self.chk_low_light.blockSignals(False)

    def set_eco_sleep_enabled(self, enabled: bool) -> None:
        if hasattr(self, "chk_eco_sleep"):
            self.chk_eco_sleep.blockSignals(True)
            self.chk_eco_sleep.setChecked(bool(enabled))
            self.chk_eco_sleep.blockSignals(False)

    def set_reduced_motion(self, enabled: bool) -> None:
        if hasattr(self, "chk_reduced_motion"):
            self.chk_reduced_motion.blockSignals(True)
            self.chk_reduced_motion.setChecked(bool(enabled))
            self.chk_reduced_motion.blockSignals(False)

    def set_ghost_peek_enabled(self, enabled: bool) -> None:
        if hasattr(self, "chk_ghost_peek"):
            self.chk_ghost_peek.blockSignals(True)
            self.chk_ghost_peek.setChecked(bool(enabled))
            self.chk_ghost_peek.blockSignals(False)

    def set_winks_enabled(self, enabled: bool) -> None:
        if hasattr(self, "chk_winks"):
            self.chk_winks.blockSignals(True)
            self.chk_winks.setChecked(bool(enabled))
            self.chk_winks.blockSignals(False)

    def set_wink_mouth_only(self, enabled: bool) -> None:
        if hasattr(self, "chk_wink_mouth_only"):
            self.chk_wink_mouth_only.blockSignals(True)
            self.chk_wink_mouth_only.setChecked(bool(enabled))
            self.chk_wink_mouth_only.blockSignals(False)

    def set_power_state(self, state: str) -> None:
        if not hasattr(self, "lbl_power_state"):
            return
        normalized = str(state or "ACTIVE").upper()
        colors = {
            "ACTIVE": "#22d3ee",
            "PAUSED_ECO": "#f59e0b",
            "AWAY_DEEP_SLEEP": "#94a3b8",
        }
        label = {
            "ACTIVE": "Activo",
            "PAUSED_ECO": "Pausa",
            "AWAY_DEEP_SLEEP": "Reposo",
        }.get(normalized, normalized.replace("_", " ").capitalize())
        self.lbl_power_state.setText(label)
        self.lbl_power_state.setToolTip("Estado del ahorro de energía")
        self.lbl_power_state.setStyleSheet(
            f"font-size: 10px; font-weight: bold; color: {colors.get(normalized, '#22d3ee')};"
        )

    def set_lighting_status(self, active: bool, luma: float) -> None:
        if hasattr(self, "lbl_lighting"):
            self.lbl_lighting.setText("Visión nocturna" if active else f"Luz: {float(luma):.0f}")
            self.lbl_lighting.setStyleSheet(
                "font-size: 10px; font-weight: bold; color: %s;" % ("#fbbf24" if active else "#34d399")
            )

    def set_linked_file(self, file_path: str) -> None:
        """Updates the active file label."""
        if file_path:
            name = os.path.basename(file_path)
            self.lbl_active_file.setText(f"Archivo: {name}")

    @pyqtSlot(str)
    def update_ai_status(self, status: str) -> None:
        """Updates the AI engine status label."""
        self.lbl_ai_engine.setText(f"IA: {status}")

    @pyqtSlot(float)
    def update_mar(self, current_mar: float) -> None:
        """Updates the MAR progress bar and style based on threshold."""
        self._last_mar = float(current_mar)
        val = max(0.0, min(1.0, current_mar))
        pct = int(val * 100)
        self.mar_bar.setValue(pct)
        self.mar_bar.setFormat(f"MAR: {current_mar:.2f}")
        self.mar_label.setText(f"Nivel MAR: {current_mar:.2f} (Umbral: {self.mar_threshold:.2f})")

        # Visual indicator when mouth opens past threshold
        if current_mar >= self.mar_threshold:
            self.mar_bar.setStyleSheet("""
                QProgressBar::chunk {
                    background-color: #22c55e;
                }
            """)
        else:
            self.mar_bar.setStyleSheet("""
                QProgressBar::chunk {
                    background-color: #22d3ee;
                }
            """)

    def _build_telemetry_card(self) -> QFrame:
        frame = QFrame(self)
        frame.setObjectName("cardFrame")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        title = QLabel("MÉTRICAS DE EFICIENCIA (LOOK-TO-CODE)", frame)
        title.setStyleSheet("font-size: 11px; font-weight: bold; color: #22d3ee; letter-spacing: 0.5px;")
        layout.addWidget(title)

        self.lbl_telemetry_saved = QLabel("Ahorro Físico: 0 teclas (0% menos esfuerzo)", frame)
        self.lbl_telemetry_saved.setStyleSheet("font-size: 10px; color: #93c5fd; padding: 1px 0;")
        self.lbl_telemetry_saved.setWordWrap(True)
        self.lbl_telemetry_saved.setMinimumWidth(0)
        self.lbl_telemetry_saved.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        layout.addWidget(self.lbl_telemetry_saved)

        self.lbl_telemetry_injected = QLabel("Inyectado: 0 chars en 0 clics", frame)
        self.lbl_telemetry_injected.setStyleSheet("font-size: 10px; color: #60a5fa; padding: 1px 0;")
        self.lbl_telemetry_injected.setWordWrap(True)
        self.lbl_telemetry_injected.setMinimumWidth(0)
        self.lbl_telemetry_injected.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        layout.addWidget(self.lbl_telemetry_injected)

        self.lbl_foreground = QLabel("Ventana activa: —", frame)
        self.lbl_foreground.setStyleSheet("font-size: 9px; color: #94a3b8; padding: 1px 0;")
        self.lbl_foreground.setWordWrap(True)
        self.lbl_foreground.setMinimumWidth(0)
        self.lbl_foreground.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        layout.addWidget(self.lbl_foreground)

        reset = QPushButton("Reset métricas", frame)
        reset.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        reset.setStyleSheet("""
            QPushButton {
                background-color: rgba(30, 41, 59, 0.7);
                border: 1px solid #1e293b;
                border-radius: 8px;
                padding: 4px 8px;
                font-size: 10px;
                color: #cbd5e1;
            }
            QPushButton:hover {
                background-color: rgba(37, 99, 235, 0.25);
                border-color: #22d3ee;
                color: #ffffff;
            }
        """)
        reset.clicked.connect(self.telemetry_reset_requested.emit)
        layout.addWidget(reset)
        return frame

    def update_telemetry(self, stats: dict) -> None:
        saved = int(stats.get("keystrokes_saved", 0))
        ratio = float(stats.get("efficiency_ratio_pct", 0.0))
        chars = int(stats.get("total_chars_injected", 0))
        clicks = int(stats.get("total_mouth_clicks", 0))
        self.lbl_telemetry_saved.setText(
            f"Ahorro Físico: {saved} teclas ({ratio:.0f}% menos esfuerzo)"
        )
        self.lbl_telemetry_injected.setText(
            f"Inyectado: {chars} chars en {clicks} clics"
        )

    def set_foreground_window(self, title: str, process_name: str) -> None:
        label = str(process_name or title or "—")
        self.lbl_foreground.setText(f"Ventana activa: {label}")
