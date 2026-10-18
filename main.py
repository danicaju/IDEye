"""
Root launcher for IDEye
Allows running `python main.py` directly from workspace root: c:\\Users\\danic\\Desktop\\IDEye
"""

import sys
import os

# Ensure eyede package is in sys.path
_ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
_EYEDE_DIR = os.path.join(_ROOT_DIR, "eyede")

for p in (_ROOT_DIR, _EYEDE_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

from eyede.main import main

if __name__ == "__main__":
    main()
