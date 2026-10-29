"""
IDEye Core Package - Vision, Tracking and Gestures
"""
try:
    from ideye.core.gesture_detector import GestureDetector, GestureState
    from ideye.core.gaze_estimator import GazeEstimator
    from ideye.core.camera_tracker import CameraTracker
    from ideye.core.hotkey_manager import GlobalHotkeyManager
except ImportError:
    from .gesture_detector import GestureDetector, GestureState
    from .gaze_estimator import GazeEstimator
    from .camera_tracker import CameraTracker
    from .hotkey_manager import GlobalHotkeyManager

__all__ = ["GestureDetector", "GestureState", "GazeEstimator", "CameraTracker", "GlobalHotkeyManager"]

