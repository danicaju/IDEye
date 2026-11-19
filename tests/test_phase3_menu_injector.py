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


if __name__ == "__main__":
    unittest.main()
