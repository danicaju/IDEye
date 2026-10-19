"""
IDEye - Terminal & Git Context Mode (Phase 6)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from eyede.actions.menu_trees import MenuAction, MenuNode

try:
    from eyede.modes._helpers import make_root, make_submenu
except ImportError:  # pragma: no cover
    from modes._helpers import make_root, make_submenu

from .base_mode import BaseMode


def _act(slot, aid, label, snippet=None, key_name=None, action_type="SNIPPET"):
    ma = MenuAction(id=aid, label=f"{slot}: {label}", hint=label, action_type=action_type, snippet=snippet, key_name=key_name, icon="")
    if key_name:
        ma.action_type = "KEY"
        ma.snippet = None
    return ma


class TerminalGitMode(BaseMode):
    mode_id = "terminal"
    display_name = "TERMINAL & GIT"
    theme_color = "#A855F7"

    def get_menu_tree(self, language: Optional[str] = None) -> Dict[str, MenuNode]:
        tree: Dict[str, MenuNode] = {}

        git_basic = [
            _act("1", "T_GIT_STATUS", "git status", "git status"),
            _act("2", "T_GIT_ADD", "git add .", "git add ."),
            _act("3", "T_GIT_DIFF", "git diff", "git diff"),
            _act("4", "T_GIT_LOG", "git log", "git log --oneline -n 5"),
            _act("6", "T_GIT_BRANCH", "git branch", "git branch"),
            _act("8", "T_GIT_CHECKOUT", "git checkout", "git checkout "),
            _act("9", "T_GIT_MERGE", "git merge", "git merge "),
        ]
        tree["TERM_GIT_BASIC"] = make_submenu("TERM_GIT_BASIC", "GIT BÁSICO", git_basic)

        git_sync = [
            _act("1", "T_COMMIT", "git commit", 'git commit -m "|>|"'),
            _act("2", "T_PUSH", "git push", "git push"),
            _act("3", "T_PULL", "git pull", "git pull"),
            _act("4", "T_STASH", "git stash", "git stash"),
            _act("6", "T_FEAT", "feat:", "feat: "),
            _act("8", "T_FIX", "fix:", "fix: "),
            _act("9", "T_CHORE", "chore:", "chore: "),
        ]
        tree["TERM_GIT_SYNC"] = make_submenu("TERM_GIT_SYNC", "GIT COMMIT / SYNC", git_sync)

        python_test = [
            _act("1", "T_PYTEST", "pytest", "pytest -v"),
            _act("2", "T_RUN", "python main.py", "python main.py"),
            _act("3", "T_PIP", "pip install", "pip install "),
            _act("4", "T_VENV", "venv activate", r"venv\Scripts\activate"),
            _act("6", "T_RUFF", "ruff check", "ruff check ."),
            _act("8", "T_PYTHON", "python", "python "),
            _act("9", "T_UV", "uv run", "uv run "),
        ]
        tree["TERM_PYTHON"] = make_submenu("TERM_PYTHON", "PYTHON / TEST", python_test)

        history = [
            _act("1", "T_HIST_UP", "Flecha arriba", None, key_name="UP"),
            _act("2", "T_HIST_DOWN", "Flecha abajo", None, key_name="DOWN"),
            _act("3", "T_CTRL_C", "Ctrl+C", None, key_name="CTRL_C"),
            _act("4", "T_CLEAR", "clear/cls", "clear"),
            _act("6", "T_TAB", "Tab", None, key_name="TAB"),
            _act("8", "T_ENTER", "Enter", None, key_name="ENTER"),
            _act("9", "T_SEARCH", "Ctrl+R", None, key_name="CTRL_R"),
        ]
        tree["TERM_HISTORY"] = make_submenu("TERM_HISTORY", "HISTORIAL CONSOLA", history)

        paths = [
            _act("1", "T_CD_UP", "cd ..", "cd .."),
            _act("2", "T_LS", "ls/dir", "ls"),
            _act("3", "T_MKDIR", "mkdir", "mkdir "),
            _act("4", "T_DOT", "./", "./"),
            _act("6", "T_DOTDOT", "../", "../"),
            _act("8", "T_TAB_COMP", "Tab", None, key_name="TAB"),
            _act("9", "T_PWD", "pwd", "pwd"),
        ]
        tree["TERM_PATHS"] = make_submenu("TERM_PATHS", "RUTAS Y ARCHIVOS", paths)

        delete = [
            _act("1", "T_CANCEL", "Ctrl+C", None, key_name="CTRL_C"),
            _act("2", "T_CLEAR_LINE", "Ctrl+U", None, key_name="CTRL_U"),
            _act("3", "T_BACKSPACE", "Backspace", None, key_name="BACKSPACE"),
            _act("4", "T_CTRL_L", "Ctrl+L", None, key_name="CTRL_L"),
            _act("6", "T_RM", "rm", "rm "),
            _act("8", "T_KILL", "kill", "kill "),
            _act("9", "T_EXIT", "exit", "exit"),
        ]
        tree["TERM_DELETE"] = make_submenu("TERM_DELETE", "BORRAR / CANCELAR", delete)

        execs = [
            _act("1", "T_RUN_ENTER", "Enter", None, key_name="ENTER"),
            _act("2", "T_AND", "&&", " && "),
            _act("3", "T_PIPE", "|", " | "),
            _act("4", "T_HELP", "--help", " --help"),
            _act("6", "T_REDIRECT", ">", " > "),
            _act("8", "T_BG", "&", " &"),
            _act("9", "T_SEMI", ";", "; "),
        ]
        tree["TERM_EXEC"] = make_submenu("TERM_EXEC", "EJECUTAR (ENTER)", execs)

        ai = [
            _act("1", "T_AI_CMD", "Sugerir comando", "suggest command"),
            _act("2", "T_AI_COMMIT", "Commit msg", "feat: implement "),
            _act("3", "T_AI_FIX", "Fix commit", "fix: resolve "),
            _act("4", "T_AI_DOCS", "Docs commit", "docs: update "),
            _act("6", "T_AI_REFACTOR", "Refactor commit", "refactor: "),
            _act("8", "T_AI_TEST", "Test commit", "test: "),
            _act("9", "T_AI_CHORE", "Chore commit", "chore: "),
        ]
        tree["TERM_AI"] = make_submenu("TERM_AI", "IA TERMINAL / COMMITS", ai)

        root_items = [
            MenuAction("TERM_GIT_BASIC", "1: GIT BÁSICO", "Comandos Git básicos", "SUBMENU", submenu_id="TERM_GIT_BASIC", icon="flow"),
            MenuAction("TERM_GIT_SYNC", "2: GIT COMMIT / SYNC", "Commit y sincronización", "SUBMENU", submenu_id="TERM_GIT_SYNC", icon="format"),
            MenuAction("TERM_PYTHON", "3: PYTHON / TEST", "Python y tests", "SUBMENU", submenu_id="TERM_PYTHON", icon="function"),
            MenuAction("TERM_HISTORY", "4: HISTORIAL CONSOLA", "Historial de consola", "SUBMENU", submenu_id="TERM_HISTORY", icon="navigation"),
            None,
            MenuAction("TERM_PATHS", "6: RUTAS Y ARCHIVOS", "Rutas y archivos", "SUBMENU", submenu_id="TERM_PATHS", icon="variables"),
            MenuAction("TERM_DELETE", "7: BORRAR / CANCELAR", "Borrado y cancelación", "SUBMENU", submenu_id="TERM_DELETE", icon="edit"),
            MenuAction("TERM_EXEC", "8: EJECUTAR (ENTER)", "Ejecución", "SUBMENU", submenu_id="TERM_EXEC", icon="operators"),
            MenuAction("TERM_AI", "9: IA TERMINAL", "IA para terminal", "SUBMENU", submenu_id="TERM_AI", icon="ai_spark"),
        ]
        from eyede.actions.menu_trees import create_pause_action
        root_items[4] = create_pause_action("5")
        root = make_root("TERMINAL & GIT", root_items)
        tree["ROOT"] = root
        return tree

    def get_root_menu(self, language: Optional[str] = None) -> MenuNode:
        return self.get_menu_tree(language)["ROOT"]

    def get_ai_system_prompt(self, context_data: Optional[Dict[str, Any]] = None) -> str:
        return (
            "You are a terminal and Git assistant for a disabled programmer using eye-tracking. "
            "Suggest shell commands, Git operations, Python/test commands, and conventional commit messages. "
            "Return ONLY a JSON array of exactly 6 strings."
        )

    def get_heuristic_predictions(
        self, context_data: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        return [
            "git status",
            "git add .",
            "git commit -m \"\"",
            "pytest -v",
            "python main.py",
            "git push",
        ]


TerminalMode = TerminalGitMode
GitMode = TerminalGitMode
TERMINAL_MODE = TerminalGitMode
Terminal = TerminalGitMode
TerminalGit = TerminalGitMode
