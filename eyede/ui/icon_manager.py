"""
EyeDE - Vector Icon Manager
Pre-loads, caches, and renders neon/glassmorphic SVG icons using QSvgRenderer.
Guarantees clean rendering, no memory leaks, and safe fallbacks if files are missing.
"""

import os
from typing import Dict, Optional, Tuple
from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QPainter, QPixmap, QIcon, QColor
from PyQt6.QtSvg import QSvgRenderer

_ICONS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "icons")


class IconManager:
    """
    Singleton-style manager that caches QSvgRenderer instances for EyeDE vector icons.
    """
    _instance: Optional["IconManager"] = None

    def __init__(self, icons_dir: Optional[str] = None):
        self.icons_dir = icons_dir or _ICONS_DIR
        self._renderers: Dict[str, QSvgRenderer] = {}
        self._pixmap_cache: Dict[Tuple[str, int, int], QPixmap] = {}
        self._load_available_icons()

    @classmethod
    def instance(cls) -> "IconManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _load_available_icons(self) -> None:
        """Loads and pre-parses SVG files in the icons directory."""
        if not os.path.isdir(self.icons_dir):
            return
        for fname in os.listdir(self.icons_dir):
            if fname.lower().endswith(".svg"):
                key = fname[:-4].lower()
                full_path = os.path.join(self.icons_dir, fname)
                renderer = QSvgRenderer(full_path)
                if renderer.isValid():
                    self._renderers[key] = renderer

    @classmethod
    def has_icon(cls, name: str) -> bool:
        """Checks if a named icon exists and is valid."""
        return name.lower() in cls.instance()._renderers

    @classmethod
    def get_app_pixmap(cls, width: int = 32, height: int = 32) -> QPixmap:
        """Returns a cached QPixmap of the application icon scaled to (width, height)."""
        inst = cls.instance()
        cache_key = ("__app_icon__", width, height)
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
                        width,
                        height,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    inst._pixmap_cache[cache_key] = scaled
                    return scaled

        # Fallback to SVG pixmap
        return cls.get_pixmap("eyede_logo", width, height)

    @classmethod
    def render_icon(
        cls,
        painter: QPainter,
        icon_name: str,
        target_rect: QRectF,
    ) -> bool:
        """
        Renders the SVG or raster icon into the target QRectF using the active QPainter.
        Returns True if rendered, False if icon was not found.
        """
        inst = cls.instance()
        if icon_name.lower() in ("eyede_logo", "app_icon"):
            pix = cls.get_app_pixmap(int(target_rect.width()), int(target_rect.height()))
            if not pix.isNull():
                painter.drawPixmap(target_rect.toRect(), pix)
                return True

        renderer = inst._renderers.get(icon_name.lower())
        if renderer is not None and renderer.isValid():
            renderer.render(painter, target_rect)
            return True
        return False

    @classmethod
    def get_pixmap(cls, icon_name: str, width: int = 32, height: int = 32) -> QPixmap:
        """
        Returns a rasterized QPixmap of the requested SVG at specified dimensions.
        Cached for optimal performance. Returns a transparent fallback if icon not found.
        """
        inst = cls.instance()
        cache_key = (icon_name.lower(), width, height)
        if cache_key in inst._pixmap_cache:
            return inst._pixmap_cache[cache_key]

        renderer = inst._renderers.get(icon_name.lower())
        pixmap = QPixmap(width, height)
        pixmap.fill(Qt.GlobalColor.transparent)
        if renderer is not None and renderer.isValid():
            p = QPainter(pixmap)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            renderer.render(p)
            p.end()

        inst._pixmap_cache[cache_key] = pixmap
        return pixmap

    @classmethod
    def get_icon(cls, icon_name: str, size: int = 32) -> QIcon:
        """Returns a QIcon for buttons, tray, and window titles."""
        pixmap = cls.get_pixmap(icon_name, size, size)
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
