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

logger = logging.getLogger("eyede.actions.code_injector")


class DummyKeyboard:
    """Fallback dummy keyboard for testing and headless environments without display."""

    def __init__(self):
        self.pressed_keys = []
        self.tapped_keys = []

    def press(self, key):
        self.pressed_keys.append(key)

    def release(self, key):
        if key in self.pressed_keys:
            self.pressed_keys.remove(key)

    def tap(self, key):
        self.tapped_keys.append(key)


class DummyClipboard:
    """Fallback dummy clipboard for testing and headless environments."""

    def __init__(self, initial_text: str = ""):
        self._text = initial_text

    def paste(self) -> str:
        return self._text

    def copy(self, text: str):
        self._text = text


class CodeInjector:
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
    # Phase 7.5: Smart Prefix Deduplication
    # ------------------------------------------------------------------ #
    def set_current_word_prefix(self, prefix: str) -> None:
        """Allows the overlay/ContextReader to seed the physical-typing prefix."""
        with self._prefix_lock:
            self._current_word_prefix = (prefix or "")[-64:]

    def prepare_insert_text(self, text: str) -> Tuple[str, int]:
        """Returns (text_to_insert, backspaces_needed) and advances the prefix tracker.

        If the user already typed "h" and then selects "hola", this returns
        ("ola", 0). If the selected word changes case ("Hola"), it returns
        ("Hola", 1) so the injector can erase the stale prefix first.
        """
        if not text:
            return "", 0
        with self._prefix_lock:
            prefix = self._current_word_prefix
            prepared = text
            backspaces = 0
            stripped = text.strip()
            if prefix and stripped:
                if stripped.lower().startswith(prefix.lower()):
                    if len(stripped) > len(prefix):
                        if text[: len(prefix)] == prefix:
                            prepared = text[len(prefix):]
                        else:
                            backspaces = len(prefix)
                    elif len(text) > len(stripped):
                        # Exact word plus trailing space/punctuation: inject only the separator.
                        if text[: len(prefix)] == prefix:
                            prepared = text[len(prefix):]
                        else:
                            backspaces = len(prefix)
                    else:
                        # Selecting the same word that is already typed is a no-op.
                        prepared = ""
            self._update_prefix_after_insert(text)
            return prepared, backspaces

    def _update_prefix_after_insert(self, text: str) -> None:
        if not text:
            return
        if any(ch.isspace() for ch in text) or not all(
            ch.isalnum() or ch == "_" for ch in text
        ):
            self._current_word_prefix = ""
            return
        if len(text) == 1:
            self._current_word_prefix = (self._current_word_prefix + text)[-64:]
        else:
            self._current_word_prefix = text[-64:]

    def _track_key_effect(self, key_name: str) -> None:
        """Updates the prefix after a cursor/editing key."""
        norm = key_name.strip().upper().replace("_", "+")
        with self._prefix_lock:
            if norm in {"BACKSPACE"}:
                self._current_word_prefix = self._current_word_prefix[:-1]
            else:
                self._current_word_prefix = ""

    def insert_snippet(
        self,
        snippet: str,
        cursor_offset_left: int = 0,
        cursor_offset_up: int = 0,
        restore_clipboard: bool = True,
        paste_delay: Optional[float] = None,
        async_exec: Optional[bool] = None,
        drop_if_busy: bool = False,
    ) -> bool:
        """
        Injects a code snippet via clipboard copy and native paste (Ctrl+V / Cmd+V).
        Preserves original user clipboard and repositions cursor inside parentheses/blocks.

        Args:
            snippet: Text content to insert.
            cursor_offset_left: Number of left arrow taps after paste.
            cursor_offset_up: Number of up arrow taps after paste.
            restore_clipboard: Whether to restore old clipboard after paste.
            paste_delay: Optional override for paste delay in seconds.
            async_exec: True to force async, False to force sync, None to use self.async_mode.
            drop_if_busy: If True and an injection is actively running, drop without queuing.

        Returns:
            True if queued or completed successfully.
        """
        if drop_if_busy and self.is_busy:
            logger.debug("Snippet injection dropped because injector is busy.")
            return False

        is_async = self.async_mode if async_exec is None else async_exec
        delay = self.paste_delay if paste_delay is None else paste_delay

        prepared, backspaces = self.prepare_insert_text(snippet)
        if not prepared and backspaces == 0:
            return True

        if is_async:
            return self._enqueue(
                self._do_insert_snippet,
                (
                    prepared,
                    cursor_offset_left,
                    cursor_offset_up,
                    restore_clipboard,
                    delay,
                    backspaces,
                ),
                {},
            )
        else:
            return self._do_insert_snippet(
                prepared,
                cursor_offset_left,
                cursor_offset_up,
                restore_clipboard,
                delay,
                backspaces,
            )

    def set_clipboard_history(self, manager: Optional[Any]) -> None:
        self.clipboard_history = manager

    def _do_insert_snippet(
        self,
        snippet: str,
        cursor_offset_left: int,
        cursor_offset_up: int,
        restore_clipboard: bool,
        delay: float,
        backspaces: int = 0,
    ) -> bool:
        """Runs insertion inside the clipboard-history internal-write lock."""
        guard = (
            self.clipboard_history.ignore_internal_writes()
            if self.clipboard_history is not None
            else nullcontext()
        )
        with guard:
            return self._do_insert_snippet_locked(
                snippet,
                cursor_offset_left,
                cursor_offset_up,
                restore_clipboard,
                delay,
                backspaces,
            )

    def _do_insert_snippet_locked(
        self,
        snippet: str,
        cursor_offset_left: int,
        cursor_offset_up: int,
        restore_clipboard: bool,
        delay: float,
        backspaces: int = 0,
    ) -> bool:
        """Synchronous implementation of snippet insertion with guaranteed clipboard restoration."""
        # 1. Read and save existing clipboard
        old_clipboard = ""
        has_old_clipboard = False
        val = self._clipboard_paste()
        if isinstance(val, str):
            old_clipboard = val
            has_old_clipboard = True

        # 2. Copy snippet into clipboard with retry/backoff.
        if not self._clipboard_copy(snippet):
            logger.error("Failed to copy snippet to clipboard after retries.")
            return False

        # Controlled pause for OS clipboard propagation (prevents race condition)
        time.sleep(0.015)

        success = False
        try:
            # 2b. Erase a stale prefix when the selected word changes case.
            if backspaces > 0:
                backspace_key = Key.backspace if Key is not None else "BACKSPACE"
                for _ in range(backspaces):
                    self.keyboard.tap(backspace_key)
                time.sleep(0.01)

            # 3. Send native paste shortcut (Ctrl+V / Cmd+V) with guaranteed modifier release
            with self.hold_modifiers(self.primary_modifier):
                self.keyboard.tap('v')

            # 4. Controlled pause to allow target IDE to ingest clipboard contents
            time.sleep(delay)

            # 5. Execute cursor offsets to position cursor inside block/parens
            self._apply_cursor_offsets(cursor_offset_left, cursor_offset_up)
            success = True
        except Exception as e:
            logger.error(f"Error during paste keystroke execution: {e}")
            success = False
        finally:
            # Guarantee all modifier keys are completely released under all circumstances
            self.release_all_modifiers()
            # 6. Restore original user clipboard (guaranteed in finally)
            if restore_clipboard and has_old_clipboard and isinstance(old_clipboard, str):
                time.sleep(0.015)
                self._clipboard_copy(old_clipboard)

        return success

    def _apply_cursor_offsets(self, offset_left: int, offset_up: int) -> None:
        """
        Applies up and left arrow keys to leave cursor in target position.
        Note: UP is executed before LEFT so multi-line line targeting is not corrupted by horizontal wrapping.
        """
        up_key = Key.up if Key is not None else "UP"
        left_key = Key.left if Key is not None else "LEFT"

        # Apply UP arrows first to navigate to target line
        if offset_up > 0:
            for _ in range(offset_up):
                self.keyboard.tap(up_key)
                if offset_up > 1:
                    time.sleep(0.005)

        # Apply LEFT arrows on the target line
        if offset_left > 0:
            for _ in range(offset_left):
                self.keyboard.tap(left_key)
                if offset_left > 1:
                    time.sleep(0.005)

    def send_key(self, key_name: str, async_exec: Optional[bool] = None) -> bool:
        """
        Sends a direct keyboard shortcut or editing command.

        Supported commands:
        ENTER, TAB, SHIFT_TAB, SPACE, BACKSPACE, CTRL_BACKSPACE, DELETE_LINE,
        UNDO, REDO, SAVE, COMMENT, UP, DOWN, LEFT, RIGHT, HOME, END,
        WORD_LEFT, WORD_RIGHT, ENTER_TWICE.
        """
        is_async = self.async_mode if async_exec is None else async_exec

        if is_async:
            return self._enqueue(self._do_send_key, (key_name,), {})
        else:
            return self._do_send_key(key_name)

    def _do_send_key(self, key_name: str) -> bool:
        """Synchronous implementation of keystroke sending with comprehensive alias support."""
        if Key is None:
            return False

        key_raw = key_name.strip().upper()
        # Create normalized variants with both '+' and '_' to accept any format
        norm_plus = key_raw.replace("_", "+").replace("-", "+")
        norm_under = key_raw.replace("+", "_").replace("-", "_")
        aliases = {key_raw, norm_plus, norm_under}

        try:
            if aliases & {"ENTER", "RETURN"}:
                self.keyboard.tap(Key.enter)
            elif aliases & {"TAB"}:
                self.keyboard.tap(Key.tab)
            elif aliases & {"SHIFT+TAB", "SHIFT_TAB", "UNINDENT"}:
                with self.hold_modifiers(Key.shift):
                    self.keyboard.tap(Key.tab)
            elif aliases & {"SPACE"}:
                self.keyboard.tap(Key.space)
            elif aliases & {"BACKSPACE"}:
                self.keyboard.tap(Key.backspace)
            elif aliases & {"CTRL+BACKSPACE", "CTRL_BACKSPACE", "DELETE_WORD", "ALT+BACKSPACE", "ALT_BACKSPACE"}:
                mod = Key.alt if self.is_macos else Key.ctrl
                with self.hold_modifiers(mod):
                    self.keyboard.tap(Key.backspace)
            elif aliases & {"DELETE_LINE", "CTRL+SHIFT+K", "CTRL_SHIFT_K", "CMD+SHIFT+K"}:
                # Ctrl+Shift+K on Windows/Linux, Cmd+Shift+K on macOS (VS Code native)
                with self.hold_modifiers(self.primary_modifier, Key.shift):
                    self.keyboard.tap('k')
            elif aliases & {"UNDO", "CTRL+Z", "CTRL_Z", "CMD+Z"}:
                with self.hold_modifiers(self.primary_modifier):
                    self.keyboard.tap('z')
            elif aliases & {"REDO", "CTRL+Y", "CTRL_Y", "CTRL+SHIFT+Z", "CTRL_SHIFT_Z", "CMD+SHIFT+Z"}:
                if self.is_macos:
                    with self.hold_modifiers(self.primary_modifier, Key.shift):
                        self.keyboard.tap('z')
                else:
                    with self.hold_modifiers(self.primary_modifier):
                        self.keyboard.tap('y')
            elif aliases & {"SAVE", "CTRL+S", "CTRL_S", "CMD+S"}:
                with self.hold_modifiers(self.primary_modifier):
                    self.keyboard.tap('s')
            elif aliases & {"COMMENT", "TOGGLE_COMMENT", "CTRL+/", "CTRL_SLASH", "CMD+/"}:
                with self.hold_modifiers(self.primary_modifier):
                    self.keyboard.tap('/')
            elif aliases & {"UP", "ARROW_UP"}:
                self.keyboard.tap(Key.up)
            elif aliases & {"DOWN", "ARROW_DOWN"}:
                self.keyboard.tap(Key.down)
            elif aliases & {"LEFT", "ARROW_LEFT"}:
                self.keyboard.tap(Key.left)
            elif aliases & {"RIGHT", "ARROW_RIGHT"}:
                self.keyboard.tap(Key.right)
            elif aliases & {"HOME"}:
                self.keyboard.tap(Key.home)
            elif aliases & {"END"}:
                self.keyboard.tap(Key.end)
            elif aliases & {"PAGE_UP", "PAGEUP", "PGUP"}:
                self.keyboard.tap(Key.page_up if hasattr(Key, "page_up") else Key.up)
            elif aliases & {"PAGE_DOWN", "PAGEDOWN", "PGDN"}:
                self.keyboard.tap(Key.page_down if hasattr(Key, "page_down") else Key.down)
            elif aliases & {"ESC", "ESCAPE"}:
                self.keyboard.tap(Key.esc if hasattr(Key, "esc") else Key.backspace)
            elif aliases & {"WORD_LEFT", "CTRL+LEFT", "CTRL_LEFT", "ALT+LEFT"}:
                mod = Key.alt if self.is_macos else Key.ctrl
                with self.hold_modifiers(mod):
                    self.keyboard.tap(Key.left)
            elif aliases & {"WORD_RIGHT", "CTRL+RIGHT", "CTRL_RIGHT", "ALT+RIGHT"}:
                mod = Key.alt if self.is_macos else Key.ctrl
                with self.hold_modifiers(mod):
                    self.keyboard.tap(Key.right)
            elif aliases & {"ENTER_TWICE", "2X_ENTER"}:
                self.keyboard.tap(Key.enter)
                time.sleep(0.02)
                self.keyboard.tap(Key.enter)
            elif aliases & {"PASTE", "CTRL+V", "CTRL_V", "CMD+V"}:
                with self.hold_modifiers(self.primary_modifier):
                    self.keyboard.tap('v')
            elif aliases & {"COPY", "CTRL+C", "CTRL_C", "CMD+C"}:
                with self.hold_modifiers(self.primary_modifier):
                    self.keyboard.tap('c')
            elif aliases & {"CUT", "CTRL+X", "CTRL_X", "CMD+X"}:
                with self.hold_modifiers(self.primary_modifier):
                    self.keyboard.tap('x')
            elif aliases & {"SELECT_ALL", "CTRL+A", "CTRL_A", "CMD+A"}:
                with self.hold_modifiers(self.primary_modifier):
                    self.keyboard.tap('a')
            else:
                logger.warning(f"Unrecognized key action: {key_name}")
                return False

            self._track_key_effect(key_name)
            return True
        except Exception as e:
            logger.error(f"Error sending key '{key_name}': {e}", exc_info=True)
            return False
        finally:
            self.release_all_modifiers()

    def set_websocket_bridge(self, bridge: Any) -> None:
        """Sets or clears the WebSocketBridge for native VS Code dispatch."""
        self.websocket_bridge = bridge

    @property
    def has_native_websocket(self) -> bool:
        """Returns True if a WebSocketBridge is assigned and currently has connected clients."""
        return self.websocket_bridge is not None and getattr(self.websocket_bridge, "is_connected", False)

    def execute_action(self, action: Any, async_exec: Optional[bool] = None) -> bool:
        """
        Dispatches an action based on its MenuAction attributes.
        Prioritizes native VS Code WebSocket bridge if connected, otherwise falls
        back safely to OS-level virtual input (pyperclip + pynput).
        """
        if not hasattr(action, "action_type"):
            return False

        atype = action.action_type.upper()

        # Check if native VS Code WebSocket bridge is available and connected
        ws = getattr(self, "websocket_bridge", None)
        if ws is not None and getattr(ws, "is_connected", False):
            if atype == "SNIPPET" and getattr(action, "snippet", None):
                offset_left = getattr(action, "cursor_offset_left", 0)
                offset_up = getattr(action, "cursor_offset_up", 0)
                prepared, backspaces = self.prepare_insert_text(action.snippet)
                for _ in range(backspaces):
                    ws.send_execute_command("deleteLeft")
                if prepared:
                    sent = ws.send_insert_snippet(
                        snippet=prepared,
                        cursor_offset_left=offset_left,
                        cursor_offset_up=offset_up,
                        tabstops=True,
                    )
                    if sent:
                        return True
                elif backspaces:
                    return True

            elif atype == "KEY" and getattr(action, "key_name", None):
                kname = action.key_name.upper().strip()
                ws_key_map = {
                    "UNDO": "undo",
                    "REDO": "redo",
                    "SAVE": "workbench.action.files.save",
                    "FORMAT": "editor.action.formatDocument",
                    "UP": "cursorUp",
                    "DOWN": "cursorDown",
                    "LEFT": "cursorLeft",
                    "RIGHT": "cursorRight",
                    "HOME": "cursorLineStart",
                    "END": "cursorLineEnd",
                    "BACKSPACE": "deleteLeft",
                    "DELETE_LINE": "editor.action.deleteLines",
                    "COMMENT": "editor.action.commentLine",
                    "TAB": "tab",
                    "SHIFT_TAB": "outdent",
                    "ENTER": "type",
                    "SPACE": "type",
                }
                cmd = ws_key_map.get(kname)
                if cmd:
                    args = [{"text": "\n"}] if kname == "ENTER" else ([{"text": " "}] if kname == "SPACE" else None)
                    sent = ws.send_execute_command(cmd, args)
                    if sent:
                        self._track_key_effect(kname)
                        return True

        # Fallback to OS-level virtual input
        if atype == "SNIPPET" and getattr(action, "snippet", None):
            return self.insert_snippet(
                snippet=action.snippet,
                cursor_offset_left=getattr(action, "cursor_offset_left", 0),
                cursor_offset_up=getattr(action, "cursor_offset_up", 0),
                async_exec=async_exec,
            )
        elif atype == "KEY" and getattr(action, "key_name", None):
            return self.send_key(action.key_name, async_exec=async_exec)

        return False


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
