"""Phase 12: semantic coding taxonomy, live context and mode trees."""

import unittest

from ideye.actions.ai_predictor import (
    generate_document_predictions,
    generate_heuristic_predictions,
)
from ideye.actions.context_reader import ContextReader, DocumentShadowBuffer
from ideye.actions.semantic_taxonomy import (
    CATEGORY_SPECS,
    build_debug_semantic_tree,
    build_navigation_dual_tree,
    build_semantic_coding_tree,
    build_terminal_semantic_tree,
)

LANGUAGES = ("python", "c", "java", "javascript", "sql", "gdscript", "lua")


def assert_nine(test, node):
    test.assertEqual(len(node.items), 9, node.id)
    test.assertEqual(node.items[4].action_type, "PAUSE", node.id)
    if node.id != "ROOT":
        test.assertEqual(node.items[6].action_type, "BACK", node.id)


class TestSemanticCodingTaxonomy(unittest.TestCase):
    def test_all_languages_have_eight_valid_category_submenus(self):
        for language in LANGUAGES:
            with self.subTest(language=language):
                tree = build_semantic_coding_tree(
                    language,
                    symbols=["usuarios", "total", "calcular_total"],
                )
                root = tree["ROOT"]
                assert_nine(self, root)
                self.assertEqual(len(CATEGORY_SPECS), 8)
                category_slots = (0, 1, 2, 3, 5, 6, 7, 8)
                for slot, (category_id, _title, _icon, _kind) in zip(category_slots, CATEGORY_SPECS):
                    item = root.items[slot]
                    self.assertEqual(item.action_type, "SUBMENU")
                    self.assertEqual(item.submenu_id, category_id)
                    self.assertIn(category_id, tree)
                    assert_nine(self, tree[category_id])

    def test_loops_and_conditions_fill_real_local_symbols(self):
        tree = build_semantic_coding_tree("python", symbols=["usuarios", "total"])
        loop_snippets = [item.snippet for item in tree["SEM_LOOP"].items if item.snippet]
        cond_snippets = [item.snippet for item in tree["SEM_COND"].items if item.snippet]
        self.assertTrue(any("usuarios" in snippet for snippet in loop_snippets))
        self.assertTrue(any("total" in snippet for snippet in cond_snippets))

    def test_ai_category_accepts_six_live_suggestions(self):
        suggestions = [f"live {index}" for index in range(6)]
        tree = build_semantic_coding_tree("python", ai_suggestions=suggestions)
        values = [item.snippet for item in tree["SEM_AI"].items if item.snippet]
        self.assertEqual(values, suggestions)

    def test_other_mode_trees_are_valid(self):
        terminal = build_terminal_semantic_tree(
            {"branch": "feature/demo", "status": [" M file.py"], "project_type": "python"}
        )
        assert_nine(self, terminal["ROOT"])
        for node in terminal.values():
            assert_nine(self, node)

        for document_mode in (False, True):
            nav = build_navigation_dual_tree(document_mode=document_mode)
            assert_nine(self, nav["ROOT"])
            for node in nav.values():
                assert_nine(self, node)

        debug = build_debug_semantic_tree(["usuarios", "total"])
        assert_nine(self, debug["ROOT"])
        for node in debug.values():
            assert_nine(self, node)


class TestLiveContext(unittest.TestCase):
    def test_document_shadow_buffer_detects_google_docs_and_keeps_text(self):
        reader = ContextReader(auto_detect=False)
        self.assertTrue(reader.set_document_context("Documentos de Google - Informe", "chrome.exe"))
        self.assertTrue(reader.document_context_active)
        reader.record_document_text("Primer párrafo con acentos: acción, diseño y señal. ")
        reader.record_document_text("Segundo párrafo.")
        ctx = reader.get_document_context()
        self.assertTrue(ctx["active"])
        self.assertIn("acción", ctx["text"])
        self.assertIn("Segundo", ctx["text"])

    def test_document_window_detection(self):
        self.assertTrue(DocumentShadowBuffer.is_document_window("Google Docs - Draft", "chrome.exe"))
        self.assertTrue(DocumentShadowBuffer.is_document_window("Notion - Notes", "notion.exe"))
        self.assertTrue(DocumentShadowBuffer.is_document_window("Overleaf - Project", "chrome.exe"))
        self.assertTrue(DocumentShadowBuffer.is_document_window("Documento1 - Word", "winword.exe"))
        self.assertFalse(DocumentShadowBuffer.is_document_window("Visual Studio Code", "code.exe"))

    def test_editor_snapshot_keeps_prefix_suffix_and_symbols(self):
        reader = ContextReader(auto_detect=False)
        reader.update_editor_snapshot(
            {
                "filePath": "demo.py",
                "prefix_lines": ["def demo():"],
                "current_line": "    return total",
                "suffix_lines": ["", "def next_fn():"],
                "active_selection": "total",
                "local_symbols": ["demo", "total"],
                "diagnostics": [{"line": 2, "message": "boom"}],
            }
        )
        ctx = reader.get_editor_context()
        self.assertEqual(ctx["prefix_lines"], ["def demo():"])
        self.assertEqual(ctx["current_line"], "    return total")
        self.assertEqual(ctx["suffix_lines"][0], "")
        self.assertEqual(ctx["local_symbols"], ["demo", "total"])
        self.assertEqual(ctx["active_selection"], "total")

    def test_document_and_code_predictions_are_six_and_coherent(self):
        doc = generate_document_predictions(
            "La inteligencia artificial permite automatizar tareas repetitivas.",
            "Informe técnico",
        )
        code = generate_heuristic_predictions(
            "def calcular_total(usuarios):\n    for usuario in usuarios:",
            ["usuarios", "total"],
        )
        self.assertEqual(len(doc), 6)
        self.assertEqual(len(code), 6)
        self.assertTrue(any("párrafo" in item.lower() or "conclusión" in item.lower() for item in doc))
        self.assertTrue(any("usuarios" in item for item in code))


if __name__ == "__main__":
    unittest.main()
