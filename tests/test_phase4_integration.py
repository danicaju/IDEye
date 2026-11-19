"""
Unit & Integration Test Suite for IDEye Phase 4
Tests Live AST Context Reader, Error-Tolerant AST/Regex Symbol Extraction,
Asynchronous AIPredictorWorker (Ollama & Fallback Heuristic Engine),
Thread Deduplication, MenuTree Layout Integrity with Dynamic Nodes,
and DebugWidget File Linking.
"""

import sys
import os
import unittest
import time
import tempfile
import shutil
import json
from unittest.mock import patch, MagicMock
from typing import List, Dict, Any, Optional

# Headless offscreen Qt platform
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtCore import Qt, QCoreApplication
from PyQt6.QtWidgets import QApplication

# Path resolution
_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_IDEYE_DIR = os.path.join(_ROOT_DIR, "ideye")
for p in (_ROOT_DIR, _IDEYE_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

import ideye.config as config
from ideye.actions.context_reader import ContextReader, PYTHON_KEYWORDS
from ideye.actions.ai_predictor import (
    AIPredictorWorker,
    generate_heuristic_predictions,
    clean_markdown_blocks,
    parse_llm_suggestions,
)
from ideye.actions.menu_trees import (
    MenuAction,
    MenuNode,
    build_menu_tree,
    validate_menu_tree,
    get_breadcrumb_path,
    populate_ai_prediction_items,
    populate_local_symbol_items,
    create_pause_action,
    create_back_action,
)
from ideye.actions.code_injector import CodeInjector
from ideye.ui.overlay_window import OverlayWindow
from ideye.ui.debug_widget import DebugWidget

_APP = QApplication.instance() or QApplication(sys.argv if hasattr(sys, "argv") else [])


class MockKeyboard:
    """Mock keyboard controller for UI testing."""
    def __init__(self):
        self.pressed_keys: List[Any] = []
        self.released_keys: List[Any] = []
        self.tapped_keys: List[Any] = []
        self.active_keys = set()

    def press(self, key):
        self.pressed_keys.append(key)
        self.active_keys.add(key)

    def release(self, key):
        self.released_keys.append(key)
        self.active_keys.discard(key)

    def tap(self, key):
        self.tapped_keys.append(key)


class MockClipboard:
    """Mock clipboard module for testing."""
    def __init__(self, initial_text: str = ""):
        self.text = initial_text
        self.history: List[str] = [initial_text]

    def paste(self) -> str:
        return self.text

    def copy(self, text: str) -> None:
        self.text = text
        self.history.append(text)


class TestMenuTreesPhase4Integration(unittest.TestCase):
    """
    Tests MenuTree layout with Phase 4 additions:
    KEYWORDS, SNIPPETS AI integration, and mathematical validation.
    """

    def setUp(self):
        self.tree = build_menu_tree()

    def test_full_tree_validates_cleanly_with_phase4(self):
        """Verifies full menu tree passes all 8 validation checks with 0 errors."""
        is_valid, errors = validate_menu_tree(self.tree)
        self.assertTrue(is_valid, f"Validation failed with errors: {errors}")
        self.assertEqual(len(errors), 0)

    def test_keywords_node_integrity(self):
        """Verifies the keyword block has 9 items, Pause at index 4, Back at index 6."""
        self.assertIn("KEYWORDS", self.tree)
        node = self.tree["KEYWORDS"]
        self.assertEqual(len(node.items), 9)
        self.assertEqual(node.items[4].action_type, "PAUSE")
        self.assertEqual(node.items[6].action_type, "BACK")
        self.assertEqual(node.items[6].submenu_id, "ROOT")
        self.assertEqual(node.parent_id, "ROOT")

    def test_populate_ai_prediction_items_layout(self):
        """Verifies populate_ai_prediction_items sets 6 predictions into slots 0, 1, 2, 3, 5, 7."""
        preds = ["print('a')", "print('b')", "print('c')", "print('d')", "print('e')", "print('f')"]
        items = populate_ai_prediction_items(preds, parent_id="ROOT")

        self.assertEqual(len(items), 9)
        # Check slots 0, 1, 2, 3
        self.assertEqual(items[0].snippet, "print('a')")
        self.assertEqual(items[1].snippet, "print('b')")
        self.assertEqual(items[2].snippet, "print('c')")
        self.assertEqual(items[3].snippet, "print('d')")
        # Center slot 4 is PAUSE
        self.assertEqual(items[4].action_type, "PAUSE")
        # Slot 5
        self.assertEqual(items[5].snippet, "print('e')")
        # Slot 6 is BACK
        self.assertEqual(items[6].action_type, "BACK")
        self.assertEqual(items[6].submenu_id, "ROOT")
        # Slot 7
        self.assertEqual(items[7].snippet, "print('f')")
        # Slot 8 is REGENERATE
        self.assertEqual(items[8].action_type, "AI_REFRESH")
        self.assertEqual(items[8].id, "AI_REGENERATE")

    def test_populate_local_symbol_items_layout(self):
        """Verifies populate_local_symbol_items populates items into slots."""
        syms = ["var_a", "var_b", "var_c", "var_d", "var_e", "var_f", "var_g"]
        items = populate_local_symbol_items(syms, parent_id="ROOT")

        self.assertEqual(len(items), 9)
        self.assertEqual(items[0].snippet, "var_a")
        self.assertEqual(items[1].snippet, "var_b")
        self.assertEqual(items[2].snippet, "var_c")
        self.assertEqual(items[3].snippet, "var_d")
        self.assertEqual(items[4].action_type, "PAUSE")
        self.assertEqual(items[5].snippet, "var_e")
        self.assertEqual(items[6].action_type, "BACK")
        self.assertEqual(items[6].submenu_id, "ROOT")
        self.assertEqual(items[7].snippet, "var_f")
        self.assertEqual(items[8].snippet, "var_g")

    def test_breadcrumbs_for_phase4_nodes(self):
        """Verifies breadcrumb trails for new and updated nodes."""
        bc_keywords = get_breadcrumb_path(self.tree, "KEYWORDS")
        self.assertTrue(bc_keywords.endswith("> PALABRAS"))

        bc_snippets = get_breadcrumb_path(self.tree, "SNIPPETS")
        self.assertEqual(bc_snippets, "RAÍZ > SUGERENCIAS")


class TestOverlayWindowPhase4(unittest.TestCase):
    """
    Tests OverlayWindow with dynamic Phase 4 features:
    - Thread deduplication (QA Requirement 3)
    - Dynamic symbol refresh on navigation
    - AI prediction triggering and injection
    """

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="ideye_overlay_test_")
        self.script_path = os.path.join(self.test_dir, "active_script.py")
        with open(self.script_path, "w", encoding="utf-8") as f:
            f.write("user_score = 95\nplayer_name = 'Alice'\nstatus = 'active'\n")

        self.mock_kb = MockKeyboard()
        self.mock_clip = MockClipboard()
        self.injector = CodeInjector(
            async_mode=False,
            paste_delay=0.005,
            keyboard_controller=self.mock_kb,
            clipboard_module=self.mock_clip,
        )
        self.context_reader = ContextReader(workspace_dir=self.test_dir, active_file=self.script_path)
        self.overlay = OverlayWindow(
            code_injector=self.injector,
            context_reader=self.context_reader,
        )
        self.overlay.resize(1280, 720)

    def tearDown(self):
        self.overlay.close()
        self.injector.stop()
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_navigate_to_keywords_shows_complete_words(self):
        """Verifies navigating to KEYWORDS shows full language keywords."""
        self.overlay.navigate_to("KEYWORDS")
        self.assertEqual(self.overlay.current_node_id, "KEYWORDS")
        labels = [item.label for item in self.overlay.current_node.items]
        self.assertIn("1: def", labels)
        self.assertIn("2: class", labels)

    def test_thread_deduplication(self):
        """
        QA Requirement 3: Prevents duplicate AIPredictorWorker threads
        if user enters AI menu twice consecutively while worker is active.
        """
        # Trigger first prediction
        self.overlay._trigger_ai_prediction()
        worker1 = self.overlay.ai_predictor_worker
        self.assertIsNotNone(worker1)
        self.assertTrue(worker1.isRunning())

        # Attempt second trigger while running
        self.overlay._trigger_ai_prediction()
        worker2 = self.overlay.ai_predictor_worker

        # Must be the exact same instance; no second thread launched!
        self.assertIs(worker1, worker2)

        # Wait for worker1 to finish cleanly
        self.assertTrue(worker1.wait(5000))
        _APP.processEvents()

    def test_navigate_to_snippets_shows_loading_and_then_results(self):
        """Verifies navigation into SNIPPETS enters loading state and then populates suggestions."""
        self.overlay.navigate_to("SNIPPETS")
        self.assertEqual(self.overlay.current_node_id, "SNIPPETS")

        # Wait for worker to finish
        if self.overlay.ai_predictor_worker:
            self.assertTrue(self.overlay.ai_predictor_worker.wait(5000))
        _APP.processEvents()

        # Predictions populated into slots 0, 1, 2, 3, 5, 7
        items = self.overlay.current_node.items
        self.assertEqual(len(items), 9)
        self.assertNotEqual(items[0].snippet, "⏳ Analizando...")
        self.assertGreater(len(items[0].snippet), 0)

    def test_selecting_ai_prediction_injects_and_returns_to_root(self):
        """Verifies clicking an AI suggestion injects code and returns to ROOT."""
        # Set ready predictions directly
        preds = ["result = []", "for x in items:", "print(data)", "return total", "if valid: pass", "val = 1"]
        self.overlay._on_ai_predictions_ready(preds)
        self.overlay.current_node_id = "SNIPPETS"

        # Click slot 0 (Prediction 1: result = [])
        self.overlay.on_gaze_updated(0.1, 0.1)  # Slot 0
        self.overlay.on_gesture_triggered("MOUTH_CLICK")

        # Injected snippet copied to clipboard
        self.assertIn("result = []", self.mock_clip.history)
        self.assertIn('v', self.mock_kb.tapped_keys)
        # Returned to ROOT
        self.assertEqual(self.overlay.current_node_id, "ROOT")

    def test_paint_event_does_not_crash(self):
        """
        Verifies paintEvent runs smoothly without NameError (fixes former is_clicked bug).
        """
        # Normal active mode
        self.overlay.on_gaze_updated(0.5, 0.5)
        self.overlay.repaint()

        # In click flash state
        self.overlay.active_click_block = 0
        self.overlay.repaint()
        self.overlay.active_click_block = None

        # In reading mode
        self.overlay.toggle_reading_mode()
        self.overlay.repaint()
        self.overlay.toggle_reading_mode()

    def test_overlay_close_event_terminates_active_worker(self):
        """Verifies closing the overlay terminates any active AIPredictorWorker cleanly."""
        self.overlay._trigger_ai_prediction()
        worker = self.overlay.ai_predictor_worker
        self.assertIsNotNone(worker)
        self.assertTrue(worker.isRunning())

        # Close overlay while worker is running
        self.overlay.close()
        self.assertFalse(worker.isRunning())

    def test_on_file_linked_does_not_break_keyword_menu(self):
        """Linking a file while KEYWORDS is open keeps the menu usable."""
        self.overlay.navigate_to("KEYWORDS")
        new_file = os.path.join(self.test_dir, "new_linked.py")
        with open(new_file, "w", encoding="utf-8") as f:
            f.write("newly_linked_var = 42\n")

        self.overlay.on_file_linked(new_file)
        self.assertEqual(self.overlay.current_node_id, "KEYWORDS")
        self.assertGreaterEqual(len(self.overlay.current_node.items), 7)


class TestDebugWidgetPhase4(unittest.TestCase):
    """
    Tests DebugWidget Phase 4 additions:
    File linking button and signal, and AI status label.
    """

    def setUp(self):
        self.widget = DebugWidget()

    def tearDown(self):
        self.widget.close()

    def test_set_linked_file_updates_label(self):
        """Verifies setting a linked file updates the label."""
        self.widget.set_linked_file("C:/projects/myapp/main_script.py")
        self.assertIn("main_script.py", self.widget.lbl_active_file.text())

    def test_update_ai_status(self):
        """Verifies update_ai_status updates the engine status label."""
        self.widget.update_ai_status("Motor Heurístico Activo")
        self.assertIn("Motor Heurístico Activo", self.widget.lbl_ai_engine.text())


if __name__ == "__main__":
    unittest.main()
