"""Error-tolerant local symbol extraction (AST first, regex fallback)."""

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


class SymbolExtractionMixin:
    """Symbol extraction methods shared by ContextReader."""

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
