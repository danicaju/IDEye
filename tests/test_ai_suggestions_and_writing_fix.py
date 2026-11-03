"""
Tests for AI suggestions diversity, condition heuristics, cursor placement,
if() replacement, and Writing mode AI assist (rephrase/correct).
"""

import os
import sys
import unittest

_ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_IDEYE_DIR = os.path.join(_ROOT_DIR, "ideye")
for p in (_ROOT_DIR, _IDEYE_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

from ideye.actions.ai_predictor import generate_heuristic_predictions
from ideye.actions.context_reader import ContextReader
from ideye.actions.menu_trees import build_menu_tree
from ideye.modes.writing_mode import WritingMode, correct_writing_text
from ideye.actions.code_injector import CodeInjector


class TestAISuggestionsAndWritingFix(unittest.TestCase):
    def test_heuristic_if_parens_returns_condition_expressions(self):
        """When the user has typed 'if ()', heuristics must suggest boolean conditions."""
        preds = generate_heuristic_predictions("if ()", ["ci_build", "data"])
        self.assertEqual(len(preds), 6)
        # Must contain smart conditions using the local symbol
        self.assertTrue(any("ci_build is not None" in p for p in preds))
        self.assertTrue(any("len(ci_build) > 0" in p or "not ci_build" in p for p in preds))
        # Must not suggest print(ci_build) when the user is writing an if() condition
        self.assertNotIn("print(ci_build)", preds)

    def test_heuristic_if_keyword_returns_condition_expressions(self):
        """When the user has typed 'if ' or 'if (', heuristics must suggest boolean conditions."""
        preds = generate_heuristic_predictions("if (", ["count", "total"])
        self.assertEqual(len(preds), 6)
        self.assertTrue(any("count is not None" in p for p in preds))
        self.assertTrue(any("count > 0" in p for p in preds))

    def test_heuristic_general_fallback_diversity(self):
        """Fallback heuristics must not repeat print(v1) across every suggestion."""
        preds = generate_heuristic_predictions("", ["ci_build"])
        self.assertEqual(len(preds), 6)
        # print(ci_build) must not be the only statement type
        self.assertTrue(any(p.startswith("if ") for p in preds))
        self.assertTrue(any(p.startswith("for ") for p in preds))

    def test_context_reader_live_editor_state(self):
        """ContextReader must prioritize live VS Code editor state over stale disk files."""
        reader = ContextReader()
        reader.update_editor_snapshot({
            "filePath": "dummy.py",
            "current_line": "if ()",
            "prefix_lines": ["x = 10", "y = 20"],
            "local_symbols": ["x", "y"],
        })
        self.assertEqual(reader.get_last_line(), "if ()")
        self.assertIn("x = 10", reader.get_recent_context())
        self.assertEqual(reader.extract_local_symbols(), ["x", "y"])

    def test_correct_writing_text_rules(self):
        """correct_writing_text fixes spacing, capitalization and inverted marks."""
        raw = "hola , como estas ?"
        corrected = correct_writing_text(raw)
        self.assertEqual(corrected, "¿Hola, como estas?")

        raw_excl = "genial !"
        corrected_excl = correct_writing_text(raw_excl)
        self.assertEqual(corrected_excl, "¡Genial!")

    def test_writing_mode_ai_actions_type(self):
        """Writing mode AI items must use action_type='WRITING_AI' instead of dummy snippets."""
        mode = WritingMode()
        tree = mode.get_menu_tree()
        ai_node = tree.get("WRITING_AI")
        self.assertIsNotNone(ai_node)

        rephrase_act = next((it for it in ai_node.items if it.id == "W_AI_3"), None)
        self.assertIsNotNone(rephrase_act)
        self.assertEqual(rephrase_act.action_type, "WRITING_AI")
        self.assertEqual(rephrase_act.snippet, "rephrase")

        correct_act = next((it for it in ai_node.items if it.id == "W_AI_6"), None)
        self.assertIsNotNone(correct_act)
        self.assertEqual(correct_act.action_type, "WRITING_AI")
        self.assertEqual(correct_act.snippet, "correct")

    def test_typescript_flow_if_cursor_inside_parens(self):
        """TS FLOW_IF snippet places cursor inside if () { parens."""
        tree = build_menu_tree("TYPESCRIPT")
        flow_node = tree.get("FLOW")
        self.assertIsNotNone(flow_node)
        if_action = next((it for it in flow_node.items if it.id == "FLOW_IF"), None)
        self.assertIsNotNone(if_action)
        self.assertEqual(if_action.cursor_offset_up, 2)
        self.assertEqual(if_action.cursor_offset_left, 3)


    def test_rephrase_writing_text(self):
        """rephrase_writing_text improves conversational phrases and applies punctuation correction."""
        from ideye.modes.writing_mode import rephrase_writing_text
        raw = "hola queria saber si podemos vernos mañana"
        rephrased = rephrase_writing_text(raw)
        self.assertIn("quisiera consultar si", rephrased)
        self.assertTrue(rephrased.startswith("Hola"))

    def test_delimiter_after_if_space_places_cursor_inside_parens(self):
        """When the line contains 'if ', inserting () must position caret inside: if (|)."""
        reader = ContextReader()
        reader.update_editor_snapshot({
            "current_line": "if ",
            "prefix_lines": ["x = 10"],
        })
        injector = CodeInjector()
        injector.set_context_reader(reader)
        offset = injector._effective_cursor_offset_left("()", 0, prefix_before="")
        self.assertEqual(offset, 1)

    def test_prepare_insert_if_suggestion_marks_inside_parens(self):
        """Selecting an if-suggestion when 'if ()' was typed marks inside_parens for clean erasure."""
        injector = CodeInjector()
        injector.set_last_statement_prefix("if ()")
        prepared, backspaces = injector.prepare_insert_text("if count > 0:")
        self.assertEqual(prepared, "if count > 0:")
        self.assertEqual(backspaces, len("if ()"))
        self.assertTrue(injector._last_statement_inside_parens)


if __name__ == "__main__":
    unittest.main()
