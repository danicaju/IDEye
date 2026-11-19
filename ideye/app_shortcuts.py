"""Global hotkey handlers."""

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


class AppShortcutsMixin:
    """Global hotkey handlers."""

    def _on_mode_shortcut(self) -> None:
        """V while gazing at the header mode button cycles the context mode."""
        if self.overlay.is_mode_shortcut_targeted():
            self._on_mode_shortcut_anywhere()

    def _on_mode_shortcut_anywhere(self) -> None:
        """Ctrl+Alt+V (or a validated plain V) cycles the context mode."""
        now = time.time()
        if now - self._last_mode_shortcut_ts < 0.25:
            return
        self._last_mode_shortcut_ts = now
        self.overlay.cycle_context_mode()

    def _on_auto_switch_shortcut(self) -> None:
        """K while gazing at the header mode button toggles automatic mode switching."""
        if self.overlay.is_mode_shortcut_targeted():
            self._on_auto_switch_shortcut_anywhere()

    def _on_auto_switch_shortcut_anywhere(self) -> None:
        """Ctrl+Alt+K (or a validated plain K) toggles automatic mode switching."""
        now = time.time()
        if now - self._last_auto_switch_ts < 0.25:
            return
        self._last_auto_switch_ts = now
        enabled = self.overlay.toggle_auto_switch()
        self.overlay.last_action_desc = f"Auto-switch: {'ON' if enabled else 'OFF'}"
        self.overlay.update()

    def _on_sound_shortcut(self) -> None:
        """S while gazing at the header toggles procedural sound."""
        if self.overlay.is_mode_shortcut_targeted():
            self._on_sound_shortcut_anywhere()

    def _on_sound_shortcut_anywhere(self) -> None:
        """Ctrl+Alt+S (or a validated plain S) toggles audio feedback."""
        self.overlay.toggle_sound_feedback()

    def _on_sniper_shortcut(self) -> None:
        """F while gazing at the header activates sniper mode."""
        if self.overlay.is_mode_shortcut_targeted():
            self._on_sniper_shortcut_anywhere()

    def _on_sniper_shortcut_anywhere(self) -> None:
        """Ctrl+Alt+F (or a validated plain F) toggles sniper mode."""
        self.overlay.toggle_sniper_mode()

    def _on_monitor_shortcut(self) -> None:
        """M while gazing at the top bar collapses/expands the monitor."""
        if self.overlay.is_mode_shortcut_targeted():
            self._on_monitor_shortcut_anywhere()

    def _on_monitor_shortcut_anywhere(self) -> None:
        """Ctrl+Alt+M (or a validated plain M) toggles the monitor panel."""
        if hasattr(self, "debug_widget") and self.debug_widget is not None:
            self.debug_widget.toggle_collapse()
            self.overlay.last_action_desc = (
                "Monitor: colapsado" if self.debug_widget.is_collapsed else "Monitor: expandido"
            )
            self.overlay.update()

    def _on_gaming_shortcut(self) -> None:
        """G while gazing at the header toggles the FreeLook gaming profile."""
        if self.overlay.is_mode_shortcut_targeted():
            self._on_gaming_shortcut_anywhere()

    def _on_gaming_shortcut_anywhere(self) -> None:
        """Ctrl+Alt+G (or a validated plain G) toggles the gaming profile."""
        if self.overlay.current_context_mode_id == "sniper":
            self.overlay.toggle_gaming_mode()

    def _open_interactive_guide(self) -> None:
        """Regenerates and opens the offline Game Manual in the default browser."""
        try:
            from ideye.core.guide_catalog import generate_interactive_guide

            path = generate_interactive_guide()
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
                logger.warning("Could not open interactive guide at %s", path)
        except Exception as exc:
            logger.warning("Interactive guide unavailable: %s", exc)

    def _on_clipboard_shortcut(self) -> None:
        """B while gazing at the command bar opens clipboard history."""
        if self.overlay.is_mode_shortcut_targeted():
            self._on_clipboard_shortcut_anywhere()

    def _on_clipboard_shortcut_anywhere(self) -> None:
        """Ctrl+Alt+B opens the six-slot clipboard history from any window."""
        self.overlay.open_clipboard_history()

    def _on_center_calibration_shortcut(self) -> None:
        """Ctrl+Alt+C: anchors the current face position as screen center."""
        estimator = getattr(self.tracker, "gaze_estimator", None)
        landmarks = None
        if hasattr(self.tracker, "get_latest_landmarks"):
            landmarks = self.tracker.get_latest_landmarks()
        try:
            ok = bool(estimator is not None and landmarks is not None and estimator.calibrate_center(landmarks))
        except Exception:
            ok = False
        if ok and landmarks is not None and hasattr(self.tracker, "health_guard"):
            try:
                self.tracker.health_guard.set_baseline(landmarks)
            except Exception:
                pass
        self.overlay.last_action_desc = "Centro calibrado" if ok else "Sin rostro: mira al centro"
        self.overlay.update()
