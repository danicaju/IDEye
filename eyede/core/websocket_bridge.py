"""
IDEye - Native VS Code WebSocket Bridge (Phase 5)
Bidirectional, low-latency WebSocket IPC server connecting IDEye to the native
VS Code extension on ws://127.0.0.1:54321.

Capabilities:
1. Real-time Editor Synchronization:
   Receives active file path, programming language ID, cursor position (line, column),
   line text, and surrounding context from VS Code.
2. Native Snippet & Code Injection:
   Dispatches snippets directly to VS Code's native editor.insertSnippet() API,
   supporting TabStops ($1, $2, $0), smart indentation, and bypassing OS clipboard
   and keystroke emulation.
3. Native Command Execution:
   Dispatches editor commands (undo, redo, save, format, navigate, revealDefinition).
4. Full Thread-Safety & Resilience:
   Runs asyncio WebSocket server on a dedicated background daemon thread,
   providing Qt signals for UI components and thread-safe dispatch from Qt threads.
"""

import sys
import time
import json
import asyncio
import logging
import threading
from typing import Optional, Dict, Any, List, Set, Union

from PyQt6.QtCore import QObject, pyqtSignal

try:
    import websockets
    try:
        from websockets.asyncio.server import serve as ws_serve
    except ImportError:  # pragma: no cover - compatibility with older websockets
        from websockets.server import serve as ws_serve
    HAS_WEBSOCKETS = True
except Exception:  # pragma: no cover
    websockets = None
    ws_serve = None
    HAS_WEBSOCKETS = False

try:
    import eyede.config as config
except ImportError:
    import config

logger = logging.getLogger("eyede.core.websocket_bridge")


class WebSocketBridge(QObject):
    """
    WebSocket IPC Bridge connecting IDEye to the native VS Code extension.
    """

    client_connected = pyqtSignal(str)          # client_id / remote_address
    client_disconnected = pyqtSignal(str)       # client_id
    editor_state_received = pyqtSignal(dict)    # { filePath, languageId, cursor, lineText, surroundingLines, workspaceRoot }
    command_ack_received = pyqtSignal(dict)     # { commandId, status, error }
    server_status_changed = pyqtSignal(bool, str) # (is_running, status_message)

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self.host = host if host is not None else getattr(config, "WEBSOCKET_HOST", "127.0.0.1")
        self.port = port if port is not None else getattr(config, "WEBSOCKET_PORT", 54321)

        self._clients: Set[Any] = set()
        self._clients_lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._server = None
        self._stop_event = threading.Event()
        self._is_running = False

        self.last_editor_state: Optional[Dict[str, Any]] = None
        self.last_active_file: Optional[str] = None
        self.last_language_id: Optional[str] = None

    @property
    def is_running(self) -> bool:
        """Returns True if the WebSocket server loop is actively running."""
        return self._is_running

    @property
    def is_connected(self) -> bool:
        """Returns True if at least one client (e.g. VS Code extension) is currently connected."""
        with self._clients_lock:
            return len(self._clients) > 0

    @property
    def connected_clients_count(self) -> int:
        """Returns number of active client connections."""
        with self._clients_lock:
            return len(self._clients)

    def start(self) -> bool:
        """
        Starts the WebSocket server on a dedicated background thread.
        Returns True if started successfully or already running.
        """
        if self._is_running:
            return True

        if not HAS_WEBSOCKETS:
            msg = "El paquete 'websockets' no está instalado. WebSocket Bridge inactivo."
            logger.warning(msg)
            self.server_status_changed.emit(False, msg)
            return False

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_server_thread,
            name="IDEye-WebSocketServer",
            daemon=True,
        )
        self._thread.start()

        # Wait briefly for background event loop to start and socket to bind
        for _ in range(25):
            if self._is_running:
                break
            time.sleep(0.02)

        return True

    def stop(self, timeout: float = 2.0) -> None:
        """
        Gracefully shuts down the WebSocket server and all active connections.
        """
        if not self._is_running and self._thread is None:
            return

        self._stop_event.set()
        if self._loop is not None and self._loop.is_running():
            try:
                # Schedule stop in loop
                asyncio.run_coroutine_threadsafe(self._async_stop(), self._loop)
            except Exception:
                pass

        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=timeout)

        self._is_running = False
        with self._clients_lock:
            self._clients.clear()
        self.server_status_changed.emit(False, "Servidor detenido")
        logger.info("[WebSocketBridge] Servidor detenido limpiamente.")

    def _run_server_thread(self) -> None:
        """Worker thread entrypoint running the asyncio event loop."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        try:
            self._loop.run_until_complete(self._async_start())
        except Exception as e:
            logger.error(f"[WebSocketBridge] Error en bucle asyncio: {e}")
            self.server_status_changed.emit(False, f"Error: {e}")
        finally:
            try:
                # Cancel pending tasks
                pending = asyncio.all_tasks(self._loop)
                for task in pending:
                    task.cancel()
                if pending:
                    self._loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                self._loop.close()
            except Exception:
                pass
            self._is_running = False

    async def _async_start(self) -> None:
        """Async entrypoint binding the WebSocket server."""
        try:
            self._server = await ws_serve(
                self._handle_client,
                self.host,
                self.port,
                ping_interval=20,
                ping_timeout=20,
            )
            self._is_running = True
            msg = f"Servidor escuchando en ws://{self.host}:{self.port}"
            logger.info(f"[WebSocketBridge] {msg}")
            self.server_status_changed.emit(True, msg)

            # Keep server running until stop event is signaled
            while not self._stop_event.is_set():
                await asyncio.sleep(0.2)

        except OSError as e:
            msg = f"No se pudo enlazar el puerto {self.port}: {e}"
            logger.warning(f"[WebSocketBridge] {msg}")
            self.server_status_changed.emit(False, msg)
        except asyncio.CancelledError:
            pass
        finally:
            if self._server is not None:
                self._server.close()
                await self._server.wait_closed()

    async def _async_stop(self) -> None:
        """Async routine closing active clients and server."""
        with self._clients_lock:
            clients_to_close = list(self._clients)
        for client in clients_to_close:
            try:
                await client.close()
            except Exception:
                pass
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()

    async def _handle_client(self, websocket) -> None:
        """Connection handler for an individual connected WebSocket client."""
        remote = str(getattr(websocket, "remote_address", "client"))
        logger.info(f"[WebSocketBridge] Cliente conectado: {remote}")
        with self._clients_lock:
            self._clients.add(websocket)
        self.client_connected.emit(remote)

        # Send welcome handshake
        try:
            handshake = {
                "type": "HANDSHAKE_ACK",
                "server": "IDEye Look-To-Code Engine",
                "version": "0.5.0",
                "status": "ready",
            }
            await websocket.send(json.dumps(handshake))
        except Exception:
            pass

        try:
            async for raw_message in websocket:
                if isinstance(raw_message, bytes):
                    raw_message = raw_message.decode("utf-8", errors="ignore")
                try:
                    payload = json.loads(raw_message)
                    self._process_inbound_message(payload, websocket)
                except (json.JSONDecodeError, TypeError, ValueError):
                    logger.warning(f"[WebSocketBridge] Mensaje JSON no válido: {raw_message[:100]}")
        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception as e:
            logger.debug(f"[WebSocketBridge] Error en conexión cliente: {e}")
        finally:
            with self._clients_lock:
                self._clients.discard(websocket)
            logger.info(f"[WebSocketBridge] Cliente desconectado: {remote}")
            self.client_disconnected.emit(remote)

    def _process_inbound_message(self, payload: Dict[str, Any], websocket: Any) -> None:
        """Dispatches inbound messages from VS Code extension to Qt signals."""
        if not isinstance(payload, dict):
            logger.warning("[WebSocketBridge] Ignoring non-object JSON payload: %r", type(payload))
            return
        msg_type = payload.get("type", "")

        if msg_type == "EDITOR_STATE":
            self.last_editor_state = payload
            self.last_active_file = payload.get("filePath")
            self.last_language_id = payload.get("languageId")
            self.editor_state_received.emit(payload)

        elif msg_type == "ACK":
            self.command_ack_received.emit(payload)

        elif msg_type == "PING":
            # Echo pong back asynchronously
            if self._loop is not None and self._loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    websocket.send(json.dumps({"type": "PONG", "timestamp": payload.get("timestamp")})),
                    self._loop,
                )

    def send_insert_snippet(
        self,
        snippet: str,
        cursor_offset_left: int = 0,
        cursor_offset_up: int = 0,
        tabstops: bool = True,
    ) -> bool:
        """
        Sends an INSERT_SNIPPET payload to connected VS Code client(s).
        Returns True if successfully queued to send.
        """
        if not self.is_connected:
            return False

        payload = {
            "type": "INSERT_SNIPPET",
            "snippet": snippet,
            "cursorOffsetLeft": cursor_offset_left,
            "cursorOffsetUp": cursor_offset_up,
            "tabstops": tabstops,
        }
        return self.broadcast_message(payload)

    def send_jump_to_line(self, line: int) -> bool:
        """Asks VS Code to reveal and place the cursor on a 1-based line."""
        if not self.is_connected:
            return False
        return self.broadcast_message({"type": "jump_to_line", "line": max(1, int(line))})

    def send_apply_line_fix(self, line: int, replacement: str, insert: bool = False) -> bool:
        """Asks the VS Code extension to replace/insert one line atomically."""
        if not self.is_connected:
            return False
        return self.broadcast_message({
            "type": "apply_line_fix",
            "line": max(1, int(line)),
            "replacement": str(replacement),
            "insert": bool(insert),
        })

    def send_execute_command(self, command: str, args: Optional[List[Any]] = None) -> bool:
        """
        Sends an EXECUTE_COMMAND payload to connected VS Code client(s).
        (e.g. 'undo', 'redo', 'save', 'format', 'cursorUp', 'cursorDown', 'revealDefinition')
        """
        if not self.is_connected:
            return False

        payload = {
            "type": "EXECUTE_COMMAND",
            "command": command,
            "args": args or [],
        }
        return self.broadcast_message(payload)

    def send_trigger_agent_prompt(
        self,
        action_id: str,
        prompt: str,
        selection_only: bool = True,
    ) -> bool:
        """Sends a rich agentic prompt to the VS Code chat/inline-chat bridge."""
        if not self.is_connected:
            return False
        return self.broadcast_message(
            {
                "type": "trigger_agent_prompt",
                "action_id": str(action_id),
                "prompt": str(prompt),
                "selection_only": bool(selection_only),
            }
        )

    def broadcast_message(self, message: Union[Dict[str, Any], str], payload: Optional[Dict[str, Any]] = None) -> bool:
        """
        Thread-safe broadcast of a JSON payload to all connected clients.
        Accepts either a single dictionary, or (message_type, payload_dict).
        Returns True if queued for at least one client.
        """
        if not self.is_connected or self._loop is None or not self._loop.is_running():
            return False

        if isinstance(message, str):
            data = {"type": message, "payload": payload or {}}
        elif isinstance(message, dict):
            data = message
        else:
            return False

        raw = json.dumps(data)
        with self._clients_lock:
            clients_snapshot = list(self._clients)

        if not clients_snapshot:
            return False

        async def _do_broadcast():
            for client in clients_snapshot:
                try:
                    await client.send(raw)
                except Exception as e:
                    logger.debug(f"[WebSocketBridge] Error enviando a cliente: {e}")

        try:
            asyncio.run_coroutine_threadsafe(_do_broadcast(), self._loop)
            return True
        except Exception as e:
            logger.error(f"[WebSocketBridge] Error en broadcast: {e}")
            return False
