"""Mouse, keyboard and language selection."""

from ideye.ui.overlay_common import *  # noqa: F401,F403


class OverlayInputMixin:
    """Mouse, keyboard and language selection."""

    def mousePressEvent(self, event) -> None:
        """Handles physical mouse clicks for testing, headless runners, and assistive caregivers."""
        pos = event.position() if hasattr(event, "position") else event.pos()
        px, py = float(pos.x()), float(pos.y())

        # Check tutorial modal dismiss and step confirmation if active
        if getattr(self, "show_tutorial_modal", False):
            if (
                hasattr(self, "tutorial_modal_close_rect")
                and self.tutorial_modal_close_rect.isValid()
                and self.tutorial_modal_close_rect.adjusted(-8.0, -8.0, 8.0, 8.0).contains(px, py)
            ):
                self.close_mini_tutorial()
                event.accept()
                return

            if getattr(self, "tutorial_step", 1) == 2:
                self.tutorial_step = 3
                self.tutorial_step_progress = 0.0
                self._tutorial_rest_start = time.time()
                self._play_sound("confirm")
                self.update()
                event.accept()
                return
            elif getattr(self, "tutorial_step", 1) == 4:
                self.close_mini_tutorial()
                event.accept()
                return

            event.accept()
            return

        # Check the help modal actions if open.
        if self.show_help_modal:
            open_guide = (
                self.help_modal_guide_rect.isValid()
                and self.help_modal_guide_rect.adjusted(-12.0, -12.0, 12.0, 12.0).contains(px, py)
            )
            start_tutorial = (
                hasattr(self, "help_modal_tutorial_rect")
                and self.help_modal_tutorial_rect.isValid()
                and self.help_modal_tutorial_rect.adjusted(-12.0, -12.0, 12.0, 12.0).contains(px, py)
            )
            self.show_help_modal = False
            self.hovered_help_modal_guide = False
            self.hovered_help_modal_tutorial = False
            self.hovered_help_modal_close = False
            if open_guide:
                self.last_action_desc = "Abriendo Manual Interactivo"
                self.interactive_guide_requested.emit()
            elif start_tutorial:
                self.start_mini_tutorial()
            self.update()
            event.accept()
            return

        # Check header exit button (+15px buffer)
        if not self.reading_mode and self.header_exit_rect.isValid() and self.header_exit_rect.adjusted(-15.0, -15.0, 15.0, 15.0).contains(px, py):
            self.hovered_header_exit = True
            self.on_gesture_triggered("MOUTH_CLICK")
            event.accept()
            return

        # Check header help button (+15px buffer)
        if not self.reading_mode and hasattr(self, "header_help_rect") and self.header_help_rect.isValid() and self.header_help_rect.adjusted(-15.0, -15.0, 15.0, 15.0).contains(px, py):
            self.hovered_header_help = True
            self.on_gesture_triggered("MOUTH_CLICK")
            event.accept()
            return

        # Check header mode button (+15px buffer)
        if not self.reading_mode and hasattr(self, "header_mode_rect") and self.header_mode_rect.isValid() and self.header_mode_rect.adjusted(-15.0, -15.0, 15.0, 15.0).contains(px, py):
            self.hovered_header_mode = True
            self.on_gesture_triggered("MOUTH_CLICK")
            event.accept()
            return

        # Check header language button (+15px buffer)
        if not self.reading_mode and hasattr(self, "header_lang_rect") and self.header_lang_rect.isValid() and self.header_lang_rect.adjusted(-15.0, -15.0, 15.0, 15.0).contains(px, py):
            self.hovered_header_lang = True
            self.on_gesture_triggered("MOUTH_CLICK")
            event.accept()
            return

        w = float(self.width()) if self.width() > 0 else 1920.0
        h = float(self.height()) if self.height() > 0 else 1080.0
        self.on_gaze_updated(px / w, py / h)
        self.on_gesture_triggered("MOUTH_CLICK")
        event.accept()

    def keyPressEvent(self, event) -> None:
        """Keyboard event handler for shortcut [T] (tracking mode), [A] (adaptive AST), [L] (language), and [H]/[F1] (help)."""
        if event.key() in (Qt.Key.Key_H, Qt.Key.Key_F1):
            self.toggle_help_modal()
            event.accept()
        elif event.key() == Qt.Key.Key_Escape and self.show_help_modal:
            self.show_help_modal = False
            self.update()
            event.accept()
        elif event.key() == Qt.Key.Key_T:
            self.tracking_mode_cycle_requested.emit()
            event.accept()
        elif event.key() == Qt.Key.Key_A:
            self.toggle_adaptive_ast()
            event.accept()
        elif event.key() == Qt.Key.Key_B:
            self.open_clipboard_history()
            event.accept()
        elif event.key() == Qt.Key.Key_L:
            self.cycle_language()
            event.accept()
        elif event.key() == Qt.Key.Key_V:
            self.cycle_context_mode()
            event.accept()
        elif event.key() == Qt.Key.Key_K:
            self.toggle_auto_switch()
            event.accept()
        elif event.key() == Qt.Key.Key_S:
            self.toggle_sound_feedback()
            event.accept()
        elif event.key() == Qt.Key.Key_Escape and getattr(self, "show_tutorial_modal", False):
            self.show_tutorial_modal = False
            self.update()
            event.accept()
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space) and getattr(self, "show_tutorial_modal", False):
            if getattr(self, "tutorial_step", 1) == 2:
                self.tutorial_step = 3
                self.tutorial_step_progress = 0.0
                self._tutorial_rest_start = time.time()
                self._play_sound("confirm")
                self.update()
                event.accept()
            elif getattr(self, "tutorial_step", 1) == 4:
                self.close_mini_tutorial()
                event.accept()
        elif event.key() == Qt.Key.Key_F2:
            self.show_tutorial_modal = not getattr(self, "show_tutorial_modal", False)
            if self.show_tutorial_modal:
                self.start_mini_tutorial()
            self.update()
            event.accept()
        elif event.key() == Qt.Key.Key_D:
            self.toggle_hud_layout()
            event.accept()
        elif event.key() == Qt.Key.Key_P:
            self.open_command_palette()
            event.accept()
        elif event.key() == Qt.Key.Key_Z:
            self.trigger_undo()
            event.accept()
        elif event.key() == Qt.Key.Key_C:
            self.snap_to_caret()
            event.accept()
        elif event.key() == Qt.Key.Key_O:
            self.toggle_theme()
            event.accept()
        elif event.key() == Qt.Key.Key_F:
            self.toggle_sniper_mode()
            event.accept()
        elif event.key() == Qt.Key.Key_G:
            if self.current_context_mode_id == "sniper":
                self.toggle_gaming_mode()
            event.accept()
        else:
            super().keyPressEvent(event)

    def cycle_language(self) -> None:
        """Cycles through supported languages in order: Python -> TypeScript -> Rust -> C++ -> Go."""
        langs = ["PYTHON", "TYPESCRIPT", "RUST", "CPP", "GO"]
        try:
            curr_idx = langs.index(self.current_language)
            next_idx = (curr_idx + 1) % len(langs)
        except ValueError:
            next_idx = 0
        self.set_language(langs[next_idx])

    @pyqtSlot(str)
    def set_language(self, lang: str) -> None:
        """Sets the active programming language, updates menus and breadcrumbs, and notifies listeners."""
        norm_lang = normalize_language(lang)
        if norm_lang == self.current_language and self.menu_tree is not None:
            return

        self.current_language = norm_lang
        if getattr(self, "current_context_mode_id", "coding") == "coding":
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
            mm = getattr(self, "mode_manager", None)
            if mm is not None:
                try:
                    self.menu_tree = mm.get_menu_tree(self.current_language)
                except Exception:
                    self.menu_tree = build_menu_tree(self.current_language)
            else:
                self.menu_tree = build_menu_tree(self.current_language)
        self._install_auxiliary_nodes()
        self._apply_macro_overrides()
        self._cached_adaptive_node = None
        self._last_ast_eval_time = 0.0
        badge = get_language_badge(self.current_language)
        self.last_action_desc = f"Lenguaje: {get_language_display_name(self.current_language)} [{badge}]"
        self.language_changed.emit(self.current_language)
        self.update()
