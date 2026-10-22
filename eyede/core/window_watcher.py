"""IDEye - OS foreground window watcher (Phase 9).

Uses a lightweight 500 ms QTimer and a small Win32 ctypes probe. The mapping is
pure and testable; headless/non-Windows environments degrade to a no-op.
"""

from __future__ import annotations

import os
import sys
from typing import Callable, Optional, Tuple

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from eyede.core.logging_config import get_logger

try:
    import eyede.config as config
except ImportError:  # pragma: no cover
    import config  # type: ignore

logger = get_logger(__name__)

ForegroundProvider = Callable[[], Tuple[str, str]]

def _processes(attr: str) -> set:
    return {str(item).lower() for item in getattr(config, attr, ())}


def _gaming_processes() -> set:
    return {str(item).lower() for item in getattr(config, "GAMING_PROCESSES", ())}


def _gaming_suffixes() -> tuple:
    return tuple(str(item).lower() for item in getattr(config, "GAMING_PROCESS_SUFFIXES", ()))


def _gaming_keywords() -> tuple:
    return tuple(str(item).lower() for item in getattr(config, "GAMING_TITLE_KEYWORDS", ()))


def is_game_process(process_name: str) -> bool:
    """Known game executable or generic Unreal/Shipping process name."""
    process = os.path.basename(str(process_name or "")).lower()
    if not process:
        return False
    if process in _gaming_processes():
        return True
    return any(process.endswith(suffix) for suffix in _gaming_suffixes())


def is_game_window(title: str, process_name: str) -> bool:
    """True for a known game process, a generic game suffix, or a game title."""
    title_l = str(title or "").lower()
    process = os.path.basename(str(process_name or "")).lower()
    if is_game_process(process):
        return True
    if process == "javaw.exe" and "minecraft" in title_l:
        return True
    return any(keyword in title_l for keyword in _gaming_keywords())


def resolve_mode_for_window(title: str, process_name: str) -> Tuple[str, Optional[str]]:
    """Maps a foreground window to (mode_id, subprofile).

    subprofile is "gaming" or "desktop" for FreeLook, otherwise None.
    Known non-game applications win over title-only matches so a browser tab
    named after a game does not activate the gaming profile.
    """
    title_l = str(title or "").lower()
    process = os.path.basename(str(process_name or "")).lower()

    if is_game_process(process) or (process == "javaw.exe" and "minecraft" in title_l):
        return "sniper", "gaming"
    if process in _processes("TERMINAL_PROCESSES"):
        return "terminal", None
    if process in _processes("WRITING_PROCESSES"):
        return "writing", None
    if process in _processes("BROWSER_PROCESSES"):
        return "sniper", "desktop"
    if process in _processes("IDE_PROCESSES"):
        return "coding", None
    if any(keyword in title_l for keyword in _gaming_keywords()):
        return "sniper", "gaming"
    return "", None


class WindowWatcher(QObject):
    """Debounced foreground-window poller with manual-lock respect."""

    foreground_changed = pyqtSignal(str, str)  # title, process
    mode_requested = pyqtSignal(str, str)  # mode_id, subprofile ("gaming"/"desktop"/"")

    def __init__(
        self,
        mode_manager: Optional[object] = None,
        poll_interval_ms: int = 500,
        foreground_provider: Optional[ForegroundProvider] = None,
        websocket_connected: Optional[Callable[[], bool]] = None,
        debounce_reads: int = 2,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self.mode_manager = mode_manager
        self.foreground_provider = foreground_provider or self._default_foreground_info
        self.websocket_connected = websocket_connected
        self.debounce_reads = max(1, int(debounce_reads))
        self._candidate: Optional[Tuple[str, str]] = None
        self._candidate_count = 0
        self._applied: Optional[Tuple[str, str]] = None
        self._timer = QTimer(self)
        self._timer.setInterval(max(100, int(poll_interval_ms)))
        self._timer.timeout.connect(self.poll_once)

    # ------------------------------------------------------------------
    def start(self) -> None:
        if not self._timer.isActive():
            self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    @staticmethod
    def _is_ideye_window(title: str, process_name: str) -> bool:
        title_l = str(title or "").lower()
        process = os.path.basename(str(process_name or "")).lower()
        return (
            "ideye" in title_l
            or process in {"ideye.exe", "python.exe", "pythonw.exe"}
        )

    def poll_once(self) -> None:
        try:
            title, process = self.foreground_provider()
        except Exception as exc:
            logger.debug("Foreground probe failed: %s", exc)
            return
        title = str(title or "")
        process = str(process or "")
        if not title and not process:
            return
        if self._is_ideye_window(title, process):
            self._candidate = None
            self._candidate_count = 0
            return

        candidate = (title, process)
        if candidate != self._candidate:
            self._candidate = candidate
            self._candidate_count = 1
            return
        self._candidate_count += 1
        if self._candidate_count < self.debounce_reads:
            return
        if candidate == self._applied:
            return
        self._applied = candidate

        self.foreground_changed.emit(title, process)
        mode_id, subprofile = resolve_mode_for_window(title, process)
        if not mode_id:
            return
        if mode_id == "coding" and self.websocket_connected is not None:
            try:
                if self.websocket_connected():
                    return
            except Exception:
                pass
        mode_manager = self.mode_manager
        if mode_manager is None or not getattr(mode_manager, "auto_switch_enabled", False):
            return
        self.mode_requested.emit(mode_id, subprofile or "")
        try:
            mode_manager.set_mode(mode_id, emit=True)
        except Exception as exc:
            logger.warning("Window watcher mode switch failed: %s", exc)
            return
        logger.info("Foreground window -> %s (%s), mode=%s", title, process, mode_id)

    # ------------------------------------------------------------------
    @staticmethod
    def _default_foreground_info() -> Tuple[str, str]:
        if not sys.platform.startswith("win"):
            return "", ""
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            hwnd = user32.GetForegroundWindow()
            if not hwnd:
                return "", ""

            length = user32.GetWindowTextLengthW(hwnd)
            title_buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, title_buf, length + 1)

            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

            process_name = ""
            process_handle = kernel32.OpenProcess(0x1000, False, pid.value)
            if process_handle:
                try:
                    size = wintypes.DWORD(1024)
                    exe_buf = ctypes.create_unicode_buffer(size.value)
                    if kernel32.QueryFullProcessImageNameW(
                        process_handle, 0, exe_buf, ctypes.byref(size)
                    ):
                        process_name = os.path.basename(exe_buf.value)
                finally:
                    kernel32.CloseHandle(process_handle)
            return title_buf.value, process_name
        except Exception as exc:
            logger.debug("Win32 foreground probe unavailable: %s", exc)
            return "", ""
