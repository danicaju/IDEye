"""Phase 7: Sniper lens, sound feedback and OS mouse injection tests.

The sniper lens tests will be added by a follow-up agent. This file covers:
  - SoundFeedbackManager buffer generation and playback safety.
  - OSMouseController coordinate injection and button mapping.
"""

import os
import sys
import time
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT_DIR not in sys.path:
    sys.path.insert(0, _ROOT_DIR)

from eyede.core.sound_feedback import SoundFeedback, SoundFeedbackManager
from eyede.core.mouse_controller import OSMouseController
from eyede.actions.code_injector import CodeInjector, DummyKeyboard, DummyClipboard
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
        self.assertEqual(mode.display_name, "FREELOOK (RATÓN)")
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
        self.assertEqual(manager.current_mode.display_name, "FREELOOK (RATÓN)")

    def test_hotkeys_include_sound_and_sniper(self):
        from pynput import keyboard

        for spec in ("s", "f", "g", "<ctrl>+<alt>+s", "<ctrl>+<alt>+f", "<ctrl>+<alt>+g"):
            with self.subTest(spec=spec):
                self.assertIn(spec, HOTKEY_ACTIONS)
                keyboard.HotKey.parse(spec)


class TestSmartPrefixDeduplication(unittest.TestCase):
    def _injector(self):
        return CodeInjector(
            async_mode=False,
            keyboard_controller=DummyKeyboard(),
            clipboard_module=DummyClipboard(),
        )

    def test_h_then_hola_injects_only_suffix(self):
        injector = self._injector()
        first, back1 = injector.prepare_insert_text("h")
        second, back2 = injector.prepare_insert_text("hola ")
        self.assertEqual(first, "h")
        self.assertEqual(back1, 0)
        self.assertEqual(second, "ola ")
        self.assertEqual(back2, 0)
        self.assertEqual(first + second, "hola ")

    def test_h_then_Hola_backspaces_then_full_word(self):
        injector = self._injector()
        injector.prepare_insert_text("h")
        prepared, backspaces = injector.prepare_insert_text("Hola ")
        self.assertEqual(prepared, "Hola ")
        self.assertEqual(backspaces, 1)

    def test_backspace_and_space_update_prefix(self):
        injector = self._injector()
        injector.prepare_insert_text("h")
        injector.prepare_insert_text("o")
        injector._track_key_effect("BACKSPACE")
        self.assertEqual(injector._current_word_prefix, "h")
        injector._track_key_effect("SPACE")
        self.assertEqual(injector._current_word_prefix, "")

    def test_exact_word_plus_space_only_injects_separator(self):
        injector = self._injector()
        injector.set_current_word_prefix("hola")
        prepared, backspaces = injector.prepare_insert_text("hola ")
        self.assertEqual(prepared, " ")
        self.assertEqual(backspaces, 0)


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

    def test_freelook_moves_real_cursor_directly(self):
        self.overlay.toggle_sniper_mode()
        self.overlay.current_mar = 0.0
        self.overlay.on_gaze_updated(0.5, 0.5)
        self.overlay.mouse_controller.move_direct.assert_called()
        screen_w, screen_h = self.overlay._get_screen_size()
        self.overlay.mouse_controller.move_direct.assert_called_with(
            int(0.5 * screen_w), int(0.5 * screen_h)
        )

    def test_jaw_lock_freezes_cursor_before_click(self):
        self.overlay.toggle_sniper_mode()
        self.overlay._freelook_last_pos = (100, 200)
        self.overlay.mar_threshold = 0.45
        self.overlay.current_mar = 0.30
        self.overlay.on_gaze_updated(0.8, 0.8)
        self.overlay.mouse_controller.move_direct.assert_not_called()
        self.assertTrue(self.overlay._jaw_locked)
        self.assertEqual(self.overlay._jaw_lock_pos, (100, 200))

    def test_short_mouth_click_fires_at_locked_position(self):
        self.overlay.toggle_sniper_mode()
        self.overlay._freelook_last_pos = (300, 400)
        self.overlay.mar_threshold = 0.45
        self.overlay._update_freelook_mouth(0.50)
        self.overlay._mouth_start = time.time() - 0.1
        self.overlay._update_freelook_mouth(0.0)
        self.overlay.mouse_controller.left_click.assert_called_once_with(300, 400)

    def test_gaming_hold_mouth_walks_with_w(self):
        self.overlay.toggle_sniper_mode()
        self.overlay.toggle_gaming_mode()
        self.overlay._freelook_last_pos = (300, 400)
        self.overlay.mar_threshold = 0.45
        self.overlay._update_freelook_mouth(0.50)
        self.overlay._mouth_start = time.time() - 0.5
        self.overlay._update_freelook_mouth(0.50)
        self.overlay.mouse_controller.key_down.assert_called_with("w")
        self.overlay._update_freelook_mouth(0.0)
        self.overlay.mouse_controller.key_up.assert_called_with("w")

    def test_gaming_right_wink_holds_right_button(self):
        self.overlay.toggle_sniper_mode()
        self.overlay.toggle_gaming_mode()
        self.overlay.on_gesture_triggered("WINK_RIGHT")
        self.overlay.mouse_controller.mouse_down.assert_called_with("right")
        self.overlay.on_gesture_triggered("WINK_RIGHT")
        self.overlay.mouse_controller.mouse_up.assert_called_with("right")

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
