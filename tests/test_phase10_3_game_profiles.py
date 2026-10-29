"""Phase 10.3: dynamic game profiles, twin-stick and strategy edge-scroll."""

import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication

from ideye.core.game_profiles import GameProfileManager
from ideye.ui.overlay_window import OverlayWindow

_APP = QApplication.instance() or QApplication(sys.argv)


class FakeController:
    def __init__(self):
        self.keys_down = []
        self.keys_up = []
        self.moves = []

    def key_down(self, key):
        self.keys_down.append(key)

    def key_up(self, key):
        self.keys_up.append(key)

    def move_direct(self, x, y):
        self.moves.append((x, y))

    def release_all_game_keys(self, *args, **kwargs):
        pass

    def release_all_buttons(self):
        pass


class TestGameProfileManager(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "game_profiles.json"
        self.manager = GameProfileManager(str(self.path))

    def tearDown(self):
        self.tmp.cleanup()

    def test_defaults_are_persisted_and_resolved(self):
        self.assertTrue(self.path.exists())
        self.assertEqual(self.manager.resolve_for_window("Minecraft", "javaw.exe"), "sandbox_3d")
        self.assertEqual(self.manager.resolve_for_window("The Binding of Isaac", "isaac-ng.exe"), "twin_stick_roguelike")
        self.assertEqual(self.manager.resolve_for_window("Baldur's Gate 3", "bg3.exe"), "strategy_rpg")
        self.assertEqual(self.manager.resolve_for_window("Chrome", "chrome.exe"), "default_desktop")
        self.assertEqual(self.manager.get_profile("twin_stick_roguelike")["primary"], "mouth_click")

    def test_profile_keys_and_active_label(self):
        profile = self.manager.set_active("sandbox_3d")
        self.assertEqual(profile["movement"], "head_joystick")
        self.assertEqual(profile["jump"], "wink_left")
        self.assertEqual(self.manager.active_label(), "Sandbox 3D")


class TestProfileControls(unittest.TestCase):
    def setUp(self):
        self.overlay = OverlayWindow()
        self.controller = FakeController()
        self.overlay.set_mouse_controller(self.controller)

    def tearDown(self):
        self.overlay.close()
        _APP.processEvents()

    def test_twin_stick_moves_head_and_gaze(self):
        self.overlay.set_game_profile("twin_stick_roguelike")
        self.overlay._update_gameplay_joystick(0.2, 0.2)
        self.assertIn("w", self.controller.keys_down)
        self.assertIn("a", self.controller.keys_down)
        self.assertTrue(self.controller.moves)

    def test_strategy_edge_scroll_moves_cursor_at_border(self):
        self.overlay.set_game_profile("strategy_rpg")
        self.overlay._gaming_mode = True
        self.overlay._freelook_last_pos = (100, 100)
        self.assertTrue(self.overlay._update_strategy_edge_scroll(1.0, 0.5, now=10.0))
        self.assertTrue(self.controller.moves)
        self.assertGreater(self.controller.moves[-1][0], 100)


if __name__ == "__main__":
    unittest.main()
