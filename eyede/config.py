"""
EyeDE - Configuration Module (Phase 1)
Central configuration for camera tracking, hybrid gaze estimation,
gesture trigger thresholds, and UI display parameters.
"""

from typing import Dict, Any, List

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
# Hybrid Gaze Estimator Weights & Sensitivities
# ==============================================================================
# Default balance: 60% head/nose vector, 40% iris vector
HEAD_WEIGHT: float = 0.60
IRIS_WEIGHT: float = 0.40

# Gain / sensitivity multipliers
DEFAULT_HEAD_SENSITIVITY_X: float = 2.6
DEFAULT_HEAD_SENSITIVITY_Y: float = 2.6
DEFAULT_IRIS_SENSITIVITY_X: float = 3.5
DEFAULT_IRIS_SENSITIVITY_Y: float = 3.5

# Smoothing factor for Exponential Moving Average (EMA)
# Higher = more responsive, lower = smoother (less jitter)
EMA_ALPHA: float = 0.22

# Blink Detection (EAR & Eye Height)
# Below this vertical opening ratio, eye is considered closed (blink suppression)
EAR_BLINK_THRESHOLD: float = 0.18
MIN_EYE_HEIGHT_RATIO: float = 0.012

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
    {"index": 4, "key": "5", "label": "5: CENTRO / PAUSA", "action": "PAUSE_RESUME", "hint": "Rest Zone"},
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

