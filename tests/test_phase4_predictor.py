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


class TestPredictorAndWorker(unittest.TestCase):
    """
    Tests ContextReader: active file detection, UTF-8 safety,
    AST symbol extraction, and regex fallback on broken syntax.
    """

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="ideye_test_context_")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_clean_markdown_blocks(self):
        """Verifies stripping of markdown code fences."""
        raw_1 = "```python\n['print(1)', 'x = 2']\n```"
        self.assertEqual(clean_markdown_blocks(raw_1), "['print(1)', 'x = 2']")

        raw_2 = "```json\n[\"s1\", \"s2\"]\n```"
        self.assertEqual(clean_markdown_blocks(raw_2), '["s1", "s2"]')

        raw_3 = "   ['a', 'b']   "
        self.assertEqual(clean_markdown_blocks(raw_3), "['a', 'b']")

    def test_parse_llm_suggestions_json_array(self):
        """Verifies parsing a clean JSON array."""
        json_text = '["x = 1", "y = 2", "z = 3", "return x", "print(y)", "pass"]'
        parsed = parse_llm_suggestions(json_text)
        self.assertEqual(len(parsed), 6)
        self.assertEqual(parsed[0], "x = 1")
        self.assertEqual(parsed[3], "return x")

    def test_parse_llm_suggestions_numbered_list(self):
        """Verifies fallback parsing from numbered or bulleted list."""
        list_text = (
            "Here are the suggestions:\n"
            "1. for item in items:\n"
            "2. print(data)\n"
            "3. total += 1\n"
            "4. result = []\n"
            "5. return total\n"
            "6. pass\n"
        )
        parsed = parse_llm_suggestions(list_text)
        self.assertGreaterEqual(len(parsed), 6)
        self.assertEqual(parsed[0], "for item in items:")
        self.assertEqual(parsed[1], "print(data)")

    def test_heuristic_predictions_various_contexts(self):
        """Verifies heuristic rules for def, for, assign, try, and returns."""
        # 1. Def context
        res_def = generate_heuristic_predictions("def compute_score(user, factor):\n", ["user", "factor"])
        self.assertEqual(len(res_def), 6)
        self.assertTrue(any("Docstring" in s or "return" in s for s in res_def))

        # 2. For loop context
        res_for = generate_heuristic_predictions("for item in batch:\n", ["batch", "item"])
        self.assertEqual(len(res_for), 6)
        self.assertTrue(any("item" in s for s in res_for))

        # 3. Assignment context
        res_assign = generate_heuristic_predictions("calculated_total = \n", ["calculated_total", "values"])
        self.assertEqual(len(res_assign), 6)
        self.assertIn("calculated_total", res_assign)

        # 4. Return context
        res_ret = generate_heuristic_predictions("return \n", ["score", "total"])
        self.assertEqual(len(res_ret), 6)
        self.assertIn("score", res_ret)

        # 5. Empty context
        res_empty = generate_heuristic_predictions("", [])
        self.assertEqual(len(res_empty), 6)
        for item in res_empty:
            self.assertIsInstance(item, str)
            self.assertGreater(len(item), 0)

    def test_worker_network_failure_falls_back_to_heuristic(self):
        """
        QA Requirement 1: When Ollama is offline (ConnectionRefused),
        worker MUST catch requests.exceptions.RequestException cleanly,
        switch to Heuristic Engine, and emit exactly 6 predictions.
        """
        worker = AIPredictorWorker(
            context_text="for record in records:\n",
            local_symbols=["records", "record", "total"],
            endpoint="http://127.0.0.1:59999/api/generate",  # Unreachable port
            timeout=0.4,
        )

        results = []
        status_updates = []
        errors = []

        worker.predictions_ready.connect(lambda p: results.append(p))
        worker.status_changed.connect(lambda s: status_updates.append(s))
        worker.prediction_failed.connect(lambda e: errors.append(e))

        worker.start()
        self.assertTrue(worker.wait(3000), "Worker thread timed out!")
        _APP.processEvents()

        # Predictions must be delivered
        self.assertEqual(len(results), 1)
        predictions = results[0]
        self.assertEqual(len(predictions), 6)
        # Error must have been recorded
        self.assertGreater(len(errors), 0)
        # Status must have signaled heuristic activation
        self.assertTrue(any("Heurístico" in s for s in status_updates))

    def test_worker_timeout_falls_back_to_heuristic(self):
        """
        QA Requirement 1: When LLM request times out, worker must switch to Heuristic Engine.
        """
        import requests

        with patch("requests.post", side_effect=requests.exceptions.Timeout("Read timeout")):
            worker = AIPredictorWorker(
                context_text="def load_config(filename):\n",
                local_symbols=["filename", "config_data"],
                timeout=0.1,
            )

            results = []
            worker.predictions_ready.connect(lambda p: results.append(p))

            worker.start()
            self.assertTrue(worker.wait(2000))
            _APP.processEvents()

            self.assertEqual(len(results), 1)
            self.assertEqual(len(results[0]), 6)

    def test_worker_corrupted_json_falls_back_cleanly(self):
        """
        QA Requirement 1: When LLM returns corrupted JSON, worker handles it safely.
        """
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        # Return bad JSON that json.loads will fail on
        mock_resp.json.side_effect = json.JSONDecodeError("Expecting value", "foo", 0)
        mock_resp.text = "{invalid json content"

        with patch("requests.post", return_value=mock_resp):
            worker = AIPredictorWorker(
                context_text="x = 10\n",
                local_symbols=["x"],
                timeout=0.5,
            )

            results = []
            worker.predictions_ready.connect(lambda p: results.append(p))

            worker.start()
            self.assertTrue(worker.wait(2000))
            _APP.processEvents()

            self.assertEqual(len(results), 1)
            self.assertEqual(len(results[0]), 6)

    def test_clean_markdown_blocks_unclosed_and_stray_fences(self):
        """Verifies stripping of unclosed or stray markdown fences."""
        raw_unclosed = "```python\n['print(1)', 'x = 2']"
        cleaned = clean_markdown_blocks(raw_unclosed)
        self.assertNotIn("```", cleaned)

    def test_parse_llm_suggestions_strips_individual_backticks(self):
        """Verifies stripping backticks inside list items."""
        raw = '["`x = 10`", "```y = 20```", "return x"]'
        parsed = parse_llm_suggestions(raw)
        self.assertEqual(parsed[0], "x = 10")
        self.assertEqual(parsed[1], "y = 20")
        self.assertEqual(parsed[2], "return x")

    def test_worker_unexpected_payload_structure(self):
        """Verifies worker survives when endpoint returns a list or primitive directly."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = ["unexpected", "list", "instead", "of", "dict"]

        with patch("requests.post", return_value=mock_resp):
            worker = AIPredictorWorker(
                context_text="val = 1\n",
                local_symbols=["val"],
                timeout=0.5,
            )

            results = []
            worker.predictions_ready.connect(lambda p: results.append(p))

            worker.start()
            self.assertTrue(worker.wait(2000))
            _APP.processEvents()

            self.assertEqual(len(results), 1)
            self.assertEqual(len(results[0]), 6)

    def test_heuristic_distinct_variables_no_self_assignment_or_loop(self):
        """Verifies heuristic generator never generates self-looping loops or self-assignment."""
        # When local_symbols is ["item"], it must not generate 'for item in item:'
        preds_item = generate_heuristic_predictions("", ["item"])
        self.assertNotIn("for item in item:", preds_item)

        # When local_symbols is ["result"], it must not generate 'result = result'
        preds_res = generate_heuristic_predictions("", ["result"])
        self.assertNotIn("result = result", preds_res)

    def test_parse_llm_suggestions_strips_backticks_and_trailing_commas(self):
        """Verifies clean extraction when suggestions have inline backticks and trailing commas."""
        raw = "1. `total += 1`,\n2. `return total`,\n3. `print(data)`,\n4. `x = 1`,\n5. `y = 2`,\n6. `pass`,"
        parsed = parse_llm_suggestions(raw)
        self.assertEqual(len(parsed), 6)
        self.assertEqual(parsed[0], "total += 1")
        self.assertEqual(parsed[1], "return total")
        self.assertNotIn("`", parsed[0])
        self.assertFalse(parsed[0].endswith(","))

    def test_parse_llm_suggestions_json_dict_wrapper(self):
        """Verifies parsing JSON responses where completions are wrapped in a dict object."""
        raw = json.dumps({"suggestions": ["res = []", "for i in data:", "print(i)", "return res", "break", "pass"]})
        parsed = parse_llm_suggestions(raw)
        self.assertEqual(len(parsed), 6)
        self.assertEqual(parsed[0], "res = []")
        self.assertEqual(parsed[1], "for i in data:")

    def test_parse_llm_suggestions_list_of_dicts(self):
        """Verifies extracting string code when array elements are dict objects."""
        raw = json.dumps([
            {"code": "alpha = 10"},
            {"code": "beta = 20"},
            {"code": "gamma = 30"},
            {"code": "return alpha + beta"},
            {"code": "print(gamma)"},
            {"code": "pass"},
        ])
        parsed = parse_llm_suggestions(raw)
        self.assertEqual(len(parsed), 6)
        self.assertEqual(parsed[0], "alpha = 10")
        self.assertEqual(parsed[1], "beta = 20")

    def test_worker_background_context_extraction(self):
        """Verifies AIPredictorWorker extracts context via context_reader on its background thread."""
        tmp_dir = tempfile.mkdtemp(prefix="ideye_worker_bg_")
        try:
            f_path = os.path.join(tmp_dir, "sample.py")
            with open(f_path, "w", encoding="utf-8") as f:
                f.write("counter = 10\nmultiplier = 2\n")

            reader = ContextReader(workspace_dir=tmp_dir, active_file=f_path)
            worker = AIPredictorWorker(
                context_reader=reader,
                endpoint="http://127.0.0.1:59998/api/generate",
                timeout=0.3,
            )

            results = []
            worker.predictions_ready.connect(lambda p: results.append(p))

            worker.start()
            self.assertTrue(worker.wait(3000))
            _APP.processEvents()

            self.assertEqual(len(results), 1)
            self.assertEqual(len(results[0]), 6)
            # The background thread should have read symbols from sample.py
            self.assertIn("counter", worker.local_symbols)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
