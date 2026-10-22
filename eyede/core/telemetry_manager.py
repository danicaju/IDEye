"""IDEye - local Look-To-Code telemetry and effort savings (Phase 9)."""

from __future__ import annotations

import json
import os
import threading
import time
from typing import Any, Dict, Optional

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from eyede.core.logging_config import get_logger

logger = get_logger(__name__)


def default_telemetry_path() -> str:
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(root, "telemetry_stats.json")


class TelemetryManager(QObject):
    """Accumulates usage metrics and persists them atomically with debounce."""

    stats_changed = pyqtSignal(dict)

    def __init__(
        self,
        path: Optional[str] = None,
        parent: Optional[QObject] = None,
        debounce_ms: int = 300,
        usage_tick_ms: int = 1000,
    ) -> None:
        super().__init__(parent)
        self.path = path or default_telemetry_path()
        self._lock = threading.RLock()
        self.total_mouth_clicks = 0
        self.total_chars_injected = 0
        self.keystrokes_saved = 0
        self.efficiency_ratio_pct = 0.0
        self.cell_heatmap = [0] * 9
        self.mode_usage_seconds: Dict[str, float] = {}
        self._current_mode: Optional[str] = None
        self._last_usage_tick = time.monotonic()

        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(max(0, int(debounce_ms)))
        self._save_timer.timeout.connect(self.save_now)

        self._usage_timer = QTimer(self)
        self._usage_timer.setInterval(max(200, int(usage_tick_ms)))
        self._usage_timer.timeout.connect(self._on_usage_tick)

        self.load()
        self._usage_timer.start()

    # ------------------------------------------------------------------
    def _recompute(self) -> None:
        saved = max(0, int(self.total_chars_injected) - int(self.total_mouth_clicks))
        self.keystrokes_saved = saved
        chars = max(0, int(self.total_chars_injected))
        clicks = max(0, int(self.total_mouth_clicks))
        if chars <= 0:
            self.efficiency_ratio_pct = 0.0
        else:
            ratio = (1.0 - (clicks / float(max(1, chars)))) * 100.0
            self.efficiency_ratio_pct = max(0.0, min(100.0, ratio))

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_mouth_clicks": int(self.total_mouth_clicks),
                "total_chars_injected": int(self.total_chars_injected),
                "keystrokes_saved": int(self.keystrokes_saved),
                "efficiency_ratio_pct": round(float(self.efficiency_ratio_pct), 2),
                "cell_heatmap": list(self.cell_heatmap),
                "mode_usage_seconds": {
                    str(k): round(float(v), 3) for k, v in self.mode_usage_seconds.items()
                },
            }

    def _emit_and_schedule(self) -> None:
        self._recompute()
        self.stats_changed.emit(self.stats())
        self._save_timer.start()

    # ------------------------------------------------------------------
    def record_mouth_click(self, cell_index: Optional[int] = None) -> None:
        with self._lock:
            self.total_mouth_clicks += 1
            if cell_index is not None and 0 <= int(cell_index) < 9:
                self.cell_heatmap[int(cell_index)] += 1
        self._emit_and_schedule()

    def record_injection(self, chars: int) -> None:
        try:
            amount = max(0, int(chars))
        except (TypeError, ValueError):
            amount = 0
        if amount <= 0:
            return
        with self._lock:
            self.total_chars_injected += amount
        self._emit_and_schedule()

    def record_cell(self, cell_index: int) -> None:
        if 0 <= int(cell_index) < 9:
            with self._lock:
                self.cell_heatmap[int(cell_index)] += 1
            self._emit_and_schedule()

    # ------------------------------------------------------------------
    def _accumulate_usage(self, now: Optional[float] = None) -> None:
        if self._current_mode is None:
            self._last_usage_tick = now if now is not None else time.monotonic()
            return
        current = now if now is not None else time.monotonic()
        delta = max(0.0, current - self._last_usage_tick)
        if delta:
            self.mode_usage_seconds[self._current_mode] = (
                self.mode_usage_seconds.get(self._current_mode, 0.0) + delta
            )
        self._last_usage_tick = current

    def set_current_mode(self, mode_id: str, timestamp: Optional[float] = None) -> None:
        with self._lock:
            self._accumulate_usage(timestamp)
            self._current_mode = str(mode_id or "").strip() or None
        self._save_timer.start()

    def tick(self, timestamp: Optional[float] = None) -> None:
        with self._lock:
            self._accumulate_usage(timestamp)
        self._save_timer.start()

    def _on_usage_tick(self) -> None:
        self.tick()
        self.stats_changed.emit(self.stats())

    # ------------------------------------------------------------------
    def load(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {}
        try:
            if os.path.isfile(self.path):
                with open(self.path, "r", encoding="utf-8") as fh:
                    raw = json.load(fh)
                if isinstance(raw, dict):
                    data = raw
        except Exception as exc:
            logger.warning("Could not load telemetry '%s': %s", self.path, exc)
            data = {}

        with self._lock:
            self.total_mouth_clicks = max(0, int(data.get("total_mouth_clicks", 0) or 0))
            self.total_chars_injected = max(0, int(data.get("total_chars_injected", 0) or 0))
            heatmap = data.get("cell_heatmap", [])
            self.cell_heatmap = [
                max(0, int(heatmap[i] if i < len(heatmap) else 0))
                for i in range(9)
            ]
            usage = data.get("mode_usage_seconds", {})
            self.mode_usage_seconds = {
                str(k): max(0.0, float(v))
                for k, v in usage.items()
                if isinstance(k, str)
            } if isinstance(usage, dict) else {}
            self._recompute()
        self.stats_changed.emit(self.stats())
        return self.stats()

    def save_now(self) -> bool:
        try:
            payload = self.stats()
            tmp_path = self.path + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2)
            os.replace(tmp_path, self.path)
            return True
        except Exception as exc:
            logger.warning("Could not save telemetry '%s': %s", self.path, exc)
            return False

    def reset(self) -> None:
        with self._lock:
            self.total_mouth_clicks = 0
            self.total_chars_injected = 0
            self.keystrokes_saved = 0
            self.efficiency_ratio_pct = 0.0
            self.cell_heatmap = [0] * 9
            self.mode_usage_seconds = {}
            self._last_usage_tick = time.monotonic()
            self._recompute()
        self.save_now()
        self.stats_changed.emit(self.stats())

    def stop(self) -> None:
        self._usage_timer.stop()
        self.save_now()
