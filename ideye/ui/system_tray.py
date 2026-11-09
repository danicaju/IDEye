"""Native Windows system tray integration for IDEye (Phase 11)."""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QMenu, QSystemTrayIcon

try:
    from ideye.ui.icon_manager import IconManager
except ImportError:  # pragma: no cover
    from ui.icon_manager import IconManager  # type: ignore


MODE_LABELS = (
    ("coding", "Código"),
    ("writing", "Redacción"),
    ("terminal", "Terminal / Git"),
    ("data_math", "Datos / Mates"),
    ("navigation", "Navegación / Lectura"),
    ("sniper", "FreeLook / Gaming"),
)

POWER_COLORS = {
    "ACTIVE": QColor(59, 130, 246),  # Cyber Sapphire Core (#3b82f6)
    "PAUSED_ECO": QColor(245, 158, 11),
    "AWAY_DEEP_SLEEP": QColor(148, 163, 184),
}


class IDEyeSystemTray(QSystemTrayIcon):
    """System tray icon with mode, pause, ghost-peek and calibration actions."""

    pause_requested = pyqtSignal()
    mode_requested = pyqtSignal(str)
    ghost_peek_toggled = pyqtSignal(bool)
    recalibrate_requested = pyqtSignal()
    guide_requested = pyqtSignal()
    mini_feed_requested = pyqtSignal()
    exit_requested = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._power_state = "ACTIVE"
        self._ghost_action: Optional[QAction] = None
        self._icon_base = IconManager.instance().get_app_icon()
        self._menu = QMenu()
        self._menu.setStyleSheet(
            """
            QMenu {
                background-color: #0a0f1d;
                color: #e2e8f0;
                border: 1px solid #1e293b;
                border-radius: 8px;
                padding: 6px;
            }
            QMenu::item {
                background-color: transparent;
                padding: 6px 24px 6px 12px;
                border-radius: 4px;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 11px;
            }
            QMenu::item:selected {
                background-color: #1d4ed8;
                color: #ffffff;
            }
            QMenu::item:disabled {
                color: #64748b;
                font-weight: bold;
            }
            QMenu::separator {
                height: 1px;
                background-color: #1e293b;
                margin: 4px 8px;
            }
            """
        )
        self._build_menu()
        self.setContextMenu(self._menu)
        self.set_power_state("ACTIVE")

    def _build_menu(self) -> None:
        title = self._menu.addAction("IDEye - Control Ocular")
        title.setEnabled(False)
        self._menu.addSeparator()

        pause = self._menu.addAction("Alternar Pausa / Modo Lectura (Ctrl+Alt+P)")
        pause.triggered.connect(self.pause_requested.emit)

        modes = self._menu.addMenu("Cambiar Modo Activo")
        for mode_id, label in MODE_LABELS:
            action = modes.addAction(label)
            action.triggered.connect(
                lambda _checked=False, mid=mode_id: self.mode_requested.emit(mid)
            )

        self._ghost_action = self._menu.addAction("Activar / Desactivar Ghost-Peek")
        self._ghost_action.setCheckable(True)
        self._ghost_action.setChecked(True)
        self._ghost_action.toggled.connect(self.ghost_peek_toggled.emit)

        self._menu.addSeparator()
        recalibrate = self._menu.addAction("Recalibrar Pantalla y MAR (5+1)")
        recalibrate.triggered.connect(self.recalibrate_requested.emit)

        guide = self._menu.addAction("Abrir Guía Interactiva (Nintendo Booklet)")
        guide.triggered.connect(self.guide_requested.emit)

        mini_feed = self._menu.addAction("Abrir Panel de Control / Mini-Feed (Ctrl+Alt+M)")
        mini_feed.triggered.connect(self.mini_feed_requested.emit)

        self._menu.addSeparator()
        exit_action = self._menu.addAction("Salir de IDEye (Ctrl+Alt+Q)")
        exit_action.triggered.connect(self.exit_requested.emit)

    def _tinted_icon(self, color: QColor) -> QIcon:
        base = self._icon_base
        if base is None or base.isNull():
            base = QIcon()
        pixmap = base.pixmap(64, 64)
        if pixmap.isNull():
            pixmap = QPixmap(64, 64)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setBrush(color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(8, 8, 48, 48)
            painter.end()
            return QIcon(pixmap)
        tinted = QPixmap(pixmap.size())
        tinted.fill(Qt.GlobalColor.transparent)
        painter = QPainter(tinted)
        painter.drawPixmap(0, 0, pixmap)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(tinted.rect(), color)
        painter.end()
        return QIcon(tinted)

    def set_power_state(self, state: str) -> None:
        normalized = str(state or "ACTIVE").upper()
        if normalized not in POWER_COLORS:
            normalized = "ACTIVE"
        self._power_state = normalized
        self.setIcon(self._tinted_icon(POWER_COLORS[normalized]))
        self.setToolTip(f"IDEye - {normalized.replace('_', ' ').title()}")

    def set_ghost_peek(self, enabled: bool) -> None:
        if self._ghost_action is not None:
            self._ghost_action.blockSignals(True)
            self._ghost_action.setChecked(bool(enabled))
            self._ghost_action.blockSignals(False)

    @property
    def power_state(self) -> str:
        return self._power_state

    @property
    def ghost_peek_enabled(self) -> bool:
        return bool(self._ghost_action is not None and self._ghost_action.isChecked())
