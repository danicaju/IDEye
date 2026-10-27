"""
Global Hotkey Manager Module for IDEye (Emergency Killswitch & Reset)
Listens for OS-level global keyboard shortcuts in the Ctrl+Alt+<letter> form.
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


# All global shortcuts intentionally use Ctrl+Alt+<letter> to avoid
# colliding with normal typing and with single-key editor bindings.
HOTKEY_ACTIONS = {
    # Every OS-global IDEye shortcut is Ctrl+Alt+<letter>.
    "<ctrl>+<alt>+q": "_on_emergency_exit",
    "<ctrl>+<alt>+r": "_on_emergency_reset",
    "<ctrl>+<alt>+v": "_on_mode_cycle_anywhere",
    "<ctrl>+<alt>+k": "_on_auto_switch_anywhere",
    "<ctrl>+<alt>+s": "_on_sound_toggle_anywhere",
    "<ctrl>+<alt>+f": "_on_sniper_toggle_anywhere",
    "<ctrl>+<alt>+g": "_on_gaming_toggle_anywhere",
    "<ctrl>+<alt>+m": "_on_monitor_toggle_anywhere",
    "<ctrl>+<alt>+a": "_on_adaptive_ast_toggle_anywhere",
    "<ctrl>+<alt>+b": "_on_clipboard_history_anywhere",
    "<ctrl>+<alt>+t": "_on_tracking_mode_cycle_anywhere",
    "<ctrl>+<alt>+c": "_on_center_calibration_anywhere",
    "<ctrl>+<alt>+p": "_on_pause_toggle_anywhere",
    "<ctrl>+<alt>+l": "_on_language_cycle_anywhere",
    "<ctrl>+<alt>+h": "_on_help_toggle_anywhere",
    "<ctrl>+<alt>+n": "_on_screen_cycle",
    "<ctrl>+<alt>+z": "_on_sniper_lens_toggle",
    "<ctrl>+<alt>+j": "_on_ast_jump",
    "<ctrl>+<alt>+i": "_on_agentic_launcher",
}


from eyede.core.logging_config import get_logger

logger = get_logger(__name__)

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
    sound_toggle_requested = pyqtSignal()
    sniper_toggle_requested = pyqtSignal()
    sound_toggle_anywhere_requested = pyqtSignal()
    sniper_toggle_anywhere_requested = pyqtSignal()
    gaming_toggle_requested = pyqtSignal()
    gaming_toggle_anywhere_requested = pyqtSignal()
    monitor_toggle_requested = pyqtSignal()
    monitor_toggle_anywhere_requested = pyqtSignal()
    screen_cycle_requested = pyqtSignal()
    sniper_lens_toggle_requested = pyqtSignal()
    ast_jump_requested = pyqtSignal()
    agentic_launcher_requested = pyqtSignal()
    adaptive_ast_toggle_requested = pyqtSignal()
    tracking_mode_cycle_requested = pyqtSignal()
    center_calibration_requested = pyqtSignal()
    pause_toggle_requested = pyqtSignal()
    clipboard_history_requested = pyqtSignal()
    clipboard_history_anywhere_requested = pyqtSignal()
    language_cycle_requested = pyqtSignal()
    help_toggle_requested = pyqtSignal()

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
                logger.warning("[HotkeyManager] Warning: pynput not available. Global hotkeys disabled.")
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
                logger.info("[HotkeyManager] Global hotkeys active: Ctrl+Alt+Q/R/V/K/S/F/G/M/A/B/T/C/P/L/N/I/J/Z (all Ctrl+Alt+letter).")
                return True
            except Exception as e:
                logger.warning(f"[HotkeyManager] Warning: Failed to start global hotkey listener: {e}")
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
        logger.warning("\n[HotkeyManager] EMERGENCY EXIT TRIGGERED (Ctrl+Alt+Q)")
        self.emergency_exit_requested.emit()

    def _on_emergency_reset(self) -> None:
        """Callback from pynput thread when emergency calibration reset is pressed."""
        logger.warning("\n[HotkeyManager] EMERGENCY RESET TRIGGERED (Ctrl+Alt+R)")
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

    def _on_sound_toggle(self) -> None:
        """Callback for S sound toggle (gated by gaze in the main app)."""
        self.sound_toggle_requested.emit()

    def _on_sniper_toggle(self) -> None:
        """Callback for F sniper toggle (gated by gaze in the main app)."""
        self.sniper_toggle_requested.emit()

    def _on_sound_toggle_anywhere(self) -> None:
        """Callback for Ctrl+Alt+S sound toggle from any window."""
        self.sound_toggle_anywhere_requested.emit()

    def _on_sniper_toggle_anywhere(self) -> None:
        """Callback for Ctrl+Alt+F sniper toggle from any window."""
        self.sniper_toggle_anywhere_requested.emit()

    def _on_gaming_toggle(self) -> None:
        """Callback for G gaming-profile toggle (gated by gaze in the app)."""
        self.gaming_toggle_requested.emit()

    def _on_gaming_toggle_anywhere(self) -> None:
        """Callback for Ctrl+Alt+G gaming-profile toggle from any window."""
        self.gaming_toggle_anywhere_requested.emit()

    def _on_monitor_toggle(self) -> None:
        """Callback for M monitor toggle (gated by gaze in the app)."""
        self.monitor_toggle_requested.emit()

    def _on_monitor_toggle_anywhere(self) -> None:
        """Callback for Ctrl+Alt+M monitor toggle from any window."""
        self.monitor_toggle_anywhere_requested.emit()

    def _on_ast_jump(self) -> None:
        """Callback for Ctrl+Alt+J Semantic AST Code Jumper."""
        self.ast_jump_requested.emit()

    def _on_agentic_launcher(self) -> None:
        """Callback for Ctrl+Alt+I Agentic Prompt Launcher."""
        self.agentic_launcher_requested.emit()

    def _on_sniper_lens_toggle(self) -> None:
        """Callback for Ctrl+Alt+Z Sniper Zoom Lens."""
        self.sniper_lens_toggle_requested.emit()

    def _on_screen_cycle(self) -> None:
        """Callback for Ctrl+Alt+N multi-monitor handover."""
        self.screen_cycle_requested.emit()

    def _on_language_cycle_anywhere(self) -> None:
        """Callback for Ctrl+Alt+L language cycling."""
        self.language_cycle_requested.emit()

    def _on_help_toggle_anywhere(self) -> None:
        """Callback for Ctrl+Alt+H help cheat sheet."""
        self.help_toggle_requested.emit()

    def _on_adaptive_ast_toggle_anywhere(self) -> None:
        """Callback for Ctrl+Alt+A adaptive AST menus."""
        self.adaptive_ast_toggle_requested.emit()

    def _on_tracking_mode_cycle_anywhere(self) -> None:
        """Callback for Ctrl+Alt+T tracking-mode cycling."""
        self.tracking_mode_cycle_requested.emit()

    def _on_center_calibration_anywhere(self) -> None:
        """Callback for Ctrl+Alt+C center recalibration."""
        self.center_calibration_requested.emit()

    def _on_pause_toggle_anywhere(self) -> None:
        """Callback for Ctrl+Alt+P pause/reading mode."""
        self.pause_toggle_requested.emit()

    def _on_clipboard_history(self) -> None:
        """Callback for the gaze-gated B clipboard shortcut."""
        self.clipboard_history_requested.emit()

    def _on_clipboard_history_anywhere(self) -> None:
        """Callback for Ctrl+Alt+B clipboard history."""
        self.clipboard_history_anywhere_requested.emit()
