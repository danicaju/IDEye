"""Tests for the Glass & Focus UI redesign (Phase 6.5)."""

import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

import ideye.config as config
from ideye.ui.debug_widget import DebugWidget
from ideye.ui.overlay_window import OverlayWindow

_APP = QApplication.instance() or QApplication(sys.argv if hasattr(sys, "argv") else [])


class TestGlassFocusLayout(unittest.TestCase):
    def setUp(self):
        self.overlay = OverlayWindow()
        self.debug = DebugWidget()

    def tearDown(self):
        self.overlay.close()
        self.debug.close()
        _APP.processEvents()

    def _dock_debug(self, width=1920, height=1080):
        self.overlay.resize(width, height)
        self.debug.move(width - config.DEBUG_WINDOW_WIDTH - 12, 24)
        self.overlay.set_debug_widget(self.debug)
        self.overlay.show()
        self.debug.show()
        _APP.processEvents()
        self.overlay.refresh_grid_right_margin(animate=False)
        self.overlay._update_header_exit_rect()
        _APP.processEvents()

    def test_expanded_monitor_reserves_space_and_collapse_expands_grid(self):
        self._dock_debug()
        margin = self.overlay._get_effective_right_margin(1920)
        self.assertGreaterEqual(margin, config.DEBUG_WINDOW_WIDTH + 16)

        debug_left = self.debug.x() - self.overlay.x()
        for idx in (2, 5, 8):
            self.assertLessEqual(self.overlay.get_block_rect(idx).right(), debug_left - 12)

        expanded_right = self.overlay.get_block_rect(2).right()
        self.debug.toggle_collapse()
        _APP.processEvents()
        self.overlay.refresh_grid_right_margin(animate=False)
        self.assertEqual(self.overlay._get_effective_right_margin(1920), 0.0)
        self.assertGreater(self.overlay.get_block_rect(2).right(), expanded_right)

        self.debug.toggle_collapse()
        _APP.processEvents()
        self.overlay.refresh_grid_right_margin(animate=False)
        self.assertGreaterEqual(self.overlay._get_effective_right_margin(1920), config.DEBUG_WINDOW_WIDTH + 16)

    def test_command_bar_never_overlaps_its_buttons_at_1280(self):
        self._dock_debug(1280, 720)
        self.assertGreaterEqual(self.overlay.header_mode_rect.left(), self.overlay._header_logo_rect.right())
        self.assertLessEqual(self.overlay.header_mode_rect.right(), self.overlay.header_lang_rect.left())
        self.assertLessEqual(self.overlay.header_lang_rect.right(), self.overlay.header_help_rect.left())
        self.assertLessEqual(self.overlay.header_help_rect.right(), self.overlay.header_exit_rect.left())
        self.assertLessEqual(self.overlay.header_exit_rect.right(), self.overlay.header_rect.right())
        self.assertGreaterEqual(self.overlay.header_exit_rect.width(), 80)
        self.assertGreaterEqual(self.overlay.header_help_rect.width(), 100)

    def test_header_keeps_large_targets_at_1080p(self):
        self.overlay.resize(1920, 1080)
        self.overlay._update_header_exit_rect()
        self.assertGreaterEqual(self.overlay.header_exit_rect.width(), 150)
        self.assertGreaterEqual(self.overlay.header_help_rect.width(), 130)
        self.assertEqual(self.overlay.header_rect.height(), 52)

    def test_card_style_hierarchy_is_neutral_except_active_theme(self):
        self.overlay._set_theme_color("#10B981")
        self.assertEqual(self.overlay._pen_card_active.color().name(), "#10b981")
        self.assertEqual(self.overlay._pen_card_inactive.color().alpha(), 28)
        self.assertEqual(self.overlay._brush_card_inactive.color().alpha(), 18)
        self.assertEqual(self.overlay._brush_card_active.color().alpha(), 115)
        self.assertEqual(self.overlay._brush_band_active.color().alpha(), 225)
        self.assertEqual(self.overlay._brush_band_inactive.color().alpha(), 230)

    def test_mar_updates_reticle_progress_state(self):
        self.overlay.mar_threshold = 0.5
        self.overlay.on_mar_updated(None, 0.25)
        self.assertAlmostEqual(self.overlay.current_mar, 0.25)
        image = self.overlay.grab()
        self.assertFalse(image.isNull())


if __name__ == "__main__":
    unittest.main()
