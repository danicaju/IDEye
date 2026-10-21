"""IDEye - Multi-monitor handover (Phase 8.3)."""

from __future__ import annotations

import math
import time
from typing import Any, List, Optional

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication

try:
    import eyede.config as config
except ImportError:  # pragma: no cover
    import config  # type: ignore


class ScreenManager(QObject):
    """Moves the HUD across monitors and re-anchors the gaze target bounds."""

    screen_changed = pyqtSignal(int, int)  # current index, total count

    def __init__(
        self,
        overlay: Optional[Any] = None,
        debug_widget: Optional[Any] = None,
        gaze_estimator: Optional[Any] = None,
        parent: Optional[QObject] = None,
        screens_override: Optional[List[Any]] = None,
    ) -> None:
        super().__init__(parent)
        self.overlay = overlay
        self.debug_widget = debug_widget
        self.gaze_estimator = gaze_estimator
        self._screens_override = screens_override
        self._cached_screens: Optional[List[Any]] = None
        self._current_index = 0
        self._yaw_since: Optional[float] = None
        self._last_handover = 0.0
        app = QApplication.instance()
        if app is not None:
            try:
                app.screenAdded.connect(lambda *_: self._on_screens_changed())
                app.screenRemoved.connect(lambda *_: self._on_screens_changed())
            except Exception:
                pass
        self._refresh_screens()

    # ------------------------------------------------------------------
    def _refresh_screens(self) -> None:
        """Refreshes the cached screen list from QApplication."""
        if self._screens_override is not None:
            self._cached_screens = list(self._screens_override)
            return
        app = QApplication.instance()
        if app is None:
            self._cached_screens = []
            return
        try:
            self._cached_screens = [screen for screen in app.screens() if screen.isAvailable()]
        except Exception:
            self._cached_screens = list(app.screens())

    def get_available_screens(self) -> List[Any]:
        if self._screens_override is not None:
            return list(self._screens_override)
        if self._cached_screens is None:
            self._refresh_screens()
        return list(self._cached_screens) if self._cached_screens is not None else []

    @property
    def screen_count(self) -> int:
        return len(self.get_available_screens())

    @property
    def current_index(self) -> int:
        return self._current_index

    def current_screen(self) -> Optional[Any]:
        screens = self.get_available_screens()
        if not screens:
            return None
        return screens[max(0, min(len(screens) - 1, self._current_index))]

    def _on_screens_changed(self) -> None:
        self._refresh_screens()
        count = self.screen_count
        if count <= 0:
            self._current_index = 0
        elif self._current_index >= count:
            self._current_index = count - 1
        self.screen_changed.emit(self._current_index, count)

    # ------------------------------------------------------------------
    def handover_to_screen(
        self,
        screen_index: int,
        reason: str = "manual",
        timestamp: Optional[float] = None,
    ) -> bool:
        self._refresh_screens()
        screens = self.get_available_screens()
        if not screens:
            return False
        try:
            index = int(screen_index)
        except (TypeError, ValueError):
            return False
        if index < 0 or index >= len(screens):
            return False
        screen = screens[index]
        try:
            geo = screen.availableGeometry()
        except Exception:
            return False

        if self.overlay is not None:
            try:
                self.overlay.setGeometry(geo)
                self.overlay.refresh_grid_right_margin(animate=False)
                if hasattr(self.overlay, "set_screen_info"):
                    self.overlay.set_screen_info(index, len(screens))
                self.overlay.update()
            except Exception as exc:
                print(f"[ScreenManager] Warning: overlay handover failed: {exc}")

        if self.debug_widget is not None:
            try:
                dw = int(getattr(config, "DEBUG_WINDOW_WIDTH", 340))
                x = geo.x() + geo.width() - dw - 12
                y = geo.y() + 24
                self.debug_widget.move(max(geo.x(), x), max(geo.y(), y))
                self.debug_widget.update()
            except Exception as exc:
                print(f"[ScreenManager] Warning: monitor handover failed: {exc}")

        if self.gaze_estimator is not None:
            try:
                self.gaze_estimator.set_target_screen(geo.width(), geo.height())
            except Exception:
                pass

        self._current_index = index
        self._last_handover = timestamp if timestamp is not None else time.time()
        self._yaw_since = None
        self.screen_changed.emit(index, len(screens))
        print(f"[ScreenManager] Handover -> screen {index + 1}/{len(screens)} ({reason})")
        return True

    def cycle_next_screen(self) -> bool:
        count = self.screen_count
        if count <= 1:
            return False
        return self.handover_to_screen((self._current_index + 1) % count, "manual")

    # ------------------------------------------------------------------
    def update_head_yaw(self, yaw_degrees: float, timestamp: Optional[float] = None) -> bool:
        """Bezel crossing: >21 degrees toward an edge for >400 ms."""
        try:
            yaw = float(yaw_degrees)
        except (TypeError, ValueError):
            yaw = 0.0
        if not math.isfinite(yaw) or abs(yaw) <= 21.0:
            self._yaw_since = None
            return False

        direction = 1 if yaw > 0 else -1
        screens = self.get_available_screens()
        target = self._current_index + direction
        if target < 0 or target >= len(screens):
            self._yaw_since = None
            return False

        now = timestamp if timestamp is not None else time.time()
        if self._yaw_since is None:
            self._yaw_since = now
            return False
        if now - self._yaw_since < 0.40:
            return False
        if now - self._last_handover < 1.0:
            return False
        self._yaw_since = None
        return self.handover_to_screen(target, "bezel", timestamp=now)
