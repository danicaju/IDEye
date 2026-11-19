"""
IDEye - Code Injector Module (Phase 3)
Non-blocking, OS-level code and keystroke injector with clipboard preservation,
cross-platform modifier mapping, and guaranteed stuck-modifier protection.

Architecture & Safety Features:
1. Multi-platform key mapping (Ctrl on Windows/Linux vs Cmd on macOS).
2. Clipboard safety: saves old clipboard, copies snippet, taps Ctrl+V,
   applies controlled delay, performs cursor offsets (left/up), and restores old clipboard.
3. Stuck Modifier Keys Audit: all modifier key presses (Ctrl, Shift, Alt, Cmd)
   are wrapped in `hold_modifiers` context manager with guaranteed release in `finally`.
4. Non-blocking UI execution: operations can be dispatched to a dedicated background
   worker thread via FIFO queue so the PyQt6 UI loop is never blocked by sleeps or I/O.
"""

import sys
import time
import logging
import threading
import queue
from contextlib import contextmanager, nullcontext
from typing import Optional, Dict, Any, Callable, List, Tuple, Union

try:
    from pynput.keyboard import Controller as KeyboardController, Key, KeyCode
except Exception:
    KeyboardController = None
    Key = None
    KeyCode = None

try:
    import pyperclip
except Exception:
    pyperclip = None

logger = logging.getLogger("ideye.actions.code_injector")


from ideye.actions.injector_dummies import DummyClipboard, DummyKeyboard  # noqa: F401
from ideye.actions.injector_snippets import SnippetInsertMixin
from ideye.actions.injector_keys import KeyDispatchMixin


class CodeInjector(SnippetInsertMixin, KeyDispatchMixin):
    """
    Intelligent code injector that executes snippets via clipboard paste
    and sends direct keyboard actions without blocking the Qt UI thread.
    """

    def __init__(
        self,
        async_mode: bool = True,
        paste_delay: float = 0.05,
        keyboard_controller: Optional[Any] = None,
        clipboard_module: Optional[Any] = None,
        websocket_bridge: Optional[Any] = None,
        clipboard_history: Optional[Any] = None,
        release_game_keys: Optional[Callable[[], None]] = None,
    ):
        """
        Initializes the CodeInjector.

        Args:
            async_mode: If True, operations run asynchronously on a background worker thread.
            paste_delay: Delay in seconds after paste to allow target window to process event.
            keyboard_controller: Optional custom/mock keyboard controller.
            clipboard_module: Optional custom/mock clipboard module.
            websocket_bridge: Optional WebSocketBridge for native VS Code injection.
        """
        self.async_mode = async_mode
        self.paste_delay = paste_delay
        self.websocket_bridge = websocket_bridge
        self.clipboard_history = clipboard_history
        self.release_game_keys = release_game_keys

        # OS Platform detection
        self.is_macos: bool = (sys.platform == "darwin")

        # Initialize keyboard controller
        if keyboard_controller is not None:
            self.keyboard = keyboard_controller
        elif KeyboardController is not None:
            try:
                self.keyboard = KeyboardController()
            except Exception as e:
                logger.warning(f"Could not initialize native pynput KeyboardController: {e}. Using dummy.")
                self.keyboard = DummyKeyboard()
        else:
            self.keyboard = DummyKeyboard()

        # Primary modifier for platform
        if Key is not None:
            self.primary_modifier = Key.cmd if self.is_macos else Key.ctrl
        else:
            self.primary_modifier = "CMD" if self.is_macos else "CTRL"

        # Initialize clipboard module
        if clipboard_module is not None:
            self.clipboard = clipboard_module
        elif pyperclip is not None:
            self.clipboard = pyperclip
        else:
            self.clipboard = DummyClipboard()

        # Modifier tracking for safety audits
        self._active_modifiers = set()
        self._mod_lock = threading.Lock()

        # Phase 7.5: prefix tracker for Smart Prefix Deduplication.
        self._current_word_prefix: str = ""
        self._last_statement_prefix: str = ""
        self._last_statement_inside_parens: bool = False
        self._context_reader: Optional[Any] = None
        self._prefix_lock = threading.Lock()

        # Background worker thread & FIFO task queue
        self._task_queue: queue.Queue = queue.Queue(maxsize=256)
        self._stop_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None
        self._is_executing: bool = False

        if self.async_mode:
            self._start_worker()

    @property
    def is_busy(self) -> bool:
        """Returns True if the worker thread is currently executing an injection task or queue is non-empty."""
        return self._is_executing or not self._task_queue.empty()

    def _enqueue(self, fn: Callable[..., Any], args: tuple, kwargs: dict) -> bool:
        """Queues a task without ever blocking the Qt UI thread."""
        try:
            self._task_queue.put_nowait((fn, args, kwargs))
            return True
        except queue.Full:
            logger.warning("Injection queue full; dropping task to protect UI latency.")
            return False

    def _clipboard_paste(self, attempts: int = 3) -> Any:
        """Reads the clipboard with short backoff for transient OS locks."""
        for attempt in range(max(1, attempts)):
            try:
                return self.clipboard.paste()
            except Exception as exc:
                if attempt + 1 >= attempts:
                    logger.warning("Could not read clipboard after %s attempts: %s", attempts, exc)
                    return None
                time.sleep(0.01 * (attempt + 1))
        return None

    def _clipboard_copy(self, text: str, attempts: int = 3) -> bool:
        """Writes the clipboard with short backoff for transient OS locks."""
        for attempt in range(max(1, attempts)):
            try:
                self.clipboard.copy(str(text))
                return True
            except Exception as exc:
                if attempt + 1 >= attempts:
                    logger.warning("Could not write clipboard after %s attempts: %s", attempts, exc)
                    return False
                time.sleep(0.01 * (attempt + 1))
        return False

    def _start_worker(self) -> None:
        """Starts the dedicated worker thread for non-blocking injection."""
        self._stop_event.clear()
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            name="IDEye-CodeInjector-Worker",
            daemon=True,
        )
        self._worker_thread.start()

    def _worker_loop(self) -> None:
        """Processes injection tasks sequentially in the background."""
        while not self._stop_event.is_set():
            try:
                task = self._task_queue.get(timeout=0.08)
            except queue.Empty:
                continue

            if task is None:
                self._task_queue.task_done()
                break

            fn, args, kwargs = task
            self._is_executing = True
            try:
                fn(*args, **kwargs)
            except Exception as e:
                logger.error(f"Error executing injection task in worker thread: {e}", exc_info=True)
            finally:
                self._is_executing = False
                self.release_all_modifiers()
                self._task_queue.task_done()

    @contextmanager
    def hold_modifiers(self, *modifiers):
        """
        Context manager ensuring modifier keys are ALWAYS released in reverse order
        even if an exception or cancellation occurs.
        Guarantees zero stuck modifier keys.
        """
        pressed = []
        try:
            for mod in modifiers:
                if mod is not None:
                    self.keyboard.press(mod)
                    pressed.append(mod)
                    with self._mod_lock:
                        self._active_modifiers.add(mod)
            yield
        finally:
            for mod in reversed(pressed):
                try:
                    self.keyboard.release(mod)
                except Exception as e:
                    logger.warning(f"Error releasing modifier {mod}: {e}")
                finally:
                    with self._mod_lock:
                        self._active_modifiers.discard(mod)

    def release_all_modifiers(self) -> None:
        """
        Safety guarantee: explicitly releases all known modifier keys.
        Can be called during shutdown or error recovery.
        """
        all_mods = []
        if Key is not None:
            all_mods = [
                Key.ctrl, Key.ctrl_l, Key.ctrl_r,
                Key.shift, Key.shift_l, Key.shift_r,
                Key.alt, Key.alt_l, Key.alt_r,
                Key.cmd, Key.cmd_l, Key.cmd_r,
            ]
        with self._mod_lock:
            all_mods.extend(list(self._active_modifiers))
            self._active_modifiers.clear()

        for mod in set(all_mods):
            if mod is not None:
                try:
                    self.keyboard.release(mod)
                except Exception:
                    pass

    # ------------------------------------------------------------------ #
    # Phase 7.5: Smart Prefix Deduplication & Statement Replacement
    # ------------------------------------------------------------------ #
    def wait_idle(self, timeout: float = 2.0) -> bool:
        """Waits until all pending queued tasks have been processed."""
        if not self.async_mode or self._worker_thread is None:
            return True
        try:
            self._task_queue.join()
            return True
        except Exception:
            return False

    def stop(self, timeout: float = 1.0) -> None:
        """Gracefully terminates the background worker thread and releases input state."""
        if self._worker_thread is not None and self._worker_thread.is_alive():
            self._stop_event.set()
            try:
                self._task_queue.put_nowait(None)
            except queue.Full:
                pass
            self._worker_thread.join(timeout=timeout)
        self.release_all_modifiers()
        callback = getattr(self, "release_game_keys", None)
        if callable(callback):
            try:
                callback()
            except Exception as exc:
                logger.warning("Could not release game keys during injector stop: %s", exc)

