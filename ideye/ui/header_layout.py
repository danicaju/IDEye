"""Pure geometry for the IDEye floating command bar.

Keeping this math outside ``OverlayWindow`` makes the header layout testable
without constructing a QWidget or relying on font rendering.
"""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import QRectF


@dataclass(frozen=True)
class HeaderLayoutRects:
    header: QRectF
    logo: QRectF
    status: QRectF
    exit: QRectF
    help: QRectF
    lang: QRectF
    mode: QRectF
    last_action: QRectF
    sniper_action: QRectF
    screen: QRectF
    breadcrumb: QRectF
    exit_w: float
    help_w: float
    lang_w: float
    mode_w: float
    ws_dot_only: bool
    ws_show: bool


class HeaderLayout:
    """Computes all header hit targets from width and display state."""

    @staticmethod
    def compute(
        width: float,
        margin: float,
        header_height: float,
        right_margin: float,
        grid_left: float,
        show_last_action: bool,
        screen_count: int,
        mode_id: str,
        brand_text_width: float,
        ws_full_width: float,
        logo_size: float = 24.0,
    ) -> HeaderLayoutRects:
        w = float(width) if width > 0 else 1920.0
        margin = float(margin)
        header_h = float(header_height)
        pill_h = max(24.0, header_h - 12.0)
        right_margin = float(right_margin)
        grid_left = float(grid_left)
        grid_right = w - margin - right_margin
        area_w = max(1.0, grid_right - grid_left)
        bar_w = max(1.0, min(1020.0, area_w))
        bar_x = grid_left + (area_w - bar_w) * 0.5

        if bar_w >= 900.0:
            exit_w = max(150.0, min(160.0, bar_w * 0.12))
            help_w = max(130.0, min(140.0, bar_w * 0.10))
        else:
            exit_w = max(104.0, min(120.0, bar_w * 0.14))
            help_w = max(100.0, min(112.0, bar_w * 0.10))
        lang_w = max(56.0, min(64.0, bar_w * 0.07))
        mode_w = max(140.0, min(200.0, bar_w * 0.26))

        header = QRectF(bar_x, margin, bar_w, header_h)
        inner = 8.0
        gap = 6.0

        exit_rect = QRectF(header.right() - inner - exit_w, header.y() + 6.0, exit_w, pill_h)
        help_rect = QRectF(exit_rect.left() - gap - help_w, header.y() + 6.0, help_w, pill_h)

        show_screen = int(screen_count) > 1 and mode_id != "sniper"
        show_last = bool(show_last_action) or show_screen
        last_w = min(170.0, max(70.0, bar_w * 0.22))
        right_block = mode_w + lang_w + help_w + exit_w + 3.0 * gap
        if show_last:
            right_block += last_w + gap

        brand_w = float(brand_text_width) + 2.0
        ws_dot = 6.0
        ws_min_w = ws_dot
        brand_min = 24.0 + 8.0 + brand_w + 10.0 + ws_min_w

        if right_block + brand_min + 12.0 > bar_w:
            last_w = max(70.0, last_w - 40.0)
            if show_last:
                right_block = mode_w + lang_w + help_w + exit_w + 3.0 * gap + last_w + gap
        if show_last and right_block + brand_min + 12.0 > bar_w:
            show_last = False
            right_block = mode_w + lang_w + help_w + exit_w + 3.0 * gap
        if right_block + brand_min + 12.0 > bar_w:
            mode_w = max(120.0, min(mode_w, bar_w - right_block + mode_w - brand_min - 12.0))

        if show_last and show_screen:
            screen_rect = QRectF(help_rect.left() - gap - last_w, header.y() + 6.0, last_w, pill_h)
            last_rect = QRectF()
        elif show_last:
            screen_rect = QRectF()
            last_rect = QRectF(help_rect.left() - gap - last_w, header.y() + 6.0, last_w, pill_h)
        else:
            screen_rect = QRectF()
            last_rect = QRectF()

        if mode_id == "sniper":
            sniper_w = min(170.0, max(130.0, last_w))
            sniper_rect = QRectF(help_rect.left() - gap - sniper_w, header.y() + 6.0, sniper_w, pill_h)
            last_rect = QRectF()
        else:
            sniper_rect = QRectF()

        if mode_id == "sniper" or not show_last:
            screen_rect = QRectF()

        selector_rect = sniper_rect if sniper_rect.isValid() else last_rect
        lang_left = (
            selector_rect.left() - gap - lang_w
            if selector_rect.isValid()
            else help_rect.left() - gap - lang_w
        )
        lang_rect = QRectF(lang_left, header.y() + 6.0, lang_w, pill_h)
        mode_rect = QRectF(lang_rect.left() - gap - mode_w, header.y() + 6.0, mode_w, pill_h)

        logo_rect = QRectF(
            header.x() + inner,
            header.y() + (header_h - logo_size) * 0.5,
            logo_size,
            logo_size,
        )
        status_left = logo_rect.right() + 8.0
        status_right = mode_rect.left() - gap
        status_w = max(0.0, status_right - status_left)
        status_rect = QRectF(status_left, header.y() + 6.0, status_w, pill_h)
        ws_dot_only = status_w < float(ws_full_width) + 4.0
        ws_show = status_w >= ws_min_w + 4.0

        return HeaderLayoutRects(
            header=header,
            logo=logo_rect,
            status=status_rect,
            exit=exit_rect,
            help=help_rect,
            lang=lang_rect,
            mode=mode_rect,
            last_action=last_rect,
            sniper_action=sniper_rect,
            screen=screen_rect,
            breadcrumb=QRectF(),
            exit_w=exit_w,
            help_w=help_w,
            lang_w=lang_w,
            mode_w=mode_w,
            ws_dot_only=ws_dot_only,
            ws_show=ws_show,
        )
