"""
Overlay Window Module for EyeDE (Phase 2)
Transparent, Non-Focus-Stealing 3x3 Macro-Block Grid Overlay.

Features:
- Configures Qt.WindowType.WindowDoesNotAcceptFocus, FramelessWindowHint,
  WindowStaysOnTopHint, Tool, and WA_TranslucentBackground.
- Ensures external IDEs (e.g. VS Code, PyCharm) NEVER lose keyboard focus or cursor blink.
- Displays 3x3 Macro-Block programming grid with dynamic HOVER and ACTIVE click highlights.
- Block 4 (Center: "PAUSA / MODO LECTURA") toggles HUD opacity to 10% and inhibits
  the remaining blocks to allow reading code beneath safely without Midas Touch triggers.
- Communicates purely via signals, adhering to Qt thread safety.
"""

from typing import Optional, Tuple
import sys
import os

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QRectF, QPointF
from PyQt6.QtGui import QPainter, QColor, QFont, QPen, QBrush
from PyQt6.QtWidgets import QWidget

try:
    import eyede.config as config
except ImportError:
    import config


class OverlayWindow(QWidget):
    """
    Transparent HUD overlay rendering the 3x3 Macro-Block grid.
    Never steals window focus from the active IDE.
    """

    block_activated = pyqtSignal(int, str)  # (block_index, action_name)
    exit_requested = pyqtSignal()
    reading_mode_toggled = pyqtSignal(bool)  # True = reading mode on (10% opacity)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        # 1. Non-focus stealing, transparent, top-level overlay flags
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        # Win32 OS-level non-activation protection
        if sys.platform == "win32":
            self._apply_win32_no_activate()

        # State tracking
        self.reading_mode: bool = False
        self.current_opacity: float = config.OVERLAY_OPACITY_ACTIVE
        self.hovered_block: Optional[int] = None
        self.active_click_block: Optional[int] = None
        self.current_gaze: Tuple[float, float] = (0.5, 0.5)

        # Window title for identification
        self.setWindowTitle("EyeDE - Gaze Macro Grid HUD")

    def _apply_win32_no_activate(self) -> None:
        """Applies WS_EX_NOACTIVATE and WS_EX_TRANSPARENT styles on Windows to guarantee zero focus stealing."""
        try:
            import ctypes
            GWL_EXSTYLE = -20
            WS_EX_NOACTIVATE = 0x08000000
            WS_EX_TOPMOST = 0x00000008
            WS_EX_TRANSPARENT = 0x00000020
            hwnd = int(self.winId())
            if hwnd:
                ex_style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                ctypes.windll.user32.SetWindowLongW(
                    hwnd, GWL_EXSTYLE, ex_style | WS_EX_NOACTIVATE | WS_EX_TOPMOST | WS_EX_TRANSPARENT
                )
        except Exception:
            pass

    def on_gaze_updated(self, gx: float, gy: float) -> None:
        """
        Receives normalized gaze coordinates from CameraTracker.
        Updates hovered block and gaze cursor position.
        """
        self.current_gaze = (gx, gy)

        # Determine 3x3 block index
        col = min(2, max(0, int(gx * 3)))
        row = min(2, max(0, int(gy * 3)))
        block_idx = row * 3 + col

        if self.reading_mode:
            # In reading mode, inhibit all blocks except Block 4 (Resume trigger)
            if block_idx == 4:
                self.hovered_block = 4
            else:
                self.hovered_block = None
        else:
            self.hovered_block = block_idx

        self.update()

    def on_gesture_triggered(self, gesture_name: str) -> None:
        """
        Handles facial gesture triggers (e.g. "MOUTH_CLICK").
        """
        if gesture_name != "MOUTH_CLICK":
            return

        target_block = self.hovered_block
        if target_block is None:
            return

        if self.reading_mode:
            if target_block == 4:
                # Resume active mode
                self.trigger_click_flash(4)
                self.toggle_reading_mode()
        else:
            self.trigger_click_flash(target_block)
            if target_block == 4:
                # Toggle into reading mode
                self.toggle_reading_mode()
            elif target_block == 8:
                # Exit action
                self.exit_requested.emit()
            else:
                action = config.MACRO_BLOCKS[target_block]["action"]
                self.block_activated.emit(target_block, action)

    def toggle_reading_mode(self) -> None:
        """Toggles between Active HUD mode and 10% Opacity Reading Mode."""
        self.reading_mode = not self.reading_mode
        self.current_opacity = config.OVERLAY_OPACITY_READING if self.reading_mode else config.OVERLAY_OPACITY_ACTIVE
        if self.reading_mode:
            self.hovered_block = None
        self.reading_mode_toggled.emit(self.reading_mode)
        self.update()

    def trigger_click_flash(self, block_idx: int) -> None:
        """Triggers vibrant green active highlight on clicked block."""
        self.active_click_block = block_idx
        self.update()
        QTimer.singleShot(int(config.CLICK_FLASH_DURATION_SEC * 1000), self._clear_click_flash)

    def _clear_click_flash(self) -> None:
        self.active_click_block = None
        self.update()

    def paintEvent(self, event) -> None:
        """Paints 3x3 Macro-Block HUD and gaze cursor."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        cell_w = w / 3.0
        cell_h = h / 3.0
        margin = 8.0

        font_label = QFont("Segoe UI", 13, QFont.Weight.Bold)
        font_hint = QFont("Segoe UI", 10)

        # Draw 9 blocks
        for i, block in enumerate(config.MACRO_BLOCKS):
            col = i % 3
            row = i // 3

            rect = QRectF(
                col * cell_w + margin,
                row * cell_h + margin,
                cell_w - 2 * margin,
                cell_h - 2 * margin,
            )

            # Determine styling based on state
            is_active_click = (self.active_click_block == i)
            is_hover = (self.hovered_block == i)

            # In reading mode, preserve high contrast for the resume block (4)
            if self.reading_mode:
                if i == 4:
                    block_opacity = 0.85 if (is_active_click or is_hover) else 0.35
                else:
                    block_opacity = self.current_opacity
            else:
                block_opacity = self.current_opacity

            painter.setOpacity(block_opacity)

            if is_active_click:
                bg_color = QColor(*config.OVERLAY_COLOR_CLICK)
                border_pen = QPen(QColor(*config.OVERLAY_CLICK_BORDER_COLOR), 3)
                text_color = QColor(10, 30, 15)
                hint_color = QColor(25, 55, 30)
            elif is_hover:
                bg_color = QColor(*config.OVERLAY_COLOR_HOVER)
                border_pen = QPen(QColor(*config.OVERLAY_HOVER_BORDER_COLOR), config.OVERLAY_HOVER_BORDER_WIDTH)
                text_color = QColor(*config.OVERLAY_TEXT_HOVER_COLOR)
                hint_color = QColor(230, 235, 245)
            elif self.reading_mode:
                if i == 4:
                    bg_color = QColor(25, 45, 75, 180)
                    border_pen = QPen(QColor(0, 150, 255, 220), 2)
                    text_color = QColor(200, 225, 255)
                    hint_color = QColor(150, 180, 220)
                else:
                    bg_color = QColor(15, 18, 22, 50)
                    border_pen = QPen(QColor(40, 45, 55, 60), 1)
                    text_color = QColor(120, 130, 145, 100)
                    hint_color = QColor(80, 90, 105, 80)
            else:
                if i == 4:
                    bg_color = QColor(*config.OVERLAY_COLOR_REST)
                    border_pen = QPen(QColor(*config.OVERLAY_REST_BORDER_COLOR), config.OVERLAY_BORDER_WIDTH)
                else:
                    bg_color = QColor(*config.OVERLAY_COLOR_BG)
                    border_pen = QPen(QColor(*config.OVERLAY_COLOR_BORDER), config.OVERLAY_BORDER_WIDTH)
                text_color = QColor(*config.OVERLAY_TEXT_COLOR)
                hint_color = QColor(*config.OVERLAY_TEXT_HINT_COLOR)

            # Draw block rounded rectangle
            painter.setBrush(QBrush(bg_color))
            painter.setPen(border_pen)
            painter.drawRoundedRect(rect, 10.0, 10.0)

            # Block text labels
            label_text = block["label"]
            hint_text = block["hint"]

            if self.reading_mode and i == 4:
                label_text = "5: REANUDAR"
                hint_text = "Modo Lectura Activo (Mire y Abra Boca)"

            painter.setPen(text_color)
            painter.setFont(font_label)
            painter.drawText(
                int(rect.x() + 10),
                int(rect.y() + 12),
                int(rect.width() - 20),
                26,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                label_text,
            )

            painter.setPen(hint_color)
            painter.setFont(font_hint)
            painter.drawText(
                int(rect.x() + 10),
                int(rect.y() + 38),
                int(rect.width() - 20),
                22,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                hint_text,
            )

        # Draw subtle gaze cursor pointer
        if not self.reading_mode or self.hovered_block == 4:
            painter.setOpacity(self.current_opacity if not self.reading_mode else 0.85)
            gx, gy = self.current_gaze
            cx = gx * w
            cy = gy * h
            r = config.OVERLAY_POINTER_RADIUS

            # Outer ring
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(*config.OVERLAY_POINTER_OUTLINE), 2))
            painter.drawEllipse(QPointF(cx, cy), r + 3, r + 3)

            # Center dot
            painter.setBrush(QBrush(QColor(*config.OVERLAY_POINTER_COLOR)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(cx, cy), r, r)

        painter.end()
