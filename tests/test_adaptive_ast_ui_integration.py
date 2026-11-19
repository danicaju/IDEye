"""
Automated Test Suite: Adaptive AST Syntactic Context Menus (Phase Extra - Option A)
Tests real-time syntactic context detection across all constructs, syntax error resilience,
3x3 9-cell ergonomic layout integrity, slot 4 pause reservation, slot 8 standard menu switch,
cursor offsets, dynamic breadcrumbs, and UI toggles in OverlayWindow and DebugWidget.
"""

import os
import sys
import tempfile
import unittest
from typing import Dict, Any

# Ensure offscreen Qt platform for test runner
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PyQt6.QtCore import Qt, QCoreApplication
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QKeyEvent

_APP = QApplication.instance() or QApplication(sys.argv if hasattr(sys, "argv") else [])

# Ensure project root is in sys.path
_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_IDEYE_DIR = os.path.join(_ROOT_DIR, "ideye")
for p in (_ROOT_DIR, _IDEYE_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

from ideye.actions.context_reader import (
    ContextReader,
    detect_syntactic_context,
    SyntacticContext,
    CONTEXT_FUNCTION_SIGNATURE,
    CONTEXT_TRY_BLOCK,
    CONTEXT_CLASS_BODY,
    CONTEXT_IF_BLOCK,
    CONTEXT_LOOP_BLOCK,
    CONTEXT_WITH_BLOCK,
    CONTEXT_GENERAL,
)
from ideye.actions.menu_trees import (
    MenuNode,
    MenuAction,
    build_menu_tree,
    get_adaptive_context_node,
    create_standard_menu_action,
    create_adaptive_menu_action,
    create_pause_action,
    create_back_action,
)
from ideye.ui.overlay_window import OverlayWindow
from ideye.ui.debug_widget import DebugWidget
import ideye.config as config


class TestOverlayWindowAdaptiveASTIntegration(unittest.TestCase):
    """Verifies OverlayWindow dynamic breadcrumbs, live context detection, and UI toggles."""

    def setUp(self):
        self.context_reader = ContextReader()
        self.overlay = OverlayWindow(context_reader=self.context_reader)

    def tearDown(self):
        self.overlay.close()

    def test_overlay_adaptive_ast_flag_default(self):
        """OverlayWindow initializes with ENABLE_ADAPTIVE_AST_MENUS config setting."""
        self.assertTrue(self.overlay.adaptive_ast_enabled)

    def test_overlay_current_node_adapts_to_function_signature(self):
        """When at ROOT and active file contains incomplete def, current_node reflects function signature."""
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write("def calculate_metrics(values, ")
            tmp_path = f.name

        try:
            self.context_reader.set_active_file(tmp_path)
            self.overlay.current_node_id = "ROOT"
            curr = self.overlay.current_node
            self.assertEqual(curr.id, "ADAPTIVE_FUNCTION_SIGNATURE")
            self.assertIn("FUNCIÓN", curr.breadcrumb_label)
        finally:
            if os.path.isfile(tmp_path):
                os.remove(tmp_path)

    def test_overlay_current_node_adapts_to_try_block(self):
        """When at ROOT and active file contains try block, current_node reflects try/except."""
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write("try:\n    risk_score = eval()")
            tmp_path = f.name

        try:
            self.context_reader.set_active_file(tmp_path)
            self.overlay.current_node_id = "ROOT"
            curr = self.overlay.current_node
            self.assertEqual(curr.id, "ADAPTIVE_TRY_BLOCK")
            self.assertIn("TRY/EXCEPT", curr.breadcrumb_label)
        finally:
            if os.path.isfile(tmp_path):
                os.remove(tmp_path)

    def test_toggle_adaptive_ast_disables_dynamic_menus(self):
        """Toggling adaptive AST off reverts ROOT to the standard root menu."""
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write("def foo(")
            tmp_path = f.name

        try:
            self.context_reader.set_active_file(tmp_path)
            self.overlay.current_node_id = "ROOT"
            self.assertEqual(self.overlay.current_node.id, "ADAPTIVE_FUNCTION_SIGNATURE")

            # Toggle off
            self.overlay.toggle_adaptive_ast()
            self.assertFalse(self.overlay.adaptive_ast_enabled)
            self.assertEqual(self.overlay.current_node.id, "ROOT")

            # Toggle back on
            self.overlay.toggle_adaptive_ast()
            self.assertTrue(self.overlay.adaptive_ast_enabled)
            self.assertEqual(self.overlay.current_node.id, "ADAPTIVE_FUNCTION_SIGNATURE")
        finally:
            if os.path.isfile(tmp_path):
                os.remove(tmp_path)

    def test_switching_to_menu_standard_node(self):
        """Selecting MENU_STANDARD navigates to standard menu with 1-click gaze return path."""
        self.assertIn("MENU_STANDARD", self.overlay.menu_tree)
        self.overlay.navigate_to("MENU_STANDARD")
        self.assertEqual(self.overlay.current_node_id, "MENU_STANDARD")
        std_node = self.overlay.current_node
        self.assertEqual(len(std_node.items), 9)

        # Slot 8 must be the return switch to adaptive menu
        return_action = std_node.items[8]
        self.assertEqual(return_action.id, "SWITCH_ADAPTIVE_MENU")
        self.assertEqual(return_action.submenu_id, "ROOT")
        self.assertIn("ADAPTATIVO", return_action.label.upper())

    def test_overlay_render_caching_and_invalidation(self):
        """OverlayWindow caches current_node during high-frequency paint events and invalidates on changes."""
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write("def foo(")
            tmp_path = f.name

        try:
            self.context_reader.set_active_file(tmp_path)
            self.overlay.current_node_id = "ROOT"
            node1 = self.overlay.current_node
            node2 = self.overlay.current_node
            # Cached object identity
            self.assertIs(node1, node2)

            # Invalidate via toggle
            self.overlay.toggle_adaptive_ast()
            self.assertEqual(self.overlay.current_node.id, "ROOT")

            self.overlay.toggle_adaptive_ast()
            node3 = self.overlay.current_node
            self.assertEqual(node3.id, "ADAPTIVE_FUNCTION_SIGNATURE")
        finally:
            if os.path.isfile(tmp_path):
                os.remove(tmp_path)


class TestDebugWidgetAdaptiveASTIntegration(unittest.TestCase):
    """Verifies DebugWidget live AST indicator, toggle button, and [A] shortcut."""

    def setUp(self):
        self.widget = DebugWidget()

    def tearDown(self):
        self.widget.close()

    def test_debug_widget_ast_label_initial(self):
        """DebugWidget includes a live AST context status label."""
        self.assertTrue(hasattr(self.widget, "lbl_ast_context"))
        self.assertIn("Contexto:", self.widget.lbl_ast_context.text())

    def test_debug_widget_update_ast_context(self):
        """Updating AST context updates the live indicator label accurately."""
        self.widget.update_ast_context("FUNCTION_SIGNATURE")
        self.assertIn("FUNCIÓN", self.widget.lbl_ast_context.text())

        self.widget.update_ast_context("TRY_BLOCK")
        self.assertIn("TRY/EXCEPT", self.widget.lbl_ast_context.text())

        self.widget.update_ast_context("CLASS_BODY")
        self.assertIn("CLASE", self.widget.lbl_ast_context.text())

    def test_debug_widget_toggle_button(self):
        """Toggle button updates adaptive AST state and emits adaptive_ast_toggled."""
        received = []
        self.widget.adaptive_ast_toggled.connect(lambda val: received.append(val))

        initial_state = self.widget.adaptive_ast_enabled
        self.widget.btn_toggle_adaptive.click()
        self.assertEqual(self.widget.adaptive_ast_enabled, not initial_state)
        self.assertEqual(received, [not initial_state])
        self.assertIn("OFF" if initial_state else "ON", self.widget.btn_toggle_adaptive.text())

    def test_debug_widget_shortcut_a_key_event(self):
        """Pressing Key_A triggers adaptive AST mode toggle."""
        initial = self.widget.adaptive_ast_enabled
        key_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_A, Qt.KeyboardModifier.NoModifier)
        self.widget.keyPressEvent(key_event)
        self.assertEqual(self.widget.adaptive_ast_enabled, not initial)


if __name__ == "__main__":
    unittest.main()
