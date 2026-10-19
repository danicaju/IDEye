"""
Global Hotkey Manager Module for IDEye (Emergency Killswitch & Reset)
Listens for OS-level global keyboard shortcuts (e.g. Ctrl+Alt+Q, F12, Ctrl+Alt+R)
even when the transparent overlay or IDE window has focus.
"""

from typing import Optional
import threading
from PyQt6.QtCore import QObject, pyqtSignal

try:
    from pynput import keyboard as pynput_keyboard
    _PYNPUT_AVAILABLE = True
except ImportError:
    pynput_keyboard = None
    _PYNPUT_AVAILABLE = False


# pynput hotkey syntax: single characters must NOT be wrapped in angle
# brackets ("v", not "<v>"). Wrapping them raises ValueError inside
# GlobalHotKeys and prevents the entire listener (including F12) from starting.
HOTKEY_ACTIONS = {
    "<ctrl>+<alt>+q": "_on_emergency_exit",
    "<f12>": "_on_emergency_exit",
    "<ctrl>+<alt>+r": "_on_emergency_reset",
    "v": "_on_mode_cycle",
    "k": "_on_auto_switch",
    "<ctrl>+<alt>+v": "_on_mode_cycle_anywhere",
    "<ctrl>+<alt>+k": "_on_auto_switch_anywhere",
}


class GlobalHotkeyManager(QObject):
    """
    Background global hotkey listener using pynput.
    Dispatches signals cleanly to the Qt event loop for emergency exit and calibration reset.
    """

    emergency_exit_requested = pyqtSignal()
    emergency_reset_requested = pyqtSignal()
    mode_cycle_requested = pyqtSignal()
    auto_switch_requested = pyqtSignal()
    mode_cycle_anywhere_requested = pyqtSignal()
    auto_switch_anywhere_requested = pyqtSignal()

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._listener: Optional[pynput_keyboard.GlobalHotKeys] = None
        self._is_running: bool = False
        self._lock = threading.Lock()

    @property
    def is_running(self) -> bool:
        return self._is_running

    def start(self) -> bool:
        """Starts global hotkey listener daemon thread."""
        with self._lock:
            if self._is_running:
                return True
            if not _PYNPUT_AVAILABLE:
                print("[HotkeyManager] Warning: pynput not available. Global hotkeys disabled.")
                return False

            try:
                hotkeys = {
                    spec: getattr(self, method_name)
                    for spec, method_name in HOTKEY_ACTIONS.items()
                }
                self._listener = pynput_keyboard.GlobalHotKeys(hotkeys)
                self._listener.daemon = True
                self._listener.start()
                self._is_running = True
                print("[HotkeyManager] Global hotkeys active (Ctrl+Alt+Q / F12: Salida Emergencia | Ctrl+Alt+R: Reset Calibración | V/K mirando al botón de modo o Ctrl+Alt+V/K).")
                return True
            except Exception as e:
                print(f"[HotkeyManager] Warning: Failed to start global hotkey listener: {e}")
                self._is_running = False
                return False

    def stop(self) -> None:
        """Stops global hotkey listener thread cleanly."""
        with self._lock:
            if not self._is_running:
                return
            try:
                if self._listener is not None:
                    self._listener.stop()
                    self._listener = None
            except Exception:
                pass
            finally:
                self._is_running = False

    def _on_emergency_exit(self) -> None:
        """Callback from pynput thread when emergency exit shortcut is pressed."""
        print("\n[HotkeyManager] EMERGENCY EXIT TRIGGERED (Ctrl+Alt+Q / F12)")
        self.emergency_exit_requested.emit()

    def _on_emergency_reset(self) -> None:
        """Callback from pynput thread when emergency calibration reset is pressed."""
        print("\n[HotkeyManager] EMERGENCY RESET TRIGGERED (Ctrl+Alt+R)")
        self.emergency_reset_requested.emit()

    def _on_mode_cycle(self) -> None:
        """Callback for V mode cycling (gated by gaze in the main app)."""
        self.mode_cycle_requested.emit()

    def _on_auto_switch(self) -> None:
        """Callback for K auto-switch toggle (gated by gaze in the main app)."""
        self.auto_switch_requested.emit()

    def _on_mode_cycle_anywhere(self) -> None:
        """Callback for Ctrl+Alt+V mode cycling from any window."""
        self.mode_cycle_anywhere_requested.emit()

    def _on_auto_switch_anywhere(self) -> None:
        """Callback for Ctrl+Alt+K auto-switch toggle from any window."""
        self.auto_switch_anywhere_requested.emit()
