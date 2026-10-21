"""Phase 8.2: custom macro persistence and menu-tree overrides."""

import json
import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication

from eyede.core.macro_manager import MacroManager
from eyede.actions.menu_trees import MenuAction, MenuNode
from eyede.ui.macro_editor_dialog import CustomMacroDialog

_APP = QApplication.instance() or QApplication(sys.argv if hasattr(sys, "argv") else [])


def make_root():
    return MenuNode(
        id="ROOT",
        title="ROOT",
        items=[
            MenuAction(id=f"DEFAULT_{i}", label=f"{i + 1}: Default", action_type="SNIPPET", snippet=f"x{i}")
            for i in range(9)
        ],
        parent_id=None,
    )


class TestMacroManager(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmpdir.name, "custom_macros.json")

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_round_trip_atomic_save(self):
        manager = MacroManager(self.path)
        self.assertTrue(
            manager.save_macro(
                "coding",
                0,
                {
                    "label": "Custom If/Else",
                    "subtitle": "Boilerplate block",
                    "icon": "code",
                    "action_type": "snippet",
                    "payload": "if condition:\n    pass",
                },
            )
        )
        self.assertFalse(os.path.exists(self.path + ".tmp"))
        with open(self.path, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
        self.assertEqual(raw["coding"]["cells"]["0"]["label"], "Custom If/Else")

        loaded = MacroManager(self.path)
        self.assertEqual(loaded.get_cells("coding")["0"]["payload"], "if condition:\n    pass")

    def test_apply_overrides_patches_only_selected_cell(self):
        manager = MacroManager(self.path)
        manager.save_macro(
            "coding",
            0,
            {
                "label": "My Macro",
                "subtitle": "Do it",
                "icon": "code",
                "action_type": "snippet",
                "payload": "print('custom')",
            },
        )
        root = make_root()
        patched = manager.apply_overrides(root, "coding")
        self.assertEqual(patched.items[0].label, "My Macro")
        self.assertEqual(patched.items[0].snippet, "print('custom')")
        self.assertEqual(patched.items[1].label, "2: Default")
        self.assertEqual(patched.items[4].label, "5: Default")
        self.assertEqual(root.items[0].label, "1: Default")

    def test_command_and_key_mapping(self):
        manager = MacroManager(self.path)
        manager.save_macro(
            "terminal", 0, {"label": "Pytest", "subtitle": "Run", "action_type": "command", "payload": "pytest -q"}
        )
        manager.save_macro(
            "terminal", 1, {"label": "Save", "subtitle": "Ctrl+S", "action_type": "key", "payload": "SAVE"}
        )
        patched = manager.apply_overrides(make_root(), "terminal")
        self.assertEqual(patched.items[0].action_type, "SNIPPET")
        self.assertEqual(patched.items[0].snippet, "pytest -q")
        self.assertEqual(patched.items[1].action_type, "KEY")
        self.assertEqual(patched.items[1].key_name, "SAVE")

    def test_protected_pause_and_back_cells_are_ignored(self):
        manager = MacroManager(self.path)
        self.assertFalse(
            manager.save_macro("coding", 4, {"label": "Nope", "action_type": "snippet", "payload": "x"})
        )
        self.assertFalse(
            manager.save_macro("coding", 6, {"label": "Nope", "action_type": "snippet", "payload": "x"})
        )

    def test_corrupt_json_falls_back_to_empty(self):
        with open(self.path, "w", encoding="utf-8") as fh:
            fh.write("{broken")
        manager = MacroManager(self.path)
        self.assertEqual(manager.load_macros(), {})


class TestMacroDialog(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmpdir.name, "custom_macros.json")
        self.manager = MacroManager(self.path)
        self.dialog = CustomMacroDialog(self.manager)

    def tearDown(self):
        self.dialog.close()
        self.tmpdir.cleanup()

    def test_editor_saves_selected_cell(self):
        self.dialog.combo_mode.setCurrentIndex(0)
        self.dialog._select_cell(0)
        self.dialog.edit_label.setText("Custom Test")
        self.dialog.edit_subtitle.setText("Subtitle")
        self.dialog.combo_action.setCurrentIndex(self.dialog.combo_action.findData("snippet"))
        self.dialog.edit_payload.setPlainText("print('x')")
        self.dialog._save_current()
        cells = self.manager.get_cells("coding")
        self.assertEqual(cells["0"]["label"], "Custom Test")
        self.assertEqual(cells["0"]["payload"], "print('x')")


if __name__ == "__main__":
    unittest.main()
