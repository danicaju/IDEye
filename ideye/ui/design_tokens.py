"""Design tokens shared by the HUD overlay, the debug panel and the sniper lens.

One accent, two corner radii, one motion budget. Keep new UI code on these
constants instead of inlining hex values or radii.
"""

from __future__ import annotations

# --- Accent -----------------------------------------------------------------
ACCENT_HEX = "#22D3EE"
ACCENT_RGB = (34, 211, 238)

# --- Corner radii (px). Only these two exist in the HUD. ---------------------
RADIUS_S = 8    # pills, badges, chips, small buttons
RADIUS_L = 14   # cards, header bar, panels

# --- Surfaces and text --------------------------------------------------------
SURFACE_BASE_HEX = "#0A0F1D"
SURFACE_RAISED_HEX = "#081026"
BORDER_HEX = "#1E293B"
BORDER_STRONG_HEX = "#334155"
TEXT_PRIMARY_HEX = "#E2E8F0"
TEXT_SECONDARY_HEX = "#94A3B8"
TEXT_STRONG_HEX = "#F8FAFC"

# --- Status colors (state only, never decoration) -----------------------------
SUCCESS_HEX = "#34D399"
WARNING_HEX = "#FBBF24"
DANGER_HEX = "#EF4444"

# --- Motion (ms) --------------------------------------------------------------
MOTION_FOCUS_MS = 80       # focus moving between cells
MOTION_WAKE_MS = 80        # ghost-peek waking up
MOTION_GHOST_FADE_MS = 400  # ghost-peek dimming
MOTION_LENS_MS = 120       # sniper lens fade
MOTION_MARGIN_MS = 180     # grid right-margin reflow

# Inactive cell outline: almost invisible, the content draws the silhouette.
INACTIVE_OUTLINE_ALPHA = 20

ALLOWED_RADII = (RADIUS_S, RADIUS_L)


def duration(ms: int, reduced_motion: bool) -> int:
    """Returns the animation duration to use; 0 means "apply instantly"."""
    return 0 if reduced_motion else int(ms)
