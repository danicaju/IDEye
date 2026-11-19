"""Sound feedback, mouse controller and Sniper precision grid."""

from ideye.ui.overlay_common import *  # noqa: F401,F403


class OverlaySniperMixin:
    """Sound feedback, mouse controller and Sniper precision grid."""

    def set_sound_feedback(self, manager: Optional[SoundFeedbackManager]) -> None:
        """Injects the procedural sound manager (optional in tests)."""
        self.sound_feedback = manager

    def _play_sound(self, sound_name: str) -> None:
        """Plays a UI sound without ever blocking the Qt thread."""
        try:
            if self.sound_feedback is not None:
                self.sound_feedback.play(sound_name)
        except Exception:
            pass

    def toggle_sound_feedback(self) -> bool:
        """Mutes/unmutes procedural audio and reports the new state."""
        if self.sound_feedback is None:
            return True
        enabled = bool(self.sound_feedback.toggle_mute())
        self.last_action_desc = f"Sonido: {'ON' if enabled else 'OFF'}"
        self.sound_enabled_changed.emit(enabled)
        self.update()
        return enabled

    # ------------------------------------------------------------------ #
    # Phase 7: sniper targeting
    # ------------------------------------------------------------------ #
    def set_mouse_controller(self, controller: Optional[OSMouseController]) -> None:
        self.mouse_controller = controller

    def _get_screen_size(self) -> Tuple[int, int]:
        screen = QApplication.primaryScreen()
        if screen is None:
            return max(1, self.width()), max(1, self.height())
        rect = screen.geometry()
        # Qt reports logical pixels; pynput injects physical screen pixels.
        dpr = float(screen.devicePixelRatio() or 1.0)
        return max(1, int(rect.width() * dpr)), max(1, int(rect.height() * dpr))

    def _calculate_sector_rect(
        self,
        sector_index: int,
        screen_w: Optional[int] = None,
        screen_h: Optional[int] = None,
    ) -> Tuple[int, int, int, int]:
        """Returns the screen-pixel rectangle of a 3x3 macro sector."""
        if screen_w is None or screen_h is None:
            screen_w, screen_h = self._get_screen_size()
        col = sector_index % 3
        row = sector_index // 3
        sector_w = screen_w / 3.0
        sector_h = screen_h / 3.0
        return (
            int(col * sector_w),
            int(row * sector_h),
            int(sector_w),
            int(sector_h),
        )

    def _calculate_subcell_coords(
        self,
        subcell_index: int,
        sector_rect: Tuple[int, int, int, int],
    ) -> Tuple[int, int]:
        """Returns the absolute screen-pixel center of a precision sub-cell."""
        x, y, w, h = sector_rect
        col = subcell_index % 3
        row = subcell_index // 3
        cell_w = w / 3.0
        cell_h = h / 3.0
        return (
            int(x + (col + 0.5) * cell_w),
            int(y + (row + 0.5) * cell_h),
        )

    def _subcell_rects_in_overlay(self) -> List[QRectF]:
        """Maps the locked sector's 3x3 sub-grid into overlay coordinates."""
        if self._sniper_locked_sector is None:
            return []
        screen_w, screen_h = self._get_screen_size()
        sx, sy, sw, sh = self._calculate_sector_rect(
            self._sniper_locked_sector, screen_w, screen_h
        )
        scale_x = self.width() / float(screen_w)
        scale_y = self.height() / float(screen_h)
        left = sx * scale_x
        top = sy * scale_y
        width = sw * scale_x
        height = sh * scale_y
        cell_w = width / 3.0
        cell_h = height / 3.0
        rects: List[QRectF] = []
        for row in range(3):
            for col in range(3):
                rects.append(
                    QRectF(
                        left + col * cell_w,
                        top + row * cell_h,
                        cell_w,
                        cell_h,
                    )
                )
        return rects

    def _subcell_from_gaze(self, gx: float, gy: float) -> Optional[int]:
        if self._sniper_locked_sector is None:
            return None
        screen_w, screen_h = self._get_screen_size()
        sx, sy, sw, sh = self._calculate_sector_rect(
            self._sniper_locked_sector, screen_w, screen_h
        )
        px = gx * screen_w
        py = gy * screen_h
        if not (sx <= px < sx + sw and sy <= py < sy + sh):
            return None
        col = min(2, max(0, int((px - sx) / (sw / 3.0))))
        row = min(2, max(0, int((py - sy) / (sh / 3.0))))
        return row * 3 + col

    def _sniper_mode(self):
        try:
            return self.mode_manager.get_mode("sniper") if self.mode_manager else None
        except Exception:
            return None

    def _cycle_sniper_action(self) -> str:
        mode = self._sniper_mode()
        if mode is None or not hasattr(mode, "cycle_action"):
            return "LEFT_CLICK"
        action = mode.cycle_action()
        self.last_action_desc = f"Ratón: {getattr(mode, 'action_label', action)}"
        self._play_sound("mode")
        self.update()
        return action

    def _execute_sniper_action(self, x: int, y: int) -> None:
        mode = self._sniper_mode()
        action = getattr(mode, "get_action", lambda: "LEFT_CLICK")() if mode else "LEFT_CLICK"
        controller = self.mouse_controller
        if controller is None:
            controller = OSMouseController()
            self.mouse_controller = controller
        if action == "RIGHT_CLICK":
            controller.right_click(x, y)
        elif action == "DOUBLE_CLICK":
            controller.double_click(x, y)
        elif action == "SCROLL_UP":
            controller.scroll_at(x, y, 3)
        elif action == "SCROLL_DOWN":
            controller.scroll_at(x, y, -3)
        else:
            controller.left_click(x, y)

    def toggle_sniper_mode(self) -> None:
        """Enters sniper mode from any mode, or returns to the previous one."""
        if self.current_context_mode_id == "sniper":
            self._exit_sniper_mode()
            return
        if self.mode_manager is None:
            return
        self._sniper_previous_mode = self.current_context_mode_id
        self._mode_selection_in_progress = True
        try:
            self.mode_manager.set_mode("sniper", emit=True)
        finally:
            self._mode_selection_in_progress = False
        self._sniper_step = 1
        self._sniper_locked_sector = None
        self.hovered_subcell = None
        self._gaming_mode = False
        self._gaming_right_held = False
        self._jaw_locked = False
        self._jaw_lock_pos = None
        self._mouth_active = False
        self._hold_started = False
        self._mar_rest_window.clear()
        self._mar_rest_baseline = max(
            0.15,
            min(
                0.60,
                max(
                    float(getattr(config, "MAR_REST_THRESHOLD", 0.20)),
                    self.mar_threshold - 0.18,
                ),
            ),
        )
        sw, sh = self._get_screen_size()
        self._freelook_last_pos = (sw // 2, sh // 2)
        self.navigate_to("ROOT")
        self.last_action_desc = "FreeLook"
        self._play_sound("mode")
        self.update()

    def _exit_sniper_mode(self) -> None:
        previous = self._sniper_previous_mode or "coding"
        self._sniper_previous_mode = None
        if self.mode_manager is not None:
            self._mode_selection_in_progress = True
            try:
                self.mode_manager.set_mode(previous, emit=True)
            finally:
                self._mode_selection_in_progress = False
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
        self.navigate_to("ROOT")
        self.last_action_desc = "Modo anterior"
        self._play_sound("back")
        self.update()

    def _paint_sniper_overlay(self, painter: QPainter) -> None:
        """Draws the step-2 precision sub-grid over the locked sector."""
        if self.current_context_mode_id != "sniper" or self._sniper_step != 2:
            return
        rects = self._subcell_rects_in_overlay()
        if not rects:
            return
        painter.save()
        mode = self._sniper_mode()
        action_label = getattr(mode, "action_label", "Clic Izq") if mode else "Clic Izq"
        for idx, rect in enumerate(rects):
            selected = idx == self.hovered_subcell
            painter.setBrush(QColor(244, 63, 94, 45) if selected else QColor(10, 15, 29, 45))
            painter.setPen(QPen(QColor(244, 63, 94, 235 if selected else 150), 2.0 if selected else 1.0))
            painter.drawRoundedRect(rect.adjusted(2, 2, -2, -2), 6.0, 6.0)
            painter.setPen(QColor(248, 250, 252) if selected else QColor(203, 213, 225))
            painter.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(idx + 1))
        # Compact instruction banner.
        banner = QRectF(
            self.width() * 0.5 - 230.0,
            self.margin,
            460.0,
            32.0,
        )
        painter.setBrush(QColor(10, 15, 29, 235))
        painter.setPen(QPen(QColor(244, 63, 94, 220), 1.2))
        painter.drawRoundedRect(banner, 9.0, 9.0)
        painter.setPen(QColor(248, 250, 252))
        painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        painter.drawText(
            banner,
            Qt.AlignmentFlag.AlignCenter,
            f"PASO 2 · {action_label} · elige sub-zona y abre la boca",
        )
        painter.restore()
