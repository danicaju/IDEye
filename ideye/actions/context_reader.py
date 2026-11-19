"""
IDEye - Live AST & Context Reader Module (Phase 4)
Non-intrusive source context reader with error-tolerant dual AST + Regex extraction
of variables, arguments, functions, and classes.
Guarantees crash-free execution against SyntaxError, UnicodeDecodeError, and missing files.
"""

import ast
import os
import re
import time
import bisect
from typing import Optional, List, Set, Tuple, Dict, Any

try:
    import ideye.config as config
except ImportError:
    import config

try:
    from ideye.actions.language_support import (
        LANG_PYTHON,
        LANG_TYPESCRIPT,
        LANG_RUST,
        LANG_CPP,
        LANG_GO,
        SUPPORTED_LANGUAGES,
        LANGUAGE_EXTENSIONS,
        LANGUAGE_KEYWORDS,
        detect_language_from_path,
        detect_language_from_id,
        normalize_language,
        get_language_display_name,
        get_language_badge,
    )
except ImportError:
    from actions.language_support import (
        LANG_PYTHON,
        LANG_TYPESCRIPT,
        LANG_RUST,
        LANG_CPP,
        LANG_GO,
        SUPPORTED_LANGUAGES,
        LANGUAGE_EXTENSIONS,
        LANGUAGE_KEYWORDS,
        detect_language_from_path,
        detect_language_from_id,
        normalize_language,
        get_language_display_name,
        get_language_badge,
    )

# Python reserved keywords and internal names to filter out from user symbol lists
PYTHON_KEYWORDS: Set[str] = LANGUAGE_KEYWORDS.get(LANG_PYTHON, {
    "False", "None", "True", "and", "as", "assert", "async", "await", "break",
    "class", "continue", "def", "del", "elif", "else", "except", "finally",
    "for", "from", "global", "if", "import", "in", "is", "lambda", "nonlocal",
    "not", "or", "pass", "raise", "return", "try", "while", "with", "yield",
    "self", "cls",
})
from ideye.actions.context_buffer import DocumentShadowBuffer  # noqa: F401
from ideye.actions.context_symbols import PYTHON_KEYWORDS, SymbolExtractionMixin  # noqa: F401
from ideye.actions.context_types import *  # noqa: F401,F403
from ideye.actions.context_detect import detect_syntactic_context  # noqa: F401


class ContextReader(SymbolExtractionMixin):
    """
    Non-intrusive live context reader for the active code editing session.
    Detects or links the active file across Python, TypeScript/JS, Rust, C++, and Go,
    and dynamically extracts local symbols and active syntactic contexts.
    """

    def __init__(
        self,
        workspace_dir: Optional[str] = None,
        active_file: Optional[str] = None,
        auto_detect: Optional[bool] = None,
        default_language: Optional[str] = None,
    ):
        raw_ws = workspace_dir if workspace_dir is not None else getattr(config, "DEFAULT_WORKSPACE_DIR", os.getcwd())
        self.workspace_dir: str = os.path.abspath(raw_ws) if raw_ws else os.getcwd()

        raw_af = active_file if active_file is not None else getattr(config, "ACTIVE_FILE_PATH", None)
        self.active_file_path: Optional[str] = os.path.abspath(raw_af) if raw_af else None

        self.auto_detect: bool = auto_detect if auto_detect is not None else getattr(config, "AUTO_DETECT_RECENT_FILE", True)
        self._cached_detected_file: Optional[str] = None
        self._last_detect_time: float = 0.0

        raw_lang = default_language or getattr(config, "DEFAULT_PROGRAMMING_LANGUAGE", LANG_PYTHON)
        self.active_language: str = normalize_language(raw_lang)
        self.document_buffer = DocumentShadowBuffer()
        self.document_context_active: bool = False
        self.editor_state: Dict[str, Any] = {}

    def set_language(self, language: str) -> None:
        """Sets the active programming language."""
        self.active_language = normalize_language(language)

    def set_active_language(self, language: str) -> None:
        """Sets the active programming language (alias for set_language)."""
        self.set_language(language)

    def get_active_language(self) -> str:
        """Returns active language, prioritizing explicitly linked or detected file."""
        target_file = self.get_active_file()
        if target_file:
            return detect_language_from_path(target_file)
        return self.active_language

    def detect_active_language(self) -> str:
        """Backward-compatible alias for get_active_language()."""
        return self.get_active_language()

    def set_document_context(self, title: str, process: str = "") -> bool:
        """Activates the shadow buffer for Google Docs, Notion, Overleaf or Word."""
        active = DocumentShadowBuffer.is_document_window(title, process)
        self.document_context_active = bool(active)
        if active:
            self.document_buffer.update_title(title, process)
        return self.document_context_active

    def clear_document_context(self) -> None:
        self.document_context_active = False
        self.document_buffer.update_title("", "")

    def record_document_text(self, text: str) -> None:
        if self.document_context_active:
            self.document_buffer.append(text)

    def get_document_context(self, max_chars: int = 4000) -> Dict[str, Any]:
        snapshot = self.document_buffer.snapshot()
        snapshot["text"] = self.document_buffer.recent(max_chars)
        snapshot["active"] = self.document_context_active
        return snapshot

    def update_editor_snapshot(self, state: Optional[Dict[str, Any]]) -> None:
        self.editor_state = dict(state or {})
        if self.editor_state.get("filePath") or self.editor_state.get("file_path"):
            self.document_context_active = False

    def get_editor_context(self) -> Dict[str, Any]:
        state = dict(self.editor_state or {})
        return {
            "prefix_lines": state.get("prefix_lines") or state.get("prefixLines") or [],
            "current_line": state.get("current_line") or state.get("lineText") or "",
            "suffix_lines": state.get("suffix_lines") or state.get("suffixLines") or [],
            "active_selection": state.get("active_selection") or state.get("selection") or "",
            "local_symbols": state.get("local_symbols") or state.get("localSymbols") or [],
            "diagnostics": state.get("diagnostics") or [],
        }

    def set_active_file(self, file_path: Optional[str]) -> None:
        """Explicitly links or unlinks an active file for context reading."""
        self._cached_detected_file = None
        self._last_detect_time = 0.0
        if file_path:
            self.active_file_path = os.path.abspath(file_path)
            self.active_language = detect_language_from_path(self.active_file_path)
        else:
            self.active_file_path = None

    def set_workspace_dir(self, workspace_dir: str) -> None:
        """Updates the workspace root directory for auto-detecting recent files."""
        if workspace_dir and os.path.isdir(workspace_dir):
            self.workspace_dir = os.path.abspath(workspace_dir)
            self._cached_detected_file = None
            self._last_detect_time = 0.0

    def detect_active_file(self) -> Optional[str]:
        """
        Scans workspace_dir for the most recently modified code file across
        all supported languages (Python, TypeScript, Rust, C++, Go).
        Skips hidden dirs, virtual environments, caches, and test artifacts.
        Throttles redundant recursive disk scans within 1.5 seconds.
        """
        if self.active_file_path and os.path.isfile(self.active_file_path):
            return self.active_file_path

        now = time.time()
        if self._cached_detected_file and (now - self._last_detect_time < 1.5):
            if os.path.isfile(self._cached_detected_file):
                return self._cached_detected_file

        if not self.auto_detect or not os.path.isdir(self.workspace_dir):
            return None

        ignored_dirs = {
            ".git", "__pycache__", ".pytest_cache", ".venv", "venv", "env",
            "node_modules", "dist", "build", ".idea", ".vscode", ".agents",
            "tests", "test", "testing", "docs", "doc", "ideye", "target",
            "vscode-extension",
        }

        latest_file: Optional[str] = None
        latest_mtime: float = -1.0

        try:
            for root, dirs, files in os.walk(self.workspace_dir):
                # Filter out ignored directories in-place to avoid descending into them
                dirs[:] = [
                    d for d in dirs
                    if d.lower() not in ignored_dirs
                    and not d.startswith(".")
                    and not d.lower().startswith("test")
                ]

                for f in files:
                    ext = os.path.splitext(f)[1].lower()
                    if ext in LANGUAGE_EXTENSIONS:
                        f_lower = f.lower()
                        ignored_root_files = {
                            "build_app.py", "create_desktop_shortcut.py", "setup.py",
                            "conftest.py", "main.py", "config.py",
                        }
                        if f_lower in ignored_root_files or f_lower.startswith("test_") or f_lower.endswith("_test.go") or f_lower == "conftest.py":
                            continue

                        full_path = os.path.join(root, f)
                        try:
                            rel_parts = [p.lower() for p in os.path.relpath(full_path, self.workspace_dir).split(os.sep)]
                            if any(p in ignored_dirs or p.startswith("test") for p in rel_parts[:-1]):
                                continue
                        except Exception:
                            pass
                        try:
                            mtime = os.path.getmtime(full_path)
                            if mtime > latest_mtime:
                                latest_mtime = mtime
                                latest_file = full_path
                        except OSError:
                            continue
        except Exception:
            pass

        self._cached_detected_file = latest_file
        self._last_detect_time = time.time()
        return latest_file

    def get_active_file(self) -> Optional[str]:
        """Returns the currently active file, auto-detecting if none explicitly set."""
        if self.active_file_path and os.path.isfile(self.active_file_path):
            return self.active_file_path
        if self.auto_detect:
            detected = self.detect_active_file()
            if detected:
                return detected
        return self.active_file_path

    def read_file_content(self, file_path: Optional[str] = None) -> str:
        """
        Reads file content on disk using utf-8 with error-ignoring.
        Guarantees zero crashes on UnicodeDecodeError, FileNotFoundError, PermissionError, or missing file.
        """
        target = file_path or self.get_active_file()
        if not target:
            return ""

        try:
            with open(target, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        except (FileNotFoundError, PermissionError, OSError):
            return ""
        except Exception:
            return ""

    def get_recent_context(self, max_lines: int = 40, file_path: Optional[str] = None) -> str:
        """
        Returns the last `max_lines` from the active file.
        Prioritizes live editor snapshot (VS Code / shadow buffer) when active.
        Safe against empty files, syntax errors, and missing files.
        """
        if file_path is None and self.editor_state:
            prefix = self.editor_state.get("prefix_lines") or self.editor_state.get("prefixLines") or []
            curr = self.editor_state.get("current_line") or self.editor_state.get("lineText") or ""
            combo = list(prefix)
            if curr:
                combo.append(curr)
            if combo:
                return "\n".join(combo[-max_lines:])

        content = self.read_file_content(file_path)
        if not content:
            return ""

        lines = content.splitlines()
        recent_lines = lines[-max_lines:] if len(lines) > max_lines else lines
        return "\n".join(recent_lines)

    def get_last_line(self, file_path: Optional[str] = None) -> str:
        """Returns the last non-empty stripped line from the active file or live editor state."""
        if file_path is None and self.editor_state:
            curr = (self.editor_state.get("current_line") or self.editor_state.get("lineText") or "").strip()
            if curr and not curr.startswith("#"):
                return curr
        context = self.get_recent_context(max_lines=20, file_path=file_path)
        if not context:
            return ""
        for line in reversed(context.splitlines()):
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                return stripped
        return ""

    def detect_syntactic_context(
        self,
        file_path: Optional[str] = None,
        source_code: Optional[str] = None,
        language: Optional[str] = None,
    ) -> "SyntacticContext":
        """
        Detects active syntactic context (e.g. FUNCTION_SIGNATURE, TRY_BLOCK, CLASS_BODY,
        IF_BLOCK, LOOP_BLOCK, WITH_BLOCK, GENERAL) for live adaptive AST menus across
        all supported programming languages (Python, TypeScript, Rust, C++, Go).
        """
        if language is not None:
            target_lang = normalize_language(language)
        elif file_path is not None:
            target_lang = detect_language_from_path(file_path)
        elif source_code is not None:
            target_lang = self.active_language
        else:
            target_lang = self.get_active_language()

        if source_code is not None:
            return detect_syntactic_context(source_code=source_code, language=target_lang)
        target = file_path or self.get_active_file()
        if target:
            content = self.read_file_content(target)
            return detect_syntactic_context(file_path=target, source_code=content, language=target_lang)
        return detect_syntactic_context(source_code="", language=target_lang)


# ==============================================================================
# Syntactic Context Constants & Types (Phase Extra - Option A: Dynamic AST Menus)
# ==============================================================================
