"""
IDEye - OS Mouse Controller (Phase 7)
Thin wrapper around pynput to inject mouse events from the gaze pipeline.
"""

from __future__ import annotations

import ctypes
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

    def __init__(self, controller: Optional[object] = None) -> None:
        self._controller = controller if controller is not None else Controller()
        try:
            self._keyboard = KeyboardController() if KeyboardController is not None else None
        except Exception:
            self._keyboard = None

    def move_to(self, x: int, y: int) -> None:
        """Move the cursor to absolute screen coordinates."""
        self._controller.position = (int(x), int(y))

    def move_direct(self, x: int, y: int) -> None:
        """Ultra-low-latency cursor move on Windows (FreeLook)."""
        if sys.platform == "win32":
            try:
                ctypes.windll.user32.SetCursorPos(int(x), int(y))
                return
            except Exception:
                pass
        self.move_to(x, y)

    def move_only(self, x: int, y: int) -> None:
        """Alias for move_to; used when no click is required."""
        self.move_to(x, y)

    def left_click(self, x: int, y: int) -> None:
        """Move and perform a single left click."""
        self.move_to(x, y)
        time.sleep(self._MOVE_CLICK_PAUSE)
        self._controller.click(Button.left)

    def right_click(self, x: int, y: int) -> None:
        """Move and perform a single right click."""
        self.move_to(x, y)
        time.sleep(self._MOVE_CLICK_PAUSE)
        self._controller.click(Button.right)

    def double_click(self, x: int, y: int) -> None:
        """Move and perform a double left click."""
        self.move_to(x, y)
        time.sleep(self._MOVE_CLICK_PAUSE)
        self._controller.click(Button.left, 2)

    def scroll(self, dy: int) -> None:
        """Scroll at the current pointer position without moving it."""
        self._controller.scroll(0, int(dy))

    def scroll_at(self, x: int, y: int, dy: int) -> None:
        """Move to coordinates and scroll vertically by dy lines."""
        self.move_to(x, y)
        time.sleep(self._MOVE_CLICK_PAUSE)
        self._controller.scroll(0, int(dy))

    def left_click_current(self) -> None:
        """Click at the current pointer position without moving it."""
        self._controller.click(Button.left)

    def release_all_game_keys(self, keys: tuple = ("w", "a", "s", "d", " ")) -> None:
        """Best-effort release of movement keys after leaving gameplay."""
        if self._keyboard is None:
            return
        for key in keys:
            try:
                self._keyboard.release(key)
            except Exception:
                pass

    def release_all_buttons(self) -> None:
        for button in (Button.left, Button.right):
            try:
                self._controller.release(button)
            except Exception:
                pass

    def mouse_down(self, button: str = "left") -> None:
        self._controller.press(Button.left if button == "left" else Button.right)

    def mouse_up(self, button: str = "left") -> None:
        self._controller.release(Button.left if button == "left" else Button.right)

    def key_down(self, char: str) -> None:
        if self._keyboard is not None:
            self._keyboard.press(char)

    def key_up(self, char: str) -> None:
        if self._keyboard is not None:
            self._keyboard.release(char)

    def tap_key(self, char: str) -> None:
        if self._keyboard is not None:
            self._keyboard.tap(char)
