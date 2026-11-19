"""Geometry, calibration flow and macro editor."""

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


class AppCalibrationMixin:
    """Geometry, calibration flow and macro editor."""

    def open_macro_editor(self) -> None:
        """Opens the Phase 8.2 custom 3x3 cell editor."""
        dialog = CustomMacroDialog(
            macro_manager=self.macro_manager,
            mode_manager=self.mode_manager,
            on_apply=self.overlay.refresh_custom_macros,
            parent=self.debug_widget,
        )
        dialog.exec()
        self.overlay.refresh_custom_macros()
        self.overlay.update()

    def _on_mar_threshold_changed(self, value: float) -> None:
        """Applies a live MAR threshold from the debug slider or Step 6."""
        mar = max(0.25, min(0.70, float(value)))
        config.MAR_THRESHOLD = mar
        if hasattr(self.tracker, "gesture_detector") and self.tracker.gesture_detector is not None:
            if hasattr(self.tracker.gesture_detector, "set_mar_calibration"):
                self.tracker.gesture_detector.set_mar_calibration(mar)
            else:
                self.tracker.gesture_detector.mar_threshold = mar
                self.tracker.gesture_detector.release_threshold = max(0.20, mar - 0.10)
        self.debug_widget.set_mar_threshold(mar, emit=False)
        self.settings_manager.set("mar_threshold", mar)
        self.settings_manager.set("mar_calibrated", True)
        if self.overlay is not None:
            if hasattr(self.overlay, "set_mar_threshold"):
                self.overlay.set_mar_threshold(mar, calibrated=True)
            self.overlay.last_action_desc = f"Umbral MAR: {mar:.2f}"
            self.overlay.update()

    def _on_window_mode_requested(self, mode_id: str, subprofile: str) -> None:
        """Applies the FreeLook gaming/desktop sub-profile from the watcher."""
        if mode_id == "sniper" and hasattr(self.overlay, "set_gaming_profile"):
            if self.overlay.current_context_mode_id != "sniper":
                self.overlay._sniper_previous_mode = self.overlay.current_context_mode_id
            self.overlay.set_gaming_profile(subprofile == "gaming")

    def _on_block_activated(self, block_idx: int, action: str) -> None:
        """Handles actions triggered from macro blocks."""
        try:
            if hasattr(self.overlay, "current_node") and self.overlay.current_node:
                curr_node = self.overlay.current_node
                if 0 <= block_idx < len(curr_node.items):
                    item = curr_node.items[block_idx]
                    label = item.label
                    msg = f"\n[IDEye ACTION] [CLICK] Bloque {block_idx + 1} Activado: '{label}' -> Accion: {action} (Nodo: {self.overlay.current_node_id})"
                    try:
                        logger.info(msg)
                    except UnicodeEncodeError:
                        logger.info(msg.encode("ascii", errors="replace").decode("ascii"))
                    return
            label = config.MACRO_BLOCKS[block_idx]["label"] if 0 <= block_idx < len(config.MACRO_BLOCKS) else f"Block {block_idx}"
            msg = f"\n[IDEye ACTION] [CLICK] Bloque {block_idx + 1} Activado: '{label}' -> Accion: {action}"
            try:
                logger.info(msg)
            except UnicodeEncodeError:
                logger.info(msg.encode("ascii", errors="replace").decode("ascii"))
        except Exception:
            pass

    def _configure_geometry(self) -> None:
        """Configures geometry of overlay across the usable desktop area."""
        screen = QApplication.primaryScreen()
        if screen:
            # availableGeometry() excludes the Windows taskbar, so the HUD can
            # never cover the bottom taskbar or overflow the usable desktop.
            screen_geo = screen.availableGeometry()
            self.overlay.setGeometry(screen_geo)
            if getattr(self, "screen_manager", None) is not None:
                self.screen_manager.bind_gaze_to_screen(screen)
            elif self.tracker is not None and hasattr(self.tracker, "gaze_estimator"):
                self.tracker.gaze_estimator.set_target_screen(
                    screen_geo.width(), screen_geo.height()
                )
            dw_x = screen_geo.x() + screen_geo.width() - config.DEBUG_WINDOW_WIDTH - 12
            # Top-aligned with the HUD header so the panel and the bar share one edge.
            dw_y = screen_geo.y() + int(getattr(self.overlay, "margin", 12))
            self.debug_widget.move(max(screen_geo.x(), dw_x), max(screen_geo.y(), dw_y))
            self.overlay.refresh_grid_right_margin(animate=False)
            # Re-anchor if the usable desktop changes (resolution, taskbar, dock).
            if not getattr(self, "_geometry_signal_connected", False):
                try:
                    screen.availableGeometryChanged.connect(
                        lambda _geo=None: self._configure_geometry()
                    )
                    self._geometry_signal_connected = True
                except Exception:
                    pass
        else:
            self.overlay.resize(config.FRAME_WIDTH, config.FRAME_HEIGHT)

    def launch_calibration(self) -> None:
        """Launches the full-screen 5-point calibration interface."""
        logger.info("[INFO] Launching 5-Point Calibration UI...")
        self.overlay.hide()
        if hasattr(self, "debug_widget") and self.debug_widget is not None:
            self.debug_widget.hide()
        self._suspend_hud_input_for_calibration()

        self.calibration_ui = CalibrationUI(
            gaze_estimator=self.tracker.gaze_estimator,
            profile_path=self.profile_path,
            auto_mar_enabled=True,
            settings_manager=self.settings_manager,
            sound_feedback=self.sound_feedback,
        )
        self.tracker.raw_gaze_updated.connect(self.calibration_ui.on_raw_gaze_updated)
        self.tracker.raw_components_updated.connect(self.calibration_ui.on_raw_components_updated)
        self.tracker.gaze_updated.connect(self.calibration_ui.on_gaze_updated)
        self.tracker.gesture_triggered.connect(self.calibration_ui.on_gesture_triggered)
        self.tracker.frame_ready.connect(self._on_calibration_frame)
        self.calibration_ui.mar_threshold_calibrated.connect(self._on_mar_threshold_changed)
        self.calibration_ui.calibration_finished.connect(self._on_calibration_finished)

        active_screen = None
        if getattr(self, "screen_manager", None) is not None:
            active_screen = self.screen_manager.current_screen()
        active_screen = active_screen or QApplication.primaryScreen()
        if active_screen is not None:
            try:
                self.calibration_ui.setScreen(active_screen)
            except Exception:
                pass
        self.calibration_ui.showFullScreen()

    @pyqtSlot(object, float)
    def _suspend_hud_input_for_calibration(self) -> None:
        """Stops hidden HUD/gesture handlers from receiving calibration mouth clicks.

        A hidden overlay still receives tracker signals. During calibration those
        clicks could start/replace an AI QThread or inject code, which is both
        incorrect and a native Qt crash risk.
        """
        if self._hud_input_suspended:
            return
        for signal, slot in (
            (self.tracker.gaze_updated, self.overlay.on_gaze_updated),
            (self.tracker.gaze_updated, self._on_gaze_for_screen_handover),
            (self.tracker.gesture_triggered, self.overlay.on_gesture_triggered),
            (self.tracker.frame_ready, self.overlay.on_mar_updated),
            (self.tracker.frame_ready, self.debug_widget.on_frame_ready),
        ):
            try:
                signal.disconnect(slot)
            except (TypeError, RuntimeError):
                pass
        self._hud_input_suspended = True

    def _resume_hud_input_after_calibration(self) -> None:
        """Reconnects HUD/gesture handlers after calibration finishes or is cancelled."""
        if not self._hud_input_suspended:
            return
        for signal, slot in (
            (self.tracker.gaze_updated, self.overlay.on_gaze_updated),
            (self.tracker.gaze_updated, self._on_gaze_for_screen_handover),
            (self.tracker.gesture_triggered, self.overlay.on_gesture_triggered),
            (self.tracker.frame_ready, self.overlay.on_mar_updated),
            (self.tracker.frame_ready, self.debug_widget.on_frame_ready),
        ):
            try:
                signal.connect(slot)
            except (TypeError, RuntimeError):
                pass
        self._hud_input_suspended = False

    def _on_gaze_for_screen_handover(self, _gx: float, _gy: float) -> None:
        """Feeds head yaw to the bezel-crossing state machine."""
        try:
            yaw = float(getattr(self.tracker.gaze_estimator, "last_head_yaw", 0.0))
            self.screen_manager.update_head_yaw(yaw)
        except Exception:
            pass

    def _on_calibration_frame(self, _frame: Any, mar: float) -> None:
        if self.calibration_ui is not None:
            self.calibration_ui.on_mar_updated(mar)
            if _frame is not None and hasattr(_frame, "mean"):
                try:
                    luma = float(np.mean(_frame))
                    self.calibration_ui.on_lighting_updated(luma)
                except Exception:
                    pass
            if self.tracker is not None and hasattr(self.tracker, "get_latest_landmarks"):
                try:
                    lm = self.tracker.get_latest_landmarks()
                    if lm is not None:
                        self.calibration_ui.on_landmarks_updated(lm)
                except Exception:
                    pass

    def _on_calibration_finished(self, succeeded: bool) -> None:
        """Handles calibration completion/cancellation and restores overlay and debug widget."""
        logger.info(f"[INFO] Calibration completed (succeeded={succeeded}). Restoring overlay HUD.")
        if self.calibration_ui is not None:
            try:
                self.tracker.raw_gaze_updated.disconnect(self.calibration_ui.on_raw_gaze_updated)
                self.tracker.raw_components_updated.disconnect(self.calibration_ui.on_raw_components_updated)
            except Exception:
                pass
            try:
                self.tracker.gaze_updated.disconnect(self.calibration_ui.on_gaze_updated)
                self.tracker.gesture_triggered.disconnect(self.calibration_ui.on_gesture_triggered)
                self.tracker.frame_ready.disconnect(self._on_calibration_frame)
                self.calibration_ui.mar_threshold_calibrated.disconnect(self._on_mar_threshold_changed)
            except Exception:
                pass
            self.calibration_ui.close()
            self.calibration_ui = None

        self._resume_hud_input_after_calibration()
        self.overlay.show()
        if hasattr(self, "debug_widget") and self.debug_widget is not None:
            self.debug_widget.show()

    def reset_calibration(self) -> None:
        """
        Emergency reset of calibration: restores safe neutral/uncalibrated state,
        resets GazeEstimator weights and anchors, and invalidates any corrupt profile.
        Thread-safe: schedules onto Qt main GUI thread if invoked from pynput background thread.
        """
        if threading.current_thread() is not threading.main_thread():
            QTimer.singleShot(0, self.reset_calibration)
            return

        logger.warning("[INFO] [EMERGENCIA] Resetting calibration to safe neutral baselines...")
        if self.tracker is not None:
            self.tracker.gaze_estimator.reset()

        if os.path.exists(self.profile_path):
            try:
                bak_path = self.profile_path + ".bak"
                if os.path.exists(bak_path):
                    os.remove(bak_path)
                os.rename(self.profile_path, bak_path)
                logger.info(f"[INFO] Moved active calibration profile to '{bak_path}'.")
            except Exception as e:
                logger.warning(f"[AVISO] Could not backup calibration profile: {e}")

        if self.tracker is not None:
            try:
                if self.tracker.gaze_estimator.clear_monitor_profiles(backup=True):
                    logger.info("[INFO] Moved per-monitor profiles to backup.")
            except Exception as e:
                logger.warning(f"[AVISO] Could not backup per-monitor profiles: {e}")

        defaults = self.settings_manager.reset_to_defaults()
        self._apply_settings(defaults)
        if self.overlay is not None:
            self.overlay.last_action_desc = "Calibración reseteada"
            self.overlay.update()
