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


class DocumentShadowBuffer:
    """Bounded in-memory mirror of text written into Google Docs or web editors."""

    DOCUMENT_KEYWORDS = (
        "google docs",
        "documentos de google",
        "notion",
        "overleaf",
        "word",
        "onedrive",
        "sharepoint",
    )

    def __init__(self, max_chars: int = 12000) -> None:
        self.max_chars = max(500, int(max_chars))
        self.title: str = ""
        self.process: str = ""
        self._text: str = ""

    @classmethod
    def is_document_window(cls, title: str, process: str = "") -> bool:
        haystack = f"{title or ''} {process or ''}".lower()
        return any(keyword in haystack for keyword in cls.DOCUMENT_KEYWORDS)

    def update_title(self, title: str, process: str = "") -> None:
        self.title = str(title or "")[:200]
        self.process = str(process or "")[:120]

    def append(self, text: str) -> None:
        value = str(text or "")
        if not value:
            return
        combined = (self._text + value)[-self.max_chars :]
        self._text = combined

    def recent(self, max_chars: int = 4000) -> str:
        limit = max(1, min(self.max_chars, int(max_chars)))
        return self._text[-limit:]

    def clear(self) -> None:
        self._text = ""

    def snapshot(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "process": self.process,
            "text": self.recent(),
            "has_text": bool(self._text),
        }


class ContextReader:
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

    def extract_local_symbols(
        self,
        max_symbols: int = 12,
        file_path: Optional[str] = None,
        source_code: Optional[str] = None,
        language: Optional[str] = None,
    ) -> List[str]:
        """
        Dual AST + Regex extractor:
        Tolerant to SyntaxError (unclosed parens, incomplete lines).
        Extracts variables, arguments, functions, and classes across
        Python, TypeScript, Rust, C++, and Go.
        Returns up to `max_symbols` (default 12) unique symbols, prioritized by recency.
        Prioritizes live VS Code editor state symbols when available.
        """
        if source_code is None and file_path is None and self.editor_state:
            live = self.editor_state.get("local_symbols") or self.editor_state.get("localSymbols") or []
            if live and isinstance(live, list):
                valid_live = [s for s in live if isinstance(s, str) and s.isidentifier()]
                if valid_live:
                    return valid_live[:max_symbols]
            # When live editor state is active but no symbols were passed by extension,
            # extract symbols from the active buffer lines
            buf_lines = (
                (self.editor_state.get("prefix_lines") or self.editor_state.get("prefixLines") or []) +
                [self.editor_state.get("current_line") or self.editor_state.get("lineText") or ""] +
                (self.editor_state.get("suffix_lines") or self.editor_state.get("suffixLines") or [])
            )
            buf_text = "\n".join(l for l in buf_lines if l)
            if buf_text.strip():
                source_code = buf_text
            elif self.editor_state.get("filePath") or self.editor_state.get("hasActiveEditor"):
                return []
        try:
            content = source_code if source_code is not None else self.read_file_content(file_path)
        except (FileNotFoundError, PermissionError, OSError):
            return []
        if not content or not content.strip():
            return []

        target_lang = normalize_language(language or (detect_language_from_path(file_path) if file_path else self.get_active_language()))
        keywords = LANGUAGE_KEYWORDS.get(target_lang, PYTHON_KEYWORDS)

        # Multi-language extraction for non-Python sources
        if target_lang != LANG_PYTHON:
            seen_ml: Set[str] = set()
            unique_ml: List[str] = []
            lines = content.splitlines()
            for line in reversed(lines):
                clean = re.sub(r'//.*$', '', line)
                clean = re.sub(r'/\*.*?\*/', '', clean)
                clean = re.sub(r'(["\'])(?:(?=(\\?))\2.)*?\1', '', clean)
                for m in re.finditer(r'\b([a-zA-Z_]\w*)\b', clean):
                    sym = m.group(1)
                    if sym not in seen_ml and sym not in keywords and not sym.startswith("__") and len(sym) > 1 and not sym.isdigit():
                        seen_ml.add(sym)
                        unique_ml.append(sym)
                        if len(unique_ml) >= max_symbols:
                            return unique_ml
            return unique_ml

        # Collect tuples: (line_no, col_offset, symbol_name)
        ast_items: List[Tuple[int, int, str]] = []
        regex_items: List[Tuple[int, int, str]] = []


        # 1. AST Extraction (if syntax is valid or partially valid)
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                lno = getattr(node, "lineno", 0)
                col = getattr(node, "col_offset", 0)
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if not node.name.startswith("__"):
                        ast_items.append((lno, col, node.name))
                    for arg in node.args.args:
                        arg_lno = getattr(arg, "lineno", lno)
                        arg_col = getattr(arg, "col_offset", col)
                        if arg.arg not in PYTHON_KEYWORDS and not arg.arg.startswith("__"):
                            ast_items.append((arg_lno, arg_col, arg.arg))
                elif isinstance(node, ast.ClassDef):
                    if not node.name.startswith("__"):
                        ast_items.append((lno, col, node.name))
                elif isinstance(node, ast.Assign):
                    for target in node.targets:
                        self._extract_ast_targets(target, lno, col, ast_items)
                elif isinstance(node, ast.AnnAssign):
                    self._extract_ast_targets(node.target, lno, col, ast_items)
                elif isinstance(node, ast.AugAssign):
                    self._extract_ast_targets(node.target, lno, col, ast_items)
                elif isinstance(node, ast.NamedExpr):
                    self._extract_ast_targets(node.target, lno, col, ast_items)
                elif isinstance(node, ast.For):
                    self._extract_ast_targets(node.target, lno, col, ast_items)
                elif isinstance(node, (ast.With, ast.AsyncWith)):
                    for item in node.items:
                        if item.optional_vars:
                            self._extract_ast_targets(item.optional_vars, lno, col, ast_items)
                elif isinstance(node, ast.ExceptHandler):
                    if node.name and node.name not in PYTHON_KEYWORDS and not node.name.startswith("__"):
                        ast_items.append((lno, col, node.name))
        except SyntaxError:
            # Expected during live editing! Handled cleanly by Regex fallback below
            pass
        except Exception:
            pass

        # 2. Regex Extraction (Always runs to complement AST or rescue broken syntax)
        line_starts = [0]
        for m in re.finditer(r'\n', content):
            line_starts.append(m.end())

        def _get_pos(char_idx: int) -> Tuple[int, int]:
            l_idx = bisect.bisect_right(line_starts, char_idx) - 1
            lno = l_idx + 1
            col = char_idx - line_starts[l_idx]
            return lno, col

        # Function definitions: def func_name(...)
        for m in re.finditer(r'\bdef\s+([a-zA-Z_]\w*)\s*\(?', content):
            sym = m.group(1)
            if sym not in PYTHON_KEYWORDS and not sym.startswith("__"):
                lno, col = _get_pos(m.start(1))
                regex_items.append((lno, col, sym))

        # Function arguments in signature: def foo(arg1, arg2: int = 0)
        # Supports both closed signatures and unclosed signatures being typed
        for m in re.finditer(r'\bdef\s+\w+\s*\((?:([^)\n]*?)\)|([^)\n]*))', content):
            raw_args = m.group(1) if m.group(1) is not None else m.group(2)
            arg_group_idx = 1 if m.group(1) is not None else 2
            start_offset = m.start(arg_group_idx)
            if raw_args:
                for arg_m in re.finditer(r'\b([a-zA-Z_]\w*)\b', raw_args):
                    arg_name = arg_m.group(1)
                    if arg_name not in PYTHON_KEYWORDS and not arg_name.startswith("__"):
                        lno, col = _get_pos(start_offset + arg_m.start(1))
                        regex_items.append((lno, col, arg_name))

        # Class definitions: class ClassName(...) or class ClassName:
        for m in re.finditer(r'\bclass\s+([a-zA-Z_]\w*)\b', content):
            sym = m.group(1)
            if sym not in PYTHON_KEYWORDS and not sym.startswith("__"):
                lno, col = _get_pos(m.start(1))
                regex_items.append((lno, col, sym))

        # For loops: for var_name in ...
        for m in re.finditer(r'\bfor\s+([a-zA-Z_]\w*)\s+in\b', content):
            sym = m.group(1)
            if sym not in PYTHON_KEYWORDS and not sym.startswith("__"):
                lno, col = _get_pos(m.start(1))
                regex_items.append((lno, col, sym))

        # Assignments: var_name = ... or var_name: type = ... or var_name += ...
        for m in re.finditer(r'(?:^|[\n;,])\s*([a-zA-Z_]\w*)\s*(?::\s*[^=]+)?\s*[\+\-\*/]?=(?!=)', content):
            sym = m.group(1)
            if sym not in PYTHON_KEYWORDS and not sym.startswith("__"):
                lno, col = _get_pos(m.start(1))
                regex_items.append((lno, col, sym))

        # Recent identifiers in last 30 lines (usage in expressions)
        lines = content.splitlines()
        recent_lines = lines[-30:] if len(lines) > 30 else lines
        start_line_no = max(1, len(lines) - len(recent_lines) + 1)
        for idx, line in enumerate(recent_lines):
            cur_lno = start_line_no + idx
            clean_line = re.sub(r'#.*$', '', line)
            clean_line = re.sub(r'(["\'])(?:(?=(\\?))\2.)*?\1', '', clean_line)
            for wm in re.finditer(r'\b[a-zA-Z_]\w*\b', clean_line):
                w = wm.group(0)
                if w not in PYTHON_KEYWORDS and not w.startswith("__") and len(w) > 1:
                    regex_items.append((cur_lno, wm.start(), w))

        # 3. Combine, Prioritize by Recency (Descending Line & Column), and Deduplicate
        all_items = ast_items + regex_items
        all_items.sort(key=lambda x: (x[0], x[1]), reverse=True)

        seen: Set[str] = set()
        unique_symbols: List[str] = []
        for _, _, sym in all_items:
            if sym not in seen and sym not in PYTHON_KEYWORDS and not sym.startswith("__"):
                seen.add(sym)
                unique_symbols.append(sym)
                if len(unique_symbols) == max_symbols:
                    break

        return unique_symbols

    def _extract_ast_targets(
        self,
        target: Optional[ast.AST],
        lno: int,
        col: int,
        out_list: List[Tuple[int, int, str]],
    ) -> None:
        """Helper to recursively extract variable names and positions from AST assignment targets."""
        if target is None:
            return
        t_lno = getattr(target, "lineno", lno)
        t_col = getattr(target, "col_offset", col)
        if isinstance(target, ast.Name):
            if target.id not in PYTHON_KEYWORDS and not target.id.startswith("__"):
                out_list.append((t_lno, t_col, target.id))
        elif isinstance(target, (ast.Tuple, ast.List)):
            for elt in target.elts:
                self._extract_ast_targets(elt, t_lno, t_col, out_list)
        elif isinstance(target, ast.Starred):
            self._extract_ast_targets(target.value, t_lno, t_col, out_list)
        elif isinstance(target, ast.Attribute):
            if isinstance(target.value, ast.Name) and target.value.id == "self":
                if target.attr not in PYTHON_KEYWORDS and not target.attr.startswith("__"):
                    out_list.append((t_lno, t_col, target.attr))

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
CONTEXT_FUNCTION_SIGNATURE: str = "FUNCTION_SIGNATURE"
CONTEXT_TRY_BLOCK: str = "TRY_BLOCK"
CONTEXT_CLASS_BODY: str = "CLASS_BODY"
CONTEXT_IF_BLOCK: str = "IF_BLOCK"
CONTEXT_LOOP_BLOCK: str = "LOOP_BLOCK"
CONTEXT_WITH_BLOCK: str = "WITH_BLOCK"
CONTEXT_GENERAL: str = "GENERAL"


class SyntacticContext(dict):
    """
    Represents the active syntactic context detected in the source code.
    Subclasses dict for 100% dictionary compatibility while supporting attribute access.
    """
    def __init__(
        self,
        context: str,
        line: str = "",
        indent: int = 0,
        details: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        data = {
            "context": context,
            "line": line,
            "indent": indent,
            "details": details or {},
        }
        data.update(kwargs)
        super().__init__(data)

    @property
    def context(self) -> str:
        return self["context"]

    @property
    def line(self) -> str:
        return self["line"]

    @property
    def indent(self) -> int:
        return self["indent"]

    @property
    def details(self) -> Dict[str, Any]:
        return self["details"]

    def to_dict(self) -> Dict[str, Any]:
        return dict(self)


def detect_syntactic_context(
    file_path: Optional[str] = None,
    source_code: Optional[str] = None,
    language: Optional[str] = None,
) -> SyntacticContext:
    """
    Detects the active syntactic construct from the file path or raw source code.
    Multi-language support for Python, TypeScript/JS, Rust, C++, and Go.
    Robust against SyntaxError and incomplete lines being typed.

    Contexts detected:
    - FUNCTION_SIGNATURE: writing function header
    - TRY_BLOCK: inside try / catch / match / error check
    - CLASS_BODY: inside class, struct, impl, or interface
    - IF_BLOCK: inside if / elif / else
    - LOOP_BLOCK: inside for / while / loop
    - WITH_BLOCK: inside with
    - GENERAL: default context when no specific construct is active
    """
    target_lang = normalize_language(language or (detect_language_from_path(file_path) if file_path else LANG_PYTHON))

    content = ""
    if source_code is not None:
        content = source_code
    elif file_path:
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except (FileNotFoundError, PermissionError, OSError):
            return SyntacticContext(CONTEXT_GENERAL, line="", indent=0)
        except Exception:
            return SyntacticContext(CONTEXT_GENERAL, line="", indent=0)
    else:
        reader = ContextReader()
        content = reader.read_file_content()

    if not content or not content.strip():
        return SyntacticContext(CONTEXT_GENERAL, line="", indent=0)

    lines = content.splitlines()
    if not lines:
        return SyntacticContext(CONTEXT_GENERAL, line="", indent=0)

    comment_pattern = r'#.*$' if target_lang == LANG_PYTHON else r'//.*$'

    # Find the last non-empty line (ignoring trailing comments)
    last_non_empty_idx = -1
    for i in range(len(lines) - 1, -1, -1):
        stripped = lines[i].strip()
        if stripped:
            if target_lang == LANG_PYTHON and not stripped.startswith("#"):
                last_non_empty_idx = i
                break
            elif target_lang != LANG_PYTHON and not stripped.startswith("//") and not stripped.startswith("/*") and not stripped.startswith("*"):
                last_non_empty_idx = i
                break

    if last_non_empty_idx == -1:
        return SyntacticContext(CONTEXT_GENERAL, line="", indent=0)

    last_line = lines[last_non_empty_idx]
    stripped_last = last_line.strip()
    last_indent = len(last_line) - len(last_line.lstrip())

    clean_last = re.sub(comment_pattern, '', last_line).strip()
    if target_lang != LANG_PYTHON:
        clean_last = re.sub(r'/\*.*?\*/', '', clean_last).strip()
    clean_last_no_str = re.sub(r'(["\'])(?:(?=(\\?))\2.)*?\1', '', clean_last)

    # -------------------------------------------------------------------------
    # MULTI-LANGUAGE SYNTACTIC CHECKS FOR NON-PYTHON LANGUAGES
    # -------------------------------------------------------------------------
    if target_lang == LANG_TYPESCRIPT:
        if re.search(r'^\s*(?:export\s+)?(?:async\s+)?function\b', clean_last) or \
           re.search(r'^\s*(?:const|let|var)\s+\w+\s*=\s*(?:async\s*)?\([^)]*$', clean_last) or \
           re.search(r'^\s*constructor\s*\(', clean_last):
            return SyntacticContext(CONTEXT_FUNCTION_SIGNATURE, line=stripped_last, indent=last_indent)
        if re.search(r'^\s*try\b', clean_last) or re.search(r'^\s*(?:catch|finally)\b', clean_last):
            return SyntacticContext(CONTEXT_TRY_BLOCK, line=stripped_last, indent=last_indent)
        if re.search(r'^\s*(?:export\s+)?(?:abstract\s+)?(?:class|interface|type)\b', clean_last):
            return SyntacticContext(CONTEXT_CLASS_BODY, line=stripped_last, indent=last_indent)
        if re.search(r'^\s*(?:if|else\s+if)\b', clean_last):
            return SyntacticContext(CONTEXT_IF_BLOCK, line=stripped_last, indent=last_indent)
        if re.search(r'^\s*(?:for|while|do)\b', clean_last):
            return SyntacticContext(CONTEXT_LOOP_BLOCK, line=stripped_last, indent=last_indent)

        # Enclosing brace block scan
        for prev_idx in range(last_non_empty_idx - 1, max(-1, last_non_empty_idx - 25), -1):
            p_line = re.sub(comment_pattern, '', lines[prev_idx]).strip()
            if not p_line:
                continue
            net_braces = sum(lines[k].count('{') - lines[k].count('}') for k in range(prev_idx, last_non_empty_idx + 1))
            if net_braces > 0:
                if re.search(r'^\s*try\b', p_line) or re.search(r'^\s*(?:catch|finally)\b', p_line):
                    return SyntacticContext(CONTEXT_TRY_BLOCK, line=p_line, indent=last_indent)
                if re.search(r'^\s*(?:export\s+)?(?:abstract\s+)?(?:class|interface|type)\b', p_line):
                    return SyntacticContext(CONTEXT_CLASS_BODY, line=p_line, indent=last_indent)
                if re.search(r'^\s*(?:if|else\s+if)\b', p_line):
                    return SyntacticContext(CONTEXT_IF_BLOCK, line=p_line, indent=last_indent)
                if re.search(r'^\s*(?:for|while|do)\b', p_line):
                    return SyntacticContext(CONTEXT_LOOP_BLOCK, line=p_line, indent=last_indent)
                break
        return SyntacticContext(CONTEXT_GENERAL, line=stripped_last, indent=last_indent)

    elif target_lang == LANG_RUST:
        if re.search(r'^\s*(?:pub(?:\([^)]*\))?\s+)?(?:async\s+)?fn\b', clean_last):
            return SyntacticContext(CONTEXT_FUNCTION_SIGNATURE, line=stripped_last, indent=last_indent)
        if re.search(r'^\s*match\b', clean_last):
            return SyntacticContext(CONTEXT_TRY_BLOCK, line=stripped_last, indent=last_indent, details={"type": "match"})
        if re.search(r'^\s*(?:pub(?:\([^)]*\))?\s+)?(?:impl|struct|enum|trait)\b', clean_last):
            return SyntacticContext(CONTEXT_CLASS_BODY, line=stripped_last, indent=last_indent)
        if re.search(r'^\s*(?:if|else\s+if)\b', clean_last):
            return SyntacticContext(CONTEXT_IF_BLOCK, line=stripped_last, indent=last_indent)
        if re.search(r'^\s*(?:for|while|loop)\b', clean_last):
            return SyntacticContext(CONTEXT_LOOP_BLOCK, line=stripped_last, indent=last_indent)

        # Enclosing brace block scan
        for prev_idx in range(last_non_empty_idx - 1, max(-1, last_non_empty_idx - 25), -1):
            p_line = re.sub(comment_pattern, '', lines[prev_idx]).strip()
            if not p_line:
                continue
            net_braces = sum(lines[k].count('{') - lines[k].count('}') for k in range(prev_idx, last_non_empty_idx + 1))
            if net_braces > 0:
                if re.search(r'^\s*match\b', p_line):
                    return SyntacticContext(CONTEXT_TRY_BLOCK, line=p_line, indent=last_indent, details={"type": "match"})
                if re.search(r'^\s*(?:pub(?:\([^)]*\))?\s+)?(?:impl|struct|enum|trait)\b', p_line):
                    return SyntacticContext(CONTEXT_CLASS_BODY, line=p_line, indent=last_indent)
                if re.search(r'^\s*(?:if|else\s+if)\b', p_line):
                    return SyntacticContext(CONTEXT_IF_BLOCK, line=p_line, indent=last_indent)
                if re.search(r'^\s*(?:for|while|loop)\b', p_line):
                    return SyntacticContext(CONTEXT_LOOP_BLOCK, line=p_line, indent=last_indent)
                break
        return SyntacticContext(CONTEXT_GENERAL, line=stripped_last, indent=last_indent)

    elif target_lang == LANG_CPP:
        if re.search(r'^\s*(?:(?:void|int|bool|auto|double|float|size_t|char|std::string)\s+)?\w+(?:::w+)?\s*\([^)]*$', clean_last):
            return SyntacticContext(CONTEXT_FUNCTION_SIGNATURE, line=stripped_last, indent=last_indent)
        if re.search(r'^\s*try\b', clean_last) or re.search(r'^\s*catch\b', clean_last):
            return SyntacticContext(CONTEXT_TRY_BLOCK, line=stripped_last, indent=last_indent)
        if re.search(r'^\s*(?:class|struct|namespace)\b', clean_last):
            return SyntacticContext(CONTEXT_CLASS_BODY, line=stripped_last, indent=last_indent)
        if re.search(r'^\s*(?:if|else\s+if)\b', clean_last):
            return SyntacticContext(CONTEXT_IF_BLOCK, line=stripped_last, indent=last_indent)
        if re.search(r'^\s*(?:for|while|do)\b', clean_last):
            return SyntacticContext(CONTEXT_LOOP_BLOCK, line=stripped_last, indent=last_indent)

        # Enclosing brace block scan
        for prev_idx in range(last_non_empty_idx - 1, max(-1, last_non_empty_idx - 25), -1):
            p_line = re.sub(comment_pattern, '', lines[prev_idx]).strip()
            if not p_line:
                continue
            net_braces = sum(lines[k].count('{') - lines[k].count('}') for k in range(prev_idx, last_non_empty_idx + 1))
            if net_braces > 0:
                if re.search(r'^\s*try\b', p_line) or re.search(r'^\s*catch\b', p_line):
                    return SyntacticContext(CONTEXT_TRY_BLOCK, line=p_line, indent=last_indent)
                if re.search(r'^\s*(?:class|struct|namespace)\b', p_line):
                    return SyntacticContext(CONTEXT_CLASS_BODY, line=p_line, indent=last_indent)
                if re.search(r'^\s*(?:if|else\s+if)\b', p_line):
                    return SyntacticContext(CONTEXT_IF_BLOCK, line=p_line, indent=last_indent)
                if re.search(r'^\s*(?:for|while|do)\b', p_line):
                    return SyntacticContext(CONTEXT_LOOP_BLOCK, line=p_line, indent=last_indent)
                break
        return SyntacticContext(CONTEXT_GENERAL, line=stripped_last, indent=last_indent)

    elif target_lang == LANG_GO:
        if re.search(r'^\s*func\b', clean_last):
            return SyntacticContext(CONTEXT_FUNCTION_SIGNATURE, line=stripped_last, indent=last_indent)
        if re.search(r'^\s*if\s+err\s*!=\s*nil\b', clean_last):
            return SyntacticContext(CONTEXT_TRY_BLOCK, line=stripped_last, indent=last_indent, details={"type": "err_check"})
        if re.search(r'^\s*type\s+\w+\s+(?:struct|interface)\b', clean_last):
            return SyntacticContext(CONTEXT_CLASS_BODY, line=stripped_last, indent=last_indent)
        if re.search(r'^\s*(?:if|else\s+if)\b', clean_last):
            return SyntacticContext(CONTEXT_IF_BLOCK, line=stripped_last, indent=last_indent)
        if re.search(r'^\s*for\b', clean_last):
            return SyntacticContext(CONTEXT_LOOP_BLOCK, line=stripped_last, indent=last_indent)

        # Enclosing brace block scan
        for prev_idx in range(last_non_empty_idx - 1, max(-1, last_non_empty_idx - 25), -1):
            p_line = re.sub(comment_pattern, '', lines[prev_idx]).strip()
            if not p_line:
                continue
            net_braces = sum(lines[k].count('{') - lines[k].count('}') for k in range(prev_idx, last_non_empty_idx + 1))
            if net_braces > 0:
                if re.search(r'^\s*if\s+err\s*!=\s*nil\b', p_line):
                    return SyntacticContext(CONTEXT_TRY_BLOCK, line=p_line, indent=last_indent, details={"type": "err_check"})
                if re.search(r'^\s*type\s+\w+\s+(?:struct|interface)\b', p_line):
                    return SyntacticContext(CONTEXT_CLASS_BODY, line=p_line, indent=last_indent)
                if re.search(r'^\s*(?:if|else\s+if)\b', p_line):
                    return SyntacticContext(CONTEXT_IF_BLOCK, line=p_line, indent=last_indent)
                if re.search(r'^\s*for\b', p_line):
                    return SyntacticContext(CONTEXT_LOOP_BLOCK, line=p_line, indent=last_indent)
                break
        return SyntacticContext(CONTEXT_GENERAL, line=stripped_last, indent=last_indent)

    # -------------------------------------------------------------------------
    # PYTHON SYNTACTIC CHECKS
    # -------------------------------------------------------------------------
    # 1. Direct active line checks (user is actively typing a construct starter)
    # Exclude standard entrypoint idioms (if __name__ == "__main__":)
    if re.search(r'^\s*if\s*\(?\s*__name__\s*==\s*["\']__main__["\']', last_line):
        return SyntacticContext(CONTEXT_GENERAL, line=stripped_last, indent=last_indent)

    # IF_BLOCK: writing if or elif condition
    if re.search(r'^\s*(?:if|elif)\b', clean_last):
        return SyntacticContext(
            CONTEXT_IF_BLOCK,
            line=stripped_last,
            indent=last_indent,
            details={"type": "if" if "if " in clean_last else "elif"},
        )

    # LOOP_BLOCK: writing for or while loop header
    if re.search(r'^\s*(?:for|while)\b', clean_last):
        return SyntacticContext(
            CONTEXT_LOOP_BLOCK,
            line=stripped_last,
            indent=last_indent,
            details={"type": "for" if "for " in clean_last else "while"},
        )

    # WITH_BLOCK: writing with statement
    if re.search(r'^\s*(?:async\s+)?with\b', clean_last):
        return SyntacticContext(
            CONTEXT_WITH_BLOCK,
            line=stripped_last,
            indent=last_indent,
            details={"type": "with"},
        )

    # TRY_BLOCK: try / try: or except or finally
    if re.search(r'^\s*try\b', clean_last) or re.search(r'^\s*(?:except\b|finally\b)', clean_last):
        return SyntacticContext(
            CONTEXT_TRY_BLOCK,
            line=stripped_last,
            indent=last_indent,
            details={"type": "try_header"},
        )

    # CLASS_BODY: class definition header
    if re.search(r'^\s*class\b', clean_last):
        return SyntacticContext(
            CONTEXT_CLASS_BODY,
            line=stripped_last,
            indent=last_indent,
            details={"type": "class_header"},
        )

    # FUNCTION_SIGNATURE (single-line header being actively typed):
    # e.g. def foo( or async def foo(a, or def foo
    def_match = re.search(r'^\s*(?:async\s+)?def\s+([a-zA-Z_]\w*)?\s*(?:\(.*)?$', clean_last_no_str)
    if def_match:
        # Check if signature was closed on this very line
        p_count = clean_last_no_str.count('(') - clean_last_no_str.count(')')
        has_colon = clean_last.rstrip().endswith(":")
        if p_count > 0 or not has_colon:
            return SyntacticContext(
                CONTEXT_FUNCTION_SIGNATURE,
                line=stripped_last,
                indent=last_indent,
                details={"signature": stripped_last},
            )

    # 2. Check for Multiline FUNCTION_SIGNATURE:
    # If the user is typing arguments across multiple lines:
    # def foo(
    #     arg1: int,
    #     arg2: str,
    # Look backwards for an unclosed def header without any intervening statements.
    statement_keywords = {
        "return", "pass", "yield", "raise", "import", "from", "break",
        "continue", "if", "elif", "else", "while", "for", "try", "except",
        "finally", "with", "class"
    }

    nearest_def_idx = -1
    multiline_def_line = ""
    multiline_def_indent = 0

    for idx in range(last_non_empty_idx - 1, max(-1, last_non_empty_idx - 30), -1):
        cur_l = lines[idx]
        c_l = re.sub(r'#.*$', '', cur_l).strip()
        if not c_l:
            continue

        first_token = c_l.split()[0] if c_l.split() else ""
        if first_token in statement_keywords:
            break

        if re.search(r'^\s*(?:async\s+)?def\b', c_l):
            nearest_def_idx = idx
            multiline_def_line = c_l
            multiline_def_indent = len(cur_l) - len(cur_l.lstrip())
            break

    if nearest_def_idx != -1:
        parens = 0
        sig_closed = False
        saw_statement = False

        for idx in range(nearest_def_idx, last_non_empty_idx + 1):
            cur_l = lines[idx]
            c_l = re.sub(r'#.*$', '', cur_l).strip()
            if not c_l:
                continue
            c_l_no_str = re.sub(r'(["\'])(?:(?=(\\?))\2.)*?\1', '', c_l)
            c_indent = len(cur_l) - len(cur_l.lstrip())

            if idx > nearest_def_idx and c_indent <= multiline_def_indent:
                saw_statement = True
                break

            first_w = c_l.split()[0] if c_l.split() else ""
            if idx > nearest_def_idx and first_w in statement_keywords:
                saw_statement = True
                break

            parens += c_l_no_str.count('(') - c_l_no_str.count(')')

            if parens <= 0 and c_l.rstrip().endswith(":"):
                sig_closed = True
                if idx < last_non_empty_idx:
                    break

        if not sig_closed and not saw_statement and (parens > 0 or not lines[last_non_empty_idx].rstrip().endswith(":")):
            return SyntacticContext(
                CONTEXT_FUNCTION_SIGNATURE,
                line=multiline_def_line,
                indent=last_indent,
                details={"signature": multiline_def_line},
            )

    # 3. Indentation Stack Analysis: determine the innermost enclosing block
    stack: List[Tuple[str, int, str]] = []  # (block_type, indent, line)

    for i in range(0, last_non_empty_idx + 1):
        line_str = lines[i]
        clean_line = re.sub(r'#.*$', '', line_str).rstrip()
        s_line = clean_line.strip()
        if not s_line:
            continue

        l_indent = len(clean_line) - len(clean_line.lstrip())

        # Pop any blocks that have closed (their indentation is >= current line's indentation)
        is_continuation = bool(re.search(r'^\s*(?:elif|else|except|finally)\b', clean_line))
        while stack and (stack[-1][1] > l_indent or (stack[-1][1] == l_indent and not is_continuation)):
            stack.pop()

        # Check for block starters
        if re.search(r'^\s*try\s*:\s*$', clean_line):
            stack.append((CONTEXT_TRY_BLOCK, l_indent, s_line))
        elif re.search(r'^\s*except\b', clean_line):
            if stack and stack[-1][0] == CONTEXT_TRY_BLOCK and stack[-1][1] == l_indent:
                stack.pop()
            stack.append((CONTEXT_TRY_BLOCK, l_indent, s_line))
        elif re.search(r'^\s*finally\s*:\s*$', clean_line):
            if stack and stack[-1][0] == CONTEXT_TRY_BLOCK and stack[-1][1] == l_indent:
                stack.pop()
            stack.append((CONTEXT_TRY_BLOCK, l_indent, s_line))
        elif re.search(r'^\s*class\b', clean_line):
            stack.append((CONTEXT_CLASS_BODY, l_indent, s_line))
        elif re.search(r'^\s*(?:async\s+)?def\b', clean_line):
            stack.append(("DEF_BODY", l_indent, s_line))
        elif re.search(r'^\s*(?:if|elif)\b', clean_line):
            if re.search(r'^\s*if\s*\(?\s*__name__\s*==\s*["\']__main__["\']', clean_line):
                stack.append(("MAIN_BLOCK", l_indent, s_line))
            else:
                if is_continuation and stack and stack[-1][0] == CONTEXT_IF_BLOCK and stack[-1][1] == l_indent:
                    stack.pop()
                stack.append((CONTEXT_IF_BLOCK, l_indent, s_line))
        elif re.search(r'^\s*else\s*:\s*$', clean_line):
            prev_type = stack[-1][0] if stack else CONTEXT_IF_BLOCK
            if stack and stack[-1][1] == l_indent:
                stack.pop()
            stack.append((prev_type, l_indent, s_line))
        elif re.search(r'^\s*(?:for|while)\b', clean_line):
            stack.append((CONTEXT_LOOP_BLOCK, l_indent, s_line))
        elif re.search(r'^\s*(?:async\s+)?with\b', clean_line):
            stack.append((CONTEXT_WITH_BLOCK, l_indent, s_line))

    # Evaluate stack for innermost enclosing block
    if stack:
        innermost_type, innermost_indent, innermost_line = stack[-1]
        if innermost_type not in ("DEF_BODY", "MAIN_BLOCK"):
            return SyntacticContext(
                innermost_type,
                line=innermost_line,
                indent=innermost_indent,
                details={"enclosing": innermost_type},
            )

    # 4. AST Validation fallback (if code happens to be valid Python)
    try:
        tree = ast.parse(content)
        target_lineno = last_non_empty_idx + 1
        candidate_nodes = []
        for node in ast.walk(tree):
            if isinstance(node, (
                ast.Try, ast.ExceptHandler, ast.For, ast.AsyncFor,
                ast.While, ast.If, ast.With, ast.AsyncWith, ast.ClassDef,
                ast.FunctionDef, ast.AsyncFunctionDef,
            )):
                if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
                    if node.lineno <= target_lineno <= node.end_lineno:
                        span = node.end_lineno - node.lineno
                        candidate_nodes.append((span, node.lineno, node))

        if candidate_nodes:
            candidate_nodes.sort(key=lambda x: (x[0], -x[1]))
            innermost_ast = candidate_nodes[0][2]

            if isinstance(innermost_ast, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return SyntacticContext(CONTEXT_GENERAL, line=stripped_last, indent=last_indent)
            elif isinstance(innermost_ast, (ast.Try, ast.ExceptHandler)):
                return SyntacticContext(CONTEXT_TRY_BLOCK, line=stripped_last, indent=last_indent)
            elif isinstance(innermost_ast, (ast.For, ast.AsyncFor, ast.While)):
                return SyntacticContext(CONTEXT_LOOP_BLOCK, line=stripped_last, indent=last_indent)
            elif isinstance(innermost_ast, ast.If):
                is_main_check = False
                if isinstance(innermost_ast.test, ast.Compare):
                    left = innermost_ast.test.left
                    if isinstance(left, ast.Name) and left.id == "__name__":
                        is_main_check = True
                    for comp in innermost_ast.test.comparators:
                        if isinstance(comp, ast.Constant) and comp.value == "__main__":
                            is_main_check = True
                if not is_main_check:
                    return SyntacticContext(CONTEXT_IF_BLOCK, line=stripped_last, indent=last_indent)
            elif isinstance(innermost_ast, (ast.With, ast.AsyncWith)):
                return SyntacticContext(CONTEXT_WITH_BLOCK, line=stripped_last, indent=last_indent)
            elif isinstance(innermost_ast, ast.ClassDef):
                return SyntacticContext(CONTEXT_CLASS_BODY, line=stripped_last, indent=last_indent)
    except Exception:
        pass

    return SyntacticContext(CONTEXT_GENERAL, line=stripped_last, indent=last_indent)
