"""FreeLook mouth click, gaming profile, sniper lens and painting."""

from ideye.ui.overlay_common import *  # noqa: F401,F403


class OverlayFreelookClickMixin:
    """FreeLook mouth click, gaming profile, sniper lens and painting."""

    def release_all_game_keys(self) -> None:
        """Guarantees that movement keys and mouse buttons are released."""
        controller = self.mouse_controller
        if controller is not None:
            try:
                controller.release_all_game_keys(tuple(self._game_keys_down) + ("w", "a", "s", "d", " "))
            except Exception:
                pass
            try:
                controller.release_all_buttons()
            except Exception:
                pass
        self._game_keys_down.clear()
        self._gaming_right_held = False
        self._hold_started = False
        self._jaw_locked = False
        self._jaw_lock_pos = None
        self._jaw_lock_since = 0.0
        self._mouth_active = False
        try:
            self.gaze_scroller.stop()
        except Exception:
            pass
        if getattr(self, "_gaze_scroll_enabled", False):
            self._gaze_scroll_enabled = False
            try:
                self.gaze_scroll_toggled.emit(False)
            except Exception:
                pass

    def reset_freelook_pointer(self) -> None:
        """Centers FreeLook and clears any frozen pointer state after face loss."""
        if self.current_context_mode_id != "sniper":
            return
        self.release_all_game_keys()
        sw, sh = self._get_screen_size()
        center = (max(0, sw // 2), max(0, sh // 2))
        self._freelook_last_pos = center
        self.current_gaze = (0.5, 0.5)
        controller = self.mouse_controller
        if controller is not None:
            try:
                controller.move_direct(*center)
            except Exception:
                pass
        self.update()

    def _freelook_click(self) -> None:
        now = time.time()
        if now - float(getattr(self, "_last_freelook_click_ts", 0.0)) < 0.12:
            return
        self._last_freelook_click_ts = now
        mode = self._sniper_mode()
        action = getattr(mode, "get_action", lambda: "LEFT_CLICK")() if mode else "LEFT_CLICK"
        x, y = self._jaw_lock_pos or self._freelook_last_pos
        controller = self.mouse_controller
        if controller is None:
            controller = OSMouseController()
            self.mouse_controller = controller
        if action == "RIGHT_CLICK":
            try:
                controller.right_click(x, y)
            except Exception:
                pass
        elif action == "DOUBLE_CLICK":
            try:
                controller.double_click(x, y)
            except Exception:
                pass
        elif action == "SCROLL_UP":
            try:
                controller.scroll_at(x, y, 3)
            except Exception:
                pass
        elif action == "SCROLL_DOWN":
            try:
                controller.scroll_at(x, y, -3)
            except Exception:
                pass
        else:
            try:
                controller.left_click(x, y)
            except Exception:
                pass
        self._play_sound("click")
        self.last_action_desc = f"FreeLook: {getattr(mode, 'action_label', 'Clic Izq')}"
        self.sniper_lens.deactivate()
        if (
            self._gaming_mode
            and self._gaming_control_state == "MENU_CURSOR"
            and getattr(config, "GAMING_AUTO_RETURN_AFTER_CLICK", False)
        ):
            self._gaming_control_state = "JOYSTICK"
            self.release_all_game_keys()

    def _update_freelook_mouth(self, mar: float) -> None:
        pre = self._freelook_prethreshold()
        threshold = float(getattr(self, "mar_threshold", 0.45))
        baseline = max(
            float(getattr(config, "MAR_REST_THRESHOLD", 0.20)),
            float(getattr(self, "_mar_rest_baseline", 0.20)),
        )
        trigger_ratio = max(0.35, min(0.95, float(getattr(config, "FREELOOK_MOUTH_TRIGGER_RATIO", 0.78))))
        release_ratio = max(0.25, min(0.90, float(getattr(config, "FREELOOK_MOUTH_RELEASE_RATIO", 0.48))))
        trigger = max(pre + 0.01, threshold * trigger_ratio, baseline + 0.08)
        release = max(pre, threshold * release_ratio, baseline + 0.035)
        release = min(trigger - 0.01, release)
        now = time.time()

        # In gameplay, mouth = click at the current pointer; never move it.
        if self._gaming_mode and self._gaming_control_state == "JOYSTICK":
            controller = self.mouse_controller
            if mar >= trigger and not self._mouth_active:
                self._mouth_active = True
                self._mouth_start = now
                self.update()
                return
            if self._mouth_active and mar < release:
                self._mouth_active = False
                self._hold_started = False
                if controller is not None:
                    try:
                        controller.left_click_current()
                    except Exception:
                        pass
                self._play_sound("click")
                self.last_action_desc = "Gaming: clic"
                self.update()
            return

        if mar >= trigger and not self._mouth_active:
            self._mouth_active = True
            self._mouth_start = now
            self._hold_started = False
            self._jaw_lock_pos = self._jaw_lock_pos or self._freelook_last_pos
            self.update()
            return

        if not self._mouth_active:
            return

        held = now - self._mouth_start
        hold_limit = 0.40 if self._gaming_mode else 0.45
        controller = self.mouse_controller
        if not self._hold_started and held >= hold_limit and controller is not None:
            self._hold_started = True
            if self._gaming_mode:
                controller.key_down("w")
            else:
                controller.mouse_down("left")

        if mar < release:
            if self._hold_started and controller is not None:
                if self._gaming_mode:
                    controller.key_up("w")
                else:
                    controller.mouse_up("left")
            elif not self._hold_started:
                self._freelook_click()
            self._mouth_active = False
            self._hold_started = False
            self.update()

    def set_game_profile(self, profile_name: str) -> None:
        """Applies a dynamic game/application profile without restarting."""
        labels = {
            "sandbox_3d": "Sandbox 3D",
            "twin_stick_roguelike": "Twin-Stick",
            "strategy_rpg": "Estrategia / RPG",
            "default_desktop": "Escritorio",
        }
        name = str(profile_name or "default_desktop")
        self._game_profile_name = name
        self._game_profile_label = labels.get(name, name)
        mode = self._sniper_mode()
        if mode is not None and hasattr(mode, "set_game_profile"):
            mode.set_game_profile(name)
        self.set_gaming_profile(name != "default_desktop")
        if name == "strategy_rpg":
            self._gaming_control_state = "MENU_CURSOR"
        self.last_action_desc = f"Perfil: {self._game_profile_label}"
        self.update()

    def set_gaming_profile(self, enabled: bool) -> None:
        """Applies the watcher's gaming/desktop FreeLook sub-profile."""
        enabled = bool(enabled)
        if enabled == self._gaming_mode:
            return
        if self._gaming_mode:
            self.release_freelook_controls()
        self._gaming_mode = enabled
        self._gaming_control_state = "JOYSTICK"
        self._game_keys_down.clear()
        self.last_action_desc = f"FreeLook: {'GAMING' if enabled else 'ESCRITORIO'}"
        self.update()

    def toggle_gaming_mode(self) -> bool:
        if self._gaming_mode:
            self.release_freelook_controls()
        self._gaming_mode = not self._gaming_mode
        self._gaming_control_state = "JOYSTICK"
        self._game_keys_down.clear()
        self.last_action_desc = f"FreeLook: {'GAMING' if self._gaming_mode else 'ESCRITORIO'}"
        self._play_sound("mode")
        self.update()
        return self._gaming_mode

    def _toggle_gaming_right(self) -> None:
        """Right wink switches between head-joystick and menu cursor."""
        if not self._gaming_mode:
            return
        if self._gaming_control_state == "JOYSTICK":
            self.release_all_game_keys()
            self._gaming_control_state = "MENU_CURSOR"
            self.last_action_desc = "Gaming: Cursor de menú"
        else:
            self._gaming_control_state = "JOYSTICK"
            self.release_all_game_keys()
            self.last_action_desc = "Gaming: Joystick de cabeza"
        self._play_sound("mode")
        self.update()

    def _capture_sniper_lens(self) -> None:
        if not self.sniper_lens.active or self.sniper_lens.target is None:
            return
        target = self.sniper_lens.target
        if self._lens_capture_target is not None:
            if ((target[0] - self._lens_capture_target[0]) ** 2 + (target[1] - self._lens_capture_target[1]) ** 2) < 225:
                return
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        self._lens_capture_in_progress = True
        try:
            # Do not touch window opacity: hiding the whole HUD caused the
            # command bar to flash on every lens refresh.
            QApplication.processEvents()
            self._lens_pixmap = screen.grabWindow(0, int(target[0]) - 40, int(target[1]) - 40, 80, 80)
            self._lens_capture_target = (target[0], target[1])
        except Exception:
            pass
        finally:
            self._lens_capture_in_progress = False

    def activate_sniper_lens(self) -> None:
        if self.current_context_mode_id != "sniper":
            return
        target = self._freelook_last_pos
        self.sniper_lens.activate(float(target[0]), float(target[1]))
        self._capture_sniper_lens()
        self.last_action_desc = "Lupa Sniper activada"
        self.update()

    def toggle_sniper_lens(self) -> None:
        if self.current_context_mode_id != "sniper":
            return
        target = self._freelook_last_pos
        active = self.sniper_lens.toggle(float(target[0]), float(target[1]))
        self.last_action_desc = "Lupa Sniper activada" if active else "Lupa Sniper desactivada"
        if active:
            self._capture_sniper_lens()
        self.update()

    def _paint_sniper_lens(self, painter: QPainter) -> None:
        if not self.sniper_lens.active or self.sniper_lens.target is None:
            return
        tx, ty = self.sniper_lens.target
        cx = tx - float(self.x())
        cy = ty - float(self.y())
        radius = 110.0
        center = QPointF(cx, cy)
        painter.save()
        path = QPainterPath()
        path.addEllipse(center, radius, radius)
        painter.setClipPath(path)
        if self._lens_pixmap is not None and not self._lens_pixmap.isNull():
            size = 80.0 * self.sniper_lens.zoom
            painter.drawPixmap(QRectF(cx - size / 2, cy - size / 2, size, size), self._lens_pixmap, QRectF(self._lens_pixmap.rect()))
        painter.setClipping(False)

        # Outer cyber sapphire precision ring
        painter.setBrush(QColor(10, 15, 29, 30))
        painter.setPen(QPen(QColor(34, 211, 238, 230), 2.5))
        painter.drawEllipse(center, radius, radius)

        # Concentric inner ring with cyan aperture ticks
        inner_r = radius - 10.0
        painter.setPen(QPen(QColor(103, 232, 249, 140), 1.0, Qt.PenStyle.DashLine))
        painter.drawEllipse(center, inner_r, inner_r)

        # Precision crosshairs with center aperture clearance
        painter.setPen(QPen(QColor(103, 232, 249, 200), 1.2))
        painter.drawLine(QPointF(cx - radius + 4.0, cy), QPointF(cx - 10.0, cy))
        painter.drawLine(QPointF(cx + 10.0, cy), QPointF(cx + radius - 4.0, cy))
        painter.drawLine(QPointF(cx, cy - radius + 4.0), QPointF(cx, cy - 10.0))
        painter.drawLine(QPointF(cx, cy + 10.0), QPointF(cx, cy + radius - 4.0))

        # Center sub-pixel aperture target
        painter.setPen(QPen(QColor(248, 250, 252, 230), 1.0))
        painter.drawLine(QPointF(cx - 5.0, cy), QPointF(cx + 5.0, cy))
        painter.drawLine(QPointF(cx, cy - 5.0), QPointF(cx, cy + 5.0))
        painter.setBrush(QBrush(QColor(34, 211, 238)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(center, 2.0, 2.0)
        painter.restore()

    def _paint_freelook_overlay(self, painter: QPainter) -> None:
        """Draws the compact FreeLook status, gaming crosshair and mode switch."""
        mode = self._sniper_mode()
        action = getattr(mode, "action_label", "Clic Izq") if mode else "Clic Izq"
        painter.save()
        if not self._gaming_mode:
            self._gaming_toggle_rect = QRectF()
            self.hovered_gaming_toggle = False
            profile = "ESCRITORIO"
            text = f"FREELOOK → {profile} → {action}"
            hint = "Mira al borde superior o inferior para hacer scroll"
            fm = QFontMetrics(self._font_freelook_hint)
            width = min(520.0, max(260.0, max(fm.horizontalAdvance(text), fm.horizontalAdvance(hint)) + 30.0))
            rect = QRectF(
                self.width() * 0.5 - width * 0.5,
                self.header_rect.bottom() + 8.0,
                width,
                44.0,
            )
            painter.setBrush(QColor(10, 15, 29, 225))
            painter.setPen(QPen(QColor(244, 63, 94, 180), 1.0))
            painter.drawRoundedRect(rect, 8.0, 8.0)
            painter.setPen(QColor(254, 205, 211))
            painter.setFont(self._font_freelook_hint)
            painter.drawText(rect.adjusted(0.0, 5.0, 0.0, -20.0), Qt.AlignmentFlag.AlignCenter, text)
            painter.setPen(QColor(148, 163, 184))
            painter.drawText(rect.adjusted(0.0, 21.0, 0.0, -4.0), Qt.AlignmentFlag.AlignCenter, hint)
            painter.restore()
            return

        state_label = "JOYSTICK" if self._gaming_control_state == "JOYSTICK" else "CURSOR"
        button_text = f"MODO JUEGO: {state_label} → {'CURSOR' if state_label == 'JOYSTICK' else 'JOYSTICK'}"
        fm = QFontMetrics(self._font_freelook_hint)
        width = min(520.0, max(320.0, fm.horizontalAdvance(button_text) + 34.0))
        self._gaming_toggle_rect = QRectF(
            self.width() * 0.5 - width * 0.5,
            self.header_rect.bottom() + 8.0,
            width,
            30.0,
        )
        hovered = getattr(self, "hovered_gaming_toggle", False)
        painter.setBrush(QColor(16, 185, 129, 55) if hovered else QColor(10, 15, 29, 225))
        painter.setPen(QPen(QColor(52, 211, 153, 230), 1.6))
        painter.drawRoundedRect(self._gaming_toggle_rect, 9.0, 9.0)
        painter.setPen(QColor(209, 250, 229))
        painter.setFont(self._font_freelook_hint)
        painter.drawText(self._gaming_toggle_rect, Qt.AlignmentFlag.AlignCenter, button_text)

        if self._gaming_control_state == "JOYSTICK":
            center = QPointF(self.width() * 0.5, self.height() * 0.5)
            radius = 40.0
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(52, 211, 153, 80), 1.4))
            painter.drawEllipse(center, radius + 8.0, radius + 8.0)
            painter.setPen(QPen(QColor(52, 211, 153, 150), 1.2))
            painter.drawLine(QPointF(center.x() - 12, center.y()), QPointF(center.x() + 12, center.y()))
            painter.drawLine(QPointF(center.x(), center.y() - 12), QPointF(center.x(), center.y() + 12))
            gx, gy = self.current_gaze
            dot = QPointF(
                center.x() + max(-1.0, min(1.0, (gx - 0.5) * 3.0)) * radius,
                center.y() + max(-1.0, min(1.0, (gy - 0.5) * 3.0)) * radius,
            )
            painter.setBrush(QColor(52, 211, 153, 230))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(dot, 6.0, 6.0)
            painter.setPen(QColor(167, 243, 208))
            painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            painter.drawText(
                QRectF(center.x() - 90.0, center.y() + 54.0, 180.0, 18.0),
                Qt.AlignmentFlag.AlignCenter,
                "mueve la cabeza → boca = clic → guiño der = cursor",
            )
        painter.restore()
