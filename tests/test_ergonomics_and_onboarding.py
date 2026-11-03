"""
Automated unit and integration tests for IDEye's user-friendly ergonomics,
smart ghost mode, 1-point micro-recalibration, pre-flight checks, adaptive dwell,
universal undo, and high-contrast themes.
"""

import os
import sys
import math
import time
import unittest
from typing import Optional

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtWidgets import QApplication

from ideye import config
from ideye.core.gaze_estimator import GazeEstimator
from ideye.core.sound_feedback import SoundFeedbackManager
from ideye.actions.menu_trees import (
    build_menu_tree,
    get_dynamic_ast_action_for_context,
    MenuAction,
)
from ideye.ui.calibration_ui import CalibrationUI
from ideye.ui.overlay_window import OverlayWindow


_APP = QApplication.instance() or QApplication(sys.argv if hasattr(sys, "argv") else [])


class TestErgonomicsAndLayout(unittest.TestCase):
    """Tests Flexible HUD Layouts (Right Dock vs Full Grid) and pass-through ergonomics."""

    def setUp(self):
        self.overlay = OverlayWindow()
        self.overlay.resize(1920, 1080)

    def tearDown(self):
        self.overlay.close()

    def test_default_layout_and_toggle(self):
        self.assertEqual(self.overlay.hud_layout_mode, "FULL_GRID")
        changed_layouts = []
        self.overlay.layout_changed.connect(lambda l: changed_layouts.append(l))

        new_layout = self.overlay.toggle_hud_layout()
        self.assertEqual(new_layout, "RIGHT_DOCK")
        self.assertEqual(self.overlay.hud_layout_mode, "RIGHT_DOCK")
        self.assertEqual(changed_layouts, ["RIGHT_DOCK"])

        new_layout_2 = self.overlay.toggle_hud_layout()
        self.assertEqual(new_layout_2, "FULL_GRID")
        self.assertEqual(self.overlay.hud_layout_mode, "FULL_GRID")
        self.assertEqual(changed_layouts, ["RIGHT_DOCK", "FULL_GRID"])

    def test_right_dock_geometry_docked_to_right_30_percent(self):
        self.overlay.set_hud_layout("RIGHT_DOCK")
        rect_0 = self.overlay.get_block_rect(0)
        rect_2 = self.overlay.get_block_rect(2)
        total_w = 1920.0
        expected_dock_w = 1920.0 * 0.30  # 576 clamped to max 500 = 500.0
        expected_dock_w = min(500.0, max(460.0, expected_dock_w))

        # Check that cards are in the right-hand column:
        self.assertGreater(rect_0.left(), total_w - expected_dock_w - 30.0)
        self.assertLessEqual(rect_2.right(), total_w)

    def test_right_dock_leaves_left_editor_area_clear_pass_through(self):
        self.overlay.set_hud_layout("RIGHT_DOCK")
        # Gaze in left editor area (e.g. normalized x=0.20, y=0.50 -> px=384)
        self.overlay.on_gaze_updated(0.20, 0.50)
        self.assertIsNone(self.overlay.hovered_block)
        self.assertEqual(self.overlay._dwell_progress, 0.0)

        # Gaze into the dock (e.g. x=0.85, y=0.50 -> px=1632)
        self.overlay.on_gaze_updated(0.85, 0.50)
        self.assertIsNotNone(self.overlay.hovered_block)

    def test_right_dock_header_alignment(self):
        self.overlay.set_hud_layout("RIGHT_DOCK")
        card_2 = self.overlay.get_block_rect(2)
        header_rect = self.overlay.header_rect
        self.assertAlmostEqual(header_rect.right(), card_2.right(), delta=1.0)


class TestSmartGhostMode(unittest.TestCase):
    """Tests Smart Ghost Mode smooth dimming and 0ms instant wake."""

    def setUp(self):
        self.overlay = OverlayWindow()
        self.overlay.resize(1920, 1080)
        self.overlay.set_ghost_peek_enabled(True, emit_signal=False)

    def tearDown(self):
        self.overlay.close()

    def test_ghost_mode_dims_on_idle(self):
        now = time.time()
        self.overlay._last_ghost_interaction = now - 40.0
        # Tick fade step
        op1 = self.overlay.update_ghost_peek(now=now, idle_seconds=30.0, target_opacity=0.15)
        self.assertLess(op1, 1.0)

        # Full fade down to target
        for _ in range(20):
            self.overlay.update_ghost_peek(now=now, idle_seconds=30.0, target_opacity=0.15)
        self.assertAlmostEqual(self.overlay._ghost_opacity, 0.15, places=2)

    def test_ghost_mode_instant_0ms_wake_on_hud_gaze(self):
        self.overlay._ghost_opacity = 0.15
        self.overlay._wake_ghost_peek()
        self.assertEqual(self.overlay._ghost_opacity, 1.0)

    def test_ghost_mode_does_not_wake_while_reading_editor_in_right_dock(self):
        self.overlay.set_hud_layout("RIGHT_DOCK")
        self.overlay._ghost_opacity = 0.15
        self.overlay._last_ghost_interaction = time.time() - 50.0

        # Looking at editor on the left (e.g. x=0.25, y=0.50)
        self.overlay.on_gaze_updated(0.25, 0.50)
        self.assertIsNone(self.overlay.hovered_block)
        # Opacity remains dimmed
        self.assertEqual(self.overlay._ghost_opacity, 0.15)

        # Looking into HUD dock (e.g. x=0.85, y=0.50)
        self.overlay.on_gaze_updated(0.85, 0.50)
        self.assertIsNotNone(self.overlay.hovered_block)
        # Opacity wakes instantly to 1.0 (0ms)
        self.assertEqual(self.overlay._ghost_opacity, 1.0)


class TestCalibrationPostureAndMicroRecalibration(unittest.TestCase):
    """Tests Pre-flight Posture/Illumination checks and 1-Point Micro-recalibration."""

    def test_posture_distance_calculation(self):
        # 60.0 * (0.28 / 0.28) = 60.0 cm (optimal)
        d_opt = GazeEstimator.calculate_posture_distance_cm(0.28)
        self.assertAlmostEqual(d_opt, 60.0, places=1)

        # Too close: eye_span = 0.40 -> ~42 cm (<50cm)
        d_close = GazeEstimator.calculate_posture_distance_cm(0.40)
        self.assertLess(d_close, 50.0)

        # Too far: eye_span = 0.20 -> ~84 cm (>70cm)
        d_far = GazeEstimator.calculate_posture_distance_cm(0.20)
        self.assertGreater(d_far, 70.0)

    def test_calibration_ui_preflight_slots(self):
        cal_ui = CalibrationUI()
        cal_ui.on_distance_updated(62.0)
        self.assertTrue(cal_ui.posture_optimal)
        self.assertEqual(cal_ui.current_distance_cm, 62.0)

        cal_ui.on_distance_updated(35.0)
        self.assertFalse(cal_ui.posture_optimal)

        cal_ui.on_lighting_updated(140.0)
        self.assertTrue(cal_ui.lighting_optimal)
        self.assertEqual(cal_ui.current_luma, 140.0)

        cal_ui.on_lighting_updated(30.0)
        self.assertFalse(cal_ui.lighting_optimal)
        cal_ui.close()

    def test_micro_recalibrate_one_point_snap_to_caret(self):
        estimator = GazeEstimator()
        # Seed an initial position
        estimator.smoothed_x = 0.45
        estimator.smoothed_y = 0.48

        # Snap to editor caret at (0.35, 0.50)
        offset_x, offset_y = estimator.micro_recalibrate(0.35, 0.50)
        self.assertAlmostEqual(offset_x, -0.10, places=2)
        self.assertAlmostEqual(offset_y, 0.02, places=2)
        self.assertAlmostEqual(estimator.smoothed_x, 0.35, places=2)
        self.assertAlmostEqual(estimator.smoothed_y, 0.50, places=2)

        # Reset micro recalibration
        estimator.reset_micro_recalibration()
        self.assertEqual(estimator.micro_offset_x, 0.0)
        self.assertEqual(estimator.micro_offset_y, 0.0)


class TestAdaptiveDwellAndSafeRest(unittest.TestCase):
    """Tests Adaptive Dwell ergonomics, safe rest infinite dwell, and relaxed magnetism."""

    def setUp(self):
        self.overlay = OverlayWindow()
        self.overlay.resize(1920, 1080)

    def tearDown(self):
        self.overlay.close()

    def test_adaptive_dwell_scaling(self):
        # Block 4 (Safe Rest) MUST be infinite dwell (no Midas touch)
        dwell_rest = self.overlay.get_adaptive_dwell_time(None, 4)
        self.assertTrue(math.isinf(dwell_rest))

        # Navigation / Keys: ~300ms agile
        nav_item = MenuAction("NAV_TEST", "1: Sub", "Desc", "SUBMENU", submenu_id="TEST")
        dwell_nav = self.overlay.get_adaptive_dwell_time(nav_item, 0)
        self.assertEqual(dwell_nav, 0.30)

        # Critical / Danger: ~850ms safe
        exit_item = MenuAction("CONFIRM_EXIT", "9: Salir", "Desc", "EXIT")
        dwell_exit = self.overlay.get_adaptive_dwell_time(exit_item, 8)
        self.assertEqual(dwell_exit, 0.85)

        # Standard snippets: ~450ms balanced
        snippet_item = MenuAction("SNIP_TEST", "2: fn", "Desc", "SNIPPET", snippet="def foo():")
        dwell_snippet = self.overlay.get_adaptive_dwell_time(snippet_item, 1)
        self.assertEqual(dwell_snippet, 0.45)

    def test_safe_rest_magnetic_capture(self):
        # Cell 4 has expanded gravity boundary
        gx, gy = self.overlay._apply_cell_gravity(0.50, 0.50, 4)
        # Should stay cleanly centered
        self.assertAlmostEqual(gx, 0.50, places=1)
        self.assertAlmostEqual(gy, 0.50, places=1)


class TestUniversalUndoAndCommandPalette(unittest.TestCase):
    """Tests Universal Undo (Ctrl+Z) and Gaze Command Palette (Spotlight)."""

    def setUp(self):
        self.overlay = OverlayWindow()
        self.overlay.resize(1920, 1080)

    def tearDown(self):
        self.overlay.close()

    def test_universal_undo_dispatch(self):
        undo_fired = []
        self.overlay.undo_requested.connect(lambda: undo_fired.append(True))
        self.overlay.trigger_undo()
        self.assertEqual(undo_fired, [True])
        self.assertIn("Deshacer", self.overlay.last_action_desc)

    def test_command_palette_navigation_and_items(self):
        self.overlay.open_command_palette()
        self.assertEqual(self.overlay.current_node_id, "COMMAND_PALETTE")
        items = self.overlay.current_node.items
        self.assertEqual(len(items), 9)
        self.assertEqual(items[3].id, "CMD_UNDO")
        self.assertEqual(items[4].id, "PAUSE_RESUME")
        self.assertEqual(items[7].id, "CMD_SNAP_CARET")
        self.assertEqual(items[8].id, "CMD_TOGGLE_DOCK")

    def test_dynamic_ast_action_injection(self):
        # FUNCTION_SIGNATURE context
        act_fn = get_dynamic_ast_action_for_context("FUNCTION_SIGNATURE", "PYTHON", "9")
        self.assertIn("docstring", act_fn.label.lower())

        # TRY_BLOCK context
        act_try = get_dynamic_ast_action_for_context("TRY_BLOCK", "PYTHON", "9")
        self.assertIn("except", act_try.label.lower())

        # IF_BLOCK context
        act_if = get_dynamic_ast_action_for_context("IF_BLOCK", "PYTHON", "9")
        self.assertIn("elif", act_if.label.lower())

    def test_universal_undo_execute_action_variants(self):
        undo_calls = []
        self.overlay.undo_requested.connect(lambda: undo_calls.append("UNDO"))

        # Test execute_action with EDIT_UNDO
        edit_undo = MenuAction("EDIT_UNDO", "4: Deshacer", "Ctrl+Z", "KEY", key_name="UNDO")
        self.overlay.execute_action(edit_undo, target_block=3)
        self.assertEqual(len(undo_calls), 1)

        # Test execute_action with CMD_UNDO
        cmd_undo = MenuAction("CMD_UNDO", "4: Deshacer", "Ctrl+Z", "KEY", key_name="UNDO")
        self.overlay.execute_action(cmd_undo, target_block=3)
        self.assertEqual(len(undo_calls), 2)

    def test_universal_undo_wink_left_gesture_at_root(self):
        undo_calls = []
        self.overlay.undo_requested.connect(lambda: undo_calls.append("UNDO"))

        self.overlay.current_node_id = "ROOT"
        self.overlay.on_gesture_triggered("WINK_LEFT")
        self.assertEqual(undo_calls, ["UNDO"])

    def test_root_card_9_behavior_general_and_ast_context(self):
        self.overlay.current_node_id = "ROOT"
        self.overlay.current_context_mode_id = "coding"
        self.overlay._cached_adaptive_node = None
        self.overlay._last_ast_eval_time = 0.0

        # General context -> Card 9 is MENU_SNIPPETS
        node_gen = self.overlay.current_node
        self.assertEqual(node_gen.items[8].id, "MENU_SNIPPETS")
        self.assertEqual(node_gen.items[8].submenu_id, "SNIPPETS")

        # Mock AST context -> Card 9 becomes immediate dynamic AST snippet
        class MockReader:
            def detect_syntactic_context(self, language="PYTHON"):
                return {"context": "FUNCTION_SIGNATURE", "line": "def hello():"}

        self.overlay.context_reader = MockReader()
        self.overlay._cached_adaptive_node = None
        self.overlay._last_ast_eval_time = 0.0
        node_ast = self.overlay.current_node
        self.assertIn("docstring", node_ast.items[8].label.lower())


class TestHighContrastThemesAndSoundscape(unittest.TestCase):
    """Tests WCAG AAA OLED Black, Solarized Dark themes, and procedural sound earcons."""

    def setUp(self):
        self.overlay = OverlayWindow()
        self.overlay.resize(1920, 1080)

    def tearDown(self):
        self.overlay.close()

    def test_theme_toggling_and_colors(self):
        self.assertEqual(self.overlay.current_theme, "CYBER_GLASS")

        # Toggle to OLED_BLACK
        t1 = self.overlay.toggle_theme()
        self.assertEqual(t1, "OLED_BLACK")
        self.assertEqual(self.overlay.current_theme, "OLED_BLACK")
        # Check pure black background brush
        self.assertEqual(self.overlay._brush_header_bg.color().red(), 0)
        self.assertEqual(self.overlay._brush_header_bg.color().green(), 0)
        self.assertEqual(self.overlay._brush_header_bg.color().blue(), 0)

        # Toggle to SOLARIZED_DARK
        t2 = self.overlay.toggle_theme()
        self.assertEqual(t2, "SOLARIZED_DARK")
        self.assertEqual(self.overlay.current_theme, "SOLARIZED_DARK")

        # Toggle back to CYBER_GLASS
        t3 = self.overlay.toggle_theme()
        self.assertEqual(t3, "CYBER_GLASS")

    def test_theme_color_sync_and_dwell_accent(self):
        self.overlay.set_theme("OLED_BLACK")
        self.assertEqual(self.overlay.theme_color, "#00FF66")

        self.overlay.set_theme("SOLARIZED_DARK")
        self.assertEqual(self.overlay.theme_color, "#268BD2")

        self.overlay.set_theme("CYBER_GLASS")
        self.assertEqual(self.overlay.theme_color, "#00F0FF")

    def test_sound_feedback_aliases_and_earcons(self):
        snd = SoundFeedbackManager(enabled=False)  # muted for headless runner
        self.assertEqual(snd._ALIASES.get("undo"), "back")
        self.assertEqual(snd._ALIASES.get("confirmation"), "click")
        self.assertEqual(snd._ALIASES.get("confirm"), "click")
        self.assertEqual(snd._ALIASES.get("navigation"), "mode")
        self.assertEqual(snd._ALIASES.get("nav"), "mode")
        self.assertEqual(snd._ALIASES.get("alert"), "pause")
        self.assertEqual(snd._ALIASES.get("error"), "pause")
        # Play should safely return without raising
        snd.play("nav")
        snd.play("confirm")
        snd.play("error")
        snd.play("undo")


class TestGuidedMiniTutorial(unittest.TestCase):
    """Tests the 3-step interactive guided mini-tutorial."""

    def setUp(self):
        self.overlay = OverlayWindow()
        self.overlay.resize(1920, 1080)

    def tearDown(self):
        self.overlay.close()

    def test_mini_tutorial_progression(self):
        self.overlay.start_mini_tutorial()
        self.assertTrue(self.overlay.show_tutorial_modal)
        self.assertEqual(self.overlay.tutorial_step, 1)

        # Step 1: Dwell simulation
        self.overlay.hovered_block = 0
        self.overlay._dwell_progress = 1.0
        self.overlay._update_mini_tutorial_gaze(0.5, 0.5)
        self.assertEqual(self.overlay.tutorial_step, 2)

        # Step 2: Gesture trigger simulation (e.g. MOUTH_CLICK or WINK)
        self.overlay.on_gesture_triggered("MOUTH_CLICK")
        self.assertEqual(self.overlay.tutorial_step, 3)

        # Step 3: Rest simulation (hovered_block = 4 for 1 second)
        self.overlay.hovered_block = 4
        self.overlay._tutorial_rest_start = time.time() - 1.5
        self.overlay._update_mini_tutorial_gaze(0.5, 0.5)
        self.assertEqual(self.overlay.tutorial_step, 4)

        # Close
        self.overlay.close_mini_tutorial()
        self.assertFalse(self.overlay.show_tutorial_modal)

    def test_tutorial_launch_from_help_modal(self):
        self.overlay.show_help_modal = True
        self.overlay._update_header_exit_rect()
        tut_rect = getattr(self.overlay, "help_modal_tutorial_rect", None)
        self.assertIsNotNone(tut_rect)
        self.assertTrue(tut_rect.isValid())

        # Gaze hover over tutorial button
        pt = tut_rect.center()
        self.overlay.on_gaze_updated(pt.x() / 1920.0, pt.y() / 1080.0)
        self.assertTrue(self.overlay.hovered_help_modal_tutorial)

        # Gesture click to activate tutorial
        self.overlay.on_gesture_triggered("MOUTH_CLICK")
        self.assertFalse(self.overlay.show_help_modal)
        self.assertTrue(self.overlay.show_tutorial_modal)
        self.assertEqual(self.overlay.tutorial_step, 1)


if __name__ == "__main__":
    unittest.main()
