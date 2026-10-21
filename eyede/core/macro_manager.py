"""IDEye - Custom macro persistence and menu-tree overrides (Phase 8.2)."""

from __future__ import annotations

import copy
import json
import os
import threading
from typing import Any, Dict, Optional

try:
    from eyede.actions.menu_trees import MenuAction, MenuNode
except ImportError:  # pragma: no cover
    from actions.menu_trees import MenuAction, MenuNode


def default_macros_path() -> str:
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(root, "custom_macros.json")


class MacroManager:
    """Loads, validates and atomically persists user-defined 3x3 cells."""

    PROTECTED_CELLS = {4, 6}  # Pause and Back remain invariant.

    def __init__(self, path: Optional[str] = None) -> None:
        self.path = path or default_macros_path()
        self._lock = threading.RLock()
        self._macros: Dict[str, Any] = {}
        self.load_macros()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def load_macros(self) -> Dict[str, Any]:
        try:
            if os.path.isfile(self.path):
                with open(self.path, "r", encoding="utf-8") as fh:
                    raw = json.load(fh)
                if isinstance(raw, dict):
                    self._macros = self._validate(raw)
                else:
                    raise ValueError("root must be an object")
            else:
                self._macros = {}
        except Exception as exc:
            print(f"[MacroManager] Warning: could not load '{self.path}': {exc}. Using defaults.")
            self._macros = {}
        return copy.deepcopy(self._macros)

    def _validate(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        for mode_id, mode_data in raw.items():
            if not isinstance(mode_data, dict):
                continue
            cells = mode_data.get("cells", {})
            if not isinstance(cells, dict):
                continue
            clean_cells: Dict[str, Any] = {}
            for key, cell in cells.items():
                try:
                    idx = int(key)
                except (TypeError, ValueError):
                    continue
                if idx < 0 or idx > 8 or idx in self.PROTECTED_CELLS:
                    continue
                if not isinstance(cell, dict):
                    continue
                label = str(cell.get("label", "")).strip()
                if not label:
                    continue
                action_type = str(cell.get("action_type", "snippet")).lower()
                if action_type not in ("snippet", "command", "key"):
                    action_type = "snippet"
                payload = str(cell.get("payload", ""))
                clean_cells[str(idx)] = {
                    "label": label,
                    "subtitle": str(cell.get("subtitle", "")),
                    "icon": str(cell.get("icon", "code")),
                    "action_type": action_type,
                    "payload": payload,
                }
            if clean_cells:
                result[str(mode_id).lower()] = {"cells": clean_cells}
        return result

    def save_macro(self, mode_id: str, cell_index: int, data: Dict[str, Any]) -> bool:
        mode = str(mode_id).lower()
        try:
            idx = int(cell_index)
        except (TypeError, ValueError):
            return False
        if idx < 0 or idx > 8 or idx in self.PROTECTED_CELLS:
            return False
        label = str(data.get("label", "")).strip()
        if not label:
            return False
        action_type = str(data.get("action_type", "snippet")).lower()
        if action_type not in ("snippet", "command", "key"):
            action_type = "snippet"
        cell = {
            "label": label,
            "subtitle": str(data.get("subtitle", "")),
            "icon": str(data.get("icon", "code")),
            "action_type": action_type,
            "payload": str(data.get("payload", "")),
        }
        with self._lock:
            mode_data = self._macros.setdefault(mode, {"cells": {}})
            mode_data.setdefault("cells", {})[str(idx)] = cell
            snapshot = copy.deepcopy(self._macros)
        return self._atomic_write(snapshot)

    def delete_macro(self, mode_id: str, cell_index: int) -> bool:
        mode = str(mode_id).lower()
        with self._lock:
            cells = self._macros.get(mode, {}).get("cells", {})
            cells.pop(str(cell_index), None)
            snapshot = copy.deepcopy(self._macros)
        return self._atomic_write(snapshot)

    def _atomic_write(self, data: Dict[str, Any]) -> bool:
        tmp = self.path + ".tmp"
        try:
            os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2, ensure_ascii=False)
                fh.write("\n")
                fh.flush()
                try:
                    os.fsync(fh.fileno())
                except OSError:
                    pass
            os.replace(tmp, self.path)
            return True
        except Exception as exc:
            print(f"[MacroManager] Warning: could not save '{self.path}': {exc}")
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except OSError:
                pass
            return False

    # ------------------------------------------------------------------
    # Menu patching
    # ------------------------------------------------------------------
    def get_cells(self, mode_id: str) -> Dict[str, Any]:
        with self._lock:
            return copy.deepcopy(self._macros.get(str(mode_id).lower(), {}).get("cells", {}))

    def apply_overrides(self, default_root_node: MenuNode, mode_id: str) -> MenuNode:
        """Returns a deep-copied root node with custom cells patched in."""
        node = copy.deepcopy(default_root_node)
        cells = self.get_cells(mode_id)
        if not cells:
            return node
        for key, data in cells.items():
            try:
                idx = int(key)
            except (TypeError, ValueError):
                continue
            if idx < 0 or idx >= len(node.items) or idx in self.PROTECTED_CELLS:
                continue
            node.items[idx] = self._to_menu_action(mode_id, idx, data)
        return node

    def _to_menu_action(self, mode_id: str, idx: int, data: Dict[str, Any]) -> MenuAction:
        action_type = str(data.get("action_type", "snippet")).lower()
        payload = str(data.get("payload", ""))
        if action_type == "key":
            return MenuAction(
                id=f"CUSTOM_{mode_id.upper()}_{idx}",
                label=str(data.get("label", f"Custom {idx + 1}")),
                hint=str(data.get("subtitle", "")),
                action_type="KEY",
                key_name=payload,
                icon=str(data.get("icon", "operators")),
                sticky=False,
            )
        return MenuAction(
            id=f"CUSTOM_{mode_id.upper()}_{idx}",
            label=str(data.get("label", f"Custom {idx + 1}")),
            hint=str(data.get("subtitle", "")),
            action_type="SNIPPET",
            snippet=payload,
            icon=str(data.get("icon", "code")),
            sticky=False,
        )
