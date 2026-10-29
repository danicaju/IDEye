"""Pre-release v1.0 exhaustive edge-case and chaos regression suite."""

from __future__ import annotations

import json
import math
import os
import sys
import tempfile
import types
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest
from PyQt6.QtWidgets import QApplication

_APP = QApplication.instance() or QApplication(sys.argv)

from ideye.actions.agentic_launcher import AgenticPromptLauncher
from ideye.actions.clipboard_history import ClipboardHistoryManager
from ideye.actions.code_injector import CodeInjector, DummyKeyboard
from ideye.actions.diagnostics_fixer import DiagnosticsFixer
from ideye.actions.ast_code_jumper import ASTCodeJumper
from ideye.actions.menu_trees import (
    MenuNode,
    build_menu_tree,
    get_adaptive_context_node,
)
from ideye.core.camera_tracker import CameraTracker
from ideye.core.game_profiles import GameProfileManager
from ideye.core.gaze_estimator import GazeEstimator, OneEuroFilter
from ideye.core.gesture_detector import GestureDetector
from ideye.core.health_guard import HealthGuard
from ideye.core.lighting_compensator import LightingCompensator
from ideye.core.mouse_controller import OSMouseController
from ideye.core.settings_manager import SettingsManager
from ideye.core.telemetry_manager import TelemetryManager
from ideye.core.websocket_bridge import WebSocketBridge
from ideye.modes.mode_manager import ModeManager
from ideye.ui.overlay_window import OverlayWindow


class _P:
    def __init__(self, x=0.5, y=0.5, z=0.0):
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)


def _landmarks(value: float = 0.5, n: int = 468):
    return types.SimpleNamespace(landmark=[_P(value, value) for _ in range(n)])


# ---------------------------------------------------------------------------
# 1. Vision / Math fuzzing
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "value",
    [0.0, 1.0, -1.0, 2.0, float("nan"), float("inf"), float("-inf"), -0.0],
)
def test_gaze_estimate_never_returns_non_finite(value):
    estimator = GazeEstimator()
    x, y, detected, _debug = estimator.estimate(_landmarks(value))
    assert math.isfinite(x) and math.isfinite(y)
    assert 0.0 <= x <= 1.0 and 0.0 <= y <= 1.0
    assert isinstance(detected, bool)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_one_euro_filter_and_safe_coord_ignore_non_finite(value):
    filt = OneEuroFilter()
    assert math.isfinite(filt.filter(1.0, value))
    assert math.isfinite(GazeEstimator._finite_unit(value))
    x, y = GazeEstimator._safe_coord(_P(value, value))
    assert math.isfinite(x) and math.isfinite(y)


def test_gaze_mode_switching_under_200_frames_is_finite():
    estimator = GazeEstimator()
    for index in range(200):
        estimator.set_tracking_mode(("HEAD_PRIMARY", "HYBRID", "PURE_IRIS")[index % 3])
        x, y, _detected, _debug = estimator.estimate(_landmarks(0.5 + (index % 5) / 100.0))
        assert math.isfinite(x) and math.isfinite(y)


@pytest.mark.parametrize(
    "frame",
    [
        np.zeros((1, 1, 3), dtype=np.uint8),
        np.full((2, 2), 255, dtype=np.uint8),
        np.zeros((2, 2, 4), dtype=np.uint8),
        np.array([[float("nan"), float("inf")]], dtype=np.float32),
        np.zeros((2, 2, 2), dtype=np.uint8),
    ],
)
def test_frame_conversion_and_lighting_survive_extreme_frames(frame):
    image = CameraTracker.frame_to_qimage(frame)
    if frame.ndim == 3 and frame.shape[2] == 2:
        assert image is None
    else:
        assert image is not None and not image.isNull()

    enhanced = LightingCompensator().process(frame)
    assert enhanced is not None
    assert enhanced.size > 0


def test_lighting_handles_black_white_gray_1x1():
    lighting = LightingCompensator()
    for frame in (
        np.zeros((1, 1, 3), dtype=np.uint8),
        np.full((1, 1, 3), 255, dtype=np.uint8),
        np.zeros((4, 4), dtype=np.uint8),
        np.full((4, 4, 4), 255, dtype=np.uint8),
    ):
        result = lighting.process(frame)
        assert result is not None and result.size > 0


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_gestures_and_health_ignore_non_finite_landmarks(value):
    landmarks = _landmarks(value)
    detector = GestureDetector()
    assert math.isfinite(detector.compute_mar(landmarks))
    left, right = detector.compute_ear(landmarks)
    assert math.isfinite(left) and math.isfinite(right)
    assert math.isfinite(detector.compute_brow_raise(landmarks))
    assert math.isfinite(detector.compute_head_roll(landmarks))
    guard = HealthGuard()
    assert guard.process(landmarks, now=1.0) is None


def test_health_guard_baseline_is_bounded():
    guard = HealthGuard()
    landmarks = _landmarks(0.5)
    for index in range(200):
        guard.process(landmarks, now=float(index))
    assert len(guard._baseline_samples) <= 45


# ---------------------------------------------------------------------------
# 2. Input safety / stuck keys
# ---------------------------------------------------------------------------
class _FakeMouse:
    def __init__(self):
        self.position = (0, 0)
        self.clicks = []
        self.releases = []
        self.scrolls = []

    def click(self, button, count=1):
        self.clicks.append((button, count))

    def release(self, button):
        self.releases.append(button)

    def scroll(self, dx, dy):
        self.scrolls.append((dx, dy))


class _FakeKeyboard:
    def __init__(self):
        self.pressed = []
        self.released = []

    def press(self, key):
        self.pressed.append(key)

    def release(self, key):
        self.released.append(key)

    def tap(self, key):
        pass


def test_mouse_controller_rejects_non_finite_and_releases_everything():
    fake = _FakeMouse()
    mouse = OSMouseController(controller=fake)
    mouse._keyboard = _FakeKeyboard()
    mouse.move_direct(float("nan"), float("inf"))
    mouse.move_to(float("inf"), float("-inf"))
    mouse.left_click(float("nan"), 20)
    mouse.scroll(float("nan"))
    mouse.release_all_game_keys()
    assert "up" in mouse._keyboard.released
    assert "left" in mouse._keyboard.released
    assert "e" in mouse._keyboard.released
    assert len(fake.releases) >= 2


class _FlakyClipboard:
    def __init__(self):
        self.text = "old"
        self.paste_failures = 2
        self.copy_failures = 1

    def paste(self):
        if self.paste_failures > 0:
            self.paste_failures -= 1
            raise RuntimeError("OpenClipboard failed")
        return self.text

    def copy(self, value):
        if self.copy_failures > 0:
            self.copy_failures -= 1
            raise RuntimeError("OpenClipboard failed")
        self.text = value


def test_code_injector_retries_clipboard_and_restores_it():
    clipboard = _FlakyClipboard()
    keyboard = DummyKeyboard()
    injector = CodeInjector(
        async_mode=False,
        keyboard_controller=keyboard,
        clipboard_module=clipboard,
        paste_delay=0.0,
    )
    assert injector.insert_snippet("x = 42", async_exec=False)
    assert clipboard.text == "old"


def test_code_injector_exception_never_leaves_modifiers_pressed():
    class ThrowingKeyboard(DummyKeyboard):
        def tap(self, key):
            self.tapped_keys.append(key)
            if key == "v":
                raise RuntimeError("paste failed")

    keyboard = ThrowingKeyboard()
    injector = CodeInjector(
        async_mode=False,
        keyboard_controller=keyboard,
        clipboard_module=_FlakyClipboard(),
        paste_delay=0.0,
    )
    assert injector.insert_snippet("x = 1", async_exec=False) is False
    assert injector._active_modifiers == set()
    assert all(key not in keyboard.pressed_keys for key in injector._active_modifiers)


def test_clipboard_history_retries_reads():
    class FlakyHistoryClipboard:
        def __init__(self):
            self.calls = 0

        def paste(self):
            self.calls += 1
            if self.calls < 3:
                raise RuntimeError("clipboard locked")
            return "ready"

    manager = ClipboardHistoryManager(
        clipboard_module=FlakyHistoryClipboard(),
        poll_interval_ms=999999,
    )
    manager._last_seen = manager._read_clipboard()
    assert manager._last_seen == "ready"
    assert len(manager.get_items()) <= 6
    manager.stop()


# ---------------------------------------------------------------------------
# 3. Corrupt JSON / network resilience
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("payload", ["", "{bad_json", "[]", '{"mar_threshold": "texto_invalido"}'])
def test_settings_manager_recovers_from_corrupt_payloads(payload):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "user_settings.json"
        path.write_text(payload, encoding="utf-8")
        manager = SettingsManager(path=str(path))
        assert isinstance(manager.get("mar_threshold"), float)


@pytest.mark.parametrize("payload", ["", "{bad_json", "[]", '{"directions": "many"}'])
def test_game_profiles_recover_from_corrupt_payloads(payload):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "game_profiles.json"
        path.write_text(payload, encoding="utf-8")
        manager = GameProfileManager(path=str(path))
        assert manager.resolve_for_window("Chrome", "chrome.exe") == "default_desktop"
        assert isinstance(manager.get_profile("strategy_rpg")["directions"], int)


@pytest.mark.parametrize(
    "payload",
    [
        '{"total_mouth_clicks": "many", "cell_heatmap": ["x", null], "mode_usage_seconds": {"coding": "bad"}}',
        "[]",
        "{bad_json",
    ],
)
def test_telemetry_recovers_from_invalid_types(payload):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "telemetry.json"
        path.write_text(payload, encoding="utf-8")
        manager = TelemetryManager(path=str(path), usage_tick_ms=999999)
        assert manager.stats()["total_mouth_clicks"] == 0
        assert len(manager.stats()["cell_heatmap"]) == 9
        manager.stop()


@pytest.mark.parametrize("payload", ["", "{bad_json", "[]", '{"weights_x": "bad"}'])
def test_calibration_profile_recovers_from_corrupt_payloads(payload):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "calibration_profile.json"
        path.write_text(payload, encoding="utf-8")
        assert GazeEstimator().load_calibration_profile(str(path)) is False


def test_websocket_ignores_malformed_payload_without_raising():
    bridge = WebSocketBridge()
    bridge._process_inbound_message(["not", "a", "dict"], None)
    bridge._process_inbound_message(None, None)
    assert bridge.last_editor_state is None


# ---------------------------------------------------------------------------
# 4. Structural 3x3 invariants and UI overflow safety
# ---------------------------------------------------------------------------
def _all_menu_nodes():
    nodes = {}
    for language in ("PYTHON", "TYPESCRIPT", "RUST", "CPP", "GO"):
        for node_id, node in build_menu_tree(language).items():
            nodes[f"{language}:{node_id}"] = node

    mode_manager = ModeManager()
    for mode_id in getattr(mode_manager, "MODE_ORDER", ()):  # pragma: no branch
        mode = getattr(mode_manager, "get_mode", lambda _id: None)(mode_id)
        if mode is not None and hasattr(mode, "get_menu_tree"):
            for node_id, node in mode.get_menu_tree().items():
                nodes[f"{mode_id}:{node_id}"] = node

    nodes["AUTO_FIX"] = DiagnosticsFixer().get_autofix_menu_node()
    nodes["AST"] = ASTCodeJumper().get_symbols_menu_node([], 0)
    nodes["CLIPBOARD"] = ClipboardHistoryManager(poll_interval_ms=999999).get_clipboard_menu_node()
    nodes["AGENTIC"] = AgenticPromptLauncher().get_agentic_menu_node()
    for context in ("FUNCTION", "IF", "LOOP", "TRY", "GENERAL", "CLASS", "CALL"):
        nodes[f"ADAPTIVE:{context}"] = get_adaptive_context_node(
            context, build_menu_tree("PYTHON")["ROOT"]
        )
    return nodes


def test_all_3x3_nodes_preserve_pause_and_back_invariants():
    for name, node in _all_menu_nodes().items():
        assert len(node.items) == 9, name
        assert node.items[4].action_type == "PAUSE", name
        if node.id != "ROOT":
            assert node.items[6].action_type == "BACK", name


def test_overlay_renders_long_unicode_labels_without_crashing():
    overlay = OverlayWindow()
    overlay.resize(1280, 720)
    long_label = "Funcion_" + ("x" * 140) + "_ñ"
    node = MenuNode(
        id="LONG_LABELS",
        title="LONG LABELS",
        items=[
            type(overlay.menu_tree["ROOT"].items[0])(
                id=f"LONG_{i}",
                label=f"{i + 1}: {long_label}",
                hint=long_label,
                action_type="SNIPPET",
                snippet="",
            )
            for i in range(9)
        ],
        parent_id="ROOT",
    )
    overlay.menu_tree["LONG_LABELS"] = node
    overlay.navigate_to("LONG_LABELS")
    overlay.show()
    pixmap = overlay.grab()
    assert not pixmap.isNull()
    overlay.close()
