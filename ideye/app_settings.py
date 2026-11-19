"""Settings application and feature toggles."""

import sys
import os
import time
import argparse
from typing import Optional, Tuple, Dict, Any, Union
import cv2
import numpy as np

# Robust path handling for workspace root and package imports
_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_PARENT_DIR = os.path.dirname(_CURRENT_DIR)
for _p in (_CURRENT_DIR, _PARENT_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    import ideye.config as config
    from ideye.core.camera_tracker import CameraTracker
    from ideye.core.gaze_estimator import GazeEstimator
    from ideye.core.gesture_detector import GestureDetector
    from ideye.core.hotkey_manager import GlobalHotkeyManager
    from ideye.core.websocket_bridge import WebSocketBridge
    from ideye.core.sound_feedback import SoundFeedbackManager
    from ideye.core.mouse_controller import OSMouseController
    from ideye.core.settings_manager import SettingsManager
    from ideye.core.macro_manager import MacroManager
    from ideye.core.screen_manager import ScreenManager
    from ideye.core.window_watcher import WindowWatcher
    from ideye.core.game_profiles import GameProfileManager
    from ideye.core.telemetry_manager import TelemetryManager
    from ideye.actions.clipboard_history import get_clipboard_history_manager
    from ideye.ui.macro_editor_dialog import CustomMacroDialog
    from ideye.ui.overlay_window import OverlayWindow
    from ideye.ui.debug_widget import DebugWidget
    from ideye.ui.calibration_ui import CalibrationUI
    from ideye.ui.icon_manager import IconManager
    from ideye.ui.system_tray import IDEyeSystemTray
    from ideye.actions.context_reader import ContextReader
    from ideye.actions.language_support import normalize_language, get_language_display_name
    from ideye.modes.mode_manager import ModeManager
except ImportError:
    import config
    from core.camera_tracker import CameraTracker
    from core.gaze_estimator import GazeEstimator
    from core.gesture_detector import GestureDetector
    from core.hotkey_manager import GlobalHotkeyManager
    from core.websocket_bridge import WebSocketBridge
    from core.sound_feedback import SoundFeedbackManager
    from core.mouse_controller import OSMouseController
    from core.settings_manager import SettingsManager
    from core.macro_manager import MacroManager
    from core.screen_manager import ScreenManager
    from core.window_watcher import WindowWatcher
    from core.game_profiles import GameProfileManager
    from core.telemetry_manager import TelemetryManager
    from actions.clipboard_history import get_clipboard_history_manager
    from ui.macro_editor_dialog import CustomMacroDialog
    from ui.overlay_window import OverlayWindow
    from ui.debug_widget import DebugWidget
    from ui.calibration_ui import CalibrationUI
    from ui.icon_manager import IconManager
    from ui.system_tray import IDEyeSystemTray
    from actions.context_reader import ContextReader
    from actions.language_support import normalize_language, get_language_display_name
    from modes.mode_manager import ModeManager

import threading

from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont, QBrush, QDesktopServices
from PyQt6.QtCore import Qt, QObject, QTimer, QUrl, pyqtSlot


from ideye.core.logging_config import get_logger

logger = get_logger(__name__)


class AppSettingsMixin:
    """Settings application and feature toggles."""

    def _apply_settings(self, values: Dict[str, Any]) -> None:
        """Applies persisted settings to every subsystem at startup/reset."""
        values = dict(values or {})
        estimator = getattr(self.tracker, "gaze_estimator", None)
        detector = getattr(self.tracker, "gesture_detector", None)

        mode = str(values.get("tracking_mode", "HEAD_PRIMARY")).upper()
        sx = float(values.get("sensitivity_x", getattr(config, "DEFAULT_HEAD_SENSITIVITY_X", 2.6)))
        sy = float(values.get("sensitivity_y", getattr(config, "DEFAULT_HEAD_SENSITIVITY_Y", 3.0)))
        level = int(values.get("one_euro_level", 6))
        mar = float(values.get("mar_threshold", getattr(config, "MAR_THRESHOLD", 0.45)))
        lang = str(values.get("active_language", "python")).lower()
        ast_enabled = bool(values.get("adaptive_ast_enabled", True))
        auto_switch = bool(values.get("auto_switch_enabled", False))
        sound_enabled = bool(values.get("sound_enabled", True))
        collapsed = bool(values.get("debug_panel_collapsed", False))
        health_enabled = bool(values.get("health_guard_enabled", True))
        micro_enabled = bool(values.get("micro_gestures_enabled", True))
        low_light_enabled = bool(values.get("auto_low_light_clahe", True))
        cap_mode = bool(values.get("cap_mode_enabled", getattr(config, "CAP_MODE_ENABLED", False)))
        eco_enabled = bool(values.get("eco_sleep_enabled", getattr(config, "ECO_SLEEP_ENABLED", True)))
        ghost_enabled = bool(values.get("ghost_peek_enabled", getattr(config, "GHOST_PEEK_ENABLED", True)))
        reduced_motion = bool(values.get("reduced_motion", getattr(config, "REDUCED_MOTION", False)))
        ghost_idle = float(
            values.get(
                "ghost_peek_idle_seconds",
                getattr(config, "GHOST_PEEK_IDLE_SECONDS", 30.0),
            )
        )
        gaze_scroll_enabled = bool(values.get("gaze_scroll_enabled", getattr(config, "GAZE_SCROLL_ENABLED", True)))
        wink_enabled = bool(values.get("wink_enabled", getattr(config, "WINK_ENABLED", True)))
        wink_mouth_only = bool(values.get("wink_mouth_only", getattr(config, "WINK_MOUTH_ONLY", False)))
        wink_difficulty = str(values.get("wink_difficulty", getattr(config, "WINK_DIFFICULTY", "normal")))
        wink_min_hold = float(values.get("wink_min_hold_sec", getattr(config, "WINK_MIN_HOLD_SEC", 0.18)))
        wink_max_hold = float(values.get("wink_max_hold_sec", getattr(config, "WINK_MAX_HOLD_SEC", 0.30)))
        wink_cooldown = float(values.get("wink_cooldown_sec", getattr(config, "WINK_COOLDOWN_SEC", 0.65)))
        wink_margin = float(values.get("wink_opposite_margin", getattr(config, "WINK_OPPOSITE_EYE_MARGIN", 0.035)))
        wink_distance = bool(values.get("wink_distance_compensation", getattr(config, "WINK_DISTANCE_COMPENSATION", True)))
        dwell_click_enabled = bool(values.get("dwell_click_enabled", getattr(config, "DWELL_CLICK_ENABLED", False)))

        if estimator is not None:
            estimator.set_tracking_mode(mode)
            estimator.set_sensitivity(
                head_x=sx,
                head_y=sy,
                iris_x=sx * 1.35,
                iris_y=sy * 1.30,
            )
            estimator.set_anti_jitter_damping(level)
        if detector is not None:
            mar_calibrated = bool(values.get("mar_calibrated", False))
            baseline_val = values.get("mar_baseline", None)
            if hasattr(detector, "set_mar_calibration") and mar_calibrated:
                detector.set_mar_calibration(mar, baseline=baseline_val)
            else:
                detector.mar_threshold = mar
                detector.release_threshold = max(0.20, mar - 0.10)
                detector.mar_calibrated = mar_calibrated
            detector.micro_gestures_enabled = micro_enabled
            if hasattr(detector, "configure_wink"):
                detector.configure_wink(
                    wink_enabled=wink_enabled,
                    wink_mouth_only=wink_mouth_only,
                    wink_difficulty=wink_difficulty,
                    wink_min_hold_sec=wink_min_hold,
                    wink_max_hold_sec=wink_max_hold,
                    wink_cooldown_sec=wink_cooldown,
                    wink_opposite_margin=wink_margin,
                    wink_distance_compensation=wink_distance,
                )
        if hasattr(self.overlay, "set_mar_threshold"):
            self.overlay.set_mar_threshold(mar, calibrated=mar_calibrated)
        if hasattr(self.tracker, "health_guard"):
            self.tracker.health_guard.enabled = health_enabled
        if hasattr(self.tracker, "lighting"):
            self.tracker.lighting.enabled = low_light_enabled
        if hasattr(self.tracker, "set_cap_mode"):
            self.tracker.set_cap_mode(cap_mode)
        if hasattr(self.tracker, "set_eco_enabled"):
            self.tracker.set_eco_enabled(eco_enabled)
        config.MAR_THRESHOLD = mar

        self.sound_feedback.set_enabled(sound_enabled)
        self.overlay.set_adaptive_ast_enabled(ast_enabled)
        if hasattr(self.overlay, "set_dwell_click_enabled"):
            self.overlay.set_dwell_click_enabled(dwell_click_enabled)
        self.overlay.toggle_auto_switch(auto_switch)
        self.overlay.set_ghost_peek_enabled(ghost_enabled, emit_signal=False)
        self.overlay.set_ghost_peek_idle_seconds(ghost_idle)
        self.overlay.set_reduced_motion(reduced_motion, emit_signal=False)
        if getattr(self.overlay, "_gaze_scroll_enabled", None) != gaze_scroll_enabled:
            self.overlay.toggle_gaze_scroll(gaze_scroll_enabled)
        self.overlay.set_language(lang)
        self.debug_widget.set_language(lang)
        self.debug_widget.set_tracking_mode_by_name(mode)
        self.debug_widget.set_adaptive_ast_enabled(ast_enabled)
        self.debug_widget.set_mar_threshold(mar, emit=False)
        self.debug_widget.set_health_guard_enabled(health_enabled)
        self.debug_widget.set_micro_gestures_enabled(micro_enabled)
        self.debug_widget.set_low_light_enabled(low_light_enabled)
        self.debug_widget.set_cap_mode_enabled(cap_mode)
        self.debug_widget.set_eco_sleep_enabled(eco_enabled)
        self.debug_widget.set_ghost_peek_enabled(ghost_enabled)
        self.debug_widget.set_reduced_motion(reduced_motion)
        self.debug_widget.set_winks_enabled(wink_enabled)
        self.debug_widget.set_wink_mouth_only(wink_mouth_only)
        if hasattr(self.mode_manager, "set_language"):
            self.mode_manager.set_language(lang)
        if hasattr(self.context_reader, "set_active_language"):
            self.context_reader.set_active_language(lang)

        # Sync sliders without re-triggering debounced saves.
        self.debug_widget.slider_sens_x.blockSignals(True)
        self.debug_widget.slider_sens_y.blockSignals(True)
        self.debug_widget.slider_damping.blockSignals(True)
        self.debug_widget.slider_sens_x.setValue(int(round(sx * 10)))
        self.debug_widget.slider_sens_y.setValue(int(round(sy * 10)))
        self.debug_widget.slider_damping.setValue(level)
        self.debug_widget.slider_sens_x.blockSignals(False)
        self.debug_widget.slider_sens_y.blockSignals(False)
        self.debug_widget.slider_damping.blockSignals(False)
        self.debug_widget.lbl_sens_x.setText(f"Sensibilidad X: {sx:.1f}x")
        self.debug_widget.lbl_sens_y.setText(f"Sensibilidad Y (Ergonómica): {sy:.1f}x")
        self.debug_widget.lbl_damping.setText(f"Anti-Temblor (Filtro 1€): Nivel {level}")

        if collapsed != bool(getattr(self.debug_widget, "is_collapsed", False)):
            self.debug_widget.toggle_collapse()
        self._settings = values

    def _on_power_state_changed(self, state: str) -> None:
        """Propagates ECO state to the debug panel and native tray."""
        if hasattr(self.debug_widget, "set_power_state"):
            self.debug_widget.set_power_state(state)
        tray = getattr(self, "tray_icon", None)
        if tray is not None and hasattr(tray, "set_power_state"):
            tray.set_power_state(state)

    def _on_eco_sleep_toggled(self, enabled: bool) -> None:
        if hasattr(self.tracker, "set_eco_enabled"):
            self.tracker.set_eco_enabled(bool(enabled))
        self.settings_manager.set("eco_sleep_enabled", bool(enabled))
        if hasattr(self.debug_widget, "set_eco_sleep_enabled"):
            self.debug_widget.set_eco_sleep_enabled(bool(enabled))

    def _on_ghost_peek_toggled(self, enabled: bool) -> None:
        if hasattr(self.overlay, "set_ghost_peek_enabled"):
            self.overlay.set_ghost_peek_enabled(bool(enabled), emit_signal=False)
        self.settings_manager.set("ghost_peek_enabled", bool(enabled))
        if hasattr(self.debug_widget, "set_ghost_peek_enabled"):
            self.debug_widget.set_ghost_peek_enabled(bool(enabled))
        tray = getattr(self, "tray_icon", None)
        if tray is not None and hasattr(tray, "set_ghost_peek"):
            tray.set_ghost_peek(bool(enabled))

    def _on_reduced_motion_toggled(self, enabled: bool) -> None:
        if hasattr(self.overlay, "set_reduced_motion"):
            self.overlay.set_reduced_motion(bool(enabled), emit_signal=False)
        self.settings_manager.set("reduced_motion", bool(enabled))
        if hasattr(self.debug_widget, "set_reduced_motion"):
            self.debug_widget.set_reduced_motion(bool(enabled))

    def _on_winks_toggled(self, enabled: bool) -> None:
        detector = getattr(self.tracker, "gesture_detector", None)
        if detector is not None and hasattr(detector, "configure_wink"):
            detector.configure_wink(wink_enabled=bool(enabled))
        self.settings_manager.set("wink_enabled", bool(enabled))
        if hasattr(self.debug_widget, "set_winks_enabled"):
            self.debug_widget.set_winks_enabled(bool(enabled))

    def _on_wink_mouth_only_toggled(self, enabled: bool) -> None:
        detector = getattr(self.tracker, "gesture_detector", None)
        if detector is not None and hasattr(detector, "configure_wink"):
            detector.configure_wink(wink_mouth_only=bool(enabled))
        self.settings_manager.set("wink_mouth_only", bool(enabled))
        if hasattr(self.debug_widget, "set_wink_mouth_only"):
            self.debug_widget.set_wink_mouth_only(bool(enabled))

    def _apply_autofix(self, fix: Dict[str, Any]) -> None:
        """Applies a selected Auto-Fix locally or through the VS Code bridge."""
        bridge = getattr(self, "ws_bridge", None)
        ok = self.overlay.diagnostics_fixer.apply_fix(
            fix, bridge=bridge, code_injector=self.overlay.code_injector
        )
        self.overlay.last_action_desc = (
            f"Auto-Fix aplicado: {fix.get('label', '')}" if ok else "Auto-Fix no disponible"
        )
        self.overlay.update()

    def _on_cap_mode_toggled(self, enabled: bool) -> None:
        if hasattr(self.tracker, "set_cap_mode"):
            self.tracker.set_cap_mode(bool(enabled))
        self.settings_manager.set("cap_mode_enabled", bool(enabled))
        self.overlay.last_action_desc = "Modo Gorra: ACTIVADO" if enabled else "Modo Gorra: DESACTIVADO"
        self.overlay.update()

    def _on_low_light_toggled(self, enabled: bool) -> None:
        if hasattr(self.tracker, "lighting"):
            self.tracker.lighting.enabled = bool(enabled)
        self.settings_manager.set("auto_low_light_clahe", bool(enabled))

    def _on_lighting_frame(self, _frame: Any, _mar: float) -> None:
        lighting = getattr(self.tracker, "lighting", None)
        if lighting is not None:
            self.debug_widget.set_lighting_status(
                bool(lighting.is_low_light_active), float(lighting.current_luma)
            )

    def _on_health_guard_toggled(self, enabled: bool) -> None:
        if hasattr(self.tracker, "health_guard"):
            self.tracker.health_guard.enabled = bool(enabled)
        self.settings_manager.set("health_guard_enabled", bool(enabled))

    def _on_micro_gestures_toggled(self, enabled: bool) -> None:
        if hasattr(self.tracker, "gesture_detector"):
            self.tracker.gesture_detector.micro_gestures_enabled = bool(enabled)
        self.settings_manager.set("micro_gestures_enabled", bool(enabled))

    def _on_tracking_mode_changed(self, mode: str) -> None:
        """Called when user changes tracking mode in DebugWidget or shortcut."""
        if hasattr(self.tracker, "gaze_estimator") and self.tracker.gaze_estimator is not None:
            self.tracker.gaze_estimator.set_tracking_mode(mode)
        mode_names = {
            "PURE_IRIS": "Solo Iris",
            "HYBRID": "Híbrido",
            "HEAD_PRIMARY": "Solo Cabeza (Recomendado)",
        }
        display_name = mode_names.get(mode, mode)
        if self.overlay is not None:
            self.overlay.last_action_desc = f"Modo: {display_name}"
            self.overlay.update()
        logger.info(f"[INFO] Modo de seguimiento activo: {display_name} ({mode})")
