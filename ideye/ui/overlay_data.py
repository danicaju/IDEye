"""Current node, clipboard, macros and AI predictions."""

from ideye.ui.overlay_common import *  # noqa: F401,F403


class OverlayDataMixin:
    """Current node, clipboard, macros and AI predictions."""

    @property
    def current_node(self) -> MenuNode:
        """Returns the currently active MenuNode, adapting dynamically when at ROOT with 250ms render caching."""
        if self.current_node_id == "ROOT" and getattr(self, "adaptive_ast_enabled", True) and getattr(self, "current_context_mode_id", "coding") == "coding":
            now = time.time()
            if self._cached_adaptive_node is not None and (now - self._last_ast_eval_time < 0.25):
                return self._cached_adaptive_node

            std_root = self.menu_tree.get("ROOT")
            if self.context_reader:
                ctx_info = self.context_reader.detect_syntactic_context(language=self.current_language)
            else:
                ctx_info = detect_syntactic_context(language=self.current_language)
            ctx_name = ctx_info.get("context", "GENERAL")
            if ctx_name != self._last_detected_context_name:
                self._last_detected_context_name = ctx_name
                self.ast_context_detected.emit(ctx_name)
            node = get_adaptive_context_node(ctx_info, std_root, language=self.current_language)
            if ctx_name != "GENERAL":
                try:
                    dyn_action = get_dynamic_ast_action_for_context(ctx_info, self.current_language, "9")
                    if len(node.items) > 8:
                        items_copy = list(node.items)
                        items_copy[8] = dyn_action
                        node = MenuNode(
                            id=node.id,
                            title=node.title,
                            breadcrumb_label=node.breadcrumb_label,
                            items=items_copy,
                            parent_id=node.parent_id,
                            sticky=node.sticky,
                        )
                except Exception:
                    pass
            if self.macro_manager is not None:
                try:
                    node = self.macro_manager.apply_overrides(node, "coding")
                except Exception:
                    pass
            self._cached_adaptive_node = node
            self._last_ast_eval_time = now
            return node
        return self.menu_tree.get(self.current_node_id, self.menu_tree.get("ROOT"))

    def set_clipboard_manager(self, manager: Optional[Any]) -> None:
        """Connects the Phase 9 clipboard history manager and injector lock."""
        self.clipboard_manager = manager
        if hasattr(self.code_injector, "set_clipboard_history"):
            self.code_injector.set_clipboard_history(manager)
        if manager is not None and hasattr(manager, "history_changed"):
            try:
                manager.history_changed.connect(self.refresh_clipboard_menu)
            except (TypeError, RuntimeError):
                pass
        self.refresh_clipboard_menu()

    def refresh_clipboard_menu(self) -> None:
        if self.clipboard_manager is None:
            return
        node = self.menu_tree.get("CLIPBOARD_HISTORY")
        parent_id = node.parent_id if node is not None and node.parent_id else "ROOT"
        try:
            self.menu_tree["CLIPBOARD_HISTORY"] = (
                self.clipboard_manager.get_clipboard_menu_node(parent_id=parent_id)
            )
            if self.current_node_id == "CLIPBOARD_HISTORY":
                self.update()
        except Exception as exc:
            logger.warning("Could not refresh clipboard menu: %s", exc)

    def open_clipboard_history(self) -> bool:
        if self.clipboard_manager is None:
            return False
        current = self.current_node_id if self.current_node_id != "CLIPBOARD_HISTORY" else "ROOT"
        try:
            self.menu_tree["CLIPBOARD_HISTORY"] = (
                self.clipboard_manager.get_clipboard_menu_node(parent_id=current)
            )
        except Exception as exc:
            logger.warning("Could not open clipboard history: %s", exc)
            return False
        return self.navigate_to("CLIPBOARD_HISTORY")

    def set_screen_info(self, index: int, count: int) -> None:
        """Updates the compact multi-monitor selector in the command bar."""
        self.screen_count = max(1, int(count))
        self.screen_index = max(0, min(int(index), self.screen_count - 1))
        self._update_header_exit_rect()
        self.update()

    def set_macro_manager(self, manager: Optional[Any]) -> None:
        self.macro_manager = manager
        self._apply_macro_overrides()
        self.update()

    def _apply_macro_overrides(self) -> None:
        if self.macro_manager is None:
            return
        mode_id = getattr(self, "current_context_mode_id", "coding")
        try:
            if "ROOT" in self.menu_tree:
                self.menu_tree["ROOT"] = self.macro_manager.apply_overrides(
                    self.menu_tree["ROOT"], mode_id
                )
            if "MENU_STANDARD" in self.menu_tree:
                self.menu_tree["MENU_STANDARD"] = self.macro_manager.apply_overrides(
                    self.menu_tree["MENU_STANDARD"], mode_id
                )
        except Exception as exc:
            logger.warning(f"[Overlay] Warning: could not apply custom macros: {exc}")
        self._cached_adaptive_node = None
        self._last_ast_eval_time = 0.0

    def refresh_custom_macros(self, mode_id: Optional[str] = None) -> None:
        """Re-applies custom macros after the editor saves."""
        if mode_id is not None and str(mode_id).lower() != str(
            getattr(self, "current_context_mode_id", "coding")
        ).lower():
            return
        self._apply_macro_overrides()
        self.update()

    @pyqtSlot(str)
    def on_file_linked(self, file_path: str) -> None:
        """Called when a user explicitly links a Python script."""
        self._cached_adaptive_node = None
        self._last_ast_eval_time = 0.0
        if self.context_reader:
            self.context_reader.set_active_file(file_path)
            self.last_action_desc = f"Vinculado: {os.path.basename(file_path)}"
            self.update()

    def _trigger_ai_prediction(self) -> None:
        """
        Triggers async AIPredictorWorker.
        Prevents duplicate workers if one is already running (QA Requirement 3).
        Sets overlay to loading state 'Analizando...' and updates 6 blocks dynamically.
        Extracts context non-blockingly on worker thread.
        """
        if self.ai_predictor_worker is not None:
            if self.ai_predictor_worker.isRunning():
                return
            old_worker = self.ai_predictor_worker
            try:
                old_worker.predictions_ready.disconnect()
                old_worker.status_changed.disconnect()
                old_worker.prediction_failed.disconnect()
                old_worker.finished.disconnect()
            except Exception:
                pass
            try:
                old_worker.wait(250)
                old_worker.deleteLater()
            except Exception:
                pass
            self.ai_predictor_worker = None

        loading_preds = [
            "Analizando...",
            "Analizando...",
            "Analizando...",
            "Analizando...",
            "Analizando...",
            "Analizando...",
        ]
        if self.menu_tree and "SNIPPETS" in self.menu_tree:
            self.menu_tree["SNIPPETS"].items = populate_ai_prediction_items(loading_preds, parent_id="ROOT")
        self.is_ai_predicting = True
        self.last_action_desc = "Buscando sugerencias..."
        self.ai_status_updated.emit("Buscando sugerencias...")
        self.update()

        editor_ctx = self.context_reader.get_editor_context() if self.context_reader else {}
        pref = editor_ctx.get("prefix_lines") or []
        curr = editor_ctx.get("current_line") or ""
        live_context = ""
        if pref or curr:
            combo = list(pref[-30:])
            if curr:
                combo.append(curr)
            live_context = "\n".join(combo)
        live_symbols = editor_ctx.get("local_symbols") or []

        self.ai_predictor_worker = AIPredictorWorker(
            context_text=live_context,
            local_symbols=live_symbols,
            provider=getattr(config, "LLM_PROVIDER", "ollama"),
            endpoint=getattr(config, "LLM_ENDPOINT", "http://localhost:11434/api/generate"),
            model=getattr(config, "LLM_MODEL", "codellama"),
            timeout=getattr(config, "LLM_TIMEOUT_SEC", 2.5),
            api_key=getattr(config, "LLM_API_KEY", ""),
            temperature=getattr(config, "LLM_TEMPERATURE", 0.2),
            context_reader=self.context_reader,
            document_context=bool(getattr(self.context_reader, "document_context_active", False)),
            document_title=str(getattr(getattr(self.context_reader, "document_buffer", None), "title", "")),
            parent=self,
        )
        self.ai_predictor_worker.predictions_ready.connect(self._on_ai_predictions_ready)
        self.ai_predictor_worker.status_changed.connect(self._on_ai_status_changed)
        self.ai_predictor_worker.prediction_failed.connect(self._on_ai_prediction_failed)
        self.ai_predictor_worker.finished.connect(self._on_ai_worker_finished)
        self.ai_predictor_worker.start()

    @pyqtSlot(list)
    def _on_ai_predictions_ready(self, predictions: List[str]) -> None:
        """Called when AIPredictorWorker finishes with 6 suggestions."""
        if self.menu_tree and "SNIPPETS" in self.menu_tree:
            self.menu_tree["SNIPPETS"].items = populate_ai_prediction_items(predictions, parent_id="ROOT")
        self.diagnostics_fixer.set_ai_suggestions(predictions)
        if self._active_diagnostics:
            self.set_diagnostics(self._active_diagnostics)
        self.is_ai_predicting = False
        self.last_action_desc = "6 sugerencias listas"
        self.ai_status_updated.emit("Listo (6 sugerencias)")
        self.update()

    @pyqtSlot(str)
    def _on_ai_status_changed(self, status: str) -> None:
        """Emits AI status update."""
        self.ai_status_updated.emit(status)

    @pyqtSlot(str)
    def _on_ai_prediction_failed(self, error_msg: str) -> None:
        """Handles prediction failure notification."""
        self.ai_status_updated.emit(f"Error: {error_msg}")

    @pyqtSlot()
    def _on_ai_worker_finished(self) -> None:
        """Worker lifecycle completion."""
        self.is_ai_predicting = False

    def navigate_to(self, node_id: str) -> bool:
        """
        Navigates to a target menu node by ID.
        Updates state, refreshes dynamic nodes on demand, and triggers repaint.
        """
        if node_id in self.menu_tree:
            self.current_node_id = node_id
            self._cached_adaptive_node = None
            self._last_ast_eval_time = 0.0
            if node_id in ("SNIPPETS", "AI_PREDICT"):
                self._trigger_ai_prediction()
            self._dwell_start_time = time.time()
            self._dwell_progress = 0.0
            self._dwell_fired = False
            self.menu_navigated.emit(node_id)
            self.update()
            return True
        return False
