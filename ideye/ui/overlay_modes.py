"""Context mode switching and adaptive AST menus."""

from ideye.ui.overlay_common import *  # noqa: F401,F403


class OverlayModesMixin:
    """Context mode switching and adaptive AST menus."""

    def _on_context_mode_changed(self, mode_id: str, display_name: str, theme_color: str) -> None:
        """Applies a context mode change to the HUD menu tree and theme."""
        was_sniper = self.current_context_mode_id == "sniper"
        self.current_context_mode_id = mode_id
        self.current_context_mode_name = display_name
        self.mode_color = str(theme_color or ACCENT_HEX)
        if mode_id != "sniper":
            if was_sniper:
                self.release_freelook_controls()
            self._sniper_step = 1
            self._sniper_locked_sector = None
            self.hovered_subcell = None
            self._gaming_mode = False
            self._gaming_right_held = False
            self._jaw_locked = False
            self._jaw_lock_pos = None
            self._mouth_active = False
            self._hold_started = False

        if mode_id == "writing":
            mode = self._writing_mode()
            if mode is not None and hasattr(mode, "reset_prefix"):
                mode.reset_prefix()

        if mode_id == "coding":
            self.menu_tree = build_menu_tree(self.current_language)
            if "MENU_STANDARD" not in self.menu_tree and "ROOT" in self.menu_tree:
                std_items = list(self.menu_tree["ROOT"].items)
                if len(std_items) > 8:
                    std_items[8] = create_adaptive_menu_action("9")
                else:
                    std_items.append(create_adaptive_menu_action("9"))
                self.menu_tree["MENU_STANDARD"] = MenuNode(
                    id="MENU_STANDARD",
                    title="MENÚ ESTÁNDAR",
                    breadcrumb_label="ESTÁNDAR",
                    items=std_items,
                    parent_id="ROOT",
                    sticky=False,
                )
        else:
            try:
                self.menu_tree = self.mode_manager.get_menu_tree(self.current_language)
            except Exception:
                self.menu_tree = {"ROOT": self.mode_manager.get_root_menu(self.current_language)}

        self._install_auxiliary_nodes()
        self._apply_macro_overrides()

        # Keep the mode hub open when an automatic editor-state change arrives.
        # When the user explicitly picked a mode, _activate_mode() sets the flag
        # and we enter that mode's ROOT instead.
        if self.current_node_id == "MODE_SELECT" and not self._mode_selection_in_progress:
            self.current_node_id = "MODE_SELECT"
        else:
            self.current_node_id = "ROOT"
        self._dwell_start_time = time.time()
        self._dwell_progress = 0.0
        self._dwell_fired = False
        self._cached_adaptive_node = None
        self._last_ast_eval_time = 0.0
        self.last_action_desc = f"Modo: {display_name}"
        self._mode_banner_text = f"Modo activo: {display_name}"
        try:
            self._mode_banner_start = time.time()
            self._mode_banner_until = self._mode_banner_start + 2.2
        except Exception:
            self._mode_banner_until = 0.0
        self.context_mode_changed.emit(mode_id, display_name, theme_color)
        self.update()

    def _short_mode_label(self, mode_id: Optional[str] = None) -> str:
        """Returns the compact human label for a context mode."""
        mid = mode_id or getattr(self, "current_context_mode_id", "coding")
        return MODE_SHORT_LABELS.get(mid, "MODO")

    def _install_auxiliary_nodes(self) -> None:
        """Adds/refreshes the shared HELP, LANG_SELECT and MODE_SELECT nodes."""
        if "HELP" not in self.menu_tree:
            self.menu_tree["HELP"] = MenuNode(
                id="HELP",
                title="GUÍA DE GESTOS Y ATAJOS",
                breadcrumb_label="AYUDA / GESTOS",
                items=populate_help_items(parent_id="ROOT"),
                parent_id="ROOT",
                sticky=False,
            )

        if "LANG_SELECT" not in self.menu_tree:
            self.menu_tree["LANG_SELECT"] = MenuNode(
                id="LANG_SELECT",
                title="SELECCIONAR LENGUAJE",
                breadcrumb_label="LENGUAJE",
                items=populate_lang_select_items(parent_id="ROOT"),
                parent_id="ROOT",
                sticky=False,
            )

        # EXIT_CONFIRM must exist in every mode, not only in the coding tree.
        if "EXIT_CONFIRM" not in self.menu_tree:
            self.menu_tree["EXIT_CONFIRM"] = MenuNode(
                id="EXIT_CONFIRM",
                title="Confirmar salida",
                breadcrumb_label="SALIR",
                items=populate_exit_confirm_items(parent_id="ROOT"),
                parent_id="ROOT",
                sticky=False,
            )

        # Gaze Command Palette (Spotlight) auxiliary node
        if "COMMAND_PALETTE" not in self.menu_tree:
            self.menu_tree["COMMAND_PALETTE"] = MenuNode(
                id="COMMAND_PALETTE",
                title="PALETA DE COMANDOS",
                breadcrumb_label="SPOTLIGHT",
                items=populate_command_palette_items(parent_id="ROOT"),
                parent_id="ROOT",
                sticky=False,
            )

        # Rebuild the hub every time because the "current mode" marker moves.
        self.menu_tree["MODE_SELECT"] = self._build_mode_select_node()

    def _build_mode_select_node(self) -> MenuNode:
        """Builds the 9-slot mode hub shown at startup and by [V]."""
        items: List[MenuAction] = []
        entry_by_id = {entry[0]: entry for entry in MODE_SELECTOR_ENTRIES}
        order = [
            "coding",
            "writing",
            "terminal",
            "data_math",
            None,  # slot 5: pause
            "navigation",
        ]

        for slot, mode_id in enumerate(order, start=1):
            if mode_id is None:
                items.append(create_pause_action(str(slot)))
                continue
            _, label, hint, icon = entry_by_id[mode_id]
            is_current = mode_id == getattr(self, "current_context_mode_id", "coding")
            items.append(
                MenuAction(
                    id=f"MODE_{mode_id.upper()}",
                    label=f"{slot}: {label}",
                    hint=("Estás en este modo" if is_current else hint),
                    action_type="MODE_SWITCH",
                    icon=icon,
                    mode_id=mode_id,
                )
            )

        # Slot 7: back to the current mode's ROOT (cancel).
        items.append(create_back_action("ROOT", "7"))
        # Slot 8: sniper mouse mode (help remains in the header and [H]).
        _, sniper_label, sniper_hint, sniper_icon = entry_by_id["sniper"]
        sniper_current = self.current_context_mode_id == "sniper"
        items.append(
            MenuAction(
                id="MODE_SNIPER",
                label=f"8: {sniper_label}",
                hint=("Estás en este modo" if sniper_current else sniper_hint),
                action_type="MODE_SWITCH",
                icon=sniper_icon,
                mode_id="sniper",
            )
        )
        # Slot 9: exit.
        items.append(
            MenuAction(
                id="MODE_EXIT",
                label="9: Salir",
                hint="Cerrar IDEye",
                action_type="EXIT",
                icon="exit",
            )
        )

        return MenuNode(
            id="MODE_SELECT",
            title="ELEGIR MODO",
            breadcrumb_label="ELEGIR MODO",
            items=items,
            parent_id="ROOT",
            sticky=False,
        )

    def open_mode_selector(self) -> None:
        """Opens the mode hub so the user can pick a mode explicitly."""
        if "MODE_SELECT" not in self.menu_tree:
            self._install_auxiliary_nodes()
        else:
            # Refresh the current-mode marker.
            self.menu_tree["MODE_SELECT"] = self._build_mode_select_node()
        self.navigate_to("MODE_SELECT")
        self.last_action_desc = "Elegir modo"
        self._mode_banner_text = "Elige un modo"
        try:
            self._mode_banner_start = time.time()
            self._mode_banner_until = self._mode_banner_start + 2.2
        except Exception:
            self._mode_banner_until = 0.0
        self.update()

    def _activate_mode(self, mode_id: Optional[str]) -> None:
        """Enters a mode selected from the hub and lands on its ROOT menu."""
        if not mode_id or self.mode_manager is None:
            return
        previous_mode = self.current_context_mode_id
        if previous_mode == "sniper" and mode_id != "sniper":
            self.release_freelook_controls()
        if mode_id == "sniper" and previous_mode != "sniper":
            self._sniper_previous_mode = previous_mode
        self._mode_selection_in_progress = True
        try:
            self.mode_manager.set_mode(mode_id, emit=True)
        finally:
            self._mode_selection_in_progress = False
        if "ROOT" in self.menu_tree:
            self.navigate_to("ROOT")
        self._sniper_step = 1
        self._sniper_locked_sector = None
        self.hovered_subcell = None
        self.last_action_desc = f"Modo: {getattr(self, 'current_context_mode_name', '')}"
        self._play_sound("mode")
        self.update()

    def cycle_context_mode(self) -> None:
        """[V] exits FreeLook, otherwise opens the mode hub."""
        if self.current_context_mode_id == "sniper":
            self._exit_sniper_mode()
        else:
            self.open_mode_selector()

    def is_mode_shortcut_targeted(self) -> bool:
        """True when gaze is on the top command bar (plain-key hotkey gate)."""
        gaze = getattr(self, "current_gaze", None)
        if not gaze:
            return False
        try:
            gx, gy = gaze
            w = max(1.0, float(self.width()))
            h = max(1.0, float(self.height()))
            px, py = gx * w, gy * h
            header = getattr(self, "header_rect", None)
            if header is not None and header.isValid() and header.adjusted(
                -18.0, -12.0, 18.0, 14.0
            ).contains(px, py):
                return True
            rect = getattr(self, "header_mode_rect", None)
            if rect is not None and rect.isValid() and rect.adjusted(
                -24.0, -18.0, 24.0, 18.0
            ).contains(px, py):
                return True
            return False
        except Exception:
            return False

    def toggle_adaptive_ast(self) -> None:
        """Toggles between dynamic adaptive AST menus and standard root menu (shortcut [A])."""
        self.adaptive_ast_enabled = not getattr(self, "adaptive_ast_enabled", True)
        self._cached_adaptive_node = None
        self._last_ast_eval_time = 0.0
        self.last_action_desc = f"Menús inteligentes: {'Activados' if self.adaptive_ast_enabled else 'Desactivados'}"
        self.adaptive_ast_toggled.emit(self.adaptive_ast_enabled)
        self.update()

    def toggle_auto_switch(self, enabled=None) -> bool:
        if self.mode_manager is not None:
            value = self.mode_manager.toggle_auto_switch(enabled)
            self.auto_switch_changed.emit(value)
            return value
        return False

    @pyqtSlot(bool)
    def set_adaptive_ast_enabled(self, enabled: bool) -> None:
        """Explicitly sets adaptive AST menus enabled status."""
        if self.adaptive_ast_enabled != enabled:
            self.adaptive_ast_enabled = enabled
            self._cached_adaptive_node = None
            self._last_ast_eval_time = 0.0
            self.last_action_desc = f"Menús inteligentes: {'Activados' if self.adaptive_ast_enabled else 'Desactivados'}"
            self.adaptive_ast_toggled.emit(self.adaptive_ast_enabled)
            self.update()
