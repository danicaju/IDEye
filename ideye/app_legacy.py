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

from ideye.app_draw import MainAppDrawMixin
class IDEyeMainApp(MainAppDrawMixin):
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
        """Triggered via global emergency hotkey (Ctrl+Alt+Q)."""
        self._emergency_exit_requested = True

    def _on_emergency_reset(self) -> None:
        """Triggered via global emergency reset hotkey (Ctrl+Alt+R)."""
        if self.gaze_estimator is not None:
            self.gaze_estimator.reset()
        self.status_message = "Calibración reseteada a baselines seguras"
        self.status_message_time = time.time()

    def handle_click_event(self, block_idx: int, norm_x: float, norm_y: float) -> None:
        """Triggers the action associated with the clicked macro block."""
        self.last_clicked_block_idx = block_idx
        self.last_click_timestamp = time.time()

        block_info = self.macro_blocks[block_idx]
        action = block_info["action"]
        label = block_info["label"]

        logger.info(f"\n[IDEye ACTION] [CLICK] Disparado en Bloque {block_idx + 1}: '{label}'")
        logger.info(f"               Accion: {action} | Coordenada: (X={norm_x:.3f}, Y={norm_y:.3f})")

        if action == "PAUSE_RESUME":
            self.is_paused = not self.is_paused
            state_str = "PAUSADO (Zona de reposo)" if self.is_paused else "REANUDADO"
            logger.info(f"[IDEye ACTION] Estado de seguimiento: {state_str}")
        elif action == "ACTION_EXIT":
            logger.info("[IDEye ACTION] Bloque SALIR activado. Cerrando aplicacion...")

    def run(self, max_frames: Optional[int] = None) -> None:
        """
        Main application loop.
        
        Args:
            max_frames: Optional frame limit (useful for non-blocking automated testing).
        """
        logger.info("=" * 60)
        logger.info("  IDEye - Motor de Vision, Tracking Hibrido y Gestos (Fase 1)")
        logger.info("=" * 60)
        logger.info("Inicializando subsistemas de vision y FaceMesh (478 landmarks)...")

        if not self.tracker.start():
            logger.warning(f"[ERROR] No se pudo inicializar la camara indice {self.tracker.camera_index}.")
            return

        cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(self.window_name, self.canvas_width, self.canvas_height)

        logger.info("[OK] Camara activa. Presiona [C] mirando al centro para calibrar.")
        logger.info("[OK] Abre ligeramente la boca durante 150ms para disparar CLICK.")
        logger.info("[OK] Presiona [Ctrl+Alt+Q] para salir limpiamente.\n")

        self.hotkey_manager.start()
        processed_frames = 0

        try:
            while True:
                if self._emergency_exit_requested:
                    logger.info("\n[INFO] Salida de emergencia solicitada via global hotkey (Ctrl+Alt+Q).")
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
                    logger.info(f"[INFO] {self.status_message}")

                if "WINK_LEFT" in triggered_winks and not self.is_paused:
                    self.status_message = "Guiño izquierdo: Volver / Deshacer"
                    self.status_message_time = time.time()
                    logger.info(f"[INFO] {self.status_message}")

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
                    logger.info(f"[TEST] Limite de {max_frames} fotogramas alcanzado.")
                    break

                # Keyboard interaction
                key = cv2.waitKey(1) & 0xFF
                if key in (ord('q'), ord('Q'), 27):  # 'q' or ESC
                    logger.info("[INFO] Salida solicitada por usuario (tecla Q/ESC).")
                    break
                elif key in (ord('c'), ord('C')):
                    # Calibrate center & distance-adaptive gain
                    if face_landmarks is not None and self.gaze_estimator.calibrate_center(face_landmarks):
                        scale_pct = int(self.gaze_estimator.distance_scale * 100)
                        logger.info(f"[INFO] [CALIB] Calibracion central completada. Escala de ganancia: {scale_pct}%.")
                    else:
                        logger.warning("[AVISO] No se pudo calibrar: rostro no detectado en el fotograma.")
                elif key in (ord('+'), ord('=')):
                    self.gaze_estimator.adjust_sensitivity(1.10)
                    logger.info(f"[INFO] Sensibilidad aumentada (+10%).")
                elif key in (ord('-'), ord('_')):
                    self.gaze_estimator.adjust_sensitivity(0.90)
                    logger.info(f"[INFO] Sensibilidad reducida (-10%).")
                elif key in (ord('m'), ord('M')):
                    self.show_mini_feed = not self.show_mini_feed
                    logger.info(f"[INFO] Mini-feed {'mostrado' if self.show_mini_feed else 'ocultado'}.")
                elif key in (ord('p'), ord('P'), 32):  # 'p' or space
                    self.is_paused = not self.is_paused
                    logger.info(f"[INFO] Modo reposo {'activado' if self.is_paused else 'desactivado'}.")
                elif key in (ord('r'), ord('R')):
                    self.gaze_estimator.reset()
                    self.gesture_detector.reset()
                    self.is_paused = False
                    logger.info("[INFO] Estado y calibracion reseteados.")
                elif key in (ord('t'), ord('T')):
                    modes = ["PURE_IRIS", "HYBRID", "HEAD_PRIMARY"]
                    curr_idx = modes.index(self.gaze_estimator.tracking_mode) if self.gaze_estimator.tracking_mode in modes else 0
                    next_mode = modes[(curr_idx + 1) % len(modes)]
                    self.gaze_estimator.set_tracking_mode(next_mode)
                    mode_names = {"PURE_IRIS": "Solo Iris", "HYBRID": "Híbrido", "HEAD_PRIMARY": "Solo Cabeza (Recomendado)"}
                    self.status_message = f"Modo: {mode_names.get(next_mode, next_mode)}"
                    self.status_message_time = time.time()
                    logger.info(f"[INFO] Modo de seguimiento cambiado a: {next_mode}")

                # Check if user closed the window directly with the 'X' button
                try:
                    if cv2.getWindowProperty(self.window_name, cv2.WND_PROP_VISIBLE) < 1:
                        logger.info("[INFO] Ventana cerrada por el usuario.")
                        break
                except cv2.error:
                    break

        finally:
            logger.info("\n[INFO] Liberando recursos de camara y cerrando ventanas...")
            if hasattr(self, "hotkey_manager") and self.hotkey_manager is not None:
                self.hotkey_manager.stop()
            self.tracker.release()
            cv2.destroyAllWindows()
            logger.info("[INFO] IDEye finalizado limpiamente.")
