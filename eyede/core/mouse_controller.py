"""
IDEye - OS Mouse Controller (Phase 7)
Thin wrapper around pynput to inject mouse events from the gaze pipeline.
"""

from __future__ import annotations

import ctypes
import math
import sys
import time
from typing import Optional

try:
    from pynput.mouse import Button, Controller
except Exception:  # pragma: no cover - import fallback for stub environments
    Button = object
    Controller = object

try:
    from pynput.keyboard import Controller as KeyboardController, KeyCode
except Exception:  # pragma: no cover
    KeyboardController = None
    KeyCode = None


class OSMouseController:
    """Injects mouse movement and clicks at absolute screen coordinates."""

    _MOVE_CLICK_PAUSE: float = 0.01
    _MAX_COORD: int = 100000

    @classmethod
    def _safe_int(cls, value: object, default: int = 0) -> int:
        """Coerces a finite screen coordinate; never raises on NaN/Inf."""
        try:
            number = float(value)
            if not math.isfinite(number):
                return int(default)
            return max(-cls._MAX_COORD, min(cls._MAX_COORD, int(number)))
        except (TypeError, ValueError, OverflowError):
            return int(default)

    @classmethod
    def _safe_xy(cls, x: object, y: object) -> tuple[int, int]:
        return cls._safe_int(x), cls._safe_int(y)

    def __init__(self, controller: Optional[object] = None) -> None:
        self._controller = controller if controller is not None else Controller()
        try:
            self._keyboard = KeyboardController() if KeyboardController is not None else None
        except Exception:
            self._keyboard = None

    def move_to(self, x: int, y: int) -> None:
        """Move the cursor to absolute screen coordinates."""
        try:
            self._controller.position = self._safe_xy(x, y)
        except Exception:
            pass

    def move_direct(self, x: int, y: int) -> None:
        """Ultra-low-latency cursor move on Windows (FreeLook)."""
        sx, sy = self._safe_xy(x, y)
        if sys.platform == "win32":
            try:
                ctypes.windll.user32.SetCursorPos(sx, sy)
                return
            except Exception:
                pass
        self.move_to(sx, sy)

    def move_only(self, x: int, y: int) -> None:
        """Alias for move_to; used when no click is required."""
        self.move_to(x, y)

    def left_click(self, x: int, y: int) -> None:
        """Move and perform a single left click."""
        self.move_to(x, y)
        time.sleep(self._MOVE_CLICK_PAUSE)
        try:
            self._controller.click(Button.left)
        except Exception:
            pass

    def right_click(self, x: int, y: int) -> None:
        """Move and perform a single right click."""
        self.move_to(x, y)
        time.sleep(self._MOVE_CLICK_PAUSE)
        try:
            self._controller.click(Button.right)
        except Exception:
            pass

    def double_click(self, x: int, y: int) -> None:
        """Move and perform a double left click."""
        self.move_to(x, y)
        time.sleep(self._MOVE_CLICK_PAUSE)
        try:
            self._controller.click(Button.left, 2)
        except Exception:
            pass

    def scroll(self, dy: int) -> None:
        """Scroll at the current pointer position without moving it."""
        try:
            self._controller.scroll(0, self._safe_int(dy))
        except Exception:
            pass

    def scroll_horizontal(self, dx: int) -> None:
        """Scroll horizontally at the current pointer position."""
        try:
            self._controller.scroll(self._safe_int(dx), 0)
        except Exception:
            pass

    def scroll_at(self, x: int, y: int, dy: int) -> None:
        """Move to coordinates and scroll vertically by dy lines."""
        self.move_to(x, y)
        time.sleep(self._MOVE_CLICK_PAUSE)
        self.scroll(dy)

    def left_click_current(self) -> None:
        """Click at the current pointer position without moving it."""
        try:
            self._controller.click(Button.left)
        except Exception:
            pass

    def release_all_game_keys(self, keys: tuple = ("w", "a", "s", "d", " ", "up", "down", "left", "right", "e")) -> None:
        """Best-effort release of movement keys and mouse buttons after gameplay."""
        if self._keyboard is not None:
            for key in keys:
                try:
                    self._keyboard.release(key)
                except Exception:
                    pass
        self.release_all_buttons()

    def release_all_buttons(self) -> None:
        for button in (Button.left, Button.right):
            try:
                self._controller.release(button)
            except Exception:
                pass

    def mouse_down(self, button: str = "left") -> None:
        try:
            self._controller.press(Button.left if button == "left" else Button.right)
        except Exception:
            pass

    def mouse_up(self, button: str = "left") -> None:
        try:
            self._controller.release(Button.left if button == "left" else Button.right)
        except Exception:
            pass

    def key_down(self, char: str) -> None:
        if self._keyboard is not None:
            try:
                self._keyboard.press(char)
            except Exception:
                pass

    def key_up(self, char: str) -> None:
        if self._keyboard is not None:
            try:
                self._keyboard.release(char)
            except Exception:
                pass

    def tap_key(self, char: str) -> None:
        if self._keyboard is not None:
            try:
                self._keyboard.tap(char)
            except Exception:
                pass
