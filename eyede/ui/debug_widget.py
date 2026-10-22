"""
Debug & Monitor Widget for IDEye (Phase 2 & Overhaul)
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
    QComboBox,
    QScrollArea,
    QSizePolicy,
)

try:
    import eyede.config as config
    from eyede.ui.icon_manager import IconManager
    from eyede.actions.language_support import (
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


class DebugWidget(QWidget):
    """
    Compact floating debug & monitor window for IDEye with interactive tuning controls.
    """

    recalibrate_requested = pyqtSignal()
    reset_calibration_requested = pyqtSignal()
    exit_requested = pyqtSignal()
    file_linked = pyqtSignal(str)
    sensitivity_x_changed = pyqtSignal(float)
    sensitivity_y_changed = pyqtSignal(float)
    anti_jitter_changed = pyqtSignal(float)
    tracking_mode_changed = pyqtSignal(str)
    adaptive_ast_toggled = pyqtSignal(bool)
    collapsed_toggled = pyqtSignal(bool)
    visibility_changed = pyqtSignal(bool)
    language_changed = pyqtSignal(str)
    mar_threshold_changed = pyqtSignal(float)
    macro_editor_requested = pyqtSignal()
    telemetry_reset_requested = pyqtSignal()
    test_sound_requested = pyqtSignal()
    open_guide_requested = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None, gaze_estimator: Optional[Any] = None):
        super().__init__(parent)

        self.setObjectName("DebugWidget")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.gaze_estimator = gaze_estimator
        self._last_frame_time: Optional[float] = None
        self._fps: float = 30.0

        self.setWindowTitle("IDEye - Monitor y Depuración")
        app_icon = IconManager.instance().get_app_icon()
        if not app_icon.isNull():
            self.setWindowIcon(app_icon)
        self.setFixedSize(config.DEBUG_WINDOW_WIDTH, config.DEBUG_WINDOW_HEIGHT)
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.adaptive_ast_enabled: bool = getattr(config, "ENABLE_ADAPTIVE_AST_MENUS", True)
        self.mar_threshold: float = float(getattr(config, "MAR_THRESHOLD", 0.45))
        self._last_mar: float = 0.0
        self.is_collapsed: bool = False
        self.current_language: str = getattr(config, "DEFAULT_PROGRAMMING_LANGUAGE", "PYTHON")
        self.is_vscode_connected: bool = False
        self._setup_ui()

        # Global Ctrl+Alt+T/A/L bindings live in GlobalHotkeyManager.

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.visibility_changed.emit(True)

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        self.visibility_changed.emit(False)

    def set_gaze_estimator(self, estimator: Any) -> None:
        """Links the GazeEstimator instance for direct real-time parameter tuning."""
        self.gaze_estimator = estimator
        if estimator is not None:
            # Sync slider positions with estimator
            hx = getattr(estimator, "head_sensitivity_x", config.DEFAULT_HEAD_SENSITIVITY_X)
            hy = getattr(estimator, "head_sensitivity_y", config.DEFAULT_HEAD_SENSITIVITY_Y)
            self.slider_sens_x.setValue(int(hx * 10))
            self.slider_sens_y.setValue(int(hy * 10))

            # Sync tracking mode
            mode = getattr(estimator, "tracking_mode", "PURE_IRIS")
            self._update_mode_ui(mode)

    def _setup_ui(self) -> None:
        """Constructs UI layout, styles, and controls."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(14, 14, 14, 14)
        main_layout.setSpacing(10)

        # 1. Dark theme stylesheet
        self.setStyleSheet("""
            QWidget#DebugWidget {
                background-color: #0b0f19;
                border: 1px solid rgba(255, 255, 255, 28);
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
                border: 1px solid rgba(255, 255, 255, 28);
                border-radius: 5px;
                background-color: #070a12;
                text-align: center;
                height: 16px;
                font-size: 10px;
                font-weight: bold;
                color: #f8fafc;
            }
            QProgressBar::chunk {
                background-color: #22d3ee;
                border-radius: 4px;
            }
            QSlider::groove:horizontal {
                height: 6px;
                background: #111827;
                border: 1px solid rgba(255, 255, 255, 24);
                border-radius: 3px;
            }
            QSlider::sub-page:horizontal {
                background: #0891b2;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #67e8f9;
                border: 1px solid #ecfeff;
                width: 14px;
                margin-top: -4px;
                margin-bottom: -4px;
                border-radius: 7px;
            }
            QSlider::handle:horizontal:hover {
                background: #a5f3fc;
            }
            QPushButton {
                background-color: rgba(255, 255, 255, 8);
                border: 1px solid rgba(255, 255, 255, 32);
                border-radius: 7px;
                padding: 6px 10px;
                font-size: 11px;
                font-weight: 600;
                color: #e2e8f0;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 16);
                border-color: rgba(255, 255, 255, 55);
            }
            QPushButton:pressed {
                background-color: #070a12;
            }
            QPushButton#btnReset {
                background-color: rgba(14, 165, 233, 34);
                border-color: rgba(56, 189, 248, 120);
            }
            QPushButton#btnReset:hover {
                background-color: rgba(14, 165, 233, 60);
            }
            QPushButton#btnExit {
                background-color: rgba(239, 68, 68, 30);
                border-color: rgba(239, 68, 68, 110);
            }
            QPushButton#btnExit:hover {
                background-color: rgba(239, 68, 68, 58);
            }
            QFrame#cardFrame {
                background-color: rgba(15, 23, 42, 170);
                border: 1px solid rgba(255, 255, 255, 22);
                border-radius: 10px;
                padding: 6px;
            }
        """)

        # 2. Top Stats Header: Live FPS Meter & Stability Indicator & Collapse Button
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(8)

        self.lbl_fps = QLabel("30.0 FPS", self)
        self.lbl_fps.setStyleSheet("font-size: 11px; font-weight: bold; color: #38bdf8;")
        stats_layout.addWidget(self.lbl_fps, alignment=Qt.AlignmentFlag.AlignLeft)

        self.lbl_stability = QLabel("100% Fijación", self)
        self.lbl_stability.setStyleSheet("font-size: 11px; font-weight: bold; color: #34d399;")
        stats_layout.addWidget(self.lbl_stability, alignment=Qt.AlignmentFlag.AlignHCenter)

        self.btn_collapse = QPushButton("▲ Colapsar", self)
        self.btn_collapse.setObjectName("btnCollapse")
        self.btn_collapse.setStyleSheet("""
            QPushButton#btnCollapse {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 4px;
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
        self.btn_collapse.setToolTip("Alternar modo barra compacta")
        self.btn_collapse.clicked.connect(self.toggle_collapse)
        stats_layout.addWidget(self.btn_collapse, alignment=Qt.AlignmentFlag.AlignRight)

        main_layout.addLayout(stats_layout)

        # Collapsible content container
        self.content_container = QWidget(self)
        content_layout = QVBoxLayout(self.content_container)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(6)

        # 3. Camera Feed Thumbnail
        self.video_label = QLabel(self)
        self.video_label.setFixedSize(config.DEBUG_FEED_WIDTH, config.DEBUG_FEED_HEIGHT)
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setStyleSheet("background-color: #070a12; border: 1px solid #1e293b; border-radius: 6px;")
        self.video_label.setText("Iniciando cámara...")
        content_layout.addWidget(self.video_label, alignment=Qt.AlignmentFlag.AlignCenter)

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
        lbl_mode.setStyleSheet("font-size: 10px; font-weight: bold; color: #38bdf8;")
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
                background-color: #1e293b;
                border: 1px solid #38bdf8;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 11px;
                font-weight: 600;
                color: #f8fafc;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox QAbstractItemView {
                background-color: #0f172a;
                color: #f8fafc;
                selection-background-color: #0284c7;
                selection-color: #ffffff;
                border: 1px solid #334155;
            }
        """)
        self.combo_mode.currentIndexChanged.connect(self._on_combo_mode_changed)
        mode_layout.addWidget(self.combo_mode)
        content_layout.addWidget(mode_frame)

        # 6. Interactive Tuning Sliders Frame
        slider_frame = QFrame(self)
        slider_frame.setObjectName("cardFrame")
        slider_layout = QVBoxLayout(slider_frame)
        slider_layout.setContentsMargins(6, 6, 6, 6)
        slider_layout.setSpacing(4)

        lbl_section = QLabel("CONTROLES DE SENSIBILIDAD Y TEMBLOR", slider_frame)
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
        sens_y_val = getattr(config, "DEFAULT_HEAD_SENSITIVITY_Y", 3.0)
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

        content_layout.addWidget(slider_frame)
        content_layout.addWidget(self._build_telemetry_card())

        # Dedicated In-App Gesture & Shortcut Reference Card
        guide_frame = QFrame(self)
        guide_frame.setObjectName("cardFrame")
        guide_layout = QVBoxLayout(guide_frame)
        guide_layout.setContentsMargins(8, 8, 8, 8)
        guide_layout.setSpacing(4)

        lbl_guide_title = QLabel("GUÍA DE GESTOS Y ATAJOS", guide_frame)
        lbl_guide_title.setStyleSheet("font-size: 11px; font-weight: bold; color: #38bdf8;")
        lbl_guide_title.setWordWrap(True)
        lbl_guide_title.setMinimumWidth(0)
        guide_layout.addWidget(lbl_guide_title)

        guide_content = QLabel(guide_frame)
        guide_content.setTextFormat(Qt.TextFormat.RichText)
        guide_content.setStyleSheet("font-size: 10px; color: #cbd5e1;")
        guide_content.setWordWrap(True)
        guide_content.setMinimumWidth(0)
        guide_content.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.MinimumExpanding)
        guide_content.setText(
            "<div style='line-height: 145%;'>"
            "<div style='color: #7dd3fc; font-weight: bold;'>GESTOS:</div>"
            "<div>• <b>Abrir boca:</b> clic o inyectar.</div>"
            "<div>• <b>Guiño derecho:</b> pausar o despertar.</div>"
            "<div>• <b>Guiño izquierdo:</b> volver o deshacer.</div>"
            "<div>&nbsp;</div>"
            "<div>• Ctrl+Alt+A menús &nbsp;·&nbsp; Ctrl+Alt+T tracking</div>"
            "<div>• Ctrl+Alt+V modos &nbsp;·&nbsp; Ctrl+Alt+K auto</div>"
            "<div>• Ctrl+Alt+S sonido &nbsp;·&nbsp; Ctrl+Alt+F FreeLook</div>"
            "<div>• Ctrl+Alt+G gaming &nbsp;·&nbsp; Ctrl+Alt+B portapapeles</div>"
            "<div>• Ctrl+Alt+M monitor &nbsp;·&nbsp; Ctrl+Alt+N pantalla</div>"
            "<div>• Ctrl+Alt+L lenguaje &nbsp;·&nbsp; Ctrl+Alt+H ayuda</div>"
            "<div>• Ctrl+Alt+P pausa &nbsp;·&nbsp; Ctrl+Alt+Q salir</div>"
            "<div style='color: #7dd3fc; font-weight: bold; margin-top: 4px;'>ATAJOS:</div>"
            "</div>"
        )
        self.guide_content = guide_content
        guide_layout.addWidget(guide_content)
        for label in guide_frame.findChildren(QLabel):
            label.setWordWrap(True)
            label.setMinimumWidth(0)
            label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        content_layout.addWidget(guide_frame)

        self.btn_open_guide = QPushButton("📖 Abrir Manual Interactivo", self)
        self.btn_open_guide.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_open_guide.setToolTip("Abre la gu?a visual interactiva completa en el navegador")
        self.btn_open_guide.setStyleSheet(
            "QPushButton { background-color: #4c1d95; color: #f5f3ff; border: 1px solid #a78bfa; "
            "border-radius: 7px; padding: 8px 10px; font-weight: bold; }"
            "QPushButton:hover { background-color: #6d28d9; }"
        )
        self.btn_open_guide.clicked.connect(self.open_guide_requested.emit)
        content_layout.addWidget(self.btn_open_guide)

        # 7. Language Selector & VS Code WebSocket Bridge Status
        lang_bridge_frame = QFrame(self)
        lang_bridge_frame.setObjectName("cardFrame")
        lang_bridge_layout = QVBoxLayout(lang_bridge_frame)
        lang_bridge_layout.setContentsMargins(6, 6, 6, 6)
        lang_bridge_layout.setSpacing(4)

        lbl_lang_section = QLabel("LENGUAJE ACTIVO Y PUENTE VS CODE (Ctrl+Alt+L)", lang_bridge_frame)
        lbl_lang_section.setStyleSheet("font-size: 10px; font-weight: bold; color: #38bdf8;")
        lang_bridge_layout.addWidget(lbl_lang_section)

        lang_row = QHBoxLayout()
        lang_row.setSpacing(6)

        self.combo_language = QComboBox(lang_bridge_frame)
        self.combo_language.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.combo_language.addItem("Python [PY]", LANG_PYTHON)
        self.combo_language.addItem("TypeScript / JS [TS]", LANG_TYPESCRIPT)
        self.combo_language.addItem("Rust [RS]", LANG_RUST)
        self.combo_language.addItem("C / C++ [C++]", LANG_CPP)
        self.combo_language.addItem("Go [GO]", LANG_GO)
        self.combo_language.setStyleSheet("""
            QComboBox {
                background-color: #1e293b;
                border: 1px solid #0284c7;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 11px;
                font-weight: 600;
                color: #f8fafc;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox QAbstractItemView {
                background-color: #0f172a;
                color: #f8fafc;
                selection-background-color: #0284c7;
                selection-color: #ffffff;
                border: 1px solid #334155;
            }
        """)
        self.combo_language.currentIndexChanged.connect(self._on_combo_language_changed)
        lang_row.addWidget(self.combo_language, stretch=3)

        self.lbl_vscode_status = QLabel("VS Code: Desconectado", lang_bridge_frame)
        self.lbl_vscode_status.setStyleSheet("font-size: 10px; font-weight: bold; color: #94a3b8; padding: 3px 6px; border: 1px solid #334155; border-radius: 4px; background: #0f172a;")
        self.lbl_vscode_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lang_row.addWidget(self.lbl_vscode_status, stretch=3)

        lang_bridge_layout.addLayout(lang_row)
        content_layout.addWidget(lang_bridge_frame)

        # 8. Context & AI Engine Status
        ai_layout = QVBoxLayout()
        ai_layout.setSpacing(2)

        self.lbl_active_file = QLabel("Archivo: detección automática", self)
        self.lbl_active_file.setStyleSheet("font-size: 10px; color: #38bdf8;")
        ai_layout.addWidget(self.lbl_active_file)

        provider_name = getattr(config, "LLM_PROVIDER", "ollama").upper()
        model_name = getattr(config, "LLM_MODEL", "codellama")
        self.lbl_ai_engine = QLabel(f"Sugerencias: {provider_name} ({model_name})", self)
        self.lbl_ai_engine.setStyleSheet("font-size: 10px; color: #a7f3d0;")
        ai_layout.addWidget(self.lbl_ai_engine)

        self.lbl_ast_context = QLabel("Contexto: general", self)
        self.lbl_ast_context.setStyleSheet("font-size: 10px; font-weight: bold; color: #f472b6;")
        ai_layout.addWidget(self.lbl_ast_context)

        content_layout.addLayout(ai_layout)

        # 9. File Link & Adaptive AST Toggle Buttons
        link_adaptive_layout = QHBoxLayout()
        link_adaptive_layout.setSpacing(6)

        self.btn_link_file = QPushButton("Vincular Código", self)
        self.btn_link_file.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_link_file.clicked.connect(self._on_link_file_clicked)
        link_adaptive_layout.addWidget(self.btn_link_file)

        self.btn_toggle_adaptive = QPushButton("Menús inteligentes: ON [Ctrl+Alt+A]", self)
        self.btn_toggle_adaptive.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_toggle_adaptive.setToolTip("Alternar menús contextuales adaptativos según AST (Atajo: Ctrl+Alt+A)")
        self.btn_toggle_adaptive.clicked.connect(self.toggle_adaptive_ast)
        link_adaptive_layout.addWidget(self.btn_toggle_adaptive)

        content_layout.addLayout(link_adaptive_layout)

        self.btn_macro_editor = QPushButton("Editor de Macros", self)
        self.btn_macro_editor.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_macro_editor.setToolTip("Editar las 9 celdas de cualquier modo")
        self.btn_macro_editor.clicked.connect(self.macro_editor_requested.emit)
        content_layout.addWidget(self.btn_macro_editor)

        # 9. Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(6)

        self.btn_recalibrate = QPushButton("Recalibrar", self)
        self.btn_recalibrate.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_recalibrate.clicked.connect(self.recalibrate_requested.emit)
        btn_layout.addWidget(self.btn_recalibrate)

        self.btn_reset = QPushButton("Reset", self)
        self.btn_reset.setObjectName("btnReset")
        self.btn_reset.setToolTip("Resetear calibración y amortiguación a valores por defecto")
        self.btn_reset.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_reset.clicked.connect(self._on_reset_clicked)
        btn_layout.addWidget(self.btn_reset)

        self.btn_exit = QPushButton("Salir", self)
        self.btn_exit.setObjectName("btnExit")
        self.btn_exit.setToolTip("Salida inmediata de la aplicación")
        self.btn_exit.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_exit.clicked.connect(self.exit_requested.emit)
        btn_layout.addWidget(self.btn_exit)

        content_layout.addLayout(btn_layout)

        # Decorate buttons and window with neon vector icons
        icon_mgr = IconManager.instance()
        logo_icon = icon_mgr.get_icon("eyede_logo", 32)
        if not logo_icon.isNull():
            self.setWindowIcon(logo_icon)

        exit_icon = icon_mgr.get_icon("exit", 16)
        if not exit_icon.isNull():
            self.btn_exit.setIcon(exit_icon)

        recalib_icon = icon_mgr.get_icon("navigation", 16)
        if not recalib_icon.isNull():
            self.btn_recalibrate.setIcon(recalib_icon)

        reset_icon = icon_mgr.get_icon("flow", 16)
        if not reset_icon.isNull():
            self.btn_reset.setIcon(reset_icon)

        link_icon = icon_mgr.get_icon("function", 16)
        if not link_icon.isNull():
            self.btn_link_file.setIcon(link_icon)

        spark_icon = icon_mgr.get_icon("ai_spark", 16)
        if not spark_icon.isNull():
            self.btn_toggle_adaptive.setIcon(spark_icon)

        macro_icon = icon_mgr.get_icon("edit", 16)
        if not macro_icon.isNull():
            self.btn_macro_editor.setIcon(macro_icon)

        # 9b. Audio verification button.
        self.btn_test_sound = QPushButton("🔊 Probar sonido", self)
        self.btn_test_sound.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_test_sound.setToolTip("Reproduce un clic de prueba con el motor de audio actual")
        self.btn_test_sound.setStyleSheet(
            "QPushButton { background-color: #0e7490; color: #ecfeff; border: 1px solid #22d3ee; "
            "border-radius: 6px; padding: 6px 10px; font-weight: bold; }"
            "QPushButton:hover { background-color: #0891b2; }"
        )
        self.btn_test_sound.clicked.connect(self.test_sound_requested.emit)
        content_layout.addWidget(self.btn_test_sound)

        # 10. Emergency Hotkey Documentation Label
        self.lbl_emergency_hint = QLabel("Emergencia: Ctrl+Alt+Q para salir", self)
        self.lbl_emergency_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_emergency_hint.setStyleSheet("font-size: 10px; font-weight: bold; color: #f87171; padding: 2px;")
        content_layout.addWidget(self.lbl_emergency_hint)

        self.content_scroll = QScrollArea(self)
        self.content_scroll.setWidgetResizable(True)
        self.content_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.content_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.content_scroll.setWidget(self.content_container)
        main_layout.addWidget(self.content_scroll)

        self._update_mode_ui("PURE_IRIS")
        self._update_adaptive_ui()

    def toggle_collapse(self) -> None:
        """Toggles between expanded monitor window and sleek mini-bar mode."""
        self.is_collapsed = not getattr(self, "is_collapsed", False)
        if self.is_collapsed:
            self.content_container.hide()
            self.content_scroll.hide()
            self.setFixedHeight(48)
            self.btn_collapse.setText("▼ Expandir")
            self.btn_collapse.setToolTip("Expandir monitor de depuración")
        else:
            self.content_container.show()
            self.content_scroll.show()
            self.setFixedSize(config.DEBUG_WINDOW_WIDTH, config.DEBUG_WINDOW_HEIGHT)
            self.btn_collapse.setText("▲ Colapsar")
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

    @pyqtSlot(str)
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
                    background-color: #38bdf8;
                }
            """)

    def _build_telemetry_card(self) -> QFrame:
        frame = QFrame(self)
        frame.setObjectName("cardFrame")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(3)

        title = QLabel("MÉTRICAS DE EFICIENCIA (LOOK-TO-CODE)", frame)
        title.setStyleSheet("font-size: 11px; font-weight: bold; color: #34d399;")
        layout.addWidget(title)

        self.lbl_telemetry_saved = QLabel("Ahorro Físico: 0 teclas (0% menos esfuerzo)", frame)
        self.lbl_telemetry_saved.setStyleSheet("font-size: 10px; color: #d1fae5;")
        self.lbl_telemetry_saved.setWordWrap(True)
        self.lbl_telemetry_saved.setMinimumWidth(0)
        self.lbl_telemetry_saved.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        layout.addWidget(self.lbl_telemetry_saved)

        self.lbl_telemetry_injected = QLabel("Inyectado: 0 chars en 0 clics", frame)
        self.lbl_telemetry_injected.setStyleSheet("font-size: 10px; color: #bae6fd;")
        self.lbl_telemetry_injected.setWordWrap(True)
        self.lbl_telemetry_injected.setMinimumWidth(0)
        self.lbl_telemetry_injected.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        layout.addWidget(self.lbl_telemetry_injected)

        self.lbl_foreground = QLabel("Ventana activa: —", frame)
        self.lbl_foreground.setStyleSheet("font-size: 9px; color: #94a3b8;")
        self.lbl_foreground.setWordWrap(True)
        self.lbl_foreground.setMinimumWidth(0)
        self.lbl_foreground.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        layout.addWidget(self.lbl_foreground)

        reset = QPushButton("Reset métricas", frame)
        reset.setFocusPolicy(Qt.FocusPolicy.NoFocus)
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
                self.lbl_fps.setText(f"{self._fps:.1f} FPS")
        self._last_frame_time = now

        # 2. Tracking Stability update from GazeEstimator if attached
        if self.gaze_estimator is not None:
            score = getattr(self.gaze_estimator, "stability_score", 1.0)
            is_fix = getattr(self.gaze_estimator, "is_fixated", True)
            pct = int(score * 100)
            if is_fix:
                self.lbl_stability.setText(f"Fijación: {pct}%")
                self.lbl_stability.setStyleSheet("font-size: 11px; font-weight: bold; color: #34d399;")
            else:
                self.lbl_stability.setText("Sácada / Movimiento")
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

    @property
    def current_tracking_mode(self) -> str:
        """Returns the currently selected tracking mode string."""
        return self.combo_mode.currentData() or "PURE_IRIS"

    def _update_mode_ui(self, mode: str) -> None:
        """Synchronizes combo and segmented buttons to reflect active mode."""
        idx = self.combo_mode.findData(mode)
        if idx >= 0 and self.combo_mode.currentIndex() != idx:
            self.combo_mode.blockSignals(True)
            self.combo_mode.setCurrentIndex(idx)
            self.combo_mode.blockSignals(False)

        style_active = """
            QPushButton {
                background-color: #0284c7;
                border: 1px solid #38bdf8;
                border-radius: 4px;
                padding: 4px 6px;
                font-size: 10px;
                font-weight: bold;
                color: #ffffff;
            }
        """
        style_inactive = """
            QPushButton {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 4px;
                padding: 4px 6px;
                font-size: 10px;
                font-weight: 500;
                color: #94a3b8;
            }
            QPushButton:hover {
                background-color: #334155;
                color: #f8fafc;
            }
        """
        if hasattr(self, "btn_mode_iris"):
            self.btn_mode_iris.setStyleSheet(style_active if mode == "PURE_IRIS" else style_inactive)
        if hasattr(self, "btn_mode_hybrid"):
            self.btn_mode_hybrid.setStyleSheet(style_active if mode == "HYBRID" else style_inactive)
        if hasattr(self, "btn_mode_head"):
            self.btn_mode_head.setStyleSheet(style_active if mode == "HEAD_PRIMARY" else style_inactive)

    def set_tracking_mode_by_name(self, mode: str) -> None:
        """Sets the active tracking mode via button or programmatic invocation."""
        mode_upper = str(mode).upper()
        if mode_upper in ("PURE_IRIS", "HYBRID", "HEAD_PRIMARY"):
            self._update_mode_ui(mode_upper)
            self.tracking_mode_changed.emit(mode_upper)
            if self.gaze_estimator is not None:
                self.gaze_estimator.set_tracking_mode(mode_upper)

    def _on_combo_mode_changed(self, index: int) -> None:
        """Handles user selecting a different tracking mode in the combo box."""
        mode = self.combo_mode.currentData()
        if mode:
            self._update_mode_ui(mode)
            self.tracking_mode_changed.emit(mode)
            if self.gaze_estimator is not None:
                self.gaze_estimator.set_tracking_mode(mode)

    def cycle_tracking_mode(self) -> None:
        """Cycles to the next tracking mode (shortcut [T])."""
        idx = (self.combo_mode.currentIndex() + 1) % self.combo_mode.count()
        self.combo_mode.setCurrentIndex(idx)

    def keyPressEvent(self, event) -> None:
        """Keyboard event handler for shortcuts [T] (Tracking), [A] (AST), and [L] (Language)."""
        if event.key() == Qt.Key.Key_T:
            self.cycle_tracking_mode()
            event.accept()
        elif event.key() == Qt.Key.Key_A:
            self.toggle_adaptive_ast()
            event.accept()
        elif event.key() == Qt.Key.Key_L:
            self.cycle_language()
            event.accept()
        else:
            super().keyPressEvent(event)

    @pyqtSlot(str)
    def set_language(self, lang: str) -> None:
        """Sets the active programming language and synchronizes UI."""
        norm = normalize_language(lang)
        self.current_language = norm
        if hasattr(self, "combo_language"):
            idx = self.combo_language.findData(norm)
            if idx >= 0 and self.combo_language.currentIndex() != idx:
                self.combo_language.blockSignals(True)
                self.combo_language.setCurrentIndex(idx)
                self.combo_language.blockSignals(False)

    def _on_combo_language_changed(self, index: int) -> None:
        """Handles manual language selection from dropdown."""
        lang = self.combo_language.currentData()
        if lang:
            self.current_language = lang
            self.language_changed.emit(lang)

    def cycle_language(self) -> None:
        """Cycles to the next programming language (shortcut [L])."""
        if hasattr(self, "combo_language") and self.combo_language.count() > 0:
            idx = (self.combo_language.currentIndex() + 1) % self.combo_language.count()
            self.combo_language.setCurrentIndex(idx)

    @pyqtSlot(bool)
    def set_vscode_connected(self, connected: bool) -> None:
        """Updates the VS Code connection badge."""
        self.is_vscode_connected = connected
        if hasattr(self, "lbl_vscode_status"):
            if connected:
                self.lbl_vscode_status.setText("VS Code: Conectado (WS)")
                self.lbl_vscode_status.setStyleSheet(
                    "font-size: 10px; font-weight: bold; color: #34d399; padding: 3px 6px; "
                    "border: 1px solid #10b981; border-radius: 4px; background: #064e3b;"
                )
            else:
                self.lbl_vscode_status.setText("VS Code: Desconectado")
                self.lbl_vscode_status.setStyleSheet(
                    "font-size: 10px; font-weight: bold; color: #94a3b8; padding: 3px 6px; "
                    "border: 1px solid #334155; border-radius: 4px; background: #0f172a;"
                )

    def toggle_adaptive_ast(self) -> None:
        """Toggles adaptive AST menus mode (shortcut [A])."""
        self.adaptive_ast_enabled = not self.adaptive_ast_enabled
        self._update_adaptive_ui()
        self.adaptive_ast_toggled.emit(self.adaptive_ast_enabled)

    @pyqtSlot(bool)
    def set_adaptive_ast_enabled(self, enabled: bool) -> None:
        """Explicitly sets adaptive AST menus enabled status."""
        if self.adaptive_ast_enabled != enabled:
            self.adaptive_ast_enabled = enabled
            self._update_adaptive_ui()
            self.adaptive_ast_toggled.emit(self.adaptive_ast_enabled)

    def _update_adaptive_ui(self) -> None:
        """Updates the button text and styling based on adaptive AST state."""
        if not hasattr(self, "btn_toggle_adaptive"):
            return
        state_str = "ON" if self.adaptive_ast_enabled else "OFF"
        self.btn_toggle_adaptive.setText(f"AST: {state_str} [Ctrl+Alt+A]")
        if self.adaptive_ast_enabled:
            self.btn_toggle_adaptive.setStyleSheet("""
                QPushButton {
                    background-color: #065f46;
                    border: 1px solid #10b981;
                    border-radius: 4px;
                    padding: 4px 6px;
                    font-size: 10px;
                    font-weight: bold;
                    color: #ecfdf5;
                }
                QPushButton:hover {
                    background-color: #047857;
                }
            """)
        else:
            self.btn_toggle_adaptive.setStyleSheet("""
                QPushButton {
                    background-color: #1e293b;
                    border: 1px solid #475569;
                    border-radius: 4px;
                    padding: 4px 6px;
                    font-size: 10px;
                    font-weight: bold;
                    color: #94a3b8;
                }
                QPushButton:hover {
                    background-color: #334155;
                }
            """)

    @pyqtSlot(str)
    def update_ast_context(self, context_name: str) -> None:
        """Updates the live AST context indicator."""
        label_map = {
            "FUNCTION_SIGNATURE": "FUNCIÓN",
            "TRY_BLOCK": "TRY/EXCEPT",
            "CLASS_BODY": "CLASE",
            "IF_BLOCK": "IF/ELIF",
            "LOOP_BLOCK": "BUCLE",
            "WITH_BLOCK": "WITH",
            "GENERAL": "GENERAL",
        }
        disp = label_map.get(context_name, context_name)
        if hasattr(self, "lbl_ast_context"):
            self.lbl_ast_context.setText(f"Contexto: {disp}")


# Alias for backwards compatibility and alternative naming conventions
DebugMonitorWidget = DebugWidget

