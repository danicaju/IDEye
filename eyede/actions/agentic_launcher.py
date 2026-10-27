"""Agentic prompt launcher for hands-free AI orchestration (Phase 10.4).

Builds rich, deterministic Markdown prompts from the current coding context
(file, selection, AST symbols and diagnostics) and dispatches them to the VS
Code WebSocket bridge or to the local MCP task queue.
"""

from __future__ import annotations

import ast
import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

try:
    from eyede.actions.menu_trees import (
        MenuAction,
        MenuNode,
        create_back_action,
        create_pause_action,
    )
except ImportError:  # pragma: no cover - legacy flat layout
    from actions.menu_trees import (  # type: ignore
        MenuAction,
        MenuNode,
        create_back_action,
        create_pause_action,
    )


AGENTIC_ACTIONS: Dict[str, Dict[str, str]] = {
    "refactor_clean": {
        "label": "REFACTOR",
        "title": "Refactor limpio",
        "instruction": (
            "Refactoriza la función o selección actual aplicando principios SOLID, "
            "tipado estricto y eliminación de código duplicado sin alterar su "
            "contrato público."
        ),
        "contract": (
            "Devuelve el código completo de la función refactorizada, una lista "
            "breve de cambios estructurales y cualquier riesgo de compatibilidad."
        ),
        "icon": "wand",
        "hint": "SOLID, tipado y sin duplicación",
    },
    "generate_pytest": {
        "label": "GEN PYTEST",
        "title": "Generar tests pytest",
        "instruction": (
            "Genera tests unitarios deterministas con pytest para la función activa. "
            "Cubre el camino feliz, valores nulos, bordes, excepciones y errores de "
            "entrada sin depender de red, tiempo real ni estado global."
        ),
        "contract": (
            "Devuelve un archivo de test ejecutable con imports completos, fixtures "
            "mínimas y aserciones explícitas para cada caso."
        ),
        "icon": "test-tube",
        "hint": "Camino feliz, nulos y bordes",
    },
    "fix_and_harden": {
        "label": "FIX & HARDEN",
        "title": "Corregir y blindar",
        "instruction": (
            "Corrige todos los diagnósticos activos del bloque actual y blinda el "
            "código frente a condiciones de carrera, divisiones por cero, fugas de "
            "recursos y entradas inválidas."
        ),
        "contract": (
            "Devuelve el parche completo, explica cada diagnóstico resuelto y añade "
            "las guardas o context managers necesarios."
        ),
        "icon": "shield-lock",
        "hint": "Diagnósticos y robustez",
    },
    "optimize_complexity": {
        "label": "OPTIMIZE O(N)",
        "title": "Optimizar complejidad",
        "instruction": (
            "Analiza la complejidad algorítmica y de memoria de la función actual y "
            "reescríbela optimizando los cuellos de botella sin cambiar su contrato."
        ),
        "contract": (
            "Incluye la complejidad antes y después, el código optimizado y una nota "
            "sobre los compromisos de legibilidad o memoria."
        ),
        "icon": "gauge",
        "hint": "Tiempo, memoria y cuellos de botella",
    },
    "write_docstring": {
        "label": "DOCSTRING",
        "title": "Escribir docstring",
        "instruction": (
            "Genera e inyecta el docstring técnico completo de la función activa con "
            "argumentos, tipo de retorno, excepciones y complejidad, siguiendo el "
            "estilo del proyecto."
        ),
        "contract": (
            "Devuelve la función completa con el docstring insertado y sin modificar "
            "la lógica ejecutable."
        ),
        "icon": "file-text",
        "hint": "Args, retorno, excepciones y O(N)",
    },
    "explain_architecture": {
        "label": "EXPLAIN",
        "title": "Explicar arquitectura",
        "instruction": (
            "Explica el flujo de datos y las dependencias de este bloque dentro de la "
            "arquitectura general del módulo, señalando acoplamientos y riesgos."
        ),
        "contract": (
            "Devuelve una explicación breve con entradas, salidas, dependencias, "
            "efectos secundarios y puntos de extensión."
        ),
        "icon": "network",
        "hint": "Flujo, dependencias y riesgos",
    },
}

ACTION_SLOTS: Sequence[str] = (
    "refactor_clean",
    "generate_pytest",
    "fix_and_harden",
    "optimize_complexity",
    "write_docstring",
    "explain_architecture",
)
SLOT_INDEXES = (0, 1, 2, 3, 5, 7)

_KEY_LABELS = ("1", "2", "3", "4", "6", "8")


def default_queue_path() -> Path:
    override = os.environ.get("IDEYE_AGENTIC_QUEUE", "").strip()
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[2] / "agentic_task_queue.json"


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class AgenticPromptLauncher:
    """Builds, queues and dispatches context-rich engineering prompts."""

    def __init__(
        self,
        context_reader: Any = None,
        diagnostics_fixer: Any = None,
        queue_path: Optional[str] = None,
    ) -> None:
        self.context_reader = context_reader
        self.diagnostics_fixer = diagnostics_fixer
        self.queue_path = Path(queue_path) if queue_path else default_queue_path()
        self.last_action_id: str = "refactor_clean"

    # ------------------------------------------------------------------
    # Context
    # ------------------------------------------------------------------
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
    def build_prompt(
        self,
        action_id: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        action_id = str(action_id or "refactor_clean")
        if action_id not in AGENTIC_ACTIONS:
            action_id = "refactor_clean"
        action = AGENTIC_ACTIONS[action_id]
        ctx = self.build_context(context)

        symbols = ctx["symbols"]
        if symbols:
            symbol_block = "\n".join(f"- `{symbol}`" for symbol in symbols)
        else:
            symbol_block = "- (sin símbolos AST detectados)"

        diagnostics = ctx["diagnostics"]
        if diagnostics:
            diag_lines = []
            for item in diagnostics:
                line = item.get("line", "?")
                severity = str(item.get("severity") or "warning").upper()
                message = item.get("message") or item.get("text") or ""
                source = item.get("source")
                suffix = f" ({source})" if source else ""
                diag_lines.append(f"- Línea {line} [{severity}] {message}{suffix}")
            diagnostics_block = "\n".join(diag_lines)
        else:
            diagnostics_block = "- (sin diagnósticos activos en el bloque)"

        language = ctx["language"]
        source_block = ctx["source_code"] or "(código fuente no disponible)"
        fence = "```"
        if fence in source_block:
            fence = "````"

        return (
            f"# {action['title']} — IDEye Agentic Prompt\n\n"
            f"## Instrucción de ingeniería\n\n{action['instruction']}\n\n"
            f"## Contexto de selección\n\n"
            f"- **Archivo:** `{ctx['file_path']}`\n"
            f"- **Rango:** líneas {ctx['line_start']}–{ctx['line_end']}\n"
            f"- **Función / bloque:** `{ctx['function_name']}`\n"
            f"- **Lenguaje:** {language}\n"
            f"- **Acción:** `{action_id}`\n\n"
            f"## Código fuente relevante\n\n"
            f"{fence}{language}\n{source_block}\n{fence}\n\n"
            f"## Símbolos AST locales\n\n{symbol_block}\n\n"
            f"## Diagnósticos activos\n\n{diagnostics_block}\n\n"
            f"## Contrato de salida\n\n{action['contract']}\n\n"
            f"---\n"
            f"Generado por IDEye Agentic Prompt Launcher. Aplica el cambio solo "
            f"sobre la selección indicada y conserva el contrato público existente.\n"
        )

    # ------------------------------------------------------------------
    # 3x3 menu
    # ------------------------------------------------------------------
    @staticmethod
    def get_action_label(action_id: str) -> str:
        """Returns the short human label for an agentic action."""
        action = AGENTIC_ACTIONS.get(str(action_id), AGENTIC_ACTIONS["refactor_clean"])
        return action["label"]

    def get_agentic_menu_node(self, parent_id: str = "ROOT") -> MenuNode:
        items: List[MenuAction] = [None] * 9  # type: ignore[list-item]
        for action_id, index, key_label in zip(ACTION_SLOTS, SLOT_INDEXES, _KEY_LABELS):
            action = AGENTIC_ACTIONS[action_id]
            items[index] = MenuAction(
                id=f"AGENTIC_{action_id.upper()}",
                label=f"{key_label}: {action['label']}",
                hint=action["hint"],
                action_type="AGENTIC_PROMPT",
                snippet=action_id,
                icon=action["icon"],
            )
        items[4] = create_pause_action("5")
        items[6] = create_back_action(parent_id, "7")
        items[8] = MenuAction(
            id="AGENTIC_SEND",
            label="9: COLA MCP / COPIAR",
            hint="Guardar en agentic_task_queue.json o copiar el prompt",
            action_type="AGENTIC_SEND",
            snippet="queue",
            icon="terminal",
        )
        return MenuNode(
            id="AGENTIC_LAUNCHER",
            title="AGENTIC PROMPT LAUNCHER",
            items=items,
            parent_id=parent_id,
            sticky=False,
        )

    # ------------------------------------------------------------------
    # Queue / dispatch
    # ------------------------------------------------------------------
    def queue_task(
        self,
        action_id: str,
        prompt: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Optional[Path]:
        queue = self.read_queue()
        now = _iso_now()
        task = {
            "id": uuid.uuid4().hex,
            "action_id": str(action_id or "refactor_clean"),
            "label": AGENTIC_ACTIONS.get(action_id, AGENTIC_ACTIONS["refactor_clean"])["label"],
            "prompt": str(prompt or ""),
            "created_at": now,
            "status": "pending",
            "selection_only": True,
        }
        if payload:
            task["payload"] = dict(payload)
        pending = list(queue.get("pending") or [])
        pending.append(task)
        queue["version"] = 1
        queue["updated_at"] = now
        queue["pending"] = pending[-20:]
        try:
            self.queue_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.queue_path.with_name(self.queue_path.name + ".tmp")
            with open(tmp, "w", encoding="utf-8") as handle:
                json.dump(queue, handle, ensure_ascii=False, indent=2)
            os.replace(tmp, self.queue_path)
            return self.queue_path
        except Exception:
            return None

    def read_queue(self) -> Dict[str, Any]:
        try:
            if self.queue_path.is_file():
                data = json.loads(self.queue_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
        return {"version": 1, "updated_at": "", "pending": []}

    def latest_task(self) -> Optional[Dict[str, Any]]:
        pending = self.read_queue().get("pending") or []
        return dict(pending[-1]) if pending else None

    def send_to_bridge(
        self,
        bridge: Any,
        action_id: str,
        prompt: str,
        selection_only: bool = True,
    ) -> bool:
        if bridge is None:
            return False
        try:
            if hasattr(bridge, "send_trigger_agent_prompt"):
                return bool(
                    bridge.send_trigger_agent_prompt(
                        action_id=action_id,
                        prompt=prompt,
                        selection_only=selection_only,
                    )
                )
            if hasattr(bridge, "broadcast_message"):
                return bool(
                    bridge.broadcast_message(
                        {
                            "type": "trigger_agent_prompt",
                            "action_id": action_id,
                            "prompt": prompt,
                            "selection_only": bool(selection_only),
                        }
                    )
                )
        except Exception:
            return False
        return False

    def dispatch(
        self,
        action_id: str,
        prompt: str,
        bridge: Any = None,
        queue_only: bool = False,
        selection_only: bool = True,
    ) -> Dict[str, Any]:
        action_id = str(action_id or "refactor_clean")
        self.last_action_id = action_id if action_id in AGENTIC_ACTIONS else "refactor_clean"
        queue_file = self.queue_task(action_id, prompt)
        sent = False
        if not queue_only:
            sent = self.send_to_bridge(
                bridge,
                action_id=action_id,
                prompt=prompt,
                selection_only=selection_only,
            )
        return {
            "action_id": action_id,
            "label": AGENTIC_ACTIONS.get(action_id, AGENTIC_ACTIONS["refactor_clean"])["label"],
            "prompt": prompt,
            "sent": bool(sent),
            "queued": queue_file is not None,
            "queue_path": str(queue_file) if queue_file else "",
        }

    def dispatch_built(
        self,
        action_id: str,
        bridge: Any = None,
        queue_only: bool = False,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        prompt = self.build_prompt(action_id, context=context)
        return self.dispatch(
            action_id,
            prompt,
            bridge=bridge,
            queue_only=queue_only,
        )
