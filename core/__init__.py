"""
Root core package forwarder to eyede.core.
"""
import sys
import os

_EYEDE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "eyede")
if _EYEDE_DIR not in sys.path:
    sys.path.insert(0, _EYEDE_DIR)

from eyede.core.camera_tracker import *
from eyede.core.gaze_estimator import *
from eyede.core.gesture_detector import *
from eyede.core.hotkey_manager import *
