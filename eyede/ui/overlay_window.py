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

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QRectF, QPointF
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
        self.breadcrumb_height: float = 38.0
        self.margin: float = 8.0

        # Window title for identification
        self.setWindowTitle("EyeDE - Gaze Macro Grid HUD (Phase 3)")

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
        self.ai_predictor_worker.finished.connect(self._on_ai_worker_finished)
        self.ai_predictor_worker.start()

    def _on_ai_predictions_ready(self, predictions: List[str]) -> None:
        """Called when AIPredictorWorker finishes with 6 suggestions."""
        if "SNIPPETS" in self.menu_tree:
            self.menu_tree["SNIPPETS"].items = populate_ai_prediction_items(predictions, parent_id="ROOT")
        self.is_ai_predicting = False
        self.last_action_desc = "⚡ 6 Sugerencias IA Listas"
        self.ai_status_updated.emit("Listo (6 sugerencias)")
        self.update()

    def _on_ai_status_changed(self, status: str) -> None:
        """Emits AI status update."""
        self.ai_status_updated.emit(status)

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

    def on_gaze_updated(self, gx: float, gy: float) -> None:
        """
        Receives normalized gaze coordinates from CameraTracker.
        Updates hovered block and gaze cursor position across the 3x3 grid.
        """
        self.current_gaze = (gx, gy)

        # Determine 3x3 block index
        col = min(2, max(0, int(gx * 3)))
        row = min(2, max(0, int(gy * 3)))
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

    def paintEvent(self, event) -> None:
        """Paints Breadcrumb Header Bar, 3x3 Menu Blocks, and Gaze Cursor."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = float(self.width())
        h = float(self.height())
        margin = self.margin
        header_h = self.breadcrumb_height

        curr_node = self.current_node
        items = curr_node.items if curr_node else []

        # =====================================================================
        # 1. Top Breadcrumb Bar
        # =====================================================================
        header_rect = QRectF(margin, margin, w - 2 * margin, header_h)
        painter.setOpacity(0.92 if not self.reading_mode else 0.25)

        # Header background pill
        header_bg = QColor(14, 18, 24, 230)
        header_border = QColor(65, 75, 95, 200)
        painter.setBrush(QBrush(header_bg))
        painter.setPen(QPen(header_border, 1.5))
        painter.drawRoundedRect(header_rect, 6.0, 6.0)

        # Breadcrumb trail text (Left aligned, elided if long)
        breadcrumb_path = get_breadcrumb_path(self.menu_tree, self.current_node_id)
        if curr_node and curr_node.sticky:
            breadcrumb_path += "  [STICKY 📌]"

        left_text = f"📁 {breadcrumb_path}"
        max_left_w = int(header_rect.width() * 0.55)
        painter.setPen(QColor(255, 215, 60))
        font_header_left = QFont("Segoe UI", 10, QFont.Weight.Bold)
        painter.setFont(font_header_left)
        elided_left = painter.fontMetrics().elidedText(left_text, Qt.TextElideMode.ElideMiddle, max_left_w)
        painter.drawText(
            int(header_rect.x() + 12),
            int(header_rect.y()),
            max_left_w,
            int(header_rect.height()),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            elided_left,
        )

        # Last executed action text (Right aligned, elided if long)
        last_action_str = f"Última: {self.last_action_desc}"
        max_right_w = int(header_rect.width() * 0.40)
        painter.setPen(QColor(160, 230, 180))
        font_header_right = QFont("Segoe UI", 9)
        painter.setFont(font_header_right)
        elided_right = painter.fontMetrics().elidedText(last_action_str, Qt.TextElideMode.ElideRight, max_right_w)
        painter.drawText(
            int(header_rect.x() + header_rect.width() - max_right_w - 12),
            int(header_rect.y()),
            max_right_w,
            int(header_rect.height()),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            elided_right,
        )

        # =====================================================================
        # 2. 3x3 Grid Blocks
        # =====================================================================
        avail_y = margin + header_h + margin
        avail_h = h - avail_y - margin
        cell_w = (w - 2 * margin) / 3.0
        cell_h = avail_h / 3.0

        font_label = QFont("Segoe UI", 12, QFont.Weight.Bold)
        font_hint = QFont("Segoe UI", 9)
        font_badge = QFont("Segoe UI", 8, QFont.Weight.Bold)

        for i in range(9):
            if i >= len(items):
                continue
            item = items[i]

            col = i % 3
            row = i // 3

            rect = QRectF(
                margin + col * cell_w + 4.0,
                avail_y + row * cell_h + 4.0,
                cell_w - 8.0,
                cell_h - 8.0,
            )

            is_active_click = (self.active_click_block == i)
            is_hover = (self.hovered_block == i)

            # Opacity logic
            if self.reading_mode:
                if i == 4:
                    block_opacity = 0.85 if (is_active_click or is_hover) else 0.35
                else:
                    block_opacity = self.current_opacity
            else:
                block_opacity = self.current_opacity

            painter.setOpacity(block_opacity)

            # Styling determination
            if is_active_click:
                bg_color = QColor(*config.OVERLAY_COLOR_CLICK)
                border_pen = QPen(QColor(*config.OVERLAY_CLICK_BORDER_COLOR), 3)
                text_color = QColor(10, 30, 15)
                hint_color = QColor(25, 55, 30)
            elif is_hover:
                bg_color = QColor(*config.OVERLAY_COLOR_HOVER)
                border_pen = QPen(QColor(*config.OVERLAY_HOVER_BORDER_COLOR), config.OVERLAY_HOVER_BORDER_WIDTH)
                text_color = QColor(*config.OVERLAY_TEXT_HOVER_COLOR)
                hint_color = QColor(230, 235, 245)
            elif self.reading_mode:
                if i == 4:
                    bg_color = QColor(25, 45, 75, 180)
                    border_pen = QPen(QColor(0, 150, 255, 220), 2)
                    text_color = QColor(200, 225, 255)
                    hint_color = QColor(150, 180, 220)
                else:
                    bg_color = QColor(15, 18, 22, 50)
                    border_pen = QPen(QColor(40, 45, 55, 60), 1)
                    text_color = QColor(120, 130, 145, 100)
                    hint_color = QColor(80, 90, 105, 80)
            else:
                if i == 4:
                    bg_color = QColor(*config.OVERLAY_COLOR_REST)
                    border_pen = QPen(QColor(*config.OVERLAY_REST_BORDER_COLOR), config.OVERLAY_BORDER_WIDTH)
                elif item.action_type == "BACK":
                    bg_color = QColor(36, 28, 38, 185)
                    border_pen = QPen(QColor(180, 110, 190, 180), 2)
                elif item.action_type == "SUBMENU":
                    bg_color = QColor(22, 28, 38, 185)
                    border_pen = QPen(QColor(70, 120, 180, 180), config.OVERLAY_BORDER_WIDTH)
                else:
                    bg_color = QColor(*config.OVERLAY_COLOR_BG)
                    border_pen = QPen(QColor(*config.OVERLAY_COLOR_BORDER), config.OVERLAY_BORDER_WIDTH)
                text_color = QColor(*config.OVERLAY_TEXT_COLOR)
                hint_color = QColor(*config.OVERLAY_TEXT_HINT_COLOR)

            # Draw block rectangle
            painter.setBrush(QBrush(bg_color))
            painter.setPen(border_pen)
            painter.drawRoundedRect(rect, 10.0, 10.0)

            # Determine labels
            label_text = f"{item.icon} {item.label}"
            hint_text = item.hint

            if self.reading_mode and i == 4:
                label_text = "👁️ 5: REANUDAR"
                hint_text = "Modo Lectura Activo (Mire y Abra Boca)"

            # Draw main label
            painter.setPen(text_color)
            painter.setFont(font_label)
            painter.drawText(
                int(rect.x() + 10),
                int(rect.y() + 10),
                int(rect.width() - 20),
                26,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                label_text,
            )

            # Draw hint / subtitle
            if hint_text:
                painter.setPen(hint_color)
                painter.setFont(font_hint)
                painter.drawText(
                    int(rect.x() + 10),
                    int(rect.y() + 36),
                    int(rect.width() - 20),
                    20,
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                    hint_text,
                )

            # Submenu or action pill indicator on bottom-right of block
            if not self.reading_mode and not is_active_click:
                badge_text = ""
                badge_color = QColor(140, 150, 165, 160)
                if item.action_type == "SUBMENU":
                    badge_text = "📁 SUBMENÚ"
                    badge_color = QColor(100, 170, 255, 180)
                elif item.action_type == "BACK":
                    badge_text = "⬅ VOLVER"
                    badge_color = QColor(220, 150, 230, 180)
                elif item.sticky:
                    badge_text = "📌 FIJO"
                    badge_color = QColor(255, 195, 60, 180)

                if badge_text:
                    painter.setPen(badge_color)
                    painter.setFont(font_badge)
                    painter.drawText(
                        int(rect.x() + 10),
                        int(rect.y() + rect.height() - 24),
                        int(rect.width() - 20),
                        18,
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                        badge_text,
                    )

        # =====================================================================
        # 3. Gaze Pointer Reticle
        # =====================================================================
        if not self.reading_mode or self.hovered_block == 4:
            painter.setOpacity(self.current_opacity if not self.reading_mode else 0.85)
            gx, gy = self.current_gaze
            cx = gx * w
            cy = gy * h
            r = config.OVERLAY_POINTER_RADIUS

            # Outer ring
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(*config.OVERLAY_POINTER_OUTLINE), 2))
            painter.drawEllipse(QPointF(cx, cy), r + 3, r + 3)

            # Center dot
            painter.setBrush(QBrush(QColor(*config.OVERLAY_POINTER_COLOR)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(cx, cy), r, r)

        painter.end()

    def closeEvent(self, event) -> None:
        """Safely stops background code injector and AI worker threads on window close."""
        if hasattr(self, "ai_predictor_worker") and self.ai_predictor_worker is not None:
            try:
                if self.ai_predictor_worker.isRunning():
                    self.ai_predictor_worker.quit()
                    if not self.ai_predictor_worker.wait(1000):
                        self.ai_predictor_worker.terminate()
                        self.ai_predictor_worker.wait(300)
            except Exception:
                pass
        if hasattr(self, "code_injector") and self.code_injector is not None:
            self.code_injector.stop()
        super().closeEvent(event)
