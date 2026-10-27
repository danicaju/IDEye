"""Phase 10.4: Agentic Prompt Launcher regression tests."""

import json
import tempfile
import unittest
from pathlib import Path

from eyede.actions.agentic_launcher import (
    AGENTIC_ACTIONS,
    ACTION_SLOTS,
    AgenticPromptLauncher,
)


class FakeBridge:
    def __init__(self, result=True):
        self.result = result
        self.calls = []

    def send_trigger_agent_prompt(self, action_id, prompt, selection_only=True):
        self.calls.append((action_id, prompt, selection_only))
        return self.result


class TestAgenticPromptLauncher(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.queue_path = Path(self.tmp.name) / "agentic_task_queue.json"
        self.launcher = AgenticPromptLauncher(queue_path=str(self.queue_path))
        self.context = {
            "file_path": "src/sample.py",
            "line_start": 10,
            "line_end": 18,
            "function_name": "compute_total",
            "language": "python",
            "source_code": (
                "def compute_total(items):\n"
                "    return sum(items) / len(items)\n"
            ),
            "symbols": ["compute_total", "items"],
            "diagnostics": [
                {
                    "line": 12,
                    "severity": "error",
                    "message": "division by zero",
                    "source": "pytest",
                }
            ],
        }

    def tearDown(self):
        self.tmp.cleanup()

    def test_prompt_includes_context_for_all_actions(self):
        for action_id in AGENTIC_ACTIONS:
            prompt = self.launcher.build_prompt(action_id, context=self.context)
            self.assertIn(AGENTIC_ACTIONS[action_id]["title"], prompt)
            self.assertIn("compute_total", prompt)
            self.assertIn("sum(items) / len(items)", prompt)
            self.assertIn("division by zero", prompt)
            self.assertIn("src/sample.py", prompt)
            self.assertIn("líneas 10–18", prompt)
            self.assertIn("Acción:** `{}`".format(action_id), prompt)

    def test_menu_invariants_and_six_actions(self):
        node = self.launcher.get_agentic_menu_node()
        self.assertEqual(node.id, "AGENTIC_LAUNCHER")
        self.assertEqual(len(node.items), 9)
        self.assertEqual(node.items[4].action_type, "PAUSE")
        self.assertEqual(node.items[6].action_type, "BACK")
        self.assertEqual(node.items[8].action_type, "AGENTIC_SEND")

        slots = (0, 1, 2, 3, 5, 7)
        for index, action_id in zip(slots, ACTION_SLOTS):
            item = node.items[index]
            self.assertEqual(item.action_type, "AGENTIC_PROMPT")
            self.assertEqual(item.snippet, action_id)
        self.assertNotIn("AGENTIC_PROMPT", [node.items[i].action_type for i in (4, 6, 8)])

    def test_queue_is_atomic_and_readable(self):
        prompt = self.launcher.build_prompt("generate_pytest", context=self.context)
        path = self.launcher.queue_task("generate_pytest", prompt, payload={"source": "gaze"})
        self.assertIsNotNone(path)
        self.assertTrue(self.queue_path.is_file())
        data = json.loads(self.queue_path.read_text(encoding="utf-8"))
        self.assertEqual(data["pending"][-1]["action_id"], "generate_pytest")
        self.assertEqual(data["pending"][-1]["status"], "pending")
        self.assertIn("compute_total", self.launcher.latest_task()["prompt"])

    def test_bridge_message_and_dispatch(self):
        bridge = FakeBridge()
        prompt = self.launcher.build_prompt("fix_and_harden", context=self.context)
        self.assertTrue(
            self.launcher.send_to_bridge(bridge, "fix_and_harden", prompt)
        )
        self.assertEqual(bridge.calls[0][0], "fix_and_harden")
        self.assertTrue(bridge.calls[0][2])

        result = self.launcher.dispatch(
            "fix_and_harden", prompt, bridge=bridge, queue_only=False
        )
        self.assertTrue(result["sent"])
        self.assertTrue(result["queued"])
        self.assertEqual(len(bridge.calls), 2)

    def test_dispatch_queue_only_does_not_send(self):
        bridge = FakeBridge()
        prompt = self.launcher.build_prompt("write_docstring", context=self.context)
        result = self.launcher.dispatch(
            "write_docstring", prompt, bridge=bridge, queue_only=True
        )
        self.assertFalse(result["sent"])
        self.assertTrue(result["queued"])
        self.assertEqual(bridge.calls, [])

    def test_unknown_action_falls_back(self):
        prompt = self.launcher.build_prompt("does_not_exist", context=self.context)
        self.assertIn("Refactor limpio", prompt)
        self.assertIn("compute_total", prompt)


if __name__ == "__main__":
    unittest.main()
