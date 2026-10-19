"""
IDEye - Coding Context Mode (Phase 6)

Thin wrapper over the existing AST-aware menu tree and Python heuristics.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

try:
    from eyede.actions.menu_trees import build_menu_tree, MenuNode
    from eyede.actions.ai_predictor import generate_heuristic_predictions as _gen_heuristics
except ImportError:  # pragma: no cover
    from actions.menu_trees import build_menu_tree, MenuNode
    from actions.ai_predictor import generate_heuristic_predictions as _gen_heuristics

from .base_mode import BaseMode


class CodingMode(BaseMode):
    mode_id = "coding"
    display_name = "CÓDIGO (AST)"
    theme_color = "#00F0FF"

    def __init__(self, language: str = "PYTHON") -> None:
        super().__init__(language)
        self.language = language

    def get_menu_tree(self, language: Optional[str] = None) -> Dict[str, MenuNode]:
        lang = language or self.language
        return build_menu_tree(lang)

    def get_root_menu(self, language: Optional[str] = None) -> MenuNode:
        lang = language or self.language
        tree = build_menu_tree(lang)
        return tree["ROOT"]

    def get_ai_system_prompt(self, context_data: Optional[Dict[str, Any]] = None) -> str:
        ctx = context_data or {}
        lang = ctx.get("language", self.language)
        return (
            "You are an expert code completion assistant for a disabled programmer using eye-tracking. "
            f"Active language: {lang}. Predict the next most useful code statements or snippets. "
            "Return ONLY a JSON array of exactly 6 strings."
        )

    def get_heuristic_predictions(
        self, context_data: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        ctx = context_data or {}
        text = ctx.get("context_text") or ctx.get("code") or ctx.get("text") or ""
        symbols = ctx.get("local_symbols") or ctx.get("symbols") or None
        try:
            return list(_gen_heuristics(text, symbols))[:6]
        except Exception:
            return ["pass"] * 6


# Backwards / naming aliases
CodeMode = CodingMode
ProgrammingMode = CodingMode
CODING_MODE = CodingMode
CodeMode = CodingMode
