"""Tests for help modal content, card header layout, and AYUDA button spacing."""

import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QRectF
from PyQt6.QtGui import QFontMetrics
from PyQt6.QtWidgets import QApplication

import eyede.config as config
from eyede.ui.debug_widget import DebugWidget
from eyede.ui.overlay_window import (
    OverlayWindow,
    HELP_GESTURES,
    HELP_SHORTCUTS,
)

_APP = QApplication.instance() or QApplication(sys.argv if hasattr(sys, "argv") else [])


def _has_emoji(text: str) -> bool:
    """Return True if the text contains emoji or pictographic symbols."""
    import re

    emoji_pattern = re.compile(
        "[\U0001F000-\U0001FAFF\u2300-\u23FF\u2600-\u27BF\uFE0F]"
    )
    return bool(emoji_pattern.search(text))


class TestHelpContent(unittest.TestCase):
    def test_help_gestures_have_no_emojis(self):
        for title, action, desc in HELP_GESTURES:
            self.assertFalse(_has_emoji(title), f"Gesture title contains emoji: {title!r}")
            self.assertFalse(_has_emoji(action), f"Gesture action contains emoji: {action!r}")
            self.assertFalse(_has_emoji(desc), f"Gesture desc contains emoji: {desc!r}")

    def test_help_gestures_include_left_wink_undo(self):
        titles = [title for title, _, _ in HELP_GESTURES]
        self.assertIn("Guiño Ojo Izquierdo", titles)
        left_wink = next((a for t, a, _ in HELP_GESTURES if t == "Guiño Ojo Izquierdo"), "")
        self.assertIn("Volver atrás / Deshacer", left_wink)

    def test_help_shortcuts_have_no_emojis(self):
        for key, name, desc in HELP_SHORTCUTS:
            self.assertFalse(_has_emoji(key), f"Shortcut key contains emoji: {key!r}")
            self.assertFalse(_has_emoji(name), f"Shortcut name contains emoji: {name!r}")
            self.assertFalse(_has_emoji(desc), f"Shortcut desc contains emoji: {desc!r}")

    def test_help_shortcuts_are_global_bindings(self):
        """Every shortcut advertised in the help modal must be a global Ctrl binding."""
        for key, name, _ in HELP_SHORTCUTS:
            self.assertTrue(key.startswith("[Ctrl+"), f"{name} is not a global Ctrl shortcut: {key}")


class TestHeaderHelpButtonLayout(unittest.TestCase):
    def setUp(self):
        self.overlay = OverlayWindow()
        self.debug = DebugWidget()

    def tearDown(self):
        self.overlay.close()
        self.debug.close()
        _APP.processEvents()

    def _dock_debug(self, width=1280, height=720):
        self.overlay.resize(width, height)
        self.debug.move(width - config.DEBUG_WINDOW_WIDTH - 12, 24)
        self.overlay.set_debug_widget(self.debug)
        self.overlay.show()
        self.debug.show()
        _APP.processEvents()
        self.overlay.refresh_grid_right_margin(animate=False)
        self.overlay._update_header_exit_rect()
        _APP.processEvents()

    def test_help_button_is_wide_enough_at_1280_compact(self):
        self._dock_debug(1280, 720)
        self.assertGreaterEqual(
            self.overlay.header_help_rect.width(),
            100.0,
            "AYUDA button must be at least 100px wide in compact layout",
        )

    def test_header_buttons_do_not_overlap_at_1280_1536_1920(self):
        for width, height in ((1280, 720), (1536, 864), (1920, 1080)):
            with self.subTest(width=width, height=height):
                self._dock_debug(width, height)
                self.assertLessEqual(
                    self.overlay.header_mode_rect.right(),
                    self.overlay.header_lang_rect.left(),
                    "mode overlaps lang",
                )
                self.assertLessEqual(
                    self.overlay.header_lang_rect.right(),
                    self.overlay.header_help_rect.left(),
                    "lang overlaps help",
                )
                self.assertLessEqual(
                    self.overlay.header_help_rect.right(),
                    self.overlay.header_exit_rect.left(),
                    "help overlaps exit",
                )
                self.assertLessEqual(
                    self.overlay.header_exit_rect.right(),
                    self.overlay.header_rect.right(),
                    "exit overflows header",
                )
                self.assertGreaterEqual(
                    self.overlay.header_help_rect.left(),
                    self.overlay.header_rect.left(),
                    "help overflows header left",
                )


class TestCardHeaderRects(unittest.TestCase):
    def setUp(self):
        self.overlay = OverlayWindow()

    def tearDown(self):
        self.overlay.close()
        _APP.processEvents()

    def test_badge_and_icon_do_not_overlap_with_badge(self):
        rect = QRectF(100.0, 100.0, 300.0, 200.0)
        badge_text = "SUBMENÚ"
        badge_rect, icon_rect = self.overlay._card_header_rects(rect, badge_text, has_icon=True)

        self.assertTrue(badge_rect.isValid())
        self.assertTrue(icon_rect.isValid())
        self.assertFalse(badge_rect.intersects(icon_rect))
        self.assertLessEqual(
            icon_rect.right(),
            badge_rect.left() - 6.0,
            "icon must sit at least 6px left of the badge",
        )
        self.assertEqual(icon_rect.width(), 28.0)
        self.assertEqual(icon_rect.height(), 28.0)

    def test_badge_width_fits_text(self):
        rect = QRectF(100.0, 100.0, 300.0, 200.0)
        badge_text = "SUBMENÚ"
        badge_rect, _ = self.overlay._card_header_rects(rect, badge_text, has_icon=False)
        metrics = QFontMetrics(self.overlay._font_status)
        min_text_w = metrics.horizontalAdvance(badge_text)
        self.assertGreaterEqual(
            badge_rect.width() - 14.0,
            min_text_w,
            "badge width minus horizontal padding must fit the text",
        )
        self.assertGreaterEqual(badge_rect.width(), 62.0, "badge width must respect 62px minimum")

    def test_icon_right_aligned_when_no_badge(self):
        rect = QRectF(100.0, 100.0, 300.0, 200.0)
        badge_rect, icon_rect = self.overlay._card_header_rects(rect, "", has_icon=True)
        self.assertFalse(badge_rect.isValid())
        self.assertTrue(icon_rect.isValid())
        self.assertAlmostEqual(icon_rect.right(), rect.right() - 10.0, places=0)

    def test_no_icon_returns_empty_rect(self):
        rect = QRectF(100.0, 100.0, 300.0, 200.0)
        badge_rect, icon_rect = self.overlay._card_header_rects(rect, "VOLVER", has_icon=False)
        self.assertTrue(badge_rect.isValid())
        self.assertFalse(icon_rect.isValid())


class TestOverlayRender(unittest.TestCase):
    def setUp(self):
        self.overlay = OverlayWindow()

    def tearDown(self):
        self.overlay.close()
        _APP.processEvents()

    def test_grab_does_not_fail_or_return_null(self):
        self.overlay.resize(1280, 720)
        self.overlay.show()
        _APP.processEvents()
        image = self.overlay.grab()
        self.assertIsNotNone(image)
        self.assertFalse(image.isNull())


if __name__ == "__main__":
    unittest.main()
