"""Paint steps: gaze-scroll indicators and help modal."""

from ideye.ui.overlay_common import *  # noqa: F401,F403


class OverlayPaintModalsMixin:
    """Paint steps: gaze-scroll indicators and help modal."""

    def _paint_gaze_scroll_indicators(self, painter: QPainter, w: float, h: float) -> None:
        """Draws subtle top/bottom velocity indicators while gaze scroll is active."""
        if not getattr(self, "_gaze_scroll_enabled", False):
            return
        try:
            speed = float(self.gaze_scroller.speed())
        except Exception:
            return
        if abs(speed) < 0.01:
            return
        intensity = min(1.0, abs(speed) / max(1e-6, self.gaze_scroller.max_scroll_rate))
        color = QColor(getattr(self, "theme_color", "#22d3ee"))
        color.setAlpha(int(45 + 150 * intensity))
        painter.save()
        painter.setPen(QPen(color, 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        cx = w * 0.5
        span = 26.0
        if speed > 0:
            y = h - 54.0
            painter.drawLine(QPointF(cx - span, y - 8.0), QPointF(cx, y))
            painter.drawLine(QPointF(cx, y), QPointF(cx + span, y - 8.0))
            painter.drawLine(QPointF(cx, y + 10.0), QPointF(cx, y + 2.0))
        else:
            y = 54.0
            painter.drawLine(QPointF(cx - span, y + 8.0), QPointF(cx, y))
            painter.drawLine(QPointF(cx, y), QPointF(cx + span, y + 8.0))
            painter.drawLine(QPointF(cx, y - 10.0), QPointF(cx, y - 2.0))
        painter.restore()

    def _paint_help_modal(self, painter: QPainter, w: float, h: float) -> None:
        """Paints a wrapped, height-fitted gesture and shortcut cheat sheet."""
        painter.fillRect(QRectF(0, 0, w, h), QColor(10, 15, 29, 230))
        layout = self._help_modal_layout(w, h)
        card = layout["card"]
        columns = layout["columns"]
        col_w = layout["col_w"]
        self.help_modal_rect = card

        painter.setBrush(QBrush(QColor(10, 15, 29, 252)))
        painter.setPen(QPen(QColor(59, 130, 246, 200), 1.5))
        painter.drawRoundedRect(card, 12.0, 12.0)
        painter.save()
        painter.setClipRect(card.adjusted(2.0, 2.0, -2.0, -2.0))

        icon_rect = QRectF(card.x() + 24.0, card.y() + 18.0, 28.0, 28.0)
        IconManager.instance().render_icon(painter, "help", icon_rect)
        painter.setFont(self._font_modal_title)
        painter.setPen(QColor(248, 250, 252))
        painter.drawText(
            QRectF(card.x() + 60.0, card.y() + 12.0, card.width() - 84.0, 32.0),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            | Qt.TextFlag.TextWordWrap,
            "GUÍA RÁPIDA DE GESTOS Y ATAJOS",
        )
        painter.setFont(self._font_modal_subtitle)
        painter.setPen(QColor(148, 163, 184))
        painter.drawText(
            QRectF(card.x() + 60.0, card.y() + 44.0, card.width() - 84.0, 30.0),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
            | Qt.TextFlag.TextWordWrap,
            "Control asistivo integral manos libres mediante seguimiento ocular y gestos faciales",
        )
        painter.setPen(QPen(QColor(30, 41, 59, 200), 1.0))
        painter.drawLine(int(card.x() + 24.0), int(card.y() + 76.0),
                         int(card.right() - 24.0), int(card.y() + 76.0))

        # Column 1: gestures.
        gesture_col = columns[0]
        painter.setBrush(QBrush(QColor(15, 23, 42, 210)))
        painter.setPen(QPen(QColor(34, 211, 238, 110), 1.0))
        painter.drawRoundedRect(gesture_col, 8.0, 8.0)
        painter.setFont(self._font_modal_section)
        painter.setPen(QColor(96, 165, 250))
        painter.drawText(
            QRectF(gesture_col.x() + 14.0, gesture_col.y() + 8.0, col_w - 28.0, 22.0),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            "GESTOS FACIALES Y OCULARES",
        )
        y = gesture_col.y() + 36.0
        for title, action, desc, title_h, action_h, desc_h, row_h in layout["gesture_rows"]:
            painter.setFont(self._font_modal_item_title)
            painter.setPen(QColor(253, 224, 71))
            painter.drawText(
                QRectF(gesture_col.x() + 14.0, y, col_w - 28.0, title_h),
                Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap, title)
            painter.setFont(self._font_modal_item_desc)
            painter.setPen(QColor(52, 211, 153))
            painter.drawText(
                QRectF(gesture_col.x() + 14.0, y + title_h, col_w - 28.0, action_h),
                Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap, f"• {action}")
            painter.setPen(QColor(148, 163, 184))
            painter.drawText(
                QRectF(gesture_col.x() + 14.0, y + title_h + action_h,
                       col_w - 28.0, max(14.0, desc_h)),
                Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap, desc)
            y += row_h

        # Columns 2-3: shortcuts split evenly, each row wrapped.
        shortcut_titles = ("ATAJOS DE TECLADO", "MÁS ATAJOS")
        for col_index, (rows, _total) in enumerate(layout["shortcut_columns"], start=1):
            column = columns[col_index]
            painter.setBrush(QBrush(QColor(15, 23, 42, 210)))
            painter.setPen(QPen(QColor(30, 41, 59, 200), 1.0))
            painter.drawRoundedRect(column, 8.0, 8.0)
            painter.setFont(self._font_modal_section)
            painter.setPen(QColor(148, 163, 184))
            painter.drawText(
                QRectF(column.x() + 14.0, column.y() + 8.0, col_w - 28.0, 22.0),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                shortcut_titles[col_index - 1],
            )
            row_y = column.y() + 36.0
            for key, name, desc, desc_h, row_h in rows:
                painter.setFont(self._font_modal_item_title)
                painter.setPen(QColor(248, 113, 113))
                painter.drawText(
                    QRectF(column.x() + 14.0, row_y, col_w - 28.0, 16.0),
                    Qt.AlignmentFlag.AlignLeft,
                    QFontMetrics(self._font_modal_item_title).elidedText(
                        key, Qt.TextElideMode.ElideRight, int(col_w - 28.0)),
                )
                painter.setPen(QColor(241, 245, 249))
                painter.drawText(
                    QRectF(column.x() + 14.0, row_y + 16.0, col_w - 28.0, 16.0),
                    Qt.AlignmentFlag.AlignLeft,
                    QFontMetrics(self._font_modal_item_title).elidedText(
                        name, Qt.TextElideMode.ElideRight, int(col_w - 28.0)),
                )
                painter.setFont(self._font_modal_item_desc)
                painter.setPen(QColor(148, 163, 184))
                painter.drawText(
                    QRectF(column.x() + 14.0, row_y + 32.0,
                           col_w - 28.0, max(14.0, desc_h)),
                    Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap, desc)
                row_y += row_h

        painter.restore()

        self._update_help_modal_rect()
        if getattr(self, "hovered_help_modal_guide", False):
            painter.setBrush(QBrush(QColor(14, 116, 144, 100)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(self.help_modal_guide_rect.adjusted(-4.0, -4.0, 4.0, 4.0), 10.0, 10.0)
            guide_brush = QBrush(QColor(29, 78, 216, 245))
            guide_pen = QPen(QColor(207, 250, 254), 2.0)
        else:
            guide_brush = QBrush(QColor(30, 41, 59, 220))
            guide_pen = QPen(QColor(59, 130, 246, 160), 1.0)
        painter.setBrush(guide_brush)
        painter.setPen(guide_pen)
        painter.drawRoundedRect(self.help_modal_guide_rect, 8.0, 8.0)
        painter.setFont(self._font_modal_close)
        painter.setPen(QColor(245, 243, 255))
        painter.drawText(
            self.help_modal_guide_rect,
            Qt.AlignmentFlag.AlignCenter,
            " ABRIR MANUAL INTERACTIVO",
        )

        if getattr(self, "hovered_help_modal_tutorial", False):
            painter.setBrush(QBrush(QColor(14, 116, 144, 100)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(self.help_modal_tutorial_rect.adjusted(-4.0, -4.0, 4.0, 4.0), 10.0, 10.0)
            tut_brush = QBrush(QColor(14, 116, 144, 245))
            tut_pen = QPen(QColor(207, 250, 254), 2.0)
        else:
            tut_brush = QBrush(QColor(30, 41, 59, 220))
            tut_pen = QPen(QColor(59, 130, 246, 160), 1.0)
        painter.setBrush(tut_brush)
        painter.setPen(tut_pen)
        painter.drawRoundedRect(self.help_modal_tutorial_rect, 8.0, 8.0)
        painter.setFont(self._font_modal_close)
        painter.setPen(QColor(240, 249, 255))
        painter.drawText(
            self.help_modal_tutorial_rect,
            Qt.AlignmentFlag.AlignCenter,
            "INICIAR TUTORIAL (F2)",
        )

        if getattr(self, "hovered_help_modal_close", False):
            painter.setBrush(QBrush(QColor(16, 185, 129, 70)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(self.help_modal_close_rect.adjusted(-4.0, -4.0, 4.0, 4.0), 10.0, 10.0)
            close_brush = QBrush(QColor(16, 185, 129, 245))
            close_pen = QPen(QColor(209, 250, 229), 2.0)
        else:
            close_brush = QBrush(QColor(6, 78, 59, 220))
            close_pen = QPen(QColor(16, 185, 129, 180), 1.0)
        painter.setBrush(close_brush)
        painter.setPen(close_pen)
        painter.drawRoundedRect(self.help_modal_close_rect, 8.0, 8.0)
        painter.setFont(self._font_modal_close)
        painter.setPen(QColor(236, 253, 245))
        painter.drawText(
            self.help_modal_close_rect,
            Qt.AlignmentFlag.AlignCenter,
            "CERRAR GUÍA (Mire aquí o abra la boca)",
        )
