"""Writing/coding menus use complete words and phrases, never a letter keyboard."""

import os
import re
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from eyede.modes.writing_mode import WritingMode
from eyede.actions.menu_trees import build_menu_tree

_APP = QApplication.instance() or QApplication(sys.argv)


class TestNoLetterKeyboards(unittest.TestCase):
    def _assert_clean_tree(self, tree, root_name):
        single_letter = re.compile(r"^[A-Za-z??????????????]$")
        for node_id, node in tree.items():
            text = " ".join([node_id, node.title, node.breadcrumb_label or ""])
            self.assertNotIn("T9", text.upper(), f"{root_name}: T9 reference in {node_id}")
            self.assertNotIn("LETRAS:", node.title.upper(), f"{root_name}: letter group {node_id}")
            for item in node.items:
                self.assertNotIn("T9", f"{item.label} {item.hint}".upper())
                self.assertIsNone(
                    re.fullmatch(r"\d+:\s*[A-Za-z??????????????]", item.label or ""),
                    f"{root_name}: single-letter label {item.label!r} in {item.id}",
                )
                if item.action_type == "SNIPPET" and item.snippet:
                    snippet = str(item.snippet).strip()
                    self.assertFalse(
                        single_letter.fullmatch(snippet),
                        f"{root_name}: single-letter snippet {snippet!r} in {item.id}",
                    )

    def test_writing_tree_has_no_t9_or_single_letters(self):
        self._assert_clean_tree(WritingMode().get_menu_tree(), "writing")

    def test_coding_tree_has_no_t9_or_single_letters(self):
        self._assert_clean_tree(build_menu_tree("PYTHON"), "coding")

    def test_writing_has_word_and_phrase_blocks(self):
        tree = WritingMode().get_menu_tree()
        self.assertIn("WRITING_WORDS", tree)
        snippets = [item.snippet for item in tree["WRITING_WORDS"].items if item.snippet]
        self.assertIn("por favor", snippets)
        self.assertIn("muchas gracias", snippets)
        self.assertIn("Quedo atento a tus comentarios.", snippets)
        self.assertNotIn("WRITING_AE", tree)
        self.assertNotIn("WRITING_MORE", tree)


if __name__ == "__main__":
    unittest.main()
