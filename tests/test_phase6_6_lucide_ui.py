"""Phase 6.6: Lucide SVG icons, High-DPI rendering, header and preview chips."""

import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QRectF
from PyQt6.QtGui import QColor, QImage, QPainter
from PyQt6.QtWidgets import QApplication

from eyede.ui.icon_manager import IconManager
from eyede.ui.overlay_window import OverlayWindow

_APP = QApplication.instance() or QApplication(sys.argv if hasattr(sys, "argv") else [])
_ICONS = Path(__file__).resolve().parent.parent / "eyede" / "assets" / "icons"

_SVG_FILES = (
    "function.svg",
    "format.svg",
    "terminal.svg",
    "database.svg",
    "pause_eye.svg",
    "navigation.svg",
    "arrow_left.svg",
    "help.svg",
    "exit.svg",
    "ai_spark.svg",
    "mode.svg",
    "flow.svg",
    "edit.svg",
    "language.svg",
    "operators.svg",
    "variables.svg",
)


class TestLucideSvgAssets(unittest.TestCase):
    def test_all_icons_use_lucide_header(self):
        for name in _SVG_FILES:
            with self.subTest(icon=name):
                text = (_ICONS / name).read_text(encoding="utf-8")
                self.assertIn('viewBox="0 0 24 24"', text)
                self.assertIn('fill="none"', text)
                self.assertIn('stroke="currentColor"', text)
                self.assertIn('stroke-width="2"', text)
                self.assertIn('stroke-linecap="round"', text)
                self.assertIn('stroke-linejoin="round"', text)

    def test_key_paths_match_lucide(self):
        expected = {
            "function.svg": '<polyline points="16 18 22 12 16 6"/>',
            "format.svg": "M14.5 2H6",
            "terminal.svg": '<polyline points="4 17 10 11 4 5"/>',
            "database.svg": '<ellipse cx="12" cy="5" rx="9" ry="3"/>',
            "navigation.svg": '<polyline points="5 9 2 12 5 15"/>',
            "arrow_left.svg": '<line x1="19" y1="12" x2="5" y2="12"/>',
            "help.svg": '<circle cx="12" cy="12" r="10"/>',
            "exit.svg": "M18.36 6.64a9 9 0 1 1-12.73 0",
            "ai_spark.svg": '<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>',
        }
        for name, fragment in expected.items():
            with self.subTest(icon=name):
                self.assertIn(fragment, (_ICONS / name).read_text(encoding="utf-8"))


class TestHighDpiIcons(unittest.TestCase):
    def test_get_pixmap_scales_by_device_pixel_ratio(self):
        pix = IconManager.get_pixmap("function", 20, 20, color=QColor("#FFFFFF"), dpr=2.0)
        self.assertEqual(pix.width(), 40)
        self.assertEqual(pix.height(), 40)
        self.assertAlmostEqual(pix.devicePixelRatioF(), 2.0, places=2)

    def test_current_color_is_replaced(self):
        svg = b'<svg stroke="currentColor"></svg>'
        out = IconManager._apply_current_color(svg, "#FF0000")
        self.assertNotIn(b"currentColor", out)
        self.assertIn(b"#FF0000", out)

    def test_render_cell_icon_draws_pixels(self):
        image = QImage(28, 28, QImage.Format.Format_ARGB32)
        image.fill(0)
        painter = QPainter(image)
        ok = IconManager.render_cell_icon(
            painter,
            "function",
            QRectF(0, 0, 28, 28),
            icon_size=20.0,
            color=QColor("#FFFFFF"),
            dpr=1.0,
        )
        painter.end()
        self.assertTrue(ok)
        self.assertTrue(any(image.pixelColor(x, y).alpha() for x in range(28) for y in range(28)))


class TestHeaderAndChips(unittest.TestCase):
    def setUp(self):
        self.overlay = OverlayWindow(start_in_mode_selector=True)

    def tearDown(self):
        self.overlay.close()
        _APP.processEvents()

    def _dock_debug(self, width=1280, height=720):
        self.overlay.resize(width, height)
        self.overlay.show()
        _APP.processEvents()
        self.overlay._update_header_exit_rect()
        _APP.processEvents()

    def test_header_fits_without_overlap_at_1280(self):
        self._dock_debug(1280, 720)
        self.assertLessEqual(self.overlay.header_mode_rect.right(), self.overlay.header_lang_rect.left())
        self.assertLessEqual(self.overlay.header_lang_rect.right(), self.overlay.header_help_rect.left())
        self.assertLessEqual(self.overlay.header_help_rect.right(), self.overlay.header_exit_rect.left())
        self.assertLessEqual(self.overlay.header_exit_rect.right(), self.overlay.header_rect.right())

    def test_last_action_is_conditional(self):
        self._dock_debug()
        self.overlay.last_action_desc = "Elegir modo"
        self.assertFalse(self.overlay._should_show_last_action())
        self.overlay.last_action_desc = "git status"
        self.assertTrue(self.overlay._should_show_last_action())

    def test_mode_switch_preview_chips(self):
        mode_node = self.overlay.menu_tree["MODE_SELECT"]
        coding = next(item for item in mode_node.items if item.action_type == "MODE_SWITCH")
        labels = self.overlay._preview_chip_labels(coding)
        self.assertGreaterEqual(len(labels), 3)
        self.assertLessEqual(len(labels), 4)
        self.assertEqual(len(labels), len(set(labels)))

    def test_submenu_preview_chips(self):
        help_item = next(
            item
            for item in self.overlay.menu_tree["MODE_SELECT"].items
            if item.action_type == "SUBMENU"
        )
        labels = self.overlay._preview_chip_labels(help_item)
        self.assertGreaterEqual(len(labels), 1)

    def test_inactive_band_and_text_colors(self):
        self.assertEqual(self.overlay._brush_band_inactive.color().alpha(), 230)
        self.assertEqual(self.overlay._color_card_text_inactive.name(), "#e2e8f0")
        self.assertEqual(self.overlay._color_card_subtitle_inactive.name(), "#94a3b8")

    def test_render_does_not_fail(self):
        self._dock_debug()
        image = self.overlay.grab()
        self.assertFalse(image.isNull())


if __name__ == "__main__":
    unittest.main()
