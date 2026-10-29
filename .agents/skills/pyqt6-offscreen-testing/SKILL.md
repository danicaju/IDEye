---
name: pyqt6-offscreen-testing
description: >-
  Use this skill when adding or changing PyQt6 widgets, HUD geometry, menu interactions, hotkeys, or rendering in IDEye. Covers headless offscreen tests, QApplication lifecycle, screenshot assertions, and why keyPressEvent is unreliable for the overlay.
---

# PyQt6 Offscreen Testing for IDEye

IDEye's test suite must run without a physical display, webcam, or window manager. The overlay is a frameless, always-on-top `QWidget`, so most bugs are geometry, focus, or paint-order bugs rather than logic bugs.

## 1. Set the platform before importing PyQt6

At the very top of every Qt test module:

```python
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication
```

`QT_QPA_PLATFORM` must be set **before** `from PyQt6...` imports. Setting it after importing Qt has no effect.

## 2. One QApplication per test process

Create or reuse a single application:

```python
app = QApplication.instance() or QApplication(["--platform", "offscreen"])
```

Do not create multiple `QApplication` objects. If a widget is kept in a fixture, call `close()`, `deleteLater()`, and `processEvents()` before the next test.

## 3. Render assertions for HUD layout

Use `grab()` to force a paint pass and validate geometry:

```python
overlay.resize(1280, 720)
overlay.show()
app.processEvents()
image = overlay.grab()
assert not image.isNull()
assert overlay._last_action_pill_rect.right() < overlay.header_mode_rect.left()
```

Useful patterns:

- Test at `1280x720`, `1536x864`, and `1920x1080`; header collisions usually appear first at 1280.
- Assert `QRectF` relations (`right() < left()`) instead of hard-coded pixel positions.
- Keep private rect attributes (`header_mode_rect`, `header_lang_rect`, `_last_action_pill_rect`) available for tests; they are the cheapest way to catch overlap regressions.
- Call `processEvents()` after `resize`, `show`, mode changes, and `navigate_to()`.

## 4. Menus and actions

The 3x3 menu is stateful. Test navigation and actions through public methods:

```python
overlay.navigate_to("ROOT")
assert overlay.current_node_id == "ROOT"

overlay.hovered_block = 0
overlay.on_gesture_triggered("MOUTH_CLICK")
app.processEvents()
```

For deterministic action tests, call `execute_action(item, target_block=0)` directly with the `MenuAction` from the current node. For gesture tests, set `hovered_block` first; `on_gesture_triggered("MOUTH_CLICK")` uses the current hovered block.

Validate every new menu tree with the project validator:

```python
from ideye.actions.menu_trees import validate_menu_tree

assert validate_menu_tree(root_node) is True
```

A valid non-root node needs 9 items, slot 5 is PAUSE, slot 6 is BACK to its parent, and all submenu IDs must exist.

## 5. The overlay does not receive plain keyboard focus

`OverlayWindow` uses `WindowDoesNotAcceptFocus`, `WA_ShowWithoutActivating`, and `NoFocus`. Therefore:

- `keyPressEvent` will not receive plain `V`, `K`, `T`, etc. from the OS.
- Global shortcuts live in `ideye/core/hotkey_manager.py` and use `pynput`; do not trigger them in tests.
- Application-level shortcuts in `DebugWidget` use `QShortcut` with `Qt.ShortcutContext.ApplicationShortcut`; test the handler method or the shortcut object directly.
- Gaze-gated shortcuts are plain `V`/`K` plus `Ctrl+Alt+V/K`; the main app checks `overlay.is_mode_shortcut_targeted()`. Tests can set `overlay.current_gaze` to a normalized point inside `header_mode_rect` and assert the gate.

## 6. Run tests quietly

```powershell
python -m pytest -q --tb=short 2>&1 | Select-Object -Last 15
```

MediaPipe prints a `W0000 ... feedback tensors` warning to stderr. It is noise, not a failure. Trust the final `NNN passed` line; the PowerShell wrapper may report exit code 1 because of the native stderr line.

## 7. Common pitfalls

- Forgetting `processEvents()` after mode/tree changes gives stale geometry.
- Reusing a `QApplication` after `quit()` causes crashes; never call `quit()` in tests.
- Asserting exact text with icon IDs is fragile; use `_menu_card_label()` / `_clean_action_label()` helpers.
- Timers from banners and click flashes can leak into the next test; close the overlay or wait for the timer to expire.
- `reading_mode` intentionally blocks most card actions; reset it with `toggle_reading_mode()` before testing normal clicks.
