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
from typing import Optional, List, Set, Tuple

try:
    import eyede.config as config
except ImportError:
    import config

# Python reserved keywords and internal names to filter out from user symbol lists
PYTHON_KEYWORDS: Set[str] = {
    "False", "None", "True", "and", "as", "assert", "async", "await", "break",
    "class", "continue", "def", "del", "elif", "else", "except", "finally",
    "for", "from", "global", "if", "import", "in", "is", "lambda", "nonlocal",
    "not", "or", "pass", "raise", "return", "try", "while", "with", "yield",
    "self", "cls",
    # Common builtins that are not user symbols
    "print", "len", "range", "str", "int", "float", "list", "dict", "set",
    "tuple", "bool", "min", "max", "sum", "abs", "round", "enumerate", "zip",
    "open", "super", "isinstance", "issubclass", "type", "id", "map", "filter",
    "any", "all", "dir", "hasattr", "getattr", "setattr", "repr", "iter", "next",
}


class ContextReader:
    """
    Non-intrusive live context reader for the active code editing session.
    Detects or links the active Python file and dynamically extracts local
    symbols (variables, arguments, functions, classes) using a dual AST + Regex engine.
    """

    def __init__(
        self,
        workspace_dir: Optional[str] = None,
        active_file: Optional[str] = None,
        auto_detect: Optional[bool] = None,
    ):
        raw_ws = workspace_dir if workspace_dir is not None else getattr(config, "DEFAULT_WORKSPACE_DIR", os.getcwd())
        self.workspace_dir: str = os.path.abspath(raw_ws) if raw_ws else os.getcwd()

        raw_af = active_file if active_file is not None else getattr(config, "ACTIVE_FILE_PATH", None)
        self.active_file_path: Optional[str] = os.path.abspath(raw_af) if raw_af else None

        self.auto_detect: bool = auto_detect if auto_detect is not None else getattr(config, "AUTO_DETECT_RECENT_FILE", True)
        self._cached_detected_file: Optional[str] = None
        self._last_detect_time: float = 0.0

    def set_active_file(self, file_path: Optional[str]) -> None:
        """Explicitly links or unlinks an active Python file for context reading."""
        self._cached_detected_file = None
        self._last_detect_time = 0.0
        if file_path:
            self.active_file_path = os.path.abspath(file_path)
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
        Scans workspace_dir for the most recently modified .py file.
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
        }

        latest_file: Optional[str] = None
        latest_mtime: float = -1.0

        try:
            for root, dirs, files in os.walk(self.workspace_dir):
                # Filter out ignored directories in-place to avoid descending into them
                dirs[:] = [d for d in dirs if d not in ignored_dirs and not d.startswith(".")]

                for f in files:
                    if f.endswith(".py"):
                        full_path = os.path.join(root, f)
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
        Safe against empty files, syntax errors, and missing files.
        """
        content = self.read_file_content(file_path)
        if not content:
            return ""

        lines = content.splitlines()
        recent_lines = lines[-max_lines:] if len(lines) > max_lines else lines
        return "\n".join(recent_lines)

    def get_last_line(self, file_path: Optional[str] = None) -> str:
        """Returns the last non-empty stripped line from the active file."""
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
    ) -> List[str]:
        """
        Dual AST + Regex extractor:
        Tolerant to SyntaxError (unclosed parens, incomplete lines).
        Extracts variables, arguments, functions, and classes.
        Returns up to `max_symbols` (default 12) unique symbols, prioritized by recency.
        """
        try:
            content = source_code if source_code is not None else self.read_file_content(file_path)
        except (FileNotFoundError, PermissionError, OSError):
            return []
        if not content or not content.strip():
            return []

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
