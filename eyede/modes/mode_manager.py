"""
IDEye - Context Mode Manager (Phase 6)
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import QObject, pyqtSignal

try:
    from eyede.modes.base_mode import BaseMode
    from eyede.modes.coding_mode import CodingMode
    from eyede.modes.writing_mode import WritingMode
    from eyede.modes.terminal_git_mode import TerminalGitMode
    from eyede.modes.data_math_mode import DataMathMode
    from eyede.modes.ide_nav_mode import IdeNavMode
    from eyede.modes.sniper_mouse_mode import SniperMouseMode
except ImportError:  # pragma: no cover
    from modes.base_mode import BaseMode
    from modes.coding_mode import CodingMode
    from modes.writing_mode import WritingMode
    from modes.terminal_git_mode import TerminalGitMode
    from modes.data_math_mode import DataMathMode
    from modes.ide_nav_mode import IdeNavMode
    from modes.sniper_mouse_mode import SniperMouseMode


MODE_ORDER: List[str] = ["coding", "writing", "terminal", "data_math", "navigation", "sniper"]

MODE_CLASSES: Dict[str, type] = {
    "coding": CodingMode,
    "writing": WritingMode,
    "terminal": TerminalGitMode,
    "data_math": DataMathMode,
    "navigation": IdeNavMode,
    "sniper": SniperMouseMode,
}

# Friendly aliases accepted by set_mode
MODE_ALIASES: Dict[str, str] = {
    "code": "coding",
    "coding_mode": "coding",
    "write": "writing",
    "writing_mode": "writing",
    "docs": "writing",
    "terminal_git": "terminal",
    "git": "terminal",
    "terminal_mode": "terminal",
    "data": "data_math",
    "math": "data_math",
    "sql": "data_math",
    "latex": "data_math",
    "data_math_mode": "data_math",
    "nav": "navigation",
    "navigation_mode": "navigation",
    "read": "navigation",
    "ide_nav": "navigation",
    "sniper": "sniper",
    "sniper_mouse": "sniper",
    "mouse": "sniper",
    "francotirador": "sniper",
}

SOURCE_EXTENSIONS = {
    ".py", ".pyw", ".ts", ".tsx", ".js", ".jsx", ".rs", ".cpp", ".cc", ".cxx",
    ".hpp", ".h", ".c", ".go", ".java", ".kt", ".swift", ".cs",
}
DOC_EXTENSIONS = {".md", ".txt", ".rst", ".adoc"}
DATA_EXTENSIONS = {".sql", ".tex", ".json", ".yaml", ".yml", ".toml", ".xml", ".csv"}


class ModeManager(QObject):
    mode_changed = pyqtSignal(str, str, str)  # mode_id, display_name, theme_color

    def __init__(
        self,
        initial_mode: str = "coding",
        language: str = "PYTHON",
        auto_switch_enabled: bool = True,
        overlay: Any = None,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self.language: str = language
        self.auto_switch_enabled: bool = bool(auto_switch_enabled)
        self.auto_switch: bool = self.auto_switch_enabled
        self.overlay = overlay

        self._modes: Dict[str, BaseMode] = {}
        for mid, cls in MODE_CLASSES.items():
            try:
                self._modes[mid] = cls(language=language)
            except TypeError:
                self._modes[mid] = cls()

        self._current_mode_id: str = self._normalize_mode_id(initial_mode)
        # Emit initial? Keep False to avoid side effects during construction.
        self._manual_lock: bool = False

    # ------------------------------------------------------------------ #
    # Properties
    # ------------------------------------------------------------------ #
    @property
    def current_mode_id(self) -> str:
        return self._current_mode_id

    @current_mode_id.setter
    def current_mode_id(self, value: str) -> None:
        self._current_mode_id = self._normalize_mode_id(value)

    @property
    def current_mode(self) -> BaseMode:
        return self._modes[self._current_mode_id]

    @property
    def current(self) -> BaseMode:
        return self.current_mode

    @property
    def active_mode(self) -> BaseMode:
        return self.current_mode

    @property
    def active_mode_id(self) -> str:
        return self._current_mode_id

    @property
    def modes(self) -> Dict[str, BaseMode]:
        return dict(self._modes)

    @property
    def mode_ids(self) -> List[str]:
        return list(MODE_ORDER)

    @property
    def available_modes(self) -> List[str]:
        return list(MODE_ORDER)

    # ------------------------------------------------------------------ #
    # Mode switching
    # ------------------------------------------------------------------ #
    def _normalize_mode_id(self, mode_id: Any) -> str:
        if isinstance(mode_id, BaseMode):
            mode_id = mode_id.mode_id
        key = str(mode_id).strip().lower()
        if key in MODE_ALIASES:
            key = MODE_ALIASES[key]
        if key not in MODE_CLASSES:
            # Try direct mode_id attribute
            for mid, mode in self._modes.items():
                if str(getattr(mode, "mode_id", "")).lower() == key:
                    key = mid
                    break
        if key not in MODE_CLASSES:
            key = "coding"
        return key

    def set_mode(self, mode_id: Any, emit: bool = True, reset_tree: bool = True) -> str:
        new_id = self._normalize_mode_id(mode_id)
        if new_id == self._current_mode_id and not emit:
            return new_id
        self._current_mode_id = new_id
        # Sync language into mode object
        try:
            self._modes[new_id].language = self.language
        except Exception:
            pass
        if emit:
            mode = self._modes[new_id]
            self.mode_changed.emit(mode.mode_id, mode.display_name, mode.theme_color)
        return new_id

    def switch_mode(self, mode_id: Any, *args, **kwargs) -> str:
        return self.set_mode(mode_id, *args, **kwargs)

    def change_mode(self, mode_id: Any, *args, **kwargs) -> str:
        return self.set_mode(mode_id, *args, **kwargs)

    def activate_mode(self, mode_id: Any, *args, **kwargs) -> str:
        return self.set_mode(mode_id, *args, **kwargs)

    def cycle_next_mode(self) -> str:
        try:
            idx = MODE_ORDER.index(self._current_mode_id)
        except ValueError:
            idx = 0
        next_id = MODE_ORDER[(idx + 1) % len(MODE_ORDER)]
        return self.set_mode(next_id, emit=True)

    def cycle_mode(self) -> str:
        return self.cycle_next_mode()

    def cycle(self) -> str:
        return self.cycle_next_mode()

    def next_mode(self) -> str:
        return self.cycle_next_mode()

    def previous_mode(self) -> str:
        try:
            idx = MODE_ORDER.index(self._current_mode_id)
        except ValueError:
            idx = 0
        prev_id = MODE_ORDER[(idx - 1) % len(MODE_ORDER)]
        return self.set_mode(prev_id, emit=True)

    def set_auto_switch_enabled(self, enabled: bool) -> None:
        self.auto_switch_enabled = bool(enabled)
        self.auto_switch = self.auto_switch_enabled

    def set_auto_switch(self, enabled: bool) -> None:
        self.set_auto_switch_enabled(enabled)

    def toggle_auto_switch(self, enabled: Optional[bool] = None) -> bool:
        if enabled is None:
            self.auto_switch_enabled = not self.auto_switch_enabled
        else:
            self.auto_switch_enabled = bool(enabled)
        self.auto_switch = self.auto_switch_enabled
        return self.auto_switch_enabled

    def set_language(self, language: str) -> None:
        self.language = language
        for mode in self._modes.values():
            try:
                mode.language = language
            except Exception:
                pass

    # ------------------------------------------------------------------ #
    # Auto-switch logic
    # ------------------------------------------------------------------ #
    def determine_mode_from_state(self, state: Any) -> str:
        if not isinstance(state, dict):
            state = {}
        context = str(state.get("context") or state.get("editorContext") or "").strip().lower()
        if context in {"terminal", "active_terminal", "integrated_terminal"}:
            return "terminal"
        if context in {"comment", "prose", "markdown", "docstring", "documentation"}:
            return "writing"

        file_path = state.get("filePath") or state.get("file_path") or state.get("activeFile") or state.get("file")
        ext = os.path.splitext(str(file_path or ""))[1].lower()

        if ext in DOC_EXTENSIONS:
            return "writing"
        if ext in DATA_EXTENSIONS:
            return "data_math"
        if ext in SOURCE_EXTENSIONS:
            # If cursor explicitly in comment/prose, writing already handled above.
            if context in {"comment", "prose", "docstring"}:
                return "writing"
            return "coding"

        # Fallbacks based on languageId
        language_id = state.get("languageId") or state.get("language_id")
        if isinstance(language_id, str):
            lid = language_id.lower()
            if lid in {"markdown", "plaintext", "restructuredtext"}:
                return "writing"
            if lid in {"sql", "latex", "json", "yaml", "yml", "toml", "xml", "csv"}:
                return "data_math"
            if lid in {"python", "typescript", "javascript", "rust", "cpp", "c", "go", "java", "kotlin", "swift", "csharp"}:
                return "coding"

        # Explicit mode hint
        hint = state.get("mode") or state.get("contextMode")
        if hint:
            try:
                return self._normalize_mode_id(hint)
            except Exception:
                pass

        return self._current_mode_id

    def handle_editor_state(self, state: Any) -> str:
        new_mode = self.determine_mode_from_state(state)
        if self.auto_switch_enabled and new_mode != self._current_mode_id:
            self.set_mode(new_mode, emit=True)
        return new_mode if self.auto_switch_enabled else self._current_mode_id

    def on_editor_state_received(self, state: Any) -> str:
        return self.handle_editor_state(state)

    def process_editor_state(self, state: Any) -> str:
        return self.handle_editor_state(state)

    def on_vscode_editor_state(self, state: Any) -> str:
        return self.handle_editor_state(state)

    def handle_vscode_state(self, state: Any) -> str:
        return self.handle_editor_state(state)

    def auto_switch_from_state(self, state: Any) -> str:
        return self.handle_editor_state(state)

    def process_websocket_state(self, state: Any) -> str:
        return self.handle_editor_state(state)

    def process_websocket_message(self, state: Any) -> str:
        return self.handle_editor_state(state)

    def handle_websocket_state(self, state: Any) -> str:
        return self.handle_editor_state(state)

    def on_websocket_state(self, state: Any) -> str:
        return self.handle_editor_state(state)

    # ------------------------------------------------------------------ #
    # Menu / AI delegation
    # ------------------------------------------------------------------ #
    def get_current_mode(self) -> BaseMode:
        return self.current_mode

    def get_mode(self, mode_id: Any) -> BaseMode:
        return self._modes[self._normalize_mode_id(mode_id)]

    def get_root_menu(self, language: Optional[str] = None) -> Any:
        lang = language or self.language
        return self.current_mode.get_root_menu(lang)

    def get_menu_tree(self, language: Optional[str] = None) -> Dict[str, Any]:
        lang = language or self.language
        return self.current_mode.get_menu_tree(lang)

    def get_ai_system_prompt(self, context_data: Optional[Dict[str, Any]] = None) -> str:
        return self.current_mode.get_ai_system_prompt(context_data)

    def get_heuristic_predictions(
        self, context_data: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        return self.current_mode.get_heuristic_predictions(context_data)

    def get_theme_color(self) -> str:
        return self.current_mode.theme_color

    def get_display_name(self) -> str:
        return self.current_mode.display_name


# Compatibility aliases
ModeController = ModeManager
ContextModeManager = ModeManager
MODE_MANAGER = ModeManager
ModeSwitcher = ModeManager
ContextModes = ModeManager
MODES = MODE_CLASSES
ALL_MODES = MODE_CLASSES
MODE_REGISTRY = MODE_CLASSES
MODE_ORDER_LIST = MODE_ORDER
ContextMode = BaseMode
Mode = BaseMode
MODE_CODING = "coding"
MODE_WRITING = "writing"
MODE_TERMINAL = "terminal"
MODE_DATA_MATH = "data_math"
MODE_NAVIGATION = "navigation"
MODE_IDS = MODE_ORDER
DEFAULT_MODE = "coding"
CODING = "coding"
WRITING = "writing"
TERMINAL = "terminal"
DATA_MATH = "data_math"
NAVIGATION = "navigation"
NAV = "navigation"
TERMINAL_GIT = "terminal"
DATA = "data_math"
MATH = "data_math"
SQL = "data_math"
LATEX = "data_math"
NAVIGATION_READ = "navigation"
IDE_NAV = "navigation"
READ = "navigation"
# Mode class aliases
CodingModeAlias = CodingMode
WritingModeAlias = WritingMode
TerminalModeAlias = TerminalGitMode
DataModeAlias = DataMathMode
NavModeAlias = IdeNavMode
# Export mode classes at module level for convenience
__all__ = [
    "ModeManager",
    "BaseMode",
    "CodingMode",
    "WritingMode",
    "TerminalGitMode",
    "DataMathMode",
    "IdeNavMode",
    "MODE_ORDER",
    "MODE_CLASSES",
]
