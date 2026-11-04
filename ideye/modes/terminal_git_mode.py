"""
IDEye - Terminal & Git Context Mode (Phase 6)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ideye.actions.menu_trees import MenuNode
from ideye.actions.semantic_taxonomy import build_terminal_semantic_tree
from .base_mode import BaseMode


class TerminalGitMode(BaseMode):
    mode_id = "terminal"
    display_name = "Terminal"
    theme_color = "#A855F7"

    def get_root_menu(self, language: Optional[str] = None) -> MenuNode:
        return self.get_menu_tree(language)["ROOT"]

    def get_menu_tree(self, language: Optional[str] = None) -> Dict[str, MenuNode]:
        return build_terminal_semantic_tree(getattr(self, "project_context", None))

    def get_ai_system_prompt(self, context_data: Optional[Dict[str, Any]] = None) -> str:
        return (
            "You are a terminal command assistant for a disabled programmer using eye-tracking. "
            "Suggest terminal commands for git, build, tests, environment, and system diagnostics. "
            "Return ONLY a JSON array of exactly 6 strings."
        )

    def get_heuristic_predictions(
        self, context_data: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        return [
            "git status",
            "git add .",
            'git commit -m ""',
            "pytest -v",
            "python main.py",
            "git push",
        ]


TerminalMode = TerminalGitMode
GitMode = TerminalGitMode
TERMINAL_MODE = TerminalGitMode
Terminal = TerminalGitMode
TerminalGit = TerminalGitMode
