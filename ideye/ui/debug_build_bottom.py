"""Debug panel construction: sliders, guide, language, AI and action buttons."""

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


class DebugBuildBottomMixin:
    """Debug panel construction: sliders, guide, language, AI and action buttons."""

    def _build_sliders(self, content_layout):
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

    def _build_guide_card(self, content_layout):
        # Dedicated In-App Gesture & Shortcut Reference Card
        guide_frame = QFrame(self)
        guide_frame.setObjectName("cardFrame")
        guide_layout = QVBoxLayout(guide_frame)
        guide_layout.setContentsMargins(8, 8, 8, 8)
        guide_layout.setSpacing(4)

        lbl_guide_title = QLabel("GUÍA DE GESTOS Y ATAJOS", guide_frame)
        lbl_guide_title.setStyleSheet("font-size: 11px; font-weight: bold; color: #22d3ee;")
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
            "<div style='color: #7dd3fc; font-weight: bold; margin-bottom: 3px;'>GESTOS FACIALES Y OCULARES</div>"
            "<div>• <b>Abrir boca:</b> clic o inyectar.</div>"
            "<div>• <b>Boca mantenida (Jaw-Lock):</b> arrastrar o seleccionar.</div>"
            "<div>• <b>Guiño izquierdo:</b> volver o deshacer.</div>"
            "<div>• <b>Guiño derecho:</b> pausar o despertar.</div>"
            "<div style='height: 7px;'></div>"
            "<div style='color: #7dd3fc; font-weight: bold; margin-bottom: 3px;'>ATAJOS DE TECLADO</div>"
            "<div>• Ctrl+Alt+A menús &nbsp;·&nbsp; Ctrl+Alt+T tracking</div>"
            "<div>• Ctrl+Alt+V modos &nbsp;·&nbsp; Ctrl+Alt+K auto</div>"
            "<div>• Ctrl+Alt+S sonido &nbsp;·&nbsp; Ctrl+Alt+F FreeLook</div>"
            "<div>• Ctrl+Alt+G gaming &nbsp;·&nbsp; Ctrl+Alt+B portapapeles</div>"
            "<div>• Ctrl+Alt+M monitor &nbsp;·&nbsp; Ctrl+Alt+N pantalla</div>"
            "<div>• Ctrl+Alt+L lenguaje &nbsp;·&nbsp; Ctrl+Alt+H ayuda</div>"
            "<div>• Ctrl+Alt+P pausa &nbsp;·&nbsp; Ctrl+Alt+Q salir</div>"
            "</div>"
        )
        self.guide_content = guide_content
        guide_layout.addWidget(guide_content)
        for label in guide_frame.findChildren(QLabel):
            label.setWordWrap(True)
            label.setMinimumWidth(0)
            label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        content_layout.addWidget(guide_frame)

        self.btn_open_guide = QPushButton("Abrir manual interactivo", self)
        self.btn_open_guide.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_open_guide.setToolTip("Abre la guía visual interactiva completa en el navegador")
        self.btn_open_guide.setStyleSheet(
            "QPushButton { background-color: #0e7490; color: #ecfeff; border: 1px solid #22d3ee; "
            "border-radius: 8px; padding: 8px 10px; font-weight: bold; }"
            "QPushButton:hover { background-color: #0891b2; }"
        )
        self.btn_open_guide.clicked.connect(self.open_guide_requested.emit)
        content_layout.addWidget(self.btn_open_guide)

        self.chk_health_guard = QCheckBox("Health Guard: parpadeo y postura", self)
        self.chk_health_guard.setChecked(bool(getattr(config, "HEALTH_GUARD_ENABLED", True)))
        self.chk_health_guard.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.chk_health_guard.toggled.connect(self.health_guard_toggled.emit)
        content_layout.addWidget(self.chk_health_guard)

        self.chk_micro_gestures = QCheckBox("Micro-gestos: cejas e inclinación", self)
        self.chk_micro_gestures.setChecked(bool(getattr(config, "MICRO_GESTURES_ENABLED", True)))
        self.chk_micro_gestures.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.chk_micro_gestures.toggled.connect(self.micro_gestures_toggled.emit)
        content_layout.addWidget(self.chk_micro_gestures)

        self.chk_low_light = QCheckBox("Visión nocturna (CLAHE)", self)
        self.chk_low_light.setChecked(bool(getattr(config, "AUTO_LOW_LIGHT_CLAHE", True)))
        self.chk_low_light.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.chk_low_light.toggled.connect(self.low_light_toggled.emit)
        content_layout.addWidget(self.chk_low_light)

        self.chk_cap_mode = QCheckBox("Modo Gorra: anclaje nasal y anti-sombra", self)
        self.chk_cap_mode.setChecked(bool(getattr(config, "CAP_MODE_ENABLED", False)))
        self.chk_cap_mode.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.chk_cap_mode.toggled.connect(self.cap_mode_toggled.emit)
        content_layout.addWidget(self.chk_cap_mode)

        self.chk_eco_sleep = QCheckBox("Eco-Sleep: 10/2 FPS en reposo", self)
        self.chk_eco_sleep.setChecked(bool(getattr(config, "ECO_SLEEP_ENABLED", True)))
        self.chk_eco_sleep.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.chk_eco_sleep.toggled.connect(self.eco_sleep_toggled.emit)
        content_layout.addWidget(self.chk_eco_sleep)

        self.chk_ghost_peek = QCheckBox("Ghost-Peek: atenuar grid al leer", self)
        self.chk_ghost_peek.setChecked(bool(getattr(config, "GHOST_PEEK_ENABLED", True)))
        self.chk_ghost_peek.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.chk_ghost_peek.toggled.connect(self.ghost_peek_toggled.emit)
        content_layout.addWidget(self.chk_ghost_peek)

        self.chk_reduced_motion = QCheckBox("Reducir movimiento (cambios instantáneos)", self)
        self.chk_reduced_motion.setChecked(bool(getattr(config, "REDUCED_MOTION", False)))
        self.chk_reduced_motion.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.chk_reduced_motion.setToolTip(
            "Desactiva las transiciones del grid: el foco, el atenuado y los avisos cambian al instante."
        )
        self.chk_reduced_motion.toggled.connect(self.reduced_motion_toggled.emit)
        content_layout.addWidget(self.chk_reduced_motion)

        self.chk_winks = QCheckBox("Guiños laterales con anti-blink", self)
        self.chk_winks.setChecked(bool(getattr(config, "WINK_ENABLED", True)))
        self.chk_winks.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.chk_winks.toggled.connect(self.winks_toggled.emit)
        content_layout.addWidget(self.chk_winks)

        self.chk_wink_mouth_only = QCheckBox("Solo boca: desactivar guiños", self)
        self.chk_wink_mouth_only.setChecked(bool(getattr(config, "WINK_MOUTH_ONLY", False)))
        self.chk_wink_mouth_only.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.chk_wink_mouth_only.toggled.connect(self.wink_mouth_only_toggled.emit)
        content_layout.addWidget(self.chk_wink_mouth_only)

    def _build_lang_bridge(self, content_layout):
        # 7. Language Selector & VS Code WebSocket Bridge Status
        lang_bridge_frame = QFrame(self)
        lang_bridge_frame.setObjectName("cardFrame")
        lang_bridge_layout = QVBoxLayout(lang_bridge_frame)
        lang_bridge_layout.setContentsMargins(6, 6, 6, 6)
        lang_bridge_layout.setSpacing(4)

        lbl_lang_section = QLabel("LENGUAJE ACTIVO Y PUENTE VS CODE (Ctrl+Alt+L)", lang_bridge_frame)
        lbl_lang_section.setStyleSheet("font-size: 10px; font-weight: bold; color: #22d3ee;")
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
                border: 1px solid #0e7490;
                border-radius: 8px;
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
                selection-background-color: #0e7490;
                selection-color: #ffffff;
                border: 1px solid #334155;
            }
        """)
        self.combo_language.currentIndexChanged.connect(self._on_combo_language_changed)
        lang_row.addWidget(self.combo_language, stretch=3)

        self.lbl_vscode_status = QLabel("VS Code: Desconectado", lang_bridge_frame)
        self.lbl_vscode_status.setStyleSheet("font-size: 10px; font-weight: bold; color: #94a3b8; padding: 3px 6px; border: 1px solid #334155; border-radius: 8px; background: #0f172a;")
        self.lbl_vscode_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lang_row.addWidget(self.lbl_vscode_status, stretch=3)

        lang_bridge_layout.addLayout(lang_row)
        content_layout.addWidget(lang_bridge_frame)

    def _build_ai_status(self, content_layout):
        # 8. Context & AI Engine Status
        ai_layout = QVBoxLayout()
        ai_layout.setSpacing(2)

        self.lbl_active_file = QLabel("Archivo: detección automática", self)
        self.lbl_active_file.setStyleSheet("font-size: 10px; color: #22d3ee;")
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

    def _build_link_adaptive(self, content_layout):
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

    def _build_action_buttons(self, content_layout):
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

    def _build_icons(self):
        # Decorate buttons and window with neon vector icons
        icon_mgr = IconManager.instance()
        logo_icon = icon_mgr.get_icon("ideye_logo", 32)
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

    def _build_audio_button(self, content_layout):
        # 9b. Audio verification button.
        self.btn_test_sound = QPushButton(" Probar sonido", self)
        self.btn_test_sound.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_test_sound.setToolTip("Reproduce un clic de prueba con el motor de audio actual")
        self.btn_test_sound.setStyleSheet(
            "QPushButton { background-color: #0e7490; color: #ecfeff; border: 1px solid #22d3ee; "
            "border-radius: 8px; padding: 6px 10px; font-weight: bold; }"
            "QPushButton:hover { background-color: #0891b2; }"
        )
        self.btn_test_sound.clicked.connect(self.test_sound_requested.emit)
        content_layout.addWidget(self.btn_test_sound)

    def _build_footer(self, content_layout, main_layout):
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
