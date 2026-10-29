"""
Automated Test Suite: Pure Iris Tracking & Hands-Free Safe Exit
Tests:
1. GazeEstimator tracking modes (PURE_IRIS, HYBRID, HEAD_PRIMARY), horizontal expansion curve,
   and VOR compensation.
2. Safe Exit Confirmation 3x3 menu node integrity and ergonomic safety rules.
3. OverlayWindow hands-free header exit hover and gesture triggering.
4. IconManager vector SVG loading, rendering, and fallback behavior.
5. DebugWidget tracking mode cycling and UI control.
"""

import os
import sys
import json
import math
import tempfile
import unittest
from unittest.mock import MagicMock, patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtCore import Qt, QRect, QPointF
from PyQt6.QtWidgets import QApplication

# Path resolution
_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_IDEYE_DIR = os.path.join(_ROOT_DIR, "ideye")
for p in (_ROOT_DIR, _IDEYE_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

import ideye.config as config
from ideye.core.gaze_estimator import (
    GazeEstimator,
    TRACKING_MODE_PURE_IRIS,
    TRACKING_MODE_HYBRID,
    TRACKING_MODE_HEAD_PRIMARY,
)
from ideye.actions.menu_trees import (
    build_menu_tree,
    validate_menu_tree,
    populate_exit_confirm_items,
    MenuNode,
    MenuAction,
)
from ideye.ui.icon_manager import IconManager
from ideye.ui.overlay_window import OverlayWindow
from ideye.ui.debug_widget import DebugWidget, DebugMonitorWidget


_APP = QApplication.instance() or QApplication(sys.argv if hasattr(sys, "argv") else [])


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
    """Returns a synthetic neutral face with canonical landmark locations."""
    face = MockFaceMesh()
    # Nose tip
    face.set_pt(1, 0.50, 0.50)

    # Left eye outer (33) and inner (133), top (159), bottom (145), iris (468)
    face.set_pt(33, 0.35, 0.40)
    face.set_pt(133, 0.45, 0.40)
    face.set_pt(159, 0.40, 0.38)
    face.set_pt(145, 0.40, 0.42)
    face.set_pt(468, 0.40, 0.40)

    # Right eye inner (362) and outer (263), top (386), bottom (374), iris (473)
    face.set_pt(362, 0.55, 0.40)
    face.set_pt(263, 0.65, 0.40)
    face.set_pt(386, 0.60, 0.38)
    face.set_pt(374, 0.60, 0.42)
    face.set_pt(473, 0.60, 0.40)
    return face


class TestTrackingModes(unittest.TestCase):
    """Verifies Pure Iris, Hybrid, and Head Primary tracking modes in GazeEstimator."""

    def setUp(self):
        self.estimator = GazeEstimator(tracking_mode=TRACKING_MODE_PURE_IRIS)

    def test_pure_iris_mode_ignores_head_movement(self):
        """In PURE_IRIS mode, moving only the head (nose tip and facial contours) must produce 0 contribution."""
        neutral_face = create_neutral_face()
        # Initialize neutral position
        self.estimator.estimate(neutral_face)

        # Move only the nose tip (landmark 1) by +0.15 horizontally (pure head yaw)
        head_turned_face = create_neutral_face()
        head_turned_face.set_pt(1, 0.65, 0.50)

        # In PURE_IRIS mode, head movement delta must be 0
        raw_x, raw_y = self.estimator.get_raw_gaze(head_turned_face)
        # Should remain at center (0.5, 0.5) because iris landmarks did not move relative to eye corners
        self.assertAlmostEqual(raw_x, 0.50, delta=0.02)
        self.assertAlmostEqual(raw_y, 0.50, delta=0.02)

    def test_pure_iris_mode_responds_strongly_to_iris_glance(self):
        """In PURE_IRIS mode, shifting only iris landmarks produces immediate horizontal response."""
        neutral_face = create_neutral_face()
        self.estimator.estimate(neutral_face)

        # Glance right: move iris landmarks 468 and 473 towards outer corners
        glance_right_face = create_neutral_face()
        # Normal left eye width = 0.45 - 0.35 = 0.10. Move iris from 0.40 to 0.43 (+0.03 = +30% of eye width)
        glance_right_face.set_pt(468, 0.43, 0.40)
        glance_right_face.set_pt(473, 0.63, 0.40)

        raw_x, _ = self.estimator.get_raw_gaze(glance_right_face)
        # With horizontal multiplier and expansion, raw_x should shift significantly to the right (> 0.70)
        self.assertGreater(raw_x, 0.70, f"Expected raw_x > 0.70 for 30% eye glance, got {raw_x}")

    def test_horizontal_expansion_curve_mathematical_properties(self):
        """Tests symmetry, monotonicity, and expansion of _apply_horizontal_expansion_curve."""
        curve = self.estimator._apply_horizontal_expansion_curve

        # 1. Zero center invariant
        self.assertAlmostEqual(curve(0.0), 0.0)

        # 2. Anti-symmetry
        for val in [0.05, 0.1, 0.2, 0.35, 0.5]:
            self.assertAlmostEqual(curve(-val), -curve(val), places=6)

        # 3. Monotonicity
        inputs = [-0.6, -0.4, -0.2, -0.05, 0.0, 0.05, 0.2, 0.4, 0.6]
        outputs = [curve(x) for x in inputs]
        for i in range(len(outputs) - 1):
            self.assertLess(outputs[i], outputs[i + 1])

        # 4. Expansion factor: for non-zero glances, |curve(x)| > |x|
        for val in [0.1, 0.2, 0.3, 0.5]:
            self.assertGreater(abs(curve(val)), abs(val))

    def test_hybrid_mode_with_vor_compensation(self):
        """In HYBRID mode, VOR counter-rotation compensates for opposing iris and head vectors."""
        hybrid_est = GazeEstimator(tracking_mode=TRACKING_MODE_HYBRID)
        neutral_face = create_neutral_face()
        hybrid_est.estimate(neutral_face)

        # Head turns right (+0.10), iris counter-rotates left (-0.02) to maintain fixation (classic VOR)
        comb_dx, _ = hybrid_est._compute_combined_deltas(
            delta_head_x=0.10,
            delta_head_y=0.0,
            delta_iris_x=-0.02,
            delta_iris_y=0.0,
        )
        self.assertIsNotNone(comb_dx)
        self.assertFalse(math.isnan(comb_dx))
        self.assertGreater(comb_dx, 0.0)

        # Mathematical verification: VOR compensation must REDUCE opposing cancellation,
        # so output must be greater than raw uncompensated fusion
        uncomp_fusion_x = (hybrid_est.head_weight * 0.10) + (hybrid_est.iris_weight * -0.02)
        uncomp_expanded_x = hybrid_est._apply_horizontal_expansion_curve(uncomp_fusion_x)
        self.assertGreater(comb_dx, uncomp_expanded_x, "VOR compensation should mitigate counter-rotation cancellation!")

    def test_nan_and_inf_resilience_in_tracking_modes(self):
        """Non-finite inputs (NaN, inf) must be guarded against and not poison filter states."""
        for mode in [TRACKING_MODE_PURE_IRIS, TRACKING_MODE_HYBRID, TRACKING_MODE_HEAD_PRIMARY]:
            self.estimator.set_tracking_mode(mode)
            dx, dy = self.estimator._compute_combined_deltas(float('nan'), float('inf'), float('-inf'), float('nan'))
            self.assertTrue(math.isfinite(dx))
            self.assertTrue(math.isfinite(dy))
            self.assertEqual(dx, 0.0)
            self.assertEqual(dy, 0.0)

    def test_head_primary_mode(self):
        """In HEAD_PRIMARY mode, head motion dominates over iris (95% vs 5%)."""
        head_est = GazeEstimator(tracking_mode=TRACKING_MODE_HEAD_PRIMARY)
        comb_head_dx, _ = head_est._compute_combined_deltas(
            delta_head_x=0.10,
            delta_head_y=0.0,
            delta_iris_x=0.0,
            delta_iris_y=0.0,
        )
        comb_iris_dx, _ = head_est._compute_combined_deltas(
            delta_head_x=0.0,
            delta_head_y=0.0,
            delta_iris_x=0.10,
            delta_iris_y=0.0,
        )
        # Head contribution is significantly larger than iris contribution (95% vs 5%)
        self.assertGreater(comb_head_dx, comb_iris_dx * 10)

    def test_set_and_cycle_tracking_mode(self):
        """Verify dynamic mode setting and validation."""
        self.estimator.set_tracking_mode(TRACKING_MODE_HYBRID)
        self.assertEqual(self.estimator.tracking_mode, TRACKING_MODE_HYBRID)

        self.estimator.set_tracking_mode(TRACKING_MODE_HEAD_PRIMARY)
        self.assertEqual(self.estimator.tracking_mode, TRACKING_MODE_HEAD_PRIMARY)

        self.estimator.set_tracking_mode("NON_EXISTENT_MODE")
        # Should fallback to safe default HYBRID
        self.assertEqual(self.estimator.tracking_mode, TRACKING_MODE_HYBRID)

    def test_dual_calibration_captures_head_and_iris_bounds(self):
        points = []
        screens = [(0.5, 0.5), (0.1, 0.1), (0.9, 0.1), (0.1, 0.9), (0.9, 0.9)]
        heads = [(0.50, 0.50), (0.30, 0.30), (0.70, 0.30), (0.30, 0.70), (0.70, 0.70)]
        irises = [(0.50, 0.50), (0.40, 0.40), (0.60, 0.40), (0.40, 0.60), (0.60, 0.60)]
        for idx, (screen, head, iris) in enumerate(zip(screens, heads, irises)):
            points.append({
                "id": "CENTER" if idx == 0 else str(idx),
                "screen": screen,
                "raw": head,
                "raw_head": head,
                "raw_iris": iris,
            })
        est = GazeEstimator()
        self.assertTrue(est.calibrate_5_points(points))
        self.assertTrue(est.has_dual_calibration)
        self.assertIsNotNone(est.head_bounds)
        self.assertIsNotNone(est.iris_bounds)
        center_head = est._map_dual_source(0.50, 0.50, est.head_bounds, est.calib_head_linear_x, est.calib_head_linear_y)
        center_iris = est._map_dual_source(0.50, 0.50, est.iris_bounds, est.calib_iris_linear_x, est.calib_iris_linear_y)
        self.assertAlmostEqual(center_head[0], 0.5, delta=0.02)
        self.assertAlmostEqual(center_head[1], 0.5, delta=0.02)
        self.assertAlmostEqual(center_iris[0], 0.5, delta=0.02)
        self.assertAlmostEqual(center_iris[1], 0.5, delta=0.02)

    def test_mode_switch_keeps_dual_calibrated_center_stable(self):
        est = GazeEstimator()
        est.has_dual_calibration = True
        est.head_bounds = (0.40, 0.60, 0.40, 0.60)
        est.iris_bounds = (0.45, 0.55, 0.45, 0.55)
        est.calib_head_linear_x = (0.0, 1.0)
        est.calib_head_linear_y = (0.0, 1.0)
        est.calib_iris_linear_x = (0.0, 1.0)
        est.calib_iris_linear_y = (0.0, 1.0)
        face = create_neutral_face()
        for mode in (TRACKING_MODE_HEAD_PRIMARY, TRACKING_MODE_HYBRID, TRACKING_MODE_PURE_IRIS):
            est.set_tracking_mode(mode)
            self.assertFalse(est._is_pinned)
            self.assertEqual(len(est._iris_history), 0)
            gx, gy, detected, _ = est.estimate(face)
            self.assertTrue(detected)
            self.assertAlmostEqual(gx, 0.5, delta=0.06)
            self.assertAlmostEqual(gy, 0.5, delta=0.06)

    def test_calibration_profile_tracking_mode_persistence(self):
        """Calibration profiles save and restore tracking_mode."""
        self.estimator.set_tracking_mode(TRACKING_MODE_PURE_IRIS)
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            temp_path = f.name

        try:
            success = self.estimator.save_calibration_profile(temp_path)
            self.assertTrue(success)

            with open(temp_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(data.get("tracking_mode"), TRACKING_MODE_PURE_IRIS)

            new_estimator = GazeEstimator(tracking_mode=TRACKING_MODE_HEAD_PRIMARY)
            new_estimator.load_calibration_profile(temp_path)
            self.assertEqual(new_estimator.tracking_mode, TRACKING_MODE_PURE_IRIS)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)


class TestSafeExitConfirmation(unittest.TestCase):
    """Verifies the 100% hands-free eye/mouth exit confirmation menu and integrity."""

    def setUp(self):
        self.tree = build_menu_tree()

    def test_exit_confirm_node_structure_and_golden_rules(self):
        """EXIT_CONFIRM node must satisfy all 3x3 layout requirements and golden rules."""
        self.assertIn("EXIT_CONFIRM", self.tree)
        node = self.tree["EXIT_CONFIRM"]
        self.assertEqual(len(node.items), 9, "Must contain exactly 9 items.")

        # Cell 0: Confirmation action to exit
        cell_0 = node.items[0]
        self.assertEqual(cell_0.action_type, "EXIT")
        self.assertEqual(cell_0.id, "CONFIRM_EXIT")
        self.assertIn("CONFIRMAR", cell_0.label)

        # Cell 4: Pause/Reading Mode (Golden Rule 2)
        cell_4 = node.items[4]
        self.assertEqual(cell_4.action_type, "PAUSE")

        # Cell 6: Back navigation (Golden Rule 3)
        cell_6 = node.items[6]
        self.assertEqual(cell_6.action_type, "BACK")

        # All other cells (1, 2, 3, 5, 7, 8): Safe Cancel returning to ROOT
        for idx in [1, 2, 3, 5, 7, 8]:
            cell = node.items[idx]
            self.assertEqual(cell.action_type, "BACK", f"Cell {idx} should be BACK cancel.")
            self.assertEqual(cell.submenu_id, "ROOT", f"Cell {idx} should safely return to ROOT.")
            self.assertIn("CANCELAR", cell.label)

    def test_exit_confirm_reachability_and_validation(self):
        """The entire tree with EXIT_CONFIRM passes validation and is reachable from ROOT."""
        valid, errors = validate_menu_tree(self.tree)
        self.assertTrue(valid, f"Menu validation failed: {errors}")

        # Check reachability via EDIT menu slot 8
        edit_node = self.tree["EDIT"]
        slot_8 = edit_node.items[8]
        self.assertEqual(slot_8.action_type, "SUBMENU")
        self.assertEqual(slot_8.submenu_id, "EXIT_CONFIRM")


class TestVectorIconsAndIconManager(unittest.TestCase):
    """Verifies vector SVG icons and IconManager caching and rendering."""

    def test_all_vector_svg_files_exist_on_disk(self):
        """All 11 modern neon/glassmorphic SVG icons must exist in ideye/assets/icons/."""
        icons_dir = os.path.join(_IDEYE_DIR, "assets", "icons")
        self.assertTrue(os.path.isdir(icons_dir), f"Icons dir not found: {icons_dir}")

        expected_icons = [
            "ideye_logo.svg",
            "flow.svg",
            "function.svg",
            "operators.svg",
            "navigation.svg",
            "pause_eye.svg",
            "variables.svg",
            "edit.svg",
            "format.svg",
            "ai_spark.svg",
            "exit.svg",
            "help.svg",
        ]

        for icon_file in expected_icons:
            icon_path = os.path.join(icons_dir, icon_file)
            self.assertTrue(os.path.isfile(icon_path), f"Missing icon: {icon_file}")
            self.assertGreater(os.path.getsize(icon_path), 50, f"Icon {icon_file} is suspiciously small.")

    def test_icon_manager_loads_and_renders_pixmaps(self):
        """IconManager successfully renders cached QPixmaps and QIcons for all registered SVGs."""
        icon_names = [
            "ideye_logo", "flow", "function", "operators", "navigation",
            "pause_eye", "variables", "edit", "format", "ai_spark", "exit", "help"
        ]

        for name in icon_names:
            pixmap = IconManager.get_pixmap(name, 48, 48)
            self.assertFalse(pixmap.isNull(), f"Pixmap for '{name}' was null.")
            self.assertEqual(pixmap.width(), 48)
            self.assertEqual(pixmap.height(), 48)

            icon = IconManager.get_icon(name)
            self.assertFalse(icon.isNull(), f"QIcon for '{name}' was null.")

    def test_icon_manager_unknown_fallback(self):
        """Requesting an unknown icon returns fallback pixmap safely without throwing."""
        pixmap = IconManager.get_pixmap("non_existent_symbol_123", 32, 32)
        self.assertFalse(pixmap.isNull())
        self.assertEqual(pixmap.width(), 32)


class TestOverlayWindowHandsFreeExit(unittest.TestCase):
    """Verifies OverlayWindow hands-free header exit button and mouth click routing."""

    def setUp(self):
        self.overlay = OverlayWindow()
        self.overlay.resize(1920, 1080)

    def tearDown(self):
        self.overlay.close()

    def test_header_exit_rect_and_hover_detection(self):
        """Header exit button rect is enlarged (>= 150x40px) and detects gaze hover with +15px tolerance buffer."""
        self.assertIsNotNone(self.overlay.header_exit_rect)
        rect = self.overlay.header_exit_rect
        self.assertGreaterEqual(rect.width(), 150.0)
        self.assertGreaterEqual(rect.height(), 40.0)

        # Normalized coordinates targeting center of exit rect
        w = float(self.overlay.width())
        h = float(self.overlay.height())
        norm_x = rect.center().x() / w
        norm_y = rect.center().y() / h

        # 1. Direct hit on exit button
        self.overlay.on_gaze_updated(norm_x, norm_y)
        self.assertTrue(self.overlay.hovered_header_exit)

        # 2. Hit within +15px tolerance buffer (e.g. 10px below button)
        near_x = rect.center().x() / w
        near_y = (rect.bottom() + 10.0) / h
        self.overlay.on_gaze_updated(near_x, near_y)
        self.assertTrue(self.overlay.hovered_header_exit, "Should detect hover within +15px buffer")

        # 3. Outside tolerance buffer (e.g. 25px below button)
        far_x = rect.center().x() / w
        far_y = (rect.bottom() + 25.0) / h
        self.overlay.on_gaze_updated(far_x, far_y)
        self.assertFalse(self.overlay.hovered_header_exit, "Should NOT detect hover outside buffer")

        # 4. Update gaze far away in cell 0 (e.g. 0.2, 0.2)
        self.overlay.on_gaze_updated(0.2, 0.2)
        self.assertFalse(self.overlay.hovered_header_exit)

    def test_double_mouth_click_on_header_exit_emits_exit(self):
        """First mouth click arms SALIR; the second click within the window exits."""
        emitted = []
        self.overlay.exit_requested.connect(lambda: emitted.append(True))
        rect = self.overlay.header_exit_rect
        w = float(self.overlay.width())
        h = float(self.overlay.height())
        nx = rect.center().x() / w
        ny = rect.center().y() / h

        self.overlay.on_gaze_updated(nx, ny)
        self.overlay.on_gesture_triggered("MOUTH_CLICK")
        self.assertEqual(emitted, [])
        self.assertGreater(self.overlay._exit_armed_until, 0.0)

        self.overlay.on_gaze_updated(nx, ny)
        self.overlay.on_gesture_triggered("MOUTH_CLICK")
        self.assertEqual(emitted, [True])

    def test_reading_mode_inhibits_header_exit_hover(self):
        """In Reading Mode, looking at the header exit button must NOT trigger hover (Midas Touch protection)."""
        self.overlay.reading_mode = True
        rect = self.overlay.header_exit_rect
        w = float(self.overlay.width())
        h = float(self.overlay.height())
        self.overlay.on_gaze_updated(rect.center().x() / w, rect.center().y() / h)
        self.assertFalse(self.overlay.hovered_header_exit, "Exit hover should be inhibited in reading mode!")

    def test_pause_stops_freelook_gaze_and_mouth(self):
        """Pause/reading mode must freeze FreeLook cursor movement and mouth holds."""
        self.overlay.current_context_mode_id = "sniper"
        self.overlay.current_node_id = "ROOT"
        self.overlay.mouse_controller = MagicMock()
        self.overlay.reading_mode = True
        with patch.object(self.overlay, "_update_freelook_mouth") as mouth:
            self.overlay.on_gaze_updated(0.8, 0.5)
            self.overlay.on_mar_updated(None, 0.8)
            mouth.assert_not_called()
        self.overlay.mouse_controller.move_direct.assert_not_called()

    def test_pause_releases_freelook_holds(self):
        """Entering pause must release a held W key or mouse button."""
        self.overlay.current_context_mode_id = "sniper"
        self.overlay.current_node_id = "ROOT"
        self.overlay.mouse_controller = MagicMock()
        self.overlay._gaming_mode = True
        self.overlay._hold_started = True
        self.overlay.reading_mode = False
        self.overlay.toggle_reading_mode()
        self.overlay.mouse_controller.key_up.assert_called_with("w")
        self.assertFalse(self.overlay._hold_started)
        self.overlay.toggle_reading_mode()

    def test_double_mouse_click_on_header_exit_emits_exit(self):
        """Two physical clicks on SALIR exit without opening the confirmation grid."""
        from PyQt6.QtGui import QMouseEvent
        from PyQt6.QtCore import QEvent
        emitted = []
        self.overlay.exit_requested.connect(lambda: emitted.append(True))
        rect = self.overlay.header_exit_rect

        def click():
            event = QMouseEvent(
                QEvent.Type.MouseButtonPress,
                rect.center(),
                rect.center(),
                Qt.MouseButton.LeftButton,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
            )
            self.overlay.mousePressEvent(event)

        click()
        self.assertEqual(emitted, [])
        self.assertNotEqual(self.overlay.current_node_id, "EXIT_CONFIRM")
        click()
        self.assertEqual(emitted, [True])

    def test_exit_confirm_node_remains_available_for_menu(self):
        """The menu confirmation node still exists as a secondary, non-header path."""
        self.assertIn("EXIT_CONFIRM", self.overlay.menu_tree)
        self.overlay.navigate_to("EXIT_CONFIRM")
        self.assertEqual(self.overlay.current_node_id, "EXIT_CONFIRM")
        self.overlay.hovered_block = 1
        self.overlay.on_gesture_triggered("MOUTH_CLICK")
        self.assertEqual(self.overlay.current_node_id, "ROOT")

    def test_confirm_exit_action_emits_exit_requested(self):
        """CONFIRM_EXIT action emits exit_requested signal."""
        emitted = []
        self.overlay.exit_requested.connect(lambda: emitted.append(True))

        confirm_action = MenuAction(
            id="CONFIRM_EXIT",
            label="CONFIRMAR SALIR",
            action_type="EXIT",
        )
        self.overlay.execute_action(confirm_action)
        self.assertEqual(len(emitted), 1)

    def test_header_help_rect_and_hover_detection(self):
        """Header help button rect is correctly computed (>= 130x40px) and detects hover with +15px buffer."""
        self.assertIsNotNone(self.overlay.header_help_rect)
        rect = self.overlay.header_help_rect
        self.assertGreaterEqual(rect.width(), 130.0)
        self.assertGreaterEqual(rect.height(), 40.0)

        w = float(self.overlay.width())
        h = float(self.overlay.height())
        norm_x = rect.center().x() / w
        norm_y = rect.center().y() / h

        # Direct hit on help button
        self.overlay.on_gaze_updated(norm_x, norm_y)
        self.assertTrue(self.overlay.hovered_header_help)
        self.assertFalse(self.overlay.hovered_header_exit)

        # Hit within +15px buffer
        near_x = rect.center().x() / w
        near_y = (rect.bottom() + 10.0) / h
        self.overlay.on_gaze_updated(near_x, near_y)
        self.assertTrue(self.overlay.hovered_header_help)

    def test_mouth_click_on_header_help_opens_cheat_sheet_modal(self):
        """Mouth gesture while looking at header help opens the cheat sheet modal."""
        rect = self.overlay.header_help_rect
        w = float(self.overlay.width())
        h = float(self.overlay.height())
        self.overlay.on_gaze_updated(rect.center().x() / w, rect.center().y() / h)
        self.assertTrue(self.overlay.hovered_header_help)

        self.assertFalse(self.overlay.show_help_modal)
        self.overlay.on_gesture_triggered("MOUTH_CLICK")
        self.assertTrue(self.overlay.show_help_modal)

    def test_help_modal_close_button_hover_and_mouth_click(self):
        """When help modal is open, gaze highlights close button and mouth click dismisses modal."""
        self.overlay.show_help_modal = True
        self.overlay._update_help_modal_rect()
        close_rect = self.overlay.help_modal_close_rect
        self.assertTrue(close_rect.isValid())

        w = float(self.overlay.width())
        h = float(self.overlay.height())
        self.overlay.on_gaze_updated(close_rect.center().x() / w, close_rect.center().y() / h)
        self.assertTrue(self.overlay.hovered_help_modal_close)

        # Mouth click dismisses
        self.overlay.on_gesture_triggered("MOUTH_CLICK")
        self.assertFalse(self.overlay.show_help_modal)

    def test_help_modal_dismissal_via_wink_gestures(self):
        """Left wink or Right wink dismisses the help modal immediately."""
        # 1. Left wink
        self.overlay.show_help_modal = True
        self.overlay.on_gesture_triggered("WINK_LEFT")
        self.assertFalse(self.overlay.show_help_modal)

        # 2. Right wink
        self.overlay.show_help_modal = True
        self.overlay.on_gesture_triggered("WINK_RIGHT")
        self.assertFalse(self.overlay.show_help_modal)

    def test_help_modal_dismissal_via_escape_and_h_keys(self):
        """ESC key and H/F1 keys toggle or dismiss the help modal."""
        from PyQt6.QtGui import QKeyEvent
        from PyQt6.QtCore import QEvent

        # [H] key opens modal
        h_event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_H, Qt.KeyboardModifier.NoModifier)
        self.overlay.keyPressEvent(h_event)
        self.assertTrue(self.overlay.show_help_modal)

        # [ESC] key closes modal
        esc_event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
        self.overlay.keyPressEvent(esc_event)
        self.assertFalse(self.overlay.show_help_modal)

        # [F1] key toggles modal open again
        f1_event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_F1, Qt.KeyboardModifier.NoModifier)
        self.overlay.keyPressEvent(f1_event)
        self.assertTrue(self.overlay.show_help_modal)


class TestDebugWidgetTrackingMode(unittest.TestCase):
    """Verifies DebugWidget live tracking mode control and cycling."""

    def setUp(self):
        self.widget = DebugWidget()

    def tearDown(self):
        self.widget.close()

    def test_toggle_buttons_select_mode_and_sync_combo(self):
        """Clicking toggle buttons updates active tracking mode, combo box, and styling."""
        # 1. Click Híbrido button
        self.widget.btn_mode_hybrid.click()
        self.assertEqual(self.widget.current_tracking_mode, TRACKING_MODE_HYBRID)
        self.assertEqual(self.widget.combo_mode.currentData(), TRACKING_MODE_HYBRID)

        # 2. Click Cabeza button
        self.widget.btn_mode_head.click()
        self.assertEqual(self.widget.current_tracking_mode, TRACKING_MODE_HEAD_PRIMARY)
        self.assertEqual(self.widget.combo_mode.currentData(), TRACKING_MODE_HEAD_PRIMARY)

        # 3. Click Solo Iris button
        self.widget.btn_mode_iris.click()
        self.assertEqual(self.widget.current_tracking_mode, TRACKING_MODE_PURE_IRIS)
        self.assertEqual(self.widget.combo_mode.currentData(), TRACKING_MODE_PURE_IRIS)

    def test_cycle_tracking_mode_t_shortcut(self):
        """cycle_tracking_mode cycles between PURE_IRIS, HYBRID, and HEAD_PRIMARY."""
        emitted_modes = []
        self.widget.tracking_mode_changed.connect(lambda mode: emitted_modes.append(mode))

        # Initial mode is PURE_IRIS
        self.assertEqual(self.widget.current_tracking_mode, TRACKING_MODE_PURE_IRIS)

        # Cycle 1 -> HYBRID
        self.widget.cycle_tracking_mode()
        self.assertEqual(self.widget.current_tracking_mode, TRACKING_MODE_HYBRID)

        # Cycle 2 -> HEAD_PRIMARY
        self.widget.cycle_tracking_mode()
        self.assertEqual(self.widget.current_tracking_mode, TRACKING_MODE_HEAD_PRIMARY)

        # Cycle 3 -> PURE_IRIS
        self.widget.cycle_tracking_mode()
        self.assertEqual(self.widget.current_tracking_mode, TRACKING_MODE_PURE_IRIS)

        self.assertEqual(emitted_modes, [TRACKING_MODE_HYBRID, TRACKING_MODE_HEAD_PRIMARY, TRACKING_MODE_PURE_IRIS])

    def test_key_t_event_triggers_cycle(self):
        """Sending Qt.Key_T keyPressEvent triggers mode cycle."""
        from PyQt6.QtGui import QKeyEvent
        from PyQt6.QtCore import QEvent
        event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_T, Qt.KeyboardModifier.NoModifier)
        self.widget.keyPressEvent(event)
        self.assertEqual(self.widget.current_tracking_mode, TRACKING_MODE_HYBRID)


if __name__ == "__main__":
    unittest.main()
