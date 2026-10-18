"""
Overlay Window Module for EyeDE (Phase 2 & 3)
Transparent, Non-Focus-Stealing 3x3 Macro-Block Grid Overlay with Hierarchical
Syntax Navigation Trees, Real-Time Code Injection, and Breadcrumb Status Bar.

Features:
- Configures Qt.WindowType.WindowDoesNotAcceptFocus, FramelessWindowHint,
  WindowStaysOnTopHint, Tool, and WA_TranslucentBackground.
- Ensures external IDEs (e.g. VS Code, PyCharm) NEVER lose keyboard focus or cursor blink.
- Renders hierarchical 3x3 Menu Trees (build_menu_tree):
    * Root Menu (Flow, Struct, Operators, Nav, Pause, T9, Edit, Format, Snippets).
    * Submenus with visual indicators ('📁' for submenus, '⚡' for actions, '👁️' for pause, '⬅' for back).
- Top Breadcrumb Bar displaying current navigation path (e.g. '📁 RAÍZ > FLUJO') and last executed action.
- Sticky submenu mode for repetitive actions (Nav, Edit, Format).
- Non-blocking CodeInjector integration: snippets pasted via clipboard with cursor centering and keystrokes.
- Block 4 (Center: 'PAUSA / MODO LECTURA') toggles HUD opacity to 10% and inhibits actions during reading.
"""

from typing import Optional, Tuple, Dict, Any, List
import sys
import os

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, pyqtSlot, QRectF, QPointF
from PyQt6.QtGui import QPainter, QColor, QFont, QPen, QBrush
from PyQt6.QtWidgets import QWidget

try:
    import eyede.config as config
    from eyede.actions.code_injector import CodeInjector
    from eyede.actions.menu_trees import (
        MenuNode,
        MenuAction,
        build_menu_tree,
        get_breadcrumb_path,
        populate_ai_prediction_items,
        populate_local_symbol_items,
    )
    from eyede.actions.context_reader import ContextReader
    from eyede.actions.ai_predictor import AIPredictorWorker
except ImportError:
    import config
    from actions.code_injector import CodeInjector
    from actions.menu_trees import (
        MenuNode,
        MenuAction,
        build_menu_tree,
        get_breadcrumb_path,
        populate_ai_prediction_items,
        populate_local_symbol_items,
    )
    from actions.context_reader import ContextReader
    from actions.ai_predictor import AIPredictorWorker


class OverlayWindow(QWidget):
    """
    Transparent HUD overlay rendering the 3x3 Macro-Block tree-based grid.
    Never steals window focus from the active IDE.
    """

    block_activated = pyqtSignal(int, str)  # (block_index, action_id)
    exit_requested = pyqtSignal()
    reading_mode_toggled = pyqtSignal(bool)  # True = reading mode on (10% opacity)
    menu_navigated = pyqtSignal(str)  # (current_node_id)
    action_executed = pyqtSignal(str, str)  # (action_id, action_description)
    ai_status_updated = pyqtSignal(str)

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        code_injector: Optional[CodeInjector] = None,
        menu_tree: Optional[Dict[str, MenuNode]] = None,
        context_reader: Optional[ContextReader] = None,
    ):
        super().__init__(parent)

        # 1. Non-focus stealing, transparent, top-level overlay flags
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        # Win32 OS-level non-activation protection
        if sys.platform == "win32":
            self._apply_win32_no_activate()

        # 2. Code Injection & Menu Tree Subsystems
        self.code_injector = code_injector if code_injector is not None else CodeInjector(async_mode=True)
        self.menu_tree: Dict[str, MenuNode] = menu_tree if menu_tree is not None else build_menu_tree()
        self.context_reader: ContextReader = context_reader if context_reader is not None else ContextReader()
        self.ai_predictor_worker: Optional[AIPredictorWorker] = None
        self.is_ai_predicting: bool = False
        self.current_node_id: str = "ROOT"
        self.last_action_desc: str = "Ninguna"

        # 3. State tracking
        self.reading_mode: bool = False
        self.current_opacity: float = config.OVERLAY_OPACITY_ACTIVE
        self.hovered_block: Optional[int] = None
        self.active_click_block: Optional[int] = None
        self.current_gaze: Tuple[float, float] = (0.5, 0.5)

        # Layout constants
        self.breadcrumb_height: float = 42.0
        self.margin: float = 8.0

        # Window title for identification
        self.setWindowTitle("EyeDE - Gaze Macro Grid HUD (Phase 3)")

        # 4. Pre-allocated rendering objects to prevent 30/60 FPS GC pressure and memory leaks
        self._font_header_pill = QFont("Segoe UI", 9, QFont.Weight.Bold)
        self._font_header_left = QFont("Segoe UI", 10, QFont.Weight.Bold)
        self._font_header_center = QFont("Segoe UI", 9, QFont.Weight.Bold)
        self._font_header_right = QFont("Segoe UI", 9)
        self._font_label = QFont("Segoe UI", 12, QFont.Weight.Bold)
        self._font_hint = QFont("Segoe UI", 9)
        self._font_badge = QFont("Segoe UI", 8, QFont.Weight.Bold)

        # Header bar styles (Acrylic Glassmorphism)
        self._brush_header_bg = QBrush(QColor(13, 17, 23, 235))
        self._pen_header_border = QPen(QColor(48, 54, 61, 200), 1.5)
        self._pen_header_left = QPen(QColor(240, 246, 252))
        self._pen_header_center = QPen(QColor(248, 113, 113))
        self._pen_header_right = QPen(QColor(56, 189, 248))

        # Mode indicator pills
        self._brush_pill_edit = QBrush(QColor(16, 185, 129, 220))
        self._brush_pill_read = QBrush(QColor(245, 158, 11, 220))
        self._color_pill_text = QColor(10, 25, 20)

        # Styles for blocks
        self._brush_click = QBrush(QColor(*config.OVERLAY_COLOR_CLICK))
        self._pen_click = QPen(QColor(*config.OVERLAY_CLICK_BORDER_COLOR), 3.5)
        self._color_click_text = QColor(10, 30, 15)
        self._color_click_hint = QColor(25, 55, 30)

        self._brush_hover = QBrush(QColor(*config.OVERLAY_COLOR_HOVER))
        self._pen_hover = QPen(QColor(*config.OVERLAY_HOVER_BORDER_COLOR), config.OVERLAY_HOVER_BORDER_WIDTH)
        self._color_hover_text = QColor(*config.OVERLAY_TEXT_HOVER_COLOR)
        self._color_hover_hint = QColor(230, 235, 245)

        self._brush_reading_center = QBrush(QColor(16, 185, 129, 180))
        self._pen_reading_center = QPen(QColor(52, 211, 153, 230), 2.5)
        self._color_reading_center_text = QColor(240, 253, 244)
        self._color_reading_center_hint = QColor(167, 243, 208)

        self._brush_reading_other = QBrush(QColor(15, 18, 22, 40))
        self._pen_reading_other = QPen(QColor(40, 45, 55, 50), 1)
        self._color_reading_other_text = QColor(120, 130, 145, 80)
        self._color_reading_other_hint = QColor(80, 90, 105, 60)

        self._brush_rest = QBrush(QColor(*config.OVERLAY_COLOR_REST))
        self._pen_rest = QPen(QColor(*config.OVERLAY_REST_BORDER_COLOR), config.OVERLAY_BORDER_WIDTH)

        self._brush_back = QBrush(QColor(38, 20, 34, 215))
        self._pen_back = QPen(QColor(236, 72, 153, 200), 2.0)

        self._brush_submenu = QBrush(QColor(16, 26, 40, 215))
        self._pen_submenu = QPen(QColor(6, 182, 212, 190), config.OVERLAY_BORDER_WIDTH)

        self._brush_default = QBrush(QColor(*config.OVERLAY_COLOR_BG))
        self._pen_default = QPen(QColor(*config.OVERLAY_COLOR_BORDER), config.OVERLAY_BORDER_WIDTH)
        self._color_default_text = QColor(*config.OVERLAY_TEXT_COLOR)
        self._color_default_hint = QColor(*config.OVERLAY_TEXT_HINT_COLOR)

        self._color_badge_submenu = QColor(6, 182, 212, 220)
        self._color_badge_back = QColor(236, 72, 153, 220)
        self._color_badge_sticky = QColor(255, 195, 60, 220)
        self._color_badge_default = QColor(140, 150, 165, 180)

        # Pre-allocated category styles for World-Class UI
        self._cat_brushes = {
            "FLOW": QBrush(QColor(12, 26, 38, 215)),
            "STRUCT": QBrush(QColor(32, 24, 12, 215)),
            "OPERATORS": QBrush(QColor(26, 16, 36, 215)),
            "NAV": QBrush(QColor(14, 24, 42, 215)),
            "PAUSE": QBrush(QColor(12, 32, 24, 215)),
            "BACK": QBrush(QColor(36, 16, 28, 215)),
            "EDIT": QBrush(QColor(18, 20, 38, 215)),
            "AI": QBrush(QColor(28, 16, 38, 215)),
            "EXIT": QBrush(QColor(36, 14, 16, 215)),
            "DEFAULT": self._brush_default,
        }
        self._cat_pens = {
            "FLOW": QPen(QColor(6, 182, 212, 200), 1.8),
            "STRUCT": QPen(QColor(245, 158, 11, 200), 1.8),
            "OPERATORS": QPen(QColor(168, 85, 247, 200), 1.8),
            "NAV": QPen(QColor(59, 130, 246, 200), 1.8),
            "PAUSE": QPen(QColor(16, 185, 129, 210), 2.2),
            "BACK": QPen(QColor(236, 72, 153, 200), 2.0),
            "EDIT": QPen(QColor(99, 102, 241, 200), 1.8),
            "AI": QPen(QColor(217, 70, 239, 200), 1.8),
            "EXIT": QPen(QColor(239, 68, 68, 200), 1.8),
            "DEFAULT": self._pen_default,
        }
        self._cat_top_pens = {
            "FLOW": QPen(QColor(34, 211, 238, 220), 2.5),
            "STRUCT": QPen(QColor(251, 191, 36, 220), 2.5),
            "OPERATORS": QPen(QColor(192, 132, 252, 220), 2.5),
            "NAV": QPen(QColor(96, 165, 250, 220), 2.5),
            "PAUSE": QPen(QColor(52, 211, 153, 230), 2.5),
            "BACK": QPen(QColor(244, 114, 182, 220), 2.5),
            "EDIT": QPen(QColor(129, 140, 248, 220), 2.5),
            "AI": QPen(QColor(240, 171, 252, 220), 2.5),
            "EXIT": QPen(QColor(248, 113, 113, 220), 2.5),
            "DEFAULT": QPen(QColor(100, 116, 139, 180), 2.0),
        }
        self._cat_badges = {
            "FLOW": ("⚡ FLUJO", QColor(34, 211, 238)),
            "STRUCT": ("⚡ ESTRUCTURA", QColor(251, 191, 36)),
            "OPERATORS": ("⚡ OPERADOR", QColor(192, 132, 252)),
            "NAV": ("⚡ NAVEGACIÓN", QColor(96, 165, 250)),
            "PAUSE": ("👁️ REPOSO", QColor(52, 211, 153)),
            "BACK": ("⬅ VOLVER", QColor(244, 114, 182)),
            "EDIT": ("⚡ EDICIÓN", QColor(129, 140, 248)),
            "AI": ("🤖 IA / CÓDIGO", QColor(240, 171, 252)),
            "EXIT": ("🚨 SALIR", QColor(248, 113, 113)),
            "DEFAULT": ("⚡ ACCIÓN", QColor(148, 163, 184)),
        }

        # High-visibility Dual-ring Gaze Pointer Reticle
        self._brush_pointer_glow = QBrush(QColor(56, 189, 248, 45))
        self._pen_pointer_ring = QPen(QColor(*config.OVERLAY_POINTER_OUTLINE), 2.2)
        self._brush_pointer_dot = QBrush(QColor(*config.OVERLAY_POINTER_COLOR))
        self._pen_pointer_ticks = QPen(QColor(255, 255, 255, 200), 1.5)

    def _apply_win32_no_activate(self) -> None:
        """Applies WS_EX_NOACTIVATE and WS_EX_TRANSPARENT styles on Windows to guarantee zero focus stealing."""
        try:
            import ctypes
            GWL_EXSTYLE = -20
            WS_EX_NOACTIVATE = 0x08000000
            WS_EX_TOPMOST = 0x00000008
            WS_EX_TRANSPARENT = 0x00000020
            hwnd = int(self.winId())
            if hwnd:
                ex_style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                ctypes.windll.user32.SetWindowLongW(
                    hwnd, GWL_EXSTYLE, ex_style | WS_EX_NOACTIVATE | WS_EX_TOPMOST | WS_EX_TRANSPARENT
                )
        except Exception:
            pass

    @property
    def current_node(self) -> MenuNode:
        """Returns the currently active MenuNode."""
        return self.menu_tree.get(self.current_node_id, self.menu_tree.get("ROOT"))

    @pyqtSlot(str)
    def on_file_linked(self, file_path: str) -> None:
        """Called when a user explicitly links a Python script."""
        if self.context_reader:
            self.context_reader.set_active_file(file_path)
            self.last_action_desc = f"📂 Vinculado: {os.path.basename(file_path)}"
            if self.current_node_id == "T9_LOCAL_VARS":
                self._refresh_local_symbols()
            self.update()

    def _refresh_local_symbols(self) -> None:
        """Refreshes local variables from active file via ContextReader."""
        if not self.context_reader:
            return
        symbols = self.context_reader.extract_local_symbols(getattr(config, "MAX_LOCAL_SYMBOLS", 12))
        new_items = populate_local_symbol_items(symbols, parent_id="T9")
        if "T9_LOCAL_VARS" in self.menu_tree:
            self.menu_tree["T9_LOCAL_VARS"].items = new_items

    def _trigger_ai_prediction(self) -> None:
        """
        Triggers async AIPredictorWorker.
        Prevents duplicate workers if one is already running (QA Requirement 3).
        Sets overlay to loading state '⏳ Analizando...' and updates 6 blocks dynamically.
        Extracts context non-blockingly on worker thread.
        """
        if self.ai_predictor_worker is not None:
            if self.ai_predictor_worker.isRunning():
                return
            try:
                self.ai_predictor_worker.predictions_ready.disconnect()
                self.ai_predictor_worker.status_changed.disconnect()
                self.ai_predictor_worker.prediction_failed.disconnect()
                self.ai_predictor_worker.finished.disconnect()
            except Exception:
                pass

        loading_preds = [
            "⏳ Analizando...",
            "⏳ Analizando...",
            "⏳ Analizando...",
            "⏳ Analizando...",
            "⏳ Analizando...",
            "⏳ Analizando...",
        ]
        if "SNIPPETS" in self.menu_tree:
            self.menu_tree["SNIPPETS"].items = populate_ai_prediction_items(loading_preds, parent_id="ROOT")
        self.is_ai_predicting = True
        self.last_action_desc = "⏳ IA Analizando..."
        self.ai_status_updated.emit("⏳ Consultando IA...")
        self.update()

        self.ai_predictor_worker = AIPredictorWorker(
            context_text="",
            local_symbols=[],
            provider=getattr(config, "LLM_PROVIDER", "ollama"),
            endpoint=getattr(config, "LLM_ENDPOINT", "http://localhost:11434/api/generate"),
            model=getattr(config, "LLM_MODEL", "codellama"),
            timeout=getattr(config, "LLM_TIMEOUT_SEC", 2.5),
            api_key=getattr(config, "LLM_API_KEY", ""),
            temperature=getattr(config, "LLM_TEMPERATURE", 0.2),
            context_reader=self.context_reader,
        )
        self.ai_predictor_worker.predictions_ready.connect(self._on_ai_predictions_ready)
        self.ai_predictor_worker.status_changed.connect(self._on_ai_status_changed)
        self.ai_predictor_worker.prediction_failed.connect(self._on_ai_prediction_failed)
        self.ai_predictor_worker.finished.connect(self._on_ai_worker_finished)
        self.ai_predictor_worker.start()

    @pyqtSlot(list)
    def _on_ai_predictions_ready(self, predictions: List[str]) -> None:
        """Called when AIPredictorWorker finishes with 6 suggestions."""
        if "SNIPPETS" in self.menu_tree:
            self.menu_tree["SNIPPETS"].items = populate_ai_prediction_items(predictions, parent_id="ROOT")
        self.is_ai_predicting = False
        self.last_action_desc = "⚡ 6 Sugerencias IA Listas"
        self.ai_status_updated.emit("Listo (6 sugerencias)")
        self.update()

    @pyqtSlot(str)
    def _on_ai_status_changed(self, status: str) -> None:
        """Emits AI status update."""
        self.ai_status_updated.emit(status)

    @pyqtSlot(str)
    def _on_ai_prediction_failed(self, error_msg: str) -> None:
        """Handles prediction failure notification."""
        self.ai_status_updated.emit(f"⚠️ {error_msg}")

    @pyqtSlot()
    def _on_ai_worker_finished(self) -> None:
        """Worker lifecycle completion."""
        self.is_ai_predicting = False

    def navigate_to(self, node_id: str) -> bool:
        """
        Navigates to a target menu node by ID.
        Updates state, refreshes dynamic nodes on demand, and triggers repaint.
        """
        if node_id in self.menu_tree:
            self.current_node_id = node_id
            if node_id == "T9_LOCAL_VARS":
                self._refresh_local_symbols()
            elif node_id in ("SNIPPETS", "AI_PREDICT"):
                self._trigger_ai_prediction()
            self.menu_navigated.emit(node_id)
            self.update()
            return True
        return False

    @pyqtSlot(float, float)
    def on_gaze_updated(self, gx: float, gy: float) -> None:
        """
        Receives normalized gaze coordinates from CameraTracker.
        Updates hovered block and gaze cursor position across the 3x3 grid,
        with sub-pixel geometry alignment matching visual category cards.
        """
        self.current_gaze = (gx, gy)

        # Determine 3x3 block index with card geometry alignment
        w = float(self.width()) if self.width() > 0 else 1920.0
        h = float(self.height()) if self.height() > 0 else 1080.0
        margin = 12.0
        header_h = 42.0
        avail_y = margin + header_h + margin
        avail_h = max(1.0, h - avail_y - margin)
        cell_h = avail_h / 3.0

        py = gy * h
        if py < avail_y:
            row = 0
        elif py >= avail_y + avail_h:
            row = 2
        else:
            row = min(2, max(0, int((py - avail_y) / cell_h)))

        avail_w = max(1.0, w - 2.0 * margin)
        cell_w = avail_w / 3.0
        px = gx * w
        if px < margin:
            col = 0
        elif px >= w - margin:
            col = 2
        else:
            col = min(2, max(0, int((px - margin) / cell_w)))

        block_idx = row * 3 + col

        if self.reading_mode:
            # In reading mode, inhibit all blocks except Block 4 (Resume trigger)
            if block_idx == 4:
                self.hovered_block = 4
            else:
                self.hovered_block = None
        else:
            self.hovered_block = block_idx

        self.update()

    @pyqtSlot(str)
    def on_gesture_triggered(self, gesture_name: str) -> None:
        """
        Handles facial gesture triggers (e.g. 'MOUTH_CLICK').
        Dispatches menu tree navigation or non-blocking code injection.
        Guarantees that clicks are not accumulated in queue while an injection is active.
        """
        if gesture_name != "MOUTH_CLICK":
            return

        target_block = self.hovered_block
        if target_block is None:
            return

        if self.reading_mode:
            if target_block == 4:
                # Resume active mode
                self.trigger_click_flash(4)
                self.toggle_reading_mode()
            return

        # Do not accumulate facial clicks while an injection is actively running
        if self.code_injector.is_busy and target_block != 4:
            return

        self.trigger_click_flash(target_block)

        # Retrieve active menu node and targeted item
        curr_node = self.current_node
        if curr_node is None or not (0 <= target_block < len(curr_node.items)):
            return

        item: MenuAction = curr_node.items[target_block]

        # 1. Pause / Reading Mode Trigger (Center block or PAUSE action)
        if target_block == 4 or item.action_type == "PAUSE":
            self.toggle_reading_mode()
            self.last_action_desc = "👁️ Modo Reposo Activo"
            self.block_activated.emit(target_block, "PAUSE_RESUME")
            return

        # 2. Back Navigation (Index 6 in submenus or BACK action)
        if item.action_type == "BACK":
            target_id = item.submenu_id or curr_node.parent_id or "ROOT"
            self.navigate_to(target_id)
            target_title = self.menu_tree[target_id].title if target_id in self.menu_tree else "RAÍZ"
            self.last_action_desc = f"⬅ Volver a {target_title}"
            self.block_activated.emit(target_block, item.id)
            return

        # 3. Submenu Forward Navigation
        if item.action_type == "SUBMENU":
            target_id = item.submenu_id
            if target_id and target_id in self.menu_tree:
                self.navigate_to(target_id)
                self.last_action_desc = f"📁 Menú: {self.menu_tree[target_id].title}"
            self.block_activated.emit(target_block, item.id)
            return

        # 4. AI Regenerate / Refresh Action
        if item.action_type == "AI_REFRESH" or item.id == "AI_REGENERATE":
            self._trigger_ai_prediction()
            self.block_activated.emit(target_block, item.id)
            return

        # 5. Code / Key Injection (SNIPPET or KEY)
        if item.action_type in ("SNIPPET", "KEY"):
            # Ignore placeholder while predicting
            if item.action_type == "SNIPPET" and (not item.snippet or "Analizando..." in item.snippet):
                return

            # Execute injection via non-blocking worker thread
            self.code_injector.execute_action(item)
            self.last_action_desc = f"{item.icon} {item.label}"
            self.action_executed.emit(item.id, self.last_action_desc)
            self.block_activated.emit(target_block, item.id)

            # Sticky Evaluation:
            # If neither the action nor the current node is sticky, return to ROOT!
            is_sticky = item.sticky or curr_node.sticky
            if not is_sticky and self.current_node_id != "ROOT":
                self.navigate_to("ROOT")
            else:
                self.update()
            return

        # 5. Exit Trigger
        if item.action_type == "EXIT" or item.id == "ACTION_EXIT":
            self.exit_requested.emit()
            self.block_activated.emit(target_block, item.id)
            return

        # Fallback default emission
        self.block_activated.emit(target_block, item.id)

    def toggle_reading_mode(self) -> None:
        """Toggles between Active HUD mode and 10% Opacity Reading Mode."""
        self.reading_mode = not self.reading_mode
        self.current_opacity = config.OVERLAY_OPACITY_READING if self.reading_mode else config.OVERLAY_OPACITY_ACTIVE
        if self.reading_mode:
            self.hovered_block = None
        self.reading_mode_toggled.emit(self.reading_mode)
        self.update()

    def trigger_click_flash(self, block_idx: int) -> None:
        """Triggers vibrant green active highlight on clicked block."""
        self.active_click_block = block_idx
        self.update()
        QTimer.singleShot(int(config.CLICK_FLASH_DURATION_SEC * 1000), self._clear_click_flash)

    def _clear_click_flash(self) -> None:
        self.active_click_block = None
        self.update()

    def _get_category_for_item(self, item: MenuAction, block_idx: int) -> str:
        """Determines the semantic category for a menu action block."""
        if block_idx == 4 or item.action_type == "PAUSE":
            return "PAUSE"
        if item.action_type == "BACK":
            return "BACK"
        if item.action_type == "EXIT" or item.id == "ACTION_EXIT":
            return "EXIT"

        sub_id = (item.submenu_id or "").upper()
        act_id = item.id.upper()
        curr_id = self.current_node_id.upper()

        if sub_id == "FLOW" or "FLOW" in curr_id or any(k in act_id for k in ("IF", "LOOP", "WHILE", "FOR", "TRY", "RETURN", "FLOW")):
            return "FLOW"
        if sub_id == "STRUCT" or "STRUCT" in curr_id or any(k in act_id for k in ("FUNC", "CLASS", "DEF", "STRUCT", "DATA", "LIST", "DICT", "T9")):
            return "STRUCT"
        if sub_id == "OPERATORS" or "OP" in curr_id or any(k in act_id for k in ("OPERATOR", "OP_", "MATH", "BOOL", "COMPARE")):
            return "OPERATORS"
        if sub_id == "NAV" or "NAV" in curr_id or any(k in act_id for k in ("NAV_", "UP", "DOWN", "LEFT", "RIGHT", "PAGE", "WORD")):
            return "NAV"
        if sub_id in ("SNIPPETS", "AI_PREDICT") or "SNIPPET" in curr_id or "AI" in act_id or "PREDICT" in act_id:
            return "AI"
        if sub_id in ("EDIT", "FORMAT") or "EDIT" in curr_id or "FORMAT" in curr_id or any(k in act_id for k in ("BACKSPACE", "DELETE", "ENTER", "TAB", "INDENT")):
            return "EDIT"

        return "DEFAULT"

    def paintEvent(self, event) -> None:
        """Paints Glassmorphic Breadcrumb Header Bar, 3x3 Category Cards, and Dual-Ring Reticle."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = float(self.width())
        h = float(self.height())
        margin = self.margin
        header_h = self.breadcrumb_height

        curr_node = self.current_node
        items = curr_node.items if curr_node else []

        # =====================================================================
        # 1. Top Breadcrumb Bar (Acrylic Glassmorphism)
        # =====================================================================
        header_rect = QRectF(margin, margin, w - 2.0 * margin, header_h)
        painter.setOpacity(0.95 if not self.reading_mode else 0.30)

        # Header background pill
        painter.setBrush(self._brush_header_bg)
        painter.setPen(self._pen_header_border)
        painter.drawRoundedRect(header_rect, 8.0, 8.0)

        # Left: Mode Pill Badge + Navigation Trail
        pill_w = 136.0
        pill_h = header_h - 14.0
        pill_rect = QRectF(header_rect.x() + 8.0, header_rect.y() + 7.0, pill_w, pill_h)

        if self.reading_mode:
            painter.setBrush(self._brush_pill_read)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(pill_rect, 5.0, 5.0)
            painter.setPen(self._color_pill_text)
            painter.setFont(self._font_header_pill)
            painter.drawText(pill_rect, Qt.AlignmentFlag.AlignCenter, "👁️ MODO LECTURA")
        else:
            painter.setBrush(self._brush_pill_edit)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(pill_rect, 5.0, 5.0)
            painter.setPen(self._color_pill_text)
            painter.setFont(self._font_header_pill)
            painter.drawText(pill_rect, Qt.AlignmentFlag.AlignCenter, "⚡ MODO EDICIÓN")

        # Breadcrumb trail text
        breadcrumb_path = get_breadcrumb_path(self.menu_tree, self.current_node_id).replace(" > ", " › ")
        if curr_node and curr_node.sticky:
            breadcrumb_path += "  [📌 FIJO]"

        left_text = f"📁 {breadcrumb_path}"
        text_start_x = header_rect.x() + pill_w + 18.0
        max_left_w = int(header_rect.width() * 0.32)
        painter.setPen(self._pen_header_left)
        painter.setFont(self._font_header_left)
        elided_left = painter.fontMetrics().elidedText(left_text, Qt.TextElideMode.ElideMiddle, max_left_w)
        painter.drawText(
            int(text_start_x),
            int(header_rect.y()),
            max_left_w,
            int(header_rect.height()),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            elided_left,
        )

        # Center: Emergency Hotkey Documentation Pill
        emergency_text = "🚨 Emergencia: Ctrl+Alt+Q para salir"
        center_pill_w = 260.0
        center_pill_rect = QRectF(header_rect.center().x() - center_pill_w * 0.5, header_rect.y() + 7.0, center_pill_w, pill_h)
        painter.setBrush(QBrush(QColor(239, 68, 68, 25)))
        painter.setPen(QPen(QColor(239, 68, 68, 120), 1.0))
        painter.drawRoundedRect(center_pill_rect, 5.0, 5.0)

        painter.setPen(self._pen_header_center)
        painter.setFont(self._font_header_center)
        painter.drawText(center_pill_rect, Qt.AlignmentFlag.AlignCenter, emergency_text)

        # Right: Last executed action pill
        last_action_str = f"✨ Última: {self.last_action_desc}"
        max_right_w = int(header_rect.width() * 0.30)
        right_pill_rect = QRectF(header_rect.right() - max_right_w - 8.0, header_rect.y() + 7.0, max_right_w, pill_h)
        painter.setBrush(QBrush(QColor(56, 189, 248, 22)))
        painter.setPen(QPen(QColor(56, 189, 248, 90), 1.0))
        painter.drawRoundedRect(right_pill_rect, 5.0, 5.0)

        painter.setPen(self._pen_header_right)
        painter.setFont(self._font_header_right)
        elided_right = painter.fontMetrics().elidedText(last_action_str, Qt.TextElideMode.ElideRight, max_right_w - 16)
        painter.drawText(
            right_pill_rect,
            Qt.AlignmentFlag.AlignCenter,
            elided_right,
        )

        # =====================================================================
        # 2. 3x3 Grid Category Cards
        # =====================================================================
        avail_y = margin + header_h + margin
        avail_h = h - avail_y - margin
        cell_w = (w - 2.0 * margin) / 3.0
        cell_h = avail_h / 3.0

        for i in range(9):
            if i >= len(items):
                continue
            item = items[i]
            col = i % 3
            row = i // 3

            rect = QRectF(
                margin + col * cell_w + 5.0,
                avail_y + row * cell_h + 5.0,
                cell_w - 10.0,
                cell_h - 10.0,
            )

            is_active_click = (self.active_click_block == i)
            is_hover = (self.hovered_block == i)
            cat = self._get_category_for_item(item, i)

            # Opacity logic
            if self.reading_mode:
                if i == 4:
                    block_opacity = 0.90 if (is_active_click or is_hover) else 0.40
                else:
                    block_opacity = self.current_opacity
            else:
                block_opacity = self.current_opacity

            painter.setOpacity(block_opacity)

            # Pre-allocated styling determination (zero allocations per frame)
            if is_active_click:
                block_brush = self._brush_click
                border_pen = self._pen_click
                text_color = self._color_click_text
                hint_color = self._color_click_hint
            elif is_hover:
                block_brush = self._brush_hover
                border_pen = self._pen_hover
                text_color = self._color_hover_text
                hint_color = self._color_hover_hint
            elif self.reading_mode:
                if i == 4:
                    block_brush = self._brush_reading_center
                    border_pen = self._pen_reading_center
                    text_color = self._color_reading_center_text
                    hint_color = self._color_reading_center_hint
                else:
                    block_brush = self._brush_reading_other
                    border_pen = self._pen_reading_other
                    text_color = self._color_reading_other_text
                    hint_color = self._color_reading_other_hint
            else:
                block_brush = self._cat_brushes.get(cat, self._brush_default)
                border_pen = self._cat_pens.get(cat, self._pen_default)
                text_color = self._color_default_text
                hint_color = self._color_default_hint

            # Draw card rounded rectangle
            painter.setBrush(block_brush)
            painter.setPen(border_pen)
            painter.drawRoundedRect(rect, 12.0, 12.0)

            # Draw subtle top accent hairline (acrylic category bar)
            if not self.reading_mode or i == 4:
                top_pen = self._cat_top_pens.get(cat, self._pen_default) if not (is_active_click or is_hover) else border_pen
                painter.setPen(top_pen)
                painter.drawLine(QPointF(rect.x() + 16.0, rect.y() + 2.0), QPointF(rect.right() - 16.0, rect.y() + 2.0))

            # Determine labels
            label_text = f"{item.icon} {item.label}"
            hint_text = item.hint

            if self.reading_mode and i == 4:
                label_text = "👁️ 5: REANUDAR"
                hint_text = "Modo Lectura Activo (Mire y Abra Boca)"

            # Draw main label
            painter.setPen(text_color)
            painter.setFont(self._font_label)
            painter.drawText(
                int(rect.x() + 14),
                int(rect.y() + 12),
                int(rect.width() - 28),
                28,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                label_text,
            )

            # Draw hint / subtitle
            if hint_text:
                painter.setPen(hint_color)
                painter.setFont(self._font_hint)
                painter.drawText(
                    int(rect.x() + 14),
                    int(rect.y() + 40),
                    int(rect.width() - 28),
                    22,
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                    hint_text,
                )

            # Submenu or action pill indicator on bottom-right of block
            if not self.reading_mode and not is_active_click:
                badge_info = self._cat_badges.get(cat, ("", self._color_badge_default))
                badge_text, badge_color = badge_info

                if item.action_type == "SUBMENU":
                    badge_text = "📁 SUBMENÚ"
                    badge_color = self._color_badge_submenu
                elif item.action_type == "BACK":
                    badge_text = "⬅ VOLVER"
                    badge_color = self._color_badge_back
                elif item.sticky:
                    badge_text = "📌 FIJO"
                    badge_color = self._color_badge_sticky

                if badge_text:
                    painter.setPen(badge_color)
                    painter.setFont(self._font_badge)
                    painter.drawText(
                        int(rect.x() + 14),
                        int(rect.y() + rect.height() - 26),
                        int(rect.width() - 28),
                        18,
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                        badge_text,
                    )

        # =====================================================================
        # 3. Refined High-Visibility Dual-Ring Reticle with Glow Aura
        # =====================================================================
        if not self.reading_mode or self.hovered_block == 4:
            painter.setOpacity(self.current_opacity if not self.reading_mode else 0.90)
            gx, gy = self.current_gaze
            cx = gx * w
            cy = gy * h
            r = float(config.OVERLAY_POINTER_RADIUS)

            # 1. Outer subtle glow aura
            painter.setBrush(self._brush_pointer_glow)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(cx, cy), r + 8.0, r + 8.0)

            # 2. Middle precision ring
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(self._pen_pointer_ring)
            painter.drawEllipse(QPointF(cx, cy), r + 2.0, r + 2.0)

            # 3. Inner crisp fixation dot
            painter.setBrush(self._brush_pointer_dot)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(cx, cy), r - 3.0, r - 3.0)

            # 4. Micro crosshairs (hairline precision ticks)
            painter.setPen(self._pen_pointer_ticks)
            painter.drawLine(QPointF(cx - r - 7.0, cy), QPointF(cx - r - 2.0, cy))
            painter.drawLine(QPointF(cx + r + 2.0, cy), QPointF(cx + r + 7.0, cy))
            painter.drawLine(QPointF(cx, cy - r - 7.0), QPointF(cx, cy - r - 2.0))
            painter.drawLine(QPointF(cx, cy + r + 2.0), QPointF(cx, cy + r + 7.0))

        painter.end()

    def closeEvent(self, event) -> None:
        """Safely stops background code injector and AI worker threads on window close without terminate()."""
        if hasattr(self, "ai_predictor_worker") and self.ai_predictor_worker is not None:
            try:
                if self.ai_predictor_worker.isRunning():
                    self.ai_predictor_worker.stop()
                    self.ai_predictor_worker.wait(2000)
            except Exception:
                pass
        if hasattr(self, "code_injector") and self.code_injector is not None:
            self.code_injector.stop()
        super().closeEvent(event)
