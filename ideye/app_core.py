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

from ideye.app_shortcuts import AppShortcutsMixin
from ideye.app_settings import AppSettingsMixin
from ideye.app_connections import AppConnectionsMixin
from ideye.app_calibration import AppCalibrationMixin
class IDEyeApplication(AppShortcutsMixin, AppSettingsMixin, AppConnectionsMixin, AppCalibrationMixin, QObject):
    """
    Phase 2 PyQt6 Orchestrator:
    - Sets up QApplication.
    - Manages CameraTracker QThread lifecycle.
    - Checks for calibration_profile.json:
        If found: loads it and shows OverlayWindow + DebugWidget directly.
        If missing (or if force_calibrate=True): launches CalibrationUI first,
        then displays OverlayWindow + DebugWidget upon completion.
    - Connects all Qt signals:
        tracker.gaze_updated -> overlay.on_gaze_updated
        tracker.gesture_triggered -> overlay.on_gesture_triggered
        tracker.frame_ready -> debug_widget.on_frame_ready
        debug_widget.recalibrate_requested -> launch_calibration()
        debug_widget.exit_requested -> shutdown()
        overlay.exit_requested -> shutdown()
    - Clean shutdown handler:
        Calls tracker.stop() and tracker.wait(2000)
        Releases capture device, closes windows, ensures 0 zombie threads!
    """

    def __init__(
        self,
        camera_index: Union[int, str] = config.CAMERA_INDEX,
        profile_path: str = config.CALIBRATION_PROFILE_PATH,
        force_calibrate: bool = False,
        threaded: bool = True,
    ):
        super().__init__()
        self.camera_index = camera_index
        self.profile_path = profile_path
        self.force_calibrate = force_calibrate
        self.threaded = threaded

        # Initialize QApplication
        self.qapp = QApplication.instance() or QApplication(sys.argv if hasattr(sys, 'argv') else [])
        app_icon = IconManager.instance().get_app_icon()
        if not app_icon.isNull():
            self.qapp.setWindowIcon(app_icon)

        # Persistent live settings (Phase 8.1)
        self.settings_manager = SettingsManager()
        self._settings = self.settings_manager.as_dict()
        self.macro_manager = MacroManager()
        self.clipboard_history = get_clipboard_history_manager()
        self.telemetry_manager = TelemetryManager(parent=self)

        # Core subsystems
        self.tracker = CameraTracker(camera_index=self.camera_index, threaded=self.threaded)
        self.context_reader = ContextReader(
            workspace_dir=getattr(config, "DEFAULT_WORKSPACE_DIR", os.getcwd()),
            active_file=getattr(config, "ACTIVE_FILE_PATH", None),
            auto_detect=getattr(config, "AUTO_DETECT_RECENT_FILE", True),
        )
        self.mode_manager = ModeManager(
            initial_mode="coding",
            language=getattr(self.context_reader, "active_language", getattr(config, "DEFAULT_PROGRAMMING_LANGUAGE", "PYTHON")),
            auto_switch_enabled=bool(self._settings.get("auto_switch_enabled", getattr(config, "CONTEXT_AUTO_SWITCH_ENABLED", False))),
        )
        self.overlay = OverlayWindow(
            context_reader=self.context_reader,
            mode_manager=self.mode_manager,
            macro_manager=self.macro_manager,
            start_in_mode_selector=getattr(config, "START_IN_MODE_SELECTOR", True),
        )
        self.debug_widget = DebugWidget()
        self.overlay.set_debug_widget(self.debug_widget)
        self.sound_feedback = SoundFeedbackManager(
            enabled=bool(self._settings.get("sound_enabled", getattr(config, "SOUND_ENABLED", True))),
            volume=getattr(config, "SOUND_VOLUME", 0.5),
        )
        self.overlay.set_sound_feedback(self.sound_feedback)
        self.mouse_controller = OSMouseController()
        self.overlay.set_mouse_controller(self.mouse_controller)
        self.overlay.set_clipboard_manager(self.clipboard_history)
        self.overlay.set_vscode_connected(False)
        self.screen_manager = ScreenManager(
            overlay=self.overlay,
            debug_widget=self.debug_widget,
            gaze_estimator=self.tracker.gaze_estimator,
            parent=self,
        )
        self.overlay.set_screen_info(0, self.screen_manager.screen_count)
        self.overlay.screen_cycle_requested.connect(self.screen_manager.cycle_next_screen)
        self.screen_manager.screen_changed.connect(self.overlay.set_screen_info)
        self._apply_settings(self._settings)
        self.calibration_ui: Optional[CalibrationUI] = None
        self._is_shutting_down: bool = False
        self.tray_icon: Optional[QSystemTrayIcon] = None
        self._last_mode_shortcut_ts: float = 0.0
        self._last_auto_switch_ts: float = 0.0
        self._hud_input_suspended: bool = False

        # WebSocket Bridge for native VS Code integration (Phase 5)
        self.ws_bridge: Optional[WebSocketBridge] = None
        if getattr(config, "ENABLE_WEBSOCKET_BRIDGE", True):
            self.ws_bridge = WebSocketBridge(
                host=getattr(config, "WEBSOCKET_HOST", "127.0.0.1"),
                port=getattr(config, "WEBSOCKET_PORT", 54321),
            )
            if hasattr(self.overlay, "code_injector") and self.overlay.code_injector is not None:
                self.overlay.code_injector.set_websocket_bridge(self.ws_bridge)

        self.game_profile_manager = GameProfileManager()
        self.window_watcher = WindowWatcher(
            mode_manager=self.mode_manager,
            profile_manager=self.game_profile_manager,
            websocket_connected=(
                (lambda: bool(self.ws_bridge and self.ws_bridge.is_connected))
                if self.ws_bridge is not None
                else None
            ),
            parent=self,
        )

        # Global Hotkey Manager for Emergency Exit & Reset
        self.hotkey_manager = GlobalHotkeyManager()
        self.hotkey_manager.emergency_exit_requested.connect(self.shutdown)
        self.hotkey_manager.emergency_reset_requested.connect(self.reset_calibration)
        self.hotkey_manager.mode_cycle_requested.connect(self._on_mode_shortcut)
        self.hotkey_manager.auto_switch_requested.connect(self._on_auto_switch_shortcut)
        self.hotkey_manager.mode_cycle_anywhere_requested.connect(self._on_mode_shortcut_anywhere)
        self.hotkey_manager.auto_switch_anywhere_requested.connect(self._on_auto_switch_shortcut_anywhere)
        self.hotkey_manager.sound_toggle_requested.connect(self._on_sound_shortcut)
        self.hotkey_manager.sound_toggle_anywhere_requested.connect(self._on_sound_shortcut_anywhere)
        self.hotkey_manager.sniper_toggle_requested.connect(self._on_sniper_shortcut)
        self.hotkey_manager.sniper_toggle_anywhere_requested.connect(self._on_sniper_shortcut_anywhere)
        self.hotkey_manager.gaming_toggle_requested.connect(self._on_gaming_shortcut)
        self.hotkey_manager.gaming_toggle_anywhere_requested.connect(self._on_gaming_shortcut_anywhere)
        self.hotkey_manager.monitor_toggle_requested.connect(self._on_monitor_shortcut)
        self.hotkey_manager.monitor_toggle_anywhere_requested.connect(self._on_monitor_shortcut_anywhere)
        self.hotkey_manager.screen_cycle_requested.connect(self.screen_manager.cycle_next_screen)
        self.hotkey_manager.sniper_lens_toggle_requested.connect(self.overlay.toggle_sniper_lens)
        self.hotkey_manager.ast_jump_requested.connect(self.overlay.open_ast_symbols)
        self.hotkey_manager.agentic_launcher_requested.connect(self.overlay.open_agentic_launcher)
        self.hotkey_manager.gaze_scroll_toggle_requested.connect(self.overlay.toggle_gaze_scroll)
        self.hotkey_manager.adaptive_ast_toggle_requested.connect(self.overlay.toggle_adaptive_ast)
        self.hotkey_manager.tracking_mode_cycle_requested.connect(self.debug_widget.cycle_tracking_mode)
        self.hotkey_manager.center_calibration_requested.connect(self._on_center_calibration_shortcut)
        self.hotkey_manager.pause_toggle_requested.connect(self.overlay.toggle_pause)
        self.hotkey_manager.language_cycle_requested.connect(self.overlay.cycle_language)
        self.hotkey_manager.help_toggle_requested.connect(self.overlay.toggle_help_modal)
        self.hotkey_manager.clipboard_history_requested.connect(self._on_clipboard_shortcut)
        self.hotkey_manager.clipboard_history_anywhere_requested.connect(
            self._on_clipboard_shortcut_anywhere
        )
        self.hotkey_manager.layout_toggle_requested.connect(self.overlay.toggle_hud_layout)
        self.hotkey_manager.theme_toggle_requested.connect(self.overlay.toggle_theme)

        self._setup_connections()
        self._configure_geometry()
        self._setup_tray_icon()

    def _setup_tray_icon(self) -> None:
        """Sets up desktop system tray icon for emergency controls and status."""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self.tray_icon = None
            return

        try:
            self.tray_icon = IDEyeSystemTray(self.debug_widget)
            self.tray_icon.pause_requested.connect(self.overlay.toggle_pause)
            self.tray_icon.mode_requested.connect(
                lambda mode_id: self.mode_manager.set_mode(mode_id)
            )
            self.tray_icon.ghost_peek_toggled.connect(self._on_ghost_peek_toggled)
            self.tray_icon.recalibrate_requested.connect(self.launch_calibration)
            self.tray_icon.guide_requested.connect(self._open_interactive_guide)
            self.tray_icon.mini_feed_requested.connect(self.debug_widget.toggle_collapse)
            self.tray_icon.exit_requested.connect(self.shutdown)
            self.tray_icon.set_ghost_peek(
                bool(getattr(self.overlay, "ghost_peek_enabled", True))
            )
            self.tray_icon.set_power_state(
                str(getattr(self.tracker, "current_power_state", "ACTIVE"))
            )
            self.tray_icon.show()
        except Exception as e:
            logger.warning(f"[IDEye] Warning: Could not initialize system tray: {e}")
            self.tray_icon = None

    def start(self) -> None:
        """Starts tracker thread, global emergency hotkeys, and displays UI."""
        # Check if calibration profile exists
        has_profile = os.path.exists(self.profile_path)
        if has_profile and not self.force_calibrate:
            logger.info(f"[INFO] Loaded calibration profile from '{self.profile_path}'.")
            self.tracker.gaze_estimator.load_calibration_profile(self.profile_path)

        # Re-bind after loading so the active monitor's per-monitor profile wins.
        if getattr(self, "screen_manager", None) is not None:
            self.screen_manager.bind_gaze_to_screen(QApplication.primaryScreen())

        # Start CameraTracker QThread
        started = self.tracker.start()
        if not started:
            logger.warning(f"[AVISO] No se pudo abrir la camara {self.tracker.camera_index}. Continuando...")

        # Start global emergency hotkey listener
        if hasattr(self, "hotkey_manager") and self.hotkey_manager is not None:
            self.hotkey_manager.start()
        if getattr(self, "clipboard_history", None) is not None:
            self.clipboard_history.start()
        if getattr(self, "window_watcher", None) is not None:
            self.window_watcher.start()

        # Start WebSocket Bridge (Phase 5)
        if self.ws_bridge is not None:
            self.ws_bridge.start()

        # Reflect any detected or preconfigured active file
        active_f = self.context_reader.get_active_file()
        if active_f:
            self.debug_widget.set_linked_file(active_f)

        if self.camera_index == "synthetic" and not self.force_calibrate:
            # Synthetic simulation mode for automated testing / headless verification:
            # Directly show overlay and debug widget without blocking on interactive human calibration.
            self.overlay.show()
            self.debug_widget.show()
        elif not has_profile or self.force_calibrate:
            logger.info("[INFO] No calibration profile found. Starting initial 5-point calibration...")
            self.debug_widget.show()
            self.launch_calibration()
        else:
            self.overlay.show()
            self.debug_widget.show()

    def shutdown(self) -> None:
        """
        Gracefully terminates CameraTracker QThread, global hotkey listener, and closes all windows.
        Guarantees zero zombie threads and camera release.
        Thread-safe: schedules onto Qt main GUI thread if invoked from pynput background thread.
        """
        if threading.current_thread() is not threading.main_thread():
            QTimer.singleShot(0, self.shutdown)
            return

        if self._is_shutting_down:
            return
        self._is_shutting_down = True
        logger.info("\n[INFO] Gracefully shutting down IDEye Phase 2...")

        if self.ws_bridge is not None:
            self.ws_bridge.stop()

        if hasattr(self, "hotkey_manager") and self.hotkey_manager is not None:
            self.hotkey_manager.stop()
        if getattr(self, "window_watcher", None) is not None:
            self.window_watcher.stop()
        if getattr(self, "clipboard_history", None) is not None:
            self.clipboard_history.stop()
        if getattr(self, "telemetry_manager", None) is not None:
            self.telemetry_manager.stop()

        if hasattr(self, "tray_icon") and self.tray_icon is not None:
            self.tray_icon.hide()

        if self.overlay is not None:
            try:
                self.overlay.release_freelook_controls()
            except Exception:
                pass

        if self.tracker is not None:
            self.tracker.stop()
            self.tracker.wait(2000)
            self.tracker.release()

        if self.overlay is not None:
            self.overlay.close()

        if self.debug_widget is not None:
            self.debug_widget.close()

        if self.calibration_ui is not None:
            self.calibration_ui.close()

        self.qapp.quit()
        logger.info("[INFO] IDEye Phase 2 terminated cleanly.")

    def run(self) -> int:
        """Runs the Qt event loop until termination."""
        self.start()
        return self.qapp.exec()
