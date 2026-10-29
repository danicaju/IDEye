"""IDEye - Multi-monitor handover and per-monitor calibration binding."""

from __future__ import annotations

import time
from typing import Any, List, Optional

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication

try:
    import ideye.config as config
except ImportError:  # pragma: no cover
    import config  # type: ignore

from ideye.core.bezel_crossing import BezelCrossingDetector
from ideye.core.logging_config import get_logger

logger = get_logger(__name__)


class ScreenManager(QObject):
    """Moves the HUD across monitors and binds gaze to each monitor profile."""

    screen_changed = pyqtSignal(int, int)  # current index, total count

    def __init__(
        self,
        overlay: Optional[Any] = None,
        debug_widget: Optional[Any] = None,
        gaze_estimator: Optional[Any] = None,
        parent: Optional[QObject] = None,
        screens_override: Optional[List[Any]] = None,
        bezel_detector: Optional[BezelCrossingDetector] = None,
    ) -> None:
        super().__init__(parent)
        self.overlay = overlay
        self.debug_widget = debug_widget
        self.gaze_estimator = gaze_estimator
        self._screens_override = screens_override
        self._cached_screens: Optional[List[Any]] = None
        self._current_index = 0
        self.bezel_detector = bezel_detector or BezelCrossingDetector()

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
    @staticmethod
    def _call_screen(screen: Any, attr: str, default: Any = None) -> Any:
        value = getattr(screen, attr, None)
        if callable(value):
            try:
                value = value()
            except Exception:
                value = None
        return default if value is None else value

    @staticmethod
    def screen_key(screen: Any) -> str:
        """Returns a stable identity for a physical monitor + resolution."""
        try:
            geo = screen.availableGeometry()
            geometry = f"{geo.width()}x{geo.height()}"
        except Exception:
            geometry = "unknown"
        name = str(ScreenManager._call_screen(screen, "name", ""))
        serial = str(ScreenManager._call_screen(screen, "serialNumber", ""))
        manufacturer = str(ScreenManager._call_screen(screen, "manufacturer", ""))
        model = str(ScreenManager._call_screen(screen, "model", ""))
        identity = serial or name or f"{manufacturer}-{model}"
        return f"{manufacturer}|{model}|{identity}|{geometry}"

    @staticmethod
    def _physical_size_mm(screen: Any) -> tuple[float, float]:
        try:
            size = screen.physicalSize()
            return float(size.width()), float(size.height())
        except Exception:
            return 0.0, 0.0

    @staticmethod
    def _device_pixel_ratio(screen: Any) -> float:
        try:
            return float(screen.devicePixelRatio())
        except Exception:
            return 1.0

    def bind_gaze_to_screen(self, screen: Any, index: Optional[int] = None) -> bool:
        """Binds the gaze estimator to a monitor and loads its calibration."""
        if screen is None:
            return False
        try:
            geo = screen.availableGeometry()
        except Exception:
            return False
        key = self.screen_key(screen)
        physical_w, physical_h = self._physical_size_mm(screen)
        dpr = self._device_pixel_ratio(screen)
        loaded = False

        estimator = self.gaze_estimator
        if estimator is not None:
            if hasattr(estimator, "set_active_monitor"):
                try:
                    loaded = bool(
                        estimator.set_active_monitor(
                            key,
                            geo.width(),
                            geo.height(),
                            physical_w,
                            physical_h,
                            dpr,
                        )
                    )
                except Exception as exc:
                    logger.warning("Per-monitor calibration binding failed: %s", exc)
            elif hasattr(estimator, "set_target_screen"):
                try:
                    estimator.set_target_screen(geo.width(), geo.height())
                except Exception:
                    pass

        idx = self._current_index if index is None else index
        if self.overlay is not None:
            try:
                state = "calibrado" if loaded else "sin calibrar"
                self.overlay.last_action_desc = f"Monitor {idx + 1}: {state}"
                self.overlay.update()
            except Exception:
                pass
        return loaded

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
                logger.warning("Overlay handover failed: %s", exc)

        if self.debug_widget is not None:
            try:
                dw = int(getattr(config, "DEBUG_WINDOW_WIDTH", 340))
                x = geo.x() + geo.width() - dw - 12
                y = geo.y() + 24
                self.debug_widget.move(max(geo.x(), x), max(geo.y(), y))
                self.debug_widget.update()
            except Exception as exc:
                logger.warning("Monitor panel handover failed: %s", exc)

        self._current_index = index
        self.bind_gaze_to_screen(screen, index)
        self.bezel_detector.note_handover(timestamp if timestamp is not None else time.time())
        self.screen_changed.emit(index, len(screens))
        logger.info("Handover -> screen %d/%d (%s)", index + 1, len(screens), reason)
        return True

    def cycle_next_screen(self) -> bool:
        count = self.screen_count
        if count <= 1:
            return False
        return self.handover_to_screen((self._current_index + 1) % count, "manual")

    # ------------------------------------------------------------------
    def update_head_yaw(self, yaw_degrees: float, timestamp: Optional[float] = None) -> bool:
        """Feeds yaw to the detector and performs a handover when it fires."""
        screens = self.get_available_screens()
        count = len(screens)
        direction = self.bezel_detector.update(
            yaw_degrees,
            can_move_left=self._current_index > 0,
            can_move_right=self._current_index < count - 1,
            timestamp=timestamp,
        )
        if direction == 0:
            return False
        now = timestamp if timestamp is not None else time.time()
        return self.handover_to_screen(self._current_index + direction, "bezel", timestamp=now)
