"""
Unit & Integration Test Suite for EyeDE Phase 4
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
_EYEDE_DIR = os.path.join(_ROOT_DIR, "eyede")
for p in (_ROOT_DIR, _EYEDE_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

import eyede.config as config
from eyede.actions.context_reader import ContextReader, PYTHON_KEYWORDS
from eyede.actions.ai_predictor import (
    AIPredictorWorker,
    generate_heuristic_predictions,
    clean_markdown_blocks,
    parse_llm_suggestions,
)
from eyede.actions.menu_trees import (
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
from eyede.actions.code_injector import CodeInjector
from eyede.ui.overlay_window import OverlayWindow
from eyede.ui.debug_widget import DebugWidget

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


class TestContextReader(unittest.TestCase):
    """
    Tests ContextReader: active file detection, UTF-8 safety,
    AST symbol extraction, and regex fallback on broken syntax.
    """

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="eyede_test_context_")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_detect_active_file_picks_latest_modified(self):
        """Verifies auto-detection selects the most recently modified .py file."""
        f1 = os.path.join(self.test_dir, "script_a.py")
        f2 = os.path.join(self.test_dir, "script_b.py")

        with open(f1, "w", encoding="utf-8") as f:
            f.write("x = 1\n")
        time.sleep(0.05)
        with open(f2, "w", encoding="utf-8") as f:
            f.write("y = 2\n")

        reader = ContextReader(workspace_dir=self.test_dir, auto_detect=True)
        detected = reader.detect_active_file()
        self.assertIsNotNone(detected)
        self.assertEqual(os.path.abspath(detected), os.path.abspath(f2))

    def test_explicit_active_file_overrides_autodetect(self):
        """Verifies explicitly setting active file takes precedence."""
        f1 = os.path.join(self.test_dir, "file1.py")
        f2 = os.path.join(self.test_dir, "file2.py")
        for f in (f1, f2):
            with open(f, "w", encoding="utf-8") as fp:
                fp.write("val = 10\n")

        reader = ContextReader(workspace_dir=self.test_dir, active_file=f1)
        self.assertEqual(reader.get_active_file(), os.path.abspath(f1))

        reader.set_active_file(f2)
        self.assertEqual(reader.get_active_file(), os.path.abspath(f2))

    def test_get_recent_context_with_lines_limit(self):
        """Verifies get_recent_context returns the last N lines."""
        f_path = os.path.join(self.test_dir, "long_file.py")
        with open(f_path, "w", encoding="utf-8") as f:
            for i in range(100):
                f.write(f"line_{i} = {i}\n")

        reader = ContextReader(workspace_dir=self.test_dir, active_file=f_path)
        ctx = reader.get_recent_context(max_lines=30)
        lines = ctx.splitlines()
        self.assertEqual(len(lines), 30)
        self.assertEqual(lines[-1], "line_99 = 99")
        self.assertEqual(lines[0], "line_70 = 70")

    def test_get_recent_context_empty_or_missing_file(self):
        """Verifies safe handling of missing and 0-byte files."""
        reader = ContextReader(workspace_dir=self.test_dir)
        # Missing file
        self.assertEqual(reader.get_recent_context(file_path="non_existent_file.py"), "")
        # Empty file
        empty_path = os.path.join(self.test_dir, "empty.py")
        open(empty_path, "w").close()
        self.assertEqual(reader.get_recent_context(file_path=empty_path), "")
        self.assertEqual(reader.extract_local_symbols(file_path=empty_path), [])

    def test_unicode_and_special_character_safety(self):
        """
        QA Requirement 2: Protection against UnicodeDecodeError.
        Verifies opening files with errors='ignore' and handling invalid bytes.
        """
        f_path = os.path.join(self.test_dir, "corrupted_unicode.py")
        # Write invalid non-utf8 raw bytes
        with open(f_path, "wb") as f:
            f.write(b"# Comentario con tilde y bytes invalidos\nvariable_es = 100\n\xff\xfe\x8d\x99\nfinal_var = 200\n")

        reader = ContextReader(workspace_dir=self.test_dir, active_file=f_path)
        content = reader.read_file_content()
        self.assertIn("variable_es", content)
        self.assertIn("final_var", content)

        symbols = reader.extract_local_symbols()
        self.assertIn("variable_es", symbols)
        self.assertIn("final_var", symbols)

    def test_ast_symbol_extraction_valid_code(self):
        """Verifies extraction of functions, classes, arguments, and assignments via AST."""
        code = (
            "class DataProcessor:\n"
            "    def process_records(self, batch_data, threshold=50):\n"
            "        valid_items = []\n"
            "        for item in batch_data:\n"
            "            if item > threshold:\n"
            "                valid_items.append(item)\n"
            "        total_count = len(valid_items)\n"
            "        return total_count\n"
        )
        reader = ContextReader()
        symbols = reader.extract_local_symbols(source_code=code, max_symbols=12)

        # Expected symbols
        expected = ["total_count", "valid_items", "item", "threshold", "batch_data", "process_records", "DataProcessor"]
        for exp in expected:
            self.assertIn(exp, symbols, f"Expected symbol '{exp}' not found in {symbols}")
        # Built-ins and keywords should NOT be present
        self.assertNotIn("self", symbols)
        self.assertNotIn("len", symbols)
        self.assertNotIn("return", symbols)

    def test_ast_tolerance_on_syntax_error_via_regex_fallback(self):
        """
        QA Requirement 2: When user is half-typing and AST fails with SyntaxError,
        Regex Fallback MUST extract user identifiers without raising exceptions.
        """
        broken_code = (
            "def calculate_tax(salary, rate_multiplier:\n"
            "    base_deduction = 1000\n"
            "    net_taxable = salary -\n"
            "    for entry in entries:\n"
            "        temp_accum = sum(\n"
        )
        reader = ContextReader()
        # Verify ast.parse would raise SyntaxError
        with self.assertRaises(SyntaxError):
            import ast
            ast.parse(broken_code)

        # ContextReader must NOT raise SyntaxError and must recover symbols!
        symbols = reader.extract_local_symbols(source_code=broken_code, max_symbols=12)
        self.assertIsInstance(symbols, list)
        self.assertGreater(len(symbols), 0)

        # Variables defined in broken code
        self.assertIn("calculate_tax", symbols)
        self.assertIn("salary", symbols)
        self.assertIn("base_deduction", symbols)
        self.assertIn("net_taxable", symbols)
        self.assertIn("entries", symbols)
        self.assertIn("entry", symbols)
        self.assertIn("temp_accum", symbols)

    def test_extract_local_symbols_cap_and_deduplication(self):
        """Verifies that max_symbols is respected and duplicate identifiers are removed."""
        code = "\n".join([f"var_{i} = {i}" for i in range(25)])
        reader = ContextReader()
        symbols = reader.extract_local_symbols(source_code=code, max_symbols=12)
        self.assertEqual(len(symbols), 12)
        self.assertEqual(len(symbols), len(set(symbols)), "Symbols must be unique")

    def test_get_last_line(self):
        """Verifies get_last_line returns the last non-comment line."""
        f_path = os.path.join(self.test_dir, "test_last_line.py")
        with open(f_path, "w", encoding="utf-8") as f:
            f.write("x = 10\n# Some trailing comment\n\nfor item in collection:\n\n")

        reader = ContextReader(workspace_dir=self.test_dir, active_file=f_path)
        last_line = reader.get_last_line()
        self.assertEqual(last_line, "for item in collection:")

    def test_context_reader_augassign_with_and_exceptions(self):
        """Verifies extraction from AugAssign, with statements, except handlers, and starred targets."""
        code = (
            "counter = 0\n"
            "counter += 5\n"
            "with open('test.txt') as file_handle:\n"
            "    data_buffer = file_handle.read()\n"
            "try:\n"
            "    first_item, *remaining_items = data_buffer\n"
            "except Exception as err_obj:\n"
            "    pass\n"
        )
        reader = ContextReader()
        symbols = reader.extract_local_symbols(source_code=code, max_symbols=12)
        self.assertIn("counter", symbols)
        self.assertIn("file_handle", symbols)
        self.assertIn("data_buffer", symbols)
        self.assertIn("first_item", symbols)
        self.assertIn("remaining_items", symbols)
        self.assertIn("err_obj", symbols)

    def test_unclosed_multiline_functions_do_not_bleed(self):
        """Verifies that an unclosed function signature line does not greedily consume downstream code."""
        code = (
            "def broken_signature(param_alpha, param_beta:\n"
            "def secondary_signature(gamma, delta):\n"
            "    return gamma + delta\n"
        )
        reader = ContextReader()
        symbols = reader.extract_local_symbols(source_code=code, max_symbols=12)
        self.assertIn("param_alpha", symbols)
        self.assertIn("param_beta", symbols)
        self.assertIn("secondary_signature", symbols)
        self.assertIn("gamma", symbols)
        self.assertIn("delta", symbols)

    def test_symbol_recency_ordering_across_functions(self):
        """Verifies that identifiers near the bottom of the file appear before earlier declarations."""
        code = (
            "def old_function(old_arg):\n"
            "    old_var_1 = 1\n"
            "    old_var_2 = 2\n\n"
            "def brand_new_function(new_arg):\n"
            "    new_var = 100\n"
        )
        reader = ContextReader()
        symbols = reader.extract_local_symbols(source_code=code, max_symbols=12)

        # Bottom function symbols must precede top function symbols in recency order
        new_var_idx = symbols.index("new_var")
        new_arg_idx = symbols.index("new_arg")
        new_func_idx = symbols.index("brand_new_function")

        old_var2_idx = symbols.index("old_var_2")
        old_var1_idx = symbols.index("old_var_1")
        old_arg_idx = symbols.index("old_arg")
        old_func_idx = symbols.index("old_function")

        self.assertLess(new_var_idx, old_var2_idx)
        self.assertLess(new_arg_idx, old_var1_idx)
        self.assertLess(new_func_idx, old_func_idx)

    def test_detect_active_file_caching(self):
        """Verifies that detect_active_file caches the result on rapid consecutive calls."""
        f_path = os.path.join(self.test_dir, "cache_test.py")
        with open(f_path, "w", encoding="utf-8") as f:
            f.write("a = 1\n")

        reader = ContextReader(workspace_dir=self.test_dir, auto_detect=True)
        detected1 = reader.detect_active_file()
        self.assertEqual(os.path.abspath(detected1), os.path.abspath(f_path))

        # Second call immediately should use cache
        detected2 = reader.detect_active_file()
        self.assertEqual(detected1, detected2)

    """
    Tests AIPredictorWorker:
    - Heuristic Engine contextual generation
    - Ollama/OpenAI API failure handling & timeout resilience
    - Markdown cleanup and JSON parsing
    """

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
        tmp_dir = tempfile.mkdtemp(prefix="eyede_worker_bg_")
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


class TestMenuTreesPhase4Integration(unittest.TestCase):
    """
    Tests MenuTree layout with Phase 4 additions:
    T9_LOCAL_VARS, SNIPPETS AI integration, and mathematical validation.
    """

    def setUp(self):
        self.tree = build_menu_tree()

    def test_full_tree_validates_cleanly_with_phase4(self):
        """Verifies full menu tree passes all 8 validation checks with 0 errors."""
        is_valid, errors = validate_menu_tree(self.tree)
        self.assertTrue(is_valid, f"Validation failed with errors: {errors}")
        self.assertEqual(len(errors), 0)

    def test_t9_local_vars_node_integrity(self):
        """Verifies T9_LOCAL_VARS node has 9 items, Pause at index 4, Back at index 6."""
        self.assertIn("T9_LOCAL_VARS", self.tree)
        node = self.tree["T9_LOCAL_VARS"]
        self.assertEqual(len(node.items), 9)
        self.assertEqual(node.items[4].action_type, "PAUSE")
        self.assertEqual(node.items[6].action_type, "BACK")
        self.assertEqual(node.items[6].submenu_id, "T9")
        self.assertEqual(node.parent_id, "T9")

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
        items = populate_local_symbol_items(syms, parent_id="T9")

        self.assertEqual(len(items), 9)
        self.assertEqual(items[0].snippet, "var_a")
        self.assertEqual(items[1].snippet, "var_b")
        self.assertEqual(items[2].snippet, "var_c")
        self.assertEqual(items[3].snippet, "var_d")
        self.assertEqual(items[4].action_type, "PAUSE")
        self.assertEqual(items[5].snippet, "var_e")
        self.assertEqual(items[6].action_type, "BACK")
        self.assertEqual(items[6].submenu_id, "T9")
        self.assertEqual(items[7].snippet, "var_f")
        self.assertEqual(items[8].snippet, "var_g")

    def test_breadcrumbs_for_phase4_nodes(self):
        """Verifies breadcrumb trails for new and updated nodes."""
        bc_t9_local = get_breadcrumb_path(self.tree, "T9_LOCAL_VARS")
        self.assertEqual(bc_t9_local, "RAÍZ > T9 > LOCALES")

        bc_snippets = get_breadcrumb_path(self.tree, "SNIPPETS")
        self.assertEqual(bc_snippets, "RAÍZ > IA")


class TestOverlayWindowPhase4(unittest.TestCase):
    """
    Tests OverlayWindow with dynamic Phase 4 features:
    - Thread deduplication (QA Requirement 3)
    - Dynamic symbol refresh on navigation
    - AI prediction triggering and injection
    """

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="eyede_overlay_test_")
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

    def test_navigate_to_local_vars_refreshes_symbols(self):
        """Verifies navigating to T9_LOCAL_VARS populates extracted symbols."""
        self.overlay.navigate_to("T9_LOCAL_VARS")
        self.assertEqual(self.overlay.current_node_id, "T9_LOCAL_VARS")

        items = self.overlay.current_node.items
        snippets = [it.snippet for it in items if it.snippet]
        self.assertIn("user_score", snippets)
        self.assertIn("player_name", snippets)
        self.assertIn("status", snippets)

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

    def test_on_file_linked_refreshes_t9_local_vars_if_active(self):
        """Verifies linking a new file immediately refreshes T9_LOCAL_VARS if currently open."""
        self.overlay.navigate_to("T9_LOCAL_VARS")
        new_file = os.path.join(self.test_dir, "new_linked.py")
        with open(new_file, "w", encoding="utf-8") as f:
            f.write("newly_linked_var = 42\n")

        self.overlay.on_file_linked(new_file)
        items = self.overlay.current_node.items
        snippets = [it.snippet for it in items if it.snippet]
        self.assertIn("newly_linked_var", snippets)


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
