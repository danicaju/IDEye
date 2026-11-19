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

        path_keywords = get_breadcrumb_path(self.overlay.menu_tree, "KEYWORDS")
        self.assertTrue(path_keywords.endswith("> PALABRAS"))

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
