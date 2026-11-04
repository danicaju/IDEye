"""
IDEye - Configuration Module (Phase 1)
Central configuration for camera tracking, hybrid gaze estimation,
gesture trigger thresholds, and UI display parameters.
"""

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

# ==============================================================================
# Gesture Detector (MAR & Asymmetric Eye-Wink) Parameters
# ==============================================================================
# Mouth Aspect Ratio threshold for detecting slightly open mouth
MAR_THRESHOLD: float = 0.45
# Hysteresis: mouth must close below this to re-arm the trigger
MAR_RELEASE_THRESHOLD: float = 0.35
# Nominal resting mouth ratio baseline
MAR_REST_THRESHOLD: float = 0.20
# Real-time adaptive baseline learning to prevent ghost clicks (Anti-Midas)
MAR_ADAPTIVE_BASELINE_ENABLED: bool = True
# Duration (seconds) mouth must stay open continuously before firing CLICK
CLICK_HOLD_TIME_SEC: float = 0.15
# Cooldown duration (seconds) after a successful click before another can occur
CLICK_COOLDOWN_SEC: float = 0.35

# Asymmetric Eye-Wink Detection (EAR) Parameters
# Scale-invariant Eye Aspect Ratio thresholds
EAR_WINK_CLOSE_THRESHOLD: float = 0.16  # Below this, eye is considered closed
EAR_WINK_OPEN_THRESHOLD: float = 0.22   # Above this, eye is considered open
WINK_MIN_HOLD_SEC: float = 0.18         # Minimum intentional wink hold (180ms)
WINK_MAX_HOLD_SEC: float = 0.30         # Longer closures are treated as squints
WINK_COOLDOWN_SEC: float = 0.65         # Cooldown between independent winks
WINK_OPPOSITE_EYE_MARGIN: float = 0.035  # Open eye must clear its threshold by this margin
WINK_MIN_INTEROCULAR_DIST: float = 0.075  # Reject winks when the face is too far away
WINK_MAX_ROLL_DEG: float = 28.0          # Reject extreme head roll
WINK_MAX_YAW_RATIO: float = 0.55         # Nose offset / interocular distance
WINK_DOUBLE_WINDOW_SEC: float = 0.90     # Second same-side wink = confirmed double wink
WINK_ENABLED: bool = True
WINK_MOUTH_ONLY: bool = False
WINK_DIFFICULTY: str = "normal"           # relaxed | normal | strict
WINK_DISTANCE_COMPENSATION: bool = True
WINK_CONFIRM_DANGEROUS: bool = True

# MediaPipe 478 Landmark Indices for EAR Calculation
# Left eye (outer corner 33, top outer 160, top inner 158, inner corner 133, bottom inner 153, bottom outer 144)
LANDMARK_LEFT_EYE_EAR_INDICES: tuple = (33, 160, 158, 133, 153, 144)
# Right eye (inner corner 362, top inner 385, top outer 387, outer corner 263, bottom outer 373, bottom inner 380)
LANDMARK_RIGHT_EYE_EAR_INDICES: tuple = (362, 385, 387, 263, 373, 380)

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
EXIT_DOUBLE_CLICK_SEC: float = 1.50

# Multi-monitor bezel crossing (Phase 8.3)
BEZEL_AUTO_HANDOVER_ENABLED: bool = True
BEZEL_YAW_THRESHOLD_DEG: float = 21.0
BEZEL_HOLD_SEC: float = 0.40
BEZEL_COOLDOWN_SEC: float = 1.0

# Phase 9: foreground-window gaming detection. Extend these tuples for games
# that are not covered by the generic Unreal/Shipping process suffixes.
GAMING_PROCESSES: tuple[str, ...] = (
    "robloxplayerbeta.exe",
    "isaac-ng.exe",
    "fortniteclient-win64-shipping.exe",
    "gta5.exe",
    "rdr2.exe",
    "cs2.exe",
    "valorant.exe",
    "league of legends.exe",
    "dota2.exe",
    "overwatch.exe",
    "destiny2.exe",
    "eldenring.exe",
    "bg3.exe",
    "witcher3.exe",
    "rocketleague.exe",
    "amongus.exe",
    "terraria.exe",
    "factorio.exe",
    "rimworldwin64.exe",
    "stardew valley.exe",
    "hollow_knight.exe",
    "celeste.exe",
    "cuphead.exe",
    "hades.exe",
    "deadcells.exe",
)
GAMING_TITLE_KEYWORDS: tuple[str, ...] = (
    "roblox",
    "minecraft",
    "isaac",
    "fortnite",
    "grand theft auto",
    "gta",
    "red dead",
    "counter-strike",
    "valorant",
    "league of legends",
    "dota",
    "overwatch",
    "destiny",
    "elden ring",
    "baldur's gate",
    "witcher",
    "rocket league",
    "among us",
    "terraria",
    "factorio",
    "rimworld",
    "stardew",
    "hollow knight",
    "celeste",
    "cuphead",
    "hades",
    "dead cells",
)
GAMING_DEADZONE: float = 0.14
HEALTH_GUARD_ENABLED: bool = True
MICRO_GESTURES_ENABLED: bool = True
AUTO_LOW_LIGHT_CLAHE: bool = True
AUTO_EYE_ROI_CLAHE: bool = True
CAP_MODE_ENABLED: bool = False
CAP_SAFE_ANCHOR_WEIGHTS: Tuple[float, ...] = (0.35, 0.35, 0.05, 0.00, 0.15, 0.10)
CAP_MODE_MIN_DETECTION_CONFIDENCE: float = 0.42
EYE_SHADOW_DELTA_THRESHOLD: float = 20.0
SNIPER_LENS_ZOOM: float = 3.5
SNIPER_LENS_SLOWMO: float = 0.28
# Brow raises happen naturally while looking up; keep them from opening the
# lens unless the user explicitly opts in.
SNIPER_LENS_BROW_TRIGGER_ENABLED: bool = False
GAMING_AUTO_RETURN_AFTER_CLICK: bool = False
GAMING_PROCESS_SUFFIXES: tuple[str, ...] = (
    "-win64-shipping.exe",
    "-shipping.exe",
    "-win64.exe",
)

# Phase 9: foreground-window routing for non-gaming applications.
TERMINAL_PROCESSES: tuple[str, ...] = (
    "windowsterminal.exe",
    "wt.exe",
    "powershell.exe",
    "pwsh.exe",
    "cmd.exe",
    "conhost.exe",
    "git-bash.exe",
    "bash.exe",
    "wsl.exe",
    "alacritty.exe",
    "wezterm-gui.exe",
    "wezterm.exe",
    "kitty.exe",
    "hyper.exe",
    "conemu64.exe",
    "conemu.exe",
    "cmder.exe",
    "tabby.exe",
    "warp.exe",
    "mintty.exe",
    "putty.exe",
    "mobaxterm.exe",
)
WRITING_PROCESSES: tuple[str, ...] = (
    "discord.exe",
    "discordcanary.exe",
    "discordptb.exe",
    "slack.exe",
    "teams.exe",
    "ms-teams.exe",
    "telegram.exe",
    "whatsapp.exe",
    "zoom.exe",
    "notion.exe",
    "obsidian.exe",
    "evernote.exe",
    "onenote.exe",
    "winword.exe",
    "wordpad.exe",
    "notepad.exe",
    "outlook.exe",
    "thunderbird.exe",
    "libreoffice-writer.exe",
    "scrivener.exe",
    "typora.exe",
    "marktext.exe",
    "joplin.exe",
    "logseq.exe",
)
BROWSER_PROCESSES: tuple[str, ...] = (
    "chrome.exe",
    "chromium.exe",
    "msedge.exe",
    "firefox.exe",
    "brave.exe",
    "vivaldi.exe",
    "opera.exe",
    "opera_gx.exe",
    "arc.exe",
    "waterfox.exe",
    "zen.exe",
    "safari.exe",
)
IDE_PROCESSES: tuple[str, ...] = (
    "code.exe",
    "code-insiders.exe",
    "cursor.exe",
    "windsurf.exe",
    "pycharm64.exe",
    "pycharm.exe",
    "idea64.exe",
    "idea.exe",
    "devenv.exe",
    "rider64.exe",
    "webstorm64.exe",
    "clion64.exe",
    "goland64.exe",
    "phpstorm64.exe",
    "rubymine64.exe",
    "datagrip64.exe",
    "rustrover64.exe",
    "fleet.exe",
    "sublime_text.exe",
    "notepad++.exe",
    "atom.exe",
    "brackets.exe",
    "eclipse.exe",
    "netbeans64.exe",
    "android-studio64.exe",
    "xcode.exe",
    "zed.exe",
    "nvim-qt.exe",
    "gvim.exe",
    "emacs.exe",
)

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

# Adaptive AST Menu Configuration (Option A: Dynamic AST Menus)
ENABLE_ADAPTIVE_AST_MENUS: bool = True

# Phase 6 UX: start on the explicit mode hub and let the user choose a mode.
# Automatic mode switching remains available through the [K] shortcut.
START_IN_MODE_SELECTOR: bool = True
CONTEXT_AUTO_SWITCH_ENABLED: bool = False

# Phase 11: ergonomic reading, eco power and ghost-peek HUD
ECO_SLEEP_ENABLED: bool = True
GHOST_PEEK_ENABLED: bool = True
GHOST_PEEK_IDLE_SECONDS: float = 30.0
GAZE_SCROLL_ENABLED: bool = True

# ==============================================================================
# Phase 5: Multi-Language Syntax Trees & Native VS Code WebSocket Bridge
# ==============================================================================
DEFAULT_PROGRAMMING_LANGUAGE: str = "PYTHON"
SUPPORTED_LANGUAGES: List[str] = ["PYTHON", "TYPESCRIPT", "RUST", "CPP", "GO"]

LANGUAGE_DISPLAY_NAMES: Dict[str, str] = {
    "PYTHON": "Python",
    "TYPESCRIPT": "TypeScript / JS",
    "RUST": "Rust",
    "CPP": "C / C++",
    "GO": "Go",
}

LANGUAGE_EXTENSIONS: Dict[str, str] = {
    ".py": "PYTHON",
    ".ts": "TYPESCRIPT",
    ".tsx": "TYPESCRIPT",
    ".js": "TYPESCRIPT",
    ".jsx": "TYPESCRIPT",
    ".mjs": "TYPESCRIPT",
    ".cjs": "TYPESCRIPT",
    ".rs": "RUST",
    ".cpp": "CPP",
    ".cc": "CPP",
    ".cxx": "CPP",
    ".hpp": "CPP",
    ".h": "CPP",
    ".c": "CPP",
    ".go": "GO",
}

LANGUAGE_ID_MAP: Dict[str, str] = {
    "python": "PYTHON",
    "typescript": "TYPESCRIPT",
    "javascript": "TYPESCRIPT",
    "typescriptreact": "TYPESCRIPT",
    "javascriptreact": "TYPESCRIPT",
    "rust": "RUST",
    "cpp": "CPP",
    "c": "CPP",
    "cuda-cpp": "CPP",
    "go": "GO",
}

# Native VS Code WebSocket Bridge
WEBSOCKET_HOST: str = "127.0.0.1"
WEBSOCKET_PORT: int = 54321
ENABLE_WEBSOCKET_BRIDGE: bool = True
WEBSOCKET_RECONNECT_INTERVAL_SEC: float = 2.0

# ==============================================================================
# Phase 7: Sniper Lens, Sound Feedback & OS Mouse Injection
# ==============================================================================
SOUND_ENABLED: bool = True
SOUND_VOLUME: float = 0.5

# ==============================================================================
# User-Friendly Ergonomics, Layouts, Themes & Onboarding
# ==============================================================================
# Flexible HUD Layouts (Full Screen 100% vs Right Dock 30%)
HUD_LAYOUT_FULL: str = "FULL_GRID"
HUD_LAYOUT_RIGHT_DOCK: str = "RIGHT_DOCK"
DEFAULT_HUD_LAYOUT: str = HUD_LAYOUT_FULL
RIGHT_DOCK_WIDTH_RATIO: float = 0.30
RIGHT_DOCK_MIN_WIDTH: float = 460.0
RIGHT_DOCK_MAX_WIDTH: float = 500.0

# Accessibility & High-Contrast Themes (WCAG AAA)
THEME_CYBER_GLASS: str = "CYBER_GLASS"
THEME_OLED_BLACK: str = "OLED_BLACK"
THEME_SOLARIZED_DARK: str = "SOLARIZED_DARK"
DEFAULT_THEME: str = THEME_CYBER_GLASS

# Visual Posture & Distance (Optimal Green Range 50-70 cm)
POSTURE_DISTANCE_MIN_CM: float = 50.0
POSTURE_DISTANCE_MAX_CM: float = 70.0
POSTURE_OPTIMAL_DISTANCE_CM: float = 60.0

# Adaptive Dwell-Time Parameters (Dynamic & Safe)
ADAPTIVE_DWELL_ENABLED: bool = True
DWELL_TIME_NAV_SEC: float = 0.30        # Fast dwell for navigation / repeated keys
DWELL_TIME_STANDARD_SEC: float = 0.45   # Standard dwell for snippets and menus
DWELL_TIME_DANGER_SEC: float = 0.85     # Safe dwell for destructive actions (exit/close)

