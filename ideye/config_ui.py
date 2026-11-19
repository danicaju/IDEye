"""Theme colors, overlay and calibration constants."""

import os
from typing import Dict, Any, List, Optional, Tuple

from ideye.config_vision import *  # noqa: F401,F403
from ideye.config_gestures import *  # noqa: F401,F403

# ==============================================================================
# Visual Theme & Colors (BGR for OpenCV)
# ==============================================================================
COLOR_BG: tuple = (22, 24, 28)
COLOR_GRID_BORDER: tuple = (50, 55, 65)
COLOR_BLOCK_DEFAULT: tuple = (32, 35, 42)
COLOR_BLOCK_HOVER: tuple = (85, 70, 35)       # Amber-tinted slate
COLOR_BLOCK_CLICK: tuple = (40, 230, 110)     # Vibrant neon green
COLOR_TEXT: tuple = (220, 225, 230)
COLOR_TEXT_DIM: tuple = (140, 145, 155)
COLOR_TEXT_HOVER: tuple = (255, 255, 255)
COLOR_TEXT_CLICK: tuple = (10, 30, 10)
COLOR_POINTER: tuple = (255, 190, 20)         # Bright cyan/amber
COLOR_POINTER_OUTLINE: tuple = (255, 255, 255)
COLOR_WARNING: tuple = (40, 50, 220)          # Red for face loss
COLOR_BAR_BG: tuple = (40, 42, 50)
COLOR_BAR_FILL: tuple = (220, 150, 30)
COLOR_BAR_READY: tuple = (40, 230, 110)
COLOR_BAR_THRESHOLD: tuple = (0, 70, 255)
COLOR_THRESHOLD_LINE: tuple = (0, 70, 255)
COLOR_PAUSED_BORDER: tuple = (0, 140, 255)

# Mini-feed overlay sizing (compact, non-blocking PiP)
MINI_FEED_WIDTH: int = 240
MINI_FEED_HEIGHT: int = 150
MINI_FEED_MARGIN: int = 16

# ==============================================================================
# Phase 2: PyQt6 Overlay, Debug & 5-Point Calibration Parameters
# ==============================================================================
# Overlay HUD opacities (High-transparency glassmorphic design)
OVERLAY_OPACITY_ACTIVE: float = 0.22
OVERLAY_OPACITY_READING: float = 0.08

# RGBA colors for PyQt6 Overlay (0-255)
OVERLAY_COLOR_BG = (15, 20, 28, 120)
OVERLAY_COLOR_BORDER = (56, 189, 248, 180)
OVERLAY_BORDER_WIDTH: int = 2

OVERLAY_COLOR_HOVER = (28, 44, 72, 235)
OVERLAY_HOVER_BORDER_COLOR = (255, 200, 55, 255)
OVERLAY_HOVER_BORDER_WIDTH: int = 3

OVERLAY_COLOR_CLICK = (25, 180, 85, 245)
OVERLAY_CLICK_BORDER_COLOR = (110, 255, 160, 255)

OVERLAY_COLOR_REST = (12, 16, 22, 110)
OVERLAY_REST_BORDER_COLOR = (16, 185, 129, 200)

OVERLAY_POINTER_COLOR = (255, 195, 40, 230)
OVERLAY_POINTER_OUTLINE = (255, 255, 255, 245)
OVERLAY_POINTER_RADIUS: int = 13
OVERLAY_POINTER_GLOW_RADIUS: int = 22

OVERLAY_TEXT_COLOR = (245, 248, 252, 250)
OVERLAY_TEXT_HINT_COLOR = (160, 175, 195, 220)
OVERLAY_TEXT_HOVER_COLOR = (255, 255, 255, 255)

# Category Accent Colors (RGB tuples 0-255)
COLOR_CAT_FLOW = (6, 182, 212)        # Cyan
COLOR_CAT_STRUCT = (245, 158, 11)     # Amber / Gold
COLOR_CAT_OPERATORS = (168, 85, 247)  # Purple
COLOR_CAT_NAV = (59, 130, 246)        # Blue
COLOR_CAT_PAUSE = (16, 185, 129)      # Emerald
COLOR_CAT_BACK = (236, 72, 153)       # Rose / Magenta
COLOR_CAT_EDIT = (99, 102, 241)       # Indigo
COLOR_CAT_AI = (217, 70, 239)         # Fuchsia
COLOR_CAT_EXIT = (239, 68, 68)        # Coral / Red

# 5-Point Calibration targets (normalized coordinates)
CALIBRATION_POINTS: List[Dict[str, Any]] = [
    {"id": "CENTER", "name": "Centro", "screen": (0.5, 0.5)},
    {"id": "TOP_LEFT", "name": "Arriba-Izquierda", "screen": (0.1, 0.1)},
    {"id": "TOP_RIGHT", "name": "Arriba-Derecha", "screen": (0.9, 0.1)},
    {"id": "BOTTOM_LEFT", "name": "Abajo-Izquierda", "screen": (0.1, 0.9)},
    {"id": "BOTTOM_RIGHT", "name": "Abajo-Derecha", "screen": (0.9, 0.9)},
]
CALIBRATION_PROFILE_PATH: str = "calibration_profile.json"
CALIBRATION_SAMPLES_PER_POINT: int = 15
CALIBRATION_SAMPLE_DELAY_SEC: float = 0.02

# Debug widget sizing & overlay right docking margin
DEBUG_WINDOW_WIDTH: int = 340
DEBUG_WINDOW_HEIGHT: int = 740
DEBUG_FEED_WIDTH: int = 300
DEBUG_FEED_HEIGHT: int = 170
OVERLAY_GRID_RIGHT_MARGIN: int = 364  # Clears space on screen so 3x3 grid never collides with debug widget

# ==============================================================================
