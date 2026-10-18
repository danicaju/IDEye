"""
Debug & Monitor Widget for EyeDE (Phase 2)
Compact floating window displaying live webcam feed, MAR meter, and controls.

Features:
- Video preview thumbnail with landmark annotations.
- Memory-safe frame conversion (.copy()) preventing dangling pointer segfaults.
- Real-time MAR (Mouth Aspect Ratio) meter with threshold indicator.
- 'Recalibrar' button to trigger 5-point calibration sequence.
- 'Salir' button to request graceful application termination.
"""

import os
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
)

try:
    import eyede.config as config
except ImportError:
    import config


class DebugWidget(QWidget):
    """
    Compact floating debug & monitor window for EyeDE.
    """

    recalibrate_requested = pyqtSignal()
    exit_requested = pyqtSignal()
    file_linked = pyqtSignal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self.setWindowTitle("EyeDE - Monitor y Depuración")
        self.setFixedSize(config.DEBUG_WINDOW_WIDTH, config.DEBUG_WINDOW_HEIGHT)
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Constructs UI layout, styles, and controls."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(8)

        # 1. Dark theme stylesheet
        self.setStyleSheet("""
            QWidget {
                background-color: #16181f;
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
                background-color: #0f172a;
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
            QPushButton {
                background-color: #1e293b;
                border: 1px solid #475569;
                border-radius: 5px;
                padding: 6px 12px;
                font-size: 11px;
                font-weight: 600;
                color: #f1f5f9;
            }
            QPushButton:hover {
                background-color: #334155;
                border-color: #64748b;
            }
            QPushButton:pressed {
                background-color: #0f172a;
            }
            QPushButton#btnExit {
                background-color: #7f1d1d;
                border-color: #991b1b;
            }
            QPushButton#btnExit:hover {
                background-color: #991b1b;
            }
        """)

        # 2. Camera Feed Thumbnail
        self.video_label = QLabel(self)
        self.video_label.setFixedSize(config.DEBUG_FEED_WIDTH, config.DEBUG_FEED_HEIGHT)
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setStyleSheet("background-color: #0b0f19; border: 1px solid #1e293b; border-radius: 6px;")
        self.video_label.setText("Iniciando cámara...")
        main_layout.addWidget(self.video_label, alignment=Qt.AlignmentFlag.AlignCenter)

        # 3. MAR Progress Bar and Text
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

        # 4. Context & AI Engine Status
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

        # 5. File Link Button
        self.btn_link_file = QPushButton("📂 Vincular Archivo .py", self)
        self.btn_link_file.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_link_file.clicked.connect(self._on_link_file_clicked)
        main_layout.addWidget(self.btn_link_file)

        # 6. Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self.btn_recalibrate = QPushButton("🎯 Recalibrar", self)
        self.btn_recalibrate.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_recalibrate.clicked.connect(self.recalibrate_requested.emit)
        btn_layout.addWidget(self.btn_recalibrate)

        self.btn_exit = QPushButton("❌ Salir", self)
        self.btn_exit.setObjectName("btnExit")
        self.btn_exit.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_exit.clicked.connect(self.exit_requested.emit)
        btn_layout.addWidget(self.btn_exit)

        main_layout.addLayout(btn_layout)

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
        """
        self.update_mar(current_mar)

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
