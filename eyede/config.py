"""
IDEye - Configuration Module (Phase 1)
Central configuration for camera tracking, hybrid gaze estimation,
gesture trigger thresholds, and UI display parameters.
"""

import os
from typing import Dict, Any, List, Optional

# ==============================================================================
# Camera & Video Capture Settings
# ==============================================================================
CAMERA_INDEX: int = 0
FRAME_WIDTH: int = 1280
FRAME_HEIGHT: int = 720
FPS: int = 30
MIRROR_CAMERA: bool = True  # Horizontal flip for intuitive mirror tracking

# ==============================================================================
# MediaPipe FaceMesh Parameters
# ==============================================================================
MAX_NUM_FACES: int = 1
REFINE_LANDMARKS: bool = True  # Required for 478 landmarks (iris 468-477)
MIN_DETECTION_CONFIDENCE: float = 0.5
MIN_TRACKING_CONFIDENCE: float = 0.5

# ==============================================================================
# Landmark Indices (MediaPipe 478 Refined Mesh)
# ==============================================================================
# Nose tip anchor
LANDMARK_NOSE_TIP: int = 1

# Iris centers
LANDMARK_IRIS_LEFT_CENTER: int = 468
LANDMARK_IRIS_RIGHT_CENTER: int = 473

# Eye corners for relative iris position
# Left eye (subject's left / viewer's right when mirrored)
LANDMARK_LEFT_EYE_INNER: int = 133
LANDMARK_LEFT_EYE_OUTER: int = 33
LANDMARK_LEFT_EYE_TOP: int = 159
LANDMARK_LEFT_EYE_BOTTOM: int = 145

# Right eye (subject's right / viewer's left when mirrored)
LANDMARK_RIGHT_EYE_INNER: int = 362
LANDMARK_RIGHT_EYE_OUTER: int = 263
LANDMARK_RIGHT_EYE_TOP: int = 386
LANDMARK_RIGHT_EYE_BOTTOM: int = 374

# Inner lips landmarks for MAR (Mouth Aspect Ratio)
# 13: Upper lip inner center, 14: Lower lip inner center
# 78: Left mouth corner, 308: Right mouth corner
LANDMARK_MOUTH_LIP_TOP: int = 13
LANDMARK_MOUTH_LIP_BOTTOM: int = 14
LANDMARK_MOUTH_CORNER_LEFT: int = 78
LANDMARK_MOUTH_CORNER_RIGHT: int = 308

# ==============================================================================
# Gaze Tracking Modes & Weights
# ==============================================================================
TRACKING_MODE_PURE_IRIS: str = "PURE_IRIS"
TRACKING_MODE_HYBRID: str = "HYBRID"
TRACKING_MODE_HEAD_PRIMARY: str = "HEAD_PRIMARY"
DEFAULT_TRACKING_MODE: str = TRACKING_MODE_HEAD_PRIMARY

# Default balance for HYBRID mode: 60% head/nose vector, 40% iris vector
HEAD_WEIGHT: float = 0.60
IRIS_WEIGHT: float = 0.40

# Gain / sensitivity multipliers
# Vertical sensitivity is scaled higher (~2.4x) to account for human ocular ergonomics
# where vertical head pitch and eye elevation range is ~30% of horizontal range.
DEFAULT_HEAD_SENSITIVITY_X: float = 2.6
DEFAULT_HEAD_SENSITIVITY_Y: float = 6.8
DEFAULT_IRIS_SENSITIVITY_X: float = 3.6
DEFAULT_IRIS_SENSITIVITY_Y: float = 8.5

# Anti-Jitter Filtering (One Euro Filter + Fixation Deadzone)
ONE_EURO_MIN_CUTOFF: float = 0.55   # Low-speed cutoff (Hz) - eliminates resting jitter
ONE_EURO_BETA: float = 0.28        # Speed coefficient - eliminates saccadic lag
ONE_EURO_D_CUTOFF: float = 1.0     # Derivative cutoff (Hz)
FIXATION_DEADZONE: float = 0.022   # Deadzone radius in normalized coords for rock-solid resting

# Ergonomic non-linear reach curves
VERTICAL_MULTIPLIER: float = 2.4       # Ergonomic independent vertical gain multiplier
VERTICAL_EXPANSION_GAIN: float = 1.8   # Ergonomic non-linear vertical curve multiplier
HORIZONTAL_MULTIPLIER: float = 1.45    # Ergonomic independent horizontal gain multiplier
HORIZONTAL_EXPANSION_GAIN: float = 1.75 # Non-linear horizontal edge expansion for border reach
VOR_COMPENSATION_FACTOR: float = 0.40  # Vestibulo-Ocular Reflex decoupling factor for HYBRID mode

# Smoothing factor for Exponential Moving Average (EMA)
# Higher = more responsive, lower = smoother (less jitter)
EMA_ALPHA: float = 0.22

# Blink Detection (EAR & Eye Height)
# Below this vertical opening ratio, eye is considered closed (blink suppression)
EAR_BLINK_THRESHOLD: float = 0.14
MIN_EYE_HEIGHT_RATIO: float = 0.008

# Nominal interocular distance (between outer canthi landmarks 33 & 263)
# Used for distance-adaptive gain/sensitivity calibration
NOMINAL_INTEROCULAR_DIST: float = 0.28

# ==============================================================================
# Gesture Detector (MAR Trigger) Parameters
# ==============================================================================
# Mouth Aspect Ratio threshold for detecting slightly open mouth
MAR_THRESHOLD: float = 0.45
# Hysteresis: mouth must close below this to re-arm the trigger
MAR_RELEASE_THRESHOLD: float = 0.35
# Duration (seconds) mouth must stay open continuously before firing CLICK
CLICK_HOLD_TIME_SEC: float = 0.15
# Cooldown duration (seconds) after a successful click before another can occur
CLICK_COOLDOWN_SEC: float = 0.35

# ==============================================================================
# Macro-Bloques Grid Layout (3x3 Matrix)
# ==============================================================================
GRID_ROWS: int = 3
GRID_COLS: int = 3
HEADER_HEIGHT: int = 38

MACRO_BLOCKS: List[Dict[str, Any]] = [
    {"index": 0, "key": "1", "label": "1: IF / ELSE", "action": "INSERT_IF_ELSE", "hint": "Control Flow"},
    {"index": 1, "key": "2", "label": "2: LOOP", "action": "INSERT_LOOP", "hint": "for / while"},
    {"index": 2, "key": "3", "label": "3: DEF / FUNC", "action": "INSERT_FUNC", "hint": "def function():"},
    {"index": 3, "key": "4", "label": "4: VARS", "action": "INSERT_VARS", "hint": "x = value"},
    {"index": 4, "key": "5", "label": "5: PAUSA / MODO LECTURA", "action": "PAUSE_RESUME", "hint": "Rest Zone"},
    {"index": 5, "key": "6", "label": "6: OPERADORES", "action": "INSERT_OPERATORS", "hint": "== != + - * /"},
    {"index": 6, "key": "7", "label": "7: BORRAR", "action": "ACTION_BACKSPACE", "hint": "Delete / Undo"},
    {"index": 7, "key": "8", "label": "8: ENTER / TAB", "action": "ACTION_ENTER_TAB", "hint": "Newline / Indent"},
    {"index": 8, "key": "9", "label": "9: SALIR", "action": "ACTION_EXIT", "hint": "Close Program"},
]

# Visual feedback duration for click highlight (seconds)
CLICK_FLASH_DURATION_SEC: float = 0.40

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

# Debug widget sizing
DEBUG_WINDOW_WIDTH: int = 340
DEBUG_WINDOW_HEIGHT: int = 640
DEBUG_FEED_WIDTH: int = 300
DEBUG_FEED_HEIGHT: int = 170

# ==============================================================================
# Phase 4: Live AST Context Reader & AI Code Predictor Settings
# ==============================================================================
# Workspace and active file context
DEFAULT_WORKSPACE_DIR: str = os.getcwd()
ACTIVE_FILE_PATH: Optional[str] = None
AUTO_DETECT_RECENT_FILE: bool = True
MAX_LOCAL_SYMBOLS: int = 12
CONTEXT_MAX_LINES: int = 40
PREDICTOR_MAX_CONTEXT_LINES: int = 30

# LLM Provider Configuration
LLM_PROVIDER: str = "ollama"  # "ollama", "openai", "groq", "gemini"
LLM_ENDPOINT: str = "http://localhost:11434/api/generate"
LLM_MODEL: str = "codellama"  # e.g. "codellama", "qwen2.5-coder", "llama3.2"
LLM_API_KEY: str = ""
LLM_TIMEOUT_SEC: float = 2.5  # Hard upper limit for responsiveness
LLM_TEMPERATURE: float = 0.2

