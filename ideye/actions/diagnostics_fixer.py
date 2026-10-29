"""Live diagnostics heuristics and one-click auto-fix menu for IDEye."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

try:
    from ideye.actions.menu_trees import (
        MenuAction,
        MenuNode,
        create_back_action,
        create_pause_action,
    )
except ImportError:  # pragma: no cover
    from actions.menu_trees import (  # type: ignore
        MenuAction,
        MenuNode,
        create_back_action,
        create_pause_action,
    )


class DiagnosticsFixer:
    """Turns editor diagnostics into low-latency, gaze-friendly fixes."""

    def __init__(self, context_reader: Optional[Any] = None) -> None:
        self.context_reader = context_reader
        self.ai_suggestions: List[str] = []
        self.last_diagnostics: List[Dict[str, Any]] = []
        self._fixes_by_id: Dict[str, Dict[str, Any]] = {}

    def set_ai_suggestions(self, suggestions: List[str]) -> None:
        self.ai_suggestions = [str(value) for value in (suggestions or []) if str(value).strip()]

    @staticmethod
    def _levenshtein(a: str, b: str) -> int:
        if a == b:
            return 0
        if not a:
            return len(b)
        if not b:
            return len(a)
        previous = list(range(len(b) + 1))
        for i, ca in enumerate(a, 1):
            current = [i]
            for j, cb in enumerate(b, 1):
                current.append(min(current[-1] + 1, previous[j] + 1, previous[j - 1] + (ca != cb)))
            previous = current
        return previous[-1]

    def _closest_symbol(self, name: str, symbols: List[str]) -> Optional[str]:
        if not symbols:
            return None
        ranked = sorted(symbols, key=lambda symbol: self._levenshtein(name.lower(), str(symbol).lower()))
        best = str(ranked[0])
        distance = self._levenshtein(name.lower(), best.lower())
        return best if distance <= max(2, len(name) // 3) else None

    def local_diagnostics(self, source_code: str, cursor_line: Optional[int] = None) -> List[Dict[str, Any]]:
        """Fallback compile() check used when VS Code is not connected."""
        try:
            compile(source_code or "", "<ideye-context>", "exec")
            return []
        except SyntaxError as exc:
            line = int(exc.lineno or 1)
            return [{
                "line": line,
                "severity": "error",
                "message": str(exc.msg or "SyntaxError"),
                "source": "python-compile",
                "code_line": (source_code.splitlines()[line - 1] if 0 < line <= len(source_code.splitlines()) else ""),
            }]
        except Exception:
            return []

    def collect_local(self, cursor_line: Optional[int] = None) -> List[Dict[str, Any]]:
        if self.context_reader is None:
            return []
        try:
            source = self.context_reader.read_file_content() or ""
        except Exception:
            source = ""
        diagnostics = self.local_diagnostics(source, cursor_line)
        self.last_diagnostics = diagnostics
        return diagnostics

    def generate_fixes(
        self,
        diagnostic: Dict[str, Any],
        context_data: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        context = dict(context_data or {})
        message = str(diagnostic.get("message", ""))
        line_text = str(diagnostic.get("code_line", context.get("line_text", "")) or "")
        line = max(1, int(diagnostic.get("line", context.get("cursor_line", 1)) or 1))
        symbols = [str(s) for s in context.get("symbols", []) if s]
        fixes: List[Dict[str, Any]] = []

        name_match = re.search(r"(?:name ['\"]?([A-Za-z_]\w*)['\"]? is not defined|Undefined name ['\"]?([A-Za-z_]\w*))", message, re.I)
        if name_match:
            name = name_match.group(1) or name_match.group(2)
            fixes.append({
                "id": f"import_{name}",
                "label": f"Importar {name}",
                "description": f"Añadir import {name} al inicio del archivo",
                "line": 1,
                "replacement": f"import {name}",
                "insert": True,
                "kind": "import",
            })
            closest = self._closest_symbol(name, symbols)
            if closest:
                fixes.append({
                    "id": f"rename_{name}_{closest}",
                    "label": f"Usar {closest}",
                    "description": f"Reemplazar '{name}' por el símbolo local '{closest}'",
                    "line": line,
                    "replacement": line_text.replace(name, closest),
                    "kind": "replace",
                })

        if re.search(r"expected ['\"]?:['\"]?", message, re.I) and not line_text.rstrip().endswith(":"):
            fixes.append({
                "id": f"colon_{line}",
                "label": "Añadir :",
                "description": "Añadir ':' al final de la sentencia",
                "line": line,
                "replacement": line_text.rstrip() + ":",
                "kind": "replace",
            })

        unclosed = re.search(r"unclosed ['\"]?([\(\[\{])", message, re.I)
        if unclosed:
            pairs = {"(": ")", "[": "]", "{": "}"}
            opener = unclosed.group(1)
            fixes.append({
                "id": f"close_{line}",
                "label": f"Cerrar {pairs[opener]}",
                "description": f"Añadir el delimitador {pairs[opener]} que falta",
                "line": line,
                "replacement": line_text.rstrip() + pairs[opener],
                "kind": "replace",
            })

        if "IndentationError" in message or "unexpected indent" in message.lower():
            fixes.append({
                "id": f"indent_{line}",
                "label": "Corregir sangría",
                "description": "Alinear la línea al siguiente múltiplo de 4 espacios",
                "line": line,
                "replacement": " " * (4 * max(1, (len(line_text) - len(line_text.lstrip()) + 3) // 4)) + line_text.lstrip(),
                "kind": "replace",
            })

        for index, suggestion in enumerate(self.ai_suggestions[:2]):
            text = str(suggestion).strip()
            if text and "\n" not in text:
                fixes.append({
                    "id": f"ai_{line}_{index}",
                    "label": f"IA: {text[:28]}",
                    "description": "Aplicar sugerencia del predictor de IA",
                    "line": line,
                    "replacement": text,
                    "kind": "replace",
                })

        if not fixes:
            fixes.append({
                "id": f"inspect_{line}",
                "label": "Revisar línea",
                "description": "Colocar el cursor y abrir las sugerencias de contexto",
                "line": line,
                "replacement": line_text,
                "kind": "inspect",
            })
        return fixes

    def build_fixes(
        self,
        diagnostics: List[Dict[str, Any]],
        context_data: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        all_fixes: List[Dict[str, Any]] = []
        for diagnostic in diagnostics or []:
            all_fixes.extend(self.generate_fixes(diagnostic, context_data))
        self._fixes_by_id = {str(fix["id"]): fix for fix in all_fixes}
        return all_fixes[:7]

    def get_autofix_menu_node(self, parent_id: str = "ROOT") -> MenuNode:
        """Builds a 9-cell menu with Pause at slot 4 and Back at slot 6."""
        fixes = list(self._fixes_by_id.values())[:7]
        items = []
        for index, fix in enumerate(fixes):
            items.append(MenuAction(
                id=str(fix["id"]),
                label=f"{index + 1}: {fix.get('label', 'Auto-Fix')}",
                hint=str(fix.get("description", "")),
                action_type="AUTOFIX",
                snippet=str(fix.get("replacement", "")),
                icon="edit",
            ))
        while len(items) < 7:
            items.append(MenuAction(
                id=f"AUTOFIX_EMPTY_{len(items)}",
                label=f"{len(items) + 1}: ?",
                hint="Sin reparación adicional",
                action_type="NOOP",
                snippet="",
            ))
        return MenuNode(
            id="AUTO_FIX",
            title="AUTO-FIX",
            breadcrumb_label="AUTO-FIX",
            items=[items[0], items[1], items[2], items[3], create_pause_action("5"), items[4], create_back_action(parent_id, "7"), items[5], items[6]],
            parent_id=parent_id,
            sticky=True,
        )

    def apply_fix(self, fix: Dict[str, Any], bridge: Optional[Any] = None, code_injector: Optional[Any] = None) -> bool:
        """Sends a line replacement to VS Code, or applies it locally as a snippet."""
        if bridge is not None and getattr(bridge, "is_connected", False):
            sender = getattr(bridge, "send_apply_line_fix", None)
            if sender is not None:
                return bool(sender(int(fix.get("line", 1)), str(fix.get("replacement", "")), bool(fix.get("insert", False))))
        if code_injector is not None:
            try:
                code_injector.insert_snippet(str(fix.get("replacement", "")))
                return True
            except Exception:
                return False
        return False

    def badge_text(self, diagnostics: Optional[List[Dict[str, Any]]] = None) -> str:
        items = diagnostics if diagnostics is not None else self.last_diagnostics
        if not items:
            return ""
        first = items[0]
        message = str(first.get("message", "Error"))
        return f"AUTO-FIX DISPONIBLE ? {message[:52]}"
