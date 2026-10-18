"""
Debug & Monitor Widget for EyeDE (Phase 2 & Overhaul)
Compact floating window displaying live webcam feed, real-time FPS meter,
tracking stability indicator, interactive sensitivity/damping sliders, and controls.

Features:
- Live FPS meter and real-time fixation/stability status indicator.
- Video preview thumbnail with landmark annotations and safe .copy() memory management.
- Real-time MAR (Mouth Aspect Ratio) meter with threshold indicator.
- Interactive sliders for X Sensitivity, Y Sensitivity, and Anti-Jitter Damping.
- 'Recalibrar' button to trigger 5-point calibration sequence.
- 'Reset' button to restore safe defaults.
- 'Salir' button to request graceful application termination.
- Strict non-focus stealing policy (WA_ShowWithoutActivating & NoFocus).
"""

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
)

try:
    import eyede.config as config
except ImportError:
    import config


class DebugWidget(QWidget):
    """
    Compact floating debug & monitor window for EyeDE with interactive tuning controls.
    """

    recalibrate_requested = pyqtSignal()
    reset_calibration_requested = pyqtSignal()
    exit_requested = pyqtSignal()
    file_linked = pyqtSignal(str)
    sensitivity_x_changed = pyqtSignal(float)
    sensitivity_y_changed = pyqtSignal(float)
    anti_jitter_changed = pyqtSignal(float)

    def __init__(self, parent: Optional[QWidget] = None, gaze_estimator: Optional[Any] = None):
        super().__init__(parent)

        self.gaze_estimator = gaze_estimator
        self._last_frame_time: Optional[float] = None
        self._fps: float = 30.0

        self.setWindowTitle("EyeDE - Monitor y Depuración")
        self.setFixedSize(config.DEBUG_WINDOW_WIDTH, config.DEBUG_WINDOW_HEIGHT)
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self._setup_ui()

    def set_gaze_estimator(self, estimator: Any) -> None:
        """Links the GazeEstimator instance for direct real-time parameter tuning."""
        self.gaze_estimator = estimator
        if estimator is not None:
            # Sync slider positions with estimator
            hx = getattr(estimator, "head_sensitivity_x", config.DEFAULT_HEAD_SENSITIVITY_X)
            hy = getattr(estimator, "head_sensitivity_y", config.DEFAULT_HEAD_SENSITIVITY_Y)
            self.slider_sens_x.setValue(int(hx * 10))
            self.slider_sens_y.setValue(int(hy * 10))

    def _setup_ui(self) -> None:
        """Constructs UI layout, styles, and controls."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(6)

        # 1. Dark theme stylesheet
        self.setStyleSheet("""
            QWidget {
                background-color: #0f172a;
                color: #e2e8f0;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QLabel {
                font-size: 11px;
                color: #94a3b8;
            }
            QProgressBar {
                border: 1px solid #334155;
                border-radius: 4px;
                background-color: #0b0f19;
                text-align: center;
                height: 16px;
                font-size: 10px;
                font-weight: bold;
                color: #f8fafc;
            }
            QProgressBar::chunk {
                background-color: #38bdf8;
                border-radius: 3px;
            }
            QSlider::groove:horizontal {
                height: 6px;
                background: #1e293b;
                border: 1px solid #334155;
                border-radius: 3px;
            }
            QSlider::sub-page:horizontal {
                background: #0284c7;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #38bdf8;
                border: 1px solid #e0f2fe;
                width: 14px;
                margin-top: -4px;
                margin-bottom: -4px;
                border-radius: 7px;
            }
            QSlider::handle:horizontal:hover {
                background: #7dd3fc;
            }
            QPushButton {
                background-color: #1e293b;
                border: 1px solid #475569;
                border-radius: 5px;
                padding: 6px 10px;
                font-size: 11px;
                font-weight: 600;
                color: #f1f5f9;
            }
            QPushButton:hover {
                background-color: #334155;
                border-color: #64748b;
            }
            QPushButton:pressed {
                background-color: #0b0f19;
            }
            QPushButton#btnReset {
                background-color: #1e3a5f;
                border-color: #2563eb;
            }
            QPushButton#btnReset:hover {
                background-color: #2563eb;
            }
            QPushButton#btnExit {
                background-color: #7f1d1d;
                border-color: #991b1b;
            }
            QPushButton#btnExit:hover {
                background-color: #991b1b;
            }
            QFrame#cardFrame {
                background-color: #162032;
                border: 1px solid #1e293b;
                border-radius: 6px;
                padding: 4px;
            }
        """)

        # 2. Top Stats Header: Live FPS Meter & Stability Indicator
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(8)

        self.lbl_fps = QLabel("⚡ 30.0 FPS", self)
        self.lbl_fps.setStyleSheet("font-size: 11px; font-weight: bold; color: #38bdf8;")
        stats_layout.addWidget(self.lbl_fps, alignment=Qt.AlignmentFlag.AlignLeft)

        self.lbl_stability = QLabel("🟢 100% Fijación", self)
        self.lbl_stability.setStyleSheet("font-size: 11px; font-weight: bold; color: #34d399;")
        stats_layout.addWidget(self.lbl_stability, alignment=Qt.AlignmentFlag.AlignRight)

        main_layout.addLayout(stats_layout)

        # 3. Camera Feed Thumbnail
        self.video_label = QLabel(self)
        self.video_label.setFixedSize(config.DEBUG_FEED_WIDTH, config.DEBUG_FEED_HEIGHT)
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setStyleSheet("background-color: #070a12; border: 1px solid #1e293b; border-radius: 6px;")
        self.video_label.setText("Iniciando cámara...")
        main_layout.addWidget(self.video_label, alignment=Qt.AlignmentFlag.AlignCenter)

        # 4. MAR Progress Bar and Text
        mar_layout = QVBoxLayout()
        mar_layout.setSpacing(2)

        self.mar_label = QLabel(f"Nivel MAR: 0.00 (Umbral Clic: {config.MAR_THRESHOLD:.2f})", self)
        mar_layout.addWidget(self.mar_label)

        self.mar_bar = QProgressBar(self)
        self.mar_bar.setRange(0, 100)
        self.mar_bar.setValue(0)
        self.mar_bar.setTextVisible(True)
        mar_layout.addWidget(self.mar_bar)

        main_layout.addLayout(mar_layout)

        # 5. Interactive Tuning Sliders Frame
        slider_frame = QFrame(self)
        slider_frame.setObjectName("cardFrame")
        slider_layout = QVBoxLayout(slider_frame)
        slider_layout.setContentsMargins(6, 6, 6, 6)
        slider_layout.setSpacing(4)

        lbl_section = QLabel("🎛️ CONTROLES DE SENSIBILIDAD Y TEMBLOR", slider_frame)
        lbl_section.setStyleSheet("font-size: 10px; font-weight: bold; color: #cbd5e1;")
        slider_layout.addWidget(lbl_section)

        # Slider 1: X Sensitivity
        sens_x_val = getattr(config, "DEFAULT_HEAD_SENSITIVITY_X", 2.6)
        self.lbl_sens_x = QLabel(f"Sensibilidad X: {sens_x_val:.1f}x", slider_frame)
        slider_layout.addWidget(self.lbl_sens_x)

        self.slider_sens_x = QSlider(Qt.Orientation.Horizontal, slider_frame)
        self.slider_sens_x.setRange(10, 80)  # 1.0 to 8.0
        self.slider_sens_x.setValue(int(sens_x_val * 10))
        self.slider_sens_x.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.slider_sens_x.valueChanged.connect(self._on_slider_sens_x_changed)
        slider_layout.addWidget(self.slider_sens_x)

        # Slider 2: Y Sensitivity
        sens_y_val = getattr(config, "DEFAULT_HEAD_SENSITIVITY_Y", 6.8)
        self.lbl_sens_y = QLabel(f"Sensibilidad Y (Ergonómica): {sens_y_val:.1f}x", slider_frame)
        slider_layout.addWidget(self.lbl_sens_y)

        self.slider_sens_y = QSlider(Qt.Orientation.Horizontal, slider_frame)
        self.slider_sens_y.setRange(20, 140)  # 2.0 to 14.0
        self.slider_sens_y.setValue(int(sens_y_val * 10))
        self.slider_sens_y.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.slider_sens_y.valueChanged.connect(self._on_slider_sens_y_changed)
        slider_layout.addWidget(self.slider_sens_y)

        # Slider 3: Anti-Jitter Damping (1€ Filter)
        self.lbl_damping = QLabel("Anti-Temblor (Filtro 1€): Nivel 6", slider_frame)
        slider_layout.addWidget(self.lbl_damping)

        self.slider_damping = QSlider(Qt.Orientation.Horizontal, slider_frame)
        self.slider_damping.setRange(1, 10)
        self.slider_damping.setValue(6)
        self.slider_damping.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.slider_damping.valueChanged.connect(self._on_slider_damping_changed)
        slider_layout.addWidget(self.slider_damping)

        main_layout.addWidget(slider_frame)

        # 6. Context & AI Engine Status
        ai_layout = QVBoxLayout()
        ai_layout.setSpacing(2)

        self.lbl_active_file = QLabel("📄 Archivo: [Auto-detectar .py]", self)
        self.lbl_active_file.setStyleSheet("font-size: 10px; color: #38bdf8;")
        ai_layout.addWidget(self.lbl_active_file)

        provider_name = getattr(config, "LLM_PROVIDER", "ollama").upper()
        model_name = getattr(config, "LLM_MODEL", "codellama")
        self.lbl_ai_engine = QLabel(f"⚡ Motor IA: {provider_name} ({model_name})", self)
        self.lbl_ai_engine.setStyleSheet("font-size: 10px; color: #a7f3d0;")
        ai_layout.addWidget(self.lbl_ai_engine)

        main_layout.addLayout(ai_layout)

        # 7. File Link Button
        self.btn_link_file = QPushButton("📂 Vincular Archivo .py", self)
        self.btn_link_file.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_link_file.clicked.connect(self._on_link_file_clicked)
        main_layout.addWidget(self.btn_link_file)

        # 8. Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(6)

        self.btn_recalibrate = QPushButton("🎯 Recalibrar", self)
        self.btn_recalibrate.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_recalibrate.clicked.connect(self.recalibrate_requested.emit)
        btn_layout.addWidget(self.btn_recalibrate)

        self.btn_reset = QPushButton("🔄 Reset", self)
        self.btn_reset.setObjectName("btnReset")
        self.btn_reset.setToolTip("Resetear calibración y amortiguación a valores por defecto")
        self.btn_reset.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_reset.clicked.connect(self._on_reset_clicked)
        btn_layout.addWidget(self.btn_reset)

        self.btn_exit = QPushButton("🚨 Salir", self)
        self.btn_exit.setObjectName("btnExit")
        self.btn_exit.setToolTip("Salida inmediata de la aplicación")
        self.btn_exit.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_exit.clicked.connect(self.exit_requested.emit)
        btn_layout.addWidget(self.btn_exit)

        main_layout.addLayout(btn_layout)

        # 9. Emergency Hotkey Documentation Label
        self.lbl_emergency_hint = QLabel("🚨 Emergencia: Ctrl+Alt+Q para salir", self)
        self.lbl_emergency_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_emergency_hint.setStyleSheet("font-size: 10px; font-weight: bold; color: #f87171; padding: 2px;")
        main_layout.addWidget(self.lbl_emergency_hint)

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

    def _on_slider_damping_changed(self, value: int) -> None:
        self.lbl_damping.setText(f"Anti-Temblor (Filtro 1€): Nivel {value}")
        self.anti_jitter_changed.emit(float(value))
        if self.gaze_estimator is not None and hasattr(self.gaze_estimator, "set_anti_jitter_damping"):
            self.gaze_estimator.set_anti_jitter_damping(float(value))

    def _on_reset_clicked(self) -> None:
        """Resets sliders to standard defaults and emits signal."""
        hx = getattr(config, "DEFAULT_HEAD_SENSITIVITY_X", 2.6)
        hy = getattr(config, "DEFAULT_HEAD_SENSITIVITY_Y", 6.8)
        self.slider_sens_x.setValue(int(hx * 10))
        self.slider_sens_y.setValue(int(hy * 10))
        self.slider_damping.setValue(6)
        self.reset_calibration_requested.emit()

    def _on_link_file_clicked(self) -> None:
        """Opens file dialog for user to select an active Python file."""
        initial_dir = getattr(config, "DEFAULT_WORKSPACE_DIR", ".")
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Vincular Archivo Python",
            initial_dir,
            "Python Files (*.py);;All Files (*)",
        )
        if file_path:
            self.set_linked_file(file_path)
            self.file_linked.emit(file_path)

    @pyqtSlot(str)
    def set_linked_file(self, file_path: str) -> None:
        """Updates the active file label."""
        if file_path:
            name = os.path.basename(file_path)
            self.lbl_active_file.setText(f"📄 Archivo: {name}")

    @pyqtSlot(str)
    def update_ai_status(self, status: str) -> None:
        """Updates the AI engine status label."""
        self.lbl_ai_engine.setText(f"⚡ IA: {status}")

    @pyqtSlot(float)
    def update_mar(self, current_mar: float) -> None:
        """Updates the MAR progress bar and style based on threshold."""
        val = max(0.0, min(1.0, current_mar))
        pct = int(val * 100)
        self.mar_bar.setValue(pct)
        self.mar_bar.setFormat(f"MAR: {current_mar:.2f}")
        self.mar_label.setText(f"Nivel MAR: {current_mar:.2f} (Umbral: {config.MAR_THRESHOLD:.2f})")

        # Visual indicator when mouth opens past threshold
        if current_mar >= config.MAR_THRESHOLD:
            self.mar_bar.setStyleSheet("""
                QProgressBar::chunk {
                    background-color: #22c55e;
                }
            """)
        else:
            self.mar_bar.setStyleSheet("""
                QProgressBar::chunk {
                    background-color: #38bdf8;
                }
            """)

    @pyqtSlot(object, float)
    def on_frame_ready(self, frame_or_qimage: Any, current_mar: float) -> None:
        """
        Receives frame and MAR from CameraTracker.
        CRITICAL: Converts numpy ndarray into QImage using .copy() to ensure
        independent memory ownership and prevent Segmentation Faults.
        Computes live FPS and updates tracking stability.
        """
        self.update_mar(current_mar)

        # 1. Real-time FPS Calculation
        now = time.perf_counter()
        if self._last_frame_time is not None:
            dt = now - self._last_frame_time
            if dt > 0.001:
                cur_fps = 1.0 / dt
                self._fps = 0.90 * self._fps + 0.10 * cur_fps
                self.lbl_fps.setText(f"⚡ {self._fps:.1f} FPS")
        self._last_frame_time = now

        # 2. Tracking Stability update from GazeEstimator if attached
        if self.gaze_estimator is not None:
            score = getattr(self.gaze_estimator, "stability_score", 1.0)
            is_fix = getattr(self.gaze_estimator, "is_fixated", True)
            pct = int(score * 100)
            if is_fix:
                self.lbl_stability.setText(f"🟢 Fijación: {pct}%")
                self.lbl_stability.setStyleSheet("font-size: 11px; font-weight: bold; color: #34d399;")
            else:
                self.lbl_stability.setText(f"🟡 Sácada / Ojo")
                self.lbl_stability.setStyleSheet("font-size: 11px; font-weight: bold; color: #fbbf24;")

        if frame_or_qimage is None:
            return

        try:
            if isinstance(frame_or_qimage, QImage):
                qimg = frame_or_qimage.copy()
            elif isinstance(frame_or_qimage, np.ndarray):
                if frame_or_qimage.size == 0:
                    return
                rgb = cv2.cvtColor(frame_or_qimage, cv2.COLOR_BGR2RGB)
                rgb = np.ascontiguousarray(rgb)
                h, w, ch = rgb.shape
                bytes_per_line = ch * w
                # Explicit deep memory copy
                qimg = QImage(rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888).copy()
            else:
                return

            pixmap = QPixmap.fromImage(qimg)
            scaled = pixmap.scaled(
                self.video_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.video_label.setPixmap(scaled)
        except Exception:
            pass
