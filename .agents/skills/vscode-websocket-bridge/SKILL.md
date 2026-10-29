---
name: vscode-websocket-bridge
description: >-
  Use this skill when changing the IDEye Python WebSocket server or the VS Code extension bridge. Covers the message protocol, editor-state sync, snippet insertion, command execution, async server lifecycle, and VSIX testing.
---

# IDEye VS Code WebSocket Bridge

The bridge connects the PyQt6 engine to a native VS Code extension so code can be inserted into the active editor without stealing focus.

## 1. Architecture

- Python server: `ideye/core/websocket_bridge.py`, class `WebSocketBridge(QObject)`.
- Transport: `ws://127.0.0.1:54321` by default (`config.WEBSOCKET_HOST` / `WEBSOCKET_PORT`).
- Server thread: dedicated daemon thread named `IDEye-WebSocketServer`, running an asyncio loop. Never block the Qt main thread.
- Extension: `vscode-extension/src/extension.ts`, compiled to `dist/extension.js`.
- Extension ID: `ideye-vscode-bridge`; publisher `danicaju`.

The Python side emits Qt signals from the bridge thread. Qt queued connections deliver them to the main thread.

## 2. Message protocol

### Python to VS Code

Handshake on connect:

```json
{"type": "HANDSHAKE_ACK", "server": "IDEye Look-To-Code Engine", "version": "0.5.0", "status": "ready"}
```

Insert a snippet:

```json
{
  "type": "INSERT_SNIPPET",
  "snippet": "print(${1:value})",
  "cursorOffsetLeft": 0,
  "cursorOffsetUp": 0,
  "tabstops": true
}
```

Execute a VS Code command:

```json
{"type": "EXECUTE_COMMAND", "command": "editor.action.formatDocument", "args": []}
```

Pong:

```json
{"type": "PONG", "timestamp": 1234567890}
```

### VS Code to Python

Editor state:

```json
{
  "type": "EDITOR_STATE",
  "filePath": "C:/project/main.py",
  "languageId": "python",
  "cursor": {"line": 10, "column": 4},
  "lineText": "def main():",
  "surroundingLines": "...",
  "workspaceRoot": "C:/project"
}
```

Acknowledgement:

```json
{"type": "ACK", "action": "INSERT_SNIPPET", "status": "ok"}
```

Ping:

```json
{"type": "PING", "timestamp": 1234567890}
```

## 3. Python API

Use these methods from the Qt side:

```python
bridge.send_insert_snippet(
    snippet="print(${1:value})",
    cursor_offset_left=0,
    cursor_offset_up=0,
    tabstops=True,
)
bridge.send_execute_command("undo")
bridge.send_execute_command("editor.action.formatDocument", [])
bridge.broadcast_message({"type": "CUSTOM", "value": 1})
```

`send_*` returns `False` when no client is connected. Do not queue snippets for later; the user expects them in the current editor.

Inbound signals:

- `client_connected(str)`
- `client_disconnected(str)`
- `editor_state_received(dict)`
- `command_ack_received(dict)`
- `server_status_changed(bool, str)`

## 4. Implementation rules

- Use `websockets.asyncio.server.serve`; keep the fallback to `websockets.server.serve` for older versions. Do not import `websockets.legacy`.
- Bind to `127.0.0.1`, not `0.0.0.0`. The bridge is local-only.
- Keep JSON messages small; `surroundingLines` should stay around 40 lines.
- Never insert text directly into the VS Code buffer from Python. Send `INSERT_SNIPPET` and let the extension call `editor.insertSnippet`, which preserves undo history and cursor placement.
- For code injection, the Python `CodeInjector` uses clipboard + `Ctrl+V`; the WebSocket path is preferred when the extension is connected.
- `cursorOffsetLeft` means move the cursor left after insertion (typically to place it inside parentheses); `cursorOffsetUp` handles multi-line snippets.
- Do not log full file contents or editor text at INFO level. Log message types and counts.

## 5. Testing

Unit tests for the bridge live in `tests/test_phase5_multilang_and_websocket.py`. They mock or connect a local client and verify:

- handshake
- `EDITOR_STATE` parsing
- `PING`/`PONG`
- snippet and command payload shape
- clean shutdown

Run:

```powershell
python -m pytest -q tests\test_phase5_multilang_and_websocket.py --tb=short
```

For an end-to-end check:

1. Start IDEye (`python main.py`).
2. Confirm the debug widget reports the WebSocket server as running.
3. Open VS Code with the VSIX installed.
4. Run `IDEye: Conectar con Motor de Mirada`.
5. Check the extension status and the Python log for `Cliente conectado`.
6. Trigger a snippet from the HUD and verify it lands at the cursor.

## 6. Packaging the extension

```powershell
cd vscode-extension
npm run compile
npm run package
```

The `.vsix` is generated in `vscode-extension/`. `dist/extension.js` is gitignored and must be rebuilt before packaging. After installing a new VSIX, reload the VS Code window; otherwise the old extension host keeps running.

## 7. Common failures

- `WinError 10048` / address in use: another IDEye instance or test still owns port 54321. Stop it or use a different port in tests.
- Extension connects but no state arrives: check the extension's `ideye.autoConnect` setting and the active editor; `EDITOR_STATE` is sent only when an editor is open.
- Snippet inserted in the wrong place: verify `cursorOffsetLeft` / `cursorOffsetUp` and that the extension uses `SnippetString`, not plain text.
- Firewall prompt: local loopback traffic should not need a rule; binding to `0.0.0.0` would trigger one.
- `websockets` deprecation warnings: ensure the code path is `websockets.asyncio.server`; the legacy import is intentionally absent.
