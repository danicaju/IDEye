"""Single source of truth for IDEye's interactive Game Manual.

The guide is intentionally data-driven: update the page/card catalog and run
``generate_interactive_guide()`` after any user-facing feature change.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from ideye.core.hotkey_manager import HOTKEY_ACTIONS
    from ideye.core.gesture_detector import GestureDetector
    from ideye.modes.mode_manager import MODE_ORDER, ModeManager
except ImportError:  # pragma: no cover
    from core.hotkey_manager import HOTKEY_ACTIONS
    from core.gesture_detector import GestureDetector
    from modes.mode_manager import MODE_ORDER, ModeManager

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DOCS_DIR = ROOT_DIR / "docs"
GUIDE_PATH = DOCS_DIR / "guia_interactiva.html"


from ideye.core.catalog_pages import PAGES  # noqa: F401
from ideye.core.catalog_data import (  # noqa: F401
    GESTURES,
    LEGAL_NOTICES,
    SHORTCUT_LABELS,
    SVG_ICONS,
)
from ideye.core.catalog_simulator import DOJO_CHALLENGES, FALLBACK_SIMULATOR  # noqa: F401


def _display_shortcuts() -> List[Dict[str, str]]:
    shortcuts: List[Dict[str, str]] = []
    for spec, _handler in HOTKEY_ACTIONS.items():
        key = spec.rsplit("+", 1)[-1].replace(">", "")
        label, description = SHORTCUT_LABELS.get(
            key, (key.upper(), "Atajo global de IDEye.")
        )
        shortcuts.append(
            {
                "key": f"Ctrl+Alt+{key.upper()}",
                "label": label,
                "description": description,
            }
        )
    return shortcuts


def _display_modes() -> List[Dict[str, str]]:
    modes: List[Dict[str, str]] = []
    try:
        manager = ModeManager(initial_mode="coding", auto_switch_enabled=False)
        for mode_id in MODE_ORDER:
            mode = manager.modes.get(mode_id)
            if mode is None:
                continue
            modes.append(
                {
                    "id": mode_id,
                    "name": str(getattr(mode, "display_name", mode_id)),
                    "color": str(getattr(mode, "theme_color", "#38bdf8")),
                }
            )
    except Exception:
        for mode_id in MODE_ORDER:
            modes.append({"id": mode_id, "name": mode_id.replace("_", " ").title(), "color": "#38bdf8"})
    return modes


def _simulator() -> Dict[str, Dict[str, Any]]:
    simulator = {key: {"name": value["name"], "cells": [dict(c) for c in value["cells"]]} for key, value in FALLBACK_SIMULATOR.items()}
    try:
        manager = ModeManager(initial_mode="coding", auto_switch_enabled=False)
        for mode_id in ("coding", "writing", "terminal", "data_math"):
            mode = manager.modes.get(mode_id)
            if mode is None or not hasattr(mode, "get_root_menu"):
                continue
            root = mode.get_root_menu()
            fallback_cells = FALLBACK_SIMULATOR.get(mode_id, {}).get("cells", [])
            cells = []
            for i, item in enumerate(root.items):
                lbl = str(getattr(item, "label", "—"))
                hnt = str(getattr(item, "hint", "Acción del modo"))
                snp = fallback_cells[i].get("snippet", f"# {lbl}: {hnt}\n") if i < len(fallback_cells) else f"# {lbl}\n"
                cells.append({"label": lbl, "hint": hnt, "snippet": snp})
            if len(cells) == 9:
                simulator[mode_id] = {"name": str(getattr(mode, "display_name", mode_id)), "cells": cells}
    except Exception:
        pass
    return simulator


def _gesture_thresholds() -> Dict[str, Any]:
    try:
        detector = GestureDetector()
        return {
            "mar_threshold": round(float(detector.mar_threshold), 3),
            "ear_close": round(float(detector.ear_close_threshold), 3),
            "wink_ms": int(round(float(detector.wink_min_hold_sec) * 1000)),
            "wink_max_ms": int(round(float(detector.wink_max_hold_sec) * 1000)),
        }
    except Exception:
        return {"mar_threshold": 0.45, "ear_close": 0.16, "wink_ms": 150, "wink_max_ms": 450}


def build_catalog() -> Dict[str, Any]:
    """Builds the live catalog consumed by the HTML builder."""
    return {
        "pages": PAGES,
        "gestures": GESTURES,
        "legal": LEGAL_NOTICES,
        "gesture_thresholds": _gesture_thresholds(),
        "shortcuts": _display_shortcuts(),
        "modes": _display_modes(),
        "simulator": _simulator(),
        "dojo_challenges": DOJO_CHALLENGES,
    }


def generate_interactive_guide(path: Optional[os.PathLike | str] = None) -> Path:
    """Regenerates the self-contained interactive guide and returns its path."""
    from ideye.core.guide_builder import build_interactive_guide_html

    target = Path(path) if path is not None else GUIDE_PATH
    html_text = build_interactive_guide_html(build_catalog())
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(html_text, encoding="utf-8")
    except OSError:
        target = Path(tempfile.gettempdir()) / "IDEye" / "guia_interactiva.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(html_text, encoding="utf-8")
    return target


__all__ = ["GUIDE_PATH", "LEGAL_NOTICES", "SVG_ICONS", "build_catalog", "generate_interactive_guide"]
