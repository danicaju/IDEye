"""Menu action execution, undo and caret snapping."""

from ideye.ui.overlay_common import *  # noqa: F401,F403
from ideye.ui.overlay_common import (  # noqa: F401
    _clean_action_label,
)


class OverlayActionsMixin:
    """Menu action execution, undo and caret snapping."""

    def execute_action(self, item: MenuAction, target_block: int = 0) -> None:
        """Programmatically executes a MenuAction directly on the overlay."""
        if getattr(item, "action_type", "") == "AUTOFIX":
            fix = self.diagnostics_fixer._fixes_by_id.get(str(item.id))
            if fix is not None:
                self.autofix_requested.emit(fix)
            self.last_action_desc = f"Auto-Fix: {item.label}"
            self.action_executed.emit(item.id, self.last_action_desc)
            self.block_activated.emit(target_block, item.id)
            return

        if getattr(item, "action_type", "") == "AST_JUMP":
            try:
                self.ast_jump_requested.emit(int(item.snippet or 1))
            except (TypeError, ValueError):
                pass
            self.last_action_desc = f"AST: saltar a {item.hint}"
            self.action_executed.emit(item.id, self.last_action_desc)
            self.block_activated.emit(target_block, item.id)
            return

        if getattr(item, "action_type", "") == "AST_NEXT_PAGE":
            self._ast_page = int(item.snippet or 0)
            self.menu_tree["AST_SYMBOLS"] = self.ast_code_jumper.get_symbols_menu_node(
                self.ast_code_jumper.symbols, self._ast_page, parent_id="ROOT"
            )
            self.navigate_to("AST_SYMBOLS")
            self.last_action_desc = f"AST: página {self._ast_page + 1}"
            self.update()
            return

        if getattr(item, "action_type", "") == "AST_REFRESH":
            self.open_ast_symbols(refresh=True)
            self.block_activated.emit(target_block, item.id)
            return

        if item.action_type in ("AGENTIC_PROMPT", "AGENTIC_SEND"):
            queue_only = item.action_type == "AGENTIC_SEND"
            action_id = (
                self._last_agentic_action_id
                if queue_only
                else str(item.snippet or "refactor_clean")
            )
            prompt = self.agentic_launcher.build_prompt(
                action_id,
                context=self._current_agentic_context(),
            )
            self._last_agentic_action_id = action_id
            self.agentic_prompt_requested.emit(action_id, prompt, bool(queue_only))
            label = self.agentic_launcher.get_action_label(action_id)
            self.last_action_desc = (
                f"Orden IA en cola MCP: {label}"
                if queue_only
                else f"Orden IA: {label}"
            )
            self.action_executed.emit(item.id, self.last_action_desc)
            self.block_activated.emit(target_block, item.id)
            self.update()
            return

        if item.action_type == "GAZE_SCROLL":
            enabled = self.toggle_gaze_scroll()
            self.last_action_desc = (
                "Scroll continuo activado" if enabled else "Scroll continuo desactivado"
            )
            self.action_executed.emit(item.id, self.last_action_desc)
            self.block_activated.emit(target_block, item.id)
            self.update()
            return

        if item.action_type == "PAUSE":
            self.toggle_reading_mode()
            self.last_action_desc = "Modo Reposo Activo"
            self.block_activated.emit(target_block, "PAUSE_RESUME")
            return

        if item.action_type == "BACK":
            target_id = item.submenu_id or (self.current_node.parent_id if self.current_node else "ROOT") or "ROOT"
            self.navigate_to(target_id)
            target_title = self.menu_tree[target_id].title if target_id in self.menu_tree else "RAÍZ"
            self.last_action_desc = f"Volver a {target_title}"
            self.block_activated.emit(target_block, item.id)
            return

        if item.action_type == "MODE_SWITCH":
            self._activate_mode(item.mode_id)
            self.block_activated.emit(target_block, item.id)
            return

        if self._handle_writing_action(item, target_block):
            return

        if item.action_type == "SUBMENU":
            target_id = item.submenu_id
            if target_id and target_id in self.menu_tree:
                self.navigate_to(target_id)
                self.last_action_desc = f"Menú: {self.menu_tree[target_id].title}"
            self.block_activated.emit(target_block, item.id)
            return

        if item.action_type == "LANG_CHANGE":
            target_lang = item.snippet or "PYTHON"
            self.set_language(target_lang)
            if self.current_node_id == "LANG_SELECT":
                self.navigate_to("ROOT")
            self.block_activated.emit(target_block, item.id)
            return

        if item.action_type == "LANG_AUTO":
            detected_lang = self.context_reader.get_active_language() if self.context_reader else "PYTHON"
            self.set_language(detected_lang)
            if self.current_node_id == "LANG_SELECT":
                self.navigate_to("ROOT")
            self.block_activated.emit(target_block, item.id)
            return

        if item.action_type == "CLIPBOARD":
            text = item.snippet or ""
            if text:
                self.code_injector.insert_snippet(text)
                self.text_injected.emit(len(text))
            self.last_action_desc = f"Pegado: {len(text)} chars"
            self.action_executed.emit(item.id, self.last_action_desc)
            self.block_activated.emit(target_block, item.id)
            return

        if item.action_type == "CLIPBOARD_COPY":
            if self.clipboard_manager is not None:
                self.clipboard_manager.copy_selection()
            self.last_action_desc = "Copiando selección..."
            self.action_executed.emit(item.id, self.last_action_desc)
            self.block_activated.emit(target_block, item.id)
            return

        if item.id in ("CMD_UNDO", "EDIT_UNDO", "ACTION_UNDO") or getattr(item, "key_name", "") == "UNDO":
            self.trigger_undo(item.id)
            self.block_activated.emit(target_block, item.id)
            return

        if item.id == "CMD_TUTORIAL":
            self.start_mini_tutorial()
            self.last_action_desc = "Tutorial guiado de inicio"
            self.action_executed.emit(item.id, self.last_action_desc)
            self.block_activated.emit(target_block, item.id)
            return

        if item.id == "CMD_SNAP_CARET":
            self.snap_to_caret()
            self.last_action_desc = "Snap Caret: Micro-recalibrado"
            self.action_executed.emit(item.id, self.last_action_desc)
            self.block_activated.emit(target_block, item.id)
            return

        if item.id == "CMD_TOGGLE_DOCK":
            new_layout = self.toggle_hud_layout()
            self.last_action_desc = f"Layout: {new_layout}"
            self.action_executed.emit(item.id, self.last_action_desc)
            self.block_activated.emit(target_block, item.id)
            return

        if item.id == "CMD_TOGGLE_THEME":
            new_theme = self.toggle_theme()
            self.last_action_desc = f"Tema: {new_theme}"
            self.action_executed.emit(item.id, self.last_action_desc)
            self.block_activated.emit(target_block, item.id)
            return

        if item.action_type in ("SNIPPET", "KEY"):
            self.code_injector.execute_action(item)
            if item.action_type == "SNIPPET":
                self.text_injected.emit(len(item.snippet or ""))
            self.last_action_desc = _clean_action_label(item.label)
            self.action_executed.emit(item.id, self.last_action_desc)
            self.block_activated.emit(target_block, item.id)
            return

        if item.action_type == "EXIT" or item.id in ("CONFIRM_EXIT", "ACTION_EXIT"):
            self.exit_requested.emit()
            self.block_activated.emit(target_block, item.id)
            return

    def trigger_undo(self, action_id: str = "ACTION_UNDO") -> None:
        """Triggers Universal Undo (Ctrl+Z) in the active editor."""
        self._play_sound("undo")
        self.code_injector.send_key("UNDO")
        self.last_action_desc = "Deshacer (Ctrl+Z)"
        self.undo_requested.emit()
        self.action_executed.emit(action_id, self.last_action_desc)
        self.update()

    def set_gaze_estimator(self, estimator: Any) -> None:
        """Connects the GazeEstimator for 1-point micro-recalibration ('Snap to Caret')."""
        self.gaze_estimator = estimator

    def snap_to_caret(
        self,
        target_x: Optional[float] = None,
        target_y: Optional[float] = None,
    ) -> Tuple[float, float]:
        """
        Micro-recalibration 1-point ('Snap to Caret'):
        Re-centers gaze estimate without requiring a full 5-point recalibration.
        If target coordinates are not provided, aims at editor caret (0.35, 0.50) in
        RIGHT_DOCK or screen center (0.50, 0.50) in FULL_GRID.
        """
        if target_x is None:
            target_x = 0.35 if getattr(self, "hud_layout_mode", "FULL_GRID") == "RIGHT_DOCK" else 0.50
        if target_y is None:
            target_y = 0.50

        offset = (0.0, 0.0)
        if self.gaze_estimator is not None and hasattr(self.gaze_estimator, "micro_recalibrate"):
            offset = self.gaze_estimator.micro_recalibrate(target_x, target_y)

        self.micro_recalibration_requested.emit(target_x, target_y)
        self._play_sound("confirm")
        self.last_action_desc = "Snap Caret: Micro-recalibrado"
        self.update()
        return offset
