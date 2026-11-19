"""Snippet insertion, prefix tracking and cursor offsets for CodeInjector."""

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


class SnippetInsertMixin:
    """Snippet insertion logic."""

    def set_context_reader(self, reader: Optional[Any]) -> None:
        """Assigns the ContextReader instance for live editor context awareness."""
        self._context_reader = reader

    def set_current_word_prefix(self, prefix: str) -> None:
        """Allows the overlay/ContextReader to seed the physical-typing prefix."""
        with self._prefix_lock:
            self._current_word_prefix = (prefix or "")[-64:]

    def set_last_statement_prefix(self, prefix: str) -> None:
        """Seeds the recent control-flow statement prefix (e.g. 'if ()')."""
        with self._prefix_lock:
            self._last_statement_prefix = str(prefix or "").strip()

    def prepare_insert_text(self, text: str) -> Tuple[str, int]:
        """Returns (text_to_insert, backspaces_needed) and advances the prefix tracker.

        If the user already typed "h" and then selects "hola", this returns
        ("ola", 0). If the selected word changes case ("Hola"), it returns
        ("Hola", 1) so the injector can erase the stale prefix first.
        If the user typed or inserted 'if ()', 'if (', or 'if', and then selects
        an if-suggestion ('if condition:', 'if (x):', 'elif condition:'), this
        returns ('if condition:', backspaces) so the typed if() is replaced.
        """
        if not text:
            return "", 0
        with self._prefix_lock:
            prefix = self._current_word_prefix
            prepared = text
            backspaces = 0
            stripped = text.strip()

            # Statement-level replacement for if/while/for/elif suggestions
            is_if_suggestion = stripped.startswith(("if ", "if(", "elif ", "elif("))
            if is_if_suggestion:
                target_erasure = ""
                inside_parens = False
                if self._last_statement_prefix in {"if ()", "if()", "if (", "if(", "if :", "if ():", "if"}:
                    target_erasure = self._last_statement_prefix
                    if target_erasure in {"if ()", "if()"}:
                        inside_parens = True
                elif prefix.lower() in {"if", "if()", "if ()", "if("}:
                    target_erasure = prefix
                    if target_erasure in {"if ()", "if()"}:
                        inside_parens = True
                elif self._context_reader is not None:
                    try:
                        ctx = self._context_reader.get_editor_context() if hasattr(self._context_reader, "get_editor_context") else {}
                        curr_line = str(ctx.get("current_line") or "").strip()
                        for cand in ("if ()", "if()", "if (", "if(", "if :", "if"):
                            if curr_line.endswith(cand):
                                target_erasure = cand
                                if cand in {"if ()", "if()"}:
                                    inside_parens = True
                                break
                    except Exception:
                        pass
                if target_erasure:
                    backspaces = len(target_erasure)
                    self._last_statement_inside_parens = inside_parens
                    self._last_statement_prefix = ""
                    self._current_word_prefix = ""
                    self._update_prefix_after_insert(text)
                    return prepared, backspaces

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
        clean = text.strip()
        if clean in {"if ()", "if()", "if (", "if(", "if", "if :", "if ():"}:
            self._last_statement_prefix = clean
        elif not clean.startswith(("if", "elif", "while", "for")):
            self._last_statement_prefix = ""

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
                self._last_statement_prefix = self._last_statement_prefix[:-1]
            else:
                self._current_word_prefix = ""
                self._last_statement_prefix = ""

    def _effective_cursor_offset_left(
        self,
        prepared: str,
        offset_left: int,
        prefix_before: str,
    ) -> int:
        """Avoid landing inside a closing pair when completing a call/name.

        Example: after typing ``func``, inserting ``()`` should leave the
        cursor after ``func()`` so the next token (for example ``:``) is
        appended in the right place. When the pair is inserted at an empty
        position, keep the historical centered cursor.
        For control flow structures (if, while, for, elif), the cursor must land
        inside the pair so the condition can be written immediately: if (|).
        """
        pairs = {"()", "[]", "{}", '""', "''"}
        control_flow = {"if", "elif", "while", "for", "switch", "catch", "assert"}

        # 1. Condition parens after control-flow: place caret inside parens so condition can be typed
        if prepared == "()":
            p_strip = prefix_before.strip().lower() if prefix_before else ""
            last_stmt = self._last_statement_prefix.strip().lower() if self._last_statement_prefix else ""
            ctx_line = ""
            if self._context_reader and hasattr(self._context_reader, "get_last_line"):
                try:
                    ctx_line = str(self._context_reader.get_last_line() or "").strip().lower()
                except Exception:
                    pass
            is_cf = (
                p_strip in control_flow or
                last_stmt in control_flow or
                any(ctx_line.endswith(cf) or ctx_line.endswith(f"{cf} ") for cf in control_flow)
            )
            if is_cf:
                return 1
            if prefix_before and prepared in pairs:
                return 0

        # 2. Control flow statements with empty parens
        prep_strip = prepared.strip()
        if prep_strip.startswith(("if ()", "if()", "elif ()", "elif()", "while ()", "while()")):
            if prep_strip.endswith(":"):
                return 2  # inside if (|):
            return 1      # inside if (|)

        if prefix_before and prefix_before.strip().lower() in control_flow:
            return max(1, int(offset_left)) if offset_left else 1
        if prefix_before and prepared in pairs:
            return 0
        try:
            return max(0, int(offset_left))
        except (TypeError, ValueError):
            return 0

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

        prefix_before = self._current_word_prefix
        prepared, backspaces = self.prepare_insert_text(snippet)
        if not prepared and backspaces == 0:
            return True
        effective_left = self._effective_cursor_offset_left(
            prepared,
            cursor_offset_left,
            prefix_before,
        )

        if is_async:
            return self._enqueue(
                self._do_insert_snippet,
                (
                    prepared,
                    effective_left,
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
                effective_left,
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
            # 2b. Erase a stale prefix when the selected word changes case or replaces if().
            if getattr(self, "_last_statement_inside_parens", False):
                right_key = Key.right if Key is not None else "RIGHT"
                self.keyboard.tap(right_key)
                time.sleep(0.005)
                self._last_statement_inside_parens = False

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
