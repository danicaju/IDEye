"""Writing mode actions, diagnostics, AST symbols and agentic launcher."""

from ideye.ui.overlay_common import *  # noqa: F401,F403


class OverlayWritingMixin:
    """Writing mode actions, diagnostics, AST symbols and agentic launcher."""

    def _writing_mode(self):
        """Returns the WritingMode instance when available."""
        if self.mode_manager is None:
            return None
        try:
            return self.mode_manager.get_mode("writing")
        except Exception:
            return None

    def _refresh_writing_predictions(self) -> None:
        """Refreshes the prediction panel after a T9 letter or word change."""
        mode = self._writing_mode()
        node = self.menu_tree.get("WRITING_PREDICT")
        if mode is None or node is None or not hasattr(mode, "build_prediction_items"):
            return
        try:
            node.items = mode.build_prediction_items()
        except Exception:
            pass

    def _erase_typed_prefix(self, mode: Any) -> int:
        """Deletes the letters already typed for the current word.

        A suggestion replaces the word being written, so the letters the user
        typed one by one ("f") must go before "Por favor" is inserted, or the
        text ends up as "fPor favor".
        """
        count = len(getattr(mode, "_prefix", "") or "")
        for _ in range(count):
            self.code_injector.send_key("BACKSPACE")
        return count

    def _handle_writing_action(self, item: MenuAction, target_block: int = 0) -> bool:
        """Executes T9/writing actions and returns True when handled."""
        action_type = getattr(item, "action_type", "")
        if action_type not in {
            "WRITING_LETTER",
            "WRITING_WORD",
            "WRITING_SPACE",
            "WRITING_BACKSPACE",
            "WRITING_CASE",
            "WRITING_AI",
        }:
            # Selecting a whole phrase also starts a new word context.
            if self.current_node_id == "WRITING_WORDS" and action_type == "SNIPPET":
                mode = self._writing_mode()
                if mode is not None:
                    self._erase_typed_prefix(mode)
                    mode.reset_prefix()
                    self._refresh_writing_predictions()
            return False

        mode = self._writing_mode()
        if mode is None:
            return False

        if action_type == "WRITING_AI":
            cmd = getattr(item, "snippet", "") or "rephrase"
            self._execute_writing_ai(cmd, item, target_block)
            return True

        if action_type == "WRITING_LETTER":
            text = mode.record_letter(item.snippet or "")
            if text:
                self.code_injector.insert_snippet(text)
                self.text_injected.emit(len(text))
            self._refresh_writing_predictions()
            self.last_action_desc = f"Letra: {text}" if text else "Letra"
            self.action_executed.emit(item.id, self.last_action_desc)
            self.block_activated.emit(target_block, item.id)
            self.update()
            return True

        if action_type == "WRITING_WORD":
            word = mode.apply_case_to_word(item.snippet or "")
            if word:
                self._erase_typed_prefix(mode)
                self.code_injector.insert_snippet(word + " ")
                self.text_injected.emit(len(word) + 1)
            mode.reset_prefix()
            self._refresh_writing_predictions()
            self.navigate_to("WRITING_T9")
            self.last_action_desc = f"Palabra: {word}" if word else "Palabra"
            self.action_executed.emit(item.id, self.last_action_desc)
            self.block_activated.emit(target_block, item.id)
            return True

        if action_type == "WRITING_SPACE":
            self.code_injector.insert_snippet(" ")
            self.text_injected.emit(1)
            mode.record_space()
            self._refresh_writing_predictions()
            self.last_action_desc = "Espacio"
            self.action_executed.emit(item.id, self.last_action_desc)
            self.block_activated.emit(target_block, item.id)
            self.update()
            return True

        if action_type == "WRITING_BACKSPACE":
            self.code_injector.send_key("BACKSPACE")
            mode.record_backspace()
            self._refresh_writing_predictions()
            self.last_action_desc = "Borrar carácter"
            self.action_executed.emit(item.id, self.last_action_desc)
            self.block_activated.emit(target_block, item.id)
            self.update()
            return True

        if action_type == "WRITING_CASE":
            enabled = mode.toggle_uppercase()
            self.last_action_desc = f"Mayúsculas: {'ON' if enabled else 'OFF'}"
            self.action_executed.emit(item.id, self.last_action_desc)
            self.block_activated.emit(target_block, item.id)
            self.update()
            return True

        return False

    def _execute_writing_ai(self, cmd: str, item: MenuAction, target_block: int = 0) -> None:
        """Executes real AI writing assist (rephrase, correct, summarize, etc.) hands-free."""
        try:
            from ideye.modes.writing_mode import WRITING_AI_PROMPTS, correct_writing_text, rephrase_writing_text
        except ImportError:
            WRITING_AI_PROMPTS = {}
            correct_writing_text = lambda s: s
            rephrase_writing_text = lambda s: s

        target_text = ""
        has_active_selection = False
        if self._vscode_editor_state:
            target_text = str(self._vscode_editor_state.get("selection") or "").strip()
            if target_text:
                has_active_selection = True
        if not target_text and self.context_reader:
            ctx = self.context_reader.get_editor_context()
            target_text = str(ctx.get("active_selection") or "").strip()
            if target_text:
                has_active_selection = True
            elif ctx.get("current_line"):
                target_text = str(ctx.get("current_line") or "").strip()
        if not target_text and self.context_reader:
            target_text = self.context_reader.get_last_line()
        if not target_text:
            mode = self._writing_mode()
            target_text = getattr(mode, "_prefix", "") if mode else ""

        ws = getattr(self.code_injector, "websocket_bridge", None)
        ws_connected = ws is not None and getattr(ws, "is_connected", False)

        if cmd in ("correct", "rephrase") and target_text:
            transformed = correct_writing_text(target_text) if cmd == "correct" else rephrase_writing_text(target_text)
            if transformed and transformed != target_text:
                if ws_connected:
                    if has_active_selection:
                        ws.send_insert_snippet(snippet=transformed)
                    else:
                        line_no = 1
                        if self._vscode_editor_state and isinstance(self._vscode_editor_state.get("cursor"), dict):
                            line_no = max(1, int(self._vscode_editor_state["cursor"].get("line", 0)) + 1)
                        ws.send_apply_line_fix(line=line_no, replacement=transformed)
                else:
                    self.code_injector.insert_snippet(transformed)

                self.last_action_desc = "Texto corregido" if cmd == "correct" else "Texto reformulado"
                self.action_executed.emit(item.id, self.last_action_desc)
                self.block_activated.emit(target_block, item.id)
                self.update()
                return

        sample = target_text or "el texto seleccionado"
        template = WRITING_AI_PROMPTS.get(cmd, "Reformula o asiste en la redacción del siguiente texto:\n\n{text}")
        prompt = template.format(text=sample)

        if ws_connected:
            if hasattr(self, "agentic_launcher") and self.agentic_launcher is not None:
                self.agentic_launcher.dispatch(cmd, prompt, bridge=ws, selection_only=bool(target_text))
            elif hasattr(ws, "send_trigger_agent_prompt"):
                ws.send_trigger_agent_prompt(action_id=cmd, prompt=prompt, selection_only=bool(target_text))
            self.last_action_desc = f"IA: {item.hint} enviado a VS Code"
        else:
            if hasattr(self, "copy_agentic_prompt"):
                self.copy_agentic_prompt(prompt)
            elif hasattr(self.code_injector, "clipboard") and hasattr(self.code_injector.clipboard, "copy"):
                self.code_injector.clipboard.copy(prompt)
            self.last_action_desc = f"Prompt de {item.hint} en portapapeles"

        self.action_executed.emit(item.id, self.last_action_desc)
        self.block_activated.emit(target_block, item.id)
        self.update()

    def _restore_autofix_slot(self) -> None:
        saved = self._autofix_slot8_saved
        root = self.menu_tree.get("ROOT") if hasattr(self, "menu_tree") else None
        if saved and root and len(root.items) >= 8:
            slot = root.items[7]
            for key, value in saved.items():
                try:
                    setattr(slot, key, value)
                except Exception:
                    pass
        self._autofix_slot8_saved = None

    def set_diagnostics(self, diagnostics: List[Dict[str, Any]]) -> None:
        """Publishes live diagnostics and exposes the one-click Auto-Fix menu."""
        self._active_diagnostics = [d for d in (diagnostics or []) if isinstance(d, dict)]
        self.diagnostics_fixer.last_diagnostics = list(self._active_diagnostics)
        self.diagnostics_fixer.build_fixes(self._active_diagnostics, {
            "symbols": self.context_reader.extract_local_symbols() if self.context_reader else [],
            "ai_suggestions": self.diagnostics_fixer.ai_suggestions,
        })
        root = self.menu_tree.get("ROOT") if hasattr(self, "menu_tree") else None
        if self.current_context_mode_id == "coding" and self._active_diagnostics and root and len(root.items) >= 8:
            if self._autofix_slot8_saved is None:
                slot = root.items[7]
                self._autofix_slot8_saved = {
                    "label": slot.label, "hint": slot.hint, "action_type": slot.action_type,
                    "snippet": slot.snippet, "key_name": slot.key_name,
                    "submenu_id": slot.submenu_id, "icon": slot.icon,
                }
            slot = root.items[7]
            slot.label = "8: AUTO-FIX"
            slot.hint = self.diagnostics_fixer.badge_text(self._active_diagnostics) or "Reparar el error actual"
            slot.action_type = "SUBMENU"
            slot.submenu_id = "AUTO_FIX"
            slot.snippet = None
            slot.key_name = None
            slot.icon = "edit"
            self.menu_tree["AUTO_FIX"] = self.diagnostics_fixer.get_autofix_menu_node(parent_id="ROOT")
        else:
            self._restore_autofix_slot()
        self.update()

    def open_ast_symbols(self, refresh: bool = True) -> None:
        """Builds the current file symbol map and opens its 3x3 page."""
        symbols = self.ast_code_jumper.extract_symbols() if refresh else self.ast_code_jumper.symbols
        if not symbols:
            self.last_action_desc = "AST: no hay símbolos en el archivo activo"
            self.update()
            return
        self._ast_page = 0
        self.menu_tree["AST_SYMBOLS"] = self.ast_code_jumper.get_symbols_menu_node(
            symbols, self._ast_page, parent_id="ROOT"
        )
        self.navigate_to("AST_SYMBOLS")
        self.last_action_desc = f"AST: {len(symbols)} símbolos"
        self.update()

    def open_agentic_launcher(self, refresh: bool = True) -> None:
        """Opens the six-action Agentic Prompt Launcher from any mode."""
        self.menu_tree["AGENTIC_LAUNCHER"] = self.agentic_launcher.get_agentic_menu_node(
            parent_id="ROOT"
        )
        self.navigate_to("AGENTIC_LAUNCHER")
        self.last_action_desc = "Agentic: elige una orden de ingeniería"
        self.update()

    def copy_agentic_prompt(self, prompt: str) -> bool:
        """Copies a rich agentic prompt to the system clipboard."""
        try:
            clipboard = QGuiApplication.clipboard()
            if clipboard is not None:
                clipboard.setText(str(prompt or ""))
                return True
        except Exception:
            pass
        return False

    def _current_agentic_context(self) -> Dict[str, Any]:
        state = getattr(self, "_vscode_editor_state", {}) or {}
        cursor = state.get("cursor") if isinstance(state, dict) else None
        cursor_line = None
        if isinstance(cursor, dict):
            try:
                cursor_line = int(cursor.get("line", 0)) + 1
            except (TypeError, ValueError):
                cursor_line = None
        return {
            "file_path": self.context_reader.get_active_file() if self.context_reader else "",
            "source_code": self.context_reader.read_file_content() if self.context_reader else "",
            "language": self.context_reader.get_active_language() if self.context_reader else "",
            "cursor_line": cursor_line,
            "diagnostics": list(getattr(self, "_active_diagnostics", []) or []),
        }
