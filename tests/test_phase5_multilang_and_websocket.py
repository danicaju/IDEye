"""
Phase 5 Comprehensive Automated Test Suite:
1. Multi-Language Syntax Support (Python, TypeScript/JavaScript, Rust, C++, Go).
2. 3x3 Gaze Macro Grid Integrity across all 5 language menu trees.
3. Language-aware Context Reader & AST Syntactic Detection.
4. Native VS Code WebSocket Bridge (ws://127.0.0.1:54321) & IPC signals.
5. CodeInjector Dual-Mode Dispatch (Native WebSocket vs OS-level Fallback).
6. UI Language Switching & Synchronization (Overlay HUD, Debug Monitor).
"""

import sys
import os
import time
import pytest
from unittest.mock import MagicMock, patch

# Ensure paths
_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_WORKSPACE_ROOT = os.path.abspath(os.path.join(_CURRENT_DIR, ".."))
if _WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, _WORKSPACE_ROOT)

from eyede.actions.language_support import (
    LANG_PYTHON,
    LANG_TYPESCRIPT,
    LANG_RUST,
    LANG_CPP,
    LANG_GO,
    SUPPORTED_LANGUAGES,
    normalize_language,
    detect_language_from_path,
    detect_language_from_vscode_id,
    get_language_display_name,
    get_language_badge,
    get_language_keywords,
)
from eyede.actions.menu_trees import (
    build_menu_tree,
    validate_menu_tree,
    get_adaptive_context_node,
    populate_lang_select_items,
    populate_ai_prediction_items,
    MenuAction,
    MenuNode,
)
from eyede.actions.context_reader import ContextReader, detect_syntactic_context
from eyede.actions.code_injector import CodeInjector
from eyede.core.websocket_bridge import WebSocketBridge
from PyQt6.QtWidgets import QApplication


# Fixture for headless Qt application
@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(["--platform", "offscreen"])
    return app


# =============================================================================
# 1. Multi-Language Definitions & Helper Function Tests
# =============================================================================

def test_language_normalization():
    """Verifies case-insensitive normalization and aliases for all 5 languages."""
    assert normalize_language("python") == LANG_PYTHON
    assert normalize_language("PY") == LANG_PYTHON
    assert normalize_language("Python3") == LANG_PYTHON

    assert normalize_language("typescript") == LANG_TYPESCRIPT
    assert normalize_language("TS") == LANG_TYPESCRIPT
    assert normalize_language("javascript") == LANG_TYPESCRIPT
    assert normalize_language("JS") == LANG_TYPESCRIPT

    assert normalize_language("rust") == LANG_RUST
    assert normalize_language("rs") == LANG_RUST

    assert normalize_language("cpp") == LANG_CPP
    assert normalize_language("C++") == LANG_CPP
    assert normalize_language("c") == LANG_CPP

    assert normalize_language("go") == LANG_GO
    assert normalize_language("golang") == LANG_GO

    # Unknown fallback
    assert normalize_language("unknown_lang") == LANG_PYTHON
    assert normalize_language(None) == LANG_PYTHON


def test_language_detection_from_path():
    """Verifies file extension detection across all supported language families."""
    assert detect_language_from_path("main.py") == LANG_PYTHON
    assert detect_language_from_path("src/app.pyw") == LANG_PYTHON

    assert detect_language_from_path("frontend/index.ts") == LANG_TYPESCRIPT
    assert detect_language_from_path("components/Button.tsx") == LANG_TYPESCRIPT
    assert detect_language_from_path("server/index.js") == LANG_TYPESCRIPT
    assert detect_language_from_path("views/App.jsx") == LANG_TYPESCRIPT

    assert detect_language_from_path("engine/src/lib.rs") == LANG_RUST

    assert detect_language_from_path("core/main.cpp") == LANG_CPP
    assert detect_language_from_path("include/engine.hpp") == LANG_CPP
    assert detect_language_from_path("native/wrapper.cc") == LANG_CPP
    assert detect_language_from_path("legacy/driver.c") == LANG_CPP

    assert detect_language_from_path("microservice/main.go") == LANG_GO

    # Unknown file extension falls back to Python
    assert detect_language_from_path("README.md") == LANG_PYTHON
    assert detect_language_from_path("") == LANG_PYTHON


def test_language_detection_from_vscode_id():
    """Verifies VS Code language ID string mapping."""
    assert detect_language_from_vscode_id("python") == LANG_PYTHON
    assert detect_language_from_vscode_id("typescript") == LANG_TYPESCRIPT
    assert detect_language_from_vscode_id("typescriptreact") == LANG_TYPESCRIPT
    assert detect_language_from_vscode_id("javascript") == LANG_TYPESCRIPT
    assert detect_language_from_vscode_id("javascriptreact") == LANG_TYPESCRIPT
    assert detect_language_from_vscode_id("rust") == LANG_RUST
    assert detect_language_from_vscode_id("cpp") == LANG_CPP
    assert detect_language_from_vscode_id("c") == LANG_CPP
    assert detect_language_from_vscode_id("go") == LANG_GO
    assert detect_language_from_vscode_id("unrecognized") == LANG_PYTHON


def test_language_badges_and_display_names():
    """Verifies human-readable names and compact high-contrast badges."""
    badges = {
        LANG_PYTHON: "PY",
        LANG_TYPESCRIPT: "TS/JS",
        LANG_RUST: "RS",
        LANG_CPP: "C++",
        LANG_GO: "GO",
    }
    for lang, expected_badge in badges.items():
        assert get_language_badge(lang) == expected_badge
        assert len(get_language_display_name(lang)) > 0


def test_language_keywords():
    """Verifies keyword sets are non-empty for each language."""
    for lang in SUPPORTED_LANGUAGES:
        keywords = get_language_keywords(lang)
        assert isinstance(keywords, set)
        assert len(keywords) >= 10


# =============================================================================
# 2. 3x3 Gaze Macro Grid Integrity Tests for all 5 Languages
# =============================================================================

@pytest.mark.parametrize("language", [LANG_PYTHON, LANG_TYPESCRIPT, LANG_RUST, LANG_CPP, LANG_GO])
def test_menu_tree_structure_for_language(language):
    """
    Validates that every single node in the menu tree for the given language
    strictly obeys the 3x3 Gaze Ergonomics Golden Rules:
    1. Exactly 9 items (indices 0..8)
    2. Index 4 is ALWAYS create_pause_action('5')
    3. Index 6 in any submenu is ALWAYS create_back_action
    4. Zero dead-ends
    """
    tree = build_menu_tree(language)
    assert "ROOT" in tree
    assert "LANG_SELECT" in tree
    assert len(tree) >= 10

    # Validate with the strict recursive validator
    is_valid, errors = validate_menu_tree(tree)
    assert is_valid, f"Validation failed for language '{language}': {errors}"


def test_language_select_menu_integrity():
    """Verifies the LANG_SELECT menu node layout and items."""
    items = populate_lang_select_items("ROOT")
    assert len(items) == 9

    # Slot 4 is Pause
    assert items[4].action_type == "PAUSE"
    # Slot 6 is Back
    assert items[6].action_type == "BACK"
    assert items[6].submenu_id == "ROOT"

    # Verify options exist for all 5 languages
    lang_snippets = [it.snippet for it in items if it.action_type == "LANG_CHANGE"]
    for lang in [LANG_PYTHON, LANG_TYPESCRIPT, LANG_RUST, LANG_CPP, LANG_GO]:
        assert lang in lang_snippets

    # Slot 7 is Auto-detect
    assert items[7].action_type == "LANG_AUTO"


def test_language_specific_snippets():
    """Verifies that each language tree contains syntax structures native to that language."""
    # Rust tree should have 'fn ' and 'match '
    rust_tree = build_menu_tree(LANG_RUST)
    rust_struct_snippets = [item.snippet for item in rust_tree["STRUCT"].items if item.snippet]
    assert any("fn " in s for s in rust_struct_snippets)
    assert any("impl " in s for s in rust_struct_snippets)

    # Go tree should have 'func ' and 'go '
    go_tree = build_menu_tree(LANG_GO)
    go_struct_snippets = [item.snippet for item in go_tree["STRUCT"].items if item.snippet]
    assert any("func " in s for s in go_struct_snippets)
    assert any("type " in s for s in go_struct_snippets)

    # TypeScript tree should have 'const ' and 'interface '
    ts_tree = build_menu_tree(LANG_TYPESCRIPT)
    ts_struct_snippets = [item.snippet for item in ts_tree["STRUCT"].items if item.snippet]
    assert any("function " in s for s in ts_struct_snippets)
    assert any("interface " in s for s in ts_struct_snippets)

    # C++ tree should have 'class ', 'void ', and '#include ' in STRUCT_IMPORT
    cpp_tree = build_menu_tree(LANG_CPP)
    cpp_struct_snippets = [item.snippet for item in cpp_tree["STRUCT"].items if item.snippet]
    assert any("class " in s for s in cpp_struct_snippets)
    assert any("void " in s for s in cpp_struct_snippets)
    cpp_import_snippets = [item.snippet for item in cpp_tree["STRUCT_IMPORT"].items if item.snippet]
    assert any("#include " in s for s in cpp_import_snippets)


# =============================================================================
# 3. Multi-Language Context Reader & AST Syntactic Detection Tests
# =============================================================================

def test_context_detection_python():
    """Tests Python syntactic context detection on incomplete lines."""
    reader = ContextReader(active_file=None, auto_detect=False)
    reader.set_active_language(LANG_PYTHON)

    assert reader.detect_syntactic_context(source_code="def process_data(data, ")["context"] == "FUNCTION_SIGNATURE"
    assert reader.detect_syntactic_context(source_code="try:\n    val = calculate()")["context"] == "TRY_BLOCK"
    assert reader.detect_syntactic_context(source_code="class SensorManager:")["context"] == "CLASS_BODY"
    assert reader.detect_syntactic_context(source_code="if threshold > 100:")["context"] == "IF_BLOCK"
    assert reader.detect_syntactic_context(source_code="for item in items:")["context"] == "LOOP_BLOCK"
    assert reader.detect_syntactic_context(source_code="with open('data.json') as f:")["context"] == "WITH_BLOCK"


def test_context_detection_typescript():
    """Tests TypeScript/JavaScript syntactic context detection on incomplete lines."""
    reader = ContextReader(active_file=None, auto_detect=False)
    reader.set_active_language(LANG_TYPESCRIPT)

    assert reader.detect_syntactic_context(source_code="function fetchData(url: string, ")["context"] == "FUNCTION_SIGNATURE"
    assert reader.detect_syntactic_context(source_code="const handleEvent = async (req: Request, ")["context"] == "FUNCTION_SIGNATURE"
    assert reader.detect_syntactic_context(source_code="try {\n    const res = await call();")["context"] == "TRY_BLOCK"
    assert reader.detect_syntactic_context(source_code="class UserService extends BaseService {")["context"] == "CLASS_BODY"
    assert reader.detect_syntactic_context(source_code="if (isValid && count > 0) {")["context"] == "IF_BLOCK"
    assert reader.detect_syntactic_context(source_code="for (const item of items) {")["context"] == "LOOP_BLOCK"


def test_context_detection_rust():
    """Tests Rust syntactic context detection on incomplete lines."""
    reader = ContextReader(active_file=None, auto_detect=False)
    reader.set_active_language(LANG_RUST)

    assert reader.detect_syntactic_context(source_code="pub fn calculate_gaze(gx: f64, ")["context"] == "FUNCTION_SIGNATURE"
    assert reader.detect_syntactic_context(source_code="match result {")["context"] == "TRY_BLOCK"
    assert reader.detect_syntactic_context(source_code="impl GazeProcessor for State {")["context"] == "CLASS_BODY"
    assert reader.detect_syntactic_context(source_code="if let Some(val) = option {")["context"] == "IF_BLOCK"
    assert reader.detect_syntactic_context(source_code="for node in nodes.iter() {")["context"] == "LOOP_BLOCK"


def test_context_detection_cpp():
    """Tests C/C++ syntactic context detection on incomplete lines."""
    reader = ContextReader(active_file=None, auto_detect=False)
    reader.set_active_language(LANG_CPP)

    assert reader.detect_syntactic_context(source_code="void renderFrame(cv::Mat& frame, ")["context"] == "FUNCTION_SIGNATURE"
    assert reader.detect_syntactic_context(source_code="try {\n    runEngine();")["context"] == "TRY_BLOCK"
    assert reader.detect_syntactic_context(source_code="class OverlayWindow : public QWidget {")["context"] == "CLASS_BODY"
    assert reader.detect_syntactic_context(source_code="if (pPointer != nullptr) {")["context"] == "IF_BLOCK"
    assert reader.detect_syntactic_context(source_code="while (isRunning) {")["context"] == "LOOP_BLOCK"


def test_context_detection_go():
    """Tests Go syntactic context detection on incomplete lines."""
    reader = ContextReader(active_file=None, auto_detect=False)
    reader.set_active_language(LANG_GO)

    assert reader.detect_syntactic_context(source_code="func HandleRequest(w http.ResponseWriter, ")["context"] == "FUNCTION_SIGNATURE"
    assert reader.detect_syntactic_context(source_code="if err != nil {")["context"] == "TRY_BLOCK"
    assert reader.detect_syntactic_context(source_code="type Client struct {")["context"] == "CLASS_BODY"
    assert reader.detect_syntactic_context(source_code="if count > 0 {")["context"] == "IF_BLOCK"
    assert reader.detect_syntactic_context(source_code="for i := 0; i < len(items); i++ {")["context"] == "LOOP_BLOCK"


def test_adaptive_context_node_generation():
    """Verifies that get_adaptive_context_node generates a valid 3x3 node for each language."""
    for lang in SUPPORTED_LANGUAGES:
        ctx_info = {"context": "FUNCTION_SIGNATURE", "line": "fn test("}
        node = get_adaptive_context_node(ctx_info, standard_root=None, language=lang)
        assert len(node.items) == 9
        # Center block 4 is always pause
        assert node.items[4].action_type == "PAUSE"
        # Slot 8 is standard menu switcher
        assert node.items[8].action_type == "SUBMENU"
        assert node.items[8].submenu_id in ("MENU_STANDARD", "ROOT")


# =============================================================================
# 4. WebSocket Bridge Subsystem Tests
# =============================================================================

def test_websocket_bridge_initialization(qapp):
    """Verifies that WebSocketBridge initializes with safe defaults and correct ports."""
    bridge = WebSocketBridge(host="127.0.0.1", port=54329)
    assert bridge.host == "127.0.0.1"
    assert bridge.port == 54329
    assert not bridge.is_connected
    assert bridge.connected_clients_count == 0


def test_websocket_bridge_start_stop(qapp):
    """Verifies that WebSocketBridge starts background daemon thread and shuts down cleanly."""
    bridge = WebSocketBridge(host="127.0.0.1", port=54328)
    started = bridge.start()
    assert started is True
    assert bridge.is_running is True

    # Starting again should be idempotent
    assert bridge.start() is True

    bridge.stop()
    assert bridge.is_running is False


def test_websocket_bridge_broadcast_and_commands(qapp):
    """Verifies outgoing command dispatch and message building."""
    bridge = WebSocketBridge(host="127.0.0.1", port=54327)

    # With no clients connected, methods should return False safely without throwing
    assert bridge.send_insert_snippet("def foo():\n    pass", 0, 0) is False
    assert bridge.send_execute_command("undo") is False
    assert bridge.broadcast_message("ping", {}) is False


def test_websocket_bridge_signals(qapp):
    """Verifies Qt signal emission on client and editor events."""
    bridge = WebSocketBridge(host="127.0.0.1", port=54326)

    received_states = []
    bridge.editor_state_received.connect(lambda s: received_states.append(s))

    # Simulate message handling directly
    simulated_state = {
        "type": "EDITOR_STATE",
        "filePath": "c:/test/app.ts",
        "languageId": "typescript",
        "cursor": {"line": 10, "character": 4},
        "lineText": "function handleEvent() {",
        "surroundingLines": ["class App {", "function handleEvent() {"],
    }
    bridge._process_inbound_message(simulated_state, None)

    assert len(received_states) == 1
    assert received_states[0]["filePath"] == "c:/test/app.ts"
    assert received_states[0]["languageId"] == "typescript"
    assert bridge.last_language_id == "typescript"
    assert bridge.last_active_file == "c:/test/app.ts"


# =============================================================================
# 5. Code Injector Dual-Mode Dispatch Tests
# =============================================================================

def test_code_injector_with_websocket_bridge(qapp):
    """
    Verifies that when WebSocket bridge is connected, CodeInjector dispatches
    directly via WebSocket, bypassing OS clipboard and keyboard emulation.
    """
    mock_bridge = MagicMock(spec=WebSocketBridge)
    mock_bridge.is_connected = True
    mock_bridge.send_insert_snippet.return_value = True
    mock_bridge.send_execute_command.return_value = True

    injector = CodeInjector(async_mode=False, websocket_bridge=mock_bridge)
    assert injector.has_native_websocket is True

    # Snippet action
    snippet_action = MenuAction(
        id="ACT_SNIPPET",
        label="Test Snippet",
        hint="Insert test",
        action_type="SNIPPET",
        snippet="const x = 42;",
        cursor_offset_left=2,
        cursor_offset_up=0,
    )
    res = injector.execute_action(snippet_action)
    assert res is True
    mock_bridge.send_insert_snippet.assert_called_once_with(
        snippet="const x = 42;",
        cursor_offset_left=2,
        cursor_offset_up=0,
        tabstops=True,
    )

    # Key action
    key_action = MenuAction(
        id="ACT_UNDO",
        label="Deshacer",
        hint="Ctrl+Z",
        action_type="KEY",
        key_name="UNDO",
    )
    res_key = injector.execute_action(key_action)
    assert res_key is True
    mock_bridge.send_execute_command.assert_called_once_with("undo", None)


def test_code_injector_fallback_when_bridge_disconnected(qapp):
    """
    Verifies that when WebSocket bridge is disconnected, CodeInjector falls back
    gracefully to OS virtual input (pynput + pyperclip).
    """
    mock_bridge = MagicMock(spec=WebSocketBridge)
    mock_bridge.is_connected = False  # Disconnected!

    injector = CodeInjector(async_mode=False, websocket_bridge=mock_bridge)
    assert injector.has_native_websocket is False

    with patch.object(injector, "insert_snippet", return_value=True) as mock_insert:
        action = MenuAction(
            id="ACT_TEST",
            label="Snippet",
            hint="",
            action_type="SNIPPET",
            snippet="fmt.Println()",
        )
        injector.execute_action(action)
        mock_insert.assert_called_once()
        # Verify websocket send was NOT called
        mock_bridge.send_insert_snippet.assert_not_called()


# =============================================================================
# 6. UI Language Switching & Synchronization Tests
# =============================================================================

def test_overlay_language_switch(qapp):
    """Verifies OverlayWindow language switching, menu tree rebuilding, and signal emission."""
    from eyede.ui.overlay_window import OverlayWindow

    overlay = OverlayWindow()
    emitted_langs = []
    overlay.language_changed.connect(lambda l: emitted_langs.append(l))

    # Switch to Rust
    overlay.set_language("RUST")
    assert overlay.current_language == LANG_RUST
    assert len(emitted_langs) == 1
    assert emitted_langs[0] == LANG_RUST
    assert "RS" in overlay.last_action_desc

    # Verify menu tree has been rebuilt for Rust
    rust_struct_snippets = [item.snippet for item in overlay.menu_tree["STRUCT"].items if item.snippet]
    assert any("fn " in s for s in rust_struct_snippets)

    # Switch to Go
    overlay.set_language("GO")
    assert overlay.current_language == LANG_GO
    assert len(emitted_langs) == 2
    assert emitted_langs[1] == LANG_GO

    overlay.close()


def test_debug_widget_language_switch_and_vscode_status(qapp):
    """Verifies DebugWidget language combo box synchronization and VS Code status badge."""
    from eyede.ui.debug_widget import DebugWidget

    widget = DebugWidget()
    emitted_langs = []
    widget.language_changed.connect(lambda l: emitted_langs.append(l))

    # Set language programmatically
    widget.set_language("TYPESCRIPT")
    assert widget.current_language == LANG_TYPESCRIPT
    assert "TypeScript" in widget.combo_language.currentText()

    # Update VS Code status
    widget.set_vscode_connected(True)
    assert widget.is_vscode_connected is True
    assert "conectado" in widget.lbl_vscode_status.text().lower()

    widget.set_vscode_connected(False)
    assert widget.is_vscode_connected is False
    assert "desconectado" in widget.lbl_vscode_status.text().lower()

    widget.close()
