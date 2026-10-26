"""Phase 10.1: adaptive CLAHE lighting and Sniper Zoom Lens."""

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np

from eyede.core.lighting_compensator import LightingCompensator
from eyede.ui.sniper_lens import SniperLens


class TestLightingCompensator(unittest.TestCase):
    def test_dark_frame_activates_clahe_and_improves_contrast(self):
        compensator = LightingCompensator(enabled=True)
        frame = np.full((80, 80, 3), 35, dtype=np.uint8)
        frame[20:60, 20:60] = 65
        original = frame.copy()
        result = compensator.process(frame)
        self.assertTrue(compensator.is_low_light_active)
        self.assertLess(compensator.current_luma, 85.0)
        self.assertGreater(float(np.mean(result)), float(np.mean(original)))
        self.assertGreater(float(np.std(result)), float(np.std(original)))

    def test_bright_frame_is_zero_cost_bypass(self):
        compensator = LightingCompensator(enabled=True)
        frame = np.full((40, 40, 3), 140, dtype=np.uint8)
        frame[10:30, 10:30] = 180
        original = frame.copy()
        result = compensator.process(frame)
        self.assertFalse(compensator.is_low_light_active)
        self.assertGreaterEqual(compensator.current_luma, 85.0)
        np.testing.assert_array_equal(result, original)

    def test_disabled_compensator_bypasses(self):
        compensator = LightingCompensator(enabled=False)
        frame = np.full((20, 20, 3), 20, dtype=np.uint8)
        result = compensator.process(frame)
        np.testing.assert_array_equal(result, frame)
        self.assertFalse(compensator.is_low_light_active)


class TestSniperLens(unittest.TestCase):
    def test_micro_fixation_activates_and_slowmo_multiplier(self):
        lens = SniperLens()
        self.assertFalse(lens.update_gaze(500, 500, now=0.0))
        self.assertTrue(lens.update_gaze(510, 505, now=0.6))
        self.assertTrue(lens.active)
        self.assertAlmostEqual(lens.movement_multiplier, 0.28)

    def test_mouth_click_and_left_wink_cancel(self):
        lens = SniperLens()
        lens.activate(500, 500)
        self.assertTrue(lens.on_gesture("MOUTH_CLICK"))
        self.assertFalse(lens.active)
        lens.activate(500, 500)
        self.assertTrue(lens.on_gesture("LEFT_WINK"))
        self.assertFalse(lens.active)

    def test_saccade_breakout_cancels(self):
        lens = SniperLens()
        lens.activate(500, 500)
        self.assertFalse(lens.update_gaze(700, 500, now=1.0))
        self.assertFalse(lens.active)

    def test_toggle_uses_explicit_target(self):
        lens = SniperLens()
        self.assertTrue(lens.toggle(640, 480))
        self.assertEqual(lens.target, (640.0, 480.0))
        self.assertFalse(lens.toggle())


if __name__ == "__main__":
    unittest.main()
