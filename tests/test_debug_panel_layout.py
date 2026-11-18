"""Debug panel layout: short telemetry states, no clipped labels, no button-like info label."""

from __future__ import annotations

import os
import re
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

_APP = QApplication.instance() or QApplication(sys.argv)

import ideye.config as config
from ideye.ui.debug_widget import DebugWidget
from ideye.ui.overlay_window import OverlayWindow

INNER_WIDTH = config.DEBUG_WINDOW_WIDTH - 2 * 14


def _row_width(widgets, spacing):
    return sum(w.sizeHint().width() for w in widgets) + spacing * (len(widgets) - 1)


def test_telemetry_rows_fit_before_the_collapse_button():
    widget = DebugWidget()
    for state in ("ACTIVE", "PAUSED_ECO", "AWAY_DEEP_SLEEP"):
        widget.set_power_state(state)
        assert _row_width([widget.lbl_fps, widget.lbl_power_state, widget.btn_collapse], 8) <= INNER_WIDTH
    for text in ("Fijación 100%", "Sácada"):
        widget.lbl_stability.setText(text)
        widget.set_lighting_status(True, 0.0)
        assert _row_width([widget.lbl_stability, widget.lbl_lighting], 12) <= INNER_WIDTH


def test_power_states_use_plain_words():
    widget = DebugWidget()
    widget.set_power_state("AWAY_DEEP_SLEEP")
    assert widget.lbl_power_state.text() == "Reposo"
    widget.set_power_state("PAUSED_ECO")
    assert "_" not in widget.lbl_power_state.text()


def test_tracking_mode_label_has_no_button_border():
    widget = DebugWidget()
    qss = widget.combo_mode.styleSheet()
    assert "border: none" in qss
    assert "background-color: transparent" in qss
    assert widget.combo_mode.itemText(2) == "Solo Cabeza (Recomendado)"


def test_no_literal_question_mark_stands_in_for_an_accent():
    source = open(DebugWidget.__module__.replace(".", "/") + ".py", encoding="utf-8").read() \
        if False else None
    widget = DebugWidget()
    for text in (widget.chk_low_light.text(), widget.chk_micro_gestures.text(), widget.btn_open_guide.toolTip()):
        assert not re.search(r"[a-z]\?[a-z]", text)


def test_grid_keeps_a_wider_gap_to_the_panel():
    overlay = OverlayWindow()
    widget = DebugWidget()
    overlay.set_debug_widget(widget)
    widget.show()
    overlay.resize(1920, 1080)
    assert overlay._target_right_margin(1920.0) >= config.DEBUG_WINDOW_WIDTH + 24
    widget.hide()
