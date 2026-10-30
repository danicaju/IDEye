"""Phase 11: gaze scroll, eco power and Ghost-Peek/system tray regression tests."""

from __future__ import annotations

import math
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication

_APP = QApplication.instance() or QApplication(sys.argv)

from ideye import config
from ideye.config import MAR_THRESHOLD
from ideye.core.eco_power_manager import EcoPowerManager
from ideye.core.gaze_scroller import GazeScroller
from ideye.ui.overlay_window import OverlayWindow
from ideye.ui.system_tray import IDEyeSystemTray


class TestGazeScroller:
    def test_deadzone_is_zero(self):
        scroller = GazeScroller()
        for y in (0.28, 0.5, 0.72):
            assert scroller.target_speed(y) == 0.0

    @pytest.mark.parametrize("y,expected_sign", [(0.90, 1.0), (0.10, -1.0)])
    def test_edge_speed_is_proportional_and_signed(self, y, expected_sign):
        scroller = GazeScroller()
        speed = scroller.target_speed(y)
        assert math.copysign(1.0, speed) == expected_sign
        assert abs(speed) > 0.0
        assert abs(speed) <= scroller.max_scroll_rate

    def test_speed_grows_toward_edge(self):
        scroller = GazeScroller()
        assert abs(scroller.target_speed(0.90)) > abs(scroller.target_speed(0.75))
        assert abs(scroller.target_speed(0.10)) > abs(scroller.target_speed(0.25))

    def test_inertia_decays_when_returning_to_center(self):
        scroller = GazeScroller()
        scroller.activate()
        first = scroller.update(0.90, dt=1.0 / 60.0)
        second = scroller.update(0.50, dt=1.0 / 60.0)
        assert first > 0.0
        assert second == pytest.approx(first * scroller.decay)
        assert scroller.speed() == pytest.approx(second)

    def test_inactive_scroller_stops_and_resets(self):
        scroller = GazeScroller()
        scroller.activate()
        scroller.update(0.90)
        scroller.stop()
        assert not scroller.active
        assert scroller.speed() == 0.0
        assert scroller.last_steps == 0

    def test_horizontal_axis_is_safe(self):
        scroller = GazeScroller()
        scroller.activate()
        assert scroller.target_horizontal_speed(0.5) == 0.0
        assert scroller.target_horizontal_speed(0.95) > 0.0
        assert scroller.target_horizontal_speed(0.05) < 0.0
        assert math.isfinite(scroller.update_horizontal(float("nan")))


class TestEcoPowerManager:
    def test_active_pause_and_deep_sleep_transitions(self):
        eco = EcoPowerManager(enabled=True)
        assert eco.update(detected=True, now=0.0) == eco.ACTIVE
        assert eco.update(detected=False, paused=True, now=1.0) == eco.PAUSED_ECO
        assert eco.fps == 10.0
        assert eco.frame_interval == pytest.approx(0.1)
        assert eco.update(detected=False, paused=False, now=2.0) == eco.ACTIVE
        assert eco.update(detected=False, paused=False, now=11.0) == eco.AWAY_DEEP_SLEEP
        assert eco.fps == 2.0
        assert eco.frame_interval == pytest.approx(0.5)

    def test_face_detection_wakes_instantly(self):
        eco = EcoPowerManager(enabled=True)
        eco.update(detected=False, now=0.0)
        assert eco.update(detected=False, now=12.0) == eco.AWAY_DEEP_SLEEP
        assert eco.update(detected=True, now=12.01) == eco.ACTIVE
        assert eco.fps == 30.0

    def test_pause_wakes_immediately_after_unpause(self):
        eco = EcoPowerManager(enabled=True)
        assert eco.set_paused(True, now=1.0) == eco.PAUSED_ECO
        assert eco.set_paused(False, now=2.0) == eco.ACTIVE


class TestGhostPeek:
    def test_fades_after_idle_and_wakes_on_mar(self):
        overlay = OverlayWindow()
        overlay.set_ghost_peek_enabled(True, emit_signal=False)
        assert overlay.ghost_peek_idle_seconds >= 30.0
        overlay._last_ghost_interaction = 0.0
        overlay._ghost_opacity = 1.0
        for _ in range(20):
            overlay.update_ghost_peek(now=35.0)
        assert overlay._ghost_opacity == pytest.approx(0.15, abs=0.01)
        overlay.on_mar_updated(None, float(getattr(config, "MAR_REST_THRESHOLD", 0.20)) + 0.10)
        assert overlay._ghost_opacity == 1.0
        overlay.close()

    def test_cell_change_wakes_ghost(self):
        overlay = OverlayWindow()
        overlay.set_ghost_peek_enabled(True, emit_signal=False)
        overlay._ghost_opacity = 0.15
        overlay._last_ghost_gaze = (0.5, 0.5)
        overlay.hovered_block = 0
        overlay.on_gaze_updated(0.75, 0.25)
        assert overlay._ghost_opacity == 1.0
        overlay.close()

    def test_disabled_ghost_keeps_cards_visible(self):
        overlay = OverlayWindow()
        overlay.set_ghost_peek_enabled(False, emit_signal=False)
        overlay._ghost_opacity = 0.15
        assert overlay._ghost_card_opacity() == 1.0
        overlay.close()


class TestSystemTray:
    def test_tray_builds_menu_and_accepts_state(self):
        tray = IDEyeSystemTray()
        assert tray.power_state == "ACTIVE"
        assert tray.ghost_peek_enabled is True
        tray.set_power_state("PAUSED_ECO")
        assert tray.power_state == "PAUSED_ECO"
        tray.set_ghost_peek(False)
        assert tray.ghost_peek_enabled is False
        actions = [action.text() for action in tray.contextMenu().actions()]
        assert any("Pausa" in text for text in actions)
        assert any("Ghost-Peek" in text for text in actions)
        assert any("Salir de IDEye" in text for text in actions)
        tray.hide()
