"""
IDEye - IDE Navigation / Reading Context Mode (Phase 6)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ideye.actions.menu_trees import MenuNode
from ideye.actions.semantic_taxonomy import build_navigation_dual_tree
from .base_mode import BaseMode


class IdeNavMode(BaseMode):
    mode_id = "navigation"
    display_name = "Navegación"
    theme_color = "#E2E8F0"

    def get_root_menu(self, language: Optional[str] = None) -> MenuNode:
        return self.get_menu_tree(language)["ROOT"]

    def get_menu_tree(self, language: Optional[str] = None) -> Dict[str, MenuNode]:
        return build_navigation_dual_tree(bool(getattr(self, "document_mode", False)))

    def get_ai_system_prompt(self, context_data: Optional[Dict[str, Any]] = None) -> str:
        return (
            "You are an IDE navigation assistant for a disabled programmer using eye-tracking. "
            "Suggest navigation commands, search, refactoring, and code understanding actions. "
            "Return ONLY a JSON array of exactly 6 strings."
        )

    def get_heuristic_predictions(
        self, context_data: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        return [
            "Ir a definición (F12)",
            "Volver posición (Alt+←)",
            "Buscar en archivos (Ctrl+Shift+F)",
            "Plegar bloque",
            "Abrir terminal (Ctrl+`)",
            "Paleta de comandos (Ctrl+Shift+P)",
        ]


NavigationMode = IdeNavMode
NavMode = IdeNavMode
IDE_NAV_MODE = IdeNavMode
Navigation = IdeNavMode
ReadMode = IdeNavMode
IdeNav = IdeNavMode
NAVIGATION_MODE = IdeNavMode
NAVIGATION_READ_MODE = IdeNavMode
