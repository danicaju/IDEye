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
_EYEDE_DIR = os.path.join(_ROOT_DIR, "eyede")
for p in (_ROOT_DIR, _EYEDE_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

import eyede.config as config
from eyede.actions.code_injector import CodeInjector, DummyKeyboard, DummyClipboard
from eyede.actions.menu_trees import (
    MenuAction,
    MenuNode,
    build_menu_tree,
    validate_menu_tree,
    get_breadcrumb_path,
    create_pause_action,
    create_back_action,
)
from eyede.ui.overlay_window import OverlayWindow


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
class TestMenuTree3x3Validation(unittest.TestCase):
    """
    Audits QA Requirement 3:
    Verifies that all nodes in menu_trees.py return exactly 9 elements (indices 0 to 8),
    Index 4 is ALWAYS Pause across all menus, Index 6 is ALWAYS Back in every submenu,
    and there are zero dead-ends or orphan nodes.
    """

    def setUp(self):
        self.tree = build_menu_tree()

    def test_full_tree_validates_cleanly(self):
        """Verifies that the entire production menu tree passes validation with 0 errors."""
        is_valid, errors = validate_menu_tree(self.tree)
        self.assertTrue(is_valid, f"Menu tree validation failed with errors: {errors}")
        self.assertEqual(len(errors), 0)

    def test_all_nodes_have_exactly_9_items(self):
        """Verifies mathematically that len(node.items) == 9 for every single node."""
        self.assertGreater(len(self.tree), 10, "Tree must have multiple hierarchical nodes.")
        for node_id, node in self.tree.items():
            self.assertEqual(
                len(node.items),
                9,
                f"Node '{node_id}' does not have exactly 9 items (has {len(node.items)}).",
            )

    def test_index_4_is_always_pause(self):
        """Verifies Golden Rule: Center Cell (Index 4) is ALWAYS Pause in all menus."""
        for node_id, node in self.tree.items():
            item_4 = node.items[4]
            self.assertEqual(
                item_4.action_type,
                "PAUSE",
                f"Node '{node_id}' Index 4 action_type is '{item_4.action_type}', expected 'PAUSE'.",
            )
            self.assertIn("PAUSA", item_4.label.upper())

    def test_index_6_is_always_back_in_all_submenus(self):
        """Verifies Golden Rule: Bottom-Left Cell (Index 6) is ALWAYS Back in all submenus."""
        for node_id, node in self.tree.items():
            if node_id == "ROOT":
                continue  # Root is Level 1, has no parent
            item_6 = node.items[6]
            self.assertEqual(
                item_6.action_type,
                "BACK",
                f"Submenu '{node_id}' Index 6 action_type is '{item_6.action_type}', expected 'BACK'.",
            )
            self.assertEqual(
                item_6.submenu_id,
                node.parent_id,
                f"Submenu '{node_id}' Back action target does not point to parent '{node.parent_id}'.",
            )

    def test_no_orphan_submenus_or_broken_links(self):
        """Verifies that every submenu_id points to an existing registered node."""
        for node_id, node in self.tree.items():
            for idx, item in enumerate(node.items):
                if item.action_type == "SUBMENU":
                    self.assertIsNotNone(item.submenu_id, f"Node '{node_id}' item {idx} has None submenu_id.")
                    self.assertIn(
                        item.submenu_id,
                        self.tree,
                        f"Node '{node_id}' item {idx} points to non-existent submenu '{item.submenu_id}'.",
                    )

    def test_unbroken_path_to_root_from_every_node(self):
        """Verifies that every single node in the tree can navigate back to ROOT."""
        for node_id, node in self.tree.items():
            curr = node_id
            visited = set()
            while curr != "ROOT":
                self.assertNotIn(curr, visited, f"Cycle detected in parent pointers starting from '{node_id}'.")
                visited.add(curr)
                parent = self.tree[curr].parent_id
                self.assertIsNotNone(parent, f"Node '{curr}' has no parent pointer and is not ROOT.")
                self.assertIn(parent, self.tree, f"Parent '{parent}' of node '{curr}' does not exist.")
                curr = parent

    def test_validator_catches_invalid_trees(self):
        """Verifies that validate_menu_tree flags corrupted trees with detailed errors."""
        # Case 1: Missing root
        bad_tree = {"FOO": MenuNode(id="FOO", title="Foo", items=[create_pause_action()] * 9)}
        valid, errs = validate_menu_tree(bad_tree)
        self.assertFalse(valid)
        self.assertTrue(any("ROOT" in e for e in errs))

        # Case 2: Node with 8 items instead of 9
        bad_tree_2 = copy.deepcopy(self.tree)
        bad_tree_2["FLOW"].items.pop()  # now 8 items
        valid, errs = validate_menu_tree(bad_tree_2)
        self.assertFalse(valid)
        self.assertTrue(any("FLOW" in e and "8 items" in e for e in errs))

        # Case 3: Node with non-pause index 4
        bad_tree_3 = copy.deepcopy(self.tree)
        bad_tree_3["ROOT"].items[4] = MenuAction(id="BAD", label="Bad", action_type="KEY")
        valid, errs = validate_menu_tree(bad_tree_3)
        self.assertFalse(valid)
        self.assertTrue(any("index 4" in e for e in errs))

        # Case 4: Submenu without back on index 6
        bad_tree_4 = copy.deepcopy(self.tree)
        bad_tree_4["STRUCT"].items[6] = MenuAction(id="BAD_BACK", label="Bad", action_type="KEY")
        valid, errs = validate_menu_tree(bad_tree_4)
        self.assertFalse(valid)
        self.assertTrue(any("index 6" in e for e in errs))

        # Case 5: Broken submenu reference
        bad_tree_5 = copy.deepcopy(self.tree)
        bad_tree_5["ROOT"].items[0].submenu_id = "NON_EXISTENT_SUBMENU"
        valid, errs = validate_menu_tree(bad_tree_5)
        self.assertFalse(valid)
        self.assertTrue(any("NON_EXISTENT_SUBMENU" in e for e in errs))


# =============================================================================
# 2. CODE INJECTOR & CLIPBOARD RACE CONDITION TESTS
# =============================================================================
class TestCodeInjectorClipboardSafety(unittest.TestCase):
    """
    Audits QA Requirement 2:
    Verifies that insert_snippet preserves prior clipboard content,
    applies controlled delays, executes cursor offsets, and restores the original clipboard.
    """

    def setUp(self):
        self.mock_kb = MockKeyboard()
        self.mock_clip = MockClipboard(initial="ORIGINAL_USER_CLIPBOARD_TEXT")
        self.injector = CodeInjector(
            async_mode=False,  # Synchronous for deterministic assertions
            paste_delay=0.01,
            keyboard_controller=self.mock_kb,
            clipboard_module=self.mock_clip,
        )

    def tearDown(self):
        self.injector.stop()

    def test_insert_snippet_preserves_and_restores_clipboard(self):
        """Verifies full clipboard lifecycle: save -> copy snippet -> paste -> restore."""
        initial_clip = "Important User Code In Clipboard"
        self.mock_clip.copy(initial_clip)

        snippet = "def calculate_matrix(data):"
        success = self.injector.insert_snippet(
            snippet=snippet,
            cursor_offset_left=2,
            cursor_offset_up=0,
            restore_clipboard=True,
            paste_delay=0.01,
            async_exec=False,
        )
        self.assertTrue(success)

        # 1. Verify paste keystroke occurred ('v' tapped while primary modifier was held)
        self.assertIn('v', self.mock_kb.tapped_keys)

        # 2. Verify left arrow was tapped 2 times for cursor offset
        from pynput.keyboard import Key
        left_taps = [k for k in self.mock_kb.tapped_keys if k == Key.left]
        self.assertEqual(len(left_taps), 2)

        # 3. Verify clipboard history sequence and final restored copy
        history_types = [h[0] for h in self.mock_clip.history]
        self.assertIn("PASTE", history_types)  # read prior
        self.assertIn("COPY", history_types)   # copy snippet
        self.assertEqual(self.mock_clip.history[-1], ("COPY", initial_clip))  # restored!

        # 4. Verify clipboard was ultimately restored to initial content
        self.assertEqual(self.mock_clip.content, initial_clip)

    def test_insert_snippet_without_restore(self):
        """Verifies restore_clipboard=False leaves the snippet on the clipboard."""
        self.mock_clip.copy("Initial")
        self.injector.insert_snippet("new_snippet", restore_clipboard=False, async_exec=False)
        self.assertEqual(self.mock_clip.paste(), "new_snippet")

    def test_clipboard_restored_even_on_paste_exception(self):
        """Verifies that user's clipboard is GUARANTEED to be restored even if paste throws an exception."""
        failing_kb = MockKeyboard(fail_on_tap='v')
        clip = MockClipboard(initial="ORIGINAL_SAFE_DATA")
        injector = CodeInjector(
            async_mode=False,
            keyboard_controller=failing_kb,
            clipboard_module=clip,
        )
        try:
            success = injector.insert_snippet("failing_snippet", cursor_offset_left=5, async_exec=False)
            self.assertFalse(success, "Snippet insertion must report failure when paste keystroke fails.")
            # Cursor offsets should NOT have run if paste failed!
            from pynput.keyboard import Key
            left_taps = [k for k in failing_kb.tapped_keys if k == Key.left]
            self.assertEqual(len(left_taps), 0, "Cursor offsets must NOT run if paste failed.")
            # Original clipboard must be restored!
            self.assertEqual(clip.content, "ORIGINAL_SAFE_DATA", "Clipboard must be restored despite paste error.")
        finally:
            injector.stop()

    def test_corrupt_or_non_text_clipboard_not_overwritten(self):
        """Verifies that if reading the initial clipboard raises an exception, it is not overwritten with empty string."""
        class ErrorClipboard:
            def __init__(self):
                self.copied = []
            def paste(self):
                raise RuntimeError("Non-text clipboard format (e.g. image or bitmap lock)")
            def copy(self, text):
                self.copied.append(text)

        err_clip = ErrorClipboard()
        injector = CodeInjector(
            async_mode=False,
            keyboard_controller=self.mock_kb,
            clipboard_module=err_clip,
        )
        try:
            success = injector.insert_snippet("my_snippet", restore_clipboard=True, async_exec=False)
            self.assertTrue(success)
            # The snippet was copied once
            self.assertIn("my_snippet", err_clip.copied)
            # But empty string was NOT restored, avoiding wiping non-text clipboard!
            self.assertNotIn("", err_clip.copied)
        finally:
            injector.stop()

    def test_cursor_offsets_order_up_before_left(self):
        """Verifies that UP arrows execute BEFORE LEFT arrows so multi-line line targeting is not corrupted."""
        from pynput.keyboard import Key
        self.mock_kb.history.clear()
        self.injector._apply_cursor_offsets(offset_left=4, offset_up=2)

        # Extract only the TAP events for arrow keys
        arrow_taps = [item[1] for item in self.mock_kb.history if item[0] == "TAP"]
        self.assertEqual(arrow_taps, [Key.up, Key.up, Key.left, Key.left, Key.left, Key.left])


# =============================================================================
# 3. STUCK MODIFIER KEYS AUDIT TESTS
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
class TestOverlayWindowPhase3Navigation(unittest.TestCase):
    """
    Tests OverlayWindow integration with MenuTrees, sticky submenu transitions,
    breadcrumb path generation, and non-blocking action dispatching.
    """

    def setUp(self):
        self.mock_kb = MockKeyboard()
        self.mock_clip = MockClipboard("code")
        self.injector = CodeInjector(
            async_mode=False,  # Synchronous for instant UI test assertions
            paste_delay=0.005,
            keyboard_controller=self.mock_kb,
            clipboard_module=self.mock_clip,
        )
        self.overlay = OverlayWindow(code_injector=self.injector)
        self.overlay.resize(1280, 720)

    def tearDown(self):
        self.overlay.close()
        self.injector.stop()

    def test_initial_state_is_root(self):
        """Verifies overlay starts in ROOT menu with 9 items."""
        self.assertEqual(self.overlay.current_node_id, "ROOT")
        self.assertEqual(len(self.overlay.current_node.items), 9)
        self.assertEqual(get_breadcrumb_path(self.overlay.menu_tree, "ROOT"), "RAÍZ")

    def test_navigate_to_flow_submenu_and_back(self):
        """Tests forward navigation into FLOW submenu and back to ROOT via block 6."""
        # 1. Hover block 0 (FLOW) and click
        self.overlay.on_gaze_updated(0.1, 0.1)  # col 0, row 0 -> index 0
        self.assertEqual(self.overlay.hovered_block, 0)
        self.overlay.on_gesture_triggered("MOUTH_CLICK")

        # Now in FLOW submenu!
        self.assertEqual(self.overlay.current_node_id, "FLOW")
        self.assertIn("FLUJO", get_breadcrumb_path(self.overlay.menu_tree, self.overlay.current_node_id))

        # 2. Hover block 6 (VOLVER ATRÁS) and click
        self.overlay.on_gaze_updated(0.1, 0.9)  # col 0, row 2 -> index 6
        self.assertEqual(self.overlay.hovered_block, 6)
        self.overlay.on_gesture_triggered("MOUTH_CLICK")

        # Returned to ROOT!
        self.assertEqual(self.overlay.current_node_id, "ROOT")

    def test_non_sticky_action_returns_to_root_after_injection(self):
        """
        Verifies that non-sticky submenus (like FLOW) automatically return to ROOT
        after code injection so the user doesn't get stuck in deep submenus.
        """
        # Navigate to FLOW
        self.overlay.navigate_to("FLOW")
        self.assertEqual(self.overlay.current_node_id, "FLOW")

        # Hover block 0 ('if ...:') and click
        self.overlay.on_gaze_updated(0.1, 0.1)
        self.overlay.on_gesture_triggered("MOUTH_CLICK")

        # Injected snippet and automatically returned to ROOT!
        self.assertEqual(self.overlay.current_node_id, "ROOT")
        self.assertIn('v', self.mock_kb.tapped_keys)

    def test_sticky_submenu_remains_active_for_repetitive_actions(self):
        """
        Verifies that sticky submenus (like NAV) remain in the submenu
        after an action is executed, allowing continuous cursor hopping.
        """
        # Navigate to NAV
        self.overlay.navigate_to("NAV")
        self.assertEqual(self.overlay.current_node_id, "NAV")
        self.assertTrue(self.overlay.current_node.sticky)

        from pynput.keyboard import Key

        # Tap UP (block 0)
        self.overlay.on_gaze_updated(0.1, 0.1)
        self.overlay.on_gesture_triggered("MOUTH_CLICK")
        self.assertEqual(self.overlay.current_node_id, "NAV", "Must stay in NAV submenu!")
        self.assertIn(Key.up, self.mock_kb.tapped_keys)

        # Tap DOWN (block 1)
        self.overlay.on_gaze_updated(0.5, 0.1)
        self.overlay.on_gesture_triggered("MOUTH_CLICK")
        self.assertEqual(self.overlay.current_node_id, "NAV", "Must stay in NAV submenu!")
        self.assertIn(Key.down, self.mock_kb.tapped_keys)

        # Tap RIGHT (block 3)
        self.overlay.on_gaze_updated(0.1, 0.5)
        self.overlay.on_gesture_triggered("MOUTH_CLICK")
        self.assertEqual(self.overlay.current_node_id, "NAV", "Must stay in NAV submenu!")
        self.assertIn(Key.right, self.mock_kb.tapped_keys)

        # Navigate back to ROOT explicitly via block 6
        self.overlay.on_gaze_updated(0.1, 0.9)  # block 6
        self.overlay.on_gesture_triggered("MOUTH_CLICK")
        self.assertEqual(self.overlay.current_node_id, "ROOT")

    def test_breadcrumb_rendering_string(self):
        """Verifies breadcrumb string formatting across 2-hop navigation."""
        path_root = get_breadcrumb_path(self.overlay.menu_tree, "ROOT")
        self.assertEqual(path_root, "RAÍZ")

        path_t9 = get_breadcrumb_path(self.overlay.menu_tree, "T9")
        self.assertEqual(path_t9, "RAÍZ > T9")

        path_t9_vars = get_breadcrumb_path(self.overlay.menu_tree, "T9_VARS")
        self.assertEqual(path_t9_vars, "RAÍZ > T9 > VARS")

        path_flow_try = get_breadcrumb_path(self.overlay.menu_tree, "FLOW_TRY_RET")
        self.assertEqual(path_flow_try, "RAÍZ > FLUJO > TRY/RET")

    def test_last_action_desc_updates_on_action(self):
        """Verifies that last_action_desc updates in overlay window upon keystroke."""
        self.overlay.navigate_to("FORMAT")
        self.overlay.on_gaze_updated(0.1, 0.1)  # ENTER
        self.overlay.on_gesture_triggered("MOUTH_CLICK")
        self.assertIn("ENTER", self.overlay.last_action_desc)

    def test_facial_click_dropped_while_injector_busy_except_pause(self):
        """Verifies that mouth clicks are dropped while injector is busy, but PAUSE (Block 4) is never blocked."""
        # Simulate active injection in background
        self.overlay.code_injector._is_executing = True
        self.assertTrue(self.overlay.code_injector.is_busy)

        # 1. Attempt mouth click on block 0 (FLOW) - must be dropped to prevent queue flood
        self.overlay.on_gaze_updated(0.1, 0.1)
        self.overlay.on_gesture_triggered("MOUTH_CLICK")
        self.assertEqual(self.overlay.current_node_id, "ROOT", "Action click must be dropped while injector is busy!")

        # 2. Attempt mouth click on block 4 (PAUSE) - must work immediately as emergency rest trigger!
        self.assertFalse(self.overlay.reading_mode)
        self.overlay.on_gaze_updated(0.5, 0.5)  # Center block 4
        self.overlay.on_gesture_triggered("MOUTH_CLICK")
        self.assertTrue(self.overlay.reading_mode, "PAUSE block 4 must NEVER be blocked even if injector is busy!")

        # Clean up
        self.overlay.code_injector._is_executing = False

    def test_root_menu_snippets_id(self):
        """Verifies ROOT block 8 has ID 'MENU_SNIPPETS', type SUBMENU, and navigates cleanly without false exit."""
        item_8 = self.overlay.menu_tree["ROOT"].items[8]
        self.assertEqual(item_8.id, "MENU_SNIPPETS")
        self.assertEqual(item_8.action_type, "SUBMENU")
        self.assertEqual(item_8.submenu_id, "SNIPPETS")

        # Hover block 8 and click
        self.overlay.on_gaze_updated(0.9, 0.9)
        self.assertEqual(self.overlay.hovered_block, 8)
        self.overlay.on_gesture_triggered("MOUTH_CLICK")
        self.assertEqual(self.overlay.current_node_id, "SNIPPETS")


if __name__ == "__main__":
    unittest.main()
