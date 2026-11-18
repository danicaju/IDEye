"""reduced_motion: persisted setting that turns gradual transitions into instant changes."""

from __future__ import annotations

import os
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

_APP = QApplication.instance() or QApplication(sys.argv)

from ideye.core.settings_manager import SettingsManager
from ideye.ui.overlay_window import OverlayWindow


def test_setting_has_default_and_persists(tmp_path):
    path = tmp_path / "settings.json"
    manager = SettingsManager(str(path))
    assert manager.get("reduced_motion") is False
    manager.set("reduced_motion", True)
    manager.save_now()
    assert SettingsManager(str(path)).get("reduced_motion") is True


def test_ghost_peek_snaps_when_reduced_motion():
    overlay = OverlayWindow()
    overlay.set_ghost_peek_enabled(True, emit_signal=False)
    overlay.set_reduced_motion(True, emit_signal=False)
    overlay._last_ghost_interaction = time.time() - 120.0
    assert overlay.update_ghost_peek() == 0.15  # one step, no gradual fade


def test_ghost_peek_fades_gradually_by_default():
    overlay = OverlayWindow()
    overlay.set_ghost_peek_enabled(True, emit_signal=False)
    overlay.set_reduced_motion(False, emit_signal=False)
    overlay._last_ghost_interaction = time.time() - 120.0
    first = overlay.update_ghost_peek()
    assert 0.15 < first < 1.0


def test_wake_is_instant_and_never_queued():
    overlay = OverlayWindow()
    overlay._ghost_opacity = 0.15
    overlay._wake_ghost_peek()
    assert overlay._ghost_opacity == 1.0


def test_focus_transition_is_interruptible_and_never_queues():
    overlay = OverlayWindow()
    overlay.set_reduced_motion(False, emit_signal=False)
    overlay.hovered_block = 0
    first = overlay._focus_anim
    overlay.hovered_block = 1  # saccade to another cell before the first fade ends
    overlay.hovered_block = 2
    assert overlay._focus_anim is not first
    assert overlay._focus_prev == 1
    assert overlay._focus_in == 0.0  # restarts from the live value, no stale queue
    assert overlay._focus_halo_weight(2, True) == 0.0


def test_focus_transition_is_instant_with_reduced_motion():
    overlay = OverlayWindow()
    overlay.set_reduced_motion(True, emit_signal=False)
    overlay.hovered_block = 3
    assert overlay._focus_in == 1.0
    assert overlay._focus_out == 0.0
    assert overlay._focus_halo_weight(3, True) == 1.0
