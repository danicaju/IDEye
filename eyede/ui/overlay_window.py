"""
Overlay Window Module for IDEye (Phase 2 & 3)
Transparent, Non-Focus-Stealing 3x3 Macro-Block Grid Overlay with Hierarchical
Syntax Navigation Trees, Real-Time Code Injection, and Breadcrumb Status Bar.

Features:
- Configures Qt.WindowType.WindowDoesNotAcceptFocus, FramelessWindowHint,
  WindowStaysOnTopHint, Tool, and WA_TranslucentBackground.
- Ensures external IDEs (e.g. VS Code, PyCharm) NEVER lose keyboard focus or cursor blink.
- Renders hierarchical 3x3 Menu Trees (build_menu_tree):
    * Root Menu (Flow, Struct, Operators, Nav, Pause, T9, Edit, Format, Snippets).
    * Submenus with visual indicators ('SUBMENU', 'ACCION', 'PAUSA', 'VOLVER').
- Top Breadcrumb Bar displaying current navigation path (e.g. 'RAIZ > FLUJO') and last executed action.
- Sticky submenu mode for repetitive actions (Nav, Edit, Format).
- Non-blocking CodeInjector integration: snippets pasted via clipboard with cursor centering and keystrokes.
- Block 4 (Center: 'PAUSA / MODO LECTURA') toggles HUD opacity to 10% and inhibits actions during reading.
"""

from typing import Optional, Tuple, Dict, Any, List
import sys
import os
import time

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, pyqtSlot, QRectF, QPointF
from PyQt6.QtGui import QPainter, QColor, QFont, QPen, QBrush
from PyQt6.QtWidgets import QWidget

try:
    import eyede.config as config
    from eyede.ui.icon_manager import IconManager
    from eyede.actions.code_injector import CodeInjector
    from eyede.actions.language_support import (
        LANG_PYTHON,
        LANG_TYPESCRIPT,
        LANG_RUST,
        LANG_CPP,
        LANG_GO,
        normalize_language,
        get_language_display_name,
        get_language_badge,
    )
    from eyede.actions.menu_trees import (
        MenuNode,
        MenuAction,
        build_menu_tree,
        get_breadcrumb_path,
        populate_ai_prediction_items,
        populate_local_symbol_items,
        populate_exit_confirm_items,
        populate_help_items,
        populate_lang_select_items,
        get_adaptive_context_node,
        create_adaptive_menu_action,
    )
    from eyede.actions.context_reader import ContextReader, detect_syntactic_context
    from eyede.actions.ai_predictor import AIPredictorWorker
    from eyede.modes.mode_manager import ModeManager
except ImportError:
    import config
    from ui.icon_manager import IconManager
    from actions.code_injector import CodeInjector
    from actions.language_support import (
        LANG_PYTHON,
        LANG_TYPESCRIPT,
        LANG_RUST,
        LANG_CPP,
        LANG_GO,
        normalize_language,
        get_language_display_name,
        get_language_badge,
    )
    from actions.menu_trees import (
        MenuNode,
        MenuAction,
        build_menu_tree,
        get_breadcrumb_path,
        populate_ai_prediction_items,
        populate_local_symbol_items,
        populate_exit_confirm_items,
        populate_help_items,
        populate_lang_select_items,
        get_adaptive_context_node,
        create_adaptive_menu_action,
    )
    from actions.context_reader import ContextReader, detect_syntactic_context
    from actions.ai_predictor import AIPredictorWorker
    from modes.mode_manager import ModeManager


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
    tracking_mode_cycle_requested = pyqtSignal()
    adaptive_ast_toggled = pyqtSignal(bool)
    ast_context_detected = pyqtSignal(str)  # (context_name)
    language_changed = pyqtSignal(str)  # (language_code)
    context_mode_changed = pyqtSignal(str, str, str)  # (mode_id, display_name, theme_color)
    mode_changed = context_mode_changed

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        code_injector: Optional[CodeInjector] = None,
        menu_tree: Optional[Dict[str, MenuNode]] = None,
        context_reader: Optional[ContextReader] = None,
        mode_manager: Optional[Any] = None,
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

        app_icon = IconManager.instance().get_app_icon()
        if not app_icon.isNull():
            self.setWindowIcon(app_icon)

        # Win32 OS-level non-activation protection
        if sys.platform == "win32":
            self._apply_win32_no_activate()

        # 2. Code Injection & Menu Tree Subsystems
        self.current_language: str = getattr(config, "DEFAULT_PROGRAMMING_LANGUAGE", "PYTHON")
        self.code_injector = code_injector if code_injector is not None else CodeInjector(async_mode=True)
        self.menu_tree: Dict[str, MenuNode] = menu_tree if menu_tree is not None else build_menu_tree(self.current_language)
        self.context_reader: ContextReader = context_reader if context_reader is not None else ContextReader()
        self.mode_manager = mode_manager if mode_manager is not None else ModeManager(
            initial_mode="coding", language=self.current_language
        )
        try:
            self.mode_manager.set_language(self.current_language)
        except Exception:
            pass
        self.current_context_mode_id: str = getattr(self.mode_manager, "current_mode_id", "coding")
        self.current_context_mode_name: str = getattr(self.mode_manager, "current_mode", None).display_name if getattr(self.mode_manager, "current_mode", None) is not None else "CÓDIGO (AST)"
        self.theme_color: str = getattr(self.mode_manager, "current_mode", None).theme_color if getattr(self.mode_manager, "current_mode", None) is not None else "#00F0FF"
        self._mode_banner_text: str = ""
        self._mode_banner_until: float = 0.0
        self._mode_banner_start: float = 0.0
        self.hovered_header_mode: bool = False
        self.active_click_header_mode: bool = False
        self.header_mode_rect: QRectF = QRectF()
        try:
            self.mode_manager.mode_changed.connect(self._on_context_mode_changed)
        except Exception:
            pass
        self.ai_predictor_worker: Optional[AIPredictorWorker] = None
        self.is_ai_predicting: bool = False
        self.current_node_id: str = "ROOT"
        self.last_action_desc: str = "Ninguna"

        # Adaptive AST Context Menu Subsystem (Phase Extra - Option A)
        self.adaptive_ast_enabled: bool = getattr(config, "ENABLE_ADAPTIVE_AST_MENUS", True)
        self._last_detected_context_name: str = "GENERAL"
        self._cached_adaptive_node: Optional[MenuNode] = None
        if "MENU_STANDARD" not in self.menu_tree and "ROOT" in self.menu_tree:
            std_items = list(self.menu_tree["ROOT"].items)
            std_items[8] = create_adaptive_menu_action("9")
            self.menu_tree["MENU_STANDARD"] = MenuNode(
                id="MENU_STANDARD",
                title="MENÚ ESTÁNDAR",
                breadcrumb_label="ESTÁNDAR",
                items=std_items,
                parent_id="ROOT",
                sticky=False,
            )

        if "HELP" not in self.menu_tree:
            self.menu_tree["HELP"] = MenuNode(
                id="HELP",
                title="GUÍA DE GESTOS Y ATAJOS",
                breadcrumb_label="AYUDA / GESTOS",
                items=populate_help_items(parent_id="ROOT"),
                parent_id="ROOT",
                sticky=False,
            )

        if "LANG_SELECT" not in self.menu_tree:
            self.menu_tree["LANG_SELECT"] = MenuNode(
                id="LANG_SELECT",
                title="SELECCIONAR LENGUAJE",
                breadcrumb_label="LENGUAJE",
                items=populate_lang_select_items(parent_id="ROOT"),
                parent_id="ROOT",
                sticky=False,
            )

        # 3. State tracking
        self.reading_mode: bool = False
        self.current_opacity: float = config.OVERLAY_OPACITY_ACTIVE
        self.hovered_block: Optional[int] = None
        self.active_click_block: Optional[int] = None
        self.current_gaze: Tuple[float, float] = (0.5, 0.5)

        # Hands-free header exit button state
        self.hovered_header_exit: bool = False
        self.active_click_header_exit: bool = False
        self.header_exit_rect: QRectF = QRectF()

        # Hands-free header help button & cheat sheet modal state
        self.hovered_header_help: bool = False
        self.active_click_header_help: bool = False
        self.header_help_rect: QRectF = QRectF()
        self.show_help_modal: bool = False
        self.help_modal_rect: QRectF = QRectF()
        self.help_modal_close_rect: QRectF = QRectF()
        self.hovered_help_modal_close: bool = False

        # Hands-free header language button state
        self.hovered_header_lang: bool = False
        self.active_click_header_lang: bool = False
        self.header_lang_rect: QRectF = QRectF()

        # Layout constants & right dock margin (clears space for DebugWidget)
        self.breadcrumb_height: float = 52.0
        self.margin: float = 8.0
        self.grid_right_margin: float = float(getattr(config, "OVERLAY_GRID_RIGHT_MARGIN", 364.0))
        self.resize(1920, 1080)

        # Window title for identification
        self.setWindowTitle("IDEye - Gaze Macro Grid HUD (Phase 5)")

        # 4. Pre-allocated rendering objects to prevent 30/60 FPS GC pressure and memory leaks
        self._font_header_pill = QFont("Segoe UI", 9, QFont.Weight.Bold)
        self._font_header_bold_btn = QFont("Segoe UI", 11, QFont.Weight.Bold)
        self._font_header_left = QFont("Segoe UI", 10, QFont.Weight.Bold)
        self._font_header_center = QFont("Segoe UI", 9, QFont.Weight.Bold)
        self._font_header_right = QFont("Segoe UI", 9)
        self._font_label = QFont("Segoe UI", 12, QFont.Weight.Bold)
        self._font_hint = QFont("Segoe UI", 9)
        self._font_badge = QFont("Segoe UI", 8, QFont.Weight.Bold)
        self._font_modal_title = QFont("Segoe UI", 15, QFont.Weight.Bold)
        self._font_modal_subtitle = QFont("Segoe UI", 9)
        self._font_modal_section = QFont("Segoe UI", 11, QFont.Weight.Bold)
        self._font_modal_item_title = QFont("Segoe UI", 10, QFont.Weight.Bold)
        self._font_modal_item_desc = QFont("Segoe UI", 8)

        # Header bar styles (Acrylic Glassmorphism)
        self._brush_header_bg = QBrush(QColor(13, 17, 23, 160))
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
            "LANG": QPen(QColor(168, 85, 247, 220), 2.5),
            "DEFAULT": QPen(QColor(100, 116, 139, 180), 2.0),
        }
        self._cat_badges = {
            "FLOW": ("FLUJO", QColor(34, 211, 238)),
            "STRUCT": ("ESTRUCTURA", QColor(251, 191, 36)),
            "OPERATORS": ("OPERADOR", QColor(192, 132, 252)),
            "NAV": ("NAVEGACIÓN", QColor(96, 165, 250)),
            "PAUSE": ("REPOSO", QColor(52, 211, 153)),
            "BACK": ("VOLVER", QColor(244, 114, 182)),
            "EDIT": ("EDICIÓN", QColor(129, 140, 248)),
            "AI": ("IA / CÓDIGO", QColor(240, 171, 252)),
            "EXIT": ("SALIR", QColor(248, 113, 113)),
            "LANG": ("LENGUAJE", QColor(168, 85, 247)),
            "DEFAULT": ("ACCIÓN", QColor(148, 163, 184)),
        }

        # High-visibility Dual-ring Gaze Pointer Reticle
        self._brush_pointer_glow = QBrush(QColor(56, 189, 248, 45))
        self._pen_pointer_ring = QPen(QColor(*config.OVERLAY_POINTER_OUTLINE), 2.2)
        self._brush_pointer_dot = QBrush(QColor(*config.OVERLAY_POINTER_COLOR))
        self._pen_pointer_ticks = QPen(QColor(255, 255, 255, 200), 1.5)
        self._update_header_exit_rect()

    def resizeEvent(self, event) -> None:
        """Handles window resize events to keep interactive target geometry updated."""
        super().resizeEvent(event)
        self._update_header_exit_rect()

    def showEvent(self, event) -> None:
        """Ensures Win32 non-activating and topmost styles are reapplied when shown/restored."""
        super().showEvent(event)
        self._update_header_exit_rect()
        if sys.platform == "win32":
            self._apply_win32_no_activate()

    def _get_effective_right_margin(self, w: float) -> float:
        """
        Returns the effective right margin to accommodate the docked DebugWidget
        while guaranteeing normalized center gaze (0.5, 0.5) always lands on Center Block 4.
        """
        base_right_margin = float(getattr(self, "grid_right_margin", 364.0))
        if w >= 1920.0:
            return base_right_margin
        return base_right_margin * (w / 1920.0)

    def set_grid_right_margin(self, margin: float) -> None:
        """Sets the reserved right margin to prevent HUD overlap with docked debug window."""
        self.grid_right_margin = max(0.0, float(margin))
        self._update_header_exit_rect()
        self.update()

    def get_block_rect(self, index: int) -> QRectF:
        """Computes the QRectF bounding box for a given 3x3 block index."""
        w = float(self.width()) if self.width() > 0 else 1920.0
        h = float(self.height()) if self.height() > 0 else 1080.0
        margin = self.margin
        header_h = self.breadcrumb_height
        avail_y = margin + header_h + margin
        avail_h = max(1.0, h - avail_y - margin)
        effective_right_margin = self._get_effective_right_margin(w)
        avail_w = max(1.0, w - 2.0 * margin - effective_right_margin)
        cell_w = avail_w / 3.0
        cell_h = avail_h / 3.0
        col = index % 3
        row = index // 3
        return QRectF(
            margin + col * cell_w + 5.0,
            avail_y + row * cell_h + 5.0,
            max(1.0, cell_w - 10.0),
            max(1.0, cell_h - 10.0),
        )

    def _update_help_modal_rect(self) -> None:
        """Computes the interactive bounding boxes of the acrylic cheat sheet modal and its close button."""
        w = float(self.width()) if self.width() > 0 else 1920.0
        h = float(self.height()) if self.height() > 0 else 1080.0
        card_w = min(880.0, max(400.0, w - 80.0))
        card_h = min(560.0, max(380.0, h - 80.0))
        card_x = (w - card_w) * 0.5
        card_y = (h - card_h) * 0.5
        self.help_modal_rect = QRectF(card_x, card_y, card_w, card_h)
        close_btn_w = min(380.0, card_w - 40.0)
        close_btn_h = 42.0
        self.help_modal_close_rect = QRectF(
            card_x + (card_w - close_btn_w) * 0.5,
            card_y + card_h - close_btn_h - 14.0,
            close_btn_w,
            close_btn_h,
        )

    def _update_header_exit_rect(self) -> None:
        """Computes the interactive bounding boxes of the top-right exit, help, and language buttons."""
        w = float(self.width()) if self.width() > 0 else 1920.0
        margin = self.margin
        header_h = self.breadcrumb_height
        pill_h = max(24.0, header_h - 10.0)
        exit_btn_w = 160.0
        help_btn_w = 140.0
        lang_btn_w = 124.0
        mode_btn_w = 150.0
        effective_right_margin = self._get_effective_right_margin(w)
        header_w = max(1.0, w - 2.0 * margin - effective_right_margin)
        header_rect = QRectF(margin, margin, header_w, header_h)
        self.header_exit_rect = QRectF(header_rect.right() - exit_btn_w - 6.0, header_rect.y() + 5.0, exit_btn_w, pill_h)
        self.header_help_rect = QRectF(self.header_exit_rect.left() - help_btn_w - 8.0, header_rect.y() + 5.0, help_btn_w, pill_h)
        self.header_lang_rect = QRectF(self.header_help_rect.left() - lang_btn_w - 8.0, header_rect.y() + 5.0, lang_btn_w, pill_h)
        self.header_mode_rect = QRectF(self.header_lang_rect.left() - mode_btn_w - 8.0, header_rect.y() + 5.0, mode_btn_w, pill_h)
        self._update_help_modal_rect()

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
        """Returns the currently active MenuNode, adapting dynamically when at ROOT with 250ms render caching."""
        if self.current_node_id == "ROOT" and getattr(self, "adaptive_ast_enabled", True) and getattr(self, "current_context_mode_id", "coding") == "coding":
            now = time.time()
            if self._cached_adaptive_node is not None and (now - self._last_ast_eval_time < 0.25):
                return self._cached_adaptive_node

            std_root = self.menu_tree.get("ROOT")
            if self.context_reader:
                ctx_info = self.context_reader.detect_syntactic_context(language=self.current_language)
            else:
                ctx_info = detect_syntactic_context(language=self.current_language)
            ctx_name = ctx_info.get("context", "GENERAL")
            if ctx_name != self._last_detected_context_name:
                self._last_detected_context_name = ctx_name
                self.ast_context_detected.emit(ctx_name)
            node = get_adaptive_context_node(ctx_info, std_root, language=self.current_language)
            self._cached_adaptive_node = node
            self._last_ast_eval_time = now
            return node
        return self.menu_tree.get(self.current_node_id, self.menu_tree.get("ROOT"))

    @pyqtSlot(str)
    def on_file_linked(self, file_path: str) -> None:
        """Called when a user explicitly links a Python script."""
        self._cached_adaptive_node = None
        self._last_ast_eval_time = 0.0
        if self.context_reader:
            self.context_reader.set_active_file(file_path)
            self.last_action_desc = f"Vinculado: {os.path.basename(file_path)}"
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
        Sets overlay to loading state 'Analizando...' and updates 6 blocks dynamically.
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
            "Analizando...",
            "Analizando...",
            "Analizando...",
            "Analizando...",
            "Analizando...",
            "Analizando...",
        ]
        if "SNIPPETS" in self.menu_tree:
            self.menu_tree["SNIPPETS"].items = populate_ai_prediction_items(loading_preds, parent_id="ROOT")
        self.is_ai_predicting = True
        self.last_action_desc = "IA Analizando..."
        self.ai_status_updated.emit("Consultando IA...")
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
        self.last_action_desc = "6 Sugerencias IA Listas"
        self.ai_status_updated.emit("Listo (6 sugerencias)")
        self.update()

    @pyqtSlot(str)
    def _on_ai_status_changed(self, status: str) -> None:
        """Emits AI status update."""
        self.ai_status_updated.emit(status)

    @pyqtSlot(str)
    def _on_ai_prediction_failed(self, error_msg: str) -> None:
        """Handles prediction failure notification."""
        self.ai_status_updated.emit(f"Error: {error_msg}")

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
            self._cached_adaptive_node = None
            self._last_ast_eval_time = 0.0
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
        margin = self.margin
        header_h = self.breadcrumb_height
        avail_y = margin + header_h + margin
        avail_h = max(1.0, h - avail_y - margin)
        cell_h = avail_h / 3.0

        py = gy * h
        px = gx * w

        # If cheat sheet modal is open, hit test its close button
        if self.show_help_modal:
            if self.help_modal_close_rect.isValid() and self.help_modal_close_rect.adjusted(-15.0, -15.0, 15.0, 15.0).contains(px, py):
                self.hovered_help_modal_close = True
            else:
                self.hovered_help_modal_close = False
            self.hovered_header_exit = False
            self.hovered_header_help = False
            self.hovered_block = None
            self.update()
            return

        self.hovered_help_modal_close = False

        # Check if gaze is targeting the prominent header exit button (+15px buffer)
        if not self.reading_mode and self.header_exit_rect.isValid():
            expanded_exit_rect = self.header_exit_rect.adjusted(-15.0, -15.0, 15.0, 15.0)
            if expanded_exit_rect.contains(px, py):
                self.hovered_header_exit = True
                self.hovered_header_help = False
                self.hovered_block = None
                self.update()
                return

        self.hovered_header_exit = False

        # Check if gaze is targeting the header help button (+15px buffer)
        if not self.reading_mode and hasattr(self, "header_help_rect") and self.header_help_rect.isValid():
            expanded_help_rect = self.header_help_rect.adjusted(-15.0, -15.0, 15.0, 15.0)
            if expanded_help_rect.contains(px, py):
                self.hovered_header_help = True
                self.hovered_header_exit = False
                self.hovered_block = None
                self.update()
                return

        self.hovered_header_help = False

        # Check if gaze is targeting the header mode button (+15px buffer)
        if not self.reading_mode and hasattr(self, "header_mode_rect") and self.header_mode_rect.isValid():
            expanded_mode_rect = self.header_mode_rect.adjusted(-15.0, -15.0, 15.0, 15.0)
            if expanded_mode_rect.contains(px, py):
                self.hovered_header_mode = True
                self.hovered_header_exit = False
                self.hovered_header_help = False
                self.hovered_header_lang = False
                self.hovered_block = None
                self.update()
                return

        self.hovered_header_mode = False

        # Check if gaze is targeting the header language button (+15px buffer)
        if not self.reading_mode and hasattr(self, "header_lang_rect") and self.header_lang_rect.isValid():
            expanded_lang_rect = self.header_lang_rect.adjusted(-15.0, -15.0, 15.0, 15.0)
            if expanded_lang_rect.contains(px, py):
                self.hovered_header_lang = True
                self.hovered_header_exit = False
                self.hovered_header_help = False
                self.hovered_block = None
                self.update()
                return

        self.hovered_header_lang = False

        if py < avail_y:
            row = 0
        elif py >= avail_y + avail_h:
            row = 2
        else:
            row = min(2, max(0, int((py - avail_y) / cell_h)))

        effective_right_margin = self._get_effective_right_margin(w)
        avail_w = max(1.0, w - 2.0 * margin - effective_right_margin)
        cell_w = avail_w / 3.0
        if px < margin:
            col = 0
        elif px >= margin + avail_w:
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

    def _clear_header_exit_flash(self) -> None:
        self.active_click_header_exit = False
        self.update()

    def _clear_header_help_flash(self) -> None:
        """Clears active click visual pulse on header help button."""
        self.active_click_header_help = False
        self.update()

    def _clear_header_mode_flash(self) -> None:
        self.active_click_header_mode = False
        self.update()

    def _clear_header_lang_flash(self) -> None:
        """Clears active click visual pulse on header language button."""
        self.active_click_header_lang = False
        self.update()

    def toggle_help_modal(self) -> None:
        """Toggles the in-app gesture and shortcut cheat sheet modal."""
        self.show_help_modal = not getattr(self, "show_help_modal", False)
        self._update_help_modal_rect()
        self.last_action_desc = "Guía de Gestos" if self.show_help_modal else "Cerrar Ayuda"
        self.update()

    @pyqtSlot(str)
    def on_gesture_triggered(self, gesture_name: str) -> None:
        """
        Handles facial gesture triggers:
        - 'MOUTH_CLICK': Gaze macro selection, menu navigation, snippet insertion.
        - 'WINK_RIGHT': Toggles Option B pause mode (hides/restores HUD completely).
        - 'WINK_LEFT': Submenu 'Volver atrás' (parent menu node), or Undo 'Ctrl+Z' at ROOT.
        """
        if gesture_name == "WINK_RIGHT":
            if self.show_help_modal:
                self.show_help_modal = False
                self.update()
            self.toggle_reading_mode()
            self.last_action_desc = "Modo Edición (HUD Restaurado)" if not self.reading_mode else "Modo Reposo (HUD Oculto)"
            self.block_activated.emit(4, "PAUSE_RESUME")
            return

        if gesture_name == "WINK_LEFT":
            if self.show_help_modal:
                self.show_help_modal = False
                self.last_action_desc = "Cerrar Ayuda"
                self.update()
                return
            if self.reading_mode:
                return
            if self.current_node_id != "ROOT":
                target_id = (self.current_node.parent_id if self.current_node and self.current_node.parent_id else "ROOT") or "ROOT"
                self.navigate_to(target_id)
                target_title = self.menu_tree[target_id].title if target_id in self.menu_tree else "RAÍZ"
                self.last_action_desc = f"Volver a {target_title}"
                self.block_activated.emit(6, "ACTION_BACK")
                self.update()
                return
            else:
                if self.code_injector.is_busy:
                    return
                undo_action = MenuAction(
                    id="ACTION_UNDO",
                    label="Deshacer",
                    hint="Ctrl+Z",
                    action_type="KEY",
                    key_name="UNDO",
                    sticky=True,
                    icon="↶",
                )
                self.code_injector.execute_action(undo_action)
                self.last_action_desc = "Deshacer (Ctrl+Z)"
                self.action_executed.emit("ACTION_UNDO", "Deshacer (Ctrl+Z)")
                self.block_activated.emit(0, "ACTION_UNDO")
                self.update()
                return

        if gesture_name != "MOUTH_CLICK":
            return

        # Dismiss cheat sheet modal if open
        if self.show_help_modal:
            self.show_help_modal = False
            self.last_action_desc = "Cerrar Ayuda"
            self.update()
            return

        # Hands-free header exit click handler
        if self.hovered_header_exit:
            self.hovered_header_exit = False
            self.active_click_header_exit = True
            QTimer.singleShot(int(config.CLICK_FLASH_DURATION_SEC * 1000), self._clear_header_exit_flash)
            prev_node = self.current_node_id if self.current_node_id != "EXIT_CONFIRM" else "ROOT"
            if "EXIT_CONFIRM" in self.menu_tree:
                self.menu_tree["EXIT_CONFIRM"].parent_id = prev_node
                self.menu_tree["EXIT_CONFIRM"].items = populate_exit_confirm_items(parent_id=prev_node)
            self.navigate_to("EXIT_CONFIRM")
            self.last_action_desc = "Confirmar Salida"
            self.update()
            return

        # Hands-free header help click handler
        if getattr(self, "hovered_header_help", False):
            self.hovered_header_help = False
            self.active_click_header_help = True
            QTimer.singleShot(int(config.CLICK_FLASH_DURATION_SEC * 1000), self._clear_header_help_flash)
            self.toggle_help_modal()
            self.last_action_desc = "Guía de Gestos"
            self.update()
            return

        # Hands-free header mode click handler
        if getattr(self, "hovered_header_mode", False):
            self.hovered_header_mode = False
            self.active_click_header_mode = True
            QTimer.singleShot(int(config.CLICK_FLASH_DURATION_SEC * 1000), self._clear_header_mode_flash)
            if self.mode_manager is not None:
                self.mode_manager.cycle_next_mode()
            self.last_action_desc = f"Modo: {getattr(self, 'current_context_mode_name', '')}"
            self.update()
            return

        # Hands-free header language click handler
        if getattr(self, "hovered_header_lang", False):
            self.hovered_header_lang = False
            self.active_click_header_lang = True
            QTimer.singleShot(int(config.CLICK_FLASH_DURATION_SEC * 1000), self._clear_header_lang_flash)
            self.navigate_to("LANG_SELECT")
            self.last_action_desc = "Seleccionar Lenguaje"
            self.update()
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
            self.last_action_desc = "Modo Reposo Activo"
            self.block_activated.emit(target_block, "PAUSE_RESUME")
            return

        # 2. Back Navigation (Index 6 in submenus or BACK action)
        if item.action_type == "BACK":
            target_id = item.submenu_id or curr_node.parent_id or "ROOT"
            self.navigate_to(target_id)
            target_title = self.menu_tree[target_id].title if target_id in self.menu_tree else "RAÍZ"
            self.last_action_desc = f"Volver a {target_title}"
            self.block_activated.emit(target_block, item.id)
            return

        # 3. Submenu Forward Navigation
        if item.action_type == "SUBMENU":
            target_id = item.submenu_id
            if target_id and target_id in self.menu_tree:
                self.navigate_to(target_id)
                self.last_action_desc = f"Menú: {self.menu_tree[target_id].title}"
            self.block_activated.emit(target_block, item.id)
            return

        # 4. AI Regenerate / Refresh Action
        if item.action_type == "AI_REFRESH" or item.id == "AI_REGENERATE":
            self._trigger_ai_prediction()
            self.block_activated.emit(target_block, item.id)
            return

        # 5. Language Selection Triggers
        if item.action_type == "LANG_CHANGE":
            target_lang = item.snippet or "PYTHON"
            self.set_language(target_lang)
            if self.current_node_id == "LANG_SELECT":
                self.navigate_to("ROOT")
            self.block_activated.emit(target_block, item.id)
            return

        if item.action_type == "LANG_AUTO":
            detected_lang = self.context_reader.detect_active_language() if self.context_reader else "PYTHON"
            self.set_language(detected_lang)
            if self.current_node_id == "LANG_SELECT":
                self.navigate_to("ROOT")
            self.block_activated.emit(target_block, item.id)
            return

        # 6. Code / Key Injection (SNIPPET or KEY)
        if item.action_type in ("SNIPPET", "KEY"):
            # Ignore placeholder while predicting
            if item.action_type == "SNIPPET" and (not item.snippet or "Analizando..." in item.snippet):
                return

            # Execute injection via non-blocking worker thread
            self.code_injector.execute_action(item)
            self.last_action_desc = f"{item.icon} {item.label}" if item.icon else item.label
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

        # 7. Exit Trigger
        if item.action_type == "EXIT" or item.id in ("CONFIRM_EXIT", "ACTION_EXIT"):
            self.exit_requested.emit()
            self.block_activated.emit(target_block, item.id)
            return

        # Fallback default emission
        self.block_activated.emit(target_block, item.id)

    def execute_action(self, item: MenuAction, target_block: int = 0) -> None:
        """Programmatically executes a MenuAction directly on the overlay."""
        if item.action_type == "PAUSE":
            self.toggle_reading_mode()
            self.last_action_desc = "Modo Reposo Activo"
            self.block_activated.emit(target_block, "PAUSE_RESUME")
            return

        if item.action_type == "BACK":
            target_id = item.submenu_id or (self.current_node.parent_id if self.current_node else "ROOT") or "ROOT"
            self.navigate_to(target_id)
            target_title = self.menu_tree[target_id].title if target_id in self.menu_tree else "RAÍZ"
            self.last_action_desc = f"Volver a {target_title}"
            self.block_activated.emit(target_block, item.id)
            return

        if item.action_type == "SUBMENU":
            target_id = item.submenu_id
            if target_id and target_id in self.menu_tree:
                self.navigate_to(target_id)
                self.last_action_desc = f"Menú: {self.menu_tree[target_id].title}"
            self.block_activated.emit(target_block, item.id)
            return

        if item.action_type == "LANG_CHANGE":
            target_lang = item.snippet or "PYTHON"
            self.set_language(target_lang)
            if self.current_node_id == "LANG_SELECT":
                self.navigate_to("ROOT")
            self.block_activated.emit(target_block, item.id)
            return

        if item.action_type == "LANG_AUTO":
            detected_lang = self.context_reader.detect_active_language() if self.context_reader else "PYTHON"
            self.set_language(detected_lang)
            if self.current_node_id == "LANG_SELECT":
                self.navigate_to("ROOT")
            self.block_activated.emit(target_block, item.id)
            return

        if item.action_type in ("SNIPPET", "KEY"):
            self.code_injector.execute_action(item)
            self.last_action_desc = f"{item.icon} {item.label}" if item.icon else item.label
            self.action_executed.emit(item.id, self.last_action_desc)
            self.block_activated.emit(target_block, item.id)
            return

        if item.action_type == "EXIT" or item.id in ("CONFIRM_EXIT", "ACTION_EXIT"):
            self.exit_requested.emit()
            self.block_activated.emit(target_block, item.id)
            return

    def mousePressEvent(self, event) -> None:
        """Handles physical mouse clicks for testing, headless runners, and assistive caregivers."""
        pos = event.position() if hasattr(event, "position") else event.pos()
        px, py = float(pos.x()), float(pos.y())

        # Check help modal close button if open
        if self.show_help_modal:
            self.show_help_modal = False
            self.update()
            event.accept()
            return

        # Check header exit button (+15px buffer)
        if not self.reading_mode and self.header_exit_rect.isValid() and self.header_exit_rect.adjusted(-15.0, -15.0, 15.0, 15.0).contains(px, py):
            self.hovered_header_exit = True
            self.on_gesture_triggered("MOUTH_CLICK")
            event.accept()
            return

        # Check header help button (+15px buffer)
        if not self.reading_mode and hasattr(self, "header_help_rect") and self.header_help_rect.isValid() and self.header_help_rect.adjusted(-15.0, -15.0, 15.0, 15.0).contains(px, py):
            self.hovered_header_help = True
            self.on_gesture_triggered("MOUTH_CLICK")
            event.accept()
            return

        # Check header mode button (+15px buffer)
        if not self.reading_mode and hasattr(self, "header_mode_rect") and self.header_mode_rect.isValid() and self.header_mode_rect.adjusted(-15.0, -15.0, 15.0, 15.0).contains(px, py):
            self.hovered_header_mode = True
            self.on_gesture_triggered("MOUTH_CLICK")
            event.accept()
            return

        # Check header language button (+15px buffer)
        if not self.reading_mode and hasattr(self, "header_lang_rect") and self.header_lang_rect.isValid() and self.header_lang_rect.adjusted(-15.0, -15.0, 15.0, 15.0).contains(px, py):
            self.hovered_header_lang = True
            self.on_gesture_triggered("MOUTH_CLICK")
            event.accept()
            return

        w = float(self.width()) if self.width() > 0 else 1920.0
        h = float(self.height()) if self.height() > 0 else 1080.0
        self.on_gaze_updated(px / w, py / h)
        self.on_gesture_triggered("MOUTH_CLICK")
        event.accept()

    def keyPressEvent(self, event) -> None:
        """Keyboard event handler for shortcut [T] (tracking mode), [A] (adaptive AST), [L] (language), and [H]/[F1] (help)."""
        if event.key() in (Qt.Key.Key_H, Qt.Key.Key_F1):
            self.toggle_help_modal()
            event.accept()
        elif event.key() == Qt.Key.Key_Escape and self.show_help_modal:
            self.show_help_modal = False
            self.update()
            event.accept()
        elif event.key() == Qt.Key.Key_T:
            self.tracking_mode_cycle_requested.emit()
            event.accept()
        elif event.key() == Qt.Key.Key_A:
            self.toggle_adaptive_ast()
            event.accept()
        elif event.key() == Qt.Key.Key_L:
            self.cycle_language()
            event.accept()
        elif event.key() == Qt.Key.Key_V:
            self.cycle_context_mode()
            event.accept()
        elif event.key() == Qt.Key.Key_K:
            self.toggle_auto_switch()
            event.accept()
        else:
            super().keyPressEvent(event)

    def cycle_language(self) -> None:
        """Cycles through supported languages in order: Python -> TypeScript -> Rust -> C++ -> Go."""
        langs = ["PYTHON", "TYPESCRIPT", "RUST", "CPP", "GO"]
        try:
            curr_idx = langs.index(self.current_language)
            next_idx = (curr_idx + 1) % len(langs)
        except ValueError:
            next_idx = 0
        self.set_language(langs[next_idx])

    @pyqtSlot(str)
    def set_language(self, lang: str) -> None:
        """Sets the active programming language, updates menus and breadcrumbs, and notifies listeners."""
        norm_lang = normalize_language(lang)
        if norm_lang == self.current_language and self.menu_tree is not None:
            return

        self.current_language = norm_lang
        if getattr(self, "current_context_mode_id", "coding") == "coding":
            self.menu_tree = build_menu_tree(self.current_language)
            if "MENU_STANDARD" not in self.menu_tree and "ROOT" in self.menu_tree:
                std_items = list(self.menu_tree["ROOT"].items)
                std_items[8] = create_adaptive_menu_action("9")
                self.menu_tree["MENU_STANDARD"] = MenuNode(
                    id="MENU_STANDARD",
                    title="MENÚ ESTÁNDAR",
                    breadcrumb_label="ESTÁNDAR",
                    items=std_items,
                    parent_id="ROOT",
                    sticky=False,
                )
        else:
            mm = getattr(self, "mode_manager", None)
            if mm is not None:
                try:
                    self.menu_tree = mm.get_menu_tree(self.current_language)
                except Exception:
                    self.menu_tree = build_menu_tree(self.current_language)
            else:
                self.menu_tree = build_menu_tree(self.current_language)
        if "HELP" not in self.menu_tree:
            self.menu_tree["HELP"] = MenuNode(
                id="HELP",
                title="GUÍA DE GESTOS Y ATAJOS",
                breadcrumb_label="AYUDA / GESTOS",
                items=populate_help_items(parent_id="ROOT"),
                parent_id="ROOT",
                sticky=False,
            )
        if "LANG_SELECT" not in self.menu_tree:
            self.menu_tree["LANG_SELECT"] = MenuNode(
                id="LANG_SELECT",
                title="SELECCIONAR LENGUAJE",
                breadcrumb_label="LENGUAJE",
                items=populate_lang_select_items(parent_id="ROOT"),
                parent_id="ROOT",
                sticky=False,
            )
        self._cached_adaptive_node = None
        self._last_ast_eval_time = 0.0
        badge = get_language_badge(self.current_language)
        self.last_action_desc = f"Lenguaje: {get_language_display_name(self.current_language)} [{badge}]"
        self.language_changed.emit(self.current_language)
        self.update()

    def _on_context_mode_changed(self, mode_id: str, display_name: str, theme_color: str) -> None:
        """Applies a context mode change to the HUD menu tree and theme."""
        self.current_context_mode_id = mode_id
        self.current_context_mode_name = display_name
        self.theme_color = theme_color

        if mode_id == "coding":
            self.menu_tree = build_menu_tree(self.current_language)
            if "MENU_STANDARD" not in self.menu_tree and "ROOT" in self.menu_tree:
                std_items = list(self.menu_tree["ROOT"].items)
                std_items[8] = create_adaptive_menu_action("9")
                self.menu_tree["MENU_STANDARD"] = MenuNode(
                    id="MENU_STANDARD",
                    title="MENÚ ESTÁNDAR",
                    breadcrumb_label="ESTÁNDAR",
                    items=std_items,
                    parent_id="ROOT",
                    sticky=False,
                )
        else:
            try:
                self.menu_tree = self.mode_manager.get_menu_tree(self.current_language)
            except Exception:
                self.menu_tree = {"ROOT": self.mode_manager.get_root_menu(self.current_language)}

        for extra in ("HELP", "LANG_SELECT"):
            if extra not in self.menu_tree:
                if extra == "HELP":
                    self.menu_tree[extra] = MenuNode(
                        id="HELP",
                        title="GUÍA DE GESTOS Y ATAJOS",
                        breadcrumb_label="AYUDA / GESTOS",
                        items=populate_help_items(parent_id="ROOT"),
                        parent_id="ROOT",
                        sticky=False,
                    )
                else:
                    self.menu_tree[extra] = MenuNode(
                        id="LANG_SELECT",
                        title="SELECCIONAR LENGUAJE",
                        breadcrumb_label="LENGUAJE",
                        items=populate_lang_select_items(parent_id="ROOT"),
                        parent_id="ROOT",
                        sticky=False,
                    )

        self.current_node_id = "ROOT"
        self._cached_adaptive_node = None
        self._last_ast_eval_time = 0.0
        self.last_action_desc = f"Modo: {display_name}"
        self._mode_banner_text = f"MODO ACTIVO: {display_name}"
        try:
            self._mode_banner_start = time.time()
            self._mode_banner_until = self._mode_banner_start + 2.2
        except Exception:
            self._mode_banner_until = 0.0
        self.context_mode_changed.emit(mode_id, display_name, theme_color)
        self.update()

    def cycle_context_mode(self) -> None:
        if self.mode_manager is not None:
            self.mode_manager.cycle_next_mode()

    def is_mode_shortcut_targeted(self) -> bool:
        """True when the gaze is on/near the header mode button (global V/K gate)."""
        gaze = getattr(self, "current_gaze", None)
        rect = getattr(self, "header_mode_rect", None)
        if not gaze or rect is None or not rect.isValid():
            return False
        try:
            gx, gy = gaze
            w = max(1.0, float(self.width()))
            h = max(1.0, float(self.height()))
            return rect.adjusted(-24.0, -18.0, 24.0, 18.0).contains(gx * w, gy * h)
        except Exception:
            return False

    def toggle_adaptive_ast(self) -> None:
        """Toggles between dynamic adaptive AST menus and standard root menu (shortcut [A])."""
        self.adaptive_ast_enabled = not getattr(self, "adaptive_ast_enabled", True)
        self._cached_adaptive_node = None
        self._last_ast_eval_time = 0.0
        self.last_action_desc = f"AST Adaptativo: {'ON' if self.adaptive_ast_enabled else 'OFF'}"
        self.adaptive_ast_toggled.emit(self.adaptive_ast_enabled)
        self.update()

    def toggle_auto_switch(self, enabled=None) -> bool:
        if self.mode_manager is not None:
            return self.mode_manager.toggle_auto_switch(enabled)
        return False

    @pyqtSlot(bool)
    def set_adaptive_ast_enabled(self, enabled: bool) -> None:
        """Explicitly sets adaptive AST menus enabled status."""
        if self.adaptive_ast_enabled != enabled:
            self.adaptive_ast_enabled = enabled
            self._cached_adaptive_node = None
            self._last_ast_eval_time = 0.0
            self.last_action_desc = f"AST Adaptativo: {'ON' if self.adaptive_ast_enabled else 'OFF'}"
            self.adaptive_ast_toggled.emit(self.adaptive_ast_enabled)
            self.update()

    def toggle_reading_mode(self) -> None:
        """Toggles between Active HUD mode and Hidden/Reading Mode (Option B: full hide)."""
        self.reading_mode = not self.reading_mode
        self.current_opacity = config.OVERLAY_OPACITY_READING if self.reading_mode else config.OVERLAY_OPACITY_ACTIVE
        if self.reading_mode:
            self.hovered_block = None
            self.hide()
        else:
            self.show()
            self.raise_()
        self.reading_mode_toggled.emit(self.reading_mode)
        self.update()

    def pause_hud(self) -> None:
        """Pauses and hides the HUD completely (Option B)."""
        if not self.reading_mode:
            self.toggle_reading_mode()

    def resume_hud(self) -> None:
        """Resumes and restores the HUD completely (Option B)."""
        if self.reading_mode:
            self.toggle_reading_mode()

    def toggle_pause(self) -> None:
        """Toggles pause/hidden state of the HUD (Option B)."""
        self.toggle_reading_mode()

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
        if (
            item.action_type == "EXIT"
            or item.id in ("CONFIRM_EXIT", "ACTION_EXIT", "ACTION_EXIT_MENU")
            or (item.submenu_id or "").upper() == "EXIT_CONFIRM"
            or "EXIT" in self.current_node_id
        ):
            return "EXIT"

        sub_id = (item.submenu_id or "").upper()
        act_id = item.id.upper()
        curr_id = self.current_node_id.upper()

        if sub_id == "FLOW" or "FLOW" in curr_id or any(k in act_id for k in ("IF", "LOOP", "WHILE", "FOR", "TRY", "RETURN", "FLOW", "CTX_TRY", "CTX_LOOP", "CTX_IF", "CTX_WITH")):
            return "FLOW"
        if (
            item.action_type in ("LANG_CHANGE", "LANG_AUTO")
            or item.id.startswith("LANG_")
            or sub_id == "LANG_SELECT"
            or curr_id == "LANG_SELECT"
        ):
            return "LANG"
        if sub_id == "STRUCT" or "STRUCT" in curr_id or any(k in act_id for k in ("FUNC", "CLASS", "DEF", "STRUCT", "DATA", "LIST", "DICT", "T9", "CTX_FN", "CTX_CLS")):
            return "STRUCT"
        if sub_id == "OPERATORS" or "OP" in curr_id or any(k in act_id for k in ("OPERATOR", "OP_", "MATH", "BOOL", "COMPARE", "COMMA")):
            return "OPERATORS"
        if sub_id in ("NAV", "MENU_STANDARD") or "NAV" in curr_id or any(k in act_id for k in ("NAV_", "UP", "DOWN", "LEFT", "RIGHT", "PAGE", "WORD", "SWITCH_MENU_STANDARD", "SWITCH_ADAPTIVE_MENU")):
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
        effective_right_margin = self._get_effective_right_margin(w)
        header_w = max(1.0, w - 2.0 * margin - effective_right_margin)
        header_rect = QRectF(margin, margin, header_w, header_h)

        # Right-side header buttons are computed before the breadcrumb so the
        # left text and the "last action" pill can never run underneath them.
        pill_h = header_h - 14.0
        exit_btn_w = 160.0
        help_btn_w = 140.0
        lang_btn_w = 124.0
        mode_btn_w = 150.0
        self.header_exit_rect = QRectF(header_rect.right() - exit_btn_w - 6.0, header_rect.y() + 5.0, exit_btn_w, pill_h)
        self.header_help_rect = QRectF(self.header_exit_rect.left() - help_btn_w - 8.0, header_rect.y() + 5.0, help_btn_w, pill_h)
        self.header_lang_rect = QRectF(self.header_help_rect.left() - lang_btn_w - 8.0, header_rect.y() + 5.0, lang_btn_w, pill_h)
        self.header_mode_rect = QRectF(self.header_lang_rect.left() - mode_btn_w - 8.0, header_rect.y() + 5.0, mode_btn_w, pill_h)

        painter.setOpacity(0.95 if not self.reading_mode else 0.30)

        # Header background pill
        painter.setBrush(self._brush_header_bg)
        painter.setPen(self._pen_header_border)
        painter.drawRoundedRect(header_rect, 8.0, 8.0)

        # Left: App Logo + Mode Pill Badge + Navigation Trail
        logo_size = 28.0
        logo_rect = QRectF(header_rect.x() + 8.0, header_rect.y() + (header_h - logo_size) * 0.5, logo_size, logo_size)
        IconManager.instance().render_icon(painter, "eyede_logo", logo_rect)

        pill_w = 136.0
        pill_rect = QRectF(logo_rect.right() + 8.0, header_rect.y() + 7.0, pill_w, pill_h)

        if self.reading_mode:
            painter.setBrush(self._brush_pill_read)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(pill_rect, 5.0, 5.0)
            painter.setPen(self._color_pill_text)
            painter.setFont(self._font_header_pill)
            painter.drawText(pill_rect, Qt.AlignmentFlag.AlignCenter, "MODO LECTURA")
        else:
            painter.setBrush(self._brush_pill_edit)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(pill_rect, 5.0, 5.0)
            painter.setPen(self._color_pill_text)
            painter.setFont(self._font_header_pill)
            painter.drawText(pill_rect, Qt.AlignmentFlag.AlignCenter, "MODO EDICIÓN")

        # Breadcrumb trail text
        breadcrumb_path = get_breadcrumb_path(self.menu_tree, self.current_node_id).replace(" > ", " › ")
        if curr_node and curr_node.sticky:
            breadcrumb_path += "  [FIJO]"

        if self.current_node_id == "ROOT" and getattr(self, "adaptive_ast_enabled", True) and curr_node:
            left_text = curr_node.breadcrumb_label
        else:
            left_text = breadcrumb_path

        # Far-left: last executed action pill. It stays to the left of the
        # breadcrumb so it can never collide with the mode selector on the right.
        last_action_str = f"Última: {self.last_action_desc}"
        last_pill_max_w = float(min(int(header_rect.width() * 0.18), 220))
        last_pill_available = (
            self.header_mode_rect.left() - 8.0 - (pill_rect.right() + 8.0) - 12.0 - 100.0
        )
        last_pill_w = min(last_pill_max_w, max(0.0, last_pill_available))
        last_pill_rect = QRectF(pill_rect.right() + 8.0, header_rect.y() + 5.0, last_pill_w, pill_h)
        if last_pill_w < 70.0:
            last_pill_rect = QRectF()
        self._last_action_pill_rect = last_pill_rect

        text_start_x = (last_pill_rect.right() + 12.0) if last_pill_rect.isValid() else (pill_rect.right() + 12.0)

        emergency_left = header_rect.center().x() - 115.0
        emergency_right = header_rect.center().x() + 115.0
        emergency_fits = (
            emergency_left >= text_start_x + 80.0
            and emergency_right <= self.header_mode_rect.left() - 8.0
        )
        text_right_limit = (emergency_left - 12.0) if emergency_fits else (self.header_mode_rect.left() - 8.0)
        max_left_w = int(min(header_rect.width() * 0.32, max(0.0, text_right_limit - text_start_x)))

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

        # Far Right: Hands-free Gaze-Selectable & Mouth-Clickable Exit Target [SALIR]
        if self.active_click_header_exit:
            exit_brush = self._brush_click
            exit_pen = self._pen_click
            exit_text_color = self._color_click_text
        elif self.hovered_header_exit:
            # Outer neon glow aura for instant visual confirmation
            glow_exit_rect = self.header_exit_rect.adjusted(-4.0, -4.0, 4.0, 4.0)
            painter.setBrush(QBrush(QColor(239, 68, 68, 70)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(glow_exit_rect, 10.0, 10.0)

            exit_brush = QBrush(QColor(239, 68, 68, 245))
            exit_pen = QPen(QColor(254, 202, 202), 3.0)
            exit_text_color = QColor(255, 255, 255)
        else:
            exit_brush = QBrush(QColor(127, 29, 29, 150))
            exit_pen = QPen(QColor(239, 68, 68, 180), 1.8)
            exit_text_color = QColor(254, 202, 202)

        painter.setBrush(exit_brush)
        painter.setPen(exit_pen)
        painter.drawRoundedRect(self.header_exit_rect, 7.0, 7.0)

        # Exit vector SVG icon + bold label inside header button
        icon_size = 22.0
        exit_icon_rect = QRectF(self.header_exit_rect.x() + 14.0, self.header_exit_rect.y() + (pill_h - icon_size) * 0.5, icon_size, icon_size)
        IconManager.instance().render_icon(painter, "exit", exit_icon_rect)
        painter.setPen(exit_text_color)
        painter.setFont(self._font_header_bold_btn)
        painter.drawText(
            QRectF(self.header_exit_rect.x() + 42.0, self.header_exit_rect.y(), exit_btn_w - 48.0, pill_h),
            Qt.AlignmentFlag.AlignCenter,
            "SALIR",
        )

        # Help / Cheat Sheet Button [? AYUDA] next to [SALIR]
        if self.active_click_header_help:
            help_brush = self._brush_click
            help_pen = self._pen_click
            help_text_color = self._color_click_text
        elif self.hovered_header_help:
            # Outer neon glow aura for instant visual confirmation
            glow_help_rect = self.header_help_rect.adjusted(-4.0, -4.0, 4.0, 4.0)
            painter.setBrush(QBrush(QColor(14, 165, 233, 70)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(glow_help_rect, 10.0, 10.0)

            help_brush = QBrush(QColor(14, 165, 233, 245))
            help_pen = QPen(QColor(186, 230, 253), 3.0)
            help_text_color = QColor(255, 255, 255)
        else:
            help_brush = QBrush(QColor(12, 74, 110, 150))
            help_pen = QPen(QColor(14, 165, 233, 180), 1.8)
            help_text_color = QColor(186, 230, 253)

        painter.setBrush(help_brush)
        painter.setPen(help_pen)
        painter.drawRoundedRect(self.header_help_rect, 7.0, 7.0)

        help_icon_rect = QRectF(self.header_help_rect.x() + 12.0, self.header_help_rect.y() + (pill_h - icon_size) * 0.5, icon_size, icon_size)
        IconManager.instance().render_icon(painter, "help", help_icon_rect)
        painter.setPen(help_text_color)
        painter.setFont(self._font_header_bold_btn)
        painter.drawText(
            QRectF(self.header_help_rect.x() + 38.0, self.header_help_rect.y(), help_btn_w - 44.0, pill_h),
            Qt.AlignmentFlag.AlignCenter,
            "AYUDA",
        )

        # Hands-free Mode Selector Button [MODO] next to [LANG]
        mode_color = QColor(self.theme_color or "#00F0FF")

        if self.active_click_header_mode:
            mode_brush = self._brush_click
            mode_pen = self._pen_click
            mode_text_color = self._color_click_text
        elif self.hovered_header_mode:
            glow_mode_rect = self.header_mode_rect.adjusted(-4.0, -4.0, 4.0, 4.0)
            glow = QColor(mode_color)
            glow.setAlpha(70)
            painter.setBrush(QBrush(glow))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(glow_mode_rect, 10.0, 10.0)

            mode_brush = QBrush(mode_color)
            mode_pen = QPen(QColor(255, 255, 255, 230), 3.0)
            mode_text_color = QColor(255, 255, 255)
        else:
            base = QColor(mode_color)
            base.setAlpha(150)
            mode_brush = QBrush(base)
            mode_pen = QPen(mode_color, 1.8)
            mode_text_color = QColor(255, 255, 255)

        painter.setBrush(mode_brush)
        painter.setPen(mode_pen)
        painter.drawRoundedRect(self.header_mode_rect, 7.0, 7.0)

        icon_size = 18.0
        mode_icon_rect = QRectF(self.header_mode_rect.x() + 8.0, self.header_mode_rect.y() + (pill_h - icon_size) * 0.5, icon_size, icon_size)
        IconManager.instance().render_icon(painter, "mode", mode_icon_rect)

        painter.setPen(mode_text_color)
        painter.setFont(self._font_header_bold_btn)
        short_mode_labels = {
            "coding": "CÓDIGO",
            "writing": "REDACCIÓN",
            "terminal": "TERMINAL",
            "data_math": "DATOS",
            "navigation": "NAV",
        }
        mode_label = short_mode_labels.get(getattr(self, "current_context_mode_id", "coding"), "MODO")
        painter.drawText(
            QRectF(self.header_mode_rect.x() + 30.0, self.header_mode_rect.y(), self.header_mode_rect.width() - 34.0, pill_h),
            Qt.AlignmentFlag.AlignCenter,
            f"{mode_label} [V]",
        )

        # Hands-free Language Selector Button [LANG] next to [AYUDA]
        if self.active_click_header_lang:
            lang_brush = self._brush_click
            lang_pen = self._pen_click
            lang_text_color = self._color_click_text
        elif self.hovered_header_lang:
            glow_lang_rect = self.header_lang_rect.adjusted(-4.0, -4.0, 4.0, 4.0)
            painter.setBrush(QBrush(QColor(168, 85, 247, 70)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(glow_lang_rect, 10.0, 10.0)

            lang_brush = QBrush(QColor(168, 85, 247, 245))
            lang_pen = QPen(QColor(243, 232, 255), 3.0)
            lang_text_color = QColor(255, 255, 255)
        else:
            lang_brush = QBrush(QColor(88, 28, 135, 150))
            lang_pen = QPen(QColor(168, 85, 247, 180), 1.8)
            lang_text_color = QColor(243, 232, 255)

        painter.setBrush(lang_brush)
        painter.setPen(lang_pen)
        painter.drawRoundedRect(self.header_lang_rect, 7.0, 7.0)

        lang_icon_rect = QRectF(self.header_lang_rect.x() + 10.0, self.header_lang_rect.y() + (pill_h - icon_size) * 0.5, icon_size, icon_size)
        IconManager.instance().render_icon(painter, "language", lang_icon_rect)
        painter.setPen(lang_text_color)
        painter.setFont(self._font_header_bold_btn)
        badge_text = get_language_badge(self.current_language)
        painter.drawText(
            QRectF(self.header_lang_rect.x() + 34.0, self.header_lang_rect.y(), lang_btn_w - 40.0, pill_h),
            Qt.AlignmentFlag.AlignCenter,
            badge_text,
        )

        # Center: Emergency Hotkey Documentation Pill (only when it fits without overlap)
        emergency_text = "Emergencia: Ctrl+Alt+Q para salir"
        center_pill_rect = QRectF(emergency_left, header_rect.y() + 5.0, 230.0, pill_h)
        if emergency_fits:
            painter.setBrush(QBrush(QColor(239, 68, 68, 25)))
            painter.setPen(QPen(QColor(239, 68, 68, 120), 1.0))
            painter.drawRoundedRect(center_pill_rect, 5.0, 5.0)

            painter.setPen(self._pen_header_center)
            painter.setFont(self._font_header_center)
            painter.drawText(center_pill_rect, Qt.AlignmentFlag.AlignCenter, emergency_text)

        # Far-left: Last executed action pill
        if last_pill_rect.isValid():
            painter.setBrush(QBrush(QColor(56, 189, 248, 22)))
            painter.setPen(QPen(QColor(56, 189, 248, 90), 1.0))
            painter.drawRoundedRect(last_pill_rect, 5.0, 5.0)

            painter.setPen(self._pen_header_right)
            painter.setFont(self._font_header_right)
            elided_right = painter.fontMetrics().elidedText(
                last_action_str,
                Qt.TextElideMode.ElideRight,
                int(max(0.0, last_pill_rect.width() - 16.0)),
            )
            painter.drawText(
                last_pill_rect,
                Qt.AlignmentFlag.AlignCenter,
                elided_right,
            )

        # =====================================================================
        # 1b. Transient mode-change banner (makes coding/writing switch obvious)
        # =====================================================================
        try:
            now = time.time()
            if self._mode_banner_text and now < self._mode_banner_until:
                duration = max(0.1, self._mode_banner_until - self._mode_banner_start)
                progress = (now - self._mode_banner_start) / duration
                progress = max(0.0, min(1.0, progress))
                if progress < 0.18:
                    alpha_factor = progress / 0.18
                elif progress > 0.78:
                    alpha_factor = (1.0 - progress) / 0.22
                else:
                    alpha_factor = 1.0
                alpha_factor = max(0.0, min(1.0, alpha_factor))
                slide = (1.0 - min(1.0, progress / 0.18)) * 18.0 if progress < 0.18 else 0.0

                banner_w = min(float(self.width()) - 2.0 * margin, 420.0)
                banner_rect = QRectF(
                    (float(self.width()) - banner_w) * 0.5,
                    header_rect.bottom() + 10.0 + slide,
                    banner_w,
                    42.0,
                )
                painter.save()
                painter.setOpacity(alpha_factor)
                color = QColor(self.theme_color or "#00F0FF")
                color.setAlpha(220)
                painter.setBrush(QBrush(color))
                painter.setPen(QPen(QColor(255, 255, 255, 200), 2.0))
                painter.drawRoundedRect(banner_rect, 10.0, 10.0)
                painter.setPen(QColor(255, 255, 255))
                painter.setFont(self._font_header_bold_btn)
                painter.drawText(banner_rect, Qt.AlignmentFlag.AlignCenter, self._mode_banner_text)
                painter.restore()
        except Exception:
            pass

        # =====================================================================
        # 2. 3x3 Grid Category Cards
        # =====================================================================
        for i in range(9):
            if i >= len(items):
                continue
            item = items[i]
            rect = self.get_block_rect(i)

            is_active_click = (self.active_click_block == i)
            is_hover = (self.hovered_block == i)
            cat = self._get_category_for_item(item, i)

            # Opacity logic:
            # - bg_opacity: Translucent glass background so editor code underneath is clearly visible
            # - content_opacity: High-contrast typography & vector icons (WCAG AAA) for effortless legibility
            if self.reading_mode:
                if i == 4:
                    bg_opacity = 0.90 if (is_active_click or is_hover) else 0.35
                    content_opacity = 1.0 if (is_active_click or is_hover) else 0.85
                else:
                    bg_opacity = self.current_opacity
                    content_opacity = self.current_opacity * 0.4
            else:
                if is_active_click:
                    bg_opacity = 0.90
                    content_opacity = 1.0
                elif is_hover:
                    bg_opacity = min(1.0, max(0.65, self.current_opacity * 3.0))
                    content_opacity = 1.0
                else:
                    bg_opacity = self.current_opacity
                    content_opacity = 0.95

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

            # 1. Draw card background with translucent glassmorphic opacity
            painter.setOpacity(bg_opacity)
            painter.setBrush(block_brush)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(rect, 12.0, 12.0)

            # 2. Draw card frame border and content with crisp, readable opacity
            painter.setOpacity(content_opacity)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(border_pen)
            painter.drawRoundedRect(rect, 12.0, 12.0)

            # Draw subtle top accent hairline (acrylic category bar)
            if not self.reading_mode or i == 4:
                top_pen = self._cat_top_pens.get(cat, self._pen_default) if not (is_active_click or is_hover) else border_pen
                painter.setPen(top_pen)
                painter.drawLine(QPointF(rect.x() + 16.0, rect.y() + 2.0), QPointF(rect.right() - 16.0, rect.y() + 2.0))

            # Render category neon vector icon in card top-right
            icon_map = {
                "FLOW": "flow",
                "STRUCT": "function",
                "OPERATORS": "operators",
                "NAV": "navigation",
                "PAUSE": "pause_eye",
                "BACK": "navigation",
                "T9": "variables",
                "EDIT": "edit",
                "FORMAT": "format",
                "AI": "ai_spark",
                "EXIT": "exit",
            }
            icon_name = icon_map.get(cat)
            if icon_name and (not self.reading_mode or i == 4):
                card_icon_rect = QRectF(rect.right() - 36.0, rect.y() + 10.0, 24.0, 24.0)
                IconManager.instance().render_icon(painter, icon_name, card_icon_rect)

            # Determine labels
            label_text = f"{item.icon} {item.label}" if item.icon else item.label
            hint_text = item.hint

            if self.reading_mode and i == 4:
                label_text = "5: REANUDAR"
                hint_text = "Modo Lectura Activo (Mire y Abra Boca)"

            # Draw main label (reserving width on the right to prevent overlap with top-right vector badge)
            max_label_w = int(rect.width() - 54)
            painter.setPen(text_color)
            painter.setFont(self._font_label)
            painter.drawText(
                int(rect.x() + 14),
                int(rect.y() + 12),
                max_label_w,
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
                    max_label_w,
                    22,
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                    hint_text,
                )

            # Submenu or action pill indicator on bottom-right of block
            if not self.reading_mode and not is_active_click:
                badge_info = self._cat_badges.get(cat, ("", self._color_badge_default))
                badge_text, badge_color = badge_info

                if item.action_type == "SUBMENU":
                    badge_text = "SUBMENÚ"
                    badge_color = self._color_badge_submenu
                elif item.action_type == "BACK":
                    badge_text = "VOLVER"
                    badge_color = self._color_badge_back
                elif item.sticky:
                    badge_text = "FIJO"
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
        # 3. High-Contrast In-App Gesture & Shortcut Cheat Sheet Modal Card
        # =====================================================================
        if getattr(self, "show_help_modal", False):
            self._paint_help_modal(painter, w, h)

        # =====================================================================
        # 4. Refined High-Visibility Dual-Ring Reticle with Glow Aura
        # =====================================================================
        if not self.reading_mode or self.hovered_block == 4:
            painter.setOpacity(0.95 if not self.reading_mode else 0.85)
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

    def _paint_help_modal(self, painter: QPainter, w: float, h: float) -> None:
        """Paints a high-contrast acrylic glassmorphic cheat sheet modal card in the center."""
        # 1. Dim background
        painter.setOpacity(1.0)
        painter.fillRect(QRectF(0, 0, w, h), QColor(2, 6, 23, 225))

        # 2. Centered Modal Card Geometry
        self._update_help_modal_rect()
        card_rect = self.help_modal_rect
        card_w = card_rect.width()
        card_h = card_rect.height()
        card_x = card_rect.x()
        card_y = card_rect.y()

        # Card body with glowing border
        card_brush = QBrush(QColor(15, 23, 42, 250))
        card_pen = QPen(QColor(56, 189, 248, 220), 2.2)
        painter.setBrush(card_brush)
        painter.setPen(card_pen)
        painter.drawRoundedRect(card_rect, 14.0, 14.0)

        # 3. Header
        icon_size = 28.0
        icon_rect = QRectF(card_x + 24.0, card_y + 18.0, icon_size, icon_size)
        IconManager.instance().render_icon(painter, "help", icon_rect)

        painter.setFont(self._font_modal_title)
        painter.setPen(QColor(248, 250, 252))
        painter.drawText(
            QRectF(card_x + 60.0, card_y + 14.0, card_w - 80.0, 32.0),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            "GUÍA RÁPIDA DE GESTOS Y ATAJOS",
        )

        painter.setFont(self._font_modal_subtitle)
        painter.setPen(QColor(148, 163, 184))
        painter.drawText(
            QRectF(card_x + 60.0, card_y + 44.0, card_w - 80.0, 18.0),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            "Control asistivo integral manos libres mediante seguimiento ocular y gestos faciales",
        )

        # Divider line
        painter.setPen(QPen(QColor(51, 65, 85, 180), 1.0))
        painter.drawLine(int(card_x + 24.0), int(card_y + 68.0), int(card_x + card_w - 24.0), int(card_y + 68.0))

        # 4. Two-Column Layout for Gestures and Shortcuts
        col_gap = 18.0
        col_w = (card_w - 48.0 - col_gap) * 0.5
        col_y = card_y + 78.0
        content_h = card_h - 150.0

        # Column A: GESTOS FACIALES Y OCULARES
        col_a_rect = QRectF(card_x + 24.0, col_y, col_w, content_h)
        painter.setBrush(QBrush(QColor(30, 41, 59, 140)))
        painter.setPen(QPen(QColor(56, 189, 248, 90), 1.0))
        painter.drawRoundedRect(col_a_rect, 10.0, 10.0)

        painter.setFont(self._font_modal_section)
        painter.setPen(QColor(56, 189, 248))
        painter.drawText(
            QRectF(col_a_rect.x() + 14.0, col_a_rect.y() + 8.0, col_w - 28.0, 22.0),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            "👁 GESTOS FACIALES Y OCULARES",
        )

        gestures_list = [
            ("👄 Apertura de Boca (MAR)", "Clic / Inyectar código o navegar", "Abra la boca ligeramente para activar la casilla enfocada."),
            ("😉 Guiño Ojo Derecho", "Pausar / Despertar HUD", "Cierre el ojo derecho ~200ms para ocultar totalmente el HUD y descansar."),
            ("😉 Guiño Ojo Izquierdo", "Volver atrás / Deshacer (Ctrl+Z)", "Cierre el ojo izquierdo ~200ms para retroceder menú o deshacer cambios."),
        ]

        item_y = col_a_rect.y() + 36.0
        for title, action, desc in gestures_list:
            painter.setFont(self._font_modal_item_title)
            painter.setPen(QColor(253, 224, 71))  # amber-300
            painter.drawText(QRectF(col_a_rect.x() + 14.0, item_y, col_w - 28.0, 18.0), Qt.AlignmentFlag.AlignLeft, title)

            painter.setFont(self._font_modal_item_desc)
            painter.setPen(QColor(52, 211, 153))  # emerald-400
            painter.drawText(QRectF(col_a_rect.x() + 14.0, item_y + 18.0, col_w - 28.0, 16.0), Qt.AlignmentFlag.AlignLeft, f"→ {action}")

            painter.setPen(QColor(148, 163, 184))  # slate-400
            painter.drawText(QRectF(col_a_rect.x() + 14.0, item_y + 36.0, col_w - 28.0, 30.0), Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap, desc)

            item_y += 72.0

        # Column B: ATAJOS DE TECLADO RÁPIDOS
        col_b_rect = QRectF(col_a_rect.right() + col_gap, col_y, col_w, content_h)
        painter.setBrush(QBrush(QColor(30, 41, 59, 140)))
        painter.setPen(QPen(QColor(251, 191, 36, 90), 1.0))
        painter.drawRoundedRect(col_b_rect, 10.0, 10.0)

        painter.setFont(self._font_modal_section)
        painter.setPen(QColor(251, 191, 36))
        painter.drawText(
            QRectF(col_b_rect.x() + 14.0, col_b_rect.y() + 8.0, col_w - 28.0, 22.0),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            "⌨ ATAJOS DE TECLADO RÁPIDOS",
        )

        shortcuts_list = [
            ("[A]", "AST Adaptativo", "Alterna menús inteligentes según el cursor."),
            ("[V]", "Cambiar Modo", "Cicla Código, Redacción, Terminal, Datos y Navegación."),
            ("[T]", "Modo Tracking", "Cicla entre Cabeza (Recomendado), Híbrido e Iris."),
            ("[M]", "Colapsar Monitor", "Alterna monitor entre ventana y barra compacta."),
            ("[C]", "Calibrar Centro", "Fija la posición actual como centro neutro de pantalla."),
            ("[P]", "Pausa / Lectura", "Pone el HUD en reposo para descansar la vista."),
            ("[Ctrl+Alt+Q]", "Salida Emergencia", "Cierre inmediato del programa en cualquier momento."),
        ]

        item_y = col_b_rect.y() + 34.0
        for key, name, desc in shortcuts_list:
            painter.setFont(self._font_modal_item_title)
            painter.setPen(QColor(248, 113, 113) if "Ctrl" in key else QColor(125, 211, 252))
            painter.drawText(QRectF(col_b_rect.x() + 14.0, item_y, 88.0, 16.0), Qt.AlignmentFlag.AlignLeft, key)

            painter.setPen(QColor(241, 245, 249))
            painter.drawText(QRectF(col_b_rect.x() + 104.0, item_y, col_w - 118.0, 16.0), Qt.AlignmentFlag.AlignLeft, name)

            painter.setFont(self._font_modal_item_desc)
            painter.setPen(QColor(148, 163, 184))
            painter.drawText(QRectF(col_b_rect.x() + 14.0, item_y + 16.0, col_w - 28.0, 14.0), Qt.AlignmentFlag.AlignLeft, desc)

            item_y += 34.0

        # 5. Gaze-Selectable Close Button at Bottom
        close_btn_w = 380.0
        close_btn_h = 42.0
        self.help_modal_close_rect = QRectF(
            card_x + (card_w - close_btn_w) * 0.5,
            card_y + card_h - close_btn_h - 14.0,
            close_btn_w,
            close_btn_h,
        )

        if getattr(self, "hovered_help_modal_close", False):
            # Outer neon emerald glow aura
            glow_close_rect = self.help_modal_close_rect.adjusted(-4.0, -4.0, 4.0, 4.0)
            painter.setBrush(QBrush(QColor(16, 185, 129, 70)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(glow_close_rect, 10.0, 10.0)

            close_brush = QBrush(QColor(16, 185, 129, 245))
            close_pen = QPen(QColor(209, 250, 229), 2.8)
            close_text_color = QColor(255, 255, 255)
        else:
            close_brush = QBrush(QColor(6, 78, 59, 160))
            close_pen = QPen(QColor(16, 185, 129, 180), 1.5)
            close_text_color = QColor(167, 243, 208)

        painter.setBrush(close_brush)
        painter.setPen(close_pen)
        painter.drawRoundedRect(self.help_modal_close_rect, 8.0, 8.0)

        painter.setFont(self._font_header_bold_btn)
        painter.setPen(close_text_color)
        painter.drawText(
            self.help_modal_close_rect,
            Qt.AlignmentFlag.AlignCenter,
            "CERRAR GUÍA (Mire aquí o abra la boca / [ESC])",
        )

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
