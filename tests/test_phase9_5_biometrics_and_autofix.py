"""Phase 9.5: diagnostics auto-fix, health guard and expressive gestures."""

import math
import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication

_APP = QApplication.instance() or QApplication(sys.argv)
from pathlib import Path
from typing import List

from ideye.actions.diagnostics_fixer import DiagnosticsFixer
from ideye.core.gesture_detector import GestureDetector
from ideye.core.health_guard import HealthGuard
from ideye.ui.overlay_window import OverlayWindow


class Point:
    def __init__(self, x: float, y: float):
        self.x = float(x)
        self.y = float(y)


class Face:
    def __init__(self):
        self.landmark: List[Point] = [Point(0.5, 0.5) for _ in range(478)]
        # neutral open eyes and closed mouth
        self.landmark[33] = Point(0.35, 0.50)
        self.landmark[263] = Point(0.65, 0.50)
        self.landmark[133] = Point(0.45, 0.50)
        self.landmark[362] = Point(0.55, 0.50)
        self.landmark[160] = Point(0.38, 0.48)
        self.landmark[158] = Point(0.42, 0.48)
        self.landmark[153] = Point(0.42, 0.52)
        self.landmark[144] = Point(0.38, 0.52)
        self.landmark[385] = Point(0.58, 0.48)
        self.landmark[387] = Point(0.62, 0.48)
        self.landmark[373] = Point(0.62, 0.52)
        self.landmark[380] = Point(0.58, 0.52)
        self.landmark[13] = Point(0.50, 0.65)
        self.landmark[14] = Point(0.50, 0.66)
        self.landmark[78] = Point(0.44, 0.66)
        self.landmark[308] = Point(0.56, 0.66)
        for idx in (65, 105, 295, 334):
            self.landmark[idx] = Point(0.5, 0.40)


class TestDiagnosticsFixer(unittest.TestCase):
    def setUp(self):
        self.fixer = DiagnosticsFixer()

    def test_name_error_generates_import_and_rename(self):
        fixes = self.fixer.generate_fixes(
            {"line": 3, "message": "NameError: name 'lenght' is not defined", "code_line": "return lenght"},
            {"symbols": ["length", "value"]},
        )
        self.assertTrue(any(f["kind"] == "import" and "import lenght" in f["replacement"] for f in fixes))
        self.assertTrue(any("length" in f["replacement"] for f in fixes))

    def test_colon_and_unclosed_delimiters(self):
        colon = self.fixer.generate_fixes({"line": 1, "message": "expected ':'", "code_line": "def foo()"})
        self.assertTrue(any(f["replacement"] == "def foo():" for f in colon))
        paren = self.fixer.generate_fixes({"line": 2, "message": "unclosed '('", "code_line": "print('x'"})
        self.assertTrue(any(f["replacement"].endswith(")") for f in paren))

    def test_autofix_menu_invariants(self):
        self.fixer.build_fixes([
            {"line": 1, "message": "expected ':'", "code_line": "if x"}
        ])
        node = self.fixer.get_autofix_menu_node()
        self.assertEqual(len(node.items), 9)
        self.assertEqual(node.items[4].action_type, "PAUSE")
        self.assertEqual(node.items[6].action_type, "BACK")

    def test_compile_fallback_detects_syntax_error(self):
        diagnostics = self.fixer.local_diagnostics("def broken(:\n    pass")
        self.assertEqual(len(diagnostics), 1)
        self.assertEqual(diagnostics[0]["source"], "python-compile")


class TestOverlayAutofix(unittest.TestCase):
    def test_diagnostics_expose_slot8_and_pause_back(self):
        overlay = OverlayWindow()
        overlay.set_diagnostics([
            {"line": 2, "severity": "error", "message": "expected ':'", "code_line": "if ready"}
        ])
        self.assertEqual(overlay.menu_tree["ROOT"].items[7].submenu_id, "AUTO_FIX")
        node = overlay.menu_tree["AUTO_FIX"]
        self.assertEqual(node.items[4].action_type, "PAUSE")
        self.assertEqual(node.items[6].action_type, "BACK")
        overlay.set_diagnostics([])
        overlay.close()

    def test_vscode_extension_source_contains_diagnostics_protocol(self):
        source = Path("vscode-extension/src/extension.ts").read_text(encoding="utf-8")
        self.assertIn("onDidChangeDiagnostics", source)
        self.assertIn("getDiagnostics", source)
        self.assertIn("apply_line_fix", source)
        self.assertIn("diagnostics:", source)


class TestHealthGuard(unittest.TestCase):
    def test_stare_alert_after_thirty_seconds(self):
        guard = HealthGuard(enabled=True, alert_cooldown_sec=0.0)
        face = Face()
        guard.set_baseline(face)
        guard.process(face, now=0.0)
        alert = guard.process(face, now=30.0)
        self.assertIsNotNone(alert)
        self.assertIn("parpadear", alert)

    def test_distance_alert_after_five_seconds(self):
        guard = HealthGuard(enabled=True, alert_cooldown_sec=0.0)
        face = Face()
        guard.set_baseline(face)
        guard.process(face, now=0.0)
        face.landmark[33] = Point(0.20, 0.50)
        face.landmark[263] = Point(0.80, 0.50)
        guard.process(face, now=1.0)
        alert = guard.process(face, now=6.1)
        self.assertIsNotNone(alert)
        self.assertIn("Demasiado cerca", alert)


class TestMicroGestures(unittest.TestCase):
    def test_brow_raise_emits_and_respects_cooldown(self):
        detector = GestureDetector(micro_gestures_enabled=True)
        face = Face()
        detector.process(face, current_time=10.0)
        for idx in (65, 105, 295, 334):
            face.landmark[idx] = Point(0.5, 0.32)
        detector.process(face, current_time=10.1)
        result = detector.process(face, current_time=10.35)
        self.assertIn("BROW_RAISE", result.gestures)
        again = detector.process(face, current_time=10.40)
        self.assertNotIn("BROW_RAISE", again.gestures)

    def test_head_tilt_emits_both_directions(self):
        detector = GestureDetector(micro_gestures_enabled=True)
        face = Face()
        face.landmark[33] = Point(0.35, 0.40)
        face.landmark[263] = Point(0.65, 0.60)
        detector.process(face, current_time=20.0)
        result = detector.process(face, current_time=20.35)
        self.assertIn("HEAD_TILT_RIGHT", result.gestures)
        # cooldown, then opposite direction
        face.landmark[33] = Point(0.35, 0.60)
        face.landmark[263] = Point(0.65, 0.40)
        detector.process(face, current_time=21.3)
        result = detector.process(face, current_time=21.65)
        self.assertIn("HEAD_TILT_LEFT", result.gestures)


if __name__ == "__main__":
    unittest.main()
