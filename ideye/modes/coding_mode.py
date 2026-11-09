"""
IDEye - Coding Context Mode (Phase 6)

Thin wrapper over the existing AST-aware menu tree and Python heuristics.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

try:
    from ideye.actions.menu_trees import build_menu_tree, MenuNode
    from ideye.actions.ai_predictor import generate_heuristic_predictions as _gen_heuristics
    from ideye.actions.semantic_taxonomy import build_semantic_coding_tree
except ImportError:  # pragma: no cover
    from actions.menu_trees import build_menu_tree, MenuNode
    from actions.ai_predictor import generate_heuristic_predictions as _gen_heuristics
    from actions.semantic_taxonomy import build_semantic_coding_tree

from .base_mode import BaseMode


class CodingMode(BaseMode):
    mode_id = "coding"
    display_name = "Código"
    theme_color = "#3b82f6"

    def __init__(self, language: str = "PYTHON") -> None:
        super().__init__(language)
        self.language = language
        self.local_symbols: List[str] = []
        self.document_context: bool = False
        self.ai_suggestions: List[str] = []

    def set_context(
        self,
        symbols: Optional[List[str]] = None,
        document_context: bool = False,
        ai_suggestions: Optional[List[str]] = None,
    ) -> None:
        self.local_symbols = list(symbols or [])
        self.document_context = bool(document_context)
        self.ai_suggestions = list(ai_suggestions or [])

    def get_menu_tree(self, language: Optional[str] = None) -> Dict[str, MenuNode]:
        lang = language or self.language
        return build_semantic_coding_tree(
            lang,
            symbols=self.local_symbols,
            ai_suggestions=self.ai_suggestions,
            document_context=self.document_context,
        )

    def get_root_menu(self, language: Optional[str] = None) -> MenuNode:
        lang = language or self.language
        tree = self.get_menu_tree(lang)
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
