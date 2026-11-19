"""Ghost peek, reduced motion, gaze scroll, reading mode and click flashes."""

from ideye.ui.overlay_common import *  # noqa: F401,F403


class OverlayGhostMixin:
    """Ghost peek, reduced motion, gaze scroll, reading mode and click flashes."""

    def _ghost_card_opacity(self) -> float:
        """Returns the live card-only opacity used by Ghost-Peek."""
        return float(max(0.15, min(1.0, self._ghost_opacity))) if self.ghost_peek_enabled else 1.0

    def update_ghost_peek(
        self,
        now: Optional[float] = None,
        idle_seconds: Optional[float] = None,
        target_opacity: float = 0.15,
    ) -> float:
        """Advances the Ghost-Peek fade and wake animation."""
        if not self.ghost_peek_enabled:
            self._ghost_opacity = 1.0
            return 1.0
        timestamp = time.time() if now is None else float(now)
        idle_threshold = (
            self.ghost_peek_idle_seconds
            if idle_seconds is None
            else max(2.0, float(idle_seconds))
        )
        idle = max(0.0, timestamp - self._last_ghost_interaction)
        if idle >= idle_threshold:
            target = max(0.15, min(1.0, float(target_opacity)))
            if self._ghost_opacity > target:
                if self.reduced_motion:
                    self._ghost_opacity = target
                else:
                    self._ghost_opacity = max(target, self._ghost_opacity - 0.08)
            else:
                self._ghost_opacity = target
        elif self._ghost_opacity < 1.0:
            self._ghost_opacity = 1.0
        return self._ghost_opacity

    def _tick_ghost_peek(self) -> None:
        before = self._ghost_opacity
        self.update_ghost_peek()
        if abs(self._ghost_opacity - before) > 1e-4:
            self.update()

    def _wake_ghost_peek(self) -> None:
        self._last_ghost_interaction = time.time()
        if self._ghost_opacity < 1.0:
            self._ghost_opacity = 1.0
            self.update()

    def set_ghost_peek_enabled(self, enabled: bool, emit_signal: bool = True) -> None:
        self.ghost_peek_enabled = bool(enabled)
        if not self.ghost_peek_enabled:
            self._ghost_opacity = 1.0
        else:
            self._last_ghost_interaction = time.time()
        if emit_signal:
            self.ghost_peek_toggled.emit(self.ghost_peek_enabled)

    def set_ghost_peek_idle_seconds(self, seconds: float) -> float:
        """Sets the minimum idle time before Ghost-Peek starts fading."""
        try:
            value = float(seconds)
        except (TypeError, ValueError, OverflowError):
            value = 30.0
        self.ghost_peek_idle_seconds = max(2.0, value)
        self.update()
        return self.ghost_peek_idle_seconds

    def set_reduced_motion(self, enabled: bool, emit_signal: bool = True) -> None:
        """Turns gradual transitions off (instant state changes) or back on."""
        self.reduced_motion = bool(enabled)
        if self.reduced_motion and self._right_margin_animation is not None:
            self._right_margin_animation.stop()
            self._right_margin_animation = None
            self.refresh_grid_right_margin(animate=False)
        if emit_signal:
            self.reduced_motion_toggled.emit(self.reduced_motion)
        self.update()

    def toggle_ghost_peek(self) -> bool:
        self.set_ghost_peek_enabled(not self.ghost_peek_enabled)
        return self.ghost_peek_enabled

    def toggle_gaze_scroll(self, enabled: Optional[bool] = None) -> bool:
        """Toggles proportional inertial scrolling for the current gaze."""
        next_state = (not self._gaze_scroll_enabled) if enabled is None else bool(enabled)
        if next_state:
            self.gaze_scroller.activate()
            self._last_ghost_interaction = time.time()
        else:
            self.gaze_scroller.stop()
        self._gaze_scroll_enabled = next_state
        self.gaze_scroll_toggled.emit(next_state)
        self.last_action_desc = "Scroll ocular activado" if next_state else "Scroll ocular desactivado"
        self.update()
        return next_state

    def _apply_gaze_scroll(self, gy: float) -> None:
        if not self._gaze_scroll_enabled or self.reading_mode or self.show_help_modal:
            return
        if self.current_context_mode_id == "sniper":
            return
        if self.mouse_controller is None:
            return
        try:
            self.gaze_scroller.update(float(gy), dt=1.0 / 60.0, active=True)
            steps = int(self.gaze_scroller.last_steps)
            horizontal = int(self.gaze_scroller.last_horizontal_steps)
            if steps:
                self.mouse_controller.scroll(steps)
            if horizontal:
                self.mouse_controller.scroll_horizontal(horizontal)
        except Exception:
            pass

    def toggle_reading_mode(self) -> None:
        """Toggles between Active HUD mode and Hidden/Reading Mode (Option B: full hide)."""
        self.reading_mode = not self.reading_mode
        self.current_opacity = config.OVERLAY_OPACITY_READING if self.reading_mode else config.OVERLAY_OPACITY_ACTIVE
        if self.reading_mode:
            self.release_freelook_controls()
            self.gaze_scroller.stop()
            self._gaze_scroll_enabled = False
            self.hovered_block = None
            self._dwell_block = None
            self._dwell_progress = 0.0
            self._dwell_fired = False
            self.hide()
        else:
            self._dwell_start_time = time.time()
            self._dwell_progress = 0.0
            self._dwell_fired = False
            self.show()
            self.raise_()
            self._wake_ghost_peek()
        self.reading_mode_toggled.emit(self.reading_mode)
        self.update()

    def pause_hud(self) -> None:
        """Pauses and hides the HUD completely (Option B)."""
        if not self.reading_mode:
            self.toggle_reading_mode()

    def resume_hud(self) -> None:
        """Resumes and restores the HUD completely (Option B)."""
        if self.reading_mode:
            self.toggle_reading_mode()

    def toggle_pause(self) -> None:
        """Toggles pause/hidden state of the HUD (Option B)."""
        self.toggle_reading_mode()

    def trigger_click_flash(self, block_idx: int) -> None:
        """Triggers vibrant green active highlight on clicked block."""
        self.active_click_block = block_idx
        self.update()
        QTimer.singleShot(int(config.CLICK_FLASH_DURATION_SEC * 1000), self._clear_click_flash)

    def _clear_click_flash(self) -> None:
        self.active_click_block = None
        self.update()

    def _get_category_for_item(self, item: MenuAction, block_idx: int) -> str:
        """Determines the semantic category for a menu action block."""
        if block_idx == 4 or item.action_type == "PAUSE":
            return "PAUSE"
        if item.action_type == "MODE_SWITCH":
            return "MODE"
        if item.action_type == "SNIPER_SECTOR":
            return "SNIPER"
        if item.action_type == "BACK":
            return "BACK"
        if (
            item.action_type == "EXIT"
            or item.id in ("CONFIRM_EXIT", "ACTION_EXIT", "ACTION_EXIT_MENU")
            or (item.submenu_id or "").upper() == "EXIT_CONFIRM"
            or "EXIT" in self.current_node_id
        ):
            return "EXIT"

        sub_id = (item.submenu_id or "").upper()
        act_id = item.id.upper()
        curr_id = self.current_node_id.upper()

        if sub_id == "FLOW" or "FLOW" in curr_id or any(k in act_id for k in ("IF", "LOOP", "WHILE", "FOR", "TRY", "RETURN", "FLOW", "CTX_TRY", "CTX_LOOP", "CTX_IF", "CTX_WITH")):
            return "FLOW"
        if (
            item.action_type in ("LANG_CHANGE", "LANG_AUTO")
            or item.id.startswith("LANG_")
            or sub_id == "LANG_SELECT"
            or curr_id == "LANG_SELECT"
        ):
            return "LANG"
        if sub_id == "STRUCT" or "STRUCT" in curr_id or any(k in act_id for k in ("FUNC", "CLASS", "DEF", "STRUCT", "DATA", "LIST", "DICT", "CTX_FN", "CTX_CLS")):
            return "STRUCT"
        if sub_id == "OPERATORS" or "OP" in curr_id or any(k in act_id for k in ("OPERATOR", "OP_", "MATH", "BOOL", "COMPARE", "COMMA")):
            return "OPERATORS"
        if sub_id in ("NAV", "MENU_STANDARD") or "NAV" in curr_id or any(k in act_id for k in ("NAV_", "UP", "DOWN", "LEFT", "RIGHT", "PAGE", "WORD", "SWITCH_MENU_STANDARD", "SWITCH_ADAPTIVE_MENU")):
            return "NAV"
        if sub_id in ("SNIPPETS", "AI_PREDICT") or "SNIPPET" in curr_id or "AI" in act_id or "PREDICT" in act_id:
            return "AI"
        if sub_id in ("EDIT", "FORMAT") or "EDIT" in curr_id or "FORMAT" in curr_id or any(k in act_id for k in ("BACKSPACE", "DELETE", "ENTER", "TAB", "INDENT")):
            return "EDIT"

        return "DEFAULT"
