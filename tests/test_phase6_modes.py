"""
Phase 6 Comprehensive Automated Test Suite:
1. 3x3 integrity for all 5 context modes.
2. Manual cycling and mode_changed signal.
3. Smart auto-switch via simulated WebSocket payloads.
4. AI prompts and heuristic predictions.
"""

import sys
import os
import pytest

_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_WORKSPACE_ROOT = os.path.abspath(os.path.join(_CURRENT_DIR, ".."))
if _WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, _WORKSPACE_ROOT)

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QRectF

from eyede.modes import (
    ModeManager,
    CodingMode,
    WritingMode,
    TerminalGitMode,
    DataMathMode,
    IdeNavMode,
    MODE_ORDER,
    MODE_CLASSES,
)
from eyede.actions.menu_trees import validate_menu_tree
from eyede.ui.overlay_window import OverlayWindow


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(["--platform", "offscreen"])
    return app


MODES = [CodingMode(), WritingMode(), TerminalGitMode(), DataMathMode(), IdeNavMode()]


def _collect_nodes(mode):
    tree = mode.get_menu_tree()
    return tree


def _validate_recursive(tree, visited=None):
    if visited is None:
        visited = set()
    errors = []
    # validate all nodes in tree
    for node_id, node in tree.items():
        if len(node.items) != 9:
            errors.append(f"{node_id}: {len(node.items)} items")
        if len(node.items) > 4 and node.items[4].action_type != "PAUSE":
            errors.append(f"{node_id}: center not pause")
        if node_id not in ("ROOT", "MENU_STANDARD") and len(node.items) > 6:
            if node.items[6].action_type != "BACK":
                errors.append(f"{node_id}: slot6 not back")
    # recursive via submenu ids
    for node_id, node in tree.items():
        for item in node.items:
            if item.action_type == "SUBMENU" and item.submenu_id in tree:
                pass
    ok, verrs = validate_menu_tree(tree)
    errors.extend(verrs)
    return len(errors) == 0, errors


@pytest.mark.parametrize("mode", MODES, ids=lambda m: m.mode_id)
def test_mode_tree_integrity(mode):
    tree = mode.get_menu_tree()
    ok, errors = validate_menu_tree(tree)
    assert ok, f"{mode.mode_id}: {errors}"


def test_manual_cycle(qapp):
    mm = ModeManager()
    received = []
    mm.mode_changed.connect(lambda mid, name, color: received.append((mid, name, color)))
    expected_colors = {
        "coding": "#00F0FF",
        "writing": "#10B981",
        "terminal": "#A855F7",
        "data_math": "#F59E0B",
        "navigation": "#E2E8F0",
    }
    for expected in MODE_ORDER:
        mm.cycle_next_mode()
    # after 5 cycles returns to coding
    assert mm.current_mode_id == "coding"
    # received 5 transitions (initial not emitted)
    assert len(received) == 5
    for mid, name, color in received:
        assert color == expected_colors[mid]


def test_auto_switch(qapp):
    mm = ModeManager()
    # terminal
    assert mm.handle_editor_state({"context": "terminal"}) == "terminal"
    assert mm.current_mode_id == "terminal"
    # writing via extension
    mm.set_mode("coding", emit=False)
    mm.handle_editor_state({"filePath": "README.md"})
    assert mm.current_mode_id == "writing"
    # writing via context
    mm.set_mode("coding", emit=False)
    mm.handle_editor_state({"context": "comment"})
    assert mm.current_mode_id == "writing"
    # data_math
    mm.set_mode("coding", emit=False)
    mm.handle_editor_state({"filePath": "query.sql"})
    assert mm.current_mode_id == "data_math"
    # coding
    mm.set_mode("writing", emit=False)
    mm.handle_editor_state({"filePath": "main.py"})
    assert mm.current_mode_id == "coding"
    # auto switch disabled
    mm.set_mode("coding", emit=False)
    mm.auto_switch_enabled = False
    mm.handle_editor_state({"filePath": "README.md"})
    assert mm.current_mode_id == "coding"


def test_header_mode_button_layout_1280(qapp):
    overlay = OverlayWindow()
    overlay.resize(1280, 720)
    overlay._update_header_exit_rect()
    assert overlay.header_mode_rect.right() <= overlay.header_lang_rect.left()
    assert overlay.header_lang_rect.right() <= overlay.header_help_rect.left()
    assert overlay.header_help_rect.right() <= overlay.header_exit_rect.left()


def test_mode_shortcut_requires_header_gaze(qapp):
    overlay = OverlayWindow()
    overlay.resize(1280, 720)
    overlay.header_mode_rect = QRectF(100.0, 10.0, 150.0, 30.0)
    overlay.current_gaze = (0.15, 0.03)  # 192, 21.6 -> inside the button
    assert overlay.is_mode_shortcut_targeted() is True
    overlay.current_gaze = (0.50, 0.50)  # center of the screen -> outside
    assert overlay.is_mode_shortcut_targeted() is False


def test_ai_prompts_and_heuristics(qapp):
    for mode in MODES:
        prompt = mode.get_ai_system_prompt({"language": "PYTHON"})
        assert isinstance(prompt, str) and len(prompt) > 10
        preds = mode.get_heuristic_predictions({"context_text": "def foo("})
        assert isinstance(preds, list)
        assert len(preds) == 6
        assert all(isinstance(p, str) for p in preds)


def test_mode_manager_aliases_and_properties(qapp):
    mm = ModeManager()
    assert mm.current_mode_id == "coding"
    assert mm.get_heuristic_predictions() is not None
    assert len(mm.get_heuristic_predictions()) == 6
    mm.set_mode("writing")
    assert mm.current_mode_id == "writing"
    assert mm.get_root_menu() is not None
    assert mm.get_menu_tree() is not None
