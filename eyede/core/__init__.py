"""
EyeDE Core Package - Vision, Tracking and Gestures
"""
try:
    from eyede.core.gesture_detector import GestureDetector, GestureState
    from eyede.core.gaze_estimator import GazeEstimator
    from eyede.core.camera_tracker import CameraTracker
except ImportError:
    from .gesture_detector import GestureDetector, GestureState
    from .gaze_estimator import GazeEstimator
    from .camera_tracker import CameraTracker

__all__ = ["GestureDetector", "GestureState", "GazeEstimator", "CameraTracker"]
