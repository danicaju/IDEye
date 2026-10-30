"""Center-anchored dual-source calibration reach tests."""

import unittest

from ideye.core.gaze_estimator import GazeEstimator


class TestCalibrationReach(unittest.TestCase):
    def test_asymmetric_raw_center_still_reaches_both_edges(self):
        bounds = (0.4921386629343033, 0.5616300523281098, 0.5917360901832581, 0.6238076686859131)
        center = (0.5206427991390229, 0.612011331319809)
        left = GazeEstimator._map_dual_source(
            bounds[0], center[1], bounds, None, None, center=center
        )
        middle = GazeEstimator._map_dual_source(
            center[0], center[1], bounds, None, None, center=center
        )
        right = GazeEstimator._map_dual_source(
            bounds[1], center[1], bounds, None, None, center=center
        )
        self.assertAlmostEqual(left[0], 0.0, places=5)
        self.assertAlmostEqual(middle[0], 0.5, places=5)
        self.assertAlmostEqual(right[0], 1.0, places=5)

    def test_vertical_center_anchors_top_and_bottom(self):
        bounds = (0.0, 1.0, 0.2, 0.7)
        center = (0.5, 0.5)
        top = GazeEstimator._map_dual_source(0.5, 0.2, bounds, None, None, center=center)
        middle = GazeEstimator._map_dual_source(0.5, 0.5, bounds, None, None, center=center)
        bottom = GazeEstimator._map_dual_source(0.5, 0.7, bounds, None, None, center=center)
        self.assertAlmostEqual(top[1], 0.0, places=5)
        self.assertAlmostEqual(middle[1], 0.5, places=5)
        self.assertAlmostEqual(bottom[1], 1.0, places=5)


if __name__ == "__main__":
    unittest.main()
