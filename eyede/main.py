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
    import eyede.config as config
    from eyede.core.camera_tracker import CameraTracker
    from eyede.core.gaze_estimator import GazeEstimator
    from eyede.core.gesture_detector import GestureDetector
    from eyede.core.hotkey_manager import GlobalHotkeyManager
    from eyede.core.websocket_bridge import WebSocketBridge
    from eyede.core.sound_feedback import SoundFeedbackManager
    from eyede.core.mouse_controller import OSMouseController
    from eyede.core.settings_manager import SettingsManager
    from eyede.ui.overlay_window import OverlayWindow
    from eyede.ui.debug_widget import DebugWidget
    from eyede.ui.calibration_ui import CalibrationUI
    from eyede.ui.icon_manager import IconManager
    from eyede.actions.context_reader import ContextReader
    from eyede.actions.language_support import normalize_language, get_language_display_name
    from eyede.modes.mode_manager import ModeManager
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
    from ui.overlay_window import OverlayWindow
    from ui.debug_widget import DebugWidget
    from ui.calibration_ui import CalibrationUI
    from ui.icon_manager import IconManager
    from actions.context_reader import ContextReader
    from actions.language_support import normalize_language, get_language_display_name
    from modes.mode_manager import ModeManager

import threading

from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont, QBrush
from PyQt6.QtCore import Qt, QObject, QTimer


class EyeDEMainApp:
    """
    Orchestrates the Phase 1 IDEye interface:
    - Threaded webcam capture with 478 MediaPipe landmarks.
    - Estimates smoothed hybrid gaze coordinates (Head + Iris with EMA and blink suppression).
    - Detects mouth opening (MAR) with debouncing & cooldown to fire CLICK events.
    - Renders an assistive 3x3 Macro-Block programming grid.
    - Displays camera mini-feed with landmark overlays and a MAR meter without obscuring Block 9.
    - Guarantees crash-free face loss handling, resting zone pause, and clean resource disposal.
    """

    def __init__(
        self,
        camera_index: Union[int, str] = config.CAMERA_INDEX,
        canvas_width: int = config.FRAME_WIDTH,
        canvas_height: int = config.FRAME_HEIGHT,
        window_name: str = "IDEye - Phase 1: Macro-Grid Vision Engine",
        threaded: bool = True,
    ):
        self.canvas_width = canvas_width
        self.canvas_height = canvas_height
        self.window_name = window_name
        self.threaded = threaded

        # Core subsystems
        self.tracker = CameraTracker(
            camera_index=camera_index,
            frame_width=canvas_width,
            frame_height=canvas_height,
            fps=config.FPS,
            mirror=config.MIRROR_CAMERA,
            max_num_faces=config.MAX_NUM_FACES,
            refine_landmarks=config.REFINE_LANDMARKS,
            min_detection_confidence=config.MIN_DETECTION_CONFIDENCE,
            min_tracking_confidence=config.MIN_TRACKING_CONFIDENCE,
            threaded=threaded,
        )

        self.gaze_estimator = GazeEstimator(
            head_weight=config.HEAD_WEIGHT,
            iris_weight=config.IRIS_WEIGHT,
            head_sensitivity_x=config.DEFAULT_HEAD_SENSITIVITY_X,
            head_sensitivity_y=config.DEFAULT_HEAD_SENSITIVITY_Y,
            iris_sensitivity_x=config.DEFAULT_IRIS_SENSITIVITY_X,
            iris_sensitivity_y=config.DEFAULT_IRIS_SENSITIVITY_Y,
            ema_alpha=config.EMA_ALPHA,
            nose_tip_idx=config.LANDMARK_NOSE_TIP,
            iris_left_center_idx=config.LANDMARK_IRIS_LEFT_CENTER,
            iris_right_center_idx=config.LANDMARK_IRIS_RIGHT_CENTER,
            left_eye_inner_idx=config.LANDMARK_LEFT_EYE_INNER,
            left_eye_outer_idx=config.LANDMARK_LEFT_EYE_OUTER,
            left_eye_top_idx=config.LANDMARK_LEFT_EYE_TOP,
            left_eye_bottom_idx=config.LANDMARK_LEFT_EYE_BOTTOM,
            right_eye_inner_idx=config.LANDMARK_RIGHT_EYE_INNER,
            right_eye_outer_idx=config.LANDMARK_RIGHT_EYE_OUTER,
            right_eye_top_idx=config.LANDMARK_RIGHT_EYE_TOP,
            right_eye_bottom_idx=config.LANDMARK_RIGHT_EYE_BOTTOM,
            tracking_mode=getattr(config, "DEFAULT_TRACKING_MODE", "PURE_IRIS"),
        )

        self.gesture_detector = GestureDetector(
            mar_threshold=config.MAR_THRESHOLD,
            release_threshold=config.MAR_RELEASE_THRESHOLD,
            hold_time_sec=config.CLICK_HOLD_TIME_SEC,
            cooldown_sec=config.CLICK_COOLDOWN_SEC,
            top_lip_idx=config.LANDMARK_MOUTH_LIP_TOP,
            bottom_lip_idx=config.LANDMARK_MOUTH_LIP_BOTTOM,
            left_corner_idx=config.LANDMARK_MOUTH_CORNER_LEFT,
            right_corner_idx=config.LANDMARK_MOUTH_CORNER_RIGHT,
        )

        # UI & Grid State
        self.grid_rows = config.GRID_ROWS
        self.grid_cols = config.GRID_COLS
        self.macro_blocks = config.MACRO_BLOCKS
        self.header_height = config.HEADER_HEIGHT

        self.active_block_idx: Optional[int] = None
        self.last_clicked_block_idx: Optional[int] = None
        self.last_click_timestamp: float = 0.0

        # Resting zone / pause state
        self.is_paused: bool = False
        self.show_mini_feed: bool = True

        # Calibration & status message timer
        self.status_message: str = "Presiona [C] mirando al centro para calibrar"
        self.status_message_time: float = time.time()

        # Performance monitoring
        self.fps: float = 0.0
        self._frame_count: int = 0
        self._fps_start_time: float = time.time()

        # Emergency Hotkey Support & Click Stabilization
        self.hotkey_manager = GlobalHotkeyManager()
        self.hotkey_manager.emergency_exit_requested.connect(self._on_emergency_exit)
        self.hotkey_manager.emergency_reset_requested.connect(self._on_emergency_reset)
        self._emergency_exit_requested: bool = False
        self._click_anchor_gaze: Optional[Tuple[float, float]] = None

    def _on_emergency_exit(self) -> None:
        """Triggered via global emergency hotkey (Ctrl+Alt+Q / F12)."""
        self._emergency_exit_requested = True

    def _on_emergency_reset(self) -> None:
        """Triggered via global emergency reset hotkey (Ctrl+Alt+R)."""
        if self.gaze_estimator is not None:
            self.gaze_estimator.reset()
        self.status_message = "Calibración reseteada a baselines seguras"
        self.status_message_time = time.time()

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

    def handle_click_event(self, block_idx: int, norm_x: float, norm_y: float) -> None:
        """Triggers the action associated with the clicked macro block."""
        self.last_clicked_block_idx = block_idx
        self.last_click_timestamp = time.time()

        block_info = self.macro_blocks[block_idx]
        action = block_info["action"]
        label = block_info["label"]

        print(f"\n[IDEye ACTION] [CLICK] Disparado en Bloque {block_idx + 1}: '{label}'")
        print(f"               Accion: {action} | Coordenada: (X={norm_x:.3f}, Y={norm_y:.3f})")

        if action == "PAUSE_RESUME":
            self.is_paused = not self.is_paused
            state_str = "PAUSADO (Zona de reposo)" if self.is_paused else "REANUDADO"
            print(f"[IDEye ACTION] Estado de seguimiento: {state_str}")
        elif action == "ACTION_EXIT":
            print("[IDEye ACTION] Bloque SALIR activado. Cerrando aplicacion...")

    def run(self, max_frames: Optional[int] = None) -> None:
        """
        Main application loop.
        
        Args:
            max_frames: Optional frame limit (useful for non-blocking automated testing).
        """
        print("=" * 60)
        print("  IDEye - Motor de Vision, Tracking Hibrido y Gestos (Fase 1)")
        print("=" * 60)
        print("Inicializando subsistemas de vision y FaceMesh (478 landmarks)...")

        if not self.tracker.start():
            print(f"[ERROR] No se pudo inicializar la camara indice {self.tracker.camera_index}.")
            return

        cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(self.window_name, self.canvas_width, self.canvas_height)

        print("[OK] Camara activa. Presiona [C] mirando al centro para calibrar.")
        print("[OK] Abre ligeramente la boca durante 150ms para disparar CLICK.")
        print("[OK] Presiona [Ctrl+Alt+Q] o [F12] o [Q/ESC] para salir limpiamente.\n")

        self.hotkey_manager.start()
        processed_frames = 0

        try:
            while True:
                if self._emergency_exit_requested:
                    print("\n[INFO] Salida de emergencia solicitada via global hotkey (Ctrl+Alt+Q / F12).")
                    break

                now = time.time()

                # Read latest frame from threaded tracker
                success, frame, face_landmarks = self.tracker.read_frame()

                if success and face_landmarks is not None:
                    # 1. Hybrid Gaze Estimation (Head + Iris with EMA & Blink Suppression)
                    if not self.is_paused:
                        gaze_x, gaze_y, face_detected, debug_info = self.gaze_estimator.estimate(face_landmarks)
                    else:
                        gaze_x, gaze_y, face_detected = 0.5, 0.5, True

                    # 2. Gesture Detection (MAR Mouth Opening Trigger)
                    click_fired, current_mar, hold_progress = self.gesture_detector.process(face_landmarks, current_time=now)

                    # Stabilization during mouth-open click hold
                    if hold_progress > 0.0:
                        if self._click_anchor_gaze is None:
                            self._click_anchor_gaze = (gaze_x, gaze_y)
                        gaze_x, gaze_y = self._click_anchor_gaze
                    else:
                        self._click_anchor_gaze = None
                else:
                    self._click_anchor_gaze = None
                    # Face lost or camera frame not yet ready: maintain safe freeze
                    gaze_x, gaze_y = self.gaze_estimator.smoothed_x, self.gaze_estimator.smoothed_y
                    face_detected = False
                    current_mar = 0.0
                    hold_progress = 0.0
                    click_fired = False

                # 3. Determine Hovered Macro-Block
                hovered_block = self._get_hovered_block(gaze_x, gaze_y)
                self.active_block_idx = hovered_block

                # 4. Handle Click & Wink Triggers
                if click_fired:
                    self.handle_click_event(hovered_block, gaze_x, gaze_y)
                    if self.macro_blocks[hovered_block]["action"] == "ACTION_EXIT":
                        break

                triggered_winks = getattr(self.gesture_detector, "triggered_gestures", [])
                if "WINK_RIGHT" in triggered_winks:
                    self.is_paused = not self.is_paused
                    self.status_message = "Modo reposo activado (Guiño derecho)" if self.is_paused else "Modo activo restaurado (Guiño derecho)"
                    self.status_message_time = time.time()
                    print(f"[INFO] {self.status_message}")

                if "WINK_LEFT" in triggered_winks and not self.is_paused:
                    self.status_message = "Guiño izquierdo: Volver / Deshacer"
                    self.status_message_time = time.time()
                    print(f"[INFO] {self.status_message}")

                # 5. Create UI Canvas
                canvas = np.full((self.canvas_height, self.canvas_width, 3), config.COLOR_BG, dtype=np.uint8)

                # 6. Render 3x3 Grid
                self._draw_grid(canvas, hovered_block, now)

                # 7. Render Smooth Gaze Cursor
                self._draw_gaze_pointer(canvas, gaze_x, gaze_y)

                # 8. Render Mini-feed & MAR Progress Bar (without blocking Block 9)
                is_flash_active = (now - self.last_click_timestamp) < config.CLICK_FLASH_DURATION_SEC
                self._draw_mini_feed_and_mar(
                    canvas, frame, face_landmarks, current_mar, hold_progress,
                    face_detected, is_flash_active, hovered_block
                )

                # 9. Render Status Bar
                self._draw_status_bar(canvas, face_detected, self.gaze_estimator.is_calibrated)

                # Display canvas
                cv2.imshow(self.window_name, canvas)

                # FPS Calculation
                self._frame_count += 1
                if now - self._fps_start_time >= 1.0:
                    self.fps = self._frame_count / (now - self._fps_start_time)
                    self._frame_count = 0
                    self._fps_start_time = now

                processed_frames += 1
                if max_frames is not None and processed_frames >= max_frames:
                    print(f"[TEST] Limite de {max_frames} fotogramas alcanzado.")
                    break

                # Keyboard interaction
                key = cv2.waitKey(1) & 0xFF
                if key in (ord('q'), ord('Q'), 27):  # 'q' or ESC
                    print("[INFO] Salida solicitada por usuario (tecla Q/ESC).")
                    break
                elif key in (ord('c'), ord('C')):
                    # Calibrate center & distance-adaptive gain
                    if face_landmarks is not None and self.gaze_estimator.calibrate_center(face_landmarks):
                        scale_pct = int(self.gaze_estimator.distance_scale * 100)
                        print(f"[INFO] [CALIB] Calibracion central completada. Escala de ganancia: {scale_pct}%.")
                    else:
                        print("[AVISO] No se pudo calibrar: rostro no detectado en el fotograma.")
                elif key in (ord('+'), ord('=')):
                    self.gaze_estimator.adjust_sensitivity(1.10)
                    print(f"[INFO] Sensibilidad aumentada (+10%).")
                elif key in (ord('-'), ord('_')):
                    self.gaze_estimator.adjust_sensitivity(0.90)
                    print(f"[INFO] Sensibilidad reducida (-10%).")
                elif key in (ord('m'), ord('M')):
                    self.show_mini_feed = not self.show_mini_feed
                    print(f"[INFO] Mini-feed {'mostrado' if self.show_mini_feed else 'ocultado'}.")
                elif key in (ord('p'), ord('P'), 32):  # 'p' or space
                    self.is_paused = not self.is_paused
                    print(f"[INFO] Modo reposo {'activado' if self.is_paused else 'desactivado'}.")
                elif key in (ord('r'), ord('R')):
                    self.gaze_estimator.reset()
                    self.gesture_detector.reset()
                    self.is_paused = False
                    print("[INFO] Estado y calibracion reseteados.")
                elif key in (ord('t'), ord('T')):
                    modes = ["PURE_IRIS", "HYBRID", "HEAD_PRIMARY"]
                    curr_idx = modes.index(self.gaze_estimator.tracking_mode) if self.gaze_estimator.tracking_mode in modes else 0
                    next_mode = modes[(curr_idx + 1) % len(modes)]
                    self.gaze_estimator.set_tracking_mode(next_mode)
                    mode_names = {"PURE_IRIS": "Solo Iris", "HYBRID": "Híbrido", "HEAD_PRIMARY": "Solo Cabeza (Recomendado)"}
                    self.status_message = f"Modo: {mode_names.get(next_mode, next_mode)}"
                    self.status_message_time = time.time()
                    print(f"[INFO] Modo de seguimiento cambiado a: {next_mode}")

                # Check if user closed the window directly with the 'X' button
                try:
                    if cv2.getWindowProperty(self.window_name, cv2.WND_PROP_VISIBLE) < 1:
                        print("[INFO] Ventana cerrada por el usuario.")
                        break
                except cv2.error:
                    break

        finally:
            print("\n[INFO] Liberando recursos de camara y cerrando ventanas...")
            if hasattr(self, "hotkey_manager") and self.hotkey_manager is not None:
                self.hotkey_manager.stop()
            self.tracker.release()
            cv2.destroyAllWindows()
            print("[INFO] IDEye finalizado limpiamente.")


# Brand alias for Phase 1 main app
IDEyeMainApp = EyeDEMainApp


class EyeDEApplication(QObject):
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
        self.overlay.set_vscode_connected(False)
        self._apply_settings(self._settings)
        self.calibration_ui: Optional[CalibrationUI] = None
        self._is_shutting_down: bool = False
        self.tray_icon: Optional[QSystemTrayIcon] = None
        self._last_mode_shortcut_ts: float = 0.0
        self._last_auto_switch_ts: float = 0.0

        # WebSocket Bridge for native VS Code integration (Phase 5)
        self.ws_bridge: Optional[WebSocketBridge] = None
        if getattr(config, "ENABLE_WEBSOCKET_BRIDGE", True):
            self.ws_bridge = WebSocketBridge(
                host=getattr(config, "WEBSOCKET_HOST", "127.0.0.1"),
                port=getattr(config, "WEBSOCKET_PORT", 54321),
            )
            if hasattr(self.overlay, "code_injector") and self.overlay.code_injector is not None:
                self.overlay.code_injector.set_websocket_bridge(self.ws_bridge)

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

        self._setup_connections()
        self._configure_geometry()
        self._setup_tray_icon()

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

    def _on_gaming_shortcut(self) -> None:
        """G while gazing at the header toggles the FreeLook gaming profile."""
        if self.overlay.is_mode_shortcut_targeted():
            self._on_gaming_shortcut_anywhere()

    def _on_gaming_shortcut_anywhere(self) -> None:
        """Ctrl+Alt+G (or a validated plain G) toggles the gaming profile."""
        if self.overlay.current_context_mode_id == "sniper":
            self.overlay.toggle_gaming_mode()

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
            detector.mar_threshold = mar
            detector.release_threshold = max(0.20, mar - 0.10)
        config.MAR_THRESHOLD = mar

        self.sound_feedback.set_enabled(sound_enabled)
        self.overlay.set_adaptive_ast_enabled(ast_enabled)
        self.overlay.toggle_auto_switch(auto_switch)
        self.overlay.set_language(lang)
        self.debug_widget.set_language(lang)
        self.debug_widget.set_tracking_mode_by_name(mode)
        self.debug_widget.set_adaptive_ast_enabled(ast_enabled)
        self.debug_widget.set_mar_threshold(mar, emit=False)
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

    def _setup_connections(self) -> None:
        """Connects signals between tracker, overlay, debug monitor, and lifecycle."""
        # Tracker signals to Overlay
        self.tracker.gaze_updated.connect(self.overlay.on_gaze_updated)
        self.tracker.gesture_triggered.connect(self.overlay.on_gesture_triggered)

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
        self.debug_widget.exit_requested.connect(self.shutdown)
        self.overlay.exit_requested.connect(self.shutdown)

        # Qt application about-to-quit hook
        self.qapp.aboutToQuit.connect(self.shutdown)

    def _on_vscode_editor_state_received(self, state: Dict[str, Any]) -> None:
        """
        Handles real-time editor state stream from native VS Code extension over WebSocket.
        Synchronizes active file path, programming language, and AST context across IDEye.
        """
        file_path = state.get("filePath") or state.get("file_path")
        language_id = state.get("languageId") or state.get("language_id")

        if file_path:
            self.context_reader.set_active_file(file_path)
            self.debug_widget.set_linked_file(file_path)
            self.overlay.on_file_linked(file_path)

        if language_id:
            normalized_lang = normalize_language(language_id)
            self.context_reader.set_active_language(normalized_lang)
            self.overlay.set_language(normalized_lang)
            self.debug_widget.set_language(normalized_lang)
            if hasattr(self, "mode_manager") and self.mode_manager is not None:
                self.mode_manager.set_language(normalized_lang)

        # Auto-switch context mode from the full editor state (file path, context, language)
        if hasattr(self, "mode_manager") and self.mode_manager is not None:
            self.mode_manager.handle_editor_state(state)

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
        print(f"[INFO] Modo de seguimiento activo: {display_name} ({mode})")

    def _on_mar_threshold_changed(self, value: float) -> None:
        """Applies a live MAR threshold from the debug slider or Step 6."""
        mar = max(0.25, min(0.70, float(value)))
        config.MAR_THRESHOLD = mar
        if hasattr(self.tracker, "gesture_detector") and self.tracker.gesture_detector is not None:
            self.tracker.gesture_detector.mar_threshold = mar
            self.tracker.gesture_detector.release_threshold = max(0.20, mar - 0.10)
        self.debug_widget.set_mar_threshold(mar, emit=False)
        self.settings_manager.set("mar_threshold", mar)
        if self.overlay is not None:
            self.overlay.last_action_desc = f"Umbral MAR: {mar:.2f}"
            self.overlay.update()

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
                        print(msg)
                    except UnicodeEncodeError:
                        print(msg.encode("ascii", errors="replace").decode("ascii"))
                    return
            label = config.MACRO_BLOCKS[block_idx]["label"] if 0 <= block_idx < len(config.MACRO_BLOCKS) else f"Block {block_idx}"
            msg = f"\n[IDEye ACTION] [CLICK] Bloque {block_idx + 1} Activado: '{label}' -> Accion: {action}"
            try:
                print(msg)
            except UnicodeEncodeError:
                print(msg.encode("ascii", errors="replace").decode("ascii"))
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
            dw_x = screen_geo.x() + screen_geo.width() - config.DEBUG_WINDOW_WIDTH - 12
            dw_y = screen_geo.y() + 24
            self.debug_widget.move(max(screen_geo.x(), dw_x), max(screen_geo.y(), dw_y))
            self.overlay.refresh_grid_right_margin(animate=False)
        else:
            self.overlay.resize(config.FRAME_WIDTH, config.FRAME_HEIGHT)

    def launch_calibration(self) -> None:
        """Launches the full-screen 5-point calibration interface."""
        print("[INFO] Launching 5-Point Calibration UI...")
        self.overlay.hide()
        if hasattr(self, "debug_widget") and self.debug_widget is not None:
            self.debug_widget.hide()

        self.calibration_ui = CalibrationUI(
            gaze_estimator=self.tracker.gaze_estimator,
            profile_path=self.profile_path,
            auto_mar_enabled=True,
            settings_manager=self.settings_manager,
            sound_feedback=self.sound_feedback,
        )
        self.tracker.raw_gaze_updated.connect(self.calibration_ui.on_raw_gaze_updated)
        self.tracker.gaze_updated.connect(self.calibration_ui.on_gaze_updated)
        self.tracker.gesture_triggered.connect(self.calibration_ui.on_gesture_triggered)
        self.tracker.frame_ready.connect(self._on_calibration_frame)
        self.calibration_ui.mar_threshold_calibrated.connect(self._on_mar_threshold_changed)
        self.calibration_ui.calibration_finished.connect(self._on_calibration_finished)

        self.calibration_ui.showFullScreen()

    def _on_calibration_frame(self, _frame: Any, mar: float) -> None:
        if self.calibration_ui is not None:
            self.calibration_ui.on_mar_updated(mar)

    def _on_calibration_finished(self, succeeded: bool) -> None:
        """Handles calibration completion/cancellation and restores overlay and debug widget."""
        print(f"[INFO] Calibration completed (succeeded={succeeded}). Restoring overlay HUD.")
        if self.calibration_ui is not None:
            try:
                self.tracker.raw_gaze_updated.disconnect(self.calibration_ui.on_raw_gaze_updated)
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

        print("[INFO] [EMERGENCIA] Resetting calibration to safe neutral baselines...")
        if self.tracker is not None:
            self.tracker.gaze_estimator.reset()

        if os.path.exists(self.profile_path):
            try:
                bak_path = self.profile_path + ".bak"
                if os.path.exists(bak_path):
                    os.remove(bak_path)
                os.rename(self.profile_path, bak_path)
                print(f"[INFO] Moved active calibration profile to '{bak_path}'.")
            except Exception as e:
                print(f"[AVISO] Could not backup calibration profile: {e}")

        defaults = self.settings_manager.reset_to_defaults()
        self._apply_settings(defaults)
        if self.overlay is not None:
            self.overlay.last_action_desc = "Calibración reseteada"
            self.overlay.update()

    def _setup_tray_icon(self) -> None:
        """Sets up desktop system tray icon for emergency controls and status."""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self.tray_icon = None
            return

        try:
            self.tray_icon = QSystemTrayIcon(self.debug_widget)
            logo_icon = IconManager.instance().get_app_icon()
            if not logo_icon.isNull():
                self.tray_icon.setIcon(logo_icon)
            else:
                pixmap = QPixmap(32, 32)
                pixmap.fill(Qt.GlobalColor.transparent)
                painter = QPainter(pixmap)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                painter.setBrush(QBrush(QColor(56, 189, 248)))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(2, 2, 28, 28)
                painter.setPen(QColor(15, 23, 42))
                painter.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
                painter.drawText(0, 0, 32, 32, Qt.AlignmentFlag.AlignCenter, "I")
                painter.end()
                self.tray_icon.setIcon(QIcon(pixmap))

            self.tray_icon.setToolTip("IDEye - Control Ocular Activo (Ctrl+Alt+Q para salir)")

            tray_menu = QMenu()
            action_title = tray_menu.addAction("IDEye - Control Ocular")
            action_title.setEnabled(False)
            tray_menu.addSeparator()

            action_mode = tray_menu.addAction("Cambiar Modo Seguimiento [T]")
            action_mode.triggered.connect(self.debug_widget.cycle_tracking_mode)
            tray_menu.addSeparator()

            action_recalib = tray_menu.addAction("Recalibrar (5 puntos)")
            action_recalib.triggered.connect(self.launch_calibration)

            action_reset = tray_menu.addAction("Resetear Calibración")
            action_reset.triggered.connect(self.reset_calibration)

            tray_menu.addSeparator()
            action_exit = tray_menu.addAction("Salida de Emergencia (Ctrl+Alt+Q)")
            action_exit.triggered.connect(self.shutdown)

            self.tray_icon.setContextMenu(tray_menu)
            self.tray_icon.show()
        except Exception as e:
            print(f"[IDEye] Warning: Could not initialize system tray: {e}")
            self.tray_icon = None

    def start(self) -> None:
        """Starts tracker thread, global emergency hotkeys, and displays UI."""
        # Check if calibration profile exists
        has_profile = os.path.exists(self.profile_path)
        if has_profile and not self.force_calibrate:
            print(f"[INFO] Loaded calibration profile from '{self.profile_path}'.")
            self.tracker.gaze_estimator.load_calibration_profile(self.profile_path)

        # Start CameraTracker QThread
        started = self.tracker.start()
        if not started:
            print(f"[AVISO] No se pudo abrir la camara {self.tracker.camera_index}. Continuando...")

        # Start global emergency hotkey listener
        if hasattr(self, "hotkey_manager") and self.hotkey_manager is not None:
            self.hotkey_manager.start()

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
            print("[INFO] No calibration profile found. Starting initial 5-point calibration...")
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
        print("\n[INFO] Gracefully shutting down IDEye Phase 2...")

        if self.ws_bridge is not None:
            self.ws_bridge.stop()

        if hasattr(self, "hotkey_manager") and self.hotkey_manager is not None:
            self.hotkey_manager.stop()

        if hasattr(self, "tray_icon") and self.tray_icon is not None:
            self.tray_icon.hide()

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
        print("[INFO] IDEye Phase 2 terminated cleanly.")

    def run(self) -> int:
        """Runs the Qt event loop until termination."""
        self.start()
        return self.qapp.exec()


# Brand alias for full IDEye naming
IDEyeApplication = EyeDEApplication


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
        app = EyeDEMainApp(
            camera_index=args.camera,
            canvas_width=args.width,
            canvas_height=args.height,
            threaded=not args.no_threads,
        )
        app.run(max_frames=args.frames)
    else:
        app = EyeDEApplication(
            camera_index=args.camera,
            profile_path=args.profile,
            force_calibrate=args.calibrate,
            threaded=not args.no_threads,
        )
        sys.exit(app.run())


if __name__ == "__main__":
    main()
