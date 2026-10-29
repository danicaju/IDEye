"""
Root wrapper for ideye.actions.context_reader.
"""
import sys
import os

_IDEYE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ideye")
if _IDEYE_DIR not in sys.path:
    sys.path.insert(0, _IDEYE_DIR)

from ideye.actions.context_reader import *
