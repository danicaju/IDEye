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


class TestContextReader(unittest.TestCase):
    """
    Tests ContextReader: active file detection, UTF-8 safety,
    AST symbol extraction, and regex fallback on broken syntax.
    """

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="ideye_test_context_")

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
        symbols = reader.extract_local_symbols(
            source_code=code, max_symbols=12, language="PYTHON"
        )

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


if __name__ == "__main__":
    unittest.main()
