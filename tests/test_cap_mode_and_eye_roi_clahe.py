"""Tests for Cap & Visor Robustness: Eye ROI CLAHE, Cap-Safe Anchors, and Micro-Gesture Gating."""

import os
import unittest
import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ideye.core.lighting_compensator import LightingCompensator
from ideye.core.gaze_estimator import GazeEstimator
from ideye.core.gesture_detector import GestureDetector
from ideye.core.settings_manager import SettingsManager


class DummyLandmark:
    def __init__(self, x: float, y: float, z: float = 0.0):
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)


class DummyFaceMesh:
    def __init__(self, landmarks_dict=None):
        self.landmark = [DummyLandmark(0.5, 0.5) for _ in range(478)]
        if landmarks_dict:
            for idx, (x, y) in landmarks_dict.items():
                self.landmark[idx] = DummyLandmark(x, y)


class TestCapModeAndEyeRoiClahe(unittest.TestCase):
    def test_lighting_compensator_activates_on_cap_visor_shadow(self):
        """
        In a well-lit room, the whole frame has high luminance (>= 90),
        but the eye region is in deep shadow under a cap visor (<= 50).
        Standard CLAHE wouldn't trigger, but Eye ROI CLAHE must activate!
        """
        compensator = LightingCompensator(enabled=True, low_light_threshold=80.0)
        # Create an 80x80 frame: background 120 (bright daylight)
        frame = np.full((80, 80, 3), 120, dtype=np.uint8)
        # Visor shadow over eye band (rows 20-40, cols 20-60): dark (45)
        frame[20:40, 20:60] = 45

        mean_global = float(np.mean(frame))
        self.assertGreaterEqual(mean_global, 80.0, "Global frame should be above standard low light threshold")

        result = compensator.process(frame)
        self.assertTrue(compensator.is_eye_shadow_active, "Eye ROI shadow should be detected and active")
        self.assertTrue(compensator.is_active)
        # Enhanced eye region should now have higher mean and contrast
        enhanced_eye_region = result[20:40, 20:60]
        self.assertGreater(float(np.mean(enhanced_eye_region)), 45.0)

    def test_lighting_compensator_cap_mode_boosts_sensitivity(self):
        compensator = LightingCompensator(enabled=True)
        self.assertFalse(compensator.cap_mode)
        compensator.set_cap_mode(True)
        self.assertTrue(compensator.cap_mode)

    def test_gaze_estimator_cap_safe_weights_zero_out_glabella(self):
        estimator = GazeEstimator()
        self.assertFalse(estimator.cap_mode)
        # Default weights should have glabella (index 3) weighted at 0.20
        self.assertEqual(estimator.head_anchor_weights[3], 0.20)

        # Enabling cap mode shifts to subnasal anchors
        estimator.set_cap_mode(True)
        self.assertTrue(estimator.cap_mode)
        self.assertEqual(estimator.head_anchor_weights[3], 0.0, "Glabella must have 0.0 weight in cap mode")
        self.assertGreater(estimator.head_anchor_weights[0], 0.30, "Nose tip must have primary weight in cap mode")
        self.assertGreater(estimator.head_anchor_weights[1], 0.30, "Columella must have primary weight in cap mode")

    def test_gaze_estimator_automatic_glabella_occlusion_fallback(self):
        """
        Even if cap_mode is False, if the cap visor occludes or collapses landmark 168 (glabella),
        _extract_head_pos must automatically engage cap-safe weights.
        """
        estimator = GazeEstimator()
        estimator.set_cap_mode(False)

        # Normal face: nose tip at y=0.55, glabella at y=0.40 (glabella distinctly above nose)
        normal_face = DummyFaceMesh({
            1: (0.50, 0.55),    # nose tip
            4: (0.50, 0.58),    # columella
            6: (0.50, 0.45),    # bridge
            168: (0.50, 0.40),  # glabella
            195: (0.50, 0.48),  # rhinion
            197: (0.50, 0.50),  # mid dorsum
        })
        x_norm, y_norm = estimator._extract_head_pos(normal_face.landmark)
        self.assertAlmostEqual(x_norm, 0.50, places=2)

        # Occluded face: visor pulled low down to the nose; glabella 168 is occluded / unpopulated (0.5, 0.5)
        occluded_face = DummyFaceMesh({
            1: (0.50, 0.55),    # nose tip
            4: (0.50, 0.58),    # columella
            6: (0.50, 0.53),    # bridge
            168: (0.50, 0.50),  # glabella unpopulated / occluded
            195: (0.50, 0.51),  # rhinion
            197: (0.50, 0.52),  # mid dorsum
        })
        x_occ, y_occ = estimator._extract_head_pos(occluded_face.landmark)
        self.assertTrue(np.isfinite(x_occ) and np.isfinite(y_occ))
        self.assertAlmostEqual(x_occ, 0.50, places=2)
        self.assertGreater(y_occ, 0.54)

    def test_gesture_detector_cap_mode_suppresses_brow_raise(self):
        detector = GestureDetector()
        detector.set_cap_mode(False)

        # Face with raised eyebrows
        raised_face = DummyFaceMesh({
            33: (0.35, 0.50),
            263: (0.65, 0.50),
            65: (0.40, 0.35),
            105: (0.45, 0.35),
            295: (0.55, 0.35),
            334: (0.60, 0.35),
        })
        brow_val = detector.compute_brow_raise(raised_face.landmark)
        self.assertGreater(brow_val, 0.0)

        # In cap mode, brow raise must return 0.0 to prevent visor movements from triggering clicks
        detector.set_cap_mode(True)
        self.assertEqual(detector.compute_brow_raise(raised_face.landmark), 0.0)

        # But mouth click (MAR) must still function normally!
        open_mouth_face = DummyFaceMesh({
            13: (0.50, 0.60),
            14: (0.50, 0.80),
            78: (0.40, 0.70),
            308: (0.60, 0.70),
        })
        mar = detector.compute_mar(open_mouth_face.landmark)
        self.assertGreater(mar, 0.40, "MAR mouth detection must remain fully functional in cap mode")

    def test_settings_manager_has_cap_mode(self):
        settings = SettingsManager()
        data = settings.as_dict()
        self.assertIn("cap_mode_enabled", data)
        self.assertIsInstance(data["cap_mode_enabled"], bool)


if __name__ == "__main__":
    unittest.main()
