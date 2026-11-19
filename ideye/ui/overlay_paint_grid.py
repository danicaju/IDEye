"""Paint steps: mode banner, status badges, grid cards and overlays."""

from ideye.ui.overlay_common import *  # noqa: F401,F403
from ideye.ui.overlay_common import (  # noqa: F401
    _CHIP_BAND_EXTRA,
    _clean_action_label,
    _menu_card_label,
    _soften_caps,
)


class OverlayPaintGridMixin:
    """Paint steps: mode banner, status badges, grid cards and overlays."""

    def _paint_mode_banner(self, header_rect, margin, painter):
        # =====================================================================
        # 1b. Transient mode-change banner (makes coding/writing switch obvious)
        # =====================================================================
        try:
            now = time.time()
            if (
                self._mode_banner_text
                and now < self._mode_banner_until
                and self.current_context_mode_id != "sniper"
            ):
                duration = max(0.1, self._mode_banner_until - self._mode_banner_start)
                progress = (now - self._mode_banner_start) / duration
                progress = max(0.0, min(1.0, progress))
                if progress < 0.18:
                    alpha_factor = progress / 0.18
                elif progress > 0.78:
                    alpha_factor = (1.0 - progress) / 0.22
                else:
                    alpha_factor = 1.0
                alpha_factor = max(0.0, min(1.0, alpha_factor))
                if self.reduced_motion:
                    alpha_factor = 1.0
                    slide = 0.0
                else:
                    slide = (1.0 - min(1.0, progress / 0.18)) * 18.0 if progress < 0.18 else 0.0

                banner_w = min(float(self.width()) - 2.0 * margin, 420.0)
                banner_rect = QRectF(
                    (float(self.width()) - banner_w) * 0.5,
                    header_rect.bottom() + 10.0 + slide,
                    banner_w,
                    42.0,
                )
                painter.save()
                painter.setOpacity(alpha_factor)
                painter.setBrush(QBrush(QColor(10, 15, 29, 240)))
                painter.setPen(QPen(QColor(self.theme_color or ACCENT_HEX), 1.5))
                painter.drawRoundedRect(banner_rect, RADIUS_L, RADIUS_L)
                painter.setPen(QColor(248, 250, 252))
                banner_font, banner_text = self._fit_text(
                    self._mode_banner_text, banner_rect.width() - 24.0, self._font_header_bold_btn
                )
                painter.setFont(banner_font)
                painter.drawText(banner_rect, Qt.AlignmentFlag.AlignCenter, banner_text)
                painter.restore()
        except Exception:
            pass

    def _paint_status_badges(self, header_rect, painter, w):
        # =====================================================================
        # Live diagnostics badge (amber/coral, non-blocking).
        if self._active_diagnostics and not self.reading_mode:
            badge = self.diagnostics_fixer.badge_text(self._active_diagnostics)
            fm = QFontMetrics(self._font_header_bold_btn)
            bw = min(560.0, max(300.0, fm.horizontalAdvance(badge) + 30.0))
            self.autofix_badge_rect = QRectF(w * 0.5 - bw * 0.5, header_rect.bottom() + 8.0, bw, 30.0)
            painter.setBrush(QColor(120, 53, 15, 235))
            painter.setPen(QPen(QColor(251, 146, 60, 245), 1.6))
            painter.drawRoundedRect(self.autofix_badge_rect, RADIUS_S, RADIUS_S)
            painter.setPen(QColor(255, 237, 213))
            painter.setFont(self._font_header_bold_btn)
            painter.drawText(self.autofix_badge_rect, Qt.AlignmentFlag.AlignCenter, badge)
        else:
            self.autofix_badge_rect = QRectF()

        # Active game/app profile badge.
        if self._game_profile_name != "default_desktop":
            profile_text = f"PERFIL: {self._game_profile_label}"
            fm_profile = QFontMetrics(self._font_header_bold_btn)
            pw = min(260.0, max(170.0, fm_profile.horizontalAdvance(profile_text) + 24.0))
            self.game_profile_badge_rect = QRectF(header_rect.left() + 8.0, header_rect.bottom() + 8.0, pw, 28.0)
            painter.setBrush(QColor(10, 15, 29, 235))
            painter.setPen(QPen(QColor(59, 130, 246, 230), 1.4))
            painter.drawRoundedRect(self.game_profile_badge_rect, 7.0, 7.0)
            painter.setPen(QColor(207, 250, 254))
            painter.setFont(self._font_header_bold_btn)
            painter.drawText(self.game_profile_badge_rect, Qt.AlignmentFlag.AlignCenter, profile_text)
        else:
            self.game_profile_badge_rect = QRectF()

    def _paint_grid_cards(self, dpr, items, painter):
        # 2. 3x3 Grid Category Cards
        # =====================================================================
        icon_map = {
            "FLOW": "flow",
            "STRUCT": "function",
            "OPERATORS": "operators",
            "NAV": "navigation",
            "PAUSE": "pause_eye",
            "BACK": "arrow_left",
            "EDIT": "edit",
            "FORMAT": "format",
            "AI": "ai_spark",
            "EXIT": "exit",
            "MODE": "mode",
            "SNIPER": "crosshair",
        }

        painter.save()
        card_alpha = self._ghost_card_opacity()
        painter.setOpacity(card_alpha)
        for i in range(9):
            if self.current_context_mode_id == "sniper" and self.current_node_id != "MODE_SELECT":
                continue
            if i >= len(items):
                continue
            item = items[i]
            rect = self.get_block_rect(i)
            is_active_click = (self.active_click_block == i)
            is_hover = (self.hovered_block == i)
            is_reading_center = self.reading_mode and i == 4
            is_active = is_hover or is_active_click or is_reading_center
            cat = self._get_category_for_item(item, i)
            is_danger = cat == "EXIT" or item.action_type == "EXIT"

            # Reading mode keeps only the center resume card readable.
            if self.reading_mode and i != 4:
                body_brush = self._brush_reading_other
                border_pen = self._pen_reading_other
                text_opacity = 0.22
                band_brush = self._brush_band_inactive
            elif is_reading_center:
                body_brush = self._brush_card_active
                border_pen = self._pen_reading_center
                text_opacity = 1.0
                band_brush = self._brush_band_active
            elif is_active:
                body_brush = self._brush_card_active
                border_pen = self._pen_card_danger if is_danger else self._pen_card_active
                text_opacity = 1.0
                band_brush = self._brush_band_active
            else:
                body_brush = self._brush_card_inactive
                border_pen = self._pen_card_inactive
                text_opacity = 1.0
                band_brush = self._brush_band_inactive

            # 1. Transparent body (keeps VS Code readable)
            painter.setOpacity(card_alpha)
            painter.setBrush(body_brush)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(rect, RADIUS_L, RADIUS_L)

            # 2. The focused card is the only element of the grid with a glow:
            #    one soft halo that fades in and out with the focus transition.
            chip_labels = [] if self.reading_mode else self._preview_chip_labels(item)
            halo_weight = self._focus_halo_weight(i, is_active)
            if halo_weight > 0.01 and not self.reading_mode:
                theme = border_pen.color() if is_active else self._pen_card_active.color()
                halo_pen = QPen(
                    QColor(theme.red(), theme.green(), theme.blue(), int(60 * halo_weight)), 3.0
                )
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(halo_pen)
                painter.drawRoundedRect(rect.adjusted(-2.0, -2.0, 2.0, 2.0), RADIUS_L + 2.0, RADIUS_L + 2.0)

            # 3. Hairline frame for idle cards, 2px accent frame for the focused one.
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(border_pen)
            painter.drawRoundedRect(rect, RADIUS_L, RADIUS_L)

            # 4. Solid header band with rounded top corners. When the card has
            #    command chips the band grows to wrap them, so they always sit on
            #    a solid dark surface instead of the desktop behind the HUD.
            band_h = min(52.0 + (_CHIP_BAND_EXTRA if chip_labels else 0.0), rect.height())
            if band_h > 4.0:
                radius = RADIUS_L
                path = QPainterPath()
                path.moveTo(rect.x(), rect.y() + radius)
                path.quadTo(rect.x(), rect.y(), rect.x() + radius, rect.y())
                path.lineTo(rect.right() - radius, rect.y())
                path.quadTo(rect.right(), rect.y(), rect.right(), rect.y() + radius)
                path.lineTo(rect.right(), rect.y() + band_h)
                path.lineTo(rect.x(), rect.y() + band_h)
                path.closeSubpath()
                painter.setBrush(band_brush)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawPath(path)

            # Content (dimmed for inactive cards)
            painter.save()
            painter.setOpacity(text_opacity * card_alpha)

            number = i + 1
            number_rect = QRectF(rect.x() + 10.0, rect.y() + 8.0, 24.0, 24.0)
            painter.setBrush(self._brush_badge_theme if is_active else self._brush_badge_inactive)
            painter.setPen(self._pen_badge_theme if is_active else self._pen_badge_active)
            painter.drawRoundedRect(number_rect, RADIUS_S, RADIUS_S)
            painter.setPen(self._color_theme_text if is_active else self._color_card_text_inactive)
            painter.setFont(self._font_card_number)
            painter.drawText(number_rect, Qt.AlignmentFlag.AlignCenter, str(number))

            # Card activation progress indicator (top-left badge)
            # Only visible when the user actively attempts to access the cell/mode:
            # - Intentional facial confirmation (mouth opening / MAR towards threshold)
            # - Intentional dwell auto-click (if dwell_click_enabled is explicitly active)
            # - Interactive onboarding tutorial (step 1 gaze fixation)
            activation_progress = 0.0
            if is_active and i != 4:
                # 1. Mouth opening gesture: user deliberately confirming access to this card/mode
                mar_threshold = max(0.01, float(getattr(self, "mar_threshold", 0.35)))
                mar_rest = float(getattr(self, "_mar_rest_baseline", 0.20))
                current_mar = float(getattr(self, "current_mar", 0.0))
                if current_mar > mar_rest + 0.015:
                    mar_ratio = max(0.0, min(1.0, (current_mar - mar_rest) / max(0.01, mar_threshold - mar_rest)))
                    if mar_ratio > 0.08:
                        activation_progress = mar_ratio

                # 2. Dwell-click enabled (accessibility opt-in) or tutorial step 1
                if activation_progress == 0.0:
                    is_tutorial_dwell = bool(getattr(self, "show_tutorial_modal", False) and getattr(self, "tutorial_step", 0) == 1)
                    is_dwell_click_active = bool(getattr(self, "dwell_click_enabled", False))
                    if (is_dwell_click_active or is_tutorial_dwell) and getattr(self, "adaptive_dwell_enabled", True):
                        activation_progress = float(getattr(self, "_dwell_progress", 0.0))

            if activation_progress > 0.0:
                dwell_rect = number_rect.adjusted(-3.0, -3.0, 3.0, 3.0)
                theme_accent = QColor(self.theme_color or ACCENT_HEX)
                dwell_pen = QPen(QColor(theme_accent.red(), theme_accent.green(), theme_accent.blue(), 230), 2.5)
                if is_danger:
                    dwell_pen.setColor(QColor(239, 68, 68, 230))
                painter.setPen(dwell_pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                span_angle = int(-activation_progress * 360 * 16)
                painter.drawArc(dwell_rect, 90 * 16, span_angle)

            # Status badge (right side of the band)
            badge_text = ""
            badge_color = self._color_badge_default
            if item.action_type == "MODE_SWITCH":
                badge_text = (
                    "Actual"
                    if item.mode_id == getattr(self, "current_context_mode_id", "")
                    else "Elegir"
                )
                badge_color = self._color_badge_sticky
            elif item.action_type == "SUBMENU":
                # A chevron replaces the old "SUBMENÚ" capsule, freeing width for the title.
                badge_text = ""
                badge_color = self._color_badge_submenu
            elif item.action_type == "BACK":
                badge_text = "Volver"
                badge_color = self._color_badge_back
            elif item.sticky:
                badge_text = "Fijo"
                badge_color = self._color_badge_sticky
            elif is_danger:
                badge_text = "Salir"
                badge_color = self._color_badge_back

            # Status badge + vector icon at the right of the band.
            icon_name = item.icon if item.action_type == "MODE_SWITCH" and item.icon else icon_map.get(cat)
            badge_rect, icon_rect = self._card_header_rects(rect, badge_text, bool(icon_name))
            chevron_rect = QRectF()
            if item.action_type == "SUBMENU":
                chevron_rect = QRectF(rect.right() - 10.0 - 14.0, rect.y() + 19.0, 14.0, 14.0)
                if icon_rect.isValid():
                    icon_rect = icon_rect.translated(-20.0, 0.0)

            if chevron_rect.isValid():
                IconManager.instance().render_icon(
                    painter,
                    "chevron_right",
                    chevron_rect,
                    color=(border_pen.color() if is_active else QColor("#94A3B8")),
                    dpr=dpr,
                )

            if badge_rect.isValid():
                painter.setBrush(self._brush_badge_active if is_active else self._brush_badge_inactive)
                painter.setPen(self._pen_badge_active if is_active else self._pen_btn_idle)
                painter.drawRoundedRect(badge_rect, RADIUS_S, RADIUS_S)
                painter.setPen(badge_color)
                painter.setFont(self._font_status)
                painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, badge_text)

            if icon_rect.isValid() and icon_name:
                IconManager.instance().render_cell_icon(
                    painter,
                    icon_name,
                    icon_rect,
                    icon_size=20.0,
                    color=(border_pen.color() if is_active else QColor("#CBD5E1")),
                    dpr=dpr,
                )

            # Title + subtitle inside the dark band.
            title = _soften_caps(_clean_action_label(_menu_card_label(item)) or item.label)
            subtitle = _soften_caps(item.hint or "")
            if self.reading_mode and i == 4:
                title = "Reanudar"
                subtitle = "Modo lectura. Mira y abre la boca para seguir."

            title_left = rect.x() + 42.0
            first_right = min(
                badge_rect.left() if badge_rect.isValid() else rect.right() - 8.0,
                icon_rect.left() if icon_rect.isValid() else rect.right() - 8.0,
                chevron_rect.left() if chevron_rect.isValid() else rect.right() - 8.0,
            )
            title_right = first_right - 8.0
            title_w = max(20.0, title_right - title_left)
            painter.setPen(self._color_card_text_active if is_active else self._color_card_text_inactive)
            title_font, title_text = self._fit_text(title, title_w, self._font_label)
            painter.setFont(title_font)
            painter.drawText(
                QRectF(title_left, rect.y() + 5.0, title_w, 24.0),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                title_text,
            )

            if subtitle:
                painter.setPen(self._color_card_subtitle if is_active else self._color_card_subtitle_inactive)
                subtitle_font, subtitle_text = self._fit_text(
                    subtitle, title_w, self._font_card_subtitle
                )
                painter.setFont(subtitle_font)
                painter.drawText(
                    QRectF(title_left, rect.y() + 27.0, title_w, 17.0),
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                    subtitle_text,
                )

            if chip_labels:
                self._paint_preview_chips(painter, rect, chip_labels)

            painter.restore()

        painter.restore()

    def _paint_overlays(self, h, painter, w):
        # =====================================================================
        # 3. High-Contrast In-App Gesture & Shortcut Cheat Sheet Modal Card
        # =====================================================================
        if getattr(self, "show_help_modal", False):
            self._paint_help_modal(painter, w, h)

        # =====================================================================
        # 3b. Sniper precision sub-grid (step 2)
        # =====================================================================
        if self.current_context_mode_id == "sniper" and self.current_node_id != "MODE_SELECT":
            self._paint_freelook_overlay(painter)
            self._paint_sniper_lens(painter)

        # =====================================================================
        # 4. Refined High-Visibility Dual-Ring Reticle with Glow Aura
        # =====================================================================
        self._paint_gaze_scroll_indicators(painter, w, h)
        if not self.reading_mode or self.hovered_block == 4:
            painter.setOpacity(0.95 if not self.reading_mode else 0.85)
            gx, gy = self.current_gaze
            cx = gx * w
            cy = gy * h
            threshold = max(0.01, float(getattr(self, "mar_threshold", 0.55)))
            ratio = max(0.0, min(1.0, float(getattr(self, "current_mar", 0.0)) / threshold))
            ring_r = 11.0 - 2.0 * ratio
            center = QPointF(cx, cy)

            # Soft glow, thin ring, and a 6px center point.
            painter.setBrush(self._brush_pointer_glow)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(center, ring_r + 7.0, ring_r + 7.0)

            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(self._pen_pointer_ring)
            painter.drawEllipse(center, ring_r, ring_r)

            # MAR progress arc closes around the ring as the mouth opens.
            if ratio > 0.005:
                progress_color = (
                    self._color_progress_warm if ratio >= 0.72 else self._color_progress_cool
                )
                self._pen_pointer_progress.setColor(progress_color)
                painter.setPen(self._pen_pointer_progress)
                arc_rect = QRectF(cx - ring_r, cy - ring_r, ring_r * 2.0, ring_r * 2.0)
                painter.drawArc(arc_rect, 90 * 16, -int(360 * 16 * ratio))

            painter.setBrush(self._brush_pointer_dot)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(center, 3.0, 3.0)

        # 5. Interactive 3-step onboarding mini-tutorial modal
        if getattr(self, "show_tutorial_modal", False):
            self._paint_tutorial_modal(painter, w, h)
