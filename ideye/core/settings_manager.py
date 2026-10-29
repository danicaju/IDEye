"""IDEye - Persistent user settings (Phase 8.1).

Atomic, debounced JSON persistence for live runtime adjustments.
"""

from __future__ import annotations

import json
import os
import threading
from typing import Any, Dict, Optional

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

try:
    import ideye.config as config
except ImportError:  # pragma: no cover
    import config  # type: ignore


# Captured once at import so runtime mutations of config.MAR_THRESHOLD never
# contaminate "factory reset" defaults.
_FACTORY_DEFAULTS: Dict[str, Any] = {
    "tracking_mode": str(getattr(config, "DEFAULT_TRACKING_MODE", "HEAD_PRIMARY")),
    "sensitivity_x": float(getattr(config, "DEFAULT_HEAD_SENSITIVITY_X", 2.6)),
    "sensitivity_y": float(getattr(config, "DEFAULT_HEAD_SENSITIVITY_Y", 3.0)),
    "one_euro_level": 6,
    "mar_threshold": float(getattr(config, "MAR_THRESHOLD", 0.45)),
    "sound_enabled": bool(getattr(config, "SOUND_ENABLED", True)),
    "auto_switch_enabled": bool(getattr(config, "CONTEXT_AUTO_SWITCH_ENABLED", False)),
    "adaptive_ast_enabled": bool(getattr(config, "ENABLE_ADAPTIVE_AST_MENUS", True)),
    "active_language": "python",
    "debug_panel_collapsed": False,
    "health_guard_enabled": bool(getattr(config, "HEALTH_GUARD_ENABLED", True)),
    "micro_gestures_enabled": bool(getattr(config, "MICRO_GESTURES_ENABLED", True)),
    "auto_low_light_clahe": bool(getattr(config, "AUTO_LOW_LIGHT_CLAHE", True)),
    "eco_sleep_enabled": bool(getattr(config, "ECO_SLEEP_ENABLED", True)),
    "ghost_peek_enabled": bool(getattr(config, "GHOST_PEEK_ENABLED", True)),
    "gaze_scroll_enabled": bool(getattr(config, "GAZE_SCROLL_ENABLED", True)),
}


from ideye.core.logging_config import get_logger

logger = get_logger(__name__)

def _defaults() -> Dict[str, Any]:
    return dict(_FACTORY_DEFAULTS)


def default_settings_path() -> str:
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(root, "user_settings.json")


class SettingsManager(QObject):
    """Thread-safe, atomic, debounced user settings store."""

    settings_changed = pyqtSignal(dict)

    def __init__(
        self,
        path: Optional[str] = None,
        parent: Optional[QObject] = None,
        debounce_ms: int = 300,
    ) -> None:
        super().__init__(parent)
        self.path = path or getattr(config, "USER_SETTINGS_PATH", default_settings_path())
        self._lock = threading.RLock()
        self._settings: Dict[str, Any] = _defaults()
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self.save_now)
        self._debounce_ms = max(0, int(debounce_ms))
        self.load()

    # ------------------------------------------------------------------
    # Loading and validation
    # ------------------------------------------------------------------
    def load(self) -> Dict[str, Any]:
        """Loads the JSON file, merging valid keys over safe defaults."""
        loaded: Dict[str, Any] = {}
        try:
            if os.path.isfile(self.path):
                with open(self.path, "r", encoding="utf-8") as fh:
                    raw = json.load(fh)
                if isinstance(raw, dict):
                    loaded = raw
                else:
                    raise ValueError("settings root must be an object")
        except Exception as exc:
            logger.warning(f"[SettingsManager] Warning: could not load '{self.path}': {exc}. Using defaults.")
            loaded = {}

        with self._lock:
            merged = _defaults()
            for key, value in loaded.items():
                if key in merged:
                    merged[key] = self._coerce(key, value, merged[key])
            self._settings = merged
        return dict(self._settings)

    @staticmethod
    def _coerce(key: str, value: Any, fallback: Any) -> Any:
        try:
            if isinstance(fallback, bool):
                return bool(value)
            if isinstance(fallback, int) and not isinstance(fallback, bool):
                return int(value)
            if isinstance(fallback, float):
                return float(value)
            if isinstance(fallback, str):
                return str(value)
        except (TypeError, ValueError):
            return fallback
        return value

    # ------------------------------------------------------------------
    # Access
    # ------------------------------------------------------------------
    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._settings.get(key, default)

    def as_dict(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._settings)

    def set(self, key: str, value: Any, save: bool = True) -> None:
        with self._lock:
            if key not in self._settings:
                return
            self._settings[key] = self._coerce(key, value, self._settings[key])
            snapshot = dict(self._settings)
        if save:
            self.schedule_save()
        self.settings_changed.emit(snapshot)

    def update(self, values: Dict[str, Any], save: bool = True) -> None:
        with self._lock:
            for key, value in values.items():
                if key in self._settings:
                    self._settings[key] = self._coerce(key, value, self._settings[key])
            snapshot = dict(self._settings)
        if save:
            self.schedule_save()
        self.settings_changed.emit(snapshot)

    def schedule_save(self) -> None:
        """Debounces disk writes so slider drags never block the GUI."""
        self._save_timer.start(self._debounce_ms)

    # ------------------------------------------------------------------
    # Atomic persistence
    # ------------------------------------------------------------------
    def save_now(self) -> bool:
        with self._lock:
            snapshot = dict(self._settings)
        tmp_path = self.path + ".tmp"
        try:
            os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
            with open(tmp_path, "w", encoding="utf-8") as fh:
                json.dump(snapshot, fh, indent=2, ensure_ascii=False)
                fh.write("\n")
                fh.flush()
                try:
                    os.fsync(fh.fileno())
                except OSError:
                    pass
            os.replace(tmp_path, self.path)
            return True
        except Exception as exc:
            logger.warning(f"[SettingsManager] Warning: could not save '{self.path}': {exc}")
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except OSError:
                pass
            return False

    def reset_to_defaults(self) -> Dict[str, Any]:
        with self._lock:
            self._settings = _defaults()
            snapshot = dict(self._settings)
        self.save_now()
        self.settings_changed.emit(snapshot)
        return snapshot
