"""Context reader, language, sniper lens and ergonomics constants."""

import os
from typing import Dict, Any, List, Optional, Tuple

from ideye.config_vision import *  # noqa: F401,F403
from ideye.config_gestures import *  # noqa: F401,F403
from ideye.config_ui import *  # noqa: F401,F403

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
# When True every UI transition (focus, ghost-peek, lens, banner, margin) is instant.
REDUCED_MOTION: bool = False
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
DWELL_CLICK_ENABLED: bool = False
ADAPTIVE_DWELL_CLICK_ENABLED: bool = False
DWELL_TIME_NAV_SEC: float = 0.30        # Fast dwell for navigation / repeated keys
DWELL_TIME_STANDARD_SEC: float = 0.45   # Standard dwell for snippets and menus
DWELL_TIME_DANGER_SEC: float = 0.85     # Safe dwell for destructive actions (exit/close)
