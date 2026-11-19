"""HUD layout, themes, adaptive dwell and onboarding tutorial."""

from ideye.ui.overlay_common import *  # noqa: F401,F403


class OverlayThemeMixin:
    """HUD layout, themes, adaptive dwell and onboarding tutorial."""

    def set_hud_layout(self, layout: str) -> None:
        """Sets the HUD layout mode ('FULL_GRID' 100% or 'RIGHT_DOCK' 30% column)."""
        normalized = layout.upper().strip()
        if normalized in ("RIGHT_DOCK", "DOCK", "SIDE"):
            self.hud_layout_mode = "RIGHT_DOCK"
        else:
            self.hud_layout_mode = "FULL_GRID"
        self._update_header_exit_rect()
        self.layout_changed.emit(self.hud_layout_mode)
        self.update()

    def toggle_hud_layout(self) -> str:
        """Toggles between FULL_GRID (100%) and RIGHT_DOCK (30% column)."""
        if self.hud_layout_mode == "RIGHT_DOCK":
            self.set_hud_layout("FULL_GRID")
        else:
            self.set_hud_layout("RIGHT_DOCK")
        self._play_sound("nav")
        return self.hud_layout_mode

    def set_theme(self, theme_name: str) -> None:
        """Applies a visual theme (CYBER_GLASS, OLED_BLACK, SOLARIZED_DARK)."""
        normalized = theme_name.upper().strip()
        if "OLED" in normalized:
            self.current_theme = "OLED_BLACK"
            self._brush_header_bg = QBrush(QColor(0, 0, 0, 250))
            self._brush_card_inactive = QBrush(QColor(0, 0, 0, 240))
            self._brush_card_active = QBrush(QColor(15, 15, 15, 245))
            self._brush_band_inactive = QBrush(QColor(12, 12, 12, 255))
            self._brush_band_active = QBrush(QColor(20, 20, 20, 255))
            self._pen_card_inactive = QPen(QColor(255, 255, 255, 48), 1.0)
            self._color_card_text_active = QColor(255, 255, 255, 255)
            self._color_card_text_inactive = QColor(240, 240, 240, 255)
            self._color_card_subtitle = QColor(200, 200, 200, 240)
            self._color_card_subtitle_inactive = QColor(180, 180, 180, 240)
            self._set_theme_color("#00FF66")
        elif "SOLARIZED" in normalized:
            self.current_theme = "SOLARIZED_DARK"
            self._brush_header_bg = QBrush(QColor(0, 43, 54, 245))
            self._brush_card_inactive = QBrush(QColor(0, 43, 54, 210))
            self._brush_card_active = QBrush(QColor(7, 54, 66, 235))
            self._brush_band_inactive = QBrush(QColor(7, 54, 66, 245))
            self._brush_band_active = QBrush(QColor(14, 65, 78, 250))
            self._pen_card_inactive = QPen(QColor(88, 110, 117, 56), 1.0)
            self._color_card_text_active = QColor(253, 246, 227, 255)
            self._color_card_text_inactive = QColor(147, 161, 161, 255)
            self._color_card_subtitle = QColor(131, 148, 150, 240)
            self._color_card_subtitle_inactive = QColor(101, 123, 131, 240)
            self._set_theme_color("#268BD2")
        else:
            self.current_theme = "CYBER_GLASS"
            self._brush_header_bg = QBrush(QColor(10, 15, 29, 225))
            self._brush_card_inactive = QBrush(QColor(10, 15, 29, 120))
            self._brush_card_active = QBrush(QColor(15, 23, 42, 235))
            self._brush_band_inactive = QBrush(QColor(10, 15, 29, 230))
            self._brush_band_active = QBrush(QColor(15, 23, 42, 240))
            self._pen_card_inactive = QPen(QColor(148, 163, 184, INACTIVE_OUTLINE_ALPHA), 1.0)
            self._color_card_text_active = QColor(248, 250, 252, 255)
            self._color_card_text_inactive = QColor(226, 232, 240, 255)
            self._color_card_subtitle = QColor(148, 163, 184, 220)
            self._color_card_subtitle_inactive = QColor(148, 163, 184, 255)
            self._set_theme_color(ACCENT_HEX)
        self.theme_changed.emit(self.current_theme)
        self.update()

    def toggle_theme(self) -> str:
        """Cycles between CYBER_GLASS -> OLED_BLACK -> SOLARIZED_DARK."""
        cycle = ["CYBER_GLASS", "OLED_BLACK", "SOLARIZED_DARK"]
        curr = self.current_theme if self.current_theme in cycle else "CYBER_GLASS"
        nxt = cycle[(cycle.index(curr) + 1) % len(cycle)]
        self.set_theme(nxt)
        self._play_sound("nav")
        return self.current_theme

    def open_command_palette(self) -> None:
        """Navigates to the Gaze Command Palette (Spotlight)."""
        self.navigate_to("COMMAND_PALETTE")
        self._play_sound("nav")

    def get_adaptive_dwell_time(self, item: Any, block_idx: int) -> float:
        """Computes the required dwell time in seconds based on action ergonomics."""
        if block_idx == 4 or (item is not None and getattr(item, "action_type", "") == "PAUSE"):
            return float("inf")  # Safe Rest Zone: Midas Touch immune
        if item is None:
            return float(getattr(config, "DWELL_TIME_STANDARD_SEC", 0.45))
        atype = getattr(item, "action_type", "")
        item_id = str(getattr(item, "id", ""))
        if atype == "EXIT" or item_id in ("CONFIRM_EXIT", "ACTION_EXIT") or "DELETE" in item_id:
            return float(getattr(config, "DWELL_TIME_DANGER_SEC", 0.85))
        if atype in ("BACK", "KEY", "SUBMENU") or item_id.startswith(("NAV_", "CMD_")):
            return float(getattr(config, "DWELL_TIME_NAV_SEC", 0.30))
        return float(getattr(config, "DWELL_TIME_STANDARD_SEC", 0.45))

    def _update_adaptive_dwell(self, block_idx: Optional[int]) -> None:
        """Advances the adaptive dwell-time accumulator and triggers activation when complete."""
        if not getattr(self, "adaptive_dwell_enabled", True) or block_idx is None:
            self._dwell_block = None
            self._dwell_progress = 0.0
            self._dwell_fired = False
            return

        now = time.time()
        if self._dwell_block != block_idx:
            self._dwell_block = block_idx
            self._dwell_start_time = now
            self._dwell_progress = 0.0
            self._dwell_fired = False
            return

        if self._dwell_fired:
            return

        node = self.current_node
        item = node.items[block_idx] if (node and block_idx < len(node.items)) else None
        target_dwell = self.get_adaptive_dwell_time(item, block_idx)

        # When mouth gesture is uncalibrated, require real deliberate dwell (minimum 0.70s)
        # to prevent accidental entry into boxes simply by looking at them (Anti-Midas protection).
        if not getattr(self, "mar_calibrated", True) and not math.isinf(target_dwell):
            target_dwell = max(target_dwell, 0.70)

        if math.isinf(target_dwell):
            self._dwell_progress = 0.0
            return

        elapsed = now - self._dwell_start_time
        progress = max(0.0, min(1.0, elapsed / max(0.05, target_dwell)))
        self._dwell_progress = progress

        if progress >= 1.0:
            self._dwell_fired = True
            # Dwell auto-click is an opt-in accessibility feature (disabled by default).
            # By default (Zero-Dwell), looking at a box only focuses/highlights it.
            # Intentional confirmation via mouth click (MAR) or physical click is required.
            if getattr(self, "dwell_click_enabled", False) and not getattr(self, "show_tutorial_modal", False):
                self.trigger_click_flash(block_idx)
                if item is not None:
                    self._play_sound("confirm")
                    self.execute_action(item, target_block=block_idx)

    def set_dwell_click_enabled(self, enabled: bool) -> None:
        """Enables or disables auto-triggering actions on gaze dwell (accessibility fallback)."""
        self.dwell_click_enabled = bool(enabled)

    def start_mini_tutorial(self) -> None:
        """Starts the interactive 3-step mini-tutorial for gaze onboarding."""
        self.show_tutorial_modal = True
        self.tutorial_step = 1
        self.tutorial_step_progress = 0.0
        self._tutorial_rest_start = 0.0
        self._play_sound("nav")
        self.update()

    def start_tutorial(self) -> None:
        """Alias for start_mini_tutorial for external callers and test runners."""
        self.start_mini_tutorial()

    def close_mini_tutorial(self) -> None:
        """Closes the interactive tutorial modal."""
        self.show_tutorial_modal = False
        self.update()

    def close_tutorial(self) -> None:
        """Alias for close_mini_tutorial."""
        self.close_mini_tutorial()

    @property
    def _tutorial_active(self) -> bool:
        """True if the onboarding tutorial modal is currently displayed."""
        return bool(getattr(self, "show_tutorial_modal", False))

    @_tutorial_active.setter
    def _tutorial_active(self, value: bool) -> None:
        self.show_tutorial_modal = bool(value)

    def _update_mini_tutorial_gaze(self, gx: float, gy: float) -> None:
        """Tracks gaze and advances the 3-step interactive onboarding tutorial."""
        if not getattr(self, "show_tutorial_modal", False):
            return

        now = time.time()
        if self.tutorial_step == 1:
            if self.hovered_block is not None and self.hovered_block != 4:
                self.tutorial_step_progress = min(1.0, getattr(self, "_dwell_progress", 0.0))
                if self.tutorial_step_progress >= 0.95 or getattr(self, "_dwell_fired", False):
                    self.tutorial_step = 2
                    self.tutorial_step_progress = 0.0
                    self._play_sound("confirm")
            else:
                self.tutorial_step_progress = 0.0
        elif self.tutorial_step == 3:
            if self.hovered_block == 4 or self.hovered_block is None:
                if self._tutorial_rest_start == 0.0:
                    self._tutorial_rest_start = now
                elapsed = now - self._tutorial_rest_start
                self.tutorial_step_progress = min(1.0, elapsed / 1.0)
                if self.tutorial_step_progress >= 1.0:
                    self.tutorial_step = 4
                    self.tutorial_step_progress = 1.0
                    self._play_sound("confirm")
            else:
                self._tutorial_rest_start = 0.0
                self.tutorial_step_progress = 0.0

    def _paint_tutorial_modal(self, painter: QPainter, w: float, h: float) -> None:
        """Renders the high-contrast 3-step interactive onboarding tutorial modal."""
        painter.save()
        try:
            modal_w = min(620.0, w - 40.0)
            modal_h = 240.0
            modal_x = (w - modal_w) * 0.5
            modal_y = (h - modal_h) * 0.5
            modal_rect = QRectF(modal_x, modal_y, modal_w, modal_h)

            painter.setBrush(QBrush(QColor(10, 15, 29, 245)))
            theme_col = QColor(self.theme_color or "#3b82f6")
            painter.setPen(QPen(theme_col, 1.5))
            painter.drawRoundedRect(modal_rect, 12.0, 12.0)

            # Close button in top-right of tutorial modal
            self.tutorial_modal_close_rect = QRectF(modal_x + modal_w - 38.0, modal_y + 14.0, 24.0, 24.0)
            painter.setBrush(QBrush(QColor(255, 255, 255, 20)))
            painter.setPen(QPen(QColor(255, 255, 255, 120), 1.0))
            painter.drawRoundedRect(self.tutorial_modal_close_rect, 4.0, 4.0)
            painter.setPen(QColor(220, 220, 220))
            painter.setFont(self._font_header_bold_btn)
            painter.drawText(self.tutorial_modal_close_rect, Qt.AlignmentFlag.AlignCenter, "X")

            step = int(getattr(self, "tutorial_step", 1))
            badge_text = f"PASO {step} DE 3" if step <= 3 else "TUTORIAL COMPLETADO"
            badge_rect = QRectF(modal_x + 24.0, modal_y + 20.0, 180.0, 26.0)
            painter.setBrush(QBrush(QColor(theme_col.red(), theme_col.green(), theme_col.blue(), 45)))
            painter.setPen(QPen(theme_col, 1.2))
            painter.drawRoundedRect(badge_rect, 6.0, 6.0)
            painter.setPen(theme_col)
            painter.setFont(self._font_header_bold_btn)
            painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, badge_text)

            titles = {
                1: "1. Fijacion de la mirada (Adaptive Dwell)",
                2: "2. Confirmación con la boca (MAR)",
                3: "3. Zona de Reposo (Safe Rest Anti-Midas)",
                4: "Listo para programar con IDEye!",
            }
            subtitles = {
                1: "Posiciona tu mirada en cualquier celda para cargar el anillo de fijacion progresivo.",
                2: "Abre levemente la boca o pulsa clic/Enter para confirmar una seleccion activa.",
                3: "Coloca tu mirada en la celda central 5 o en el editor para reposar sin disparos accidentales.",
                4: "Has completado los fundamentos de control ocular. Pulsa F2 o parpadea para cerrar.",
            }

            title = titles.get(step, "")
            subtitle = subtitles.get(step, "")

            painter.setPen(QColor(255, 255, 255))
            painter.setFont(self._font_modal_title)
            painter.drawText(
                QRectF(modal_x + 24.0, modal_y + 58.0, modal_w - 48.0, 32.0),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                title,
            )

            painter.setPen(QColor(203, 213, 225))
            painter.setFont(self._font_modal_item_title)
            painter.drawText(
                QRectF(modal_x + 24.0, modal_y + 96.0, modal_w - 48.0, 52.0),
                Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap,
                subtitle,
            )

            bar_x = modal_x + 24.0
            bar_y = modal_y + 165.0
            bar_w = modal_w - 48.0
            bar_h = 10.0
            painter.setBrush(QBrush(QColor(30, 41, 59, 200)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(QRectF(bar_x, bar_y, bar_w, bar_h), 5.0, 5.0)

            prog = max(0.0, min(1.0, float(getattr(self, "tutorial_step_progress", 0.0))))
            if prog > 0.01:
                painter.setBrush(QBrush(theme_col))
                painter.drawRoundedRect(QRectF(bar_x, bar_y, bar_w * prog, bar_h), 5.0, 5.0)

            painter.setPen(QColor(148, 163, 184))
            painter.setFont(self._font_modal_item_desc)
            painter.drawText(
                QRectF(modal_x + 24.0, modal_y + 190.0, modal_w - 48.0, 24.0),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                "Pulsa F2 o Escape para salir del tutorial",
            )
        except Exception as exc:
            logger.warning(f"Error rendering tutorial modal: {exc}")
        finally:
            painter.restore()
