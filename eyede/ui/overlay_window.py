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

from PyQt6.QtCore import (
    Qt,
    QTimer,
    QVariantAnimation,
    QEasingCurve,
    pyqtSignal,
    pyqtSlot,
    QRectF,
    QPointF,
)
from PyQt6.QtGui import QPainter, QColor, QFont, QFontMetrics, QPen, QBrush, QPainterPath, QLinearGradient
from PyQt6.QtWidgets import QWidget, QApplication

try:
    import eyede.config as config
    from eyede.ui.icon_manager import IconManager
    from eyede.core.sound_feedback import SoundFeedbackManager
    from eyede.core.mouse_controller import OSMouseController
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
        create_pause_action,
        create_back_action,
        get_adaptive_context_node,
        create_adaptive_menu_action,
    )
    from eyede.actions.context_reader import ContextReader, detect_syntactic_context
    from eyede.actions.ai_predictor import AIPredictorWorker
    from eyede.modes.mode_manager import ModeManager
except ImportError:
    import config
    from ui.icon_manager import IconManager
    from core.sound_feedback import SoundFeedbackManager
    from core.mouse_controller import OSMouseController
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
        create_pause_action,
        create_back_action,
        get_adaptive_context_node,
        create_adaptive_menu_action,
    )
    from actions.context_reader import ContextReader, detect_syntactic_context
    from actions.ai_predictor import AIPredictorWorker
    from modes.mode_manager import ModeManager


def _clean_action_label(label: str) -> str:
    """Removes the numeric slot prefix from a menu label for status messages.

    Example: ``"8: Espacios y saltos"`` -> ``"Espacios y saltos"``.
    """
    head, sep, tail = (label or "").partition(": ")
    if sep and head.strip().isdigit():
        return tail
    return label or ""


def _menu_card_label(item) -> str:
    """Returns the human-facing card label, never the internal icon id.

    Icon identifiers such as ``format`` or ``ai_spark`` are implementation
    details and must not leak into the HUD text.
    """
    return getattr(item, "label", "") or ""


MODE_SHORT_LABELS = {
    "coding": "CÓDIGO",
    "writing": "REDACCIÓN",
    "terminal": "TERMINAL",
    "data_math": "DATOS",
    "navigation": "NAV",
    "sniper": "FREELOOK",
}

# (mode_id, display label, hint, icon) in the order shown in the mode hub.
MODE_SELECTOR_ENTRIES = (
    ("coding", "Código", "Programar con menús inteligentes", "function"),
    ("writing", "Redacción", "Textos, Markdown y documentación", "format"),
    ("terminal", "Terminal", "Git, consola y pruebas", "terminal"),
    ("data_math", "Datos", "SQL, JSON, YAML y fórmulas", "database"),
    ("navigation", "Navegación", "Moverse por el editor y VS Code", "navigation"),
    ("sniper", "FreeLook", "Ratón directo y perfil Gaming", "crosshair"),
)

# Data displayed in the in-app help modal. Extracted as constants so the
# rendered content can be verified without instantiating a QPainter.
HELP_GESTURES = (
    (
        "Apertura de Boca (MAR)",
        "Clic / Inyectar código o navegar",
        "Abra la boca ligeramente para activar la casilla enfocada.",
    ),
    (
        "Guiño Ojo Derecho",
        "Pausar / Despertar HUD",
        "Cierre el ojo derecho ~200ms para ocultar totalmente el HUD y descansar.",
    ),
    (
        "Guiño Ojo Izquierdo",
        "Volver atrás / Deshacer (Ctrl+Z)",
        "Cierre el ojo izquierdo ~200ms para retroceder menú o deshacer cambios.",
    ),
)

HELP_SHORTCUTS = (
    ("[A]", "Menús inteligentes", "Adapta las opciones al código bajo el cursor."),
    ("[V] / [K]", "Elegir modo / Auto-switch", "V abre el selector de modos; K alterna el cambio automático."),
    ("[T]", "Modo Tracking", "Cicla entre Cabeza (Recomendado), Híbrido e Iris."),
    ("[M]", "Colapsar Monitor", "Alterna monitor entre ventana y barra compacta."),
    ("[C]", "Calibrar Centro", "Fija la posición actual como centro neutro de pantalla."),
    ("[P]", "Pausa / Lectura", "Pone el HUD en reposo para descansar la vista."),
    ("[S]", "Sonido", "Silencia o activa el feedback acústico."),
    ("[F]", "FreeLook", "Activa el ratón directo por mirada."),
    ("[G]", "Gaming", "Alterna el perfil Gaming dentro de FreeLook."),
    ("[Ctrl+Alt+Q]", "Salida Emergencia", "Cierre inmediato del programa en cualquier momento."),
)


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
    sound_enabled_changed = pyqtSignal(bool)
    auto_switch_changed = pyqtSignal(bool)
    mode_changed = context_mode_changed

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        code_injector: Optional[CodeInjector] = None,
        menu_tree: Optional[Dict[str, MenuNode]] = None,
        context_reader: Optional[ContextReader] = None,
        mode_manager: Optional[Any] = None,
        start_in_mode_selector: bool = False,
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
        self.current_context_mode_name: str = getattr(self.mode_manager, "current_mode", None).display_name if getattr(self.mode_manager, "current_mode", None) is not None else "Código"
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
        self._mode_selection_in_progress: bool = False
        self._ws_connected: bool = False

        # Phase 7: sound feedback and sniper targeting state
        self.sound_feedback: Optional[SoundFeedbackManager] = None
        self.mouse_controller: Optional[OSMouseController] = None
        self._sniper_step: int = 1
        self._sniper_locked_sector: Optional[int] = None
        self._sniper_previous_mode: Optional[str] = None
        self.hovered_subcell: Optional[int] = None
        self.hovered_sniper_action: bool = False
        self._sniper_action_pill_rect: QRectF = QRectF()

        # FreeLook / gaming state
        self._freelook_last_pos: Tuple[int, int] = (0, 0)
        self._jaw_locked: bool = False
        self._jaw_lock_pos: Optional[Tuple[int, int]] = None
        self._mouth_active: bool = False
        self._mouth_start: float = 0.0
        self._hold_started: bool = False
        self._gaming_mode: bool = False
        self._gaming_right_held: bool = False
        self._font_freelook_hint = QFont("Segoe UI", 10, QFont.Weight.Bold)
        self._gravity_block: Optional[int] = None
        self._gravity_since: float = 0.0

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

        self._install_auxiliary_nodes()
        if start_in_mode_selector:
            self.current_node_id = "MODE_SELECT"
            self.last_action_desc = "Elige un modo"
            self._mode_banner_text = "ELIGE UN MODO"
            try:
                self._mode_banner_start = time.time()
                self._mode_banner_until = self._mode_banner_start + 3.0
            except Exception:
                self._mode_banner_until = 0.0

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
        self.margin: float = 12.0
        self.gap: float = 10.0
        self.grid_right_margin: float = float(getattr(config, "OVERLAY_GRID_RIGHT_MARGIN", 364.0))
        self.debug_widget: Optional[QWidget] = None
        self._animated_right_margin: Optional[float] = None
        self._right_margin_animation: Optional[QVariantAnimation] = None
        self.header_rect: QRectF = QRectF()
        self._header_logo_rect: QRectF = QRectF()
        self._header_breadcrumb_rect: QRectF = QRectF()
        self._header_status_rect: QRectF = QRectF()
        self._last_action_pill_rect: QRectF = QRectF()
        self._header_exit_w: float = 112.0
        self._header_help_w: float = 96.0
        self._header_lang_w: float = 62.0
        self._header_mode_w: float = 220.0
        self.current_mar: float = 0.0
        self.mar_threshold: float = float(getattr(config, "MAR_THRESHOLD", 0.55))
        self.resize(1920, 1080)

        # Window title for identification
        self.setWindowTitle("IDEye - Gaze Macro Grid HUD (Phase 5)")

        # 4. Pre-allocated rendering objects to prevent 30/60 FPS GC pressure and memory leaks
        self._font_header_pill = QFont("Segoe UI", 9, QFont.Weight.Bold)
        self._font_header_bold_btn = QFont("Segoe UI", 10, QFont.Weight.Bold)
        self._font_header_left = QFont("Segoe UI", 9, QFont.Weight.Medium)
        self._font_header_center = QFont("Segoe UI", 9, QFont.Weight.Bold)
        self._font_header_right = QFont("Segoe UI", 8)
        self._font_label = QFont("Segoe UI", 14, QFont.Weight.Bold)
        self._font_hint = QFont("Segoe UI", 9)
        self._font_badge = QFont("Segoe UI", 7, QFont.Weight.Bold)
        self._font_card_number = QFont("Segoe UI", 11, QFont.Weight.Bold)
        self._font_card_subtitle = QFont("Segoe UI", 9)
        self._font_status = QFont("Segoe UI", 7, QFont.Weight.Bold)
        self._font_modal_title = QFont("Segoe UI", 15, QFont.Weight.Bold)
        self._font_modal_subtitle = QFont("Segoe UI", 9)
        self._font_modal_section = QFont("Segoe UI", 11, QFont.Weight.Bold)
        self._font_modal_item_title = QFont("Segoe UI", 10, QFont.Weight.Bold)
        self._font_modal_item_desc = QFont("Segoe UI", 8)

        # Header / command bar styles
        self._brush_header_bg = QBrush(QColor(11, 15, 25, 235))
        self._pen_header_border = QPen(QColor(255, 255, 255, 40), 1.0)
        self._pen_header_left = QPen(QColor(148, 163, 184))
        self._pen_header_center = QPen(QColor(248, 113, 113))
        self._pen_header_right = QPen(QColor(56, 189, 248))

        # Focus hierarchy: neutral inactive cards, theme-colored active card.
        self._brush_card_inactive = QBrush(QColor(15, 23, 42, 18))
        self._pen_card_inactive = QPen(QColor(255, 255, 255, 28), 1.0)
        self._brush_card_active = QBrush(QColor(15, 23, 42, 115))
        self._pen_card_active = QPen(QColor("#00F0FF"), 2.5)
        self._pen_card_danger = QPen(QColor(239, 68, 68), 2.5)
        self._brush_band_inactive = QBrush(QColor(11, 15, 25, 230))
        self._brush_band_active = QBrush(QColor(11, 15, 25, 225))
        self._color_card_text_inactive = QColor(226, 232, 240, 255)
        self._color_card_text_active = QColor(248, 250, 252, 255)
        self._color_card_subtitle = QColor(148, 163, 184, 220)
        self._color_card_subtitle_inactive = QColor(148, 163, 184, 255)
        self._pen_badge_active = QPen(QColor(255, 255, 255, 90), 1.0)
        self._brush_badge_active = QBrush(QColor(255, 255, 255, 28))
        self._brush_badge_inactive = QBrush(QColor(255, 255, 255, 12))
        self._brush_status_pill = QBrush(QColor(56, 189, 248, 18))
        self._pen_status_pill = QPen(QColor(56, 189, 248, 70), 1.0)
        self._brush_btn_idle = QBrush(QColor(255, 255, 255, 8))
        self._pen_btn_idle = QPen(QColor(255, 255, 255, 35), 1.0)
        self._brush_help_idle = QBrush(QColor(14, 165, 233, 22))
        self._pen_help_idle = QPen(QColor(14, 165, 233, 90), 1.0)
        self._brush_exit_idle = QBrush(QColor(239, 68, 68, 28))
        self._pen_exit_idle = QPen(QColor(239, 68, 68, 105), 1.0)
        self._brush_exit_glow = QBrush(QColor(239, 68, 68, 55))
        self._brush_help_glow = QBrush(QColor(14, 165, 233, 50))
        self._color_exit_text = QColor(254, 202, 202)
        self._color_help_text = QColor(186, 230, 253)
        self._brush_mode_idle = QBrush(QColor(0, 240, 255, 24))
        self._pen_mode_idle = QPen(QColor("#00F0FF"), 1.0)
        self._brush_mode_glow = QBrush(QColor(0, 240, 255, 55))
        self._color_mode_text = QColor(224, 251, 255)

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
            "MODE": QBrush(QColor(10, 30, 40, 220)),
            "SNIPER": QBrush(QColor(40, 10, 22, 220)),
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
            "MODE": QPen(QColor(34, 211, 238, 200), 1.8),
            "SNIPER": QPen(QColor(244, 63, 94, 210), 1.8),
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
            "MODE": QPen(QColor(34, 211, 238, 220), 2.5),
            "SNIPER": QPen(QColor(244, 63, 94, 230), 2.5),
            "DEFAULT": QPen(QColor(100, 116, 139, 180), 2.0),
        }
        self._cat_badges = {
            "FLOW": ("LÓGICA", QColor(34, 211, 238)),
            "STRUCT": ("FUNCIONES", QColor(251, 191, 36)),
            "OPERATORS": ("SÍMBOLOS", QColor(192, 132, 252)),
            "NAV": ("NAVEGACIÓN", QColor(96, 165, 250)),
            "PAUSE": ("REPOSO", QColor(52, 211, 153)),
            "BACK": ("VOLVER", QColor(244, 114, 182)),
            "EDIT": ("EDICIÓN", QColor(129, 140, 248)),
            "AI": ("SUGERENCIAS", QColor(240, 171, 252)),
            "EXIT": ("SALIR", QColor(248, 113, 113)),
            "LANG": ("LENGUAJE", QColor(168, 85, 247)),
            "MODE": ("MODO", QColor(34, 211, 238)),
            "SNIPER": ("SECTOR", QColor(244, 63, 94)),
            "DEFAULT": ("ACCIÓN", QColor(148, 163, 184)),
        }

        # Dynamic reticle: clean center point + thin outer ring + MAR progress arc.
        self._brush_pointer_glow = QBrush(QColor(56, 189, 248, 38))
        self._pen_pointer_ring = QPen(QColor(248, 250, 252, 210), 1.8)
        self._brush_pointer_dot = QBrush(QColor(248, 250, 252, 245))
        self._pen_pointer_progress = QPen(QColor(34, 211, 238), 2.2)
        self._color_progress_cool = QColor(34, 211, 238)
        self._color_progress_warm = QColor(251, 146, 60)
        self._set_theme_color(self.theme_color)
        self._update_header_exit_rect()

    def resizeEvent(self, event) -> None:
        """Handles window resize events to keep interactive target geometry updated."""
        super().resizeEvent(event)
        if self.debug_widget is not None:
            self.refresh_grid_right_margin(animate=False)
        self._update_header_exit_rect()

    def showEvent(self, event) -> None:
        """Ensures Win32 non-activating and topmost styles are reapplied when shown/restored."""
        super().showEvent(event)
        if self.debug_widget is not None:
            self.refresh_grid_right_margin(animate=False)
        self._update_header_exit_rect()
        if sys.platform == "win32":
            self._apply_win32_no_activate()

    def _set_theme_color(self, theme_color: str) -> None:
        """Updates the cached active-card and mode-button colors for a mode."""
        color = QColor(theme_color or "#00F0FF")
        self._pen_card_active = QPen(color, 2.5)
        self._pen_mode_idle = QPen(color, 1.0)
        glow = QColor(color)
        glow.setAlpha(55)
        self._brush_mode_glow = QBrush(glow)
        idle = QColor(color)
        idle.setAlpha(24)
        self._brush_mode_idle = QBrush(idle)
        badge = QColor(color)
        badge.setAlpha(58)
        self._brush_badge_theme = QBrush(badge)
        self._pen_badge_theme = QPen(QColor(color.red(), color.green(), color.blue(), 150), 1.0)
        self._color_theme_text = QColor(color)

    def _get_grid_left(self, w: float, effective_right_margin: float) -> float:
        """Returns the grid's left origin.

        With a docked monitor the grid is centered symmetrically so normalized
        gaze (0.5, 0.5) still lands on the center card. Without a monitor the
        historical left-anchored layout is preserved for multi-resolution
        center-gaze compatibility.
        """
        if self.debug_widget is not None:
            return self.margin + effective_right_margin
        return self.margin

    def _get_effective_right_margin(self, w: float) -> float:
        """Returns the right margin, including the docked DebugWidget when visible."""
        if self.debug_widget is not None:
            if self._animated_right_margin is not None:
                return max(0.0, float(self._animated_right_margin))
            return self._target_right_margin(w)
        # No monitor attached: preserve the historical scaled default used by tests.
        base_right_margin = float(getattr(self, "grid_right_margin", 364.0))
        if w >= 1920.0:
            return base_right_margin
        return base_right_margin * (w / 1920.0)

    def _target_right_margin(self, w: Optional[float] = None) -> float:
        """Computes the monitor-aware right margin (width + 16px safety gap)."""
        if self.debug_widget is None:
            return 0.0
        if not self.debug_widget.isVisible() or getattr(self.debug_widget, "is_collapsed", False):
            return 0.0
        width = float(w if w is not None else (self.width() or 1920.0))
        debug_left = float(self.debug_widget.x() - self.x())
        # The monitor's true left edge determines the gap; the width+16 rule is
        # kept as a floor so the grid never slides under the panel.
        return max(float(self.debug_widget.width()) + 16.0, width - debug_left + 16.0)

    def set_debug_widget(self, widget: Optional[QWidget]) -> None:
        """Links the docked DebugWidget so the grid can react to its layout."""
        self.debug_widget = widget
        if widget is not None:
            try:
                widget.collapsed_toggled.connect(self._on_debug_widget_layout_changed)
            except Exception:
                pass
            try:
                widget.visibility_changed.connect(self._on_debug_widget_visible_changed)
            except Exception:
                pass
        self.refresh_grid_right_margin(animate=False)

    @pyqtSlot(bool)
    def set_vscode_connected(self, connected: bool) -> None:
        """Updates the VS Code WebSocket connection badge in the header."""
        self._ws_connected = bool(connected)
        self.update()

    def _on_debug_widget_layout_changed(self, _collapsed: bool = False) -> None:
        self.refresh_grid_right_margin()

    def _on_debug_widget_visible_changed(self, _visible: bool = False) -> None:
        self.refresh_grid_right_margin()

    def refresh_grid_right_margin(self, animate: bool = True) -> None:
        """Animates the grid between docked and expanded layouts."""
        if self._right_margin_animation is not None:
            self._right_margin_animation.stop()
            self._right_margin_animation = None

        if self.debug_widget is None:
            self._animated_right_margin = None
            self._update_header_exit_rect()
            self.update()
            return

        target = self._target_right_margin()
        current = (
            self._animated_right_margin
            if self._animated_right_margin is not None
            else self._get_effective_right_margin(float(self.width() or 1920.0))
        )
        if not animate or abs(current - target) < 0.5:
            self._animated_right_margin = target
            self._update_header_exit_rect()
            self.update()
            return

        if self._right_margin_animation is not None:
            self._right_margin_animation.stop()
        animation = QVariantAnimation(self)
        animation.setStartValue(float(current))
        animation.setEndValue(float(target))
        animation.setDuration(180)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.valueChanged.connect(self._on_right_margin_animated)
        animation.finished.connect(lambda: setattr(self, "_animated_right_margin", float(target)))
        self._right_margin_animation = animation
        animation.start()

    def _on_right_margin_animated(self, value: Any) -> None:
        try:
            self._animated_right_margin = float(value)
        except (TypeError, ValueError):
            return
        self._update_header_exit_rect()
        self.update()

    def set_grid_right_margin(self, margin: float) -> None:
        """Sets the fallback reserved margin when no DebugWidget is attached."""
        self.grid_right_margin = max(0.0, float(margin))
        if self.debug_widget is None:
            self._update_header_exit_rect()
            self.update()

    def get_block_rect(self, index: int) -> QRectF:
        """Computes the QRectF for a 3x3 card with 12px padding and 10px gaps."""
        w = float(self.width()) if self.width() > 0 else 1920.0
        h = float(self.height()) if self.height() > 0 else 1080.0
        right_margin = self._get_effective_right_margin(w)
        left = self._get_grid_left(w, right_margin)
        right = w - self.margin - right_margin
        top = self.margin + self.breadcrumb_height + self.gap
        bottom = h - self.margin
        avail_w = max(1.0, right - left)
        avail_h = max(1.0, bottom - top)
        cell_w = max(1.0, (avail_w - 2.0 * self.gap) / 3.0)
        cell_h = max(1.0, (avail_h - 2.0 * self.gap) / 3.0)
        col = index % 3
        row = index // 3
        return QRectF(
            left + col * (cell_w + self.gap),
            top + row * (cell_h + self.gap),
            cell_w,
            cell_h,
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

    def _should_show_last_action(self) -> bool:
        """Returns True when the last-action pill should be rendered."""
        desc = (self.last_action_desc or "").strip()
        if not desc:
            return False
        lowered = desc.lower()
        if lowered in ("ninguna", "elegir modo", "elige un modo", "elige un modo"):
            return False
        if lowered.startswith("modo:"):
            return False
        return True

    def _update_header_exit_rect(self) -> None:
        """Computes the unified floating command bar and its interactive targets."""
        w = float(self.width()) if self.width() > 0 else 1920.0
        margin = self.margin
        header_h = self.breadcrumb_height
        pill_h = max(24.0, header_h - 12.0)
        right_margin = self._get_effective_right_margin(w)
        grid_left = self._get_grid_left(w, right_margin)
        grid_right = w - margin - right_margin
        area_w = max(1.0, grid_right - grid_left)
        bar_w = max(1.0, min(1020.0, area_w))
        bar_x = grid_left + (area_w - bar_w) * 0.5

        if bar_w >= 900.0:
            self._header_exit_w = max(150.0, min(160.0, bar_w * 0.12))
            self._header_help_w = max(130.0, min(140.0, bar_w * 0.10))
        else:
            self._header_exit_w = max(104.0, min(120.0, bar_w * 0.14))
            self._header_help_w = max(100.0, min(112.0, bar_w * 0.10))
        self._header_lang_w = max(56.0, min(64.0, bar_w * 0.07))
        self._header_mode_w = max(140.0, min(200.0, bar_w * 0.26))

        header_rect = QRectF(bar_x, margin, bar_w, header_h)
        self.header_rect = header_rect
        inner = 8.0
        gap = 6.0

        # Right-to-left: EXIT | HELP | [LAST ACTION] | LANG | MODE
        self.header_exit_rect = QRectF(
            header_rect.right() - inner - self._header_exit_w,
            header_rect.y() + 6.0,
            self._header_exit_w,
            pill_h,
        )
        self.header_help_rect = QRectF(
            self.header_exit_rect.left() - gap - self._header_help_w,
            header_rect.y() + 6.0,
            self._header_help_w,
            pill_h,
        )

        show_last = self._should_show_last_action()
        last_w = min(170.0, max(70.0, bar_w * 0.22))
        right_block = (
            self._header_mode_w + self._header_lang_w + self._header_help_w
            + self._header_exit_w + 3.0 * gap
        )
        if show_last:
            right_block += last_w + gap

        # Brand area needs logo + IDEye + optional WS status
        brand_fm = QFontMetrics(self._font_header_bold_btn)
        brand_w = float(brand_fm.horizontalAdvance("IDEye")) + 2.0
        ws_dot = 6.0
        ws_gap = 5.0
        ws_full_w = ws_dot + ws_gap + float(QFontMetrics(self._font_header_left).horizontalAdvance("VS Code"))
        ws_min_w = ws_dot
        brand_min = 24.0 + 8.0 + brand_w + 10.0 + ws_min_w

        # If it doesn't fit, shrink or hide the last-action pill
        if right_block + brand_min + 12.0 > bar_w:
            last_w = max(70.0, last_w - 40.0)
            right_block = (
                self._header_mode_w + self._header_lang_w + self._header_help_w
                + self._header_exit_w + 3.0 * gap + last_w + gap
            ) if show_last else right_block
        if show_last and right_block + brand_min + 12.0 > bar_w:
            show_last = False
            right_block = (
                self._header_mode_w + self._header_lang_w + self._header_help_w
                + self._header_exit_w + 3.0 * gap
            )
        if right_block + brand_min + 12.0 > bar_w:
            # Last resort: narrow the mode button to its hard minimum
            self._header_mode_w = max(120.0, min(self._header_mode_w, bar_w - right_block + self._header_mode_w - brand_min - 12.0))

        if show_last:
            self._last_action_pill_rect = QRectF(
                self.header_help_rect.left() - gap - last_w,
                header_rect.y() + 6.0,
                last_w,
                pill_h,
            )
        else:
            self._last_action_pill_rect = QRectF()

        # In sniper mode the same slot becomes a clickable mouse-action selector.
        if self.current_context_mode_id == "sniper":
            sniper_w = min(170.0, max(130.0, last_w))
            self._sniper_action_pill_rect = QRectF(
                self.header_help_rect.left() - gap - sniper_w,
                header_rect.y() + 6.0,
                sniper_w,
                pill_h,
            )
            self._last_action_pill_rect = QRectF()
        else:
            self._sniper_action_pill_rect = QRectF()

        selector_rect = (
            self._sniper_action_pill_rect
            if self._sniper_action_pill_rect.isValid()
            else self._last_action_pill_rect
        )
        lang_left = (
            selector_rect.left() - gap - self._header_lang_w
            if selector_rect.isValid()
            else self.header_help_rect.left() - gap - self._header_lang_w
        )
        self.header_lang_rect = QRectF(
            lang_left,
            header_rect.y() + 6.0,
            self._header_lang_w,
            pill_h,
        )
        self.header_mode_rect = QRectF(
            self.header_lang_rect.left() - gap - self._header_mode_w,
            header_rect.y() + 6.0,
            self._header_mode_w,
            pill_h,
        )

        logo_size = 24.0
        self._header_logo_rect = QRectF(
            header_rect.x() + inner,
            header_rect.y() + (header_h - logo_size) * 0.5,
            logo_size,
            logo_size,
        )

        status_left = self._header_logo_rect.right() + 8.0
        status_right = self.header_mode_rect.left() - gap
        status_w = max(0.0, status_right - status_left)
        self._header_status_rect = QRectF(status_left, header_rect.y() + 6.0, status_w, pill_h)
        self._header_ws_dot_only = status_w < ws_full_w + 4.0
        self._header_ws_show = status_w >= ws_min_w + 4.0

        # Breadcrumb is no longer painted; keep an empty rect for compatibility.
        self._header_breadcrumb_rect = QRectF()
        self._update_help_modal_rect()

    def _card_header_rects(
        self, rect: QRectF, badge_text: str, has_icon: bool
    ) -> tuple[QRectF, QRectF]:
        """Compute status badge and vector icon cell rectangles for a menu card header.

        Returns a 2-tuple (badge_rect, cell_rect). The badge stays at the top-right
        of the band. The icon cell (28x28) is rendered immediately to its left with
        an 8-10 px gap. If the remaining title width would drop below 72 px, the
        icon cell is hidden but the badge is kept.
        """
        y = rect.y()
        badge_rect = QRectF()
        cell_rect = QRectF()

        if badge_text:
            metrics = QFontMetrics(self._font_status)
            badge_w = max(62.0, metrics.horizontalAdvance(badge_text) + 14.0)
            badge_rect = QRectF(rect.right() - 10.0 - badge_w, y + 17.0, badge_w, 18.0)

        cell_size = 28.0
        if has_icon:
            if badge_rect.isValid():
                cell_x = badge_rect.left() - 10.0 - cell_size
            else:
                cell_x = rect.right() - 10.0 - cell_size
            icon_y = y + 12.0
            cell_rect = QRectF(cell_x, icon_y, cell_size, cell_size)

        # Hide the icon cell if the title area would become too narrow.
        title_left = rect.x() + 42.0
        first_right = min(
            badge_rect.left() if badge_rect.isValid() else rect.right() - 8.0,
            cell_rect.left() if cell_rect.isValid() else rect.right() - 8.0,
        )
        title_w = max(20.0, first_right - 8.0 - title_left)
        if title_w < 72.0 and cell_rect.isValid():
            cell_rect = QRectF()

        return badge_rect, cell_rect

    def _preview_chip_labels(self, item: MenuAction) -> list[str]:
        """Returns up to 4 preview labels for MODE_SWITCH and SUBMENU cards."""
        source_items: list = []
        if item.action_type == "MODE_SWITCH" and self.mode_manager is not None:
            try:
                mode = self.mode_manager.get_mode(item.mode_id)
                node = mode.get_root_menu(self.current_language)
                source_items = list(node.items)
            except Exception:
                source_items = []
        elif item.action_type == "SUBMENU" and item.submenu_id in self.menu_tree:
            source_items = list(self.menu_tree[item.submenu_id].items)
        else:
            return []

        labels: list[str] = []
        seen: set[str] = set()
        for child in source_items:
            if child.action_type in ("PAUSE", "BACK", "EXIT"):
                continue
            raw = _clean_action_label(getattr(child, "label", "") or "")
            if not raw:
                continue
            for part in raw.split(" / "):
                part = part.strip()
                if not part:
                    continue
                if len(part) > 14:
                    part = part[:14] + "…"
                key = part.lower()
                if key in seen:
                    continue
                seen.add(key)
                labels.append(part)
                if len(labels) >= 4:
                    return labels
        return labels

    def _paint_preview_chips(
        self,
        painter: QPainter,
        card_rect: QRectF,
        chip_labels: list[str],
    ) -> None:
        """Paints small preview chips under the card header band."""
        if not chip_labels:
            return
        fm = QFontMetrics(self._font_card_subtitle)
        chip_h = 18.0
        gap = 4.0
        radius = 5.0
        start_x = card_rect.x() + 12.0
        y = card_rect.y() + 58.0
        max_right = card_rect.right() - 12.0

        painter.setFont(self._font_card_subtitle)
        for label in chip_labels:
            text_w = fm.horizontalAdvance(label)
            chip_w = float(text_w) + 10.0
            if start_x + chip_w > max_right:
                break
            chip_rect = QRectF(start_x, y, chip_w, chip_h)
            painter.setBrush(QColor(255, 255, 255, 12))
            painter.setPen(QPen(QColor(255, 255, 255, 28), 1.0))
            painter.drawRoundedRect(chip_rect, radius, radius)
            painter.setPen(QColor(203, 213, 225))
            painter.drawText(chip_rect, Qt.AlignmentFlag.AlignCenter, label)
            start_x += chip_w + gap

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
        self.last_action_desc = "Buscando sugerencias..."
        self.ai_status_updated.emit("Buscando sugerencias...")
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
        self.last_action_desc = "6 sugerencias listas"
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

        # FreeLook: header remains interactive; the rest of the screen moves
        # the real OS cursor directly and hides the 3x3 grid.
        if (
            self.current_context_mode_id == "sniper"
            and self.current_node_id != "MODE_SELECT"
            and not self.show_help_modal
        ):
            px = gx * max(1.0, float(self.width()))
            py = gy * max(1.0, float(self.height()))
            header_targets = (
                ("hovered_header_exit", self.header_exit_rect),
                ("hovered_header_help", self.header_help_rect),
                ("hovered_header_mode", self.header_mode_rect),
                ("hovered_header_lang", self.header_lang_rect),
                ("hovered_sniper_action", self._sniper_action_pill_rect),
            )
            for attr, rect in header_targets:
                if rect.isValid() and rect.adjusted(-15.0, -15.0, 15.0, 15.0).contains(px, py):
                    for other, _ in header_targets:
                        setattr(self, other, other == attr)
                    self.hovered_block = None
                    self.update()
                    return
            for attr, _ in header_targets:
                setattr(self, attr, False)
            self._handle_freelook_gaze(gx, gy)
            return

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

        # Sniper action selector pill (between language and help).
        if (
            self.current_context_mode_id == "sniper"
            and self._sniper_action_pill_rect.isValid()
            and self._sniper_action_pill_rect.adjusted(-10.0, -10.0, 10.0, 10.0).contains(px, py)
        ):
            self.hovered_sniper_action = True
            self.hovered_block = None
            self.update()
            return
        self.hovered_sniper_action = False

        # Hit-test the actual card rectangles. This is exact even when the
        # monitor-aware layout shifts the grid and adds 10px gaps.
        point = QPointF(px, py)
        block_idx = None
        for candidate in range(9):
            if self.get_block_rect(candidate).adjusted(-6.0, -6.0, 6.0, 6.0).contains(point):
                block_idx = candidate
                break
        if block_idx is None:
            nearest = min(
                range(9),
                key=lambda idx: (
                    self.get_block_rect(idx).center().x() - px
                ) ** 2
                + (self.get_block_rect(idx).center().y() - py) ** 2,
            )
            block_idx = nearest

        if self.current_context_mode_id != "sniper":
            gx, gy = self._apply_cell_gravity(gx, gy, block_idx)
            self.current_gaze = (gx, gy)

        if self.reading_mode:
            # In reading mode, inhibit all blocks except Block 4 (Resume trigger)
            if block_idx == 4:
                self.hovered_block = 4
            else:
                self.hovered_block = None
        else:
            self.hovered_block = block_idx

        self.update()

    def _apply_cell_gravity(
        self, gx: float, gy: float, block_idx: Optional[int]
    ) -> Tuple[float, float]:
        """Soft 15% pull to a cell center after 150ms of stable dwell."""
        if (
            not getattr(config, "CELL_MAGNETISM_ENABLED", True)
            or self.reading_mode
            or self.current_context_mode_id == "sniper"
            or block_idx is None
        ):
            self._gravity_block = None
            self._gravity_since = 0.0
            return gx, gy

        now = time.time()
        if block_idx != self._gravity_block:
            self._gravity_block = block_idx
            self._gravity_since = now
            return gx, gy

        rect = self.get_block_rect(block_idx)
        if rect.width() <= 1.0 or rect.height() <= 1.0:
            return gx, gy
        px, py = gx * self.width(), gy * self.height()
        rel_x = (px - rect.left()) / rect.width()
        rel_y = (py - rect.top()) / rect.height()
        if not (0.18 <= rel_x <= 0.82 and 0.18 <= rel_y <= 0.82):
            self._gravity_since = now
            return gx, gy
        if now - self._gravity_since < float(getattr(config, "CELL_MAGNETISM_DWELL", 0.15)):
            return gx, gy

        strength = float(getattr(config, "CELL_MAGNETISM_STRENGTH", 0.15))
        center = rect.center()
        cx = center.x() / max(1.0, self.width())
        cy = center.y() / max(1.0, self.height())
        return gx + (cx - gx) * strength, gy + (cy - gy) * strength

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

    # ------------------------------------------------------------------ #
    # Phase 7: sound feedback
    # ------------------------------------------------------------------ #
    def set_sound_feedback(self, manager: Optional[SoundFeedbackManager]) -> None:
        """Injects the procedural sound manager (optional in tests)."""
        self.sound_feedback = manager

    def _play_sound(self, sound_name: str) -> None:
        """Plays a UI sound without ever blocking the Qt thread."""
        try:
            if self.sound_feedback is not None:
                self.sound_feedback.play(sound_name)
        except Exception:
            pass

    def toggle_sound_feedback(self) -> bool:
        """Mutes/unmutes procedural audio and reports the new state."""
        if self.sound_feedback is None:
            return True
        enabled = bool(self.sound_feedback.toggle_mute())
        self.last_action_desc = f"Sonido: {'ON' if enabled else 'OFF'}"
        self.sound_enabled_changed.emit(enabled)
        self.update()
        return enabled

    # ------------------------------------------------------------------ #
    # Phase 7: sniper targeting
    # ------------------------------------------------------------------ #
    def set_mouse_controller(self, controller: Optional[OSMouseController]) -> None:
        self.mouse_controller = controller

    def _get_screen_size(self) -> Tuple[int, int]:
        screen = QApplication.primaryScreen()
        if screen is None:
            return max(1, self.width()), max(1, self.height())
        rect = screen.geometry()
        # Qt reports logical pixels; pynput injects physical screen pixels.
        dpr = float(screen.devicePixelRatio() or 1.0)
        return max(1, int(rect.width() * dpr)), max(1, int(rect.height() * dpr))

    def _calculate_sector_rect(
        self,
        sector_index: int,
        screen_w: Optional[int] = None,
        screen_h: Optional[int] = None,
    ) -> Tuple[int, int, int, int]:
        """Returns the screen-pixel rectangle of a 3x3 macro sector."""
        if screen_w is None or screen_h is None:
            screen_w, screen_h = self._get_screen_size()
        col = sector_index % 3
        row = sector_index // 3
        sector_w = screen_w / 3.0
        sector_h = screen_h / 3.0
        return (
            int(col * sector_w),
            int(row * sector_h),
            int(sector_w),
            int(sector_h),
        )

    def _calculate_subcell_coords(
        self,
        subcell_index: int,
        sector_rect: Tuple[int, int, int, int],
    ) -> Tuple[int, int]:
        """Returns the absolute screen-pixel center of a precision sub-cell."""
        x, y, w, h = sector_rect
        col = subcell_index % 3
        row = subcell_index // 3
        cell_w = w / 3.0
        cell_h = h / 3.0
        return (
            int(x + (col + 0.5) * cell_w),
            int(y + (row + 0.5) * cell_h),
        )

    def _subcell_rects_in_overlay(self) -> List[QRectF]:
        """Maps the locked sector's 3x3 sub-grid into overlay coordinates."""
        if self._sniper_locked_sector is None:
            return []
        screen_w, screen_h = self._get_screen_size()
        sx, sy, sw, sh = self._calculate_sector_rect(
            self._sniper_locked_sector, screen_w, screen_h
        )
        scale_x = self.width() / float(screen_w)
        scale_y = self.height() / float(screen_h)
        left = sx * scale_x
        top = sy * scale_y
        width = sw * scale_x
        height = sh * scale_y
        cell_w = width / 3.0
        cell_h = height / 3.0
        rects: List[QRectF] = []
        for row in range(3):
            for col in range(3):
                rects.append(
                    QRectF(
                        left + col * cell_w,
                        top + row * cell_h,
                        cell_w,
                        cell_h,
                    )
                )
        return rects

    def _subcell_from_gaze(self, gx: float, gy: float) -> Optional[int]:
        if self._sniper_locked_sector is None:
            return None
        screen_w, screen_h = self._get_screen_size()
        sx, sy, sw, sh = self._calculate_sector_rect(
            self._sniper_locked_sector, screen_w, screen_h
        )
        px = gx * screen_w
        py = gy * screen_h
        if not (sx <= px < sx + sw and sy <= py < sy + sh):
            return None
        col = min(2, max(0, int((px - sx) / (sw / 3.0))))
        row = min(2, max(0, int((py - sy) / (sh / 3.0))))
        return row * 3 + col

    def _sniper_mode(self):
        try:
            return self.mode_manager.get_mode("sniper") if self.mode_manager else None
        except Exception:
            return None

    def _cycle_sniper_action(self) -> str:
        mode = self._sniper_mode()
        if mode is None or not hasattr(mode, "cycle_action"):
            return "LEFT_CLICK"
        action = mode.cycle_action()
        self.last_action_desc = f"Ratón: {getattr(mode, 'action_label', action)}"
        self._play_sound("mode")
        self.update()
        return action

    def _execute_sniper_action(self, x: int, y: int) -> None:
        mode = self._sniper_mode()
        action = getattr(mode, "get_action", lambda: "LEFT_CLICK")() if mode else "LEFT_CLICK"
        controller = self.mouse_controller
        if controller is None:
            controller = OSMouseController()
            self.mouse_controller = controller
        if action == "RIGHT_CLICK":
            controller.right_click(x, y)
        elif action == "DOUBLE_CLICK":
            controller.double_click(x, y)
        elif action == "SCROLL_UP":
            controller.scroll_at(x, y, 3)
        elif action == "SCROLL_DOWN":
            controller.scroll_at(x, y, -3)
        else:
            controller.left_click(x, y)

    def toggle_sniper_mode(self) -> None:
        """Enters sniper mode from any mode, or returns to the previous one."""
        if self.current_context_mode_id == "sniper":
            self._exit_sniper_mode()
            return
        if self.mode_manager is None:
            return
        self._sniper_previous_mode = self.current_context_mode_id
        self._mode_selection_in_progress = True
        try:
            self.mode_manager.set_mode("sniper", emit=True)
        finally:
            self._mode_selection_in_progress = False
        self._sniper_step = 1
        self._sniper_locked_sector = None
        self.hovered_subcell = None
        self._gaming_mode = False
        self._gaming_right_held = False
        self._jaw_locked = False
        self._jaw_lock_pos = None
        self._mouth_active = False
        self._hold_started = False
        sw, sh = self._get_screen_size()
        self._freelook_last_pos = (sw // 2, sh // 2)
        self.navigate_to("ROOT")
        self.last_action_desc = "FreeLook"
        self._play_sound("mode")
        self.update()

    def _exit_sniper_mode(self) -> None:
        previous = self._sniper_previous_mode or "coding"
        self._sniper_previous_mode = None
        if self.mode_manager is not None:
            self._mode_selection_in_progress = True
            try:
                self.mode_manager.set_mode(previous, emit=True)
            finally:
                self._mode_selection_in_progress = False
        controller = self.mouse_controller
        if controller is not None:
            if self._gaming_right_held:
                controller.mouse_up("right")
            if self._hold_started:
                controller.key_up("w") if self._gaming_mode else controller.mouse_up("left")
        self._sniper_step = 1
        self._sniper_locked_sector = None
        self.hovered_subcell = None
        self._gaming_mode = False
        self._gaming_right_held = False
        self._jaw_locked = False
        self._jaw_lock_pos = None
        self._mouth_active = False
        self._hold_started = False
        self.navigate_to("ROOT")
        self.last_action_desc = "Modo anterior"
        self._play_sound("back")
        self.update()

    def _paint_sniper_overlay(self, painter: QPainter) -> None:
        """Draws the step-2 precision sub-grid over the locked sector."""
        if self.current_context_mode_id != "sniper" or self._sniper_step != 2:
            return
        rects = self._subcell_rects_in_overlay()
        if not rects:
            return
        painter.save()
        mode = self._sniper_mode()
        action_label = getattr(mode, "action_label", "Clic Izq") if mode else "Clic Izq"
        for idx, rect in enumerate(rects):
            selected = idx == self.hovered_subcell
            painter.setBrush(QColor(244, 63, 94, 45) if selected else QColor(2, 6, 23, 38))
            painter.setPen(QPen(QColor(244, 63, 94, 235 if selected else 150), 2.0 if selected else 1.0))
            painter.drawRoundedRect(rect.adjusted(2, 2, -2, -2), 6.0, 6.0)
            painter.setPen(QColor(248, 250, 252) if selected else QColor(203, 213, 225))
            painter.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(idx + 1))
        # Compact instruction banner.
        banner = QRectF(
            self.width() * 0.5 - 230.0,
            self.margin,
            460.0,
            32.0,
        )
        painter.setBrush(QColor(11, 15, 25, 235))
        painter.setPen(QPen(QColor(244, 63, 94, 220), 1.2))
        painter.drawRoundedRect(banner, 9.0, 9.0)
        painter.setPen(QColor(248, 250, 252))
        painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        painter.drawText(
            banner,
            Qt.AlignmentFlag.AlignCenter,
            f"PASO 2 · {action_label} · elige sub-zona y abre la boca",
        )
        painter.restore()

    # ------------------------------------------------------------------ #
    # Phase 7.5: FreeLook / direct OS mouse
    # ------------------------------------------------------------------ #
    def _freelook_prethreshold(self) -> float:
        return max(0.01, float(getattr(self, "mar_threshold", 0.45)) * 0.55)

    def _freelook_screen_coords(
        self, gx: float, gy: float, screen_w: int, screen_h: int
    ) -> Tuple[int, int]:
        """Maps normalized gaze to the full physical screen with edge overscan.

        The grid still lives inside availableGeometry; only FreeLook uses the
        full geometry so the taskbar, tray and maximized-window close button
        remain reachable.
        """
        margin_x = max(0.0, min(0.20, float(getattr(config, "OVERSCAN_MARGIN_X", 0.04))))
        margin_top = max(0.0, min(0.20, float(getattr(config, "OVERSCAN_MARGIN_Y_TOP", 0.04))))
        margin_bottom = max(0.0, min(0.25, float(getattr(config, "OVERSCAN_MARGIN_Y_BOTTOM", 0.07))))
        span_x = max(1e-6, 1.0 - 2.0 * margin_x)
        span_y = max(1e-6, 1.0 - margin_top - margin_bottom)
        nx = max(0.0, min(1.0, (float(gx) - margin_x) / span_x))
        ny = max(0.0, min(1.0, (float(gy) - margin_top) / span_y))
        x = int(round(nx * max(0, screen_w - 1)))
        y = int(round(ny * max(0, screen_h - 1)))

        rail_height = max(1, int(getattr(config, "TASKBAR_RAIL_HEIGHT", 52)))
        if y >= screen_h - rail_height:
            target_y = max(0, screen_h - int(getattr(config, "TASKBAR_RAIL_TARGET_Y", 24)))
            pull = max(0.0, min(1.0, float(getattr(config, "TASKBAR_RAIL_PULL", 0.60))))
            y = int(round(y + (target_y - y) * pull))
        return (
            max(0, min(screen_w - 1, x)),
            max(0, min(screen_h - 1, y)),
        )

    def _handle_freelook_gaze(self, gx: float, gy: float) -> None:
        screen_w, screen_h = self._get_screen_size()
        x, y = self._freelook_screen_coords(gx, gy, screen_w, screen_h)
        pre = self._freelook_prethreshold()

        if self.current_mar >= pre:
            if not self._jaw_locked:
                self._jaw_locked = True
                self._jaw_lock_pos = self._freelook_last_pos
            if self._jaw_lock_pos is not None:
                x, y = self._jaw_lock_pos
        else:
            self._jaw_locked = False
            self._jaw_lock_pos = None
            self._freelook_last_pos = (x, y)
            controller = self.mouse_controller
            if controller is not None:
                try:
                    controller.move_direct(x, y)
                except Exception:
                    pass

        normalized = (x / float(screen_w), y / float(screen_h))
        if normalized != self.current_gaze:
            self.current_gaze = normalized
            self.update()

    def _freelook_click(self) -> None:
        mode = self._sniper_mode()
        action = getattr(mode, "get_action", lambda: "LEFT_CLICK")() if mode else "LEFT_CLICK"
        x, y = self._jaw_lock_pos or self._freelook_last_pos
        controller = self.mouse_controller
        if controller is None:
            controller = OSMouseController()
            self.mouse_controller = controller
        if action == "RIGHT_CLICK":
            controller.right_click(x, y)
        elif action == "DOUBLE_CLICK":
            controller.double_click(x, y)
        elif action == "SCROLL_UP":
            controller.scroll_at(x, y, 3)
        elif action == "SCROLL_DOWN":
            controller.scroll_at(x, y, -3)
        else:
            controller.left_click(x, y)
        self._play_sound("click")
        self.last_action_desc = f"FreeLook: {getattr(mode, 'action_label', 'Clic Izq')}"

    def _update_freelook_mouth(self, mar: float) -> None:
        pre = self._freelook_prethreshold()
        trigger = max(pre + 0.01, float(getattr(self, "mar_threshold", 0.45)))
        now = time.time()

        if mar >= trigger and not self._mouth_active:
            self._mouth_active = True
            self._mouth_start = now
            self._hold_started = False
            self._jaw_lock_pos = self._jaw_lock_pos or self._freelook_last_pos
            self.update()
            return

        if not self._mouth_active:
            return

        held = now - self._mouth_start
        hold_limit = 0.40 if self._gaming_mode else 0.45
        controller = self.mouse_controller
        if not self._hold_started and held >= hold_limit and controller is not None:
            self._hold_started = True
            if self._gaming_mode:
                controller.key_down("w")
            else:
                controller.mouse_down("left")

        if mar < pre:
            if self._hold_started and controller is not None:
                if self._gaming_mode:
                    controller.key_up("w")
                else:
                    controller.mouse_up("left")
            elif not self._hold_started:
                self._freelook_click()
            self._mouth_active = False
            self._hold_started = False
            self.update()

    def toggle_gaming_mode(self) -> bool:
        self._gaming_mode = not self._gaming_mode
        if not self._gaming_mode and self._gaming_right_held:
            if self.mouse_controller is not None:
                self.mouse_controller.mouse_up("right")
            self._gaming_right_held = False
        self.last_action_desc = f"FreeLook: {'GAMING' if self._gaming_mode else 'ESCRITORIO'}"
        self._play_sound("mode")
        self.update()
        return self._gaming_mode

    def _toggle_gaming_right(self) -> None:
        controller = self.mouse_controller
        if controller is None:
            return
        if self._gaming_right_held:
            controller.mouse_up("right")
        else:
            controller.mouse_down("right")
        self._gaming_right_held = not self._gaming_right_held
        self.last_action_desc = "Gaming: Clic Der mantenido" if self._gaming_right_held else "Gaming: Clic Der liberado"
        self._play_sound("mode")
        self.update()

    def _paint_freelook_overlay(self, painter: QPainter) -> None:
        """Draws only a compact status pill below the command bar."""
        mode = self._sniper_mode()
        action = getattr(mode, "action_label", "Clic Izq") if mode else "Clic Izq"
        profile = "GAMING" if self._gaming_mode else "ESCRITORIO"
        text = f"FREELOOK · {profile} · {action}"
        painter.save()
        fm = QFontMetrics(self._font_freelook_hint)
        width = min(440.0, max(240.0, fm.horizontalAdvance(text) + 28.0))
        rect = QRectF(
            self.width() * 0.5 - width * 0.5,
            self.header_rect.bottom() + 8.0,
            width,
            26.0,
        )
        painter.setBrush(QColor(11, 15, 25, 215))
        painter.setPen(QPen(QColor(244, 63, 94, 180), 1.0))
        painter.drawRoundedRect(rect, 8.0, 8.0)
        painter.setPen(QColor(254, 205, 211))
        painter.setFont(self._font_freelook_hint)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
        painter.restore()

    def toggle_help_modal(self) -> None:
        """Toggles the in-app gesture and shortcut cheat sheet modal."""
        self.show_help_modal = not getattr(self, "show_help_modal", False)
        self._update_help_modal_rect()
        self.last_action_desc = "Guía de Gestos" if self.show_help_modal else "Cerrar Ayuda"
        self.update()

    @pyqtSlot(object, float)
    def on_mar_updated(self, _frame: Any, current_mar: float) -> None:
        """Receives the current mouth-aspect ratio for reticle click feedback."""
        try:
            self.current_mar = float(current_mar)
        except (TypeError, ValueError):
            self.current_mar = 0.0
        if (
            self.current_context_mode_id == "sniper"
            and self.current_node_id != "MODE_SELECT"
            and not self.show_help_modal
        ):
            self._update_freelook_mouth(self.current_mar)
            return
        if self.hovered_block is not None:
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
            if self.current_context_mode_id == "sniper" and self._gaming_mode:
                self._toggle_gaming_right()
                return
            self._play_sound("pause")
            if self.show_help_modal:
                self.show_help_modal = False
                self.update()
            self.toggle_reading_mode()
            self.last_action_desc = "Modo Edición (HUD Restaurado)" if not self.reading_mode else "Modo Reposo (HUD Oculto)"
            self.block_activated.emit(4, "PAUSE_RESUME")
            return

        if gesture_name == "WINK_LEFT":
            if self.current_context_mode_id == "sniper":
                if self._gaming_mode and self.mouse_controller is not None:
                    self.mouse_controller.tap_key(" ")
                    self._play_sound("click")
                else:
                    self._exit_sniper_mode()
                return
            self._play_sound("back")
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

        self._play_sound("click")

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

        # Sniper action selector (only visible in sniper mode)
        if getattr(self, "hovered_sniper_action", False):
            self.hovered_sniper_action = False
            self._cycle_sniper_action()
            return

        # Hands-free header mode click handler
        if getattr(self, "hovered_header_mode", False):
            self.hovered_header_mode = False
            self.active_click_header_mode = True
            QTimer.singleShot(int(config.CLICK_FLASH_DURATION_SEC * 1000), self._clear_header_mode_flash)
            self.open_mode_selector()
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

        # FreeLook handles mouth clicks in on_mar_updated (click vs. hold).
        # The mode hub still uses normal card selection.
        if self.current_context_mode_id == "sniper" and self.current_node_id != "MODE_SELECT":
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

        # Do not accumulate facial clicks while an injection is actively running.
        # Writing mode is the exception: T9 letters should queue naturally so
        # the user can spell a word without waiting for each clipboard paste.
        if self.code_injector.is_busy and target_block != 4 and self.current_context_mode_id != "writing":
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

        # Sniper step 1: lock the macro sector and show its precision sub-grid.
        if item.action_type == "SNIPER_SECTOR":
            try:
                self._sniper_locked_sector = int(item.snippet)
            except (TypeError, ValueError):
                self._sniper_locked_sector = None
            if self._sniper_locked_sector is not None:
                self._sniper_step = 2
                self.hovered_subcell = self._subcell_from_gaze(*self.current_gaze)
                self.last_action_desc = f"Sector {self._sniper_locked_sector + 1}"
                self._play_sound("mode")
                self.update()
            self.block_activated.emit(target_block, item.id)
            return

        # 3. Context Mode Selection from the mode hub
        if item.action_type == "MODE_SWITCH":
            self._activate_mode(item.mode_id)
            self.block_activated.emit(target_block, item.id)
            return

        # 3b. Writing-mode T9 letters, words, spaces and case toggle
        if self._handle_writing_action(item, target_block):
            return

        # 4. Submenu Forward Navigation
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
            self.last_action_desc = _clean_action_label(item.label)
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

    def _writing_mode(self):
        """Returns the WritingMode instance when available."""
        if self.mode_manager is None:
            return None
        try:
            return self.mode_manager.get_mode("writing")
        except Exception:
            return None

    def _refresh_writing_predictions(self) -> None:
        """Refreshes the prediction panel after a T9 letter or word change."""
        mode = self._writing_mode()
        node = self.menu_tree.get("WRITING_PREDICT")
        if mode is None or node is None or not hasattr(mode, "build_prediction_items"):
            return
        try:
            node.items = mode.build_prediction_items()
        except Exception:
            pass

    def _handle_writing_action(self, item: MenuAction, target_block: int = 0) -> bool:
        """Executes T9/writing actions and returns True when handled."""
        action_type = getattr(item, "action_type", "")
        if action_type not in {
            "WRITING_LETTER",
            "WRITING_WORD",
            "WRITING_SPACE",
            "WRITING_BACKSPACE",
            "WRITING_CASE",
        }:
            return False

        mode = self._writing_mode()
        if mode is None:
            return False

        if action_type == "WRITING_LETTER":
            text = mode.record_letter(item.snippet or "")
            if text:
                self.code_injector.insert_snippet(text)
            self._refresh_writing_predictions()
            self.last_action_desc = f"Letra: {text}" if text else "Letra"
            self.action_executed.emit(item.id, self.last_action_desc)
            self.block_activated.emit(target_block, item.id)
            self.update()
            return True

        if action_type == "WRITING_WORD":
            word = mode.apply_case_to_word(item.snippet or "")
            if word:
                self.code_injector.insert_snippet(word + " ")
            mode.reset_prefix()
            self._refresh_writing_predictions()
            self.navigate_to("WRITING_T9")
            self.last_action_desc = f"Palabra: {word}" if word else "Palabra"
            self.action_executed.emit(item.id, self.last_action_desc)
            self.block_activated.emit(target_block, item.id)
            return True

        if action_type == "WRITING_SPACE":
            self.code_injector.insert_snippet(" ")
            mode.record_space()
            self._refresh_writing_predictions()
            self.last_action_desc = "Espacio"
            self.action_executed.emit(item.id, self.last_action_desc)
            self.block_activated.emit(target_block, item.id)
            self.update()
            return True

        if action_type == "WRITING_BACKSPACE":
            self.code_injector.send_key("BACKSPACE")
            mode.record_backspace()
            self._refresh_writing_predictions()
            self.last_action_desc = "Borrar carácter"
            self.action_executed.emit(item.id, self.last_action_desc)
            self.block_activated.emit(target_block, item.id)
            self.update()
            return True

        if action_type == "WRITING_CASE":
            enabled = mode.toggle_uppercase()
            self.last_action_desc = f"Mayúsculas: {'ON' if enabled else 'OFF'}"
            self.action_executed.emit(item.id, self.last_action_desc)
            self.block_activated.emit(target_block, item.id)
            self.update()
            return True

        return False

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

        if item.action_type == "MODE_SWITCH":
            self._activate_mode(item.mode_id)
            self.block_activated.emit(target_block, item.id)
            return

        if self._handle_writing_action(item, target_block):
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
            self.last_action_desc = _clean_action_label(item.label)
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
        elif event.key() == Qt.Key.Key_S:
            self.toggle_sound_feedback()
            event.accept()
        elif event.key() == Qt.Key.Key_F:
            self.toggle_sniper_mode()
            event.accept()
        elif event.key() == Qt.Key.Key_G:
            if self.current_context_mode_id == "sniper":
                self.toggle_gaming_mode()
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
        self._install_auxiliary_nodes()
        self._cached_adaptive_node = None
        self._last_ast_eval_time = 0.0
        badge = get_language_badge(self.current_language)
        self.last_action_desc = f"Lenguaje: {get_language_display_name(self.current_language)} [{badge}]"
        self.language_changed.emit(self.current_language)
        self.update()

    def _on_context_mode_changed(self, mode_id: str, display_name: str, theme_color: str) -> None:
        """Applies a context mode change to the HUD menu tree and theme."""
        was_sniper = self.current_context_mode_id == "sniper"
        self.current_context_mode_id = mode_id
        self.current_context_mode_name = display_name
        self.theme_color = theme_color
        self._set_theme_color(theme_color)
        if mode_id != "sniper":
            if was_sniper and self.mouse_controller is not None:
                if self._gaming_right_held:
                    self.mouse_controller.mouse_up("right")
                if self._hold_started:
                    if self._gaming_mode:
                        self.mouse_controller.key_up("w")
                    else:
                        self.mouse_controller.mouse_up("left")
            self._sniper_step = 1
            self._sniper_locked_sector = None
            self.hovered_subcell = None
            self._gaming_mode = False
            self._gaming_right_held = False
            self._jaw_locked = False
            self._jaw_lock_pos = None
            self._mouth_active = False
            self._hold_started = False

        if mode_id == "writing":
            mode = self._writing_mode()
            if mode is not None and hasattr(mode, "reset_prefix"):
                mode.reset_prefix()

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

        self._install_auxiliary_nodes()

        # Keep the mode hub open when an automatic editor-state change arrives.
        # When the user explicitly picked a mode, _activate_mode() sets the flag
        # and we enter that mode's ROOT instead.
        if self.current_node_id == "MODE_SELECT" and not self._mode_selection_in_progress:
            self.current_node_id = "MODE_SELECT"
        else:
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

    def _short_mode_label(self, mode_id: Optional[str] = None) -> str:
        """Returns the compact human label for a context mode."""
        mid = mode_id or getattr(self, "current_context_mode_id", "coding")
        return MODE_SHORT_LABELS.get(mid, "MODO")

    def _install_auxiliary_nodes(self) -> None:
        """Adds/refreshes the shared HELP, LANG_SELECT and MODE_SELECT nodes."""
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

        # Rebuild the hub every time because the "current mode" marker moves.
        self.menu_tree["MODE_SELECT"] = self._build_mode_select_node()

    def _build_mode_select_node(self) -> MenuNode:
        """Builds the 9-slot mode hub shown at startup and by [V]."""
        items: List[MenuAction] = []
        entry_by_id = {entry[0]: entry for entry in MODE_SELECTOR_ENTRIES}
        order = [
            "coding",
            "writing",
            "terminal",
            "data_math",
            None,  # slot 5: pause
            "navigation",
        ]

        for slot, mode_id in enumerate(order, start=1):
            if mode_id is None:
                items.append(create_pause_action(str(slot)))
                continue
            _, label, hint, icon = entry_by_id[mode_id]
            is_current = mode_id == getattr(self, "current_context_mode_id", "coding")
            items.append(
                MenuAction(
                    id=f"MODE_{mode_id.upper()}",
                    label=f"{slot}: {label}",
                    hint=("Estás en este modo" if is_current else hint),
                    action_type="MODE_SWITCH",
                    icon=icon,
                    mode_id=mode_id,
                )
            )

        # Slot 7: back to the current mode's ROOT (cancel).
        items.append(create_back_action("ROOT", "7"))
        # Slot 8: sniper mouse mode (help remains in the header and [H]).
        _, sniper_label, sniper_hint, sniper_icon = entry_by_id["sniper"]
        sniper_current = self.current_context_mode_id == "sniper"
        items.append(
            MenuAction(
                id="MODE_SNIPER",
                label=f"8: {sniper_label}",
                hint=("Estás en este modo" if sniper_current else sniper_hint),
                action_type="MODE_SWITCH",
                icon=sniper_icon,
                mode_id="sniper",
            )
        )
        # Slot 9: exit.
        items.append(
            MenuAction(
                id="MODE_EXIT",
                label="9: Salir",
                hint="Cerrar IDEye",
                action_type="EXIT",
                icon="exit",
            )
        )

        return MenuNode(
            id="MODE_SELECT",
            title="ELEGIR MODO",
            breadcrumb_label="ELEGIR MODO",
            items=items,
            parent_id="ROOT",
            sticky=False,
        )

    def open_mode_selector(self) -> None:
        """Opens the mode hub so the user can pick a mode explicitly."""
        if "MODE_SELECT" not in self.menu_tree:
            self._install_auxiliary_nodes()
        else:
            # Refresh the current-mode marker.
            self.menu_tree["MODE_SELECT"] = self._build_mode_select_node()
        self.navigate_to("MODE_SELECT")
        self.last_action_desc = "Elegir modo"
        self._mode_banner_text = "ELIGE UN MODO"
        try:
            self._mode_banner_start = time.time()
            self._mode_banner_until = self._mode_banner_start + 2.2
        except Exception:
            self._mode_banner_until = 0.0
        self.update()

    def _activate_mode(self, mode_id: Optional[str]) -> None:
        """Enters a mode selected from the hub and lands on its ROOT menu."""
        if not mode_id or self.mode_manager is None:
            return
        previous_mode = self.current_context_mode_id
        if mode_id == "sniper" and previous_mode != "sniper":
            self._sniper_previous_mode = previous_mode
        self._mode_selection_in_progress = True
        try:
            self.mode_manager.set_mode(mode_id, emit=True)
        finally:
            self._mode_selection_in_progress = False
        if "ROOT" in self.menu_tree:
            self.navigate_to("ROOT")
        self._sniper_step = 1
        self._sniper_locked_sector = None
        self.hovered_subcell = None
        self.last_action_desc = f"Modo: {getattr(self, 'current_context_mode_name', '')}"
        self._play_sound("mode")
        self.update()

    def cycle_context_mode(self) -> None:
        """[V] exits FreeLook, otherwise opens the mode hub."""
        if self.current_context_mode_id == "sniper":
            self._exit_sniper_mode()
        else:
            self.open_mode_selector()

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
        self.last_action_desc = f"Menús inteligentes: {'Activados' if self.adaptive_ast_enabled else 'Desactivados'}"
        self.adaptive_ast_toggled.emit(self.adaptive_ast_enabled)
        self.update()

    def toggle_auto_switch(self, enabled=None) -> bool:
        if self.mode_manager is not None:
            value = self.mode_manager.toggle_auto_switch(enabled)
            self.auto_switch_changed.emit(value)
            return value
        return False

    @pyqtSlot(bool)
    def set_adaptive_ast_enabled(self, enabled: bool) -> None:
        """Explicitly sets adaptive AST menus enabled status."""
        if self.adaptive_ast_enabled != enabled:
            self.adaptive_ast_enabled = enabled
            self._cached_adaptive_node = None
            self._last_ast_eval_time = 0.0
            self.last_action_desc = f"Menús inteligentes: {'Activados' if self.adaptive_ast_enabled else 'Desactivados'}"
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
        if item.action_type == "MODE_SWITCH":
            return "MODE"
        if item.action_type == "SNIPER_SECTOR":
            return "SNIPER"
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
        self._update_header_exit_rect()
        header_rect = self.header_rect
        pill_h = max(24.0, header_h - 12.0)
        logo_rect = self._header_logo_rect
        last_pill_rect = self._last_action_pill_rect
        sniper_pill_rect = self._sniper_action_pill_rect

        painter.setOpacity(0.95 if not self.reading_mode else 0.30)

        dpr = self.devicePixelRatioF() or 1.0

        # Unified floating command bar (Dynamic Island / Linear style)
        painter.setBrush(self._brush_header_bg)
        painter.setPen(self._pen_header_border)
        painter.drawRoundedRect(header_rect, 14.0, 14.0)

        IconManager.instance().render_icon(painter, "eyede_logo", logo_rect, dpr=dpr)

        # Brand + WS status (left side)
        brand_x = logo_rect.right() + 8.0
        painter.setPen(self._color_card_text_active)
        painter.setFont(self._font_header_bold_btn)
        painter.drawText(
            QRectF(brand_x, header_rect.y() + 6.0, 80.0, pill_h),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            "IDEye",
        )
        brand_w = float(painter.fontMetrics().horizontalAdvance("IDEye")) + 2.0
        ws_x = brand_x + brand_w + 10.0
        if getattr(self, "_header_ws_show", False):
            ws_color = QColor(34, 197, 94) if self._ws_connected else QColor(148, 163, 184)
            painter.setBrush(QBrush(ws_color))
            painter.setPen(Qt.PenStyle.NoPen)
            y = header_rect.y() + 6.0 + (pill_h - 6.0) * 0.5
            painter.drawEllipse(QRectF(ws_x, y, 6.0, 6.0))
            if not getattr(self, "_header_ws_dot_only", False):
                ws_text = "VS Code" if self._ws_connected else "Local"
                painter.setPen(self._pen_header_left)
                painter.setFont(self._font_header_left)
                painter.drawText(
                    QRectF(ws_x + 11.0, header_rect.y() + 6.0, 120.0, pill_h),
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                    ws_text,
                )

        # Sniper action selector, or compact last-action status.
        if sniper_pill_rect.isValid():
            mode = self._sniper_mode()
            action_label = getattr(mode, "action_label", "Clic Izq") if mode else "Clic Izq"
            painter.setBrush(QBrush(QColor(244, 63, 94, 38)))
            painter.setPen(QPen(QColor(244, 63, 94, 220), 1.2))
            painter.drawRoundedRect(sniper_pill_rect, 7.0, 7.0)
            painter.setPen(QColor(254, 205, 211))
            painter.setFont(self._font_header_bold_btn)
            action_text = painter.fontMetrics().elidedText(
                f"RATÓN: {action_label}",
                Qt.TextElideMode.ElideRight,
                int(max(0.0, sniper_pill_rect.width() - 14.0)),
            )
            painter.drawText(sniper_pill_rect, Qt.AlignmentFlag.AlignCenter, action_text)
        elif last_pill_rect.isValid():
            painter.setBrush(self._brush_status_pill)
            painter.setPen(self._pen_status_pill)
            painter.drawRoundedRect(last_pill_rect, 7.0, 7.0)
            painter.setPen(self._pen_header_right)
            painter.setFont(self._font_header_right)
            status_text = painter.fontMetrics().elidedText(
                f"Última: {self.last_action_desc}",
                Qt.TextElideMode.ElideRight,
                int(max(0.0, last_pill_rect.width() - 14.0)),
            )
            painter.drawText(last_pill_rect, Qt.AlignmentFlag.AlignCenter, status_text)

        icon_size = 20.0

        # Exit: soft red command button
        if self.active_click_header_exit:
            exit_brush, exit_pen, exit_text_color = self._brush_click, self._pen_click, self._color_click_text
        elif self.hovered_header_exit:
            painter.setBrush(self._brush_exit_glow)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(self.header_exit_rect.adjusted(-4.0, -4.0, 4.0, 4.0), 10.0, 10.0)
            exit_brush, exit_pen, exit_text_color = QBrush(QColor(239, 68, 68, 230)), QPen(QColor(254, 202, 202), 2.0), QColor(255, 255, 255)
        else:
            exit_brush, exit_pen, exit_text_color = self._brush_exit_idle, self._pen_exit_idle, self._color_exit_text
        painter.setBrush(exit_brush)
        painter.setPen(exit_pen)
        painter.drawRoundedRect(self.header_exit_rect, 8.0, 8.0)
        exit_icon_rect = QRectF(
            self.header_exit_rect.x() + 12.0,
            self.header_exit_rect.y() + (pill_h - icon_size) * 0.5,
            icon_size,
            icon_size,
        )
        IconManager.instance().render_icon(painter, "exit", exit_icon_rect, color="#FCA5A5", dpr=dpr)
        painter.setPen(exit_text_color)
        painter.setFont(self._font_header_bold_btn)
        painter.drawText(
            QRectF(self.header_exit_rect.x() + 34.0, self.header_exit_rect.y(), self.header_exit_rect.width() - 38.0, pill_h),
            Qt.AlignmentFlag.AlignCenter,
            "SALIR",
        )

        # Help
        if self.active_click_header_help:
            help_brush, help_pen, help_text_color = self._brush_click, self._pen_click, self._color_click_text
        elif self.hovered_header_help:
            painter.setBrush(self._brush_help_glow)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(self.header_help_rect.adjusted(-4.0, -4.0, 4.0, 4.0), 10.0, 10.0)
            help_brush, help_pen, help_text_color = QBrush(QColor(14, 165, 233, 230)), QPen(QColor(186, 230, 253), 2.0), QColor(255, 255, 255)
        else:
            help_brush, help_pen, help_text_color = self._brush_help_idle, self._pen_help_idle, self._color_help_text
        painter.setBrush(help_brush)
        painter.setPen(help_pen)
        painter.drawRoundedRect(self.header_help_rect, 8.0, 8.0)
        help_vpad = 2.0
        help_icon_rect = QRectF(
            self.header_help_rect.x() + 12.0,
            self.header_help_rect.y() + (pill_h - icon_size) * 0.5,
            icon_size,
            icon_size,
        )
        IconManager.instance().render_icon(painter, "help", help_icon_rect, color="#7DD3FC", dpr=dpr)
        painter.setPen(help_text_color)
        painter.setFont(self._font_header_bold_btn)
        painter.drawText(
            QRectF(
                self.header_help_rect.x() + 36.0,
                self.header_help_rect.y() + help_vpad,
                self.header_help_rect.width() - 46.0,
                pill_h - help_vpad * 2.0,
            ),
            Qt.AlignmentFlag.AlignCenter,
            "AYUDA",
        )

        # Mode selector: single interactive button (mode + dropdown hint)
        if self.active_click_header_mode:
            mode_brush, mode_pen, mode_text_color = self._brush_click, self._pen_click, self._color_click_text
        elif self.hovered_header_mode:
            painter.setBrush(self._brush_mode_glow)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(self.header_mode_rect.adjusted(-4.0, -4.0, 4.0, 4.0), 11.0, 11.0)
            mode_brush, mode_pen, mode_text_color = self._brush_mode_idle, QPen(QColor(255, 255, 255, 170), 1.5), QColor(255, 255, 255)
        else:
            mode_brush, mode_pen, mode_text_color = self._brush_mode_idle, self._pen_mode_idle, self._color_mode_text
        painter.setBrush(mode_brush)
        painter.setPen(mode_pen)
        painter.drawRoundedRect(self.header_mode_rect, 8.0, 8.0)
        mode_icon_rect = QRectF(
            self.header_mode_rect.x() + 9.0,
            self.header_mode_rect.y() + (pill_h - 18.0) * 0.5,
            18.0,
            18.0,
        )
        mode_icon_color = self.theme_color or "#00F0FF"
        IconManager.instance().render_icon(painter, "mode", mode_icon_rect, color=mode_icon_color, dpr=dpr)
        painter.setPen(mode_text_color)
        painter.setFont(self._font_header_bold_btn)
        mode_label = f"MODO: {self._short_mode_label()}  ▾  (V)"
        mode_label = painter.fontMetrics().elidedText(
            mode_label,
            Qt.TextElideMode.ElideRight,
            int(max(20.0, self.header_mode_rect.width() - 36.0)),
        )
        painter.drawText(
            QRectF(self.header_mode_rect.x() + 31.0, self.header_mode_rect.y(), self.header_mode_rect.width() - 36.0, pill_h),
            Qt.AlignmentFlag.AlignCenter,
            mode_label,
        )

        # Language badge [ PY ]
        if self.active_click_header_lang:
            lang_brush, lang_pen, lang_text_color = self._brush_click, self._pen_click, self._color_click_text
        elif self.hovered_header_lang:
            lang_brush, lang_pen, lang_text_color = QBrush(QColor(168, 85, 247, 210)), QPen(QColor(243, 232, 255), 1.6), QColor(255, 255, 255)
        else:
            lang_brush, lang_pen, lang_text_color = self._brush_btn_idle, self._pen_btn_idle, QColor(216, 180, 254)
        painter.setBrush(lang_brush)
        painter.setPen(lang_pen)
        painter.drawRoundedRect(self.header_lang_rect, 8.0, 8.0)
        lang_badge = get_language_badge(self.current_language)
        painter.setPen(lang_text_color)
        painter.setFont(self._font_header_bold_btn)
        painter.drawText(
            self.header_lang_rect,
            Qt.AlignmentFlag.AlignCenter,
            f"[ {lang_badge} ]",
        )

        # =====================================================================
        # 1b. Transient mode-change banner (makes coding/writing switch obvious)
        # =====================================================================
        try:
            now = time.time()
            if (
                self._mode_banner_text
                and now < self._mode_banner_until
                and self.current_context_mode_id != "sniper"
            ):
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
        icon_map = {
            "FLOW": "flow",
            "STRUCT": "function",
            "OPERATORS": "operators",
            "NAV": "navigation",
            "PAUSE": "pause_eye",
            "BACK": "arrow_left",
            "T9": "variables",
            "EDIT": "edit",
            "FORMAT": "format",
            "AI": "ai_spark",
            "EXIT": "exit",
            "MODE": "mode",
            "SNIPER": "crosshair",
        }

        for i in range(9):
            if self.current_context_mode_id == "sniper" and self.current_node_id != "MODE_SELECT":
                continue
            if i >= len(items):
                continue
            item = items[i]
            rect = self.get_block_rect(i)
            is_active_click = (self.active_click_block == i)
            is_hover = (self.hovered_block == i)
            is_reading_center = self.reading_mode and i == 4
            is_active = is_hover or is_active_click or is_reading_center
            cat = self._get_category_for_item(item, i)
            is_danger = cat == "EXIT" or item.action_type == "EXIT"

            # Reading mode keeps only the center resume card readable.
            if self.reading_mode and i != 4:
                body_brush = self._brush_reading_other
                border_pen = self._pen_reading_other
                text_opacity = 0.22
                band_brush = self._brush_band_inactive
            elif is_reading_center:
                body_brush = self._brush_card_active
                border_pen = self._pen_reading_center
                text_opacity = 1.0
                band_brush = self._brush_band_active
            elif is_active:
                body_brush = self._brush_card_active
                border_pen = self._pen_card_danger if is_danger else self._pen_card_active
                text_opacity = 1.0
                band_brush = self._brush_band_active
            else:
                body_brush = self._brush_card_inactive
                border_pen = self._pen_card_inactive
                text_opacity = 1.0
                band_brush = self._brush_band_inactive

            # 1. Transparent body (keeps VS Code readable)
            painter.setOpacity(1.0)
            painter.setBrush(body_brush)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(rect, 12.0, 12.0)

            # 2. Focused card gets a subtle theme glow at the top edge.
            if is_active and not self.reading_mode:
                theme = border_pen.color()
                gradient = QLinearGradient(rect.x(), rect.y(), rect.right(), rect.y())
                transparent = QColor(theme)
                transparent.setAlpha(0)
                middle = QColor(theme)
                middle.setAlpha(105)
                gradient.setColorAt(0.0, transparent)
                gradient.setColorAt(0.5, middle)
                gradient.setColorAt(1.0, transparent)
                painter.fillRect(
                    QRectF(rect.x() + 14.0, rect.y() + 1.0, max(1.0, rect.width() - 28.0), 3.0),
                    QBrush(gradient),
                )

            # 3. Neutral 1px frame, or 2.5px theme frame for the focused card.
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(border_pen)
            painter.drawRoundedRect(rect, 12.0, 12.0)

            # 4. High-contrast header band with rounded top corners.
            band_h = min(52.0, rect.height())
            if band_h > 4.0:
                radius = 12.0
                path = QPainterPath()
                path.moveTo(rect.x(), rect.y() + radius)
                path.quadTo(rect.x(), rect.y(), rect.x() + radius, rect.y())
                path.lineTo(rect.right() - radius, rect.y())
                path.quadTo(rect.right(), rect.y(), rect.right(), rect.y() + radius)
                path.lineTo(rect.right(), rect.y() + band_h)
                path.lineTo(rect.x(), rect.y() + band_h)
                path.closeSubpath()
                painter.setBrush(band_brush)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawPath(path)

            # Content (dimmed for inactive cards)
            painter.save()
            painter.setOpacity(text_opacity)

            number = i + 1
            number_rect = QRectF(rect.x() + 10.0, rect.y() + 8.0, 24.0, 24.0)
            painter.setBrush(self._brush_badge_theme if is_active else self._brush_badge_inactive)
            painter.setPen(self._pen_badge_theme if is_active else self._pen_badge_active)
            painter.drawRoundedRect(number_rect, 7.0, 7.0)
            painter.setPen(self._color_theme_text if is_active else self._color_card_text_inactive)
            painter.setFont(self._font_card_number)
            painter.drawText(number_rect, Qt.AlignmentFlag.AlignCenter, str(number))

            # Status badge (right side of the band)
            badge_text = ""
            badge_color = self._color_badge_default
            if item.action_type == "MODE_SWITCH":
                badge_text = (
                    "ACTUAL"
                    if item.mode_id == getattr(self, "current_context_mode_id", "")
                    else "ELEGIR"
                )
                badge_color = self._color_badge_sticky
            elif item.action_type == "SUBMENU":
                badge_text = "SUBMENÚ"
                badge_color = self._color_badge_submenu
            elif item.action_type == "BACK":
                badge_text = "VOLVER"
                badge_color = self._color_badge_back
            elif item.sticky:
                badge_text = "FIJO"
                badge_color = self._color_badge_sticky
            elif is_danger:
                badge_text = "SALIR"
                badge_color = self._color_badge_back

            # Status badge + vector icon at the right of the band.
            icon_name = item.icon if item.action_type == "MODE_SWITCH" and item.icon else icon_map.get(cat)
            badge_rect, icon_rect = self._card_header_rects(rect, badge_text, bool(icon_name))

            if badge_rect.isValid():
                painter.setBrush(self._brush_badge_active if is_active else self._brush_badge_inactive)
                painter.setPen(self._pen_badge_active if is_active else self._pen_btn_idle)
                painter.drawRoundedRect(badge_rect, 6.0, 6.0)
                painter.setPen(badge_color)
                painter.setFont(self._font_status)
                painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, badge_text)

            if icon_rect.isValid() and icon_name:
                IconManager.instance().render_cell_icon(
                    painter,
                    icon_name,
                    icon_rect,
                    icon_size=20.0,
                    color=(border_pen.color() if is_active else QColor("#CBD5E1")),
                    dpr=dpr,
                )

            # Title + subtitle inside the dark band.
            title = _clean_action_label(_menu_card_label(item)) or item.label
            subtitle = item.hint or ""
            if self.reading_mode and i == 4:
                title = "REANUDAR"
                subtitle = "Modo lectura activo · mira y abre la boca"

            title_left = rect.x() + 42.0
            first_right = min(
                badge_rect.left() if badge_rect.isValid() else rect.right() - 8.0,
                icon_rect.left() if icon_rect.isValid() else rect.right() - 8.0,
            )
            title_right = first_right - 8.0
            title_w = max(20.0, title_right - title_left)
            painter.setPen(self._color_card_text_active if is_active else self._color_card_text_inactive)
            painter.setFont(self._font_label)
            title_text = painter.fontMetrics().elidedText(
                title,
                Qt.TextElideMode.ElideRight,
                int(title_w),
            )
            painter.drawText(
                QRectF(title_left, rect.y() + 5.0, title_w, 24.0),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                title_text,
            )

            if subtitle:
                painter.setPen(self._color_card_subtitle if is_active else self._color_card_subtitle_inactive)
                painter.setFont(self._font_card_subtitle)
                subtitle_text = painter.fontMetrics().elidedText(
                    subtitle,
                    Qt.TextElideMode.ElideRight,
                    int(title_w),
                )
                painter.drawText(
                    QRectF(title_left, rect.y() + 27.0, title_w, 17.0),
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                    subtitle_text,
                )

            if not self.reading_mode:
                self._paint_preview_chips(painter, rect, self._preview_chip_labels(item))

            painter.restore()

        # =====================================================================
        # 3. High-Contrast In-App Gesture & Shortcut Cheat Sheet Modal Card
        # =====================================================================
        if getattr(self, "show_help_modal", False):
            self._paint_help_modal(painter, w, h)

        # =====================================================================
        # 3b. Sniper precision sub-grid (step 2)
        # =====================================================================
        if self.current_context_mode_id == "sniper" and self.current_node_id != "MODE_SELECT":
            self._paint_freelook_overlay(painter)

        # =====================================================================
        # 4. Refined High-Visibility Dual-Ring Reticle with Glow Aura
        # =====================================================================
        if not self.reading_mode or self.hovered_block == 4:
            painter.setOpacity(0.95 if not self.reading_mode else 0.85)
            gx, gy = self.current_gaze
            cx = gx * w
            cy = gy * h
            threshold = max(0.01, float(getattr(self, "mar_threshold", 0.55)))
            ratio = max(0.0, min(1.0, float(getattr(self, "current_mar", 0.0)) / threshold))
            ring_r = 11.0 - 2.0 * ratio
            center = QPointF(cx, cy)

            # Soft glow, thin ring, and a 6px center point.
            painter.setBrush(self._brush_pointer_glow)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(center, ring_r + 7.0, ring_r + 7.0)

            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(self._pen_pointer_ring)
            painter.drawEllipse(center, ring_r, ring_r)

            # MAR progress arc closes around the ring as the mouth opens.
            if ratio > 0.005:
                progress_color = (
                    self._color_progress_warm if ratio >= 0.72 else self._color_progress_cool
                )
                self._pen_pointer_progress.setColor(progress_color)
                painter.setPen(self._pen_pointer_progress)
                arc_rect = QRectF(cx - ring_r, cy - ring_r, ring_r * 2.0, ring_r * 2.0)
                painter.drawArc(arc_rect, 90 * 16, -int(360 * 16 * ratio))

            painter.setBrush(self._brush_pointer_dot)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(center, 3.0, 3.0)

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
            "GESTOS FACIALES Y OCULARES",
        )

        item_y = col_a_rect.y() + 36.0
        for title, action, desc in HELP_GESTURES:
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
            "ATAJOS DE TECLADO RÁPIDOS",
        )

        item_y = col_b_rect.y() + 34.0
        for key, name, desc in HELP_SHORTCUTS:
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
