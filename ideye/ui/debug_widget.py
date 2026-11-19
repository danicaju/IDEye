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

from ideye.ui.debug_build_top import DebugBuildTopMixin
from ideye.ui.debug_build_bottom import DebugBuildBottomMixin
from ideye.ui.debug_handlers import DebugHandlersMixin


class DebugWidget(DebugBuildTopMixin, DebugBuildBottomMixin, DebugHandlersMixin, QWidget):
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
    health_guard_toggled = pyqtSignal(bool)
    micro_gestures_toggled = pyqtSignal(bool)
    low_light_toggled = pyqtSignal(bool)
    cap_mode_toggled = pyqtSignal(bool)
    eco_sleep_toggled = pyqtSignal(bool)
    ghost_peek_toggled = pyqtSignal(bool)
    reduced_motion_toggled = pyqtSignal(bool)
    winks_toggled = pyqtSignal(bool)
    wink_mouth_only_toggled = pyqtSignal(bool)

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
        main_layout = self._build_shell()
        self._build_header(main_layout)
        content_layout = self._build_content_and_camera()
        self._build_mar_and_mode(content_layout)
        self._build_sliders(content_layout)
        self._build_guide_card(content_layout)
        self._build_lang_bridge(content_layout)
        self._build_ai_status(content_layout)
        self._build_link_adaptive(content_layout)
        self._build_action_buttons(content_layout)
        self._build_icons()
        self._build_audio_button(content_layout)
        self._build_footer(content_layout, main_layout)

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
                self.lbl_stability.setText(f"Fijación {pct}%")
                self.lbl_stability.setStyleSheet("font-size: 11px; font-weight: bold; color: #34d399;")
            else:
                self.lbl_stability.setText("Sácada")
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
                background-color: #0e7490;
                border: 1px solid #22d3ee;
                border-radius: 8px;
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
                border-radius: 8px;
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
                    "border: 1px solid #10b981; border-radius: 8px; background: #064e3b;"
                )
            else:
                self.lbl_vscode_status.setText("VS Code: Desconectado")
                self.lbl_vscode_status.setStyleSheet(
                    "font-size: 10px; font-weight: bold; color: #94a3b8; padding: 3px 6px; "
                    "border: 1px solid #334155; border-radius: 8px; background: #0f172a;"
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
                    border-radius: 8px;
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
                    border-radius: 8px;
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
