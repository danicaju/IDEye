"""Tests for the Writing mode letter keyboard and local word predictions."""

import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from ideye.actions.menu_trees import validate_menu_tree
from ideye.actions.text_predictor import predict_words
from ideye.modes.mode_manager import ModeManager
from ideye.modes.writing_mode import WritingMode
from ideye.ui.overlay_window import OverlayWindow

_APP = QApplication.instance() or QApplication(sys.argv if hasattr(sys, "argv") else [])


class TestWritingLetterKeyboard(unittest.TestCase):
    def test_tree_is_valid_and_covers_spanish_alphabet(self):
        mode = WritingMode()
        tree = mode.get_menu_tree()

        valid, errors = validate_menu_tree(tree)
        self.assertTrue(valid, errors)
        for node_id, node in tree.items():
            self.assertEqual(len(node.items), 9, node_id)

        letters = set()
        for node_id in (
            "WRITING_AE",
            "WRITING_FJ",
            "WRITING_KO",
            "WRITING_PT",
            "WRITING_UZ",
            "WRITING_MORE",
        ):
            for item in tree[node_id].items:
                if item.action_type == "WRITING_LETTER" and item.snippet:
                    letters.add(item.snippet)

        self.assertTrue(set("abcdefghijklmnopqrstuvwxyz").issubset(letters))
        self.assertTrue(set("áéíóúüñ").issubset(letters))

    def test_writing_keeps_word_and_phrase_blocks(self):
        tree = WritingMode().get_menu_tree()
        self.assertIn("WRITING_WORDS", tree)
        snippets = [item.snippet for item in tree["WRITING_WORDS"].items if item.snippet]
        self.assertIn("por favor", snippets)
        self.assertIn("muchas gracias", snippets)
        self.assertIn("Quedo atento a tus comentarios.", snippets)

    def test_predictor_matches_prefix_and_ignores_accents_for_matching(self):
        self.assertIn("casa", predict_words("ca"))
        self.assertEqual(predict_words("cancion")[0], "canción")
        self.assertEqual(len(predict_words("")), 6)
        self.assertTrue(all(word.startswith("n") for word in predict_words("n")))

    def test_predictions_shrink_as_prefix_grows(self):
        mode = WritingMode()
        first = mode.predictions()
        mode.record_letter("c")
        second = mode.predictions()
        mode.record_letter("a")
        third = mode.predictions()

        self.assertEqual(len(first), 6)
        self.assertTrue(all(word.startswith("c") for word in second))
        self.assertTrue(all(word.startswith("ca") for word in third))
        self.assertIn("casa", third)


class TestWritingLetterOverlayIntegration(unittest.TestCase):
    def setUp(self):
        self.manager = ModeManager(initial_mode="writing", auto_switch_enabled=False)
        self.overlay = OverlayWindow(
            mode_manager=self.manager,
            start_in_mode_selector=False,
        )
        self.manager.set_mode("writing", emit=True)
        self.overlay.navigate_to("WRITING_T9")
        self.inserted = []
        self.keys = []
        self.overlay.code_injector.insert_snippet = (
            lambda snippet, *args, **kwargs: self.inserted.append(snippet) or True
        )
        self.overlay.code_injector.send_key = (
            lambda key, *args, **kwargs: self.keys.append(key) or True
        )
        self.mode = self.manager.get_mode("writing")

    def tearDown(self):
        self.overlay.close()
        _APP.processEvents()

    def _letter(self, char):
        node = self.overlay.menu_tree["WRITING_AE"]
        item = next(i for i in node.items if i.snippet == char)
        self.overlay.execute_action(item)

    def test_letter_actions_insert_and_refresh_predictions(self):
        self._letter("c")
        self._letter("a")

        self.assertEqual(self.inserted, ["c", "a"])
        self.assertEqual(self.mode._prefix, "ca")
        labels = [item.label for item in self.overlay.menu_tree["WRITING_PREDICT"].items]
        self.assertIn("1: casa", labels)

    def test_selecting_prediction_inserts_word_and_space(self):
        self._letter("c")
        self._letter("a")
        prediction = self.overlay.menu_tree["WRITING_PREDICT"].items[0]
        self.overlay.execute_action(prediction)

        self.assertEqual(self.inserted[-1], "casa ")
        self.assertEqual(self.mode._prefix, "")
        self.assertEqual(self.overlay.current_node_id, "WRITING_T9")

    def test_uppercase_toggle_applies_to_letters_and_accents(self):
        more = self.overlay.menu_tree["WRITING_MORE"]
        case_action = next(i for i in more.items if i.action_type == "WRITING_CASE")
        self.overlay.execute_action(case_action)

        accent_action = next(
            i for i in more.items if i.action_type == "WRITING_LETTER" and i.snippet == "á"
        )
        self.overlay.execute_action(accent_action)
        self.assertEqual(self.inserted[-1], "Á")

    def test_phrase_selection_resets_letter_prefix(self):
        self._letter("c")
        self._letter("a")
        self.overlay.navigate_to("WRITING_WORDS")
        phrase = next(
            item for item in self.overlay.menu_tree["WRITING_WORDS"].items
            if item.action_type == "SNIPPET" and item.snippet
        )
        self.assertFalse(self.overlay._handle_writing_action(phrase))
        self.assertEqual(self.mode._prefix, "")

    def test_backspace_updates_prefix(self):
        self._letter("c")
        self._letter("a")
        back = self.overlay.menu_tree["WRITING_PREDICT"].items[8]
        self.overlay.execute_action(back)

        self.assertEqual(self.keys[-1], "BACKSPACE")
        self.assertEqual(self.mode._prefix, "c")


if __name__ == "__main__":
    unittest.main()
