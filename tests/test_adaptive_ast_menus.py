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


class TestAdaptiveASTContextDetection(unittest.TestCase):
    """Rigorous validation of the dual AST + Regex context detection engine."""

    def test_syntactic_context_dict_compatibility(self):
        """SyntacticContext must behave as both a dict and an object with attributes."""
        ctx = SyntacticContext(
            context="FUNCTION_SIGNATURE",
            line="def foo(",
            indent=4,
            details={"arg": "x"},
        )
        self.assertTrue(isinstance(ctx, dict))
        self.assertEqual(ctx["context"], "FUNCTION_SIGNATURE")
        self.assertEqual(ctx.context, "FUNCTION_SIGNATURE")
        self.assertEqual(ctx["line"], "def foo(")
        self.assertEqual(ctx.line, "def foo(")
        self.assertEqual(ctx["indent"], 4)
        self.assertEqual(ctx.indent, 4)
        self.assertEqual(ctx.get("context"), "FUNCTION_SIGNATURE")
        self.assertIn("context", ctx)
        self.assertEqual(ctx.to_dict()["context"], "FUNCTION_SIGNATURE")

    def test_detect_function_signature_simple(self):
        """Detects incomplete function signature being written."""
        code = "def calculate_total("
        ctx = detect_syntactic_context(source_code=code)
        self.assertEqual(ctx.context, CONTEXT_FUNCTION_SIGNATURE)

    def test_detect_function_signature_async(self):
        """Detects async function signature with parameters."""
        code = "async def fetch_user_data(user_id: int, "
        ctx = detect_syntactic_context(source_code=code)
        self.assertEqual(ctx.context, CONTEXT_FUNCTION_SIGNATURE)

    def test_detect_function_signature_multiline(self):
        """Detects unclosed multiline function signature across lines."""
        code = "def process_transaction(\n    account_id: str,\n    amount: float,\n"
        ctx = detect_syntactic_context(source_code=code)
        self.assertEqual(ctx.context, CONTEXT_FUNCTION_SIGNATURE)

    def test_detect_completed_function_is_not_signature(self):
        """A completed function definition header is not an active signature."""
        code = "def foo():\n    return 42"
        ctx = detect_syntactic_context(source_code=code)
        self.assertNotEqual(ctx.context, CONTEXT_FUNCTION_SIGNATURE)

    def test_detect_try_block_direct(self):
        """Detects immediate try: statement."""
        code = "try:"
        ctx = detect_syntactic_context(source_code=code)
        self.assertEqual(ctx.context, CONTEXT_TRY_BLOCK)

    def test_detect_try_block_indented_body(self):
        """Detects execution inside a try: block."""
        code = "try:\n    result = compute_risk()"
        ctx = detect_syntactic_context(source_code=code)
        self.assertEqual(ctx.context, CONTEXT_TRY_BLOCK)

    def test_detect_try_block_except_handler(self):
        """Detects context inside or immediately at except handler."""
        code = "try:\n    x = 1\nexcept ValueError as e:\n    "
        ctx = detect_syntactic_context(source_code=code)
        self.assertEqual(ctx.context, CONTEXT_TRY_BLOCK)

    def test_detect_try_block_finally_handler(self):
        """Detects context at finally: statement."""
        code = "try:\n    x = 1\nfinally:\n    "
        ctx = detect_syntactic_context(source_code=code)
        self.assertEqual(ctx.context, CONTEXT_TRY_BLOCK)

    def test_detect_class_body_header(self):
        """Detects immediate class definition."""
        code = "class UserRepository:"
        ctx = detect_syntactic_context(source_code=code)
        self.assertEqual(ctx.context, CONTEXT_CLASS_BODY)

    def test_detect_class_body_inheritance(self):
        """Detects class definition with base classes."""
        code = "class DataStore(BaseStore, Serializable):"
        ctx = detect_syntactic_context(source_code=code)
        self.assertEqual(ctx.context, CONTEXT_CLASS_BODY)

    def test_detect_class_body_internal_scope(self):
        """Detects context within class body scope."""
        code = "class Service:\n    version: str = '1.0'\n    "
        ctx = detect_syntactic_context(source_code=code)
        self.assertEqual(ctx.context, CONTEXT_CLASS_BODY)

    def test_detect_if_block_typing(self):
        """Detects active if or elif condition being written."""
        ctx_if = detect_syntactic_context(source_code="if ")
        self.assertEqual(ctx_if.context, CONTEXT_IF_BLOCK)

        ctx_elif = detect_syntactic_context(source_code="elif index > 0")
        self.assertEqual(ctx_elif.context, CONTEXT_IF_BLOCK)

    def test_detect_if_block_indented_body(self):
        """Detects context inside an if body."""
        code = "if threshold >= 0.5:\n    activate_sensor()"
        ctx = detect_syntactic_context(source_code=code)
        self.assertEqual(ctx.context, CONTEXT_IF_BLOCK)

    def test_detect_loop_block_for(self):
        """Detects for loop construct."""
        ctx_for = detect_syntactic_context(source_code="for item in ")
        self.assertEqual(ctx_for.context, CONTEXT_LOOP_BLOCK)

        ctx_body = detect_syntactic_context(source_code="for item in items:\n    process(item)")
        self.assertEqual(ctx_body.context, CONTEXT_LOOP_BLOCK)

    def test_detect_loop_block_while(self):
        """Detects while loop construct."""
        ctx_while = detect_syntactic_context(source_code="while is_running:")
        self.assertEqual(ctx_while.context, CONTEXT_LOOP_BLOCK)

    def test_detect_with_block_typing(self):
        """Detects with statement construct."""
        ctx_with = detect_syntactic_context(source_code="with ")
        self.assertEqual(ctx_with.context, CONTEXT_WITH_BLOCK)

    def test_detect_with_block_indented_body(self):
        """Detects context inside with context manager."""
        code = "with open('config.json', 'r') as f:\n    raw = f.read()"
        ctx = detect_syntactic_context(source_code=code)
        self.assertEqual(ctx.context, CONTEXT_WITH_BLOCK)

    def test_detect_general_default(self):
        """Top-level expressions, imports, and empty files resolve to GENERAL."""
        self.assertEqual(detect_syntactic_context(source_code="").context, CONTEXT_GENERAL)
        self.assertEqual(detect_syntactic_context(source_code="   \n\n  ").context, CONTEXT_GENERAL)
        self.assertEqual(detect_syntactic_context(source_code="# Just a comment").context, CONTEXT_GENERAL)
        self.assertEqual(detect_syntactic_context(source_code="import os\nimport sys").context, CONTEXT_GENERAL)
        self.assertEqual(detect_syntactic_context(source_code="x = 10\ny = 20").context, CONTEXT_GENERAL)
        self.assertEqual(detect_syntactic_context(source_code='if __name__ == "__main__":').context, CONTEXT_GENERAL)
        self.assertEqual(detect_syntactic_context(source_code='if __name__ == "__main__":\n    unittest.main()').context, CONTEXT_GENERAL)

    def test_detect_syntax_error_resilience(self):
        """Guarantees crash-free execution against broken, invalid, or truncated code."""
        broken_samples = [
            "def ((( broken syntax",
            "x = [1, 2, (3 + ",
            "class :::: invalid",
            "try without colon",
            "''' unclosed multi-line docstring",
            "\"\"\" unterminated triple quote",
            "if (x >: None",
        ]
        for sample in broken_samples:
            ctx = detect_syntactic_context(source_code=sample)
            self.assertTrue(isinstance(ctx, dict))
            self.assertIn("context", ctx)
            self.assertIsInstance(ctx.context, str)

    def test_detect_missing_file_resilience(self):
        """Non-existent file paths return GENERAL with zero exceptions."""
        ctx = detect_syntactic_context(file_path="non_existent_file_987654321.py")
        self.assertEqual(ctx.context, CONTEXT_GENERAL)

    def test_context_reader_instance_method(self):
        """ContextReader instance method detect_syntactic_context functions accurately."""
        reader = ContextReader()
        ctx = reader.detect_syntactic_context(source_code="def execute_task(")
        self.assertEqual(ctx.context, CONTEXT_FUNCTION_SIGNATURE)

    def test_detect_function_body_with_unclosed_parens_is_not_signature(self):
        """Unclosed parens inside function bodies must not falsely trigger FUNCTION_SIGNATURE."""
        # 1. Print call inside function body
        code1 = "def calculate(x):\n    print("
        self.assertEqual(detect_syntactic_context(source_code=code1).context, CONTEXT_GENERAL)

        # 2. For loop inside function body
        code2 = "def process():\n    for item in get_items("
        self.assertEqual(detect_syntactic_context(source_code=code2).context, CONTEXT_LOOP_BLOCK)

        # 3. If condition inside function body
        code3 = "def process():\n    if is_valid("
        self.assertEqual(detect_syntactic_context(source_code=code3).context, CONTEXT_IF_BLOCK)

        # 4. With statement inside function body
        code4 = "def process():\n    with open("
        self.assertEqual(detect_syntactic_context(source_code=code4).context, CONTEXT_WITH_BLOCK)

    def test_detect_top_level_expressions_with_parens_after_function(self):
        """Top level expressions with unclosed parens following functions resolve cleanly."""
        code1 = "def foo(a, b):\n    pass\n\nx = (1 + 2"
        self.assertEqual(detect_syntactic_context(source_code=code1).context, CONTEXT_GENERAL)

        code2 = "def foo(a, b):\n    pass\n\ndata = [\n    (1, 2),\n    (3,"
        self.assertEqual(detect_syntactic_context(source_code=code2).context, CONTEXT_GENERAL)

    def test_detect_try_block_with_inline_comments(self):
        """Try blocks with inline comments are correctly recognized by stack analyzer."""
        code = "try:  # attempt operation\n    do_work()"
        self.assertEqual(detect_syntactic_context(source_code=code).context, CONTEXT_TRY_BLOCK)

    def test_detect_try_block_without_colon(self):
        """Active typing of 'try' or 'except' without colon detects TRY_BLOCK."""
        self.assertEqual(detect_syntactic_context(source_code="try").context, CONTEXT_TRY_BLOCK)
        self.assertEqual(detect_syntactic_context(source_code="except").context, CONTEXT_TRY_BLOCK)

    def test_detect_deeply_nested_constructs(self):
        """Deeply nested constructs inside functions within context managers resolve to innermost block."""
        code = (
            "with open('data.txt', 'r') as f:\n"
            "    try:\n"
            "        async def stream_records(path: str):\n"
            "            for line in f:\n"
            "                if 'error' in line:\n"
            "                    yield ("
        )
        self.assertEqual(detect_syntactic_context(source_code=code).context, CONTEXT_IF_BLOCK)


class TestAdaptiveMenuNodeIntegrity(unittest.TestCase):
    """Verifies that adaptive menu nodes satisfy all Golden Rules of Gaze Ergonomics."""

    def setUp(self):
        self.tree = build_menu_tree()
        self.root = self.tree["ROOT"]

    def test_all_contexts_have_exactly_nine_items(self):
        """Golden Rule 1: Every adaptive context menu node has exactly 9 items (indices 0..8)."""
        contexts = [
            CONTEXT_FUNCTION_SIGNATURE,
            CONTEXT_TRY_BLOCK,
            CONTEXT_CLASS_BODY,
            CONTEXT_IF_BLOCK,
            CONTEXT_LOOP_BLOCK,
            CONTEXT_WITH_BLOCK,
        ]
        for ctx in contexts:
            node = get_adaptive_context_node(ctx, self.root)
            self.assertEqual(
                len(node.items),
                9,
                f"Adaptive node for '{ctx}' has {len(node.items)} items instead of 9.",
            )

    def test_all_contexts_have_pause_at_center_slot_four(self):
        """Golden Rule 2: Index 4 is strictly reserved for PAUSE across all adaptive menus."""
        contexts = [
            CONTEXT_FUNCTION_SIGNATURE,
            CONTEXT_TRY_BLOCK,
            CONTEXT_CLASS_BODY,
            CONTEXT_IF_BLOCK,
            CONTEXT_LOOP_BLOCK,
            CONTEXT_WITH_BLOCK,
        ]
        for ctx in contexts:
            node = get_adaptive_context_node(ctx, self.root)
            pause_item = node.items[4]
            self.assertEqual(pause_item.action_type, "PAUSE")
            self.assertIn("PAUSA", pause_item.label.upper())

    def test_designated_slot_switches_to_standard_menu(self):
        """Designated slot (Index 8) provides one-click switching to MENU_STANDARD."""
        contexts = [
            CONTEXT_FUNCTION_SIGNATURE,
            CONTEXT_TRY_BLOCK,
            CONTEXT_CLASS_BODY,
            CONTEXT_IF_BLOCK,
            CONTEXT_LOOP_BLOCK,
            CONTEXT_WITH_BLOCK,
        ]
        for ctx in contexts:
            node = get_adaptive_context_node(ctx, self.root, switch_slot=8)
            switch_item = node.items[8]
            self.assertEqual(switch_item.action_type, "SUBMENU")
            self.assertEqual(switch_item.submenu_id, "MENU_STANDARD")
            self.assertIn("ESTÁNDAR", switch_item.label.upper())

    def test_alternative_switch_slot_six_support(self):
        """Supports configuring slot 6 as the standard menu switch target."""
        node = get_adaptive_context_node(CONTEXT_TRY_BLOCK, self.root, switch_slot=6)
        self.assertEqual(node.items[6].submenu_id, "MENU_STANDARD")
        self.assertEqual(len(node.items), 9)
        self.assertEqual(node.items[4].action_type, "PAUSE")

    def test_alternative_switch_slot_six_key_numbering(self):
        """Alternative switch slot 6 produces strictly consecutive 1..9 numpad key prefixes."""
        node = get_adaptive_context_node(CONTEXT_TRY_BLOCK, self.root, switch_slot=6)
        expected_keys = [f"{i}:" for i in range(1, 10)]
        actual_keys = [it.label.split()[0] for it in node.items]
        self.assertEqual(actual_keys, expected_keys)
        self.assertEqual(node.items[6].submenu_id, "MENU_STANDARD")

    def test_general_context_returns_standard_root(self):
        """GENERAL context safely returns the standard root menu unchanged."""
        node = get_adaptive_context_node(CONTEXT_GENERAL, self.root)
        self.assertEqual(node.id, "ROOT")
        self.assertEqual(node.title, "RAÍZ")

    def test_precise_cursor_offsets_in_snippets(self):
        """Validates that snippets specify exact cursor offsets to center within quotes/parens."""
        with_node = get_adaptive_context_node(CONTEXT_WITH_BLOCK, self.root)
        open_action = next((it for it in with_node.items if "open" in (it.snippet or "")), None)
        self.assertIsNotNone(open_action)
        self.assertEqual(open_action.cursor_offset_left, 14)

        if_node = get_adaptive_context_node(CONTEXT_IF_BLOCK, self.root)
        elif_action = next((it for it in if_node.items if "elif" in (it.snippet or "")), None)
        self.assertIsNotNone(elif_action)
        self.assertEqual(elif_action.cursor_offset_left, 1)

        loop_node = get_adaptive_context_node(CONTEXT_LOOP_BLOCK, self.root)
        enum_action = next((it for it in loop_node.items if "enumerate" in (it.snippet or "")), None)
        self.assertIsNotNone(enum_action)
        self.assertEqual(enum_action.cursor_offset_left, 1)

        range_action = next((it for it in loop_node.items if "range" in (it.snippet or "")), None)
        self.assertIsNotNone(range_action)
        self.assertEqual(range_action.cursor_offset_left, 1)

    def test_zero_emojis_in_adaptive_labels(self):
        """Adheres to the zero-emoji professional UI guideline."""
        contexts = [
            CONTEXT_FUNCTION_SIGNATURE,
            CONTEXT_TRY_BLOCK,
            CONTEXT_CLASS_BODY,
            CONTEXT_IF_BLOCK,
            CONTEXT_LOOP_BLOCK,
            CONTEXT_WITH_BLOCK,
        ]
        for ctx in contexts:
            node = get_adaptive_context_node(ctx, self.root)
            for item in node.items:
                for ch in item.label:
                    self.assertLess(
                        ord(ch),
                        0x1F000,
                        f"Found emoji in item label: '{item.label}' for context '{ctx}'",
                    )


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
