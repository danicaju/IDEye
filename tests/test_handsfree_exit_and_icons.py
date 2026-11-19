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
