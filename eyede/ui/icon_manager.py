"""
IDEye - Vector Icon Manager (Phase 6.6)
Pre-loads, caches, and renders neon/glassmorphic SVG icons using QSvgRenderer.
High-DPI aware, tintable via currentColor replacement, and safe fallbacks.
"""

import os
import re
from typing import Dict, Optional, Tuple, Union

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QPainter, QPixmap, QIcon, QColor
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QApplication

_ICONS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "icons")


def _normalize_color(color: Union[QColor, str, None]) -> str:
    """Returns a #RRGGBB hex string for a QColor or color name."""
    if color is None:
        return "#E2E8F0"
    if isinstance(color, str):
        return QColor(color).name() if color else "#E2E8F0"
    return color.name()


class IconManager:
    """
    Singleton-style manager that caches vector icon paths and tinted renderers.
    """
    _instance: Optional["IconManager"] = None

    def __init__(self, icons_dir: Optional[str] = None):
        self.icons_dir = icons_dir or _ICONS_DIR
        self._icon_paths: Dict[str, str] = {}
        self._renderers: Dict[Tuple[str, str], QSvgRenderer] = {}
        self._pixmap_cache: Dict[Tuple[str, int, int, str, int], QPixmap] = {}
        self._load_available_icons()

    @classmethod
    def instance(cls) -> "IconManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _load_available_icons(self) -> None:
        """Loads SVG file paths in the icons directory keyed by lowercase name."""
        if not os.path.isdir(self.icons_dir):
            return
        for fname in os.listdir(self.icons_dir):
            if fname.lower().endswith(".svg"):
                key = fname[:-4].lower()
                full_path = os.path.join(self.icons_dir, fname)
                self._icon_paths[key] = full_path

    @classmethod
    def has_icon(cls, name: str) -> bool:
        """Checks if a named icon exists and is valid."""
        return name.lower() in cls.instance()._icon_paths

    @classmethod
    def _apply_current_color(cls, svg_bytes: bytes, color_hex: str) -> bytes:
        """Replaces currentColor with the requested hex (QSvgRenderer ignores QPen)."""
        hex_clean = color_hex.lstrip("#")
        if len(hex_clean) == 3:
            hex_clean = "".join(c * 2 for c in hex_clean)
        replacement = f"#{hex_clean}"
        return svg_bytes.replace(b"currentColor", replacement.encode("ascii"))

    @classmethod
    def _renderer_for(cls, name: str, color_hex: str) -> Optional[QSvgRenderer]:
        inst = cls.instance()
        key = (name.lower(), color_hex)
        renderer = inst._renderers.get(key)
        if renderer is not None and renderer.isValid():
            return renderer
        path = inst._icon_paths.get(name.lower())
        if not path or not os.path.isfile(path):
            return None
        try:
            with open(path, "rb") as f:
                svg_bytes = f.read()
        except Exception:
            return None
        tinted = cls._apply_current_color(svg_bytes, color_hex)
        renderer = QSvgRenderer(tinted)
        if renderer.isValid():
            inst._renderers[key] = renderer
            return renderer
        return None

    @classmethod
    def get_app_pixmap(
        cls, width: int = 32, height: int = 32, dpr: Optional[float] = None
    ) -> QPixmap:
        """Returns a cached QPixmap of the application icon scaled to (width, height)."""
        inst = cls.instance()
        dpr = max(1.0, dpr or cls._primary_dpr())
        cache_key = ("__app_icon__", width, height, "", round(dpr * 100))
        if cache_key in inst._pixmap_cache:
            return inst._pixmap_cache[cache_key]

        candidate_paths = [
            os.path.join(inst.icons_dir, "app_icon_rounded.png"),
            os.path.join(inst.icons_dir, "app_icon.png"),
            os.path.join(inst.icons_dir, "eyede.ico"),
        ]
        for p in candidate_paths:
            if os.path.isfile(p):
                base_pix = QPixmap(p)
                if not base_pix.isNull():
                    scaled = base_pix.scaled(
                        round(width * dpr),
                        round(height * dpr),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    scaled.setDevicePixelRatio(dpr)
                    inst._pixmap_cache[cache_key] = scaled
                    return scaled

        # Fallback to SVG pixmap
        return cls.get_pixmap("eyede_logo", width, height, dpr=dpr)

    @classmethod
    def _primary_dpr(cls) -> float:
        screen = QApplication.primaryScreen()
        return float(screen.devicePixelRatio()) if screen else 1.0

    @classmethod
    def render_icon(
        cls,
        painter: QPainter,
        icon_name: str,
        target_rect: QRectF,
        *,
        color: Union[QColor, str, None] = None,
        dpr: Optional[float] = None,
    ) -> bool:
        """
        Renders the SVG or raster icon into the target QRectF using the active QPainter.
        Returns True if rendered, False if icon was not found.
        """
        inst = cls.instance()
        if icon_name.lower() in ("eyede_logo", "app_icon"):
            pix = cls.get_app_pixmap(
                int(target_rect.width()), int(target_rect.height()), dpr=dpr
            )
            if not pix.isNull():
                painter.drawPixmap(target_rect.toRect(), pix)
                return True
            return False

        color_hex = _normalize_color(color)
        dpr = max(1.0, dpr or cls._primary_dpr())
        width = max(1, round(target_rect.width() * dpr))
        height = max(1, round(target_rect.height() * dpr))
        cache_key = (icon_name.lower(), width, height, color_hex, round(dpr * 100))
        if cache_key in inst._pixmap_cache:
            pix = inst._pixmap_cache[cache_key]
        else:
            renderer = cls._renderer_for(icon_name, color_hex)
            pix = QPixmap(width, height)
            pix.fill(Qt.GlobalColor.transparent)
            pix.setDevicePixelRatio(dpr)
            if renderer is not None and renderer.isValid():
                p = QPainter(pix)
                p.setRenderHint(QPainter.RenderHint.Antialiasing)
                p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
                renderer.render(p, QRectF(0, 0, target_rect.width(), target_rect.height()))
                p.end()
            inst._pixmap_cache[cache_key] = pix

        if not pix.isNull():
            painter.drawPixmap(target_rect.toRect(), pix)
            return True
        return False

    @classmethod
    def render_cell_icon(
        cls,
        painter: QPainter,
        icon_name: str,
        cell_rect: QRectF,
        *,
        icon_size: float = 20.0,
        color: Union[QColor, str, None] = None,
        dpr: Optional[float] = None,
    ) -> bool:
        """Renders a 28x28 rounded cell background with a centered icon."""
        if not cell_rect.isValid():
            return False
        painter.save()
        # Subtle rounded background
        painter.setBrush(QColor(255, 255, 255, 12))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(cell_rect, 7.0, 7.0)

        cx = cell_rect.x() + (cell_rect.width() - icon_size) * 0.5
        cy = cell_rect.y() + (cell_rect.height() - icon_size) * 0.5
        icon_rect = QRectF(cx, cy, icon_size, icon_size)
        result = cls.render_icon(painter, icon_name, icon_rect, color=color, dpr=dpr)
        painter.restore()
        return result

    @classmethod
    def get_pixmap(
        cls,
        icon_name: str,
        width: int = 32,
        height: int = 32,
        color: Union[QColor, str, None] = None,
        dpr: Optional[float] = None,
    ) -> QPixmap:
        """
        Returns a rasterized QPixmap of the requested SVG at specified dimensions.
        Cached for optimal performance. Returns a transparent fallback if icon not found.
        """
        inst = cls.instance()
        color_hex = _normalize_color(color)
        dpr = max(1.0, dpr or cls._primary_dpr())
        target_w = max(1, round(width * dpr))
        target_h = max(1, round(height * dpr))
        cache_key = (icon_name.lower(), target_w, target_h, color_hex, round(dpr * 100))
        if cache_key in inst._pixmap_cache:
            return inst._pixmap_cache[cache_key]

        renderer = cls._renderer_for(icon_name, color_hex)
        pixmap = QPixmap(target_w, target_h)
        pixmap.fill(Qt.GlobalColor.transparent)
        pixmap.setDevicePixelRatio(dpr)
        if renderer is not None and renderer.isValid():
            p = QPainter(pixmap)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            # QPainter on a DPR-scaled pixmap uses logical coordinates.
            renderer.render(p, QRectF(0, 0, width, height))
            p.end()

        inst._pixmap_cache[cache_key] = pixmap
        return pixmap

    @classmethod
    def get_icon(
        cls,
        icon_name: str,
        size: int = 32,
        color: Union[QColor, str, None] = None,
        dpr: Optional[float] = None,
    ) -> QIcon:
        """Returns a QIcon for buttons, tray, and window titles."""
        pixmap = cls.get_pixmap(icon_name, size, size, color=color, dpr=dpr)
        if pixmap is not None and not pixmap.isNull():
            return QIcon(pixmap)
        return QIcon()

    @classmethod
    def get_app_icon(cls) -> QIcon:
        """
        Returns the primary application icon (from eyede.ico, app_icon_rounded.png, or app_icon.png).
        Used across windows, taskbar, system tray, and dialogs.
        """
        inst = cls.instance()
        # 1. Try eyede.ico (in assets/icons or project root)
        candidate_paths = [
            os.path.join(inst.icons_dir, "eyede.ico"),
            os.path.join(os.path.dirname(inst.icons_dir), "eyede.ico"),
            os.path.join(os.path.dirname(os.path.dirname(inst.icons_dir)), "eyede.ico"),
            os.path.join(inst.icons_dir, "app_icon_rounded.png"),
            os.path.join(inst.icons_dir, "app_icon.png"),
        ]
        for path in candidate_paths:
            if os.path.isfile(path):
                icon = QIcon(path)
                if not icon.isNull():
                    return icon

        # 2. Fallback to SVG logo
        svg_icon = cls.get_icon("eyede_logo", 128)
        if not svg_icon.isNull():
            return svg_icon

        return QIcon()
