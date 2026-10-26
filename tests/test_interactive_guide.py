"""Interactive Game Manual generation and integration tests."""

import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from eyede.core.guide_builder import build_interactive_guide_html
from eyede.core.guide_catalog import build_catalog, generate_interactive_guide
from eyede.ui.debug_widget import DebugWidget
from eyede.ui.overlay_window import OverlayWindow

_APP = QApplication.instance() or QApplication(sys.argv if hasattr(sys, "argv") else [])


class TestGuideCatalog(unittest.TestCase):
    def test_catalog_has_pages_modes_shortcuts_and_simulator(self):
        catalog = build_catalog()
        self.assertEqual(len(catalog["pages"]), 5)
        self.assertEqual(
            set(catalog["simulator"]),
            {"coding", "writing", "terminal", "sniper"},
        )
        self.assertEqual(len(catalog["modes"]), 6)
        self.assertTrue(catalog["gestures"])
        self.assertTrue(catalog["shortcuts"])
        self.assertEqual(len(catalog["legal"]), 3)
        for shortcut in catalog["shortcuts"]:
            self.assertRegex(shortcut["key"], r"^Ctrl\+Alt\+[A-Z]$")
        for mode_id, mode in catalog["simulator"].items():
            self.assertEqual(len(mode["cells"]), 9, mode_id)

    def test_html_is_self_contained_and_has_print_and_simulator(self):
        text = build_interactive_guide_html(build_catalog())
        self.assertNotIn("http://", text)
        self.assertNotIn("https://", text)
        self.assertEqual(text.count('<section class="page'), 5)
        self.assertIn("@media print", text)
        self.assertIn("size:A4 landscape", text)
        self.assertIn("SIMULADOR EN VIVO", text)
        self.assertIn('id="simGrid"', text)
        self.assertIn("window.print()", text)
        self.assertIn("Página 1", text)
        self.assertIn("Explorando IDEye", text)
        self.assertIn("Guiño", text)

    def test_generator_writes_a_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "guia.html"
            result = generate_interactive_guide(target)
            self.assertEqual(result, target)
            self.assertGreater(target.stat().st_size, 10000)
            self.assertIn("IDEye — Manual Interactivo", target.read_text(encoding="utf-8"))


class TestGuideEntryPoints(unittest.TestCase):
    def test_debug_widget_has_open_guide_button(self):
        widget = DebugWidget()
        emitted = []
        widget.open_guide_requested.connect(lambda: emitted.append(True))
        self.assertTrue(hasattr(widget, "btn_open_guide"))
        widget.btn_open_guide.click()
        self.assertEqual(emitted, [True])
        widget.close()

    def test_help_modal_has_interactive_guide_action(self):
        overlay = OverlayWindow()
        overlay.resize(1280, 720)
        overlay.show_help_modal = True
        overlay._update_help_modal_rect()
        self.assertTrue(overlay.help_modal_guide_rect.isValid())
        self.assertTrue(overlay.help_modal_rect.contains(overlay.help_modal_guide_rect))
        emitted = []
        overlay.interactive_guide_requested.connect(lambda: emitted.append(True))
        overlay.hovered_help_modal_guide = True
        overlay.on_gesture_triggered("MOUTH_CLICK")
        self.assertEqual(emitted, [True])
        self.assertFalse(overlay.show_help_modal)
        overlay.close()


if __name__ == "__main__":
    unittest.main()
