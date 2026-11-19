"""Gaze handling, dwell, cell gravity and header flashes."""

from ideye.ui.overlay_common import *  # noqa: F401,F403


class OverlayGazeMixin:
    """Gaze handling, dwell, cell gravity and header flashes."""

    @pyqtSlot(float, float)
    def on_gaze_updated(self, gx: float, gy: float) -> None:
        """
        Receives normalized gaze coordinates from CameraTracker.
        Updates hovered block and gaze cursor position across the 3x3 grid,
        with sub-pixel geometry alignment matching visual category cards.
        """
        try:
            gx = float(gx)
            gy = float(gy)
        except (TypeError, ValueError, OverflowError):
            return
        if not (math.isfinite(gx) and math.isfinite(gy)):
            return
        self.current_gaze = (gx, gy)
        self._apply_gaze_scroll(gy)

        # FreeLook: header remains interactive; the rest of the screen moves
        # the real OS cursor directly and hides the 3x3 grid.
        if (
            self.current_context_mode_id == "sniper"
            and self.current_node_id != "MODE_SELECT"
            and not self.show_help_modal
            and not self.reading_mode
        ):
            screen_w, screen_h = self._get_screen_size()
            mx, my = self._freelook_screen_coords(gx, gy, screen_w, screen_h)
            px = mx * (max(1.0, float(self.width())) / max(1.0, float(screen_w)))
            py = my * (max(1.0, float(self.height())) / max(1.0, float(screen_h)))
            header_targets = (
                ("hovered_header_exit", self.header_exit_rect),
                ("hovered_header_help", self.header_help_rect),
                ("hovered_header_mode", self.header_mode_rect),
                ("hovered_header_lang", self.header_lang_rect),
                ("hovered_header_screen", self.header_screen_rect),
                ("hovered_sniper_action", self._sniper_action_pill_rect),
                ("hovered_gaming_toggle", self._gaming_toggle_rect),
            )
            active_target = next(
                (attr for attr, _ in header_targets if getattr(self, attr, False)),
                None,
            )
            for attr, rect in header_targets:
                if not rect.isValid():
                    continue
                pad = 24.0 if attr == active_target else 15.0
                if rect.adjusted(-pad, -pad, pad, pad).contains(px, py):
                    for other, _ in header_targets:
                        setattr(self, other, other == attr)
                    self.hovered_block = None
                    self._wake_ghost_peek()
                    self.update()
                    return
            for attr, _ in header_targets:
                setattr(self, attr, False)
            self._handle_freelook_gaze(gx, gy)
            return

        # Determine 3x3 block index with card geometry alignment
        w = float(self.width()) if self.width() > 0 else 1920.0
        h = float(self.height()) if self.height() > 0 else 1080.0
        margin = self.margin
        header_h = self.breadcrumb_height
        avail_y = margin + header_h + margin
        avail_h = max(1.0, h - avail_y - margin)
        cell_h = avail_h / 3.0

        py = gy * h
        px = gx * w

        # If cheat sheet modal is open, hit test its buttons (Guide, Tutorial, Close)
        if self.show_help_modal:
            guide_hit = (
                self.help_modal_guide_rect.isValid()
                and self.help_modal_guide_rect.adjusted(-12.0, -12.0, 12.0, 12.0).contains(px, py)
            )
            tutorial_hit = (
                hasattr(self, "help_modal_tutorial_rect")
                and self.help_modal_tutorial_rect.isValid()
                and self.help_modal_tutorial_rect.adjusted(-12.0, -12.0, 12.0, 12.0).contains(px, py)
            )
            close_hit = (
                self.help_modal_close_rect.isValid()
                and self.help_modal_close_rect.adjusted(-12.0, -12.0, 12.0, 12.0).contains(px, py)
            )
            self.hovered_help_modal_guide = bool(guide_hit)
            self.hovered_help_modal_tutorial = bool(tutorial_hit and not guide_hit)
            self.hovered_help_modal_close = bool(close_hit and not guide_hit and not tutorial_hit)
            self.hovered_header_exit = False
            self.hovered_header_help = False
            self.hovered_block = None
            if guide_hit or tutorial_hit or close_hit:
                self._wake_ghost_peek()
            self.update()
            return

        self.hovered_help_modal_close = False
        self.hovered_help_modal_tutorial = False

        # Check if gaze is targeting the prominent header exit button (+15px buffer)
        if not self.reading_mode and self.header_exit_rect.isValid():
            expanded_exit_rect = self.header_exit_rect.adjusted(-15.0, -15.0, 15.0, 15.0)
            if expanded_exit_rect.contains(px, py):
                self.hovered_header_exit = True
                self.hovered_header_help = False
                self.hovered_block = None
                self._wake_ghost_peek()
                self.update()
                return

        self.hovered_header_exit = False

        # Check if gaze is targeting the header help button (+15px buffer)
        if not self.reading_mode and hasattr(self, "header_help_rect") and self.header_help_rect.isValid():
            expanded_help_rect = self.header_help_rect.adjusted(-15.0, -15.0, 15.0, 15.0)
            if expanded_help_rect.contains(px, py):
                self.hovered_header_help = True
                self.hovered_header_exit = False
                self.hovered_block = None
                self._wake_ghost_peek()
                self.update()
                return

        self.hovered_header_help = False

        # Check if gaze is targeting the header mode button (+15px buffer)
        if not self.reading_mode and hasattr(self, "header_mode_rect") and self.header_mode_rect.isValid():
            expanded_mode_rect = self.header_mode_rect.adjusted(-15.0, -15.0, 15.0, 15.0)
            if expanded_mode_rect.contains(px, py):
                self.hovered_header_mode = True
                self.hovered_header_exit = False
                self.hovered_header_help = False
                self.hovered_header_lang = False
                self.hovered_block = None
                self._wake_ghost_peek()
                self.update()
                return

        self.hovered_header_mode = False

        # Check if gaze is targeting the header language button (+15px buffer)
        if not self.reading_mode and hasattr(self, "header_lang_rect") and self.header_lang_rect.isValid():
            expanded_lang_rect = self.header_lang_rect.adjusted(-15.0, -15.0, 15.0, 15.0)
            if expanded_lang_rect.contains(px, py):
                self.hovered_header_lang = True
                self.hovered_header_exit = False
                self.hovered_header_help = False
                self.hovered_block = None
                self._wake_ghost_peek()
                self.update()
                return

        self.hovered_header_lang = False

        # Multi-monitor selector pill (between language and help).
        if (
            not self.reading_mode
            and self.header_screen_rect.isValid()
            and self.header_screen_rect.adjusted(-12.0, -12.0, 12.0, 12.0).contains(px, py)
        ):
            self.hovered_header_screen = True
            self.hovered_block = None
            self._wake_ghost_peek()
            self.update()
            return
        self.hovered_header_screen = False

        # Sniper action selector pill (between language and help).
        if (
            self.current_context_mode_id == "sniper"
            and self._sniper_action_pill_rect.isValid()
            and self._sniper_action_pill_rect.adjusted(-10.0, -10.0, 10.0, 10.0).contains(px, py)
        ):
            self.hovered_sniper_action = True
            self.hovered_block = None
            self._wake_ghost_peek()
            self.update()
            return
        self.hovered_sniper_action = False

        # Hit-test the actual card rectangles. This is exact even when the
        # monitor-aware layout shifts the grid and adds 10px gaps.
        point = QPointF(px, py)
        block_idx = None
        for candidate in range(9):
            if self.get_block_rect(candidate).adjusted(-6.0, -6.0, 6.0, 6.0).contains(point):
                block_idx = candidate
                break
        if block_idx is None:
            if getattr(self, "hud_layout_mode", "FULL_GRID") == "RIGHT_DOCK":
                w = float(self.width()) if self.width() > 0 else 1920.0
                dock_w = max(
                    float(getattr(self, "right_dock_min_w", 460.0)),
                    min(
                        float(getattr(self, "right_dock_max_w", 500.0)),
                        w * float(getattr(self, "right_dock_ratio", 0.30)),
                    ),
                )
                dock_w = min(dock_w, max(120.0, w - 2.0 * self.margin))
                dock_left = max(self.margin, w - self.margin - dock_w)
                if px < dock_left - 15.0:
                    self.hovered_block = None
                    self._dwell_block = None
                    self._dwell_progress = 0.0
                    self._dwell_fired = False
                    if getattr(self, "show_tutorial_modal", False):
                        self._update_mini_tutorial_gaze(gx, gy)
                    self.update()
                    return
            nearest = min(
                range(9),
                key=lambda idx: (
                    self.get_block_rect(idx).center().x() - px
                ) ** 2
                + (self.get_block_rect(idx).center().y() - py) ** 2,
            )
            block_idx = nearest

        if self.current_context_mode_id != "sniper":
            gx, gy = self._apply_cell_gravity(gx, gy, block_idx)
            self.current_gaze = (gx, gy)

        if self.reading_mode:
            # In reading mode, inhibit all blocks except Block 4 (Resume trigger)
            if block_idx == 4:
                self.hovered_block = 4
            else:
                self.hovered_block = None
        else:
            self.hovered_block = block_idx

        # Wake ghost mode instantly when interacting with HUD
        if self.hovered_block is not None:
            self._wake_ghost_peek()

        # Update adaptive dwell engine
        self._update_adaptive_dwell(self.hovered_block)

        # Update mini-tutorial gaze
        if getattr(self, "show_tutorial_modal", False):
            self._update_mini_tutorial_gaze(gx, gy)

        self.update()

    def _apply_cell_gravity(
        self, gx: float, gy: float, block_idx: Optional[int]
    ) -> Tuple[float, float]:
        """Soft 15% pull to a cell center after 150ms of stable dwell."""
        if (
            not getattr(config, "CELL_MAGNETISM_ENABLED", True)
            or self.reading_mode
            or self.current_context_mode_id == "sniper"
            or block_idx is None
        ):
            self._gravity_block = None
            self._gravity_since = 0.0
            return gx, gy

        now = time.time()
        if block_idx != self._gravity_block:
            self._gravity_block = block_idx
            self._gravity_since = now
            return gx, gy

        rect = self.get_block_rect(block_idx)
        if rect.width() <= 1.0 or rect.height() <= 1.0:
            return gx, gy
        px, py = gx * self.width(), gy * self.height()
        rel_x = (px - rect.left()) / rect.width()
        rel_y = (py - rect.top()) / rect.height()
        # Block 5 (index 4) has an expanded magnetic capture zone for safe rest
        if block_idx == 4:
            if not (0.10 <= rel_x <= 0.90 and 0.10 <= rel_y <= 0.90):
                self._gravity_since = now
                return gx, gy
            strength = float(getattr(config, "CELL_MAGNETISM_STRENGTH", 0.15)) * 1.8
        else:
            if not (0.18 <= rel_x <= 0.82 and 0.18 <= rel_y <= 0.82):
                self._gravity_since = now
                return gx, gy
            strength = float(getattr(config, "CELL_MAGNETISM_STRENGTH", 0.15))
        center = rect.center()
        cx = center.x() / max(1.0, self.width())
        cy = center.y() / max(1.0, self.height())
        return gx + (cx - gx) * strength, gy + (cy - gy) * strength

    def _clear_header_exit_flash(self) -> None:
        self.active_click_header_exit = False
        self.update()

    def _disarm_exit(self) -> None:
        """Clears the two-click exit arm after the confirmation window expires."""
        if time.time() < self._exit_armed_until:
            return
        self._exit_armed_until = 0.0
        if self.last_action_desc.startswith("SALIR:"):
            self.last_action_desc = "Listo"
        self.update()

    def release_freelook_controls(self) -> None:
        """Releases any FreeLook mouse/key hold before pausing or shutting down."""
        controller = self.mouse_controller
        try:
            if controller is not None and getattr(self, "_gaming_right_held", False):
                controller.mouse_up("right")
            if controller is not None and getattr(self, "_hold_started", False):
                if getattr(self, "_gaming_mode", False):
                    controller.key_up("w")
                else:
                    controller.mouse_up("left")
        except Exception:
            pass
        self._gaming_right_held = False
        self._hold_started = False
        self._mouth_active = False
        self._jaw_locked = False
        self._jaw_lock_pos = None
        self._reset_freelook_edge_scroll()
        self.release_all_game_keys()

    def _clear_header_help_flash(self) -> None:
        """Clears active click visual pulse on header help button."""
        self.active_click_header_help = False
        self.update()

    def _clear_header_mode_flash(self) -> None:
        self.active_click_header_mode = False
        self.update()

    def _clear_header_lang_flash(self) -> None:
        """Clears active click visual pulse on header language button."""
        self.active_click_header_lang = False
        self.update()
