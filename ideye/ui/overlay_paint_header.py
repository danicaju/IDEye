"""Paint entry point, scene setup and header bar."""

from ideye.ui.overlay_common import *  # noqa: F401,F403
from ideye.ui.overlay_common import (  # noqa: F401
    _soften_caps,
)


class OverlayPaintHeaderMixin:
    """Paint entry point, scene setup and header bar."""

    def paintEvent(self, event) -> None:
        """Paints Glassmorphic Breadcrumb Header Bar, 3x3 Category Cards, and Dual-Ring Reticle."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if getattr(self, "_lens_capture_in_progress", False):
            painter.end()
            return
        self._paint_scene(painter, event)
        painter.end()

    def _paint_scene(self, painter, event) -> None:
        """Paints header, grid cards, modals and reticle onto an open painter."""
        h, header_h, items, margin, w = self._paint_setup()
        dpr, header_rect, pill_h = self._paint_header_brand(header_h, painter)
        self._paint_header_buttons(dpr, painter, pill_h)
        self._paint_mode_banner(header_rect, margin, painter)
        self._paint_status_badges(header_rect, painter, w)
        self._paint_grid_cards(dpr, items, painter)
        self._paint_overlays(h, painter, w)

    def _paint_setup(self):
        w = float(self.width())
        h = float(self.height())
        margin = self.margin
        header_h = self.breadcrumb_height

        curr_node = self.current_node
        items = curr_node.items if curr_node else []
        return h, header_h, items, margin, w

    def _paint_header_brand(self, header_h, painter):
        # =====================================================================
        # 1. Top Breadcrumb Bar (Acrylic Glassmorphism)
        # =====================================================================
        self._update_header_exit_rect()
        header_rect = self.header_rect
        pill_h = max(24.0, header_h - 12.0)
        logo_rect = self._header_logo_rect
        last_pill_rect = self._last_action_pill_rect
        sniper_pill_rect = self._sniper_action_pill_rect
        screen_pill_rect = self.header_screen_rect

        painter.setOpacity(0.95 if not self.reading_mode else 0.30)

        dpr = self.devicePixelRatioF() or 1.0

        # Unified floating command bar (Dynamic Island / Linear style)
        painter.setBrush(self._brush_header_bg)
        painter.setPen(self._pen_header_border)
        painter.drawRoundedRect(header_rect, RADIUS_L, RADIUS_L)

        IconManager.instance().render_icon(painter, "ideye_logo", logo_rect, dpr=dpr)

        # Brand + WS status (left side). Clip both to the space before the
        # mode selector so "Local"/"VS Code" can never run under it.
        brand_x = logo_rect.right() + 8.0
        status_right = self.header_mode_rect.left() - 8.0
        available_w = max(0.0, status_right - brand_x)
        painter.setFont(self._font_header_left)
        ws_text = "VS Code" if self._ws_connected else "Local"
        ws_text_w = float(painter.fontMetrics().horizontalAdvance(ws_text))
        show_ws = bool(getattr(self, "_header_ws_show", False)) and available_w > 50.0
        ws_reserve = (11.0 + ws_text_w + 6.0) if show_ws else 0.0
        brand_draw_w = max(0.0, available_w - ws_reserve - 10.0)
        painter.setPen(self._color_card_text_active)
        painter.setFont(self._font_header_bold_btn)
        if brand_draw_w >= 20.0:
            brand_font, brand_text = self._fit_text("IDEye", brand_draw_w, painter.font())
            painter.setFont(brand_font)
            painter.drawText(
                QRectF(brand_x, header_rect.y() + 6.0, brand_draw_w, pill_h),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                brand_text,
            )
        if show_ws:
            ws_x = brand_x + brand_draw_w + 10.0
            if ws_x + 6.0 <= status_right:
                ws_color = QColor(34, 197, 94) if self._ws_connected else QColor(148, 163, 184)
                painter.setBrush(QBrush(ws_color))
                painter.setPen(Qt.PenStyle.NoPen)
                y = header_rect.y() + 6.0 + (pill_h - 6.0) * 0.5
                painter.drawEllipse(QRectF(ws_x, y, 6.0, 6.0))
                if not getattr(self, "_header_ws_dot_only", False):
                    text_w = max(0.0, status_right - (ws_x + 11.0))
                    if text_w > 10.0:
                        painter.setPen(self._pen_header_left)
                        ws_font, ws_fit = self._fit_text(ws_text, text_w, self._font_header_left)
                        painter.setFont(ws_font)
                        painter.drawText(
                            QRectF(ws_x + 11.0, header_rect.y() + 6.0, text_w, pill_h),
                            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                            ws_fit,
                        )

        # Multi-monitor selector.
        if screen_pill_rect.isValid():
            painter.setBrush(self._brush_status_pill)
            painter.setPen(self._pen_status_pill)
            painter.drawRoundedRect(screen_pill_rect, RADIUS_S, RADIUS_S)
            painter.setPen(self._pen_header_right)
            painter.setFont(self._font_header_bold_btn)
            painter.drawText(
                screen_pill_rect,
                Qt.AlignmentFlag.AlignCenter,
                f"Pantalla {self.screen_index + 1}/{self.screen_count}",
            )
        # Sniper action selector, or compact last-action status.
        elif sniper_pill_rect.isValid():
            mode = self._sniper_mode()
            action_label = getattr(mode, "action_label", "Clic Izq") if mode else "Clic Izq"
            painter.setBrush(self._brush_status_pill)
            painter.setPen(self._pen_status_pill)
            painter.drawRoundedRect(sniper_pill_rect, RADIUS_S, RADIUS_S)
            painter.setPen(self._pen_header_right)
            action_font, action_text = self._fit_text(
                f"Ratón: {action_label}",
                max(0.0, sniper_pill_rect.width() - 14.0),
                self._font_header_bold_btn,
            )
            painter.setFont(action_font)
            painter.drawText(sniper_pill_rect, Qt.AlignmentFlag.AlignCenter, action_text)
        elif last_pill_rect.isValid():
            painter.setBrush(self._brush_status_pill)
            painter.setPen(self._pen_status_pill)
            painter.drawRoundedRect(last_pill_rect, RADIUS_S, RADIUS_S)
            painter.setPen(self._pen_header_right)
            status_font, status_text = self._fit_text(
                f"Última: {self.last_action_desc}",
                max(0.0, last_pill_rect.width() - 14.0),
                self._font_header_right,
            )
            painter.setFont(status_font)
            painter.drawText(last_pill_rect, Qt.AlignmentFlag.AlignCenter, status_text)
        return dpr, header_rect, pill_h

    def _paint_header_buttons(self, dpr, painter, pill_h):
        icon_size = 20.0

        # Exit: soft red command button
        if self.active_click_header_exit:
            exit_brush, exit_pen, exit_text_color = self._brush_click, self._pen_click, self._color_click_text
        elif self.hovered_header_exit:
            exit_brush, exit_pen, exit_text_color = QBrush(QColor(239, 68, 68, 230)), QPen(QColor(254, 202, 202), 2.0), QColor(255, 255, 255)
        else:
            exit_brush, exit_pen, exit_text_color = self._brush_exit_idle, self._pen_exit_idle, self._color_exit_text
        painter.setBrush(exit_brush)
        painter.setPen(exit_pen)
        painter.drawRoundedRect(self.header_exit_rect, RADIUS_S, RADIUS_S)
        exit_icon_rect = QRectF(
            self.header_exit_rect.x() + 12.0,
            self.header_exit_rect.y() + (pill_h - icon_size) * 0.5,
            icon_size,
            icon_size,
        )
        IconManager.instance().render_icon(painter, "exit", exit_icon_rect, color="#FCA5A5", dpr=dpr)
        painter.setPen(exit_text_color)
        painter.setFont(self._font_header_bold_btn)
        painter.drawText(
            QRectF(self.header_exit_rect.x() + 34.0, self.header_exit_rect.y(), self.header_exit_rect.width() - 38.0, pill_h),
            Qt.AlignmentFlag.AlignCenter,
            "¿Salir?" if time.time() < self._exit_armed_until else "Salir",
        )

        # Help
        if self.active_click_header_help:
            help_brush, help_pen, help_text_color = self._brush_click, self._pen_click, self._color_click_text
        elif self.hovered_header_help:
            help_brush, help_pen, help_text_color = QBrush(QColor(14, 116, 144, 235)), QPen(QColor(207, 250, 254), 2.0), QColor(255, 255, 255)
        else:
            help_brush, help_pen, help_text_color = self._brush_help_idle, self._pen_help_idle, self._color_help_text
        painter.setBrush(help_brush)
        painter.setPen(help_pen)
        painter.drawRoundedRect(self.header_help_rect, RADIUS_S, RADIUS_S)
        help_vpad = 2.0
        help_icon_rect = QRectF(
            self.header_help_rect.x() + 12.0,
            self.header_help_rect.y() + (pill_h - icon_size) * 0.5,
            icon_size,
            icon_size,
        )
        IconManager.instance().render_icon(painter, "help", help_icon_rect, color="#67E8F9", dpr=dpr)
        painter.setPen(help_text_color)
        painter.setFont(self._font_header_bold_btn)
        painter.drawText(
            QRectF(
                self.header_help_rect.x() + 36.0,
                self.header_help_rect.y() + help_vpad,
                self.header_help_rect.width() - 46.0,
                pill_h - help_vpad * 2.0,
            ),
            Qt.AlignmentFlag.AlignCenter,
            "Ayuda",
        )

        # Mode selector: single interactive button (mode + dropdown hint)
        if self.active_click_header_mode:
            mode_brush, mode_pen, mode_text_color = self._brush_click, self._pen_click, self._color_click_text
        elif self.hovered_header_mode:
            mode_brush, mode_pen, mode_text_color = self._brush_mode_idle, QPen(QColor(ACCENT_HEX), 1.5), QColor(255, 255, 255)
        else:
            mode_brush, mode_pen, mode_text_color = self._brush_mode_idle, self._pen_mode_idle, self._color_mode_text
        painter.setBrush(mode_brush)
        painter.setPen(mode_pen)
        painter.drawRoundedRect(self.header_mode_rect, RADIUS_S, RADIUS_S)
        mode_icon_rect = QRectF(
            self.header_mode_rect.x() + 9.0,
            self.header_mode_rect.y() + (pill_h - 18.0) * 0.5,
            18.0,
            18.0,
        )
        IconManager.instance().render_icon(
            painter, "mode", mode_icon_rect, color=self.theme_color or ACCENT_HEX, dpr=dpr
        )
        # The mode's own color lives only in this 6px dot; everything else is accent.
        painter.setBrush(QBrush(QColor(self.mode_color or ACCENT_HEX)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(
            QRectF(
                self.header_mode_rect.x() + 31.0,
                self.header_mode_rect.y() + (pill_h - 6.0) * 0.5,
                6.0,
                6.0,
            )
        )
        painter.setPen(mode_text_color)
        mode_text_w = max(20.0, self.header_mode_rect.width() - 50.0)
        mode_font, mode_label = self._fit_text(
            f"{_soften_caps(self._short_mode_label())} (V)",
            mode_text_w,
            self._font_header_bold_btn,
        )
        painter.setFont(mode_font)
        painter.drawText(
            QRectF(self.header_mode_rect.x() + 42.0, self.header_mode_rect.y(), mode_text_w, pill_h),
            Qt.AlignmentFlag.AlignCenter,
            mode_label,
        )

        # Language badge [ PY ]
        if self.active_click_header_lang:
            lang_brush, lang_pen, lang_text_color = self._brush_click, self._pen_click, self._color_click_text
        elif self.hovered_header_lang:
            lang_brush, lang_pen, lang_text_color = QBrush(QColor(14, 116, 144, 190)), QPen(QColor(207, 250, 254), 1.6), QColor(255, 255, 255)
        else:
            lang_brush, lang_pen, lang_text_color = self._brush_btn_idle, self._pen_btn_idle, QColor(165, 243, 252)
        painter.setBrush(lang_brush)
        painter.setPen(lang_pen)
        painter.drawRoundedRect(self.header_lang_rect, RADIUS_S, RADIUS_S)
        lang_badge = get_language_badge(self.current_language)
        painter.setPen(lang_text_color)
        painter.setFont(self._font_header_bold_btn)
        painter.drawText(
            self.header_lang_rect,
            Qt.AlignmentFlag.AlignCenter,
            f"[ {lang_badge} ]",
        )
