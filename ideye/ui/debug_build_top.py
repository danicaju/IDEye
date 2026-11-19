"""Debug panel construction: shell, header, camera, MAR and mode selector."""

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


class DebugBuildTopMixin:
    """Debug panel construction: shell, header, camera, MAR and mode selector."""

    def _build_shell(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(14, 14, 14, 14)
        main_layout.setSpacing(10)

        # 1. Dark theme stylesheet (Sleek Cyber-Glass)
        self.setStyleSheet("""
            QWidget#DebugWidget {
                background-color: #0a0f1d;
                border: 1px solid #1e293b;
                border-radius: 14px;
            }
            QWidget {
                background-color: transparent;
                color: #e2e8f0;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QLabel {
                background-color: transparent;
                font-size: 11px;
                color: #94a3b8;
            }
            QProgressBar {
                border: 1px solid #1e293b;
                border-radius: 6px;
                background-color: #081026;
                text-align: center;
                height: 16px;
                font-size: 10px;
                font-weight: bold;
                color: #f8fafc;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0e7490, stop:1 #22d3ee);
                border-radius: 5px;
            }
            QSlider::groove:horizontal {
                height: 6px;
                background: #081026;
                border: 1px solid #1e293b;
                border-radius: 3px;
            }
            QSlider::sub-page:horizontal {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0e7490, stop:1 #22d3ee);
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #22d3ee;
                border: 1px solid #93c5fd;
                width: 14px;
                margin-top: -4px;
                margin-bottom: -4px;
                border-radius: 7px;
            }
            QSlider::handle:horizontal:hover {
                background: #60a5fa;
            }
            QPushButton {
                background-color: rgba(30, 41, 59, 0.6);
                border: 1px solid #1e293b;
                border-radius: 8px;
                padding: 6px 10px;
                font-size: 11px;
                font-weight: 600;
                color: #e2e8f0;
            }
            QPushButton:hover {
                background-color: rgba(37, 99, 235, 0.2);
                border-color: #22d3ee;
                color: #ffffff;
            }
            QPushButton:pressed {
                background-color: #081026;
            }
            QPushButton#btnReset {
                background-color: rgba(37, 99, 235, 0.22);
                border: 1px solid #0e7490;
                color: #93c5fd;
            }
            QPushButton#btnReset:hover {
                background-color: rgba(37, 99, 235, 0.42);
                border-color: #22d3ee;
                color: #ffffff;
            }
            QPushButton#btnExit {
                background-color: rgba(239, 68, 68, 0.18);
                border: 1px solid rgba(239, 68, 68, 0.55);
                color: #fca5a5;
            }
            QPushButton#btnExit:hover {
                background-color: rgba(239, 68, 68, 0.38);
                border-color: #ef4444;
                color: #ffffff;
            }
            QFrame#cardFrame {
                background-color: rgba(10, 15, 29, 0.85);
                border: 1px solid #1e293b;
                border-radius: 14px;
                padding: 6px;
            }
        """)
        return main_layout

    def _build_header(self, main_layout):
        # 2. Top Stats Header: Live FPS Meter & Stability Indicator & Collapse Button
        stats_layout = QVBoxLayout()
        stats_layout.setSpacing(4)
        stats_row = QHBoxLayout()
        stats_row.setSpacing(8)
        state_row = QHBoxLayout()
        state_row.setSpacing(12)

        self.lbl_fps = QLabel("30.0 FPS", self)
        self.lbl_fps.setStyleSheet("font-size: 11px; font-weight: bold; color: #22d3ee;")
        stats_row.addWidget(self.lbl_fps, alignment=Qt.AlignmentFlag.AlignLeft)
        self.lbl_power_state = QLabel("Activo", self)
        self.lbl_power_state.setStyleSheet("font-size: 10px; font-weight: bold; color: #22d3ee;")
        stats_row.addWidget(self.lbl_power_state, alignment=Qt.AlignmentFlag.AlignLeft)
        stats_row.addStretch(1)

        self.lbl_stability = QLabel("Fijación", self)
        self.lbl_stability.setStyleSheet("font-size: 11px; font-weight: bold; color: #34d399;")
        state_row.addWidget(self.lbl_stability, alignment=Qt.AlignmentFlag.AlignLeft)

        self.lbl_lighting = QLabel("Luz: OK", self)
        self.lbl_lighting.setStyleSheet("font-size: 10px; font-weight: bold; color: #fbbf24;")
        state_row.addWidget(self.lbl_lighting, alignment=Qt.AlignmentFlag.AlignLeft)
        state_row.addStretch(1)

        self.btn_collapse = QPushButton("Colapsar", self)
        self.btn_collapse.setObjectName("btnCollapse")
        self.btn_collapse.setStyleSheet("""
            QPushButton#btnCollapse {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 2px 6px;
                font-size: 10px;
                color: #94a3b8;
            }
            QPushButton#btnCollapse:hover {
                background-color: #334155;
                color: #f8fafc;
            }
        """)
        self.btn_collapse.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_collapse.setToolTip("Reduce el panel a una barra compacta")
        self.btn_collapse.clicked.connect(self.toggle_collapse)
        self.btn_collapse.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        stats_row.addWidget(self.btn_collapse, alignment=Qt.AlignmentFlag.AlignRight)

        stats_layout.addLayout(stats_row)
        stats_layout.addLayout(state_row)
        main_layout.addLayout(stats_layout)

    def _build_content_and_camera(self):
        # Collapsible content container
        self.content_container = QWidget(self)
        content_layout = QVBoxLayout(self.content_container)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(6)

        # 3. Camera Feed Thumbnail
        self.video_label = QLabel(self)
        self.video_label.setFixedSize(config.DEBUG_FEED_WIDTH, config.DEBUG_FEED_HEIGHT)
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setStyleSheet("background-color: #081026; border: 1px solid #1e293b; border-radius: 14px;")
        self.video_label.setText("Iniciando cámara...")
        content_layout.addWidget(self.video_label, alignment=Qt.AlignmentFlag.AlignCenter)
        return content_layout

    def _build_mar_and_mode(self, content_layout):
        # 4. MAR Progress Bar and Text
        mar_layout = QVBoxLayout()
        mar_layout.setSpacing(2)

        self.mar_label = QLabel(f"Nivel MAR: 0.00 (Umbral: {self.mar_threshold:.2f})", self)
        mar_layout.addWidget(self.mar_label)

        self.mar_bar = QProgressBar(self)
        self.mar_bar.setRange(0, 100)
        self.mar_bar.setValue(0)
        self.mar_bar.setTextVisible(True)
        mar_layout.addWidget(self.mar_bar)

        self.lbl_mar_threshold = QLabel(f"Umbral MAR: {self.mar_threshold:.2f}", self)
        self.lbl_mar_threshold.setStyleSheet("font-size: 10px; color: #fbbf24;")
        mar_layout.addWidget(self.lbl_mar_threshold)
        self.slider_mar_threshold = QSlider(Qt.Orientation.Horizontal, self)
        self.slider_mar_threshold.setRange(25, 70)
        self.slider_mar_threshold.setValue(int(round(self.mar_threshold * 100)))
        self.slider_mar_threshold.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.slider_mar_threshold.valueChanged.connect(self._on_slider_mar_changed)
        mar_layout.addWidget(self.slider_mar_threshold)

        content_layout.addLayout(mar_layout)

        # 5. Tracking Mode Selector Frame (Pure Iris / Hybrid / Head Primary)
        mode_frame = QFrame(self)
        mode_frame.setObjectName("cardFrame")
        mode_layout = QVBoxLayout(mode_frame)
        mode_layout.setContentsMargins(6, 6, 6, 6)
        mode_layout.setSpacing(4)

        lbl_mode = QLabel("MODO DE SEGUIMIENTO (Ctrl+Alt+T)", mode_frame)
        lbl_mode.setStyleSheet("font-size: 10px; font-weight: bold; color: #22d3ee;")
        mode_layout.addWidget(lbl_mode)

        # Live segmented quick-toggle buttons
        btn_mode_layout = QHBoxLayout()
        btn_mode_layout.setSpacing(4)

        self.btn_mode_iris = QPushButton("Solo Iris", mode_frame)
        self.btn_mode_iris.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_mode_iris.setToolTip("Modo Solo Iris: Alcance horizontal total solo con los ojos")
        self.btn_mode_iris.clicked.connect(lambda: self.set_tracking_mode_by_name("PURE_IRIS"))
        btn_mode_layout.addWidget(self.btn_mode_iris)

        self.btn_mode_hybrid = QPushButton("Híbrido", mode_frame)
        self.btn_mode_hybrid.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_mode_hybrid.setToolTip("Modo Híbrido: Fusión Cabeza + Iris con compensación RVO")
        self.btn_mode_hybrid.clicked.connect(lambda: self.set_tracking_mode_by_name("HYBRID"))
        btn_mode_layout.addWidget(self.btn_mode_hybrid)

        self.btn_mode_head = QPushButton("Cabeza", mode_frame)
        self.btn_mode_head.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_mode_head.setToolTip("Modo Solo Cabeza: Control por orientación de cabeza (Recomendado)")
        self.btn_mode_head.clicked.connect(lambda: self.set_tracking_mode_by_name("HEAD_PRIMARY"))
        btn_mode_layout.addWidget(self.btn_mode_head)

        mode_layout.addLayout(btn_mode_layout)

        self.combo_mode = QComboBox(mode_frame)
        self.combo_mode.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.combo_mode.addItem("Solo Iris", "PURE_IRIS")
        self.combo_mode.addItem("Híbrido (Cabeza + Iris)", "HYBRID")
        self.combo_mode.addItem("Solo Cabeza (Recomendado)", "HEAD_PRIMARY")
        self.combo_mode.setStyleSheet("""
            QComboBox {
                background-color: transparent;
                border: none;
                padding: 2px 0px;
                font-size: 11px;
                font-weight: 600;
                color: #94a3b8;
            }
            QComboBox::drop-down {
                border: none;
                width: 0px;
            }
            QComboBox QAbstractItemView {
                background-color: #0a0f1d;
                color: #f8fafc;
                selection-background-color: #0e7490;
                selection-color: #ffffff;
                border: 1px solid #1e293b;
            }
        """)
        self.combo_mode.currentIndexChanged.connect(self._on_combo_mode_changed)
        mode_layout.addWidget(self.combo_mode)
        content_layout.addWidget(mode_frame)
