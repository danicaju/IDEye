"""Phase 7: Sniper lens, sound feedback and OS mouse injection tests.

The sniper lens tests will be added by a follow-up agent. This file covers:
  - SoundFeedbackManager buffer generation and playback safety.
  - OSMouseController coordinate injection and button mapping.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT_DIR not in sys.path:
    sys.path.insert(0, _ROOT_DIR)

from eyede.core.sound_feedback import SoundFeedback, SoundFeedbackManager
from eyede.core.mouse_controller import OSMouseController
from eyede.actions.menu_trees import validate_menu_tree
from eyede.core.hotkey_manager import HOTKEY_ACTIONS
from eyede.modes.mode_manager import ModeManager
from eyede.modes.sniper_mouse_mode import SniperMouseMode
from PyQt6.QtWidgets import QApplication
from eyede.ui.overlay_window import OverlayWindow

_APP = QApplication.instance() or QApplication(sys.argv if hasattr(sys, "argv") else [])


class TestSoundFeedback(unittest.TestCase):
    def test_all_buffers_are_valid_wav(self):
        mgr = SoundFeedbackManager(enabled=True, volume=0.5)
        self.assertEqual(len(mgr._buffers), 4)
        for name, buf in mgr._buffers.items():
            with self.subTest(sound=name):
                self.assertTrue(buf.startswith(b"RIFF"))
                self.assertIn(b"WAVE", buf)
                self.assertGreater(len(buf), 44)

    def test_mute_prevents_backend_call(self):
        mgr = SoundFeedbackManager(enabled=True, volume=0.5)
        mgr.set_enabled(False)
        with patch("eyede.core.sound_feedback.winsound.PlaySound") as mock_play:
            mgr.play("click")
            mgr.play("back")
            mgr.play("mode")
            mgr.play("pause")
            mock_play.assert_not_called()

    def test_backend_exception_is_swallowed(self):
        mgr = SoundFeedbackManager(enabled=True, volume=0.5)
        with patch("eyede.core.sound_feedback.winsound.PlaySound", side_effect=OSError("boom")):
            # Should not raise.
            mgr.play("click")
            mgr.play("unknown")

    def test_unknown_sound_is_noop(self):
        mgr = SoundFeedbackManager(enabled=True, volume=0.5)
        with patch("eyede.core.sound_feedback.winsound.PlaySound") as mock_play:
            mgr.play("nonexistent")
            mock_play.assert_not_called()

    def test_toggle_mute_returns_new_state(self):
        mgr = SoundFeedbackManager(enabled=True, volume=0.5)
        self.assertTrue(mgr.is_enabled())
        self.assertFalse(mgr.toggle_mute())
        self.assertFalse(mgr.is_enabled())
        self.assertTrue(mgr.toggle_mute())
        self.assertTrue(mgr.is_enabled())

    def test_volume_is_clipped(self):
        mgr = SoundFeedbackManager(enabled=True, volume=1.5)
        self.assertAlmostEqual(mgr.volume, 1.0)
        mgr.volume = -0.1
        self.assertAlmostEqual(mgr.volume, 0.0)

    def test_alias(self):
        self.assertIs(SoundFeedback, SoundFeedbackManager)


class TestOSMouseController(unittest.TestCase):
    def test_left_click_moves_then_clicks(self):
        mock_controller = MagicMock()
        mouse = OSMouseController(controller=mock_controller)
        mouse.left_click(123, 456)
        self.assertEqual(mock_controller.position, (123, 456))
        mock_controller.click.assert_called_once()
        args, _ = mock_controller.click.call_args
        self.assertIs(args[0].name if hasattr(args[0], "name") else str(args[0]), "left")

    def test_right_click_uses_right_button(self):
        mock_controller = MagicMock()
        mouse = OSMouseController(controller=mock_controller)
        mouse.right_click(200, 100)
        self.assertEqual(mock_controller.position, (200, 100))
        args, _ = mock_controller.click.call_args
        self.assertIs(args[0].name if hasattr(args[0], "name") else str(args[0]), "right")

    def test_double_click_fires_twice(self):
        mock_controller = MagicMock()
        mouse = OSMouseController(controller=mock_controller)
        mouse.double_click(50, 75)
        self.assertEqual(mock_controller.position, (50, 75))
        mock_controller.click.assert_called_once()
        args, kwargs = mock_controller.click.call_args
        self.assertIs(args[0].name if hasattr(args[0], "name") else str(args[0]), "left")
        self.assertEqual(kwargs.get("count", args[1] if len(args) > 1 else 1), 2)

    def test_move_only_sets_position_without_click(self):
        mock_controller = MagicMock()
        mouse = OSMouseController(controller=mock_controller)
        mouse.move_only(999, 1)
        self.assertEqual(mock_controller.position, (999, 1))
        mock_controller.click.assert_not_called()
        mock_controller.scroll.assert_not_called()

    def test_scroll_at_moves_then_scrolls(self):
        mock_controller = MagicMock()
        mouse = OSMouseController(controller=mock_controller)
        mouse.scroll_at(400, 300, -3)
        self.assertEqual(mock_controller.position, (400, 300))
        mock_controller.scroll.assert_called_once_with(0, -3)

    def test_move_to_casts_to_int(self):
        mock_controller = MagicMock()
        mouse = OSMouseController(controller=mock_controller)
        mouse.move_to(12.9, 34.1)
        self.assertEqual(mock_controller.position, (12, 34))


class TestSniperMouseMode(unittest.TestCase):
    def test_mode_metadata_and_root_structure(self):
        mode = SniperMouseMode()
        self.assertEqual(mode.mode_id, "sniper")
        self.assertEqual(mode.display_name, "FRANCOTIRADOR (RATÓN)")
        self.assertEqual(mode.theme_color, "#F43F5E")

        root = mode.get_root_menu()
        self.assertEqual(len(root.items), 9)
        self.assertTrue(validate_menu_tree({"ROOT": root}))
        self.assertEqual(root.items[4].action_type, "PAUSE")
        self.assertEqual(root.items[6].action_type, "BACK")
        self.assertEqual(root.items[0].id, "SNIPER_SECTOR_0")
        self.assertEqual(root.items[5].id, "SNIPER_SECTOR_5")
        self.assertEqual(root.items[8].id, "SNIPER_SECTOR_8")
        self.assertEqual(root.items[0].label, "1: Sector 1")
        self.assertEqual(root.items[5].label, "6: Sector 6")
        self.assertEqual(root.items[8].label, "9: Sector 9")

    def test_action_cycle(self):
        mode = SniperMouseMode()
        self.assertEqual(mode.get_action(), SniperMouseMode.ACTION_LEFT)
        self.assertEqual(mode.cycle_action(), SniperMouseMode.ACTION_DOUBLE)
        self.assertEqual(mode.cycle_action(), SniperMouseMode.ACTION_RIGHT)
        self.assertEqual(mode.cycle_action(), SniperMouseMode.ACTION_SCROLL_UP)
        self.assertEqual(mode.cycle_action(), SniperMouseMode.ACTION_SCROLL_DOWN)
        self.assertEqual(mode.cycle_action(), SniperMouseMode.ACTION_LEFT)
        mode.set_action("right")
        self.assertEqual(mode.get_action(), SniperMouseMode.ACTION_RIGHT)
        self.assertEqual(mode.action_label, "Clic Der")

    def test_mode_manager_registration_and_switch(self):
        manager = ModeManager(initial_mode="coding", auto_switch_enabled=False)
        self.assertIn("sniper", manager.mode_ids)
        self.assertIsInstance(manager.get_mode("sniper"), SniperMouseMode)
        manager.set_mode("sniper", emit=False)
        self.assertEqual(manager.current_mode_id, "sniper")
        self.assertEqual(manager.current_mode.display_name, "FRANCOTIRADOR (RATÓN)")

    def test_hotkeys_include_sound_and_sniper(self):
        from pynput import keyboard

        for spec in ("s", "f", "<ctrl>+<alt>+s", "<ctrl>+<alt>+f"):
            with self.subTest(spec=spec):
                self.assertIn(spec, HOTKEY_ACTIONS)
                keyboard.HotKey.parse(spec)


class TestSniperOverlayCoordinates(unittest.TestCase):
    def setUp(self):
        self.overlay = OverlayWindow(start_in_mode_selector=False)
        self.overlay.mouse_controller = MagicMock()

    def tearDown(self):
        self.overlay.close()
        _APP.processEvents()

    def test_sector_and_subcell_math_1920x1080(self):
        self.assertEqual(self.overlay._calculate_sector_rect(0, 1920, 1080), (0, 0, 640, 360))
        self.assertEqual(self.overlay._calculate_sector_rect(8, 1920, 1080), (1280, 720, 640, 360))
        self.assertEqual(
            self.overlay._calculate_subcell_coords(4, (0, 0, 640, 360)),
            (320, 180),
        )

    def test_two_step_click_uses_locked_sector_center(self):
        self.overlay.toggle_sniper_mode()
        self.assertEqual(self.overlay.current_context_mode_id, "sniper")
        self.overlay.navigate_to("ROOT")
        self.overlay.hovered_block = 0
        self.overlay.on_gesture_triggered("MOUTH_CLICK")
        self.assertEqual(self.overlay._sniper_step, 2)
        self.assertEqual(self.overlay._sniper_locked_sector, 0)

        self.overlay.hovered_subcell = 4
        self.overlay.on_gesture_triggered("MOUTH_CLICK")
        self.assertEqual(self.overlay._sniper_step, 1)
        sector = self.overlay._calculate_sector_rect(0, *self.overlay._get_screen_size())
        expected = self.overlay._calculate_subcell_coords(4, sector)
        self.overlay.mouse_controller.left_click.assert_called_once_with(*expected)

    def test_sound_toggle_updates_state(self):
        fake = MagicMock()
        fake.toggle_mute.return_value = False
        self.overlay.set_sound_feedback(fake)
        self.assertFalse(self.overlay.toggle_sound_feedback())
        fake.toggle_mute.assert_called_once()
        self.assertIn("Sonido: OFF", self.overlay.last_action_desc)

    def test_sniper_is_reachable_without_breaking_hub_back(self):
        node = self.overlay.menu_tree["MODE_SELECT"]
        self.assertEqual(node.items[6].action_type, "BACK")
        self.assertEqual(node.items[7].mode_id, "sniper")
        self.assertEqual(self.overlay.mode_manager.get_mode("sniper").mode_id, "sniper")


if __name__ == "__main__":
    unittest.main()
