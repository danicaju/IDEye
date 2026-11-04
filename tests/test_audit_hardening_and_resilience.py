"""
IDEye - Audit Hardening & Error-Proofing Test Suite.
Validates resilience against malformed diagnostics, monotonic timing coherency,
zero-division guards, and boundary safety in menu trees.
"""

import time
import unittest
from unittest.mock import MagicMock

from ideye.actions.diagnostics_fixer import DiagnosticsFixer, _safe_int_line
from ideye.actions.menu_trees import MenuAction, MenuNode
from ideye.core.gaze_estimator import GazeEstimator
from ideye.modes.ide_nav_mode import IdeNavMode
from ideye.modes.terminal_git_mode import TerminalGitMode
from ideye.ui.sniper_lens import SniperLens


class TestAuditHardeningAndResilience(unittest.TestCase):
    def test_safe_int_line_edge_cases(self):
        self.assertEqual(_safe_int_line(10), 10)
        self.assertEqual(_safe_int_line("42"), 42)
        self.assertEqual(_safe_int_line("12.8"), 12)
        self.assertEqual(_safe_int_line(None, default=5), 5)
        self.assertEqual(_safe_int_line("", default=1), 1)
        self.assertEqual(_safe_int_line("invalid_line", default=1), 1)
        self.assertEqual(_safe_int_line(-5, default=1), 1)
        self.assertEqual(_safe_int_line(0, default=1), 1)
        self.assertEqual(_safe_int_line([1, 2, 3], default=1), 1)
        self.assertEqual(_safe_int_line({"line": 1}, default=1), 1)

    def test_diagnostics_fixer_malformed_lines_never_raises(self):
        fixer = DiagnosticsFixer()
        malformed_diagnostics = [
            {"message": "name 'foo' is not defined", "line": None},
            {"message": "name 'bar' is not defined", "line": "invalid_line_str"},
            {"message": "name 'baz' is not defined", "line": ""},
            {"message": "name 'qux' is not defined", "line": -10},
            {"message": "SyntaxError: invalid syntax", "line": "99.4"},
            {"message": "Undefined name 'my_var'"},
        ]
        for diag in malformed_diagnostics:
            fixes = fixer.generate_fixes(diag, context_data={"cursor_line": "not_an_int"})
            self.assertIsInstance(fixes, list)
            for fix in fixes:
                self.assertGreaterEqual(fix["line"], 1)

    def test_sniper_lens_monotonic_timing_coherency(self):
        lens = SniperLens(fixation_hold_sec=0.20, auto_fixation=True)
        lens.activate(200.0, 200.0)
        self.assertIsNotNone(lens._anchor_since)

        # Ensure that update_gaze without explicit now uses perf_counter and does not jump
        t0 = time.perf_counter()
        time.sleep(0.01)
        lens.update_gaze(200.0, 200.0)
        delta = time.perf_counter() - lens._anchor_since
        self.assertLess(delta, 5.0, "Delta between activate and update_gaze must be seconds, not epoch time")

    def test_gaze_estimator_zero_anchor_weights_resilience(self):
        estimator = GazeEstimator()
        # Mock 478 landmarks with non-default coords
        dummy_landmarks = [MagicMock(x=0.35, y=0.45, z=0.0) for _ in range(478)]

        # Zero weights guard test
        original_weights = estimator.head_anchor_weights
        try:
            estimator.head_anchor_weights = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
            cx, cy = estimator._extract_head_pos(dummy_landmarks)
            self.assertTrue(0.0 <= cx <= 1.0)
            self.assertTrue(0.0 <= cy <= 1.0)
        finally:
            estimator.head_anchor_weights = original_weights

    def test_refactored_terminal_git_and_ide_nav_modes(self):
        nav_mode = IdeNavMode()
        nav_tree = nav_mode.get_menu_tree()
        self.assertIn("ROOT", nav_tree)
        self.assertEqual(len(nav_tree["ROOT"].items), 9)

        term_mode = TerminalGitMode()
        term_tree = term_mode.get_menu_tree()
        self.assertIn("ROOT", term_tree)
        self.assertEqual(len(term_tree["ROOT"].items), 9)


if __name__ == "__main__":
    unittest.main()
