"""Key sending and action dispatch for CodeInjector."""

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


class KeyDispatchMixin:
    """Key press and action execution logic."""

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
            elif aliases & {"FORMAT", "SHIFT+ALT+F", "SHIFT_ALT_F"}:
                with self.hold_modifiers(Key.shift, Key.alt):
                    self.keyboard.tap('f')
            elif aliases & {"COMMAND_PALETTE", "VSCODE_PALETTE", "CTRL+SHIFT+P", "CTRL_SHIFT_P"}:
                with self.hold_modifiers(self.primary_modifier, Key.shift):
                    self.keyboard.tap('p')
            elif aliases & {"TERMINAL", "CTRL+`", "CTRL_BACKTICK"}:
                with self.hold_modifiers(self.primary_modifier):
                    self.keyboard.tap('`')
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

    @staticmethod
    def embed_vscode_snippet_cursor(snippet: str, offset_left: int = 0, offset_up: int = 0) -> str:
        """Embeds $0 in a snippet for VS Code if tabstops are not already defined."""
        if not snippet or "$0" in snippet or "$1" in snippet or (offset_left == 0 and offset_up == 0):
            return snippet
        lines = snippet.splitlines(keepends=True)
        if not lines:
            return snippet
        target_line_idx = len(lines) - 1 - max(0, offset_up)
        if 0 <= target_line_idx < len(lines):
            line = lines[target_line_idx]
            nl = "\n" if line.endswith("\n") else ("\r\n" if line.endswith("\r\n") else "")
            raw_line = line[:-len(nl)] if nl else line
            target_char_idx = max(0, len(raw_line) - max(0, offset_left))
            lines[target_line_idx] = raw_line[:target_char_idx] + "$0" + raw_line[target_char_idx:] + nl
            return "".join(lines)
        return snippet


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
                prefix_before = self._current_word_prefix
                prepared, backspaces = self.prepare_insert_text(action.snippet)
                offset_left = self._effective_cursor_offset_left(
                    prepared,
                    offset_left,
                    prefix_before,
                )
                is_statement_replacement = prepared.strip().startswith(("if ", "if(", "elif ", "elif("))
                if not is_statement_replacement:
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
                    "COMMAND_PALETTE": "workbench.action.showCommands",
                    "TERMINAL": "workbench.action.terminal.toggleTerminal",
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
