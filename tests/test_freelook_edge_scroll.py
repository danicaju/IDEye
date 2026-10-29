"""FreeLook desktop edge-scroll regression tests."""

import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from ideye.ui.overlay_window import OverlayWindow

_APP = QApplication.instance() or QApplication(sys.argv if hasattr(sys, "argv") else [])


class ScrollController:
    def __init__(self):
        self.scrolls = []

    def scroll(self, dy):
        self.scrolls.append(dy)


class TestFreeLookEdgeScroll(unittest.TestCase):
    def setUp(self):
        self.overlay = OverlayWindow()
        self.overlay.mouse_controller = ScrollController()
        self.overlay._gaming_mode = False
        self.overlay._jaw_locked = False

    def tearDown(self):
        self.overlay.close()
        _APP.processEvents()

    def test_top_edge_scrolls_up_after_hold(self):
        self.assertEqual(self.overlay._update_freelook_edge_scroll(0.01, now=10.0), 0)
        self.assertEqual(self.overlay._update_freelook_edge_scroll(0.01, now=10.35), 1)
        self.assertIn(3, self.overlay.mouse_controller.scrolls)

    def test_bottom_edge_scrolls_down_after_hold(self):
        self.overlay._update_freelook_edge_scroll(0.99, now=20.0)
        self.assertEqual(self.overlay._update_freelook_edge_scroll(0.99, now=20.35), -1)
        self.assertIn(-3, self.overlay.mouse_controller.scrolls)

    def test_center_and_gaming_do_not_scroll(self):
        self.assertEqual(self.overlay._update_freelook_edge_scroll(0.50, now=30.0), 0)
        self.overlay._gaming_mode = True
        self.assertEqual(self.overlay._update_freelook_edge_scroll(0.01, now=31.0), 0)
        self.assertEqual(self.overlay._update_freelook_edge_scroll(0.01, now=31.5), 0)
        self.assertEqual(self.overlay.mouse_controller.scrolls, [])

    def test_jaw_lock_suspends_edge_scroll(self):
        self.overlay._jaw_locked = True
        self.assertEqual(self.overlay._update_freelook_edge_scroll(0.01, now=40.0), 0)
        self.assertEqual(self.overlay.mouse_controller.scrolls, [])


if __name__ == "__main__":
    unittest.main()
