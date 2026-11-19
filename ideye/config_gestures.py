"""Gesture, grid, gaming and window-routing constants."""

import os
from typing import Dict, Any, List, Optional, Tuple

from ideye.config_vision import *  # noqa: F401,F403

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
