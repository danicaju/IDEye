"""Hotfix regression tests: help overflow, audio test button and head-joystick."""

import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPainter, QPixmap

from ideye.ui.overlay_window import OverlayWindow, HELP_SHORTCUTS
from ideye.ui.debug_widget import DebugWidget

_APP = QApplication.instance() or QApplication(sys.argv)


class FakeController:
    def __init__(self):
        self.down = []
        self.up = []
        self.moves = []
        self.released = []
        self.current_clicks = 0
        self.buttons_released = 0

    def key_down(self, key):
        self.down.append(key)

    def key_up(self, key):
        self.up.append(key)

    def move_direct(self, x, y):
        self.moves.append((x, y))

    def left_click_current(self):
        self.current_clicks += 1

    def left_click(self, x, y):
        self.moves.append((x, y))

    def release_all_game_keys(self, keys=("w", "a", "s", "d", " ")):
        self.released.append(tuple(keys))

    def release_all_buttons(self):
        self.buttons_released += 1


class TestHelpModalOverflow(unittest.TestCase):
    def setUp(self):
        self.overlay = OverlayWindow()
        self.overlay.resize(1280, 720)

    def tearDown(self):
        self.overlay.close()

    def test_modal_and_all_columns_fit_inside_screen(self):
        layout = self.overlay._help_modal_layout(1280, 720)
        card = layout["card"]
        self.assertLessEqual(card.bottom(), 720)
        self.assertGreaterEqual(card.top(), 0)
        for column in layout["columns"]:
            self.assertLessEqual(column.right(), card.right())
            self.assertLessEqual(column.bottom(), card.bottom())
        for rows, _ in layout["shortcut_columns"]:
            total = 36.0 + sum(row[4] for row in rows)
            self.assertLessEqual(total, layout["columns"][1].height())
        gestures_total = 36.0 + sum(row[6] for row in layout["gesture_rows"])
        self.assertLessEqual(gestures_total, layout["columns"][0].height())

    def test_close_button_is_inside_card(self):
        self.overlay._update_help_modal_rect()
        self.assertTrue(self.overlay.help_modal_rect.contains(self.overlay.help_modal_close_rect))

    def test_all_help_keys_are_ctrl_alt_letter(self):
        for key, _name, _desc in HELP_SHORTCUTS:
            self.assertTrue(key.startswith("[Ctrl+Alt+"))

    def test_help_modal_paints_without_error(self):
        pixmap = QPixmap(1280, 720)
        painter = QPainter(pixmap)
        try:
            self.overlay._paint_help_modal(painter, 1280, 720)
        finally:
            painter.end()


class TestDebugGuideWrapping(unittest.TestCase):
    def test_guide_labels_wrap_and_do_not_expand(self):
        widget = DebugWidget()
        self.assertTrue(widget.guide_content.wordWrap())
        self.assertEqual(widget.guide_content.minimumWidth(), 0)
        self.assertTrue(hasattr(widget, "btn_test_sound"))
        emitted = []
        widget.test_sound_requested.connect(lambda: emitted.append(True))
        widget.btn_test_sound.click()
        self.assertEqual(len(emitted), 1)
        widget.close()

    def test_guide_uses_unicode_bullets_and_spanish_accents(self):
        widget = DebugWidget()
        text = widget.guide_content.text()
        self.assertIn("•", text)
        self.assertIn("Guiño", text)
        self.assertIn("menús", text)
        self.assertNotIn("<div>? ", text)
        self.assertLess(text.index("GESTOS FACIALES Y OCULARES"), text.index("Abrir boca"))
        self.assertLess(text.index("Abrir boca"), text.index("ATAJOS DE TECLADO"))
        self.assertLess(text.index("ATAJOS DE TECLADO"), text.index("Ctrl+Alt+A"))
        widget.close()


class TestHeadJoystick(unittest.TestCase):
    def setUp(self):
        self.overlay = OverlayWindow()
        self.overlay.resize(1280, 720)
        self.controller = FakeController()
        self.overlay.set_mouse_controller(self.controller)
        self.overlay.toggle_sniper_mode()
        self.overlay.toggle_gaming_mode()

    def tearDown(self):
        self.overlay.close()

    def test_joystick_moves_without_cursor_and_releases_center(self):
        self.overlay.on_gaze_updated(0.5, 0.20)
        self.assertIn("w", self.controller.down)
        self.assertEqual(self.controller.moves, [])
        self.overlay.on_gaze_updated(0.5, 0.50)
        self.assertIn("w", self.controller.up)

    def test_joystick_left_right_and_release_all(self):
        self.overlay.on_gaze_updated(0.20, 0.50)
        self.assertIn("a", self.controller.down)
        self.overlay.release_all_game_keys()
        self.assertTrue(any("a" in keys for keys in self.controller.released))
        self.assertEqual(self.controller.buttons_released, 1)

    def test_right_wink_toggles_menu_cursor_and_back(self):
        self.overlay.on_gesture_triggered("WINK_RIGHT")
        self.assertEqual(self.overlay._gaming_control_state, "MENU_CURSOR")
        self.overlay.on_gaze_updated(0.8, 0.2)
        self.assertTrue(self.controller.moves)
        self.overlay.on_gesture_triggered("WINK_RIGHT")
        self.assertEqual(self.overlay._gaming_control_state, "JOYSTICK")

    def test_mouth_click_in_joystick_does_not_move_cursor(self):
        self.overlay._update_freelook_mouth(0.60)
        self.overlay._update_freelook_mouth(0.0)
        self.assertEqual(self.controller.current_clicks, 1)
        self.assertEqual(self.controller.moves, [])

    def test_leaving_gaming_releases_all_keys(self):
        self.overlay.on_gaze_updated(0.5, 0.20)
        self.assertTrue(self.overlay._game_keys_down)
        self.overlay.toggle_gaming_mode()
        self.assertFalse(self.overlay._game_keys_down)
        self.assertTrue(self.controller.released)


if __name__ == "__main__":
    unittest.main()
