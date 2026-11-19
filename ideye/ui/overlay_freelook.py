"""FreeLook edge scroll, gaze-to-screen mapping and gameplay joystick."""

from ideye.ui.overlay_common import *  # noqa: F401,F403


class OverlayFreelookMixin:
    """FreeLook edge scroll, gaze-to-screen mapping and gameplay joystick."""

    def _reset_freelook_edge_scroll(self) -> None:
        self._edge_scroll_direction = 0
        self._edge_scroll_since = 0.0
        self._edge_scroll_last = 0.0

    def _update_strategy_edge_scroll(self, gx: float, gy: float, now: Optional[float] = None) -> bool:
        """Pan the cursor/camera near the 20 px screen borders in strategy profiles."""
        if self._game_profile_name != "strategy_rpg" or not self._gaming_mode:
            return False
        sw, sh = self._get_screen_size()
        x, y = self._freelook_screen_coords(gx, gy, sw, sh)
        margin = 20
        dx = -8 if x <= margin else 8 if x >= sw - margin else 0
        dy = -8 if y <= margin else 8 if y >= sh - margin else 0
        if dx == 0 and dy == 0:
            self._edge_scroll_last = 0.0
            return False
        timestamp = time.time() if now is None else float(now)
        if timestamp - self._edge_scroll_last < 0.08:
            return True
        controller = self.mouse_controller
        if controller is None:
            return False
        px, py = self._freelook_last_pos
        nx = max(0, min(sw - 1, px + dx))
        ny = max(0, min(sh - 1, py + dy))
        try:
            controller.move_direct(nx, ny)
            self._freelook_last_pos = (nx, ny)
        except Exception:
            pass
        self._edge_scroll_last = timestamp
        self.last_action_desc = "Edge-Scroll activo"
        return True

    def _update_freelook_edge_scroll(self, gy: float, now: Optional[float] = None) -> int:
        """Scroll while the gaze rests near the top/bottom edge in desktop FreeLook."""
        if (
            (self._gaming_mode and self._game_profile_name != "strategy_rpg")
            or self._jaw_locked
            or not bool(getattr(config, "FREELOOK_EDGE_SCROLL_ENABLED", True))
        ):
            self._reset_freelook_edge_scroll()
            return 0
        zone = max(0.02, min(0.20, float(getattr(config, "FREELOOK_EDGE_SCROLL_ZONE", 0.075))))
        if gy <= zone:
            direction = 1
        elif gy >= 1.0 - zone:
            direction = -1
        else:
            self._reset_freelook_edge_scroll()
            return 0

        timestamp = time.time() if now is None else float(now)
        if direction != self._edge_scroll_direction:
            self._edge_scroll_direction = direction
            self._edge_scroll_since = timestamp
            self._edge_scroll_last = 0.0
            return 0

        delay = max(0.05, float(getattr(config, "FREELOOK_EDGE_SCROLL_DELAY_SEC", 0.30)))
        interval = max(0.04, float(getattr(config, "FREELOOK_EDGE_SCROLL_INTERVAL_SEC", 0.11)))
        if timestamp - self._edge_scroll_since < delay:
            return 0
        if self._edge_scroll_last and timestamp - self._edge_scroll_last < interval:
            return 0

        controller = self.mouse_controller
        if controller is None:
            controller = OSMouseController()
            self.mouse_controller = controller
        step = max(1, int(getattr(config, "FREELOOK_EDGE_SCROLL_STEP", 3)))
        try:
            controller.scroll(direction * step)
        except Exception:
            pass
        self._edge_scroll_last = timestamp
        self.last_action_desc = "Scroll \u2191" if direction > 0 else "Scroll \u2193"
        return direction

    def _freelook_prethreshold(self) -> float:
        return max(0.01, float(getattr(self, "mar_threshold", 0.45)) * 0.55)

    def _freelook_jaw_threshold(self) -> float:
        """Mouth opening that freezes the pointer before a click.

        The old 55% threshold was close to a relaxed mouth for many users,
        which made the cursor stop and swallowed intentional clicks.
        """
        rest = max(
            float(getattr(config, "MAR_REST_THRESHOLD", 0.20)),
            float(getattr(self, "_mar_rest_baseline", 0.20)),
        )
        minimum = float(getattr(config, "FREELOOK_JAW_LOCK_MIN_MAR", 0.27))
        return max(self._freelook_prethreshold(), rest + 0.08, minimum)

    def set_mar_threshold(self, value: float, calibrated: Optional[bool] = None) -> None:
        """Keeps FreeLook click thresholds aligned with calibration/settings."""
        try:
            mar = max(0.10, min(0.90, float(value)))
        except (TypeError, ValueError, OverflowError):
            return
        self.mar_threshold = mar
        if calibrated is not None:
            self.mar_calibrated = bool(calibrated)
        self._mar_rest_window.clear()
        self._mar_rest_baseline = max(
            0.15,
            min(
                0.60,
                max(
                    float(getattr(config, "MAR_REST_THRESHOLD", 0.20)),
                    mar - 0.18,
                ),
            ),
        )

    def _freelook_screen_coords(
        self, gx: float, gy: float, screen_w: int, screen_h: int
    ) -> Tuple[int, int]:
        """Maps normalized gaze to the full physical screen with edge overscan.

        The grid still lives inside availableGeometry; only FreeLook uses the
        full geometry so the taskbar, tray and maximized-window close button
        remain reachable.
        """
        try:
            gx = float(gx)
            gy = float(gy)
        except (TypeError, ValueError, OverflowError):
            return (0, 0)
        if not (math.isfinite(gx) and math.isfinite(gy)):
            return (0, 0)
        margin_x = max(0.0, min(0.20, float(getattr(config, "OVERSCAN_MARGIN_X", 0.04))))
        margin_top = max(0.0, min(0.20, float(getattr(config, "OVERSCAN_MARGIN_Y_TOP", 0.04))))
        margin_bottom = max(0.0, min(0.25, float(getattr(config, "OVERSCAN_MARGIN_Y_BOTTOM", 0.07))))
        span_x = max(1e-6, 1.0 - 2.0 * margin_x)
        span_y = max(1e-6, 1.0 - margin_top - margin_bottom)
        nx = max(0.0, min(1.0, (float(gx) - margin_x) / span_x))
        ny = max(0.0, min(1.0, (float(gy) - margin_top) / span_y))
        x = int(round(nx * max(0, screen_w - 1)))
        y = int(round(ny * max(0, screen_h - 1)))

        # Top magnet: comfortable upward gaze rarely reaches the extreme top
        # of the screen. Pull the cursor into the command bar before applying
        # the taskbar rail so the header, mode selector and exit stay usable.
        top_zone = max(0.0, min(0.35, float(getattr(config, "FREELOOK_TOP_MAGNET_ZONE", 0.18))))
        top_pull = max(0.0, min(1.0, float(getattr(config, "FREELOOK_TOP_MAGNET_PULL", 0.94))))
        gaze_y = max(0.0, min(1.0, float(gy)))
        if top_zone > 0.0 and gaze_y < top_zone:
            strength = max(0.0, 1.0 - (gaze_y / top_zone))
            y = int(round(y * (1.0 - top_pull * strength)))

        rail_height = max(1, int(getattr(config, "TASKBAR_RAIL_HEIGHT", 52)))
        if y >= screen_h - rail_height:
            target_y = max(0, screen_h - int(getattr(config, "TASKBAR_RAIL_TARGET_Y", 24)))
            pull = max(0.0, min(1.0, float(getattr(config, "TASKBAR_RAIL_PULL", 0.60))))
            y = int(round(y + (target_y - y) * pull))
        return (
            max(0, min(screen_w - 1, x)),
            max(0, min(screen_h - 1, y)),
        )

    def _handle_freelook_gaze(self, gx: float, gy: float) -> None:
        if self._gaming_mode and self._gaming_control_state == "JOYSTICK":
            self._update_gameplay_joystick(gx, gy)
            return
        screen_w, screen_h = self._get_screen_size()
        x, y = self._freelook_screen_coords(gx, gy, screen_w, screen_h)
        pre = self._freelook_prethreshold()
        jaw_threshold = self._freelook_jaw_threshold()
        now = time.time()
        max_lock = max(0.5, float(getattr(config, "FREELOOK_JAW_LOCK_MAX_SEC", 2.0)))

        if self._jaw_locked and self._jaw_lock_since > 0.0 and now - self._jaw_lock_since > max_lock:
            # Safety watchdog: a stuck jaw-lock must never leave the pointer
            # frozen at a corner indefinitely.
            self._jaw_locked = False
            self._jaw_lock_pos = None
            self._jaw_lock_since = 0.0
            self._mouth_active = False

        if self.current_mar >= jaw_threshold:
            if not self._jaw_locked:
                self._jaw_locked = True
                self._jaw_lock_pos = self._freelook_last_pos
                self._jaw_lock_since = now
            if self._jaw_lock_pos is not None:
                x, y = self._jaw_lock_pos
        else:
            self._jaw_locked = False
            self._jaw_lock_pos = None
            self._jaw_lock_since = 0.0
            self._freelook_last_pos = (x, y)
            controller = self.mouse_controller
            if controller is not None:
                try:
                    controller.move_direct(x, y)
                except Exception:
                    pass

        self.sniper_lens.update_gaze(x, y)
        if self.sniper_lens.active:
            px, py = self._freelook_last_pos
            x = int(round(px + (x - px) * self.sniper_lens.movement_multiplier))
            y = int(round(py + (y - py) * self.sniper_lens.movement_multiplier))
            self._capture_sniper_lens()
        self._update_strategy_edge_scroll(gx, gy)
        self._update_freelook_edge_scroll(gy)
        normalized = (x / float(screen_w), y / float(screen_h))
        if normalized != self.current_gaze:
            self.current_gaze = normalized
            self.update()

    def _update_gameplay_joystick(self, gx: float, gy: float) -> None:
        """Maps head position to WASD with a comfortable central deadzone."""
        dx = float(gx) - 0.5
        dy = float(gy) - 0.5
        deadzone = float(getattr(config, "GAMING_DEADZONE", 0.14))
        desired = set()
        if dy < -deadzone:
            desired.add("w")
        elif dy > deadzone:
            desired.add("s")
        if dx < -deadzone:
            desired.add("a")
        elif dx > deadzone:
            desired.add("d")

        controller = self.mouse_controller
        if controller is None:
            controller = OSMouseController()
            self.mouse_controller = controller
        had_keys = bool(self._game_keys_down)
        for key in ("w", "a", "s", "d"):
            if key in desired and key not in self._game_keys_down:
                try:
                    controller.key_down(key)
                except Exception:
                    pass
                self._game_keys_down.add(key)
            elif key not in desired and key in self._game_keys_down:
                try:
                    controller.key_up(key)
                except Exception:
                    pass
                self._game_keys_down.discard(key)
        if had_keys and not desired:
            self.release_all_game_keys()
        mode = self._sniper_mode()
        if mode is not None and getattr(mode, "is_twin_stick", False):
            sw, sh = self._get_screen_size()
            tx, ty = self._freelook_screen_coords(gx, gy, sw, sh)
            try:
                controller.move_direct(tx, ty)
                self._freelook_last_pos = (tx, ty)
            except Exception:
                pass
        self.current_gaze = (float(gx), float(gy))
        self.update()
