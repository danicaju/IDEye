"""
Root wrapper for ideye.config so `import config` works from root workspace.
"""
import sys
import os

_IDEYE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ideye")
if _IDEYE_DIR not in sys.path:
    sys.path.insert(0, _IDEYE_DIR)

from ideye.config import *
