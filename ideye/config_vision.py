"""Camera, landmarks, tracking modes and filtering constants."""

import os
from typing import Dict, Any, List, Optional, Tuple

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
# Vertical sensitivity is calibrated balanced with horizontal sensitivity (3.0 vs 2.6)
# to ensure completely natural, stable, and proportional head pitch without exaggerated jumps.
DEFAULT_HEAD_SENSITIVITY_X: float = 2.6
DEFAULT_HEAD_SENSITIVITY_Y: float = 3.0
DEFAULT_IRIS_SENSITIVITY_X: float = 3.6
DEFAULT_IRIS_SENSITIVITY_Y: float = 8.5

# Anti-Jitter Filtering (One Euro Filter + Fixation Deadzone)
ONE_EURO_MIN_CUTOFF: float = 0.55   # Low-speed cutoff (Hz) - eliminates resting jitter
ONE_EURO_BETA: float = 0.28        # Speed coefficient - eliminates saccadic lag
ONE_EURO_D_CUTOFF: float = 1.0     # Derivative cutoff (Hz)
FIXATION_DEADZONE: float = 0.022   # Deadzone radius in normalized coords for rock-solid resting

# Ergonomic non-linear reach curves
VERTICAL_MULTIPLIER: float = 2.35      # Ergonomic independent vertical gain multiplier (softened from 2.40)
VERTICAL_EXPANSION_GAIN: float = 1.6   # Ergonomic non-linear vertical curve multiplier (softened from 1.80)
HORIZONTAL_MULTIPLIER: float = 1.45    # Ergonomic independent horizontal gain multiplier
HORIZONTAL_EXPANSION_GAIN: float = 1.75 # Non-linear horizontal edge expansion for border reach
VOR_COMPENSATION_FACTOR: float = 0.40  # Vestibulo-Ocular Reflex decoupling factor for HYBRID mode

# Phase 7.6: static hysteresis pinning and dynamic fusion
STATIC_LOCK_RADIUS: float = 0.0035       # Enter rock-solid rest below this frame delta
STATIC_BREAKOUT_RADIUS: float = 0.0085   # Intentional movement required to leave rest
STATIC_LOCK_FRAMES: int = 3              # Consecutive quiet frames before pinning again
IRIS_MEDIAN_WINDOW: int = 5              # Temporal median window for PURE_IRIS
HYBRID_IRIS_WEIGHT_REST: float = 0.08    # Iris weight while fixating in HYBRID
HYBRID_IRIS_WEIGHT_SACCADE: float = 0.55 # Iris weight during ocular saccades
IRIS_SACCADE_THRESHOLD: float = 0.012    # Iris innovation that counts as a saccade
CELL_MAGNETISM_ENABLED: bool = True
CELL_MAGNETISM_STRENGTH: float = 0.15
CELL_MAGNETISM_DWELL: float = 0.15

# Phase 7.7: FreeLook full-screen overscan and taskbar magnetic rail
# Phase 7.8: Easy page scrolling in desktop FreeLook.
FREELOOK_EDGE_SCROLL_ENABLED: bool = True
FREELOOK_EDGE_SCROLL_ZONE: float = 0.075
FREELOOK_EDGE_SCROLL_DELAY_SEC: float = 0.30
FREELOOK_EDGE_SCROLL_INTERVAL_SEC: float = 0.11
FREELOOK_EDGE_SCROLL_STEP: int = 3

OVERSCAN_MARGIN_X: float = 0.04
OVERSCAN_MARGIN_Y_TOP: float = 0.04
OVERSCAN_MARGIN_Y_BOTTOM: float = 0.07
TASKBAR_RAIL_HEIGHT: int = 52
TASKBAR_RAIL_TARGET_Y: int = 24
TASKBAR_RAIL_PULL: float = 0.60

# FreeLook ergonomics: guarantee the top command bar and desktop top edge
# remain reachable even when the user's comfortable upward gaze is limited.
FREELOOK_TOP_MAGNET_ZONE: float = 0.18
FREELOOK_TOP_MAGNET_PULL: float = 0.94
FREELOOK_JAW_LOCK_MIN_MAR: float = 0.27
FREELOOK_JAW_LOCK_MAX_SEC: float = 2.0
FREELOOK_MOUTH_TRIGGER_RATIO: float = 0.78
FREELOOK_MOUTH_RELEASE_RATIO: float = 0.48

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
