"""Grid geometry, margins, focus transitions and block rectangles."""

from ideye.ui.overlay_common import *  # noqa: F401,F403


class OverlayLayoutMixin:
    """Grid geometry, margins, focus transitions and block rectangles."""

    def resizeEvent(self, event) -> None:
        """Handles window resize events to keep interactive target geometry updated."""
        super().resizeEvent(event)
        if self.debug_widget is not None:
            self.refresh_grid_right_margin(animate=False)
        self._update_header_exit_rect()

    def showEvent(self, event) -> None:
        """Ensures Win32 non-activating and topmost styles are reapplied when shown/restored."""
        super().showEvent(event)
        if self.debug_widget is not None:
            self.refresh_grid_right_margin(animate=False)
        self._update_header_exit_rect()
        if sys.platform == "win32":
            self._apply_win32_no_activate()

    def _set_theme_color(self, theme_color: str) -> None:
        """Updates the cached active-card and mode-button colors for a mode."""
        self.theme_color = str(theme_color or "#3b82f6")
        color = QColor(self.theme_color)
        self._pen_card_active = QPen(color, 2.0)
        self._pen_mode_idle = QPen(color, 1.0)
        glow = QColor(color)
        glow.setAlpha(55)
        self._brush_mode_glow = QBrush(glow)
        idle = QColor(color)
        idle.setAlpha(24)
        self._brush_mode_idle = QBrush(idle)
        badge = QColor(color)
        badge.setAlpha(58)
        self._brush_badge_theme = QBrush(badge)
        self._pen_badge_theme = QPen(QColor(color.red(), color.green(), color.blue(), 150), 1.0)
        self._color_theme_text = QColor(color)

    def _get_grid_left(self, w: float, effective_right_margin: float) -> float:
        """Returns the grid's left origin.

        With a docked monitor the grid is centered symmetrically so normalized
        gaze (0.5, 0.5) still lands on the center card. Without a monitor the
        historical left-anchored layout is preserved for multi-resolution
        center-gaze compatibility.
        """
        if self.debug_widget is not None:
            return self.margin + effective_right_margin
        return self.margin

    def _get_effective_right_margin(self, w: float) -> float:
        """Returns the right margin, including the docked DebugWidget when visible."""
        if self.debug_widget is not None:
            if self._animated_right_margin is not None:
                return max(0.0, float(self._animated_right_margin))
            return self._target_right_margin(w)
        # No monitor attached: preserve the historical scaled default used by tests.
        base_right_margin = float(getattr(self, "grid_right_margin", 364.0))
        if w >= 1920.0:
            return base_right_margin
        return base_right_margin * (w / 1920.0)

    def _target_right_margin(self, w: Optional[float] = None) -> float:
        """Computes the monitor-aware right margin (width + 24px safety gap)."""
        if self.debug_widget is None:
            return 0.0
        if not self.debug_widget.isVisible() or getattr(self.debug_widget, "is_collapsed", False):
            return 0.0
        width = float(w if w is not None else (self.width() or 1920.0))
        debug_left = float(self.debug_widget.x() - self.x())
        # The monitor's true left edge determines the gap; the width+16 rule is
        # kept as a floor so the grid never slides under the panel.
        return max(float(self.debug_widget.width()) + 24.0, width - debug_left + 24.0)

    def set_debug_widget(self, widget: Optional[QWidget]) -> None:
        """Links the docked DebugWidget so the grid can react to its layout."""
        self.debug_widget = widget
        if widget is not None:
            try:
                widget.collapsed_toggled.connect(self._on_debug_widget_layout_changed)
            except Exception:
                pass
            try:
                widget.visibility_changed.connect(self._on_debug_widget_visible_changed)
            except Exception:
                pass
        self.refresh_grid_right_margin(animate=False)

    @pyqtSlot(bool)
    def set_vscode_connected(self, connected: bool) -> None:
        """Updates the VS Code WebSocket connection badge in the header."""
        self._ws_connected = bool(connected)
        self.update()

    def _on_debug_widget_layout_changed(self, _collapsed: bool = False) -> None:
        self.refresh_grid_right_margin()

    def _on_debug_widget_visible_changed(self, _visible: bool = False) -> None:
        self.refresh_grid_right_margin()

    @property
    def hovered_block(self) -> Optional[int]:
        return getattr(self, "_hovered_block", None)

    @hovered_block.setter
    def hovered_block(self, value: Optional[int]) -> None:
        old = getattr(self, "_hovered_block", None)
        self._hovered_block = value
        if old != value:
            self._start_focus_transition(old)

    def _start_focus_transition(self, previous: Optional[int]) -> None:
        """Cross-fades the focus halo between cells; always restarts from the live value.

        Any running transition is stopped first, so rapid focus changes (a
        saccade across the grid) never queue: the halo of the cell the user
        left fades from wherever it currently is, and the new one fades in.
        """
        running = getattr(self, "_focus_anim", None)
        if running is not None:
            running.stop()
            self._focus_anim = None
        live_in = float(getattr(self, "_focus_in", 1.0))
        self._focus_prev = previous
        self._focus_out_start = live_in if previous is not None else 0.0
        self._focus_out = self._focus_out_start
        self._focus_in = 0.0
        ms = duration(MOTION_FOCUS_MS, bool(getattr(self, "reduced_motion", False)))
        if ms <= 0:
            self._focus_in = 1.0
            self._focus_out = 0.0
            self.update()
            return
        anim = QVariantAnimation(self)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setDuration(ms)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.valueChanged.connect(self._on_focus_animated)
        self._focus_anim = anim
        anim.start()

    def _on_focus_animated(self, value: Any) -> None:
        try:
            t = float(value)
        except (TypeError, ValueError):
            return
        self._focus_in = t
        self._focus_out = float(getattr(self, "_focus_out_start", 0.0)) * (1.0 - t)
        self.update()

    def _focus_halo_weight(self, index: int, is_active: bool) -> float:
        """Returns the 0..1 halo strength for a cell during the focus transition."""
        if is_active:
            if index == getattr(self, "_hovered_block", None):
                return float(getattr(self, "_focus_in", 1.0))
            return 1.0
        if index == getattr(self, "_focus_prev", None):
            return float(getattr(self, "_focus_out", 0.0))
        return 0.0

    def refresh_grid_right_margin(self, animate: bool = True) -> None:
        """Animates the grid between docked and expanded layouts."""
        if self._right_margin_animation is not None:
            self._right_margin_animation.stop()
            self._right_margin_animation = None

        if self.debug_widget is None:
            self._animated_right_margin = None
            self._update_header_exit_rect()
            self.update()
            return

        target = self._target_right_margin()
        current = (
            self._animated_right_margin
            if self._animated_right_margin is not None
            else self._get_effective_right_margin(float(self.width() or 1920.0))
        )
        if not animate or self.reduced_motion or abs(current - target) < 0.5:
            self._animated_right_margin = target
            self._update_header_exit_rect()
            self.update()
            return

        if self._right_margin_animation is not None:
            self._right_margin_animation.stop()
        animation = QVariantAnimation(self)
        animation.setStartValue(float(current))
        animation.setEndValue(float(target))
        animation.setDuration(180)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.valueChanged.connect(self._on_right_margin_animated)
        self._right_margin_target = float(target)
        animation.finished.connect(self._on_right_margin_finished)
        self._right_margin_animation = animation
        animation.start()

    def _on_right_margin_finished(self) -> None:
        try:
            self._animated_right_margin = float(self._right_margin_target)
            self._update_header_exit_rect()
            self.update()
        except RuntimeError:
            pass

    def _on_right_margin_animated(self, value: Any) -> None:
        try:
            self._animated_right_margin = float(value)
        except (TypeError, ValueError):
            return
        self._update_header_exit_rect()
        self.update()

    def set_grid_right_margin(self, margin: float) -> None:
        """Sets the fallback reserved margin when no DebugWidget is attached."""
        self.grid_right_margin = max(0.0, float(margin))
        if self.debug_widget is None:
            self._update_header_exit_rect()
            self.update()

    def get_block_rect(self, index: int) -> QRectF:
        """Computes the QRectF for a 3x3 card with 12px padding and 10px gaps."""
        w = float(self.width()) if self.width() > 0 else 1920.0
        h = float(self.height()) if self.height() > 0 else 1080.0
        if getattr(self, "hud_layout_mode", "FULL_GRID") == "RIGHT_DOCK":
            dock_w = max(
                float(getattr(self, "right_dock_min_w", 460.0)),
                min(
                    float(getattr(self, "right_dock_max_w", 500.0)),
                    w * float(getattr(self, "right_dock_ratio", 0.30)),
                ),
            )
            dock_w = min(dock_w, max(120.0, w - 2.0 * self.margin))
            left = max(self.margin, w - self.margin - dock_w)
            right = w - self.margin
        else:
            right_margin = self._get_effective_right_margin(w)
            left = self._get_grid_left(w, right_margin)
            right = w - self.margin - right_margin
        top = self.margin + self.breadcrumb_height + self.gap
        bottom = h - self.margin
        avail_w = max(1.0, right - left)
        avail_h = max(1.0, bottom - top)
        cell_w = max(1.0, (avail_w - 2.0 * self.gap) / 3.0)
        cell_h = max(1.0, (avail_h - 2.0 * self.gap) / 3.0)
        col = index % 3
        row = index // 3
        return QRectF(
            left + col * (cell_w + self.gap),
            top + row * (cell_h + self.gap),
            cell_w,
            cell_h,
        )

    @staticmethod
    def _wrapped_text_height(font: QFont, text: str, width: float) -> int:
        fm = QFontMetrics(font)
        rect = fm.boundingRect(
            QRect(0, 0, max(20, int(width)), 0),
            Qt.TextFlag.TextWordWrap,
            str(text),
        )
        return max(fm.height(), int(rect.height()))
