"""
Tests for Zero-Dwell Midas Elimination & Intentional Grid Selection:
Verifies that looking at / hovering over boxes in the 3x3 HUD grid never auto-clicks
or activates actions by default. Intentional selection requires facial gestures (mouth click MAR)
or physical input according to IDEye design.
"""

import time
import unittest
from PyQt6.QtWidgets import QApplication

import ideye.config as config
from ideye.core.settings_manager import SettingsManager
from ideye.ui.overlay_window import OverlayWindow


class TestZeroDwellGridIntentionalSelection(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.overlay = OverlayWindow()
        self.overlay.resize(1920, 1080)

    def tearDown(self):
        self.overlay.close()

    def test_default_config_and_overlay_zero_dwell(self):
        """By default, DWELL_CLICK_ENABLED is False and adaptive dwell does not auto-click."""
        self.assertFalse(getattr(config, "DWELL_CLICK_ENABLED", True))
        self.assertFalse(self.overlay.dwell_click_enabled)
        self.assertTrue(self.overlay.adaptive_dwell_enabled)

    def test_settings_manager_factory_defaults(self):
        """SettingsManager defaults must keep dwell_click_enabled disabled."""
        sm = SettingsManager()
        self.assertFalse(sm.get("dwell_click_enabled"))

    def test_hover_and_extended_dwell_never_clicks_or_navigates(self):
        """
        Critical bug test:
        Staring at block 0 (which contains a SUBMENU action) past nominal dwell (0.30s)
        charges the fixation indicator (_dwell_fired = True), but NEVER executes the action.
        The current node MUST remain ROOT and NO activation signals may be emitted.
        """
        actions_executed = []
        blocks_activated = []
        self.overlay.action_executed.connect(lambda aid, desc: actions_executed.append((aid, desc)))
        self.overlay.block_activated.connect(lambda bidx, aid: blocks_activated.append((bidx, aid)))

        self.assertEqual(self.overlay.current_node_id, "ROOT")

        # Simulate gaze hovering on block 0
        self.overlay._update_adaptive_dwell(0)
        # Advance dwell start time by 1.5s (far beyond 0.30s or 0.70s uncalibrated threshold)
        self.overlay._dwell_start_time = time.time() - 1.5
        self.overlay._update_adaptive_dwell(0)

        # Dwell fixation completed
        self.assertTrue(self.overlay._dwell_fired)
        self.assertAlmostEqual(self.overlay._dwell_progress, 1.0)

        # But ZERO actions or navigations occurred
        self.assertEqual(self.overlay.current_node_id, "ROOT", "Looking at a box must NEVER enter a submenu by dwell!")
        self.assertEqual(actions_executed, [], "action_executed signal must NOT fire on hover/dwell!")
        self.assertEqual(blocks_activated, [], "block_activated signal must NOT fire on hover/dwell!")

    def test_hover_over_all_blocks_does_not_execute_actions(self):
        """None of the 9 blocks trigger actions purely from gaze hover/dwell."""
        blocks_activated = []
        self.overlay.block_activated.connect(lambda bidx, aid: blocks_activated.append((bidx, aid)))

        for block_idx in range(9):
            self.overlay._update_adaptive_dwell(block_idx)
            self.overlay._dwell_start_time = time.time() - 2.0
            self.overlay._update_adaptive_dwell(block_idx)

        self.assertEqual(blocks_activated, [], "Gazing across all 9 blocks must not activate any actions!")
        self.assertEqual(self.overlay.current_node_id, "ROOT")

    def test_intentional_mouth_click_activates_hovered_block(self):
        """
        Intentional selection via mouth click (MAR) confirms the hovered cell
        and executes the expected action.
        """
        blocks_activated = []
        self.overlay.block_activated.connect(lambda bidx, aid: blocks_activated.append((bidx, aid)))

        self.overlay.hovered_block = 0
        # Gaze rests on block 0
        self.overlay._update_adaptive_dwell(0)

        # User deliberately opens mouth -> MOUTH_CLICK gesture arrives
        self.overlay.on_gesture_triggered("MOUTH_CLICK")

        # Now block 0 is activated and navigates to the FLOW submenu
        self.assertIn(self.overlay.current_node_id, ("FLOW", "CONDITIONAL_BRANCHES"))
        self.assertEqual(len(blocks_activated), 1)
        self.assertEqual(blocks_activated[0][0], 0)

    def test_opt_in_dwell_click_executes_action_when_enabled(self):
        """
        When dwell_click_enabled is explicitly set to True (accessibility fallback),
        dwelling past target_dwell DOES execute the action.
        """
        self.overlay.set_dwell_click_enabled(True)
        self.overlay.mar_calibrated = True
        self.assertTrue(self.overlay.dwell_click_enabled)

        self.assertEqual(self.overlay.current_node_id, "ROOT")

        self.overlay._update_adaptive_dwell(0)
        self.overlay._dwell_start_time = time.time() - 0.5
        self.overlay._update_adaptive_dwell(0)

        # Action executed by dwell click and navigated to FLOW (which resets dwell for new node)
        self.assertIn(self.overlay.current_node_id, ("FLOW", "CONDITIONAL_BRANCHES"))

    def test_dwell_click_suppressed_when_tutorial_modal_is_active(self):
        """Even if dwell_click_enabled is True, tutorial modal absorbs clicks without executing underlying actions."""
        self.overlay.set_dwell_click_enabled(True)
        self.overlay.mar_calibrated = True
        self.overlay.start_mini_tutorial()
        self.assertTrue(self.overlay.show_tutorial_modal)

        self.overlay.hovered_block = 0
        self.overlay._update_adaptive_dwell(0)
        self.overlay._dwell_start_time = time.time() - 1.0
        self.overlay._update_adaptive_dwell(0)
        self.overlay._update_mini_tutorial_gaze(0.1, 0.1)

        # Tutorial step advances to step 2 upon dwell fixation
        self.assertEqual(self.overlay.tutorial_step, 2)
        # But underlying menu did NOT navigate
        self.assertEqual(self.overlay.current_node_id, "ROOT")

    def test_tutorial_step1_and_step2_interaction_flow(self):
        """
        Step 1 requires gaze dwell fixation to charge the ring.
        Step 2 requires intentional mouth click or Enter to confirm.
        Neither step triggers accidental underlying grid actions.
        """
        self.overlay.start_mini_tutorial()
        self.assertEqual(self.overlay.tutorial_step, 1)

        # Step 1: user gazes at cell 0
        self.overlay.hovered_block = 0
        self.overlay._update_adaptive_dwell(0)
        self.overlay._dwell_start_time = time.time() - 0.5
        self.overlay._update_adaptive_dwell(0)
        self.overlay._update_mini_tutorial_gaze(0.1, 0.1)

        # Advances to Step 2
        self.assertEqual(self.overlay.tutorial_step, 2)
        self.assertEqual(self.overlay.current_node_id, "ROOT")

        # Step 2: user opens mouth -> MOUTH_CLICK
        self.overlay.on_gesture_triggered("MOUTH_CLICK")
        self.assertEqual(self.overlay.tutorial_step, 3)
        self.assertEqual(self.overlay.current_node_id, "ROOT")

    def test_navigating_to_new_menu_resets_dwell_state(self):
        """Navigating between menus resets the dwell accumulator so new items are not accidentally fired."""
        self.overlay._dwell_block = 0
        self.overlay._dwell_progress = 0.8
        self.overlay._dwell_fired = True

        self.overlay.navigate_to("FLOW")
        self.assertEqual(self.overlay._dwell_progress, 0.0)
        self.assertFalse(self.overlay._dwell_fired)


if __name__ == "__main__":
    unittest.main()
