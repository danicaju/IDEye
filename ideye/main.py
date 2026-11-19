"""
IDEye - Main Entrypoint & Grid Orchestrator (Phase 1)
3x3 Macro-Block Grid with Threaded Hybrid Gaze Tracking & Facial Gesture (MAR) Trigger.

Architecture:
- Background worker thread for camera capture & MediaPipe FaceMesh processing (<35ms budget).
- Silky smooth UI loop (60+ FPS) rendering the 3x3 Macro-Block programming grid.
- Eye blink suppression (prevents cursor jumps when blinking).
- Distance-adaptive center calibration.
- Full visibility for all 9 blocks (Block 9 never obscured by mini-feed).
- Guaranteed crash-free face loss handling, pause/rest zone support, and clean resource destruction.
"""

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

from ideye.app_draw import MainAppDrawMixin  # noqa: F401
from ideye.app_legacy import IDEyeMainApp  # noqa: F401
from ideye.app_core import IDEyeApplication  # noqa: F401


def main():
    """CLI Entry point."""
    parser = argparse.ArgumentParser(description="IDEye - Assistive Eye-Tracking IDE (Phase 2)")
    parser.add_argument("--camera", default=config.CAMERA_INDEX, help="Camera device index or 'synthetic'")
    parser.add_argument("--calibrate", action="store_true", help="Force 5-point calibration on startup")
    parser.add_argument("--profile", default=config.CALIBRATION_PROFILE_PATH, help="Path to calibration profile JSON")
    parser.add_argument("--no-threads", action="store_true", help="Disable background worker thread")
    parser.add_argument("--phase1", action="store_true", help="Run legacy Phase 1 OpenCV window instead of PyQt6")
    parser.add_argument("--width", type=int, default=config.FRAME_WIDTH, help="Canvas width (Phase 1)")
    parser.add_argument("--height", type=int, default=config.FRAME_HEIGHT, help="Canvas height (Phase 1)")
    parser.add_argument("--frames", type=int, default=None, help="Limit number of frames (for QA testing)")
    args = parser.parse_args()

    if args.phase1:
        app = IDEyeMainApp(
            camera_index=args.camera,
            canvas_width=args.width,
            canvas_height=args.height,
            threaded=not args.no_threads,
        )
        app.run(max_frames=args.frames)
    else:
        app = IDEyeApplication(
            camera_index=args.camera,
            profile_path=args.profile,
            force_calibrate=args.calibrate,
            threaded=not args.no_threads,
        )
        sys.exit(app.run())


if __name__ == "__main__":
    main()

