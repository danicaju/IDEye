"""Header bar rectangles, help modal layout and preview chips."""

from ideye.ui.overlay_common import *  # noqa: F401,F403
from ideye.ui.overlay_common import (  # noqa: F401
    _clean_action_label,
    _soften_caps,
)


class OverlayHeaderMixin:
    """Header bar rectangles, help modal layout and preview chips."""

    def _help_modal_layout(self, w: float, h: float) -> Dict[str, Any]:
        """Computes a height that fits every wrapped row inside the modal."""
        card_w = min(1180.0, max(720.0, w - 60.0))
        margin = 24.0
        gap = 14.0
        col_w = max(160.0, (card_w - 2.0 * margin - 2.0 * gap) / 3.0)

        gesture_rows = []
        for title, action, desc in HELP_GESTURES:
            title_h = QFontMetrics(self._font_modal_item_title).height()
            action_h = QFontMetrics(self._font_modal_item_desc).height()
            desc_h = self._wrapped_text_height(self._font_modal_item_desc, desc, col_w - 28.0)
            gesture_rows.append((title, action, desc, title_h, action_h, desc_h,
                                 title_h + action_h + desc_h + 12.0))

        half = (len(HELP_SHORTCUTS) + 1) // 2
        shortcut_cols = [list(HELP_SHORTCUTS[:half]), list(HELP_SHORTCUTS[half:])]
        shortcut_heights = []
        for column in shortcut_cols:
            total = 0.0
            heights = []
            for key, name, desc in column:
                desc_h = self._wrapped_text_height(self._font_modal_item_desc, desc, col_w - 28.0)
                row_h = 16.0 + 16.0 + desc_h + 6.0
                heights.append((key, name, desc, desc_h, row_h))
                total += row_h
            shortcut_heights.append((heights, total))

        content_h = max(
            sum(row[6] for row in gesture_rows),
            max((total for _, total in shortcut_heights), default=0.0),
        )
        card_h = min(max(420.0, h - 24.0), max(440.0, content_h + 190.0))
        card_x = (w - card_w) * 0.5
        card_y = (h - card_h) * 0.5
        card_rect = QRectF(card_x, card_y, card_w, card_h)
        col_y = card_y + 80.0
        col_content_h = max(80.0, card_h - 80.0 - 58.0)
        columns = [
            QRectF(card_x + margin, col_y, col_w, col_content_h),
            QRectF(card_x + margin + col_w + gap, col_y, col_w, col_content_h),
            QRectF(card_x + margin + 2.0 * (col_w + gap), col_y, col_w, col_content_h),
        ]
        return {
            "card": card_rect,
            "columns": columns,
            "gesture_rows": gesture_rows,
            "shortcut_columns": shortcut_heights,
            "col_w": col_w,
        }

    def _update_help_modal_rect(self) -> None:
        """Computes the modal card, its columns and the close-button target."""
        w = float(self.width()) if self.width() > 0 else 1920.0
        h = float(self.height()) if self.height() > 0 else 1080.0
        layout = self._help_modal_layout(w, h)
        card = layout["card"]
        self.help_modal_rect = card
        close_btn_h = 42.0
        button_gap = 12.0
        row_margin = 24.0
        available = max(300.0, card.width() - row_margin * 2.0 - 2.0 * button_gap)
        guide_btn_w = min(280.0, available * 0.36)
        tutorial_btn_w = min(230.0, available * 0.28)
        close_btn_w = max(160.0, available - guide_btn_w - tutorial_btn_w)
        row_y = card.y() + card.height() - close_btn_h - 14.0
        self.help_modal_guide_rect = QRectF(
            card.x() + row_margin, row_y, guide_btn_w, close_btn_h
        )
        self.help_modal_tutorial_rect = QRectF(
            self.help_modal_guide_rect.right() + button_gap, row_y, tutorial_btn_w, close_btn_h
        )
        self.help_modal_close_rect = QRectF(
            self.help_modal_tutorial_rect.right() + button_gap, row_y, close_btn_w, close_btn_h
        )

    def _should_show_last_action(self) -> bool:
        """Returns True when the last-action pill should be rendered."""
        desc = (self.last_action_desc or "").strip()
        if not desc:
            return False
        lowered = desc.lower()
        if lowered in ("ninguna", "elegir modo", "elige un modo", "elige un modo"):
            return False
        if lowered.startswith("modo:"):
            return False
        return True

    def _update_header_exit_rect(self) -> None:
        """Computes the unified floating command bar and its interactive targets."""
        w = float(self.width()) if self.width() > 0 else 1920.0
        if getattr(self, "hud_layout_mode", "FULL_GRID") == "RIGHT_DOCK":
            dock_w = max(
                float(getattr(self, "right_dock_min_w", 460.0)),
                min(
                    float(getattr(self, "right_dock_max_w", 500.0)),
                    w * float(getattr(self, "right_dock_ratio", 0.30)),
                ),
            )
            dock_w = min(dock_w, max(120.0, w - 2.0 * self.margin))
            grid_left = max(self.margin, w - self.margin - dock_w)
            right_margin = 0.0
        else:
            right_margin = self._get_effective_right_margin(w)
            grid_left = self._get_grid_left(w, right_margin)
        brand_w = float(QFontMetrics(self._font_header_bold_btn).horizontalAdvance("IDEye"))
        ws_full_w = float(QFontMetrics(self._font_header_left).horizontalAdvance("VS Code")) + 11.0
        layout = HeaderLayout.compute(
            width=w,
            margin=self.margin,
            header_height=self.breadcrumb_height,
            right_margin=right_margin,
            grid_left=grid_left,
            show_last_action=self._should_show_last_action(),
            screen_count=self.screen_count,
            mode_id=self.current_context_mode_id,
            brand_text_width=brand_w,
            ws_full_width=ws_full_w,
        )
        self.header_rect = layout.header
        self._header_logo_rect = layout.logo
        self._header_breadcrumb_rect = layout.breadcrumb
        self._header_status_rect = layout.status
        self.header_exit_rect = layout.exit
        self.header_help_rect = layout.help
        self.header_lang_rect = layout.lang
        self.header_mode_rect = layout.mode
        self._last_action_pill_rect = layout.last_action
        self._sniper_action_pill_rect = layout.sniper_action
        self.header_screen_rect = layout.screen
        self._header_exit_w = layout.exit_w
        self._header_help_w = layout.help_w
        self._header_lang_w = layout.lang_w
        self._header_mode_w = layout.mode_w
        self._header_ws_dot_only = layout.ws_dot_only
        self._header_ws_show = layout.ws_show
        if not self.header_screen_rect.isValid():
            self.hovered_header_screen = False
        self._update_help_modal_rect()

    def _card_header_rects(
        self, rect: QRectF, badge_text: str, has_icon: bool
    ) -> tuple[QRectF, QRectF]:
        """Compute status badge and vector icon cell rectangles for a menu card header.

        Returns a 2-tuple (badge_rect, cell_rect). The badge stays at the top-right
        of the band. The icon cell (28x28) is rendered immediately to its left with
        an 8-10 px gap. If the remaining title width would drop below 72 px, the
        icon cell is hidden but the badge is kept.
        """
        y = rect.y()
        badge_rect = QRectF()
        cell_rect = QRectF()

        if badge_text:
            metrics = QFontMetrics(self._font_status)
            badge_w = max(62.0, metrics.horizontalAdvance(badge_text) + 14.0)
            badge_rect = QRectF(rect.right() - 10.0 - badge_w, y + 17.0, badge_w, 18.0)

        cell_size = 28.0
        if has_icon:
            if badge_rect.isValid():
                cell_x = badge_rect.left() - 10.0 - cell_size
            else:
                cell_x = rect.right() - 10.0 - cell_size
            icon_y = y + 12.0
            cell_rect = QRectF(cell_x, icon_y, cell_size, cell_size)

        # Hide the icon cell if the title area would become too narrow.
        title_left = rect.x() + 42.0
        first_right = min(
            badge_rect.left() if badge_rect.isValid() else rect.right() - 8.0,
            cell_rect.left() if cell_rect.isValid() else rect.right() - 8.0,
        )
        title_w = max(20.0, first_right - 8.0 - title_left)
        if title_w < 72.0 and cell_rect.isValid():
            cell_rect = QRectF()

        return badge_rect, cell_rect

    @staticmethod
    def _fit_text(text: str, width: float, base_font: QFont, min_scale: float = 0.72) -> tuple[QFont, str]:
        """Fits text into `width` without ever drawing an ellipsis.

        The font shrinks in small steps down to `min_scale`. If the text still
        does not fit, whole trailing words are dropped (a lone oversized word is
        trimmed by characters), so nothing is shown cut mid-word with dots.
        """
        text = str(text or "")
        limit = max(1, int(width))
        font = QFont(base_font)
        use_point = base_font.pointSizeF() > 0
        base_size = base_font.pointSizeF() if use_point else float(max(1, base_font.pixelSize()))
        scale = 1.0
        while QFontMetrics(font).horizontalAdvance(text) > limit and scale > min_scale:
            scale = max(min_scale, scale - 0.06)
            if use_point:
                font.setPointSizeF(base_size * scale)
            else:
                font.setPixelSize(max(1, int(base_size * scale)))
        metrics = QFontMetrics(font)
        if metrics.horizontalAdvance(text) <= limit:
            return font, text
        words = text.split(" ")
        while len(words) > 1 and metrics.horizontalAdvance(" ".join(words)) > limit:
            words.pop()
        out = " ".join(words)
        while len(out) > 1 and metrics.horizontalAdvance(out) > limit:
            out = out[:-1]
        return font, out

    def _preview_chip_labels(self, item: MenuAction) -> list[str]:
        """Returns up to 4 preview labels for MODE_SWITCH and SUBMENU cards."""
        source_items: list = []
        if item.action_type == "MODE_SWITCH" and self.mode_manager is not None:
            try:
                mode = self.mode_manager.get_mode(item.mode_id)
                node = mode.get_root_menu(self.current_language)
                source_items = list(node.items)
            except Exception:
                source_items = []
        elif item.action_type == "SUBMENU" and item.submenu_id in self.menu_tree:
            source_items = list(self.menu_tree[item.submenu_id].items)
        else:
            return []

        labels: list[str] = []
        seen: set[str] = set()
        for child in source_items:
            if child.action_type in ("PAUSE", "BACK", "EXIT"):
                continue
            raw = _clean_action_label(getattr(child, "label", "") or "")
            if not raw:
                continue
            for part in raw.split(" / "):
                part = part.strip()
                if not part:
                    continue
                part = _soften_caps(part)
                key = part.lower()
                if key in seen:
                    continue
                seen.add(key)
                labels.append(part)
                if len(labels) >= 4:
                    return labels
        return labels

    def _paint_preview_chips(
        self,
        painter: QPainter,
        card_rect: QRectF,
        chip_labels: list[str],
    ) -> None:
        """Paints small preview chips under the card header band."""
        if not chip_labels:
            return
        fm = QFontMetrics(self._font_card_subtitle)
        chip_h = 18.0
        gap = 4.0
        radius = RADIUS_S
        start_x = card_rect.x() + 12.0
        y = card_rect.y() + 58.0
        max_right = card_rect.right() - 12.0

        painter.setFont(self._font_card_subtitle)
        for label in chip_labels:
            # Only whole labels are drawn: a chip that does not fit is dropped,
            # never cut mid-word with an ellipsis.
            text = str(label)
            text_w = fm.horizontalAdvance(text)
            chip_w = float(text_w) + 12.0
            if start_x + chip_w > max_right:
                break
            chip_rect = QRectF(start_x, y, chip_w, chip_h)
            painter.setBrush(QColor(30, 41, 59, 255))
            painter.setPen(QPen(QColor(71, 85, 105, 255), 1.0))
            painter.drawRoundedRect(chip_rect, radius, radius)
            painter.setPen(QColor(241, 245, 249))
            painter.drawText(chip_rect, Qt.AlignmentFlag.AlignCenter, text)
            start_x += chip_w + gap

    def _apply_win32_no_activate(self) -> None:
        """Applies WS_EX_NOACTIVATE and WS_EX_TRANSPARENT styles on Windows to guarantee zero focus stealing."""
        try:
            import ctypes
            GWL_EXSTYLE = -20
            WS_EX_NOACTIVATE = 0x08000000
            WS_EX_TOPMOST = 0x00000008
            WS_EX_TRANSPARENT = 0x00000020
            hwnd = int(self.winId())
            if hwnd:
                ex_style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                ctypes.windll.user32.SetWindowLongW(
                    hwnd, GWL_EXSTYLE, ex_style | WS_EX_NOACTIVATE | WS_EX_TOPMOST | WS_EX_TRANSPARENT
                )
        except Exception:
            pass
