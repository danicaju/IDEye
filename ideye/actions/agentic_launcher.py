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
    from ideye.actions.menu_trees import (
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


from ideye.actions.agentic_actions import (  # noqa: F401
    ACTION_SLOTS,
    AGENTIC_ACTIONS,
    SLOT_INDEXES,
    _KEY_LABELS,
)
from ideye.actions.agentic_context import AgenticContextMixin




def default_queue_path() -> Path:
    override = os.environ.get("IDEYE_AGENTIC_QUEUE", "").strip()
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[2] / "agentic_task_queue.json"


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class AgenticPromptLauncher(AgenticContextMixin):
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
