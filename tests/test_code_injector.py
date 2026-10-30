"""
Automated Forensic Test Suite: Code Injector (Phase Extra)
Mocks pynput and pyperclip to verify insert_snippet(), cursor offsets (up and left),
clipboard restoration, anti-stuck modifier safety guarantees, and asynchronous execution.
"""

import os
import sys
import time
import unittest
from typing import List, Any, Optional

# Ensure project root is in sys.path
_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_IDEYE_DIR = os.path.join(_ROOT_DIR, "ideye")
for p in (_ROOT_DIR, _IDEYE_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

from ideye.actions.code_injector import CodeInjector
from ideye.actions.menu_trees import MenuAction

try:
    from pynput.keyboard import Key
except Exception:
    Key = None


class MockRecorderKeyboard:
    """Mock keyboard controller that records presses, releases, and taps."""

    def __init__(self, raise_on_v_tap: bool = False):
        self.pressed: List[Any] = []
        self.released: List[Any] = []
        self.tapped: List[Any] = []
        self.events: List[tuple] = []
        self.raise_on_v_tap = raise_on_v_tap

    def press(self, key):
        self.pressed.append(key)
        self.events.append(("PRESS", key))

    def release(self, key):
        self.released.append(key)
        self.events.append(("RELEASE", key))

    def tap(self, key):
        if self.raise_on_v_tap and key == 'v':
            raise RuntimeError("Simulated sudden keyboard hardware failure during paste")
        self.tapped.append(key)
        self.events.append(("TAP", key))


class MockClipboard:
    """Mock clipboard module that tracks copy and paste calls."""

    def __init__(self, initial_text: str = ""):
        self.contents = initial_text
        self.copy_history: List[str] = []

    def paste(self) -> str:
        return self.contents

    def copy(self, text: str):
        self.contents = text
        self.copy_history.append(text)


class TestCodeInjector(unittest.TestCase):
    """Deep verification of CodeInjector snippet insertion, clipboard preservation, and modifier safety."""

    def test_insert_snippet_basic_paste_and_clipboard_restoration(self):
        """Snippet must be copied, pasted via primary modifier + v, and old clipboard restored."""
        mock_kb = MockRecorderKeyboard()
        mock_clip = MockClipboard(initial_text="pre-existing clipboard text")

        injector = CodeInjector(
            async_mode=False,
            paste_delay=0.001,
            keyboard_controller=mock_kb,
            clipboard_module=mock_clip,
        )

        res = injector.insert_snippet("def calculate_total():\n    pass", restore_clipboard=True)
        self.assertTrue(res)

        # 1. Clipboard received snippet first, then restored to initial text
        self.assertGreaterEqual(len(mock_clip.copy_history), 2)
        self.assertEqual(mock_clip.copy_history[0], "def calculate_total():\n    pass")
        self.assertEqual(mock_clip.copy_history[-1], "pre-existing clipboard text")
        self.assertEqual(mock_clip.paste(), "pre-existing clipboard text")

        # 2. 'v' was tapped while primary modifier was held
        self.assertIn('v', mock_kb.tapped)
        # Check that primary modifier was pressed and released
        self.assertIn(injector.primary_modifier, mock_kb.pressed)
        self.assertIn(injector.primary_modifier, mock_kb.released)

    def test_cursor_offsets_up_and_left(self):
        """Cursor offsets must tap UP arrows first, then LEFT arrows the exact requested count."""
        mock_kb = MockRecorderKeyboard()
        mock_clip = MockClipboard(initial_text="")

        injector = CodeInjector(
            async_mode=False,
            paste_delay=0.001,
            keyboard_controller=mock_kb,
            clipboard_module=mock_clip,
        )

        # Snippet with 3 chars back (e.g. inside parens) and 1 line up
        res = injector.insert_snippet(
            snippet="for item in collection:\n    ",
            cursor_offset_left=3,
            cursor_offset_up=1,
            restore_clipboard=False,
        )
        self.assertTrue(res)

        # Check arrow key taps
        up_key = Key.up if Key is not None else "UP"
        left_key = Key.left if Key is not None else "LEFT"

        up_taps = [k for k in mock_kb.tapped if k == up_key]
        left_taps = [k for k in mock_kb.tapped if k == left_key]

        self.assertEqual(len(up_taps), 1)
        self.assertEqual(len(left_taps), 3)

        # Verify UP occurred before LEFT in sequence
        first_up_idx = mock_kb.tapped.index(up_key)
        first_left_idx = mock_kb.tapped.index(left_key)
        self.assertLess(first_up_idx, first_left_idx)

    def test_anti_stuck_modifiers_on_unexpected_exception(self):
        """If paste throws an unexpected exception, all modifiers MUST be released in finally."""
        mock_kb = MockRecorderKeyboard(raise_on_v_tap=True)
        mock_clip = MockClipboard(initial_text="important data")

        injector = CodeInjector(
            async_mode=False,
            paste_delay=0.001,
            keyboard_controller=mock_kb,
            clipboard_module=mock_clip,
        )

        res = injector.insert_snippet("bad snippet", restore_clipboard=True)
        # Insertion returned False due to exception
        self.assertFalse(res)

        # Modifier was pressed during attempt
        self.assertIn(injector.primary_modifier, mock_kb.pressed)
        # CRITICAL: Modifier was explicitly released in finally despite exception!
        self.assertIn(injector.primary_modifier, mock_kb.released)
        # Clipboard was also restored
        self.assertEqual(mock_clip.paste(), "important data")

    def test_send_key_shortcuts_and_modifier_release(self):
        """send_key() must trigger correct keys and release all modifiers."""
        mock_kb = MockRecorderKeyboard()
        mock_clip = MockClipboard()

        injector = CodeInjector(
            async_mode=False,
            keyboard_controller=mock_kb,
            clipboard_module=mock_clip,
        )

        # 1. Simple key: ENTER
        ok_enter = injector.send_key("ENTER")
        self.assertTrue(ok_enter)
        enter_key = Key.enter if Key is not None else "ENTER"
        self.assertIn(enter_key, mock_kb.tapped)

        # 2. Modifier shortcut: DELETE_LINE (Ctrl+Shift+K or Cmd+Shift+K)
        ok_del = injector.send_key("DELETE_LINE")
        self.assertTrue(ok_del)
        self.assertIn('k', mock_kb.tapped)
        # Shift must have been released
        if Key is not None:
            self.assertIn(Key.shift, mock_kb.released)

        # 3. UNDO (Ctrl+Z)
        ok_undo = injector.send_key("UNDO")
        self.assertTrue(ok_undo)
        self.assertIn('z', mock_kb.tapped)
        self.assertIn(injector.primary_modifier, mock_kb.released)

    def test_async_worker_queue_execution_and_stop(self):
        """In async_mode=True, tasks run on background thread and injector stops cleanly."""
        mock_kb = MockRecorderKeyboard()
        mock_clip = MockClipboard(initial_text="start")

        injector = CodeInjector(
            async_mode=True,
            paste_delay=0.005,
            keyboard_controller=mock_kb,
            clipboard_module=mock_clip,
        )

        # Dispatch async action
        action = MenuAction(
            id="TEST_ACT",
            label="Test Action",
            action_type="SNIPPET",
            snippet="async_code = 1",
            cursor_offset_left=1,
        )
        ok = injector.execute_action(action)
        self.assertTrue(ok)

        # Wait for worker thread to finish processing
        injector.wait_idle(timeout=2.0)
        self.assertIn('v', mock_kb.tapped)
        self.assertIn("async_code = 1", mock_clip.copy_history)

        # Stop worker thread
        injector.stop()
        self.assertFalse(injector._worker_thread.is_alive())

    def test_non_string_clipboard_safety(self):
        """If clipboard contains non-string data (e.g. None or binary object), injector does not crash."""
        mock_kb = MockRecorderKeyboard()
        mock_clip = MockClipboard()
        mock_clip.contents = None  # Non-string clipboard

        injector = CodeInjector(
            async_mode=False,
            keyboard_controller=mock_kb,
            clipboard_module=mock_clip,
        )

        ok = injector.insert_snippet("x = 42", restore_clipboard=True)
        self.assertTrue(ok)
        self.assertIn('v', mock_kb.tapped)
        self.assertEqual(mock_clip.paste(), "x = 42")


    def test_delimiter_after_word_places_cursor_after_pair(self):
        """After a typed name, () must leave the cursor after func(), not inside."""
        mock_kb = MockRecorderKeyboard()
        injector = CodeInjector(
            async_mode=False,
            paste_delay=0.001,
            keyboard_controller=mock_kb,
            clipboard_module=MockClipboard(),
        )
        injector.set_current_word_prefix("func")
        self.assertTrue(injector.insert_snippet("()", cursor_offset_left=1, restore_clipboard=False))
        left_key = Key.left if Key is not None else "LEFT"
        self.assertEqual([k for k in mock_kb.tapped if k == left_key], [])

    def test_delimiter_at_empty_position_keeps_centered_cursor(self):
        """An empty () keeps the historical centered cursor for grouping."""
        mock_kb = MockRecorderKeyboard()
        injector = CodeInjector(
            async_mode=False,
            paste_delay=0.001,
            keyboard_controller=mock_kb,
            clipboard_module=MockClipboard(),
        )
        injector.set_current_word_prefix("")
        self.assertTrue(injector.insert_snippet("()", cursor_offset_left=1, restore_clipboard=False))
        left_key = Key.left if Key is not None else "LEFT"
        self.assertEqual(len([k for k in mock_kb.tapped if k == left_key]), 1)

    def test_websocket_delimiter_uses_adjusted_cursor_offset(self):
        """VS Code bridge receives the same smart offset as the OS path."""
        class FakeBridge:
            is_connected = True

            def __init__(self):
                self.inserts = []
                self.commands = []

            def send_execute_command(self, command, args=None):
                self.commands.append((command, args))
                return True

            def send_insert_snippet(self, snippet, cursor_offset_left=0, cursor_offset_up=0, tabstops=True):
                self.inserts.append((snippet, cursor_offset_left, cursor_offset_up, tabstops))
                return True

        bridge = FakeBridge()
        injector = CodeInjector(
            async_mode=False,
            keyboard_controller=MockRecorderKeyboard(),
            clipboard_module=MockClipboard(),
        )
        injector.set_websocket_bridge(bridge)
        injector.set_current_word_prefix("func")
        action = MenuAction(
            id="DELIM_PAREN",
            label="1: ()",
            action_type="SNIPPET",
            snippet="()",
            cursor_offset_left=1,
        )
        self.assertTrue(injector.execute_action(action))
        self.assertEqual(bridge.inserts[0][0], "()")
        self.assertEqual(bridge.inserts[0][1], 0)


if __name__ == "__main__":
    unittest.main()
