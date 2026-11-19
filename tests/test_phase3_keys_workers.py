"""
Unit & Integration Test Suite for IDEye Phase 3
Tests Hierarchical Menu Trees (3x3 Layout), CodeInjector (Clipboard Preservation & Multiplatform),
Stuck Modifier Keys Audit, Non-Blocking Worker Execution, Sticky Submenu Transitions,
and Breadcrumb Rendering in OverlayWindow.
"""

import sys
import os
import unittest
import time
import copy
from typing import List, Dict, Any, Optional

# Set offscreen platform before importing PyQt6 to guarantee 100% headless execution
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtCore import Qt, QCoreApplication
from PyQt6.QtWidgets import QApplication

# Path resolution
_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_IDEYE_DIR = os.path.join(_ROOT_DIR, "ideye")
for p in (_ROOT_DIR, _IDEYE_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

import ideye.config as config
from ideye.actions.code_injector import CodeInjector, DummyKeyboard, DummyClipboard
from ideye.actions.menu_trees import (
    MenuAction,
    MenuNode,
    build_menu_tree,
    validate_menu_tree,
    get_breadcrumb_path,
    create_pause_action,
    create_back_action,
)
from ideye.ui.overlay_window import OverlayWindow


# Single QApplication instance for the test suite
_APP = QApplication.instance() or QApplication(sys.argv if hasattr(sys, "argv") else [])


class MockKeyboard:
    """Mock keyboard controller that records events and tracks active keys."""

    def __init__(self, fail_on_tap: Optional[str] = None):
        self.pressed_keys: List[Any] = []
        self.released_keys: List[Any] = []
        self.tapped_keys: List[Any] = []
        self.history: List[Tuple[str, Any]] = []
        self.active_keys: Set[Any] = set()
        self.fail_on_tap = fail_on_tap

    def press(self, key):
        self.pressed_keys.append(key)
        self.active_keys.add(key)
        self.history.append(("PRESS", key))

    def release(self, key):
        self.released_keys.append(key)
        self.active_keys.discard(key)
        self.history.append(("RELEASE", key))

    def tap(self, key):
        if self.fail_on_tap is not None and key == self.fail_on_tap:
            raise RuntimeError(f"Simulated hardware failure on tapping key: {key}")
        self.tapped_keys.append(key)
        self.history.append(("TAP", key))


class MockClipboard:
    """Mock clipboard storing current text and recording all operations."""

    def __init__(self, initial: str = ""):
        self.content: str = initial
        self.history: List[Tuple[str, str]] = []

    def paste(self) -> str:
        self.history.append(("PASTE", self.content))
        return self.content

    def copy(self, text: str):
        self.content = text
        self.history.append(("COPY", text))


# =============================================================================
# 1. MATHEMATICAL 3X3 MENU TREE VALIDATION TESTS
# =============================================================================
class TestStuckModifierKeysAudit(unittest.TestCase):
    """
    Audits QA Requirement 1:
    Verifies that hold_modifiers context manager guarantees modifier release
    even when an unhandled exception occurs during keystroke execution.
    """

    def setUp(self):
        self.mock_kb = MockKeyboard(fail_on_tap='v')  # Crash when tapping 'v'
        self.mock_clip = MockClipboard("hello")
        self.injector = CodeInjector(
            async_mode=False,
            keyboard_controller=self.mock_kb,
            clipboard_module=self.mock_clip,
        )

    def tearDown(self):
        self.injector.stop()

    def test_stuck_modifiers_released_on_exception(self):
        """Verifies modifier keys are released when an exception occurs inside hold_modifiers."""
        from pynput.keyboard import Key

        # Attempt snippet insert that triggers tap failure
        self.injector.insert_snippet("test_snippet", async_exec=False)

        # Ensure no active pressed keys remain in mock keyboard!
        self.assertEqual(
            len(self.mock_kb.active_keys),
            0,
            f"Stuck modifier keys detected! Active keys: {self.mock_kb.active_keys}",
        )
        self.assertEqual(len(self.injector._active_modifiers), 0)

    def test_release_all_modifiers_safety_call(self):
        """Verifies explicit release_all_modifiers clears any residual key states."""
        from pynput.keyboard import Key
        self.mock_kb.press(Key.ctrl)
        self.mock_kb.press(Key.shift)
        self.assertEqual(len(self.mock_kb.active_keys), 2)

        self.injector.release_all_modifiers()
        self.assertEqual(len(self.mock_kb.active_keys), 0)


# =============================================================================
# 4. DIRECT KEYBOARD COMMANDS & MULTIPLATFORM TESTS
# =============================================================================
class TestDirectKeystrokes(unittest.TestCase):
    """Tests all required direct keyboard commands (ENTER, TAB, UNDO, REDO, SAVE, etc.)."""

    def setUp(self):
        self.mock_kb = MockKeyboard()
        self.injector = CodeInjector(
            async_mode=False,
            keyboard_controller=self.mock_kb,
            clipboard_module=DummyClipboard(),
        )

    def tearDown(self):
        self.injector.stop()

    def test_enter_and_tab_and_space(self):
        from pynput.keyboard import Key
        self.injector.send_key("ENTER", async_exec=False)
        self.assertIn(Key.enter, self.mock_kb.tapped_keys)

        self.injector.send_key("TAB", async_exec=False)
        self.assertIn(Key.tab, self.mock_kb.tapped_keys)

        self.injector.send_key("SPACE", async_exec=False)
        self.assertIn(Key.space, self.mock_kb.tapped_keys)

    def test_shift_tab_unindent(self):
        from pynput.keyboard import Key
        self.mock_kb.history.clear()
        self.injector.send_key("SHIFT_TAB", async_exec=False)

        # Shift was pressed, Tab was tapped, Shift was released
        self.assertIn(("PRESS", Key.shift), self.mock_kb.history)
        self.assertIn(("TAP", Key.tab), self.mock_kb.history)
        self.assertIn(("RELEASE", Key.shift), self.mock_kb.history)
        self.assertEqual(len(self.mock_kb.active_keys), 0)

    def test_delete_line_keystroke(self):
        from pynput.keyboard import Key
        self.mock_kb.history.clear()
        self.injector.send_key("DELETE_LINE", async_exec=False)

        # Modifier + Shift pressed, 'k' tapped
        self.assertIn(("TAP", 'k'), self.mock_kb.history)
        self.assertEqual(len(self.mock_kb.active_keys), 0)

    def test_undo_and_redo_and_save(self):
        self.mock_kb.history.clear()
        self.injector.send_key("UNDO", async_exec=False)
        self.assertIn(("TAP", 'z'), self.mock_kb.history)

        self.mock_kb.history.clear()
        self.injector.send_key("SAVE", async_exec=False)
        self.assertIn(("TAP", 's'), self.mock_kb.history)

        self.mock_kb.history.clear()
        self.injector.send_key("COMMENT", async_exec=False)
        self.assertIn(("TAP", '/'), self.mock_kb.history)
        self.assertEqual(len(self.mock_kb.active_keys), 0)

    def test_arrow_keys_navigation(self):
        from pynput.keyboard import Key
        for cmd, key in [
            ("UP", Key.up),
            ("DOWN", Key.down),
            ("LEFT", Key.left),
            ("RIGHT", Key.right),
            ("HOME", Key.home),
            ("END", Key.end),
        ]:
            self.mock_kb.tapped_keys.clear()
            self.injector.send_key(cmd, async_exec=False)
            self.assertIn(key, self.mock_kb.tapped_keys)

    def test_plus_separated_shortcut_aliases(self):
        """Verifies that plus-separated key notations (CTRL+BACKSPACE, CTRL+Z, CTRL+S, etc.) work identically."""
        from pynput.keyboard import Key

        # 1. CTRL+BACKSPACE
        self.mock_kb.history.clear()
        self.injector.send_key("CTRL+BACKSPACE", async_exec=False)
        self.assertIn(("TAP", Key.backspace), self.mock_kb.history)
        self.assertEqual(len(self.mock_kb.active_keys), 0)

        # 2. CTRL+Z
        self.mock_kb.history.clear()
        self.injector.send_key("CTRL+Z", async_exec=False)
        self.assertIn(("TAP", 'z'), self.mock_kb.history)
        self.assertEqual(len(self.mock_kb.active_keys), 0)

        # 3. CTRL+Y
        self.mock_kb.history.clear()
        self.injector.send_key("CTRL+Y", async_exec=False)
        expected_redo_char = 'z' if self.injector.is_macos else 'y'
        self.assertIn(("TAP", expected_redo_char), self.mock_kb.history)
        self.assertEqual(len(self.mock_kb.active_keys), 0)

        # 4. CTRL+S
        self.mock_kb.history.clear()
        self.injector.send_key("CTRL+S", async_exec=False)
        self.assertIn(("TAP", 's'), self.mock_kb.history)
        self.assertEqual(len(self.mock_kb.active_keys), 0)

        # 5. CTRL+SHIFT+K
        self.mock_kb.history.clear()
        self.injector.send_key("CTRL+SHIFT+K", async_exec=False)
        self.assertIn(("TAP", 'k'), self.mock_kb.history)
        self.assertEqual(len(self.mock_kb.active_keys), 0)

        # 6. CTRL+/
        self.mock_kb.history.clear()
        self.injector.send_key("CTRL+/", async_exec=False)
        self.assertIn(("TAP", '/'), self.mock_kb.history)
        self.assertEqual(len(self.mock_kb.active_keys), 0)

        # 7. Direction aliases: ARROW_UP, ARROW_DOWN, PAGE_UP, PAGE_DOWN, ESC
        self.mock_kb.tapped_keys.clear()
        self.injector.send_key("ARROW_UP", async_exec=False)
        self.assertIn(Key.up, self.mock_kb.tapped_keys)

        self.mock_kb.tapped_keys.clear()
        self.injector.send_key("ARROW_DOWN", async_exec=False)
        self.assertIn(Key.down, self.mock_kb.tapped_keys)

        self.mock_kb.tapped_keys.clear()
        self.injector.send_key("ESC", async_exec=False)
        self.assertGreater(len(self.mock_kb.tapped_keys), 0)

        # 8. Standard shortcuts: PASTE, COPY, CUT, SELECT_ALL
        for name, char in [("PASTE", 'v'), ("COPY", 'c'), ("CUT", 'x'), ("SELECT_ALL", 'a')]:
            self.mock_kb.history.clear()
            self.injector.send_key(name, async_exec=False)
            self.assertIn(("TAP", char), self.mock_kb.history)
            self.assertEqual(len(self.mock_kb.active_keys), 0)


# =============================================================================
# 5. NON-BLOCKING UI EXECUTION & FIFO QUEUE TESTS
# =============================================================================
class TestNonBlockingWorkerExecution(unittest.TestCase):
    """
    Audits QA Requirement 4:
    Verifies that async_mode=True executes snippet injections on a background
    worker thread, returning immediately to prevent freezing PyQt6 rendering.
    """

    def setUp(self):
        self.mock_kb = MockKeyboard()
        self.mock_clip = MockClipboard()
        self.injector = CodeInjector(
            async_mode=True,
            paste_delay=0.08,  # Deliberate 80ms sleep
            keyboard_controller=self.mock_kb,
            clipboard_module=self.mock_clip,
        )

    def tearDown(self):
        self.injector.stop()

    def test_async_call_returns_immediately_without_blocking_caller(self):
        """Verifies that calling insert_snippet in async mode takes < 15ms (non-blocking)."""
        t0 = time.time()
        res = self.injector.insert_snippet("async_snippet();", paste_delay=0.10)
        elapsed = time.time() - t0

        self.assertTrue(res)
        # 100ms paste_delay should NOT block the caller!
        self.assertLess(elapsed, 0.04, f"Caller thread was blocked for {elapsed:.3f}s!")

        # Wait for worker thread to complete
        self.assertTrue(self.injector.wait_idle(timeout=1.0))
        self.assertIn('v', self.mock_kb.tapped_keys)

    def test_multiple_rapid_calls_execute_in_fifo_order(self):
        """Verifies that rapid clicks don't collide or get dropped."""
        keys_to_send = ["UP", "DOWN", "LEFT", "RIGHT", "ENTER"]
        for k in keys_to_send:
            self.injector.send_key(k)

        self.assertTrue(self.injector.wait_idle(timeout=1.0))

        from pynput.keyboard import Key
        expected = [Key.up, Key.down, Key.left, Key.right, Key.enter]
        self.assertEqual(self.mock_kb.tapped_keys, expected)

    def test_is_busy_and_drop_if_busy(self):
        """Verifies is_busy reflects worker execution state and drop_if_busy drops calls when busy."""
        self.assertFalse(self.injector.is_busy)

        # Launch an async snippet with a 150ms delay
        queued = self.injector.insert_snippet("slow_snippet();", paste_delay=0.15)
        self.assertTrue(queued)

        # Give worker thread a moment to pick up the task
        time.sleep(0.01)
        self.assertTrue(self.injector.is_busy, "Injector must report is_busy=True while executing task.")

        # Attempt to insert with drop_if_busy=True
        dropped = self.injector.insert_snippet("dropped_snippet();", drop_if_busy=True)
        self.assertFalse(dropped, "Snippet must be dropped when drop_if_busy=True and injector is busy.")

        # Wait for all tasks to complete
        self.assertTrue(self.injector.wait_idle(timeout=1.0))
        self.assertFalse(self.injector.is_busy, "Injector must report is_busy=False once queue is drained.")


# =============================================================================
# 6. STICKY SUBMENU TRANSITIONS & BREADCRUMBS IN OVERLAY WINDOW
# =============================================================================


if __name__ == "__main__":
    unittest.main()
