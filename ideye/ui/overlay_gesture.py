"""Facial gesture dispatch, health alerts and help modal toggle."""

from ideye.ui.overlay_common import *  # noqa: F401,F403
from ideye.ui.overlay_common import (  # noqa: F401
    _clean_action_label,
)


class OverlayGestureMixin:
    """Facial gesture dispatch, health alerts and help modal toggle."""

    def show_health_alert(self, message: str) -> None:
        """Shows a non-intrusive 4-second health reminder in the command bar."""
        self.last_action_desc = str(message)
        self.update()
        QTimer.singleShot(4000, self._clear_health_alert)

    def _clear_health_alert(self) -> None:
        if str(self.last_action_desc).startswith(("Vista fija", "Demasiado cerca")):
            self.last_action_desc = "Listo"
            self.update()

    def toggle_help_modal(self) -> None:
        """Toggles the in-app gesture and shortcut cheat sheet modal."""
        self.show_help_modal = not getattr(self, "show_help_modal", False)
        self._update_help_modal_rect()
        self.last_action_desc = "Guía de Gestos" if self.show_help_modal else "Cerrar Ayuda"
        self.update()

    @pyqtSlot(object, float)
    def on_mar_updated(self, _frame: Any, current_mar: float) -> None:
        """Receives the current mouth-aspect ratio for reticle click feedback."""
        try:
            self.current_mar = float(current_mar)
        except (TypeError, ValueError):
            self.current_mar = 0.0
        if not math.isfinite(self.current_mar):
            self.current_mar = 0.0
        self._mar_rest_window.append(self.current_mar)
        if len(self._mar_rest_window) >= 20:
            values = sorted(self._mar_rest_window)
            baseline = values[max(0, int(len(values) * 0.10) - 1)]
            self._mar_rest_baseline = max(0.10, min(0.60, float(baseline)))
        mouth_rest = max(0.0, float(getattr(config, "MAR_REST_THRESHOLD", 0.20)))
        if self.current_mar > mouth_rest + 0.04:
            self._wake_ghost_peek()
        if (
            self.current_context_mode_id == "sniper"
            and self.current_node_id != "MODE_SELECT"
            and not self.show_help_modal
            and not self.reading_mode
        ):
            self._update_freelook_mouth(self.current_mar)
            return
        if self.hovered_block is not None:
            self.update()

    @pyqtSlot(str)
    def on_gesture_triggered(self, gesture_name: str) -> None:
        """
        Handles facial gesture triggers:
        - 'MOUTH_CLICK': Gaze macro selection, menu navigation, snippet insertion.
        - 'WINK_RIGHT': Toggles Option B pause mode (hides/restores HUD completely).
        - 'WINK_LEFT': Submenu 'Volver atrás' (parent menu node), or Undo 'Ctrl+Z' at ROOT.
        """
        self._wake_ghost_peek()
        if gesture_name in ("MOUTH_CLICK", "WINK_LEFT", "WINK_RIGHT"):
            self.gaze_scroller.stop()
            if self._gaze_scroll_enabled:
                self._gaze_scroll_enabled = False
                self.gaze_scroll_toggled.emit(False)
        if getattr(self, "show_tutorial_modal", False):
            if self.tutorial_step == 2:
                self.tutorial_step = 3
                self.tutorial_step_progress = 0.0
                self._tutorial_rest_start = time.time()
                self._play_sound("confirm")
                self.update()
                return
            elif self.tutorial_step == 4:
                self.show_tutorial_modal = False
                self.update()
                return

        if self.show_help_modal and gesture_name == "MOUTH_CLICK":
            self.mouth_clicked.emit(self.hovered_block if self.hovered_block is not None else -1)
            open_guide = bool(getattr(self, "hovered_help_modal_guide", False))
            start_tut = bool(getattr(self, "hovered_help_modal_tutorial", False))
            self.show_help_modal = False
            self.hovered_help_modal_guide = False
            self.hovered_help_modal_tutorial = False
            self.hovered_help_modal_close = False
            if open_guide:
                self.last_action_desc = "Abriendo Manual Interactivo"
                self.interactive_guide_requested.emit()
            elif start_tut:
                self.start_mini_tutorial()
            else:
                self.last_action_desc = "Cerrar Ayuda"
            self.update()
            return

        if gesture_name == "BROW_RAISE":
            if self.current_context_mode_id == "sniper":
                if bool(getattr(config, "SNIPER_LENS_BROW_TRIGGER_ENABLED", False)) and (
                    not self._gaming_mode or self._gaming_control_state == "MENU_CURSOR"
                ):
                    self.activate_sniper_lens()
                return
            if self._active_diagnostics and "AUTO_FIX" in self.menu_tree:
                self.navigate_to("AUTO_FIX")
                self.last_action_desc = "Auto-Fix: elige una reparación"
            else:
                self._trigger_ai_prediction()
                self.last_action_desc = "Sugerencias de contexto"
            self.update()
            return

        if gesture_name in ("HEAD_TILT_RIGHT", "HEAD_TILT_LEFT"):
            if self.current_context_mode_id in ("coding", "writing", "terminal"):
                key = "TAB" if gesture_name == "HEAD_TILT_RIGHT" else "SHIFT_TAB"
                try:
                    self.code_injector.send_key(key)
                except Exception:
                    pass
                self.last_action_desc = "Indentar" if key == "TAB" else "Des-indentar"
                self._play_sound("click")
                self.update()
            return

        if gesture_name == "WINK_RIGHT":
            if self.current_context_mode_id == "sniper" and self._gaming_mode:
                self._toggle_gaming_right()
                return
            self._play_sound("pause")
            if self.show_help_modal:
                self.show_help_modal = False
                self.update()
            self.toggle_reading_mode()
            self.last_action_desc = "Modo Edición (HUD Restaurado)" if not self.reading_mode else "Modo Reposo (HUD Oculto)"
            self.block_activated.emit(4, "PAUSE_RESUME")
            return

        if gesture_name == "WINK_LEFT":
            if self.sniper_lens.active:
                self.sniper_lens.deactivate()
                self.last_action_desc = "Lupa Sniper desactivada"
                self.update()
                return
            if self.current_context_mode_id == "sniper":
                if self._gaming_mode and self.mouse_controller is not None:
                    self.mouse_controller.tap_key(" ")
                    self._play_sound("click")
                else:
                    self._exit_sniper_mode()
                return
            self._play_sound("back")
            if self.show_help_modal:
                self.show_help_modal = False
                self.last_action_desc = "Cerrar Ayuda"
                self.update()
                return
            if self.reading_mode:
                return
            if self.current_node_id != "ROOT":
                target_id = (self.current_node.parent_id if self.current_node and self.current_node.parent_id else "ROOT") or "ROOT"
                self.navigate_to(target_id)
                target_title = self.menu_tree[target_id].title if target_id in self.menu_tree else "RAÍZ"
                self.last_action_desc = f"Volver a {target_title}"
                self.block_activated.emit(6, "ACTION_BACK")
                self.update()
                return
            else:
                if self.code_injector.is_busy:
                    return
                self.trigger_undo()
                self.block_activated.emit(0, "ACTION_UNDO")
                return

        if gesture_name != "MOUTH_CLICK":
            return

        self._last_mouth_click_time = time.time()
        self.mouth_clicked.emit(self.hovered_block if self.hovered_block is not None else -1)

        # Dismiss cheat sheet modal if open
        if self.show_help_modal:
            self.show_help_modal = False
            self.last_action_desc = "Cerrar Ayuda"
            self.update()
            return

        self._play_sound("click")

        # Hands-free header exit: first click arms, second click exits.
        if self.hovered_header_exit:
            self.hovered_header_exit = False
            self.active_click_header_exit = True
            QTimer.singleShot(int(config.CLICK_FLASH_DURATION_SEC * 1000), self._clear_header_exit_flash)
            now = time.time()
            if now < self._exit_armed_until:
                self._exit_armed_until = 0.0
                self.last_action_desc = "Saliendo..."
                self.update()
                self.exit_requested.emit()
                return
            arm_sec = float(getattr(config, "EXIT_DOUBLE_CLICK_SEC", 1.5))
            self._exit_armed_until = now + arm_sec
            self.last_action_desc = "SALIR: pulsa otra vez para confirmar"
            QTimer.singleShot(int(arm_sec * 1000), self._disarm_exit)
            self.update()
            return

        # Hands-free header help click handler
        if getattr(self, "hovered_header_help", False):
            self.hovered_header_help = False
            self.active_click_header_help = True
            QTimer.singleShot(int(config.CLICK_FLASH_DURATION_SEC * 1000), self._clear_header_help_flash)
            self.toggle_help_modal()
            self.last_action_desc = "Guía de Gestos"
            self.update()
            return

        # Multi-monitor selector
        if getattr(self, "hovered_header_screen", False):
            self.hovered_header_screen = False
            self.screen_cycle_requested.emit()
            return

        # In-game Joystick / Menu-cursor switch.
        if getattr(self, "hovered_gaming_toggle", False):
            self.hovered_gaming_toggle = False
            self._toggle_gaming_right()
            return

        # Sniper action selector (only visible in sniper mode)
        if getattr(self, "hovered_sniper_action", False):
            self.hovered_sniper_action = False
            self._cycle_sniper_action()
            return

        # Hands-free header mode click handler
        if getattr(self, "hovered_header_mode", False):
            self.hovered_header_mode = False
            self.active_click_header_mode = True
            QTimer.singleShot(int(config.CLICK_FLASH_DURATION_SEC * 1000), self._clear_header_mode_flash)
            self.open_mode_selector()
            return

        # Hands-free header language click handler
        if getattr(self, "hovered_header_lang", False):
            self.hovered_header_lang = False
            self.active_click_header_lang = True
            QTimer.singleShot(int(config.CLICK_FLASH_DURATION_SEC * 1000), self._clear_header_lang_flash)
            self.navigate_to("LANG_SELECT")
            self.last_action_desc = "Seleccionar Lenguaje"
            self.update()
            return

        # FreeLook handles mouth clicks in on_mar_updated (click vs. hold).
        # Confirmed MOUTH_CLICK is a fallback when MAR sampling misses a quick
        # opening; duplicate suppression lives in _freelook_click.
        if self.current_context_mode_id == "sniper" and self.current_node_id != "MODE_SELECT":
            if not self.reading_mode and not self._mouth_active and not self._hold_started:
                self._freelook_click()
            return

        target_block = self.hovered_block
        if target_block is None:
            return

        if self.reading_mode:
            if target_block == 4:
                # Resume active mode
                self.trigger_click_flash(4)
                self.toggle_reading_mode()
            return

        # Do not accumulate facial clicks while an injection is actively running.
        # Writing mode queues full-word insertions without blocking on each paste.
        if self.code_injector.is_busy and target_block != 4 and self.current_context_mode_id != "writing":
            return

        self.trigger_click_flash(target_block)

        # Retrieve active menu node and targeted item
        curr_node = self.current_node
        if curr_node is None or not (0 <= target_block < len(curr_node.items)):
            return

        item: MenuAction = curr_node.items[target_block]

        # 1. Pause / Reading Mode Trigger (Center block or PAUSE action)
        if target_block == 4 or item.action_type == "PAUSE":
            self.toggle_reading_mode()
            self.last_action_desc = "Modo Reposo Activo"
            self.block_activated.emit(target_block, "PAUSE_RESUME")
            return

        # 2. Back Navigation (Index 6 in submenus or BACK action)
        if item.action_type == "BACK":
            target_id = item.submenu_id or curr_node.parent_id or "ROOT"
            self.navigate_to(target_id)
            target_title = self.menu_tree[target_id].title if target_id in self.menu_tree else "RAÍZ"
            self.last_action_desc = f"Volver a {target_title}"
            self.block_activated.emit(target_block, item.id)
            return

        # Sniper step 1: lock the macro sector and show its precision sub-grid.
        if item.action_type == "SNIPER_SECTOR":
            try:
                self._sniper_locked_sector = int(item.snippet)
            except (TypeError, ValueError):
                self._sniper_locked_sector = None
            if self._sniper_locked_sector is not None:
                self._sniper_step = 2
                self.hovered_subcell = self._subcell_from_gaze(*self.current_gaze)
                self.last_action_desc = f"Sector {self._sniper_locked_sector + 1}"
                self._play_sound("mode")
                self.update()
            self.block_activated.emit(target_block, item.id)
            return

        # 3. Context Mode Selection from the mode hub
        if item.action_type == "MODE_SWITCH":
            self._activate_mode(item.mode_id)
            self.block_activated.emit(target_block, item.id)
            return

        # 3b. Writing-mode complete words and phrases
        if self._handle_writing_action(item, target_block):
            return

        # 4. Submenu Forward Navigation
        if item.action_type == "SUBMENU":
            target_id = item.submenu_id
            if target_id and target_id in self.menu_tree:
                self.navigate_to(target_id)
                self.last_action_desc = f"Menú: {self.menu_tree[target_id].title}"
            self.block_activated.emit(target_block, item.id)
            return

        # 4. AI Regenerate / Refresh Action
        if item.action_type == "AI_REFRESH" or item.id == "AI_REGENERATE":
            self._trigger_ai_prediction()
            self.block_activated.emit(target_block, item.id)
            return

        # 5. Language Selection Triggers
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

        # 6. Code / Key Injection (SNIPPET or KEY)
        if item.action_type in ("SNIPPET", "KEY"):
            # Ignore placeholder while predicting
            if item.action_type == "SNIPPET" and (not item.snippet or "Analizando..." in item.snippet):
                return

            # Execute injection via non-blocking worker thread
            self.code_injector.execute_action(item)
            self.last_action_desc = _clean_action_label(item.label)
            self.action_executed.emit(item.id, self.last_action_desc)
            self.block_activated.emit(target_block, item.id)

            # Sticky Evaluation:
            # If neither the action nor the current node is sticky, return to ROOT!
            is_sticky = item.sticky or curr_node.sticky
            if not is_sticky and self.current_node_id != "ROOT":
                self.navigate_to("ROOT")
            else:
                self.update()
            return

        # 7. Exit Trigger
        if item.action_type == "EXIT" or item.id in ("CONFIRM_EXIT", "ACTION_EXIT"):
            self.exit_requested.emit()
            self.block_activated.emit(target_block, item.id)
            return

        # Fallback default emission
        self.block_activated.emit(target_block, item.id)
