"""Phase 7.6: rigid head anchor, static pinning, iris median and dynamic fusion."""

import math
import random
import unittest

from eyede.core.gaze_estimator import GazeEstimator


class FakeFace:
    def __init__(self):
        self.landmark = [(0.5, 0.5)] * 478

    def set(self, idx, x, y):
        self.landmark[idx] = (float(x), float(y))


def make_face(noise=0.0, iris_shift=0.0):
    face = FakeFace()
    rng = random.Random(7)
    head_points = {
        1: (0.50, 0.50),
        4: (0.50, 0.49),
        6: (0.50, 0.48),
        168: (0.50, 0.47),
        195: (0.49, 0.49),
        197: (0.51, 0.49),
    }
    for idx, (x, y) in head_points.items():
        face.set(idx, x + rng.uniform(-noise, noise), y + rng.uniform(-noise, noise))

    left_orbital = {
        33: (0.60, 0.40),
        133: (0.65, 0.40),
        159: (0.625, 0.385),
        145: (0.625, 0.415),
        158: (0.62, 0.39),
        153: (0.63, 0.41),
    }
    right_orbital = {
        362: (0.40, 0.40),
        263: (0.35, 0.40),
        386: (0.375, 0.385),
        374: (0.375, 0.415),
        385: (0.38, 0.39),
        380: (0.37, 0.41),
    }
    for mapping, base_x in ((left_orbital, 0.625), (right_orbital, 0.375)):
        for idx, (x, y) in mapping.items():
            face.set(idx, x + rng.uniform(-noise, noise), y + rng.uniform(-noise, noise))
        for i, idx in enumerate(range(468, 473) if base_x > 0.5 else range(473, 478)):
            face.set(
                idx,
                base_x + iris_shift + rng.uniform(-noise, noise),
                0.40 + rng.uniform(-noise, noise),
            )
    return face


class TestHeadAnchor(unittest.TestCase):
    def test_six_point_centroid_uses_rigid_weights(self):
        est = GazeEstimator()
        face = FakeFace()
        face.set(1, 0.10, 0.10)
        face.set(4, 0.10, 0.10)
        face.set(6, 0.70, 0.70)
        face.set(168, 0.70, 0.70)
        face.set(195, 0.70, 0.70)
        face.set(197, 0.70, 0.70)
        x, y = est._extract_head_pos(face.landmark)
        self.assertAlmostEqual(x, 0.58, places=5)
        self.assertAlmostEqual(y, 0.58, places=5)

    def test_falls_back_to_nose_for_sparse_synthetic_faces(self):
        est = GazeEstimator()
        face = FakeFace()
        face.set(1, 0.58, 0.42)
        x, y = est._extract_head_pos(face.landmark)
        self.assertEqual((x, y), (0.58, 0.42))


class TestStaticPinning(unittest.TestCase):
    def test_noisy_rest_is_exactly_constant(self):
        est = GazeEstimator(tracking_mode="HEAD_PRIMARY")
        face = make_face()
        est.calibrate_center(face)
        outputs = []
        for _ in range(24):
            noisy = make_face(noise=0.002)
            gx, gy, detected, _ = est.estimate(noisy, timestamp=1.0 + len(outputs) * 0.016)
            self.assertTrue(detected)
            outputs.append((gx, gy))
        xs = [p[0] for p in outputs]
        ys = [p[1] for p in outputs]
        self.assertEqual(max(xs) - min(xs), 0.0)
        self.assertEqual(max(ys) - min(ys), 0.0)

    def test_breakout_unlocks_intentional_movement(self):
        est = GazeEstimator()
        est._pinned_pos = (0.5, 0.5)
        est._is_pinned = True
        x, y = est._apply_static_pinning(0.53, 0.5)
        self.assertFalse(est._is_pinned)
        self.assertNotEqual((x, y), (0.5, 0.5))

    def test_relocks_after_quiet_frames(self):
        est = GazeEstimator()
        est._pinned_pos = (0.5, 0.5)
        est._is_pinned = False
        est._pinned_pos = None
        est._static_last_filtered = (0.51, 0.5)
        for _ in range(est.static_lock_frames):
            est._apply_static_pinning(0.5101, 0.5)
        self.assertTrue(est._is_pinned)


class TestPureIrisMedian(unittest.TestCase):
    def test_single_corrupt_frame_is_rejected(self):
        est = GazeEstimator(tracking_mode="PURE_IRIS")
        stable = make_face()
        for _ in range(5):
            est._extract_iris_ratio(stable.landmark)
        base = (est.last_valid_iris_x, est.last_valid_iris_y)
        spike = make_face(iris_shift=0.08)
        gx, gy = est._extract_iris_ratio(spike.landmark)
        self.assertLess(abs(gx - base[0]), 0.02, "median must reject a one-frame iris spike")
        self.assertLess(abs(gy - base[1]), 0.02)

    def test_missing_orbital_points_do_not_crash(self):
        est = GazeEstimator(tracking_mode="PURE_IRIS")
        face = make_face()
        for idx in (158, 153, 385, 380):
            face.set(idx, 0.5, 0.5)
        gx, gy = est._extract_iris_ratio(face.landmark)
        self.assertTrue(math.isfinite(gx) and math.isfinite(gy))


class TestDynamicHybridFusion(unittest.TestCase):
    def test_iris_weight_drops_at_rest_and_rises_on_saccade(self):
        est = GazeEstimator(tracking_mode="HYBRID")
        for _ in range(12):
            est._compute_effective_iris_weight(0.5, 0.5)
        rest_weight = est._effective_iris_weight
        self.assertLess(rest_weight, 0.12)
        for _ in range(4):
            est._compute_effective_iris_weight(0.8, 0.5)
        self.assertGreater(est._effective_iris_weight, rest_weight)

    def test_dynamic_fusion_reduces_iris_noise_at_rest(self):
        est = GazeEstimator(tracking_mode="HYBRID")
        est._effective_iris_weight = est.hybrid_iris_weight_rest
        est._dynamic_fusion_active = True
        try:
            dx, _ = est._compute_combined_deltas(0.05, 0.0, 0.05, 0.0)
        finally:
            est._dynamic_fusion_active = False
        self.assertAlmostEqual(dx, 0.05, delta=0.02)


if __name__ == "__main__":
    unittest.main()
