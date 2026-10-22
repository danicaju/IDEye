"""Phase 9: clipboard time-machine, foreground watcher and telemetry."""

import json
import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from eyede.actions.clipboard_history import ClipboardHistoryManager, HISTORY_SLOTS
from eyede.actions.code_injector import CodeInjector, DummyKeyboard
from eyede.actions.menu_trees import build_menu_tree
from eyede.core.telemetry_manager import TelemetryManager
from eyede.core.window_watcher import (
    WindowWatcher,
    is_game_process,
    resolve_mode_for_window,
)
from eyede.modes.data_math_mode import DataMathMode
from eyede.modes.writing_mode import WritingMode
from eyede.ui.debug_widget import DebugWidget

_APP = QApplication.instance() or QApplication(sys.argv if hasattr(sys, "argv") else [])


class FakeClipboard:
    def __init__(self, text=""):
        self.text = text

    def paste(self):
        return self.text

    def copy(self, text):
        self.text = text


class FakeModeManager:
    def __init__(self, auto=True, mode="coding"):
        self.auto_switch_enabled = auto
        self.current_mode_id = mode
        self.calls = []

    def set_mode(self, mode_id, emit=True):
        self.current_mode_id = mode_id
        self.calls.append((mode_id, emit))
        return mode_id


class SequenceProvider:
    def __init__(self, values):
        self.values = list(values)
        self.index = 0

    def __call__(self):
        if self.index >= len(self.values):
            return self.values[-1] if self.values else ("", "")
        value = self.values[self.index]
        self.index += 1
        return value


class TestClipboardHistory(unittest.TestCase):
    def setUp(self):
        self.clipboard = FakeClipboard()
        self.manager = ClipboardHistoryManager(
            clipboard_module=self.clipboard, poll_interval_ms=999999
        )

    def tearDown(self):
        self.manager.stop()

    def test_keeps_six_newest_and_moves_duplicates_to_front(self):
        for i in range(8):
            self.manager.record(f"item-{i}")
        self.assertEqual(
            self.manager.get_items(),
            ["item-7", "item-6", "item-5", "item-4", "item-3", "item-2"],
        )
        self.manager.record("item-4")
        self.assertEqual(
            self.manager.get_items(),
            ["item-4", "item-7", "item-6", "item-5", "item-3", "item-2"],
        )

    def test_internal_writes_are_ignored(self):
        self.manager.record("real user copy")
        with self.manager.ignore_internal_writes():
            self.assertFalse(self.manager.record("snippet from injector"))
        self.assertEqual(self.manager.get_items(), ["real user copy"])

    def test_poll_respects_internal_lock_and_changed_text(self):
        self.clipboard.text = "from injector"
        with self.manager.ignore_internal_writes():
            self.manager.poll_once()
        self.assertEqual(self.manager.get_items(), [])
        # The lock exit marks the leftover snippet as already seen.
        self.manager.poll_once()
        self.assertEqual(self.manager.get_items(), [])
        self.clipboard.text = "from user"
        self.manager.poll_once()
        self.assertEqual(self.manager.get_items(), ["from user"])

    def test_menu_has_nine_cells_and_invariants(self):
        for i in range(6):
            self.manager.record(f"text {i}")
        node = self.manager.get_clipboard_menu_node(parent_id="EDIT")
        self.assertEqual(len(node.items), 9)
        self.assertEqual(node.items[4].action_type, "PAUSE")
        self.assertEqual(node.items[6].action_type, "BACK")
        self.assertEqual(node.items[6].submenu_id, "EDIT")
        for slot in HISTORY_SLOTS:
            self.assertEqual(node.items[slot].action_type, "CLIPBOARD")
            self.assertTrue(node.items[slot].label)
            self.assertIn("chars", node.items[slot].hint)
        self.assertEqual(node.items[8].action_type, "CLIPBOARD_COPY")

    def test_empty_menu_is_safe(self):
        node = self.manager.get_clipboard_menu_node()
        self.assertEqual(len(node.items), 9)
        self.assertIn("Vacío", node.items[0].label)
        self.assertEqual(node.items[0].action_type, "INFO")

    def test_code_injector_does_not_record_temporary_snippet(self):
        self.manager.record("user clipboard")
        injector = CodeInjector(
            async_mode=False,
            clipboard_module=self.clipboard,
            keyboard_controller=DummyKeyboard(),
            clipboard_history=self.manager,
        )
        injector.insert_snippet("temporary snippet", async_exec=False)
        self.assertEqual(self.manager.get_items(), ["user clipboard"])


class TestClipboardMenuIntegration(unittest.TestCase):
    def test_coding_edit_node_exposes_clipboard(self):
        tree = build_menu_tree("PYTHON")
        self.assertIn("CLIPBOARD_HISTORY", tree)
        self.assertEqual(tree["EDIT"].items[7].submenu_id, "CLIPBOARD_HISTORY")

    def test_writing_and_data_modes_expose_clipboard(self):
        writing = WritingMode().get_menu_tree("PYTHON")
        data = DataMathMode().get_menu_tree("PYTHON")
        self.assertIn("CLIPBOARD_HISTORY", writing)
        self.assertIn("CLIPBOARD_HISTORY", data)
        self.assertEqual(writing["WRITING_CURSOR"].items[8].submenu_id, "CLIPBOARD_HISTORY")
        self.assertEqual(data["DATA_CURSOR"].items[8].submenu_id, "CLIPBOARD_HISTORY")


class TestWindowWatcher(unittest.TestCase):
    def test_resolve_mapping_rules(self):
        self.assertEqual(
            resolve_mode_for_window("Roblox", "RobloxPlayerBeta.exe"), ("sniper", "gaming")
        )
        self.assertEqual(resolve_mode_for_window("Discord", "Discord.exe"), ("writing", None))
        self.assertEqual(
            resolve_mode_for_window("PowerShell", "WindowsTerminal.exe"), ("terminal", None)
        )
        self.assertEqual(resolve_mode_for_window("VS Code", "Code.exe"), ("coding", None))
        self.assertEqual(
            resolve_mode_for_window("YouTube", "chrome.exe"), ("sniper", "desktop")
        )
        self.assertEqual(resolve_mode_for_window("Unknown", "unknown.exe"), ("", None))

    def test_gaming_detection_is_not_limited_to_roblox(self):
        self.assertEqual(
            resolve_mode_for_window(
                "Fortnite", "FortniteClient-Win64-Shipping.exe"
            ),
            ("sniper", "gaming"),
        )
        self.assertEqual(
            resolve_mode_for_window("The Witcher 3", "witcher3.exe"),
            ("sniper", "gaming"),
        )
        self.assertEqual(
            resolve_mode_for_window("Elden Ring", "custom-game.exe"),
            ("sniper", "gaming"),
        )
        self.assertTrue(is_game_process("SomeGame-Win64-Shipping.exe"))
        self.assertFalse(is_game_process("chrome.exe"))

    def test_other_routes_cover_common_apps(self):
        self.assertEqual(resolve_mode_for_window("Alacritty", "alacritty.exe"), ("terminal", None))
        self.assertEqual(resolve_mode_for_window("WezTerm", "wezterm-gui.exe"), ("terminal", None))
        self.assertEqual(resolve_mode_for_window("Slack", "slack.exe"), ("writing", None))
        self.assertEqual(resolve_mode_for_window("Teams", "ms-teams.exe"), ("writing", None))
        self.assertEqual(resolve_mode_for_window("Vivaldi", "vivaldi.exe"), ("sniper", "desktop"))
        self.assertEqual(resolve_mode_for_window("Opera GX", "opera_gx.exe"), ("sniper", "desktop"))
        self.assertEqual(resolve_mode_for_window("Cursor", "cursor.exe"), ("coding", None))
        self.assertEqual(resolve_mode_for_window("Notepad++", "notepad++.exe"), ("coding", None))
        self.assertEqual(
            resolve_mode_for_window("Android Studio", "android-studio64.exe"), ("coding", None)
        )

    def test_route_process_lists_are_configurable(self):
        import eyede.config as config

        original = config.TERMINAL_PROCESSES
        try:
            config.TERMINAL_PROCESSES = tuple(original) + ("myterm.exe",)
            self.assertEqual(resolve_mode_for_window("My Term", "myterm.exe"), ("terminal", None))
        finally:
            config.TERMINAL_PROCESSES = original

    def test_game_title_in_browser_does_not_activate_gaming(self):
        self.assertEqual(
            resolve_mode_for_window("Fortnite - YouTube", "chrome.exe"),
            ("sniper", "desktop"),
        )
        self.assertEqual(resolve_mode_for_window("Steam", "steam.exe"), ("", None))

    def test_gaming_lists_are_configurable(self):
        import eyede.config as config

        original = config.GAMING_PROCESSES
        try:
            config.GAMING_PROCESSES = tuple(original) + ("mygame.exe",)
            self.assertTrue(is_game_process("mygame.exe"))
        finally:
            config.GAMING_PROCESSES = original

    def test_debounce_requires_two_reads_and_emits_subprofile(self):
        mode = FakeModeManager()
        provider = SequenceProvider([("Roblox", "RobloxPlayerBeta.exe")] * 2)
        watcher = WindowWatcher(mode_manager=mode, foreground_provider=provider)
        requested = []
        watcher.mode_requested.connect(lambda m, p: requested.append((m, p)))
        watcher.poll_once()
        self.assertEqual(mode.current_mode_id, "coding")
        watcher.poll_once()
        self.assertEqual(mode.current_mode_id, "sniper")
        self.assertEqual(requested, [("sniper", "gaming")])

    def test_manual_lock_keeps_mode_but_updates_indicator(self):
        mode = FakeModeManager(auto=False)
        provider = SequenceProvider([("Discord", "Discord.exe")] * 2)
        watcher = WindowWatcher(mode_manager=mode, foreground_provider=provider)
        seen = []
        watcher.foreground_changed.connect(lambda t, p: seen.append((t, p)))
        watcher.poll_once()
        watcher.poll_once()
        self.assertEqual(mode.current_mode_id, "coding")
        self.assertEqual(seen, [("Discord", "Discord.exe")])

    def test_websocket_connected_ide_does_not_switch(self):
        mode = FakeModeManager()
        provider = SequenceProvider([("VS Code", "Code.exe")] * 2)
        watcher = WindowWatcher(
            mode_manager=mode,
            foreground_provider=provider,
            websocket_connected=lambda: True,
        )
        watcher.poll_once()
        watcher.poll_once()
        self.assertEqual(mode.current_mode_id, "coding")
        self.assertEqual(mode.calls, [])

    def test_own_window_is_ignored(self):
        mode = FakeModeManager()
        provider = SequenceProvider([("IDEye", "python.exe")] * 3)
        watcher = WindowWatcher(mode_manager=mode, foreground_provider=provider)
        for _ in range(3):
            watcher.poll_once()
        self.assertEqual(mode.calls, [])


class TestTelemetryManager(unittest.TestCase):
    def test_effort_savings_math_and_persistence(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "telemetry_stats.json")
            manager = TelemetryManager(path=path, usage_tick_ms=999999)
            manager.record_injection(50)
            manager.record_mouth_click(4)
            manager.record_mouth_click(0)
            stats = manager.stats()
            self.assertEqual(stats["keystrokes_saved"], 48)
            self.assertAlmostEqual(stats["efficiency_ratio_pct"], 96.0, places=2)
            self.assertEqual(stats["cell_heatmap"][4], 1)
            self.assertTrue(manager.save_now())
            with open(path, "r", encoding="utf-8") as fh:
                persisted = json.load(fh)
            self.assertEqual(persisted["total_chars_injected"], 50)
            self.assertEqual(persisted["total_mouth_clicks"], 2)

            restored = TelemetryManager(path=path, usage_tick_ms=999999)
            self.assertEqual(restored.stats()["keystrokes_saved"], 48)
            self.assertAlmostEqual(restored.stats()["efficiency_ratio_pct"], 96.0, places=2)
            manager.stop()
            restored.stop()

    def test_mode_usage_and_reset(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = TelemetryManager(
                path=os.path.join(tmp, "telemetry_stats.json"), usage_tick_ms=999999
            )
            manager.set_current_mode("coding", timestamp=10.0)
            manager.tick(timestamp=12.5)
            self.assertAlmostEqual(
                manager.stats()["mode_usage_seconds"]["coding"], 2.5, places=2
            )
            manager.reset()
            stats = manager.stats()
            self.assertEqual(stats["total_mouth_clicks"], 0)
            self.assertEqual(stats["mode_usage_seconds"], {})
            manager.stop()


class TestDebugTelemetryCard(unittest.TestCase):
    def test_card_updates_live_values(self):
        widget = DebugWidget()
        widget.update_telemetry(
            {
                "keystrokes_saved": 48,
                "efficiency_ratio_pct": 96.0,
                "total_chars_injected": 50,
                "total_mouth_clicks": 2,
            }
        )
        self.assertIn("48 teclas", widget.lbl_telemetry_saved.text())
        self.assertIn("96%", widget.lbl_telemetry_saved.text())
        self.assertIn("50 chars", widget.lbl_telemetry_injected.text())
        widget.set_foreground_window("Discord", "Discord.exe")
        self.assertIn("Discord.exe", widget.lbl_foreground.text())
        widget.close()


if __name__ == "__main__":
    unittest.main()
