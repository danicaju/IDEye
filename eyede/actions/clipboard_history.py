"""IDEye - Clipboard Time-Machine (Phase 9).

Keeps the last six unique user clipboard texts and exposes them as a 3x3
MenuNode. Internal CodeInjector clipboard writes are excluded through an
explicit lock/context manager.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from contextlib import contextmanager
from typing import Any, Deque, Iterator, List, Optional

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

try:
    import pyperclip
except ImportError:  # pragma: no cover
    pyperclip = None

try:
    from eyede.actions.menu_trees import (
        MenuAction,
        MenuNode,
        create_back_action,
        create_pause_action,
    )
    from eyede.core.logging_config import get_logger
except ImportError:  # pragma: no cover
    from actions.menu_trees import (  # type: ignore
        MenuAction,
        MenuNode,
        create_back_action,
        create_pause_action,
    )
    from core.logging_config import get_logger  # type: ignore

logger = get_logger(__name__)

HISTORY_SLOTS = (0, 1, 2, 3, 5, 7)
HISTORY_SIZE = len(HISTORY_SLOTS)


class _DummyClipboard:
    def __init__(self) -> None:
        self._text = ""

    def paste(self) -> str:
        return self._text

    def copy(self, text: str) -> None:
        self._text = str(text)


def _shorten(text: str, limit: int = 18) -> str:
    cleaned = " ".join(str(text).replace("\r", " ").replace("\n", " ").split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: max(1, limit - 3)].rstrip() + "..."


class ClipboardHistoryManager(QObject):
    """Six-slot MTF clipboard history with internal-write exclusion."""

    history_changed = pyqtSignal()

    def __init__(
        self,
        clipboard_module: Optional[Any] = None,
        poll_interval_ms: int = 500,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self.clipboard = clipboard_module or pyperclip or _DummyClipboard()
        self._history: Deque[str] = deque(maxlen=HISTORY_SIZE)
        self._lock = threading.RLock()
        self._internal_writes = 0
        self._last_seen: Optional[str] = None
        self._timer = QTimer(self)
        self._timer.setInterval(max(100, int(poll_interval_ms)))
        self._timer.timeout.connect(self.poll_once)

    # ------------------------------------------------------------------
    def start(self) -> None:
        self._last_seen = self._read_clipboard()
        if not self._timer.isActive():
            self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def _read_clipboard(self) -> str:
        try:
            value = self.clipboard.paste()
            return value if isinstance(value, str) else ""
        except Exception as exc:
            logger.debug("Could not read clipboard: %s", exc)
            return ""

    def poll_once(self) -> None:
        """Records a changed OS clipboard value unless an internal write is active."""
        with self._lock:
            if self._internal_writes > 0:
                return
        text = self._read_clipboard()
        if not text or text == self._last_seen:
            return
        self._last_seen = text
        self.record(text)

    def record(self, text: str) -> bool:
        """Adds a real user copy using move-to-front deduplication."""
        if not isinstance(text, str) or not text.strip():
            return False
        with self._lock:
            if self._internal_writes > 0:
                return False
            if text in self._history:
                self._history.remove(text)
            self._history.appendleft(text)
        self.history_changed.emit()
        return True

    @contextmanager
    def ignore_internal_writes(self) -> Iterator[None]:
        """Context manager used by CodeInjector around temporary clipboard use."""
        with self._lock:
            self._internal_writes += 1
        try:
            yield
        finally:
            with self._lock:
                self._internal_writes = max(0, self._internal_writes - 1)
            # Do not treat a snippet intentionally left on the clipboard as a
            # real user copy when restore_clipboard=False.
            self._last_seen = self._read_clipboard()

    def get_items(self) -> List[str]:
        with self._lock:
            return list(self._history)

    def clear(self) -> None:
        with self._lock:
            self._history.clear()
        self.history_changed.emit()

    # ------------------------------------------------------------------
    def copy_selection(self) -> None:
        """Sends Ctrl+C to the active window and polls the new clipboard."""
        try:
            from pynput.keyboard import Controller, Key

            keyboard = Controller()
            with keyboard.pressed(Key.ctrl):
                keyboard.tap("c")
        except Exception as exc:
            logger.warning("Could not send Ctrl+C for clipboard capture: %s", exc)
        QTimer.singleShot(80, self.poll_once)

    # ------------------------------------------------------------------
    def get_clipboard_menu_node(self, parent_id: str = "ROOT") -> MenuNode:
        """Builds the live 3x3 clipboard submenu with all invariants."""
        items = self.get_items()
        by_slot: dict[int, MenuAction] = {}
        for display_slot, history_index in enumerate(range(HISTORY_SIZE)):
            n = display_slot + 1
            slot = HISTORY_SLOTS[display_slot]
            text = items[history_index] if history_index < len(items) else ""
            if not text:
                by_slot[slot] = MenuAction(
                    id=f"CLIP_EMPTY_{n}",
                    label=f"{n}: (Vacío)",
                    hint="Sin historial",
                    action_type="INFO",
                    icon="edit",
                )
            else:
                by_slot[slot] = MenuAction(
                    id=f"CLIP_ITEM_{n}",
                    label=f"{n}: {_shorten(text)}",
                    hint=f"{len(text)} chars",
                    action_type="CLIPBOARD",
                    snippet=text,
                    icon="edit",
                )

        def cell(slot: int) -> MenuAction:
            return by_slot.get(
                slot,
                MenuAction(
                    id=f"CLIP_EMPTY_SLOT_{slot}",
                    label="(Vacío)",
                    hint="Sin historial",
                    action_type="INFO",
                    icon="edit",
                ),
            )

        grid = [
            cell(0),
            cell(1),
            cell(2),
            cell(3),
            create_pause_action("5"),
            cell(5),
            create_back_action(parent_id, "7"),
            cell(7),
            MenuAction(
                id="CLIPBOARD_COPY_SELECTION",
                label="9: COPIAR SELECCIÓN",
                hint="Ctrl+C en la ventana activa",
                action_type="CLIPBOARD_COPY",
                key_name="CTRL_C",
                icon="edit",
            ),
        ]
        return MenuNode(
            id="CLIPBOARD_HISTORY",
            title="PORTAPAPELES (HISTORIAL)",
            breadcrumb_label="PORTAPAPELES",
            items=grid,
            parent_id=parent_id,
            sticky=False,
        )


_MANAGER: Optional[ClipboardHistoryManager] = None


def get_clipboard_history_manager() -> ClipboardHistoryManager:
    """Returns the process-wide clipboard history manager."""
    global _MANAGER
    if _MANAGER is None:
        _MANAGER = ClipboardHistoryManager()
    return _MANAGER
