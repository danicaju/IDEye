"""
Root launcher for IDEye
Allows running `python main.py` directly from workspace root: c:\\Users\\danic\\Desktop\\IDEye
"""

import sys
import os

# Ensure ideye package is in sys.path
_ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
_IDEYE_DIR = os.path.join(_ROOT_DIR, "ideye")

for p in (_ROOT_DIR, _IDEYE_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

from ideye.main import main

if __name__ == "__main__":
    main()
