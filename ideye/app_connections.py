"""Signal wiring and editor/agentic event handlers."""

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


class AppConnectionsMixin:
    """Signal wiring and editor/agentic event handlers."""

    def _setup_connections(self) -> None:
        """Connects signals between tracker, overlay, debug monitor, and lifecycle."""
        # Tracker signals to Overlay
        self.tracker.gaze_updated.connect(self.overlay.on_gaze_updated)
        self.tracker.gaze_updated.connect(self._on_gaze_for_screen_handover)
        self.tracker.gesture_triggered.connect(self.overlay.on_gesture_triggered)
        self.tracker.face_lost.connect(self.overlay.reset_freelook_pointer)
        self.tracker.health_alert.connect(self.overlay.show_health_alert)
        if hasattr(self.tracker, "gaze_estimator") and self.tracker.gaze_estimator is not None:
            self.overlay.set_gaze_estimator(self.tracker.gaze_estimator)

        # Tracker signals to DebugWidget
        self.tracker.frame_ready.connect(self.debug_widget.on_frame_ready)
        self.tracker.frame_ready.connect(self.overlay.on_mar_updated)

        # WebSocket Bridge connections (Phase 5)
        if self.ws_bridge is not None:
            self.ws_bridge.client_connected.connect(
                lambda client_id: self.debug_widget.set_vscode_connected(True)
            )
            self.ws_bridge.client_disconnected.connect(
                lambda client_id: self.debug_widget.set_vscode_connected(self.ws_bridge.is_connected)
            )
            self.ws_bridge.client_connected.connect(
                lambda *_: self.overlay.set_vscode_connected(True)
            )
            self.ws_bridge.client_disconnected.connect(
                lambda *_: self.overlay.set_vscode_connected(self.ws_bridge.is_connected)
            )
            self.ws_bridge.editor_state_received.connect(self._on_vscode_editor_state_received)

        # Multi-language synchronization between overlay, debug monitor, and context reader
        self.debug_widget.language_changed.connect(self.overlay.set_language)
        self.debug_widget.language_changed.connect(self.context_reader.set_active_language)
        self.debug_widget.language_changed.connect(self.mode_manager.set_language)
        self.overlay.language_changed.connect(self.debug_widget.set_language)
        self.overlay.language_changed.connect(self.context_reader.set_active_language)
        self.overlay.language_changed.connect(self.mode_manager.set_language)

        # Interactive debug tuning to tracker gaze estimator
        if hasattr(self.tracker, "gaze_estimator") and self.tracker.gaze_estimator is not None:
            self.debug_widget.set_gaze_estimator(self.tracker.gaze_estimator)
            self.debug_widget.sensitivity_x_changed.connect(
                lambda v: self.tracker.gaze_estimator.set_sensitivity(head_x=v, iris_x=v * 1.35)
            )
            self.debug_widget.sensitivity_y_changed.connect(
                lambda v: self.tracker.gaze_estimator.set_sensitivity(head_y=v, iris_y=v * 1.30)
            )
            self.debug_widget.anti_jitter_changed.connect(
                lambda v: self.tracker.gaze_estimator.set_anti_jitter_damping(v)
            )
            self.debug_widget.tracking_mode_changed.connect(self._on_tracking_mode_changed)
            self.debug_widget.sensitivity_x_changed.connect(
                lambda v: self.settings_manager.set("sensitivity_x", v)
            )
            self.debug_widget.sensitivity_y_changed.connect(
                lambda v: self.settings_manager.set("sensitivity_y", v)
            )
            self.debug_widget.anti_jitter_changed.connect(
                lambda v: self.settings_manager.set("one_euro_level", int(v))
            )
            self.debug_widget.mar_threshold_changed.connect(self._on_mar_threshold_changed)
            self.debug_widget.collapsed_toggled.connect(
                lambda v: self.settings_manager.set("debug_panel_collapsed", bool(v))
            )
            self.debug_widget.language_changed.connect(
                lambda lang: self.settings_manager.set("active_language", str(lang).lower())
            )
            self.debug_widget.adaptive_ast_toggled.connect(
                lambda v: self.settings_manager.set("adaptive_ast_enabled", bool(v))
            )
            self.debug_widget.tracking_mode_changed.connect(
                lambda mode: self.settings_manager.set("tracking_mode", str(mode).upper())
            )

        # Overlay actions
        self.overlay.block_activated.connect(self._on_block_activated)
        self.overlay.tracking_mode_cycle_requested.connect(self.debug_widget.cycle_tracking_mode)
        self.overlay.autofix_requested.connect(self._apply_autofix)
        self.overlay.ast_jump_requested.connect(self._on_ast_jump_requested)
        self.overlay.agentic_prompt_requested.connect(self._on_agentic_prompt_requested)
        self.overlay.reading_mode_toggled.connect(self.tracker.set_paused)
        self.overlay.gaze_scroll_toggled.connect(
            lambda v: self.settings_manager.set("gaze_scroll_enabled", bool(v))
        )
        self.overlay.ghost_peek_toggled.connect(
            lambda v: self.settings_manager.set("ghost_peek_enabled", bool(v))
        )
        if hasattr(self.tracker, "power_state_changed"):
            self.tracker.power_state_changed.connect(self._on_power_state_changed)
        self.debug_widget.eco_sleep_toggled.connect(self._on_eco_sleep_toggled)
        self.debug_widget.ghost_peek_toggled.connect(self._on_ghost_peek_toggled)
        self.debug_widget.reduced_motion_toggled.connect(self._on_reduced_motion_toggled)
        self.debug_widget.winks_toggled.connect(self._on_winks_toggled)
        self.debug_widget.wink_mouth_only_toggled.connect(self._on_wink_mouth_only_toggled)

        # Context reader & AI status connections
        self.debug_widget.file_linked.connect(self.context_reader.set_active_file)
        self.debug_widget.file_linked.connect(self.overlay.on_file_linked)
        self.overlay.ai_status_updated.connect(self.debug_widget.update_ai_status)
        self.debug_widget.adaptive_ast_toggled.connect(self.overlay.set_adaptive_ast_enabled)
        self.overlay.adaptive_ast_toggled.connect(self.debug_widget.set_adaptive_ast_enabled)
        self.overlay.adaptive_ast_toggled.connect(
            lambda v: self.settings_manager.set("adaptive_ast_enabled", bool(v))
        )
        self.overlay.language_changed.connect(
            lambda lang: self.settings_manager.set("active_language", str(lang).lower())
        )
        self.overlay.sound_enabled_changed.connect(
            lambda v: self.settings_manager.set("sound_enabled", bool(v))
        )
        self.overlay.auto_switch_changed.connect(
            lambda v: self.settings_manager.set("auto_switch_enabled", bool(v))
        )
        self.overlay.ast_context_detected.connect(self.debug_widget.update_ast_context)

        # Controls from UI to application lifecycle
        self.debug_widget.recalibrate_requested.connect(self.launch_calibration)
        self.debug_widget.reset_calibration_requested.connect(self.reset_calibration)
        self.debug_widget.macro_editor_requested.connect(self.open_macro_editor)
        self.debug_widget.exit_requested.connect(self.shutdown)
        self.overlay.exit_requested.connect(self.shutdown)

        # Phase 9: clipboard, foreground watcher and telemetry
        self.overlay.text_injected.connect(self.telemetry_manager.record_injection)
        self.overlay.mouth_clicked.connect(self.telemetry_manager.record_mouth_click)
        self.telemetry_manager.stats_changed.connect(self.debug_widget.update_telemetry)
        self.debug_widget.telemetry_reset_requested.connect(self.telemetry_manager.reset)
        self.debug_widget.test_sound_requested.connect(self.sound_feedback.test_play)
        self.debug_widget.open_guide_requested.connect(self._open_interactive_guide)
        self.debug_widget.health_guard_toggled.connect(self._on_health_guard_toggled)
        self.debug_widget.micro_gestures_toggled.connect(self._on_micro_gestures_toggled)
        self.debug_widget.low_light_toggled.connect(self._on_low_light_toggled)
        self.debug_widget.cap_mode_toggled.connect(self._on_cap_mode_toggled)
        self.tracker.frame_ready.connect(self._on_lighting_frame)
        self.overlay.interactive_guide_requested.connect(self._open_interactive_guide)
        self.window_watcher.foreground_changed.connect(self.debug_widget.set_foreground_window)
        self.window_watcher.foreground_changed.connect(self._on_foreground_document_context)
        self.window_watcher.mode_requested.connect(self._on_window_mode_requested)
        self.window_watcher.profile_requested.connect(self.overlay.set_game_profile)
        self.mode_manager.mode_changed.connect(
            lambda mode_id, *_: self.telemetry_manager.set_current_mode(mode_id)
        )
        self.telemetry_manager.set_current_mode(self.mode_manager.current_mode_id)
        self.debug_widget.update_telemetry(self.telemetry_manager.stats())

        # Qt application about-to-quit hook
        self.qapp.aboutToQuit.connect(self.shutdown)

    def _on_foreground_document_context(self, title: str, process: str) -> None:
        """Routes Google Docs, Notion, Overleaf and Word to the shadow buffer."""
        active = self.context_reader.set_document_context(title, process)
        coding_mode = self.mode_manager.modes.get("coding") if self.mode_manager else None
        if coding_mode is not None and hasattr(coding_mode, "set_context"):
            coding_mode.set_context(
                symbols=self.context_reader.extract_local_symbols() if not active else [],
                document_context=active,
            )
        if active:
            self.overlay.last_action_desc = f"Documento: {title[:48]}"
            self.overlay.update()

    def _on_vscode_editor_state_received(self, state: Dict[str, Any]) -> None:
        """
        Handles real-time editor state stream from native VS Code extension over WebSocket.
        Synchronizes active file path, programming language, and AST context across IDEye.
        """
        self.overlay._vscode_editor_state = dict(state or {})
        self.context_reader.update_editor_snapshot(state or {})
        file_path = state.get("filePath") or state.get("file_path")
        language_id = state.get("languageId") or state.get("language_id")

        if file_path:
            self.context_reader.set_active_file(file_path)
            self.debug_widget.set_linked_file(file_path)
            self.overlay.on_file_linked(file_path)
            coding_mode = self.mode_manager.modes.get("coding") if self.mode_manager else None
            if coding_mode is not None and hasattr(coding_mode, "set_context"):
                coding_mode.set_context(
                    symbols=state.get("local_symbols") or self.context_reader.extract_local_symbols(),
                    document_context=False,
                )

        if language_id:
            normalized_lang = normalize_language(language_id)
            self.context_reader.set_active_language(normalized_lang)
            self.overlay.set_language(normalized_lang)
            self.debug_widget.set_language(normalized_lang)
            if hasattr(self, "mode_manager") and self.mode_manager is not None:
                self.mode_manager.set_language(normalized_lang)

        diagnostics = state.get("diagnostics") or []
        if diagnostics:
            self.overlay.set_diagnostics(diagnostics)
        elif not (getattr(self, "ws_bridge", None) and self.ws_bridge.is_connected):
            self.overlay.set_diagnostics(self.overlay.diagnostics_fixer.collect_local())
        else:
            self.overlay.set_diagnostics([])

        # Auto-switch context mode from the full editor state (file path, context, language)
        if hasattr(self, "mode_manager") and self.mode_manager is not None:
            self.mode_manager.handle_editor_state(state)

    def _on_ast_jump_requested(self, line: int) -> None:
        bridge = getattr(self, "ws_bridge", None)
        if bridge is not None and bridge.is_connected and hasattr(bridge, "send_jump_to_line"):
            bridge.send_jump_to_line(int(line))
            self.overlay.last_action_desc = f"AST: saltando a L{int(line)}"
        else:
            try:
                self.overlay.code_injector.send_key("CTRL+SHIFT+O")
            except Exception:
                pass
            self.overlay.last_action_desc = "AST: abriendo símbolos del editor"
        self.overlay.update()

    def _on_agentic_prompt_requested(
        self,
        action_id: str,
        prompt: str,
        queue_only: bool = False,
    ) -> None:
        """Sends a gaze-fired engineering prompt to VS Code or the MCP queue."""
        launcher = getattr(self.overlay, "agentic_launcher", None)
        if launcher is None:
            return
        bridge = getattr(self, "ws_bridge", None)
        result = launcher.dispatch(
            action_id,
            prompt,
            bridge=bridge,
            queue_only=bool(queue_only),
            selection_only=True,
        )
        if result.get("sent") and not queue_only:
            self.overlay.last_action_desc = (
                f"IA: {result.get('label', action_id)} enviado a VS Code"
            )
        else:
            self.overlay.copy_agentic_prompt(prompt)
            self.overlay.last_action_desc = "ORDEN IA LISTA EN PORTAPAPELES / MCP"
        self.overlay.update()
