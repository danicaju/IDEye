"""Grid, pointer, mini-feed and status-bar drawing for the legacy OpenCV window."""

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


class MainAppDrawMixin:
    """Grid, pointer, mini-feed and status-bar drawing for the legacy OpenCV window."""

    def _get_block_rect(self, row: int, col: int) -> Tuple[int, int, int, int]:
        """Returns (x1, y1, x2, y2) bounding box for a given grid cell taking header into account."""
        grid_top = self.header_height
        avail_h = self.canvas_height - grid_top
        cell_w = self.canvas_width // self.grid_cols
        cell_h = avail_h // self.grid_rows

        x1 = col * cell_w
        y1 = grid_top + row * cell_h
        x2 = self.canvas_width if col == self.grid_cols - 1 else (col + 1) * cell_w
        y2 = self.canvas_height if row == self.grid_rows - 1 else grid_top + (row + 1) * cell_h
        return x1, y1, x2, y2

    def _get_hovered_block(self, norm_x: float, norm_y: float) -> int:
        """Calculates which of the 9 macro-blocks contains the gaze point."""
        col = int(np.clip(int(norm_x * self.grid_cols), 0, self.grid_cols - 1))
        row = int(np.clip(int(norm_y * self.grid_rows), 0, self.grid_rows - 1))
        return row * self.grid_cols + col

    def _draw_grid(
        self,
        canvas: np.ndarray,
        hovered_idx: int,
        now: float,
    ) -> None:
        """Renders the 3x3 Macro-Block grid onto the canvas with full visibility for all blocks."""
        is_flash_active = (now - self.last_click_timestamp) < config.CLICK_FLASH_DURATION_SEC

        for row in range(self.grid_rows):
            for col in range(self.grid_cols):
                idx = row * self.grid_cols + col
                x1, y1, x2, y2 = self._get_block_rect(row, col)

                block_info = self.macro_blocks[idx]
                is_hovered = (idx == hovered_idx)
                is_clicked = is_flash_active and (idx == self.last_clicked_block_idx)

                # Determine background color
                if is_clicked:
                    bg_color = config.COLOR_BLOCK_CLICK
                    border_color = (255, 255, 255)
                    text_color = config.COLOR_TEXT_CLICK
                elif self.is_paused and idx == 4:
                    bg_color = (40, 30, 20)
                    border_color = config.COLOR_PAUSED_BORDER
                    text_color = (255, 200, 80)
                elif is_hovered:
                    bg_color = config.COLOR_BLOCK_HOVER
                    border_color = config.COLOR_POINTER
                    text_color = config.COLOR_TEXT_HOVER
                else:
                    bg_color = config.COLOR_BLOCK_DEFAULT
                    border_color = config.COLOR_GRID_BORDER
                    text_color = config.COLOR_TEXT

                # Fill block with inner margin
                margin = 3
                cv2.rectangle(canvas, (x1 + margin, y1 + margin), (x2 - margin, y2 - margin), bg_color, -1)
                cv2.rectangle(canvas, (x1 + margin, y1 + margin), (x2 - margin, y2 - margin), border_color, 2 if not is_hovered else 3)

                label = block_info["label"]
                hint = block_info.get("hint", "")

                font = cv2.FONT_HERSHEY_DUPLEX
                font_scale = 0.82 if is_hovered else 0.72
                thickness = 2 if is_hovered else 1

                # Special layout for Block 9 ("9: SALIR") to guarantee it is NEVER obscured by the mini-feed
                if idx == 8:
                    # Place label and hint in the top-left area of the block
                    text_x = x1 + 24
                    text_y = y1 + 38
                    cv2.putText(canvas, label, (text_x, text_y), font, font_scale, text_color, thickness, cv2.LINE_AA)
                    if hint:
                        hint_scale = 0.44
                        hint_color = config.COLOR_TEXT_CLICK if is_clicked else config.COLOR_TEXT_DIM
                        cv2.putText(canvas, hint, (text_x, text_y + 24), font, hint_scale, hint_color, 1, cv2.LINE_AA)
                elif idx == 4 and self.is_paused:
                    # Special label for paused resting zone
                    pause_lbl = "5: EN REPOSO"
                    (tw, th), _ = cv2.getTextSize(pause_lbl, font, font_scale, thickness)
                    text_x = x1 + (x2 - x1 - tw) // 2
                    text_y = y1 + (y2 - y1) // 2 - 5
                    cv2.putText(canvas, pause_lbl, (text_x, text_y), font, font_scale, text_color, thickness, cv2.LINE_AA)
                    p_hint = "Mirada fija / Clic para reanudar"
                    (hw, hh), _ = cv2.getTextSize(p_hint, font, 0.45, 1)
                    cv2.putText(canvas, p_hint, (x1 + (x2 - x1 - hw) // 2, text_y + 26), font, 0.45, (255, 180, 50), 1, cv2.LINE_AA)
                else:
                    # Standard centered label
                    (tw, th), _ = cv2.getTextSize(label, font, font_scale, thickness)
                    text_x = x1 + (x2 - x1 - tw) // 2
                    text_y = y1 + (y2 - y1) // 2 - 5
                    cv2.putText(canvas, label, (text_x, text_y), font, font_scale, text_color, thickness, cv2.LINE_AA)

                    if hint:
                        hint_scale = 0.45
                        hint_color = config.COLOR_TEXT_CLICK if is_clicked else config.COLOR_TEXT_DIM
                        (hw, hh), _ = cv2.getTextSize(hint, font, hint_scale, 1)
                        hint_x = x1 + (x2 - x1 - hw) // 2
                        hint_y = text_y + 26
                        cv2.putText(canvas, hint, (hint_x, hint_y), font, hint_scale, hint_color, 1, cv2.LINE_AA)

    def _draw_gaze_pointer(self, canvas: np.ndarray, norm_x: float, norm_y: float) -> None:
        """Renders an anti-aliased smooth gaze cursor with a reticle."""
        grid_top = self.header_height
        avail_h = self.canvas_height - grid_top

        px = int(np.clip(norm_x * self.canvas_width, 0, self.canvas_width - 1))
        py = int(np.clip(grid_top + norm_y * avail_h, grid_top, self.canvas_height - 1))

        if self.is_paused:
            # Paused reticle (soft orange)
            cv2.circle(canvas, (px, py), 14, config.COLOR_PAUSED_BORDER, 2, cv2.LINE_AA)
            cv2.circle(canvas, (px, py), 4, (255, 200, 80), -1, cv2.LINE_AA)
            return

        # Outer ring
        cv2.circle(canvas, (px, py), 18, config.COLOR_POINTER, 2, cv2.LINE_AA)
        # Inner glow dot
        cv2.circle(canvas, (px, py), 5, (255, 255, 255), -1, cv2.LINE_AA)
        # Subtle crosshair
        ch_len = 8
        cv2.line(canvas, (px - ch_len, py), (px + ch_len, py), config.COLOR_POINTER_OUTLINE, 1, cv2.LINE_AA)
        cv2.line(canvas, (px, py - ch_len), (px, py + ch_len), config.COLOR_POINTER_OUTLINE, 1, cv2.LINE_AA)

    def _draw_mini_feed_and_mar(
        self,
        canvas: np.ndarray,
        camera_frame: Optional[np.ndarray],
        face_landmarks: Any,
        current_mar: float,
        hold_progress: float,
        face_detected: bool,
        is_flash_active: bool,
        hovered_idx: int,
    ) -> None:
        """
        Renders the mini-feed in the bottom-right corner with a MAR progress bar.
        Synchronizes border glow and click flash with Block 9 so Block 9 is completely responsive.
        """
        if not self.show_mini_feed:
            return

        mw = config.MINI_FEED_WIDTH
        mh = config.MINI_FEED_HEIGHT
        margin = config.MINI_FEED_MARGIN

        # Position at bottom-right corner (inside Block 9 bounds, leaving top label clear)
        fx1 = self.canvas_width - mw - margin
        fy1 = self.canvas_height - mh - margin
        fx2 = self.canvas_width - margin
        fy2 = self.canvas_height - margin

        # Synchronize mini-feed border with Block 9 hover/click
        is_block_9_clicked = is_flash_active and (self.last_clicked_block_idx == 8)
        is_block_9_hovered = (hovered_idx == 8)

        if is_block_9_clicked:
            border_col = config.COLOR_BLOCK_CLICK
            border_thick = 3
        elif is_block_9_hovered:
            border_col = config.COLOR_BLOCK_HOVER
            border_thick = 2
        elif hold_progress >= 0.99:
            border_col = config.COLOR_BAR_READY
            border_thick = 2
        else:
            border_col = config.COLOR_GRID_BORDER
            border_thick = 1

        # Background container card with header for MAR meter
        header_h = 28
        cv2.rectangle(canvas, (fx1 - 3, fy1 - header_h), (fx2 + 3, fy2 + 3), (16, 18, 22), -1)
        cv2.rectangle(canvas, (fx1 - 3, fy1 - header_h), (fx2 + 3, fy2 + 3), border_col, border_thick)

        # Title banner
        title = "MINI-FEED"
        cv2.putText(canvas, title, (fx1 + 4, fy1 - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.40, config.COLOR_TEXT_DIM, 1, cv2.LINE_AA)

        # MAR Value label
        mar_txt = f"MAR: {current_mar:.2f}"
        if current_mar >= config.MAR_THRESHOLD:
            mar_txt += f" ({int(hold_progress * 100)}%)"
        cv2.putText(canvas, mar_txt, (fx2 - 95, fy1 - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.38, config.COLOR_BAR_READY if current_mar >= config.MAR_THRESHOLD else config.COLOR_TEXT, 1, cv2.LINE_AA)

        # ======================================================================
        # MAR Visual Gauge Bar
        # ======================================================================
        bar_x1 = fx1 + 72
        bar_y1 = fy1 - 20
        bar_w = mw - 175
        bar_h = 7

        # Background bar
        cv2.rectangle(canvas, (bar_x1, bar_y1), (bar_x1 + bar_w, bar_y1 + bar_h), config.COLOR_BAR_BG, -1)

        # MAR fill
        norm_mar = float(np.clip(current_mar, 0.0, 1.0))
        fill_w = int(norm_mar * bar_w)
        fill_color = config.COLOR_BAR_READY if current_mar >= config.MAR_THRESHOLD else config.COLOR_BAR_FILL
        if fill_w > 0:
            cv2.rectangle(canvas, (bar_x1, bar_y1), (bar_x1 + fill_w, bar_y1 + bar_h), fill_color, -1)

        # Threshold line marker
        thresh_x = bar_x1 + int(config.MAR_THRESHOLD * bar_w)
        cv2.line(canvas, (thresh_x, bar_y1 - 2), (thresh_x, bar_y1 + bar_h + 2), config.COLOR_THRESHOLD_LINE, 2)

        # Camera feed
        if camera_frame is not None:
            annotated = camera_frame.copy()
            if face_landmarks is not None:
                self.tracker.draw_debug_landmarks(annotated, face_landmarks)
            resized = cv2.resize(annotated, (mw, mh), interpolation=cv2.INTER_AREA)
            canvas[fy1:fy2, fx1:fx2] = resized
        else:
            cv2.rectangle(canvas, (fx1, fy1), (fx2, fy2), (28, 30, 36), -1)
            cv2.putText(canvas, "SIN CAMARA", (fx1 + mw // 4, fy1 + mh // 2), cv2.FONT_HERSHEY_SIMPLEX, 0.55, config.COLOR_TEXT_DIM, 1)

        # Face loss overlay banner on feed
        if not face_detected:
            overlay = canvas[fy1:fy2, fx1:fx2].copy()
            cv2.rectangle(overlay, (0, 0), (mw, mh), (0, 0, 180), -1)
            cv2.addWeighted(overlay, 0.50, canvas[fy1:fy2, fx1:fx2], 0.50, 0, canvas[fy1:fy2, fx1:fx2])
            cv2.putText(canvas, "ROSTRO PERDIDO", (fx1 + 35, fy1 + mh // 2), cv2.FONT_HERSHEY_DUPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)

    def _draw_status_bar(self, canvas: np.ndarray, face_detected: bool, is_calibrated: bool) -> None:
        """Renders top header with tracking status, shortcuts, and FPS."""
        cv2.rectangle(canvas, (0, 0), (self.canvas_width, self.header_height), (14, 16, 19), -1)
        cv2.line(canvas, (0, self.header_height), (self.canvas_width, self.header_height), config.COLOR_GRID_BORDER, 1)

        # Brand
        brand = "IDEye v0.1.0 [FASE 1: Tracking Hibrido + Gestos]"
        cv2.putText(canvas, brand, (15, 24), cv2.FONT_HERSHEY_DUPLEX, 0.52, (255, 215, 0), 1, cv2.LINE_AA)

        # Status guide
        guide = "[C] Calibrar  |  [Ctrl+Alt+Q] Emergencia  |  [M] Mini-feed  |  [P] Pausa  |  [Q/ESC] Salir"
        cv2.putText(canvas, guide, (360, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.44, config.COLOR_TEXT_DIM, 1, cv2.LINE_AA)

        # Tracking status badge
        if not face_detected:
            status_text = "ROSTRO PERDIDO"
            status_color = config.COLOR_WARNING
        elif self.is_paused:
            status_text = "EN REPOSO / PAUSA"
            status_color = config.COLOR_PAUSED_BORDER
        elif is_calibrated:
            sens_pct = int(self.gaze_estimator.distance_scale * 100)
            status_text = f"SEGUIMIENTO [{sens_pct}% Sens]"
            status_color = config.COLOR_BAR_READY
        else:
            status_text = "ACTIVO [Pulsa C]"
            status_color = (0, 180, 255)

        cv2.putText(canvas, status_text, (self.canvas_width - 240, 24), cv2.FONT_HERSHEY_DUPLEX, 0.44, status_color, 1, cv2.LINE_AA)

        # Face loss top warning banner
        if not face_detected:
            alert = "ALERTA: Rostro fuera de plano. Posicion congelada para evitar toques accidentales."
            (aw, ah), _ = cv2.getTextSize(alert, cv2.FONT_HERSHEY_DUPLEX, 0.55, 1)
            ax = (self.canvas_width - aw) // 2
            cv2.rectangle(canvas, (ax - 12, 44), (ax + aw + 12, 74), (0, 0, 150), -1)
            cv2.putText(canvas, alert, (ax, 65), cv2.FONT_HERSHEY_DUPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
