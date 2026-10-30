"""Phase 12: dynamic debug inspector mode."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

try:
    from ideye.actions.menu_trees import MenuNode
    from ideye.actions.semantic_taxonomy import build_debug_semantic_tree
except ImportError:  # pragma: no cover
    from actions.menu_trees import MenuNode  # type: ignore
    from actions.semantic_taxonomy import build_debug_semantic_tree  # type: ignore

from .base_mode import BaseMode


class DebugMode(BaseMode):
    mode_id = "debug"
    display_name = "Debug"
    theme_color = "#F97316"

    def __init__(self, language: str = "PYTHON") -> None:
        super().__init__(language)
        self.local_symbols: List[str] = []

    def set_local_symbols(self, symbols: Optional[List[str]]) -> None:
        self.local_symbols = list(symbols or [])

    def get_menu_tree(self, language: Optional[str] = None) -> Dict[str, MenuNode]:
        return build_debug_semantic_tree(self.local_symbols)

    def get_root_menu(self, language: Optional[str] = None) -> MenuNode:
        return self.get_menu_tree(language)["ROOT"]

    def get_ai_system_prompt(self, context_data: Optional[Dict[str, Any]] = None) -> str:
        return "You are a debugger assistant. Return exactly 6 concise debugging actions."

    def get_heuristic_predictions(self, context_data: Optional[Dict[str, Any]] = None) -> List[str]:
        return [
            "Step over",
            "Step into",
            "Inspect locals",
            "Show call stack",
            "Explain failure",
            "Generate regression test",
        ]


DEBUG_MODE = DebugMode
