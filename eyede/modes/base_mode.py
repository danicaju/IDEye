"""
IDEye - Base Context Mode (Phase 6)

Abstract base class for all context modes plus the ModeTheme value object.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

try:
    from eyede.actions.menu_trees import MenuNode, MenuAction
except ImportError:  # pragma: no cover - fallback for script-style imports
    from actions.menu_trees import MenuNode, MenuAction


@dataclass
class ModeTheme:
    """Visual theme associated with a context mode."""

    mode_id: str
    display_name: str
    theme_color: str
    accent_color: str = ""

    def __post_init__(self) -> None:
        if not self.accent_color:
            self.accent_color = self.theme_color


class BaseMode(ABC):
    """Abstract base class for a context mode (Strategy pattern)."""

    mode_id: str = "coding"
    display_name: str = "CÓDIGO (AST)"
    theme_color: str = "#00F0FF"

    # Canonical order used by ModeManager.cycle_next_mode()
    MODE_ORDER: List[str] = ["coding", "writing", "terminal", "data_math", "navigation"]

    def __init__(self, language: str = "PYTHON") -> None:
        self.language: str = language
        self._language = language

    # ------------------------------------------------------------------ #
    # Identity helpers
    # ------------------------------------------------------------------ #
    @property
    def mode_name(self) -> str:
        return self.display_name

    @property
    def name(self) -> str:
        return self.display_name

    @property
    def color(self) -> str:
        return self.theme_color

    def get_theme(self) -> ModeTheme:
        return ModeTheme(
            mode_id=self.mode_id,
            display_name=self.display_name,
            theme_color=self.theme_color,
        )

    # ------------------------------------------------------------------ #
    # Menu tree contract
    # ------------------------------------------------------------------ #
    @abstractmethod
    def get_root_menu(self, language: Optional[str] = None) -> MenuNode:
        """Returns the root 3x3 MenuNode for this mode."""

    def get_menu_tree(self, language: Optional[str] = None) -> Dict[str, MenuNode]:
        """Returns the full menu tree (defaults to a single ROOT node)."""
        root = self.get_root_menu(language)
        return {"ROOT": root}

    def get_node(self, node_id: str, language: Optional[str] = None) -> Optional[MenuNode]:
        tree = self.get_menu_tree(language)
        return tree.get(node_id)

    # ------------------------------------------------------------------ #
    # AI contract
    # ------------------------------------------------------------------ #
    @abstractmethod
    def get_ai_system_prompt(self, context_data: Optional[Dict[str, Any]] = None) -> str:
        """Returns the specialised system prompt for the AI predictor."""

    @abstractmethod
    def get_heuristic_predictions(
        self, context_data: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """Returns exactly 6 zero-latency heuristic suggestions."""

    # ------------------------------------------------------------------ #
    # Convenience
    # ------------------------------------------------------------------ #
    def to_dict(self) -> Dict[str, Any]:
        return {
            "mode_id": self.mode_id,
            "display_name": self.display_name,
            "theme_color": self.theme_color,
        }
