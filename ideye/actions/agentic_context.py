"""Context extraction helpers for the agentic prompt launcher."""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any, Dict, List, Optional


class AgenticContextMixin:
    """Builds the editor context dictionary used by prompts."""

    def build_context(self, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Normalizes a caller context and fills missing data from IDEye."""
        raw = dict(context or {})
        source = str(raw.get("source_code") or raw.get("code") or "")
        file_path = str(raw.get("file_path") or "")
        language = str(raw.get("language") or "")

        reader = self.context_reader
        if not file_path and reader is not None:
            try:
                file_path = str(reader.get_active_file() or "")
            except Exception:
                file_path = ""
        if not source and reader is not None:
            try:
                source = str(reader.read_file_content(file_path or None) or "")
            except Exception:
                source = ""
        if not language and reader is not None:
            try:
                language = str(reader.get_active_language() or "")
            except Exception:
                language = ""
        if not language:
            language = self._language_from_path(file_path)

        explicit_start = raw.get("line_start")
        explicit_end = raw.get("line_end")
        cursor_line = raw.get("cursor_line") or raw.get("line")
        function_name = str(raw.get("function_name") or "")
        detected_start: Optional[int] = None
        detected_end: Optional[int] = None

        if source and (not function_name or explicit_start is None):
            name, start, end = self._detect_function(
                source,
                cursor_line=int(cursor_line) if cursor_line else None,
                line_offset=int(explicit_start) - 1 if explicit_start else 0,
            )
            function_name = function_name or name
            detected_start, detected_end = start, end

        lines = source.splitlines()
        if explicit_start:
            line_start = int(explicit_start)
            line_end = int(explicit_end or line_start)
        elif detected_start:
            line_start, line_end = detected_start, detected_end or detected_start
        else:
            line_start, line_end = (1, len(lines)) if lines else (0, 0)

        # Keep the prompt bounded while preserving the target function.
        if len(lines) > 220 and detected_start:
            pad = 4
            low = max(1, detected_start - pad)
            high = min(len(lines), (detected_end or detected_start) + pad)
            lines = lines[low - 1:high]
            if not explicit_start:
                line_start, line_end = low, high
        elif len(lines) > 220:
            lines = lines[-180:]
            line_start = max(1, len(source.splitlines()) - len(lines) + 1)
            line_end = line_start + len(lines) - 1

        source = "\n".join(lines)
        symbols = self._normalize_symbols(raw.get("symbols"))
        if not symbols and reader is not None:
            try:
                symbols = self._normalize_symbols(
                    reader.extract_local_symbols(
                        max_symbols=12,
                        file_path=file_path or None,
                        source_code=source or None,
                        language=language or None,
                    )
                )
            except Exception:
                symbols = []
        if function_name and function_name not in symbols:
            symbols.insert(0, function_name)

        diagnostics = self._normalize_diagnostics(raw.get("diagnostics"))
        if not diagnostics and self.diagnostics_fixer is not None:
            diagnostics = self._normalize_diagnostics(
                getattr(self.diagnostics_fixer, "last_diagnostics", None)
            )
        relevant = diagnostics
        if line_start and line_end and diagnostics:
            inside = [
                item for item in diagnostics
                if line_start <= int(item.get("line") or 0) <= line_end
            ]
            relevant = inside or diagnostics

        return {
            "file_path": file_path or "(archivo activo no detectado)",
            "line_start": int(line_start),
            "line_end": int(line_end),
            "function_name": function_name or "selección actual",
            "language": language or "text",
            "source_code": source,
            "symbols": symbols,
            "diagnostics": relevant,
        }

    def _detect_function(
        self,
        source: str,
        cursor_line: Optional[int] = None,
        line_offset: int = 0,
    ) -> tuple[str, int, int]:
        """Returns (name, start_line, end_line) for the target function."""
        try:
            tree = ast.parse(source)
        except SyntaxError:
            tree = None
        if tree is not None:
            candidates = [
                node for node in ast.walk(tree)
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            ]
            if candidates:
                if cursor_line is not None:
                    adjusted = max(1, cursor_line - line_offset)
                    containing = [
                        node for node in candidates
                        if node.lineno <= adjusted <= getattr(node, "end_lineno", node.lineno)
                    ]
                    if containing:
                        node = min(
                            containing,
                            key=lambda item: getattr(item, "end_lineno", item.lineno) - item.lineno,
                        )
                        return (
                            node.name,
                            node.lineno + line_offset,
                            getattr(node, "end_lineno", node.lineno) + line_offset,
                        )
                node = candidates[0]
                return (
                    node.name,
                    node.lineno + line_offset,
                    getattr(node, "end_lineno", node.lineno) + line_offset,
                )

        pattern = re.compile(
            r"^\s*(?:async\s+)?(?:def|function|fn|fun|func)\s+([A-Za-z_]\w*)",
            re.MULTILINE,
        )
        matches = list(pattern.finditer(source))
        if not matches:
            return "", 0, 0
        match = matches[0]
        start = source[: match.start()].count("\n") + 1 + line_offset
        name = match.group(1)
        return name, start, start

    @staticmethod
    def _language_from_path(file_path: str) -> str:
        suffix = Path(file_path).suffix.lower()
        return {
            ".py": "python",
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".java": "java",
            ".cs": "csharp",
            ".cpp": "cpp",
            ".cc": "cpp",
            ".c": "c",
            ".h": "c",
            ".go": "go",
            ".rs": "rust",
            ".rb": "ruby",
            ".php": "php",
        }.get(suffix, "text")

    @staticmethod
    def _normalize_symbols(value: Any) -> List[str]:
        output: List[str] = []
        if not value:
            return output
        for item in value:
            text = str(item) if not isinstance(item, dict) else str(
                item.get("name") or item.get("label") or ""
            )
            if text and text not in output:
                output.append(text)
        return output

    @staticmethod
    def _normalize_diagnostics(value: Any) -> List[Dict[str, Any]]:
        output: List[Dict[str, Any]] = []
        if not value:
            return output
        for item in value:
            if isinstance(item, dict):
                output.append(dict(item))
            elif isinstance(item, (tuple, list)) and len(item) >= 3:
                output.append({"line": item[0], "severity": item[1], "message": item[2]})
        return output

    # ------------------------------------------------------------------
    # Prompt generation
    # ------------------------------------------------------------------
