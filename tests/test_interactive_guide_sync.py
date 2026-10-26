"""Regression tests for the Nintendo Booklet guide and UTF-8 sync."""

import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from eyede.core.guide_builder import build_interactive_guide_html
from eyede.core.guide_catalog import build_catalog, generate_interactive_guide

_APP = QApplication.instance() or QApplication(sys.argv if hasattr(sys, "argv") else [])


class TestInteractiveGuideSync(unittest.TestCase):
    def test_utf8_text_is_clean(self):
        text = build_interactive_guide_html(build_catalog())
        self.assertNotIn("autom?ticos", text)
        self.assertIn("autom\u00e1ticos", text)
        self.assertNotIn("\ufffd", text)
        self.assertTrue(text.startswith("<!DOCTYPE html>"))
        self.assertIn('<meta charset="UTF-8">', text)

    def test_nintendo_booklet_is_default_and_toggle_exists(self):
        text = build_interactive_guide_html(build_catalog())
        self.assertIn('<body data-theme="nintendo-booklet">', text)
        self.assertIn('id="themeToggle"', text)
        self.assertIn("toggleTheme()", text)
        self.assertIn("Cyber-Glass", text)
        self.assertIn("brush-title", text)
        self.assertIn("illustration", text)
        self.assertIn("page-numbers", text)
        self.assertIn("sticker", text)
        self.assertIn("body[data-theme=\"nintendo-booklet\"]", text)
        self.assertIn("@media print", text)

    def test_all_booklet_cards_survive_regeneration(self):
        catalog = build_catalog()
        titles = [card["title"] for page in catalog["pages"] for card in page["cards"]]
        for required in (
            "Mira para mover",
            "Calibraci\u00f3n 5 + 1",
            "Abre la boca para confirmar",
            "Scroll sin manos",
            "Head-Joystick",
            "Editor de Macros",
            "M\u00e1quina del Tiempo",
        ):
            self.assertIn(required, titles)
        self.assertEqual(len(catalog["pages"]), 5)

    def test_generator_writes_utf8_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "guia.html"
            result = generate_interactive_guide(target)
            raw = target.read_bytes()
            self.assertTrue(raw.startswith(b"<!DOCTYPE html>"))
            decoded = raw.decode("utf-8")
            self.assertIn("autom\u00e1ticos", decoded)
            self.assertNotIn("autom?ticos", decoded)
            self.assertEqual(result, target)


if __name__ == "__main__":
    unittest.main()
