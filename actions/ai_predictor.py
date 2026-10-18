"""
Root wrapper for eyede.actions.ai_predictor.
"""
import sys
import os

_EYEDE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "eyede")
if _EYEDE_DIR not in sys.path:
    sys.path.insert(0, _EYEDE_DIR)

from eyede.actions.ai_predictor import *
