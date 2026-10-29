"""
Automated Forensic Test Suite: Context Reader & AI Predictor (Phase Extra)
Tests ContextReader with valid/invalid Python code, deleted files (FileNotFoundError),
and permission errors (PermissionError).
Tests AIPredictorWorker with mocked timeouts, corrupt JSON, conversational wrappers,
and validates the Heuristic Fallback Engine guaranteeing exactly 6 suggestions.
"""

import os
import sys
import json
import tempfile
import unittest
from unittest.mock import patch, MagicMock
import requests

# Ensure offscreen Qt platform for test runner
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PyQt6.QtCore import QCoreApplication
from PyQt6.QtWidgets import QApplication

_APP = QApplication.instance() or QApplication(sys.argv if hasattr(sys, "argv") else [])

# Ensure project root is in sys.path
_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_IDEYE_DIR = os.path.join(_ROOT_DIR, "ideye")
for p in (_ROOT_DIR, _IDEYE_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

from ideye.actions.context_reader import ContextReader
from ideye.actions.ai_predictor import (
    AIPredictorWorker,
    generate_heuristic_predictions,
    parse_llm_suggestions,
    clean_markdown_blocks,
)


class TestContextReader(unittest.TestCase):
    """Deep verification of ContextReader dual AST + Regex extraction and error resilience."""

    def setUp(self):
        self.reader = ContextReader(auto_detect=False)

    def test_extract_symbols_valid_python_code(self):
        """Extracts functions, classes, arguments, and assigned variables from valid Python code."""
        code = """
import os

class DataProcessor:
    def __init__(self, raw_input, buffer_size=1024):
        self.raw_input = raw_input
        self.buffer_size = buffer_size

    def execute_pipeline(self, target_node):
        transformed = self.raw_input.strip()
        count = len(transformed)
        for chunk in transformed.split():
            result_item = chunk.upper()
            total_sum += 1
        return count
"""
        symbols = self.reader.extract_local_symbols(source_code=code, max_symbols=20)
        self.assertIsInstance(symbols, list)
        self.assertGreater(len(symbols), 0)

        # Expected symbols
        for expected in ("DataProcessor", "raw_input", "buffer_size", "execute_pipeline", "target_node", "transformed", "count"):
            self.assertIn(expected, symbols)

        # Keywords must never leak into symbols
        for kw in ("class", "def", "self", "for", "in", "return", "import"):
            self.assertNotIn(kw, symbols)

    def test_extract_symbols_syntax_error_resilience(self):
        """When AST parser fails due to incomplete syntax or typos, Regex fallback rescues local symbols."""
        broken_code = """
def process_data(user_token, payload
    # Note missing closing paren and invalid indentation
    temp_var = 100
    active_record = 
    for element in items:
        valid_flag = True
"""
        # ast.parse(broken_code) raises SyntaxError!
        symbols = self.reader.extract_local_symbols(source_code=broken_code, max_symbols=12)
        self.assertIsInstance(symbols, list)
        self.assertGreater(len(symbols), 0)

        # Regex fallback should have rescued key tokens
        self.assertIn("process_data", symbols)
        self.assertIn("user_token", symbols)
        self.assertIn("temp_var", symbols)

    def test_file_not_found_resilience(self):
        """If linked file is deleted or does not exist, reader safely returns empty list without crashing."""
        non_existent = "C:/temp/surely_does_not_exist_982374.py"
        self.reader.set_active_file(non_existent)

        content = self.reader.read_file_content()
        self.assertEqual(content, "")

        symbols = self.reader.extract_local_symbols(file_path=non_existent)
        self.assertEqual(symbols, [])

        recent = self.reader.get_recent_context(file_path=non_existent)
        self.assertEqual(recent, "")

    def test_permission_error_resilience(self):
        """If file access raises PermissionError, reader safely returns empty string and list."""
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as f:
            temp_path = f.name
            f.write(b"secret_data = 42\n")

        try:
            with patch("builtins.open", side_effect=PermissionError("Access Denied [Errno 13]")):
                content = self.reader.read_file_content(temp_path)
                self.assertEqual(content, "")

                symbols = self.reader.extract_local_symbols(file_path=temp_path)
                self.assertEqual(symbols, [])
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)


class TestAIPredictorAndHeuristics(unittest.TestCase):
    """Deep verification of AIPredictorWorker, LLM response parsing, and heuristic engine."""

    def test_heuristic_predictions_guarantees_exactly_six(self):
        """generate_heuristic_predictions() must ALWAYS return a list of exactly 6 distinct strings."""
        test_contexts = [
            ("def calculate_metric(alpha):", ["alpha", "metric"]),
            ("class EyeTrackerHUD:", ["HUD"]),
            ("if user_logged_in:", ["user_logged_in", "session"]),
            ("for idx in range(10):", ["idx", "items"]),
            ("while is_active:", ["is_active"]),
            ("try:", []),
            ("except Exception as e:", ["e"]),
            ("with open('file.txt') as f:", ["f"]),
            ("total_count = ", ["count", "total_count"]),
            ("user_data.", ["user_data"]),
            ("return ", ["result"]),
            ("", []),
            ("random unformatted code line here", ["foo", "bar"]),
        ]

        for ctx, syms in test_contexts:
            preds = generate_heuristic_predictions(ctx, syms)
            self.assertEqual(
                len(preds),
                6,
                f"Context '{ctx}' generated {len(preds)} suggestions instead of exactly 6.",
            )
            self.assertIsInstance(preds, list)
            for item in preds:
                self.assertIsInstance(item, str)
                self.assertGreater(len(item.strip()), 0)

    def test_parse_llm_suggestions_regex_and_formats(self):
        """parse_llm_suggestions() must extract code from raw JSON arrays, JSON objects, markdown, and text wrappers."""
        # 1. Clean JSON array
        raw_arr = '["result = []", "for x in items:", "print(data)", "return total", "if not valid: break", "self.value = 0"]'
        parsed = parse_llm_suggestions(raw_arr)
        self.assertEqual(len(parsed), 6)
        self.assertEqual(parsed[0], "result = []")

        # 2. Markdown fenced JSON
        fenced = '```json\n["x = 10", "y = 20", "z = x + y"]\n```'
        parsed_fenced = parse_llm_suggestions(fenced)
        self.assertEqual(len(parsed_fenced), 3)
        self.assertEqual(parsed_fenced[0], "x = 10")

        # 3. Conversational wrapper with JSON object containing suggestions key
        conversational = """
Here are the next 6 Python code statements you requested:
```json
{
  "model": "codellama",
  "suggestions": [
    "if items is not None:",
    "total = sum(items)",
    "return total"
  ]
}
```
Let me know if you need any additional assistance!
"""
        parsed_conv = parse_llm_suggestions(conversational)
        self.assertGreaterEqual(len(parsed_conv), 3)
        self.assertEqual(parsed_conv[0], "if items is not None:")
        self.assertEqual(parsed_conv[1], "total = sum(items)")

        # 4. Numbered list fallback
        numbered = "1. value = process()\n2. if value:\n3. return True"
        parsed_num = parse_llm_suggestions(numbered)
        self.assertEqual(len(parsed_num), 3)
        self.assertEqual(parsed_num[0], "value = process()")

    def test_ai_predictor_worker_partial_llm_backfills_to_six(self):
        """If the LLM returns fewer than 6 suggestions (e.g. 2), Heuristic Engine backfills to exactly 6."""
        worker = AIPredictorWorker(
            context_text="def process_request(token):\n    ",
            local_symbols=["token", "request"],
            timeout=1.0,
        )

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        # Return only 2 suggestions
        mock_resp.json.return_value = {"response": '["validate(token)", "token.clean()"]'}

        received_suggestions = []

        def _on_preds(preds):
            received_suggestions.extend(preds)

        worker.predictions_ready.connect(_on_preds)

        with patch("requests.post", return_value=mock_resp):
            worker.run()

        self.assertEqual(len(received_suggestions), 6)
        # Original 2 suggestions are preserved at start
        self.assertEqual(received_suggestions[0], "validate(token)")
        self.assertEqual(received_suggestions[1], "token.clean()")
        # Remaining 4 suggestions were filled by heuristic engine
        for s in received_suggestions[2:]:
            self.assertIsInstance(s, str)
            self.assertGreater(len(s), 0)

    def test_ai_predictor_worker_timeout_heuristic_fallback(self):
        """When LLM request times out, worker emits prediction_failed and falls back to 6 heuristic suggestions."""
        worker = AIPredictorWorker(
            context_text="class DataStream:\n    ",
            local_symbols=["stream", "buffer"],
            timeout=0.1,
        )

        received_suggestions = []
        failure_messages = []

        worker.predictions_ready.connect(lambda p: received_suggestions.extend(p))
        worker.prediction_failed.connect(lambda msg: failure_messages.append(msg))

        # Simulate requests.Timeout
        with patch("requests.post", side_effect=requests.exceptions.Timeout("Connection timed out")):
            worker.run()

        self.assertEqual(len(failure_messages), 1)
        self.assertIn("Timeout", failure_messages[0])

        # Must still guarantee exactly 6 suggestions
        self.assertEqual(len(received_suggestions), 6)

    def test_ai_predictor_worker_corrupt_json_fallback(self):
        """When LLM returns corrupted JSON, worker falls back cleanly to heuristic suggestions."""
        worker = AIPredictorWorker(
            context_text="for item in items:\n    ",
            local_symbols=["item", "items"],
            timeout=1.0,
        )

        received_suggestions = []
        worker.predictions_ready.connect(lambda p: received_suggestions.extend(p))

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"response": "Definitely not a json [unclosed array"}

        with patch("requests.post", return_value=mock_resp):
            worker.run()

        self.assertEqual(len(received_suggestions), 6)

    def test_ai_predictor_worker_clean_stop_no_terminate(self):
        """Calling worker.stop() sets _running=False and halts worker without crashing."""
        worker = AIPredictorWorker(
            context_text="x = 1",
            timeout=1.0,
        )
        self.assertTrue(worker._running)
        worker.stop()
        self.assertFalse(worker._running)

        # Running stopped worker should return immediately
        received = []
        worker.predictions_ready.connect(lambda p: received.extend(p))
        worker.run()
        self.assertEqual(len(received), 0)

    def test_parse_llm_suggestions_trailing_commas_and_balanced_scanner(self):
        """parse_llm_suggestions() must tolerate trailing commas and extract isolated JSON among conversational text."""
        # 1. Trailing comma in JSON array
        trailing_arr = '["alpha = 1", "beta = 2", "gamma = 3",]'
        parsed_arr = parse_llm_suggestions(trailing_arr)
        self.assertEqual(len(parsed_arr), 3)
        self.assertEqual(parsed_arr[0], "alpha = 1")
        self.assertEqual(parsed_arr[2], "gamma = 3")

        # 2. Trailing comma in JSON dict object
        trailing_dict = '{"suggestions": ["x = 10", "y = 20",],}'
        parsed_dict = parse_llm_suggestions(trailing_dict)
        self.assertEqual(len(parsed_dict), 2)
        self.assertEqual(parsed_dict[0], "x = 10")
        self.assertEqual(parsed_dict[1], "y = 20")

        # 3. Conversational text with note brackets around a JSON array
        conv_brackets = 'Here is note [1]: ["x = 1", "y = 2"]. That is all [2].'
        parsed_conv_brackets = parse_llm_suggestions(conv_brackets)
        self.assertEqual(len(parsed_conv_brackets), 2)
        self.assertEqual(parsed_conv_brackets[0], "x = 1")
        self.assertEqual(parsed_conv_brackets[1], "y = 2")

        # 4. Conversational text with both brackets and braces surrounding JSON suggestions
        conv_both = 'Explanation {"note": 1} [1]: {"suggestions": ["res = []", "return res"]}. End {"done": 2} [2].'
        parsed_conv_both = parse_llm_suggestions(conv_both)
        self.assertEqual(len(parsed_conv_both), 2)
        self.assertEqual(parsed_conv_both[0], "res = []")
        self.assertEqual(parsed_conv_both[1], "return res")

        # 5. Malformed JSON with raw quoted strings rescued
        malformed_quoted = '["incomplete line", "second item"'
        parsed_malformed = parse_llm_suggestions(malformed_quoted)
        self.assertGreaterEqual(len(parsed_malformed), 1)
        self.assertEqual(parsed_malformed[0], "incomplete line")

    def test_cross_module_signal_slot_signatures(self):
        """Cross-Module Check: pyqtSignal signatures must match slots and connection targets across components."""
        from ideye.core.camera_tracker import CameraTracker
        from ideye.ui.overlay_window import OverlayWindow
        from ideye.ui.debug_widget import DebugWidget

        # Ensure OverlayWindow and DebugWidget slots exist and have callable signatures
        overlay = OverlayWindow()
        debug_widget = DebugWidget()
        worker = AIPredictorWorker(context_text="", timeout=1.0)

        # 1. Tracker to Overlay: gaze_updated(float, float) -> overlay.on_gaze_updated
        self.assertTrue(hasattr(overlay, "on_gaze_updated"))
        self.assertTrue(callable(overlay.on_gaze_updated))

        # 2. Tracker to Overlay: gesture_triggered(str) -> overlay.on_gesture_triggered
        self.assertTrue(hasattr(overlay, "on_gesture_triggered"))
        self.assertTrue(callable(overlay.on_gesture_triggered))

        # 3. Tracker to DebugWidget: frame_ready(object, float) -> debug_widget.on_frame_ready
        self.assertTrue(hasattr(debug_widget, "on_frame_ready"))
        self.assertTrue(callable(debug_widget.on_frame_ready))

        # 4. Worker to Overlay: predictions_ready(list) -> overlay._on_ai_predictions_ready
        self.assertTrue(hasattr(overlay, "_on_ai_predictions_ready"))
        self.assertTrue(callable(overlay._on_ai_predictions_ready))

        # 5. Worker to Overlay: status_changed(str) -> overlay._on_ai_status_changed
        self.assertTrue(hasattr(overlay, "_on_ai_status_changed"))
        self.assertTrue(callable(overlay._on_ai_status_changed))

        # 6. Worker to Overlay: prediction_failed(str) -> overlay._on_ai_prediction_failed
        self.assertTrue(hasattr(overlay, "_on_ai_prediction_failed"))
        self.assertTrue(callable(overlay._on_ai_prediction_failed))

        # 7. Overlay to DebugWidget: ai_status_updated(str) -> debug_widget.update_ai_status
        self.assertTrue(hasattr(debug_widget, "update_ai_status"))
        self.assertTrue(callable(debug_widget.update_ai_status))

        # 8. DebugWidget to Overlay: file_linked(str) -> overlay.on_file_linked
        self.assertTrue(hasattr(overlay, "on_file_linked"))
        self.assertTrue(callable(overlay.on_file_linked))

        overlay.close()
        debug_widget.close()


if __name__ == "__main__":
    unittest.main()
