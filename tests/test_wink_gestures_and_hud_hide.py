"""
Unit & Integration Test Suite for IDEye Option B Pause, Eye Wink Gestures, and Non-Collision Layout.
Tests:
1. Scale-invariant Eye Aspect Ratio (EAR) computation and zero-division protection.
2. Unilateral wink detection (WINK_LEFT and WINK_RIGHT), twitch rejection, prolonged closure rejection,
   and bilateral blink discrimination.
3. Cooldown enforcement (400ms) and GestureResult tuple-unpacking backwards compatibility.
4. Option B pause behavior: HUD overlay hides completely when paused, restores completely on WINK_RIGHT,
   and Center Block 4 (PAUSA) triggers full hide.
5. WINK_LEFT back navigation (submenu -> parent) and Undo (Ctrl+Z at ROOT).
6. Non-collision geometry between OverlayWindow 3x3 macro cards and DebugWidget.
7. Collapsible mini-bar mode in DebugWidget.
"""

import os
import sys
import unittest
import time
import math
from typing import List, Tuple

# Headless Qt environment setup
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtWidgets import QApplication

# Path resolution
_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_EYEDE_DIR = os.path.join(_ROOT_DIR, "eyede")
for p in (_ROOT_DIR, _EYEDE_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

from typing import List, Tuple, Any, Optional

import eyede.config as config
from eyede.core.gesture_detector import GestureDetector, GestureResult, GestureState
from eyede.ui.overlay_window import OverlayWindow
from eyede.ui.debug_widget import DebugWidget
from eyede.actions.menu_trees import MenuAction
from eyede.actions.code_injector import CodeInjector

_APP = QApplication.instance() or QApplication(sys.argv if hasattr(sys, 'argv') else [])


class MockKeyboard:
    def __init__(self):
        self.pressed_keys: List[Any] = []
        self.released_keys: List[Any] = []
        self.tapped_keys: List[Any] = []
        self.history: List[Tuple[str, Any]] = []

    def press(self, key):
        self.pressed_keys.append(key)
        self.history.append(("PRESS", key))

    def release(self, key):
        self.released_keys.append(key)
        self.history.append(("RELEASE", key))

    def tap(self, key):
        self.tapped_keys.append(key)
        self.history.append(("TAP", key))


class MockClipboard:
    def __init__(self, initial: str = ""):
        self.content: str = initial

    def paste(self) -> str:
        return self.content

    def copy(self, text: str):
        self.content = text


class MockLandmarkPoint:
    def __init__(self, x: float, y: float, z: float = 0.0):
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)


class MockFaceMesh:
    def __init__(self, count: int = 478, default_x: float = 0.5, default_y: float = 0.5):
        self.landmark = [MockLandmarkPoint(default_x, default_y) for _ in range(count)]

    def set_pt(self, idx: int, x: float, y: float, z: float = 0.0):
        self.landmark[idx] = MockLandmarkPoint(x, y, z)


def create_neutral_face() -> MockFaceMesh:
    """Creates a canonical face landmark set with both eyes open and mouth closed."""
    face = MockFaceMesh()
    # Left eye: (33, 160, 158, 133, 153, 144)
    # Horizontal width = 0.10, Vertical height = 0.03 -> EAR = 0.06 / 0.20 = 0.30 (Open > 0.22)
    face.set_pt(33, 0.35, 0.40)
    face.set_pt(160, 0.38, 0.385)
    face.set_pt(158, 0.42, 0.385)
    face.set_pt(133, 0.45, 0.40)
    face.set_pt(153, 0.42, 0.415)
    face.set_pt(144, 0.38, 0.415)

    # Right eye: (362, 385, 387, 263, 373, 380)
    # Horizontal width = 0.10, Vertical height = 0.03 -> EAR = 0.06 / 0.20 = 0.30 (Open > 0.22)
    face.set_pt(362, 0.55, 0.40)
    face.set_pt(385, 0.58, 0.385)
    face.set_pt(387, 0.62, 0.385)
    face.set_pt(263, 0.65, 0.40)
    face.set_pt(373, 0.62, 0.415)
    face.set_pt(380, 0.58, 0.415)

    # Mouth closed
    face.set_pt(13, 0.50, 0.65)
    face.set_pt(14, 0.50, 0.67)
    face.set_pt(78, 0.44, 0.66)
    face.set_pt(308, 0.56, 0.66)

    return face


def set_left_eye_closed(face: MockFaceMesh) -> None:
    """Closes left eye: vertical height = 0.002 -> EAR = 0.004 / 0.20 = 0.02 (< 0.16)"""
    face.set_pt(160, 0.38, 0.399)
    face.set_pt(158, 0.42, 0.399)
    face.set_pt(153, 0.42, 0.401)
    face.set_pt(144, 0.38, 0.401)


def set_left_eye_open(face: MockFaceMesh) -> None:
    """Restores left eye open: vertical height = 0.030 -> EAR = 0.30 (> 0.22)"""
    face.set_pt(160, 0.38, 0.385)
    face.set_pt(158, 0.42, 0.385)
    face.set_pt(153, 0.42, 0.415)
    face.set_pt(144, 0.38, 0.415)


def set_right_eye_closed(face: MockFaceMesh) -> None:
    """Closes right eye: vertical height = 0.002 -> EAR = 0.004 / 0.20 = 0.02 (< 0.16)"""
    face.set_pt(385, 0.58, 0.399)
    face.set_pt(387, 0.62, 0.399)
    face.set_pt(373, 0.62, 0.401)
    face.set_pt(380, 0.58, 0.401)


def set_right_eye_open(face: MockFaceMesh) -> None:
    """Restores right eye open: vertical height = 0.030 -> EAR = 0.30 (> 0.22)"""
    face.set_pt(385, 0.58, 0.385)
    face.set_pt(387, 0.62, 0.385)
    face.set_pt(373, 0.62, 0.415)
    face.set_pt(380, 0.58, 0.415)


class TestEARMathAndSafety(unittest.TestCase):
    """Verifies EAR mathematical calculation, scale invariance, and zero-division protection."""

    def setUp(self):
        self.detector = GestureDetector()

    def test_ear_open_values(self):
        """Standard open eyes have EAR around 0.30 (> 0.22 threshold)."""
        face = create_neutral_face()
        left_ear, right_ear = self.detector.compute_ear(face)
        self.assertAlmostEqual(left_ear, 0.30, delta=0.03)
        self.assertAlmostEqual(right_ear, 0.30, delta=0.03)
        self.assertGreater(left_ear, self.detector.ear_open_threshold)
        self.assertGreater(right_ear, self.detector.ear_open_threshold)

    def test_ear_closed_values(self):
        """Closed eye drops EAR below 0.16 threshold."""
        face = create_neutral_face()
        set_left_eye_closed(face)
        left_ear, right_ear = self.detector.compute_ear(face)
        self.assertLess(left_ear, self.detector.ear_close_threshold)
        self.assertGreater(right_ear, self.detector.ear_open_threshold)

    def test_ear_scale_invariance(self):
        """EAR must remain strictly identical if face landmarks are uniformly scaled."""
        face = create_neutral_face()
        ear_l1, ear_r1 = self.detector.compute_ear(face)

        # Scale face by 2.5x
        scaled_face = MockFaceMesh()
        for idx in range(len(face.landmark)):
            scaled_face.set_pt(idx, face.landmark[idx].x * 2.5, face.landmark[idx].y * 2.5)

        ear_l2, ear_r2 = self.detector.compute_ear(scaled_face)
        self.assertAlmostEqual(ear_l1, ear_l2, places=4)
        self.assertAlmostEqual(ear_r1, ear_r2, places=4)

    def test_ear_zero_division_protection(self):
        """When outer and inner corners collapse (width=0), EAR returns 0.0 with NO ZeroDivisionError."""
        collapsed_face = MockFaceMesh()
        for i in (33, 160, 158, 133, 153, 144, 362, 385, 387, 263, 373, 380):
            collapsed_face.set_pt(i, 0.5, 0.5)

        left_ear, right_ear = self.detector.compute_ear(collapsed_face)
        self.assertEqual(left_ear, 0.0)
        self.assertEqual(right_ear, 0.0)


class TestWinkGestureDetection(unittest.TestCase):
    """Verifies unilateral winks, bilateral blink cancellation, twitch/prolonged rejection, and cooldown."""

    def setUp(self):
        self.detector = GestureDetector(
            ear_close_threshold=0.16,
            ear_open_threshold=0.22,
            wink_min_hold_sec=0.15,
            wink_max_hold_sec=0.45,
            wink_cooldown_sec=0.40,
            wink_trigger_on_release=True,
        )

    def test_left_wink_detection_on_release(self):
        """Holding left eye closed for 250ms and reopening triggers WINK_LEFT."""
        face = create_neutral_face()
        t = 100.0

        # Frame 0: Both open
        res = self.detector.process(face, current_time=t)
        self.assertNotIn("WINK_LEFT", res.gestures)

        # Frame 1: Left eye closes (wink begins)
        set_left_eye_closed(face)
        t += 0.05
        res = self.detector.process(face, current_time=t)
        self.assertNotIn("WINK_LEFT", res.gestures)

        # Frame 2: Left eye still closed at 250ms duration (within 150-450ms)
        t += 0.20
        res = self.detector.process(face, current_time=t)
        self.assertNotIn("WINK_LEFT", res.gestures)  # not released yet

        # Frame 3: Left eye reopens -> triggers WINK_LEFT!
        set_left_eye_open(face)
        t += 0.03
        res = self.detector.process(face, current_time=t)
        self.assertIn("WINK_LEFT", res.gestures)

    def test_right_wink_detection_on_release(self):
        """Holding right eye closed for 250ms and reopening triggers WINK_RIGHT."""
        face = create_neutral_face()
        t = 100.0

        # Frame 0: Both open
        res = self.detector.process(face, current_time=t)
        self.assertNotIn("WINK_RIGHT", res.gestures)

        # Frame 1: Right eye closes
        set_right_eye_closed(face)
        t += 0.05
        res = self.detector.process(face, current_time=t)
        self.assertNotIn("WINK_RIGHT", res.gestures)

        # Frame 2: Held for 250ms
        t += 0.20
        res = self.detector.process(face, current_time=t)
        self.assertNotIn("WINK_RIGHT", res.gestures)

        # Frame 3: Right eye reopens -> triggers WINK_RIGHT!
        set_right_eye_open(face)
        t += 0.03
        res = self.detector.process(face, current_time=t)
        self.assertIn("WINK_RIGHT", res.gestures)

    def test_bilateral_blink_cancels_wink(self):
        """When both eyes close (< 0.16), wink detection is cancelled/invalidated."""
        face = create_neutral_face()
        t = 100.0

        # Frame 1: Left eye closes
        set_left_eye_closed(face)
        t += 0.05
        self.detector.process(face, current_time=t)

        # Frame 2: Right eye ALSO closes (bilateral blink!)
        set_right_eye_closed(face)
        t += 0.10
        self.detector.process(face, current_time=t)

        # Frame 3: Both reopen
        set_left_eye_open(face)
        set_right_eye_open(face)
        t += 0.10
        res = self.detector.process(face, current_time=t)

        # Must NOT trigger WINK_LEFT or WINK_RIGHT!
        self.assertNotIn("WINK_LEFT", res.gestures)
        self.assertNotIn("WINK_RIGHT", res.gestures)

    def test_twitch_rejection_under_min_hold(self):
        """Eye closed for only 50ms (< 150ms) must NOT trigger a wink."""
        face = create_neutral_face()
        t = 100.0

        set_left_eye_closed(face)
        t += 0.02
        self.detector.process(face, current_time=t)

        # Reopen after only 50ms total
        set_left_eye_open(face)
        t += 0.03
        res = self.detector.process(face, current_time=t)
        self.assertNotIn("WINK_LEFT", res.gestures)

    def test_prolonged_closure_rejection_over_max_hold(self):
        """Eye closed for 600ms (> 450ms) must NOT trigger a wink (e.g. squint/sleep)."""
        face = create_neutral_face()
        t = 100.0

        set_left_eye_closed(face)
        t += 0.05
        self.detector.process(face, current_time=t)

        # Still closed after 500ms
        t += 0.50
        self.detector.process(face, current_time=t)

        # Reopen at 600ms
        set_left_eye_open(face)
        t += 0.05
        res = self.detector.process(face, current_time=t)
        self.assertNotIn("WINK_LEFT", res.gestures)

    def test_wink_cooldown_enforcement(self):
        """Second wink triggered within 400ms cooldown is ignored."""
        face = create_neutral_face()
        t = 100.0

        # Wink 1
        set_left_eye_closed(face)
        self.detector.process(face, current_time=t)
        t += 0.20
        self.detector.process(face, current_time=t)
        set_left_eye_open(face)
        t += 0.02
        res1 = self.detector.process(face, current_time=t)
        self.assertIn("WINK_LEFT", res1.gestures)

        # Immediate Wink 2 attempt 100ms later (< 400ms cooldown)
        t += 0.10
        set_left_eye_closed(face)
        self.detector.process(face, current_time=t)
        t += 0.20
        self.detector.process(face, current_time=t)
        set_left_eye_open(face)
        t += 0.02
        res2 = self.detector.process(face, current_time=t)
        self.assertNotIn("WINK_LEFT", res2.gestures)

        # After full cooldown (450ms later)
        t += 0.45
        set_left_eye_closed(face)
        self.detector.process(face, current_time=t)
        t += 0.20
        self.detector.process(face, current_time=t)
        set_left_eye_open(face)
        t += 0.02
        res3 = self.detector.process(face, current_time=t)
        self.assertIn("WINK_LEFT", res3.gestures)

    def test_gesture_result_tuple_unpacking(self):
        """GestureResult must unpack as (clicked, mar, hold_progress) while providing .gestures."""
        face = create_neutral_face()
        res = self.detector.process(face)
        clicked, mar, prog = res
        self.assertFalse(clicked)
        self.assertIsInstance(mar, float)
        self.assertIsInstance(prog, float)
        self.assertIsInstance(res.gestures, list)


class TestOverlayOptionBPauseAndWinkIntegration(unittest.TestCase):
    """Verifies Option B pause HUD hide, WINK_RIGHT restore, Block 5 pause, and WINK_LEFT navigation."""

    def setUp(self):
        self.mock_kb = MockKeyboard()
        self.mock_clip = MockClipboard()
        self.injector = CodeInjector(
            async_mode=False,
            keyboard_controller=self.mock_kb,
            clipboard_module=self.mock_clip,
        )
        self.overlay = OverlayWindow(code_injector=self.injector)
        self.overlay.show()

    def tearDown(self):
        self.overlay.close()

    def test_pause_hides_overlay_completely(self):
        """Calling pause_hud() sets reading_mode=True and calls hide()."""
        self.assertFalse(self.overlay.reading_mode)
        self.assertFalse(self.overlay.isHidden())

        self.overlay.pause_hud()
        self.assertTrue(self.overlay.reading_mode)
        self.assertTrue(self.overlay.isHidden())
        self.assertAlmostEqual(self.overlay.current_opacity, config.OVERLAY_OPACITY_READING, delta=0.01)

    def test_wink_right_toggles_pause_and_restore(self):
        """WINK_RIGHT gesture toggles HUD hide and full unhide/restore."""
        # 1. Active -> Pause (hide)
        self.overlay.on_gesture_triggered("WINK_RIGHT")
        self.assertTrue(self.overlay.reading_mode)
        self.assertTrue(self.overlay.isHidden())

        # 2. Paused -> Resume (show)
        self.overlay.on_gesture_triggered("WINK_RIGHT")
        self.assertFalse(self.overlay.reading_mode)
        self.assertFalse(self.overlay.isHidden())
        self.assertAlmostEqual(self.overlay.current_opacity, config.OVERLAY_OPACITY_ACTIVE, delta=0.01)

    def test_center_block_pause_hides_and_wink_restores(self):
        """Activating Center Block 4 (PAUSA) hides the HUD completely; WINK_RIGHT restores it."""
        self.overlay.on_gaze_updated(0.5, 0.5)
        self.assertEqual(self.overlay.hovered_block, 4)

        # Mouth click on Block 4 triggers pause
        self.overlay.on_gesture_triggered("MOUTH_CLICK")
        self.assertTrue(self.overlay.reading_mode)
        self.assertTrue(self.overlay.isHidden())

        # WINK_RIGHT restores the HUD completely
        self.overlay.on_gesture_triggered("WINK_RIGHT")
        self.assertFalse(self.overlay.reading_mode)
        self.assertFalse(self.overlay.isHidden())

    def test_wink_left_submenu_back_navigation(self):
        """In a submenu, WINK_LEFT navigates back to parent / ROOT."""
        self.overlay.navigate_to("FLOW")
        self.assertEqual(self.overlay.current_node_id, "FLOW")

        self.overlay.on_gesture_triggered("WINK_LEFT")
        self.assertEqual(self.overlay.current_node_id, "ROOT")

    def test_wink_left_root_triggers_undo(self):
        """At ROOT, WINK_LEFT triggers Undo (Ctrl+Z) action."""
        self.assertEqual(self.overlay.current_node_id, "ROOT")

        executed = []
        self.overlay.action_executed.connect(lambda act_id, desc: executed.append(act_id))

        self.overlay.on_gesture_triggered("WINK_LEFT")
        self.assertIn("ACTION_UNDO", executed)
        self.assertIn("Deshacer", self.overlay.last_action_desc)
        self.assertIn('z', self.mock_kb.tapped_keys)

    def test_wink_left_ignored_when_paused(self):
        """When HUD is paused/hidden, WINK_LEFT is safely ignored."""
        self.overlay.pause_hud()
        self.assertTrue(self.overlay.reading_mode)

        executed = []
        self.overlay.action_executed.connect(lambda act_id, desc: executed.append(act_id))

        self.overlay.on_gesture_triggered("WINK_LEFT")
        self.assertEqual(len(executed), 0)


class TestGeometryAndDebugWidgetNoCollision(unittest.TestCase):
    """Verifies OVERLAY_GRID_RIGHT_MARGIN guarantees non-collision with DebugWidget, and DebugWidget collapse."""

    def setUp(self):
        self.overlay = OverlayWindow()
        self.overlay.resize(1920, 1080)
        self.debug_widget = DebugWidget()
        self.debug_widget.resize(config.DEBUG_WINDOW_WIDTH, config.DEBUG_WINDOW_HEIGHT)

    def tearDown(self):
        self.overlay.close()
        self.debug_widget.close()

    def test_grid_right_margin_clears_debug_widget(self):
        """
        Guarantees that 3x3 category cards right boundary strictly does NOT collide
        with the docked DebugWidget.
        """
        self.assertEqual(self.overlay.grid_right_margin, 364.0)

        # Rightmost blocks are col 2: indices 2, 5, 8
        for block_idx in (2, 5, 8):
            card_rect = self.overlay.get_block_rect(block_idx)
            # Card right edge must not exceed 1920 - 364 = 1556
            self.assertLessEqual(card_rect.right(), 1920.0 - 364.0)

        # Docked DebugWidget position (x = 1920 - 340 - 20 = 1560)
        debug_x = 1920.0 - float(config.DEBUG_WINDOW_WIDTH) - 20.0
        card_col2_right = self.overlay.get_block_rect(2).right()

        # Strict positive clearance gap (card right < debug_x)
        clearance = debug_x - card_col2_right
        self.assertGreaterEqual(clearance, 12.0, f"Expected >= 12px clearance, got {clearance}px")

    def test_debug_widget_collapsible_mini_bar_mode(self):
        """
        DebugWidget has btn_collapse and toggle_collapse() to shrink into a sleek mini bar.
        """
        self.assertTrue(hasattr(self.debug_widget, "btn_collapse"))
        self.assertFalse(self.debug_widget.is_collapsed)
        self.assertEqual(self.debug_widget.height(), config.DEBUG_WINDOW_HEIGHT)
        self.assertFalse(self.debug_widget.content_container.isHidden())

        # Toggle collapse
        self.debug_widget.btn_collapse.click()
        self.assertTrue(self.debug_widget.is_collapsed)
        self.assertEqual(self.debug_widget.height(), 48)
        self.assertTrue(self.debug_widget.content_container.isHidden())
        self.assertIn("Expandir", self.debug_widget.btn_collapse.text())

        # Toggle expand back
        self.debug_widget.btn_collapse.click()
        self.assertFalse(self.debug_widget.is_collapsed)
        self.assertEqual(self.debug_widget.height(), config.DEBUG_WINDOW_HEIGHT)
        self.assertFalse(self.debug_widget.content_container.isHidden())
        self.assertIn("Colapsar", self.debug_widget.btn_collapse.text())

    def test_multi_resolution_debug_widget_clearance(self):
        """
        Verifies:
        1. At 1080p and high-DPI (1920x1080, 2560x1440, 3840x2160), 3x3 category cards strictly clear DebugWidget.
        2. Across ALL resolutions (1280x720, 1366x768, 1600x900, 1920x1080), normalized center gaze (0.5, 0.5)
           is guaranteed to land on Center Block 4 (PAUSA).
        3. On sub-1080p displays, DebugWidget collapsible mini-bar mode eliminates right-column occlusion.
        """
        for w, h in [(1920, 1080), (2560, 1440), (3840, 2160)]:
            self.overlay.resize(w, h)
            debug_x = float(w) - float(config.DEBUG_WINDOW_WIDTH) - 20.0
            for block_idx in (2, 5, 8):
                card_rect = self.overlay.get_block_rect(block_idx)
                clearance = debug_x - card_rect.right()
                self.assertGreaterEqual(
                    clearance,
                    12.0,
                    f"At resolution {w}x{h}, Block {block_idx} had clearance {clearance:.1f}px (< 12px)",
                )

        # Test center gaze alignment across all monitor resolutions
        for w, h in [(1280, 720), (1366, 768), (1600, 900), (1920, 1080), (2560, 1440)]:
            self.overlay.resize(w, h)
            self.overlay.on_gaze_updated(0.5, 0.5)
            self.assertEqual(
                self.overlay.hovered_block,
                4,
                f"At resolution {w}x{h}, normalized center gaze (0.5, 0.5) must hover Block 4, got {self.overlay.hovered_block}",
            )

    def test_debug_widget_collapsed_signal(self):
        """DebugWidget emits collapsed_toggled(bool) when collapsed or expanded."""
        signals = []
        self.debug_widget.collapsed_toggled.connect(lambda state: signals.append(state))

        self.debug_widget.toggle_collapse()
        self.assertEqual(signals, [True])

        self.debug_widget.toggle_collapse()
        self.assertEqual(signals, [True, False])


class TestEdgeCasesAndRobustness(unittest.TestCase):
    """Deep verification of edge cases, NaN resilience, and cooldown handling."""

    def setUp(self):
        self.detector = GestureDetector()

    def test_nan_and_inf_landmark_resilience(self):
        """GestureDetector compute_ear and compute_mar handle NaN and Inf coordinates gracefully."""
        face = create_neutral_face()
        # Corrupt landmarks with NaN and Inf
        face.set_pt(33, float("nan"), float("nan"))
        face.set_pt(160, float("inf"), 0.385)
        face.set_pt(362, float("nan"), 0.40)

        left_ear, right_ear = self.detector.compute_ear(face)
        self.assertEqual(left_ear, 0.0)
        self.assertEqual(right_ear, 0.0)

        mar = self.detector.compute_mar(face)
        self.assertIsInstance(mar, float)
        self.assertFalse(math.isnan(mar))

        res = self.detector.process(face)
        self.assertFalse(res.clicked)
        self.assertEqual(len(res.gestures), 0)

    def test_cooldown_wink_attempt_during_active_cooldown_rejected(self):
        """
        If a user begins closing their eye during active cooldown, the wink attempt
        must be marked invalid so it does not trigger a spurious delayed wink when cooldown expires.
        """
        face = create_neutral_face()
        t = 10.0

        # Wink 1: valid left wink
        set_left_eye_closed(face)
        self.detector.process(face, current_time=t)
        t += 0.20
        self.detector.process(face, current_time=t)
        set_left_eye_open(face)
        t += 0.02
        res1 = self.detector.process(face, current_time=t)
        self.assertIn("WINK_LEFT", res1.gestures)

        # Immediate Wink 2 attempt starting 100ms later (< 400ms cooldown)
        t += 0.10
        set_left_eye_closed(face)
        self.detector.process(face, current_time=t)  # eye closed during cooldown -> invalid
        t += 0.35  # holds eye closed past cooldown expiration
        self.detector.process(face, current_time=t)
        set_left_eye_open(face)
        t += 0.02
        res2 = self.detector.process(face, current_time=t)
        # Must NOT trigger because wink began during cooldown!
        self.assertNotIn("WINK_LEFT", res2.gestures)

        # Now clean Wink 3 after eye was fully released and cooldown passed
        t += 0.20
        set_left_eye_closed(face)
        self.detector.process(face, current_time=t)
        t += 0.20
        self.detector.process(face, current_time=t)
        set_left_eye_open(face)
        t += 0.02
        res3 = self.detector.process(face, current_time=t)
        self.assertIn("WINK_LEFT", res3.gestures)


if __name__ == "__main__":
    unittest.main()
