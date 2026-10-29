"""
Root core package forwarder to ideye.core.
"""
import sys
import os

_IDEYE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ideye")
if _IDEYE_DIR not in sys.path:
    sys.path.insert(0, _IDEYE_DIR)

from ideye.core.camera_tracker import *
from ideye.core.gaze_estimator import *
from ideye.core.gesture_detector import *
from ideye.core.hotkey_manager import *
