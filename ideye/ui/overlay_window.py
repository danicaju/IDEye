"""
Overlay Window Module for IDEye (Phase 2 & 3)
Transparent, Non-Focus-Stealing 3x3 Macro-Block Grid Overlay with Hierarchical
Syntax Navigation Trees, Real-Time Code Injection, and Breadcrumb Status Bar.

Features:
- Configures Qt.WindowType.WindowDoesNotAcceptFocus, FramelessWindowHint,
  WindowStaysOnTopHint, Tool, and WA_TranslucentBackground.
- Ensures external IDEs (e.g. VS Code, PyCharm) NEVER lose keyboard focus or cursor blink.
- Renders hierarchical 3x3 Menu Trees (build_menu_tree):
    * Root Menu (Flow, Struct, Operators, Nav, Pause, Keywords, Edit, Format, Snippets).
    * Submenus with visual indicators ('SUBMENU', 'ACCION', 'PAUSA', 'VOLVER').
- Top Breadcrumb Bar displaying current navigation path (e.g. 'RAIZ > FLUJO') and last executed action.
- Sticky submenu mode for repetitive actions (Nav, Edit, Format).
- Non-blocking CodeInjector integration: snippets pasted via clipboard with cursor centering and keystrokes.
- Block 4 (Center: 'PAUSA / MODO LECTURA') toggles HUD opacity to 10% and inhibits actions during reading.
"""

from typing import Optional, Tuple, Dict, Any, List
from collections import deque
import sys
import os
import math
import time

from PyQt6.QtCore import (
    Qt,
    QTimer,
    QVariantAnimation,
    QEasingCurve,
    pyqtSignal,
    pyqtSlot,
    QRect,
    QRectF,
    QPointF,
)
from PyQt6.QtGui import QGuiApplication, QPainter, QColor, QFont, QFontMetrics, QPen, QBrush, QPainterPath, QLinearGradient
from PyQt6.QtWidgets import QWidget, QApplication

try:
    import ideye.config as config
    from ideye.ui.icon_manager import IconManager
    from ideye.ui.header_layout import HeaderLayout
    from ideye.core.sound_feedback import SoundFeedbackManager
    from ideye.core.mouse_controller import OSMouseController
    from ideye.actions.code_injector import CodeInjector
    from ideye.actions.language_support import (
        LANG_PYTHON,
        LANG_TYPESCRIPT,
        LANG_RUST,
        LANG_CPP,
        LANG_GO,
        normalize_language,
        get_language_display_name,
        get_language_badge,
    )
    from ideye.actions.menu_trees import (
        MenuNode,
        MenuAction,
        build_menu_tree,
        get_breadcrumb_path,
        populate_ai_prediction_items,
        populate_exit_confirm_items,
        populate_help_items,
        populate_lang_select_items,
        create_pause_action,
        create_back_action,
        get_adaptive_context_node,
        create_adaptive_menu_action,
        get_dynamic_ast_action_for_context,
        populate_command_palette_items,
    )
    from ideye.actions.context_reader import ContextReader, detect_syntactic_context
    from ideye.actions.ai_predictor import AIPredictorWorker
    from ideye.actions.diagnostics_fixer import DiagnosticsFixer
    from ideye.actions.ast_code_jumper import ASTCodeJumper
    from ideye.actions.agentic_launcher import AgenticPromptLauncher
    from ideye.core.gaze_scroller import GazeScroller
    from ideye.ui.sniper_lens import SniperLens
    from ideye.modes.mode_manager import ModeManager
except ImportError:
    import config
    from ui.icon_manager import IconManager
    from ui.header_layout import HeaderLayout
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
        populate_exit_confirm_items,
        populate_help_items,
        populate_lang_select_items,
        create_pause_action,
        create_back_action,
        get_adaptive_context_node,
        create_adaptive_menu_action,
        get_dynamic_ast_action_for_context,
        populate_command_palette_items,
    )
    from actions.context_reader import ContextReader, detect_syntactic_context
    from actions.ai_predictor import AIPredictorWorker
    from actions.diagnostics_fixer import DiagnosticsFixer
    from actions.ast_code_jumper import ASTCodeJumper
    from actions.agentic_launcher import AgenticPromptLauncher
    from core.gaze_scroller import GazeScroller
    from ui.sniper_lens import SniperLens
    from modes.mode_manager import ModeManager


from ideye.core.logging_config import get_logger

logger = get_logger(__name__)

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
        "Apertura de boca (MAR)",
        "Clic / inyectar / navegar",
        "Abre la boca brevemente para activar la casilla enfocada.",
    ),
    (
        "Boca mantenida (Jaw-Lock)",
        "Arrastrar / seleccionar",
        "Mantén la boca abierta para arrastrar sin botones.",
    ),
    (
        "Guiño ojo izquierdo",
        "Volver / deshacer",
        "Cierra el ojo izquierdo ~200 ms para retroceder o deshacer.",
    ),
    (
        "Guiño ojo derecho",
        "Pausa / Gaming: joystick ⇄ cursor",
        "Cierra el ojo derecho ~200 ms para ocultar el HUD o cambiar el control de juego.",
    ),
)

HELP_SHORTCUTS = (
    ("[Ctrl+Alt+A]", "Menús inteligentes", "Adapta las opciones al código bajo el cursor."),
    ("[Ctrl+Alt+B]", "Portapapeles", "Abre las últimas 6 copias en cuadrícula 3x3."),
    ("[Ctrl+Alt+L]", "Cambiar lenguaje", "Cicla Python, TypeScript, Rust, C++ y Go."),
    ("[Ctrl+Alt+H]", "Ayuda", "Abre o cierra esta guía."),
    ("[Ctrl+Alt+V]", "Elegir modo", "Abre el selector de modos."),
    ("[Ctrl+Alt+K]", "Auto-switch", "Activa o desactiva el cambio automático."),
    ("[Ctrl+Alt+T]", "Modo tracking", "Cicla Cabeza, Híbrido e Iris."),
    ("[Ctrl+Alt+M]", "Monitor", "Colapsa o expande el panel de depuración."),
    ("[Ctrl+Alt+C]", "Calibrar centro", "Fija la posición actual como centro neutro."),
    ("[Ctrl+Alt+P]", "Pausa / lectura", "Oculta el HUD para descansar la vista."),
    ("[Ctrl+Alt+S]", "Sonido", "Activa o silencia el audio."),
    ("[Ctrl+Alt+F]", "FreeLook", "Activa el ratón por mirada."),
    ("[Ctrl+Alt+G]", "Gaming", "Alterna el perfil Gaming."),
    ("[Ctrl+Alt+N]", "Cambiar pantalla", "Mueve HUD y mirada al siguiente monitor."),
    ("[Ctrl+Alt+Z]", "Lupa Sniper", "Activa la lupa x3.5 y el modo slow-mo en FreeLook."),
    ("[Ctrl+Alt+J]", "Salto AST", "Abre el mapa 3x3 de clases, m?todos y funciones."),
    ("[Ctrl+Alt+Q]", "Salida de emergencia", "Cierra IDEye de inmediato."),
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
    screen_cycle_requested = pyqtSignal()
    interactive_guide_requested = pyqtSignal()
    text_injected = pyqtSignal(int)  # characters inserted into the active editor
    mouth_clicked = pyqtSignal(int)  # hovered block index, or -1 for header/other
    autofix_requested = pyqtSignal(object)
    ast_jump_requested = pyqtSignal(int)
    agentic_prompt_requested = pyqtSignal(str, str, bool)  # action_id, prompt, queue_only
    ghost_peek_toggled = pyqtSignal(bool)
    gaze_scroll_toggled = pyqtSignal(bool)
    micro_recalibration_requested = pyqtSignal(float, float)
    layout_changed = pyqtSignal(str)
    theme_changed = pyqtSignal(str)
    undo_requested = pyqtSignal()
    mode_changed = context_mode_changed

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        code_injector: Optional[CodeInjector] = None,
        menu_tree: Optional[Dict[str, MenuNode]] = None,
        context_reader: Optional[ContextReader] = None,
        mode_manager: Optional[Any] = None,
        macro_manager: Optional[Any] = None,
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
        self.clipboard_manager: Optional[Any] = None
        self.menu_tree: Dict[str, MenuNode] = menu_tree if menu_tree is not None else build_menu_tree(self.current_language)
        self.context_reader: ContextReader = context_reader if context_reader is not None else ContextReader()
        if hasattr(self.code_injector, "set_context_reader"):
            self.code_injector.set_context_reader(self.context_reader)
        self.diagnostics_fixer = DiagnosticsFixer(self.context_reader)
        self.ast_code_jumper = ASTCodeJumper(self.context_reader)
        self.agentic_launcher = AgenticPromptLauncher(
            self.context_reader,
            self.diagnostics_fixer,
        )
        self._last_agentic_action_id: str = "refactor_clean"
        self._ast_page: int = 0
        self._active_diagnostics: List[Dict[str, Any]] = []
        self._vscode_editor_state: Dict[str, Any] = {}
        self._autofix_slot8_saved: Optional[tuple] = None
        self.autofix_badge_rect: QRectF = QRectF()
        self.sniper_lens = SniperLens(
            zoom=float(getattr(config, "SNIPER_LENS_ZOOM", 3.5)),
            slowmo_factor=float(getattr(config, "SNIPER_LENS_SLOWMO", 0.28)),
        )
        self._lens_pixmap = None
        self._lens_capture_target: Optional[tuple] = None
        self._lens_capture_in_progress: bool = False
        self._last_freelook_click_ts: float = 0.0
        self._jaw_lock_since: float = 0.0
        self.mode_manager = mode_manager if mode_manager is not None else ModeManager(
            initial_mode="coding", language=self.current_language
        )
        try:
            self.mode_manager.set_language(self.current_language)
        except Exception:
            pass
        self.current_context_mode_id: str = getattr(self.mode_manager, "current_mode_id", "coding")
        self.current_context_mode_name: str = getattr(self.mode_manager, "current_mode", None).display_name if getattr(self.mode_manager, "current_mode", None) is not None else "Código"
        self.theme_color: str = getattr(self.mode_manager, "current_mode", None).theme_color if getattr(self.mode_manager, "current_mode", None) is not None else "#3b82f6"
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
        self.macro_manager: Optional[Any] = macro_manager
        self._sniper_step: int = 1
        self._sniper_locked_sector: Optional[int] = None
        self._sniper_previous_mode: Optional[str] = None
        self.hovered_subcell: Optional[int] = None
        self.hovered_sniper_action: bool = False
        self._sniper_action_pill_rect: QRectF = QRectF()
        self.header_screen_rect: QRectF = QRectF()
        self.hovered_header_screen: bool = False
        self.screen_index: int = 0
        self.screen_count: int = 1

        # FreeLook / gaming state
        self._freelook_last_pos: Tuple[int, int] = (0, 0)
        self._edge_scroll_direction: int = 0
        self._edge_scroll_since: float = 0.0
        self._edge_scroll_last: float = 0.0
        self._jaw_locked: bool = False
        self._jaw_lock_pos: Optional[Tuple[int, int]] = None
        self._mouth_active: bool = False
        self._mouth_start: float = 0.0
        self._hold_started: bool = False
        self._gaming_mode: bool = False
        self._gaming_right_held: bool = False
        self._gaming_control_state: str = "JOYSTICK"
        self._game_profile_name: str = "default_desktop"
        self._game_profile_label: str = "Escritorio"
        self.game_profile_badge_rect: QRectF = QRectF()
        self._game_keys_down: set = set()
        self._gaming_toggle_rect: QRectF = QRectF()
        self.hovered_gaming_toggle: bool = False
        self._font_freelook_hint = QFont("Segoe UI", 10, QFont.Weight.Bold)
        self._gravity_block: Optional[int] = None
        self._gravity_since: float = 0.0

        # Adaptive AST Context Menu Subsystem (Phase Extra - Option A)
        self.adaptive_ast_enabled: bool = getattr(config, "ENABLE_ADAPTIVE_AST_MENUS", True)
        self._last_detected_context_name: str = "GENERAL"
        self._cached_adaptive_node: Optional[MenuNode] = None
        if "MENU_STANDARD" not in self.menu_tree and "ROOT" in self.menu_tree:
            std_items = list(self.menu_tree["ROOT"].items)
            if len(std_items) > 8:
                std_items[8] = create_adaptive_menu_action("9")
            else:
                std_items.append(create_adaptive_menu_action("9"))
            self.menu_tree["MENU_STANDARD"] = MenuNode(
                id="MENU_STANDARD",
                title="MENÚ ESTÁNDAR",
                breadcrumb_label="ESTÁNDAR",
                items=std_items,
                parent_id="ROOT",
                sticky=False,
            )

        self._install_auxiliary_nodes()
        self._apply_macro_overrides()
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
        self.gaze_scroller = GazeScroller()
        self._gaze_scroll_enabled: bool = bool(getattr(config, "GAZE_SCROLL_ENABLED", True))
        self.ghost_peek_enabled: bool = bool(getattr(config, "GHOST_PEEK_ENABLED", True))
        self.ghost_peek_idle_seconds: float = max(
            30.0, float(getattr(config, "GHOST_PEEK_IDLE_SECONDS", 30.0))
        )
        self._ghost_opacity: float = 1.0
        self._last_ghost_interaction: float = time.time()
        self._last_ghost_gaze: Tuple[float, float] = (0.5, 0.5)
        self._ghost_timer = QTimer(self)
        self._ghost_timer.setInterval(50)
        self._ghost_timer.timeout.connect(self._tick_ghost_peek)
        self._ghost_timer.start()

        # Hands-free header exit button state
        self.hovered_header_exit: bool = False
        self.active_click_header_exit: bool = False
        self.header_exit_rect: QRectF = QRectF()
        self._exit_armed_until: float = 0.0

        # Hands-free header help button & cheat sheet modal state
        self.hovered_header_help: bool = False
        self.active_click_header_help: bool = False
        self.header_help_rect: QRectF = QRectF()
        self.show_help_modal: bool = False
        self.help_modal_rect: QRectF = QRectF()
        self.help_modal_close_rect: QRectF = QRectF()
        self.help_modal_guide_rect: QRectF = QRectF()
        self.help_modal_tutorial_rect: QRectF = QRectF()
        self.hovered_help_modal_close: bool = False
        self.hovered_help_modal_guide: bool = False
        self.hovered_help_modal_tutorial: bool = False

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
        self._right_margin_target: float = 0.0
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
        self.mar_calibrated: bool = True
        self._mar_rest_window: deque = deque(maxlen=90)
        self._mar_rest_baseline: float = max(
            0.15,
            min(
                0.60,
                max(
                    float(getattr(config, "MAR_REST_THRESHOLD", 0.20)),
                    self.mar_threshold - 0.18,
                ),
            ),
        )
        self.resize(1920, 1080)

        # Flexible HUD Layout (Full Grid 100% vs Right Dock 30% Column)
        self.hud_layout_mode: str = getattr(config, "DEFAULT_HUD_LAYOUT", "FULL_GRID")
        self.right_dock_ratio: float = getattr(config, "RIGHT_DOCK_WIDTH_RATIO", 0.30)
        self.right_dock_min_w: float = getattr(config, "RIGHT_DOCK_MIN_WIDTH", 460.0)
        self.right_dock_max_w: float = getattr(config, "RIGHT_DOCK_MAX_WIDTH", 500.0)

        # Adaptive Dwell-Time Engine
        self.adaptive_dwell_enabled: bool = getattr(config, "ADAPTIVE_DWELL_ENABLED", True)
        self.dwell_click_enabled: bool = bool(
            getattr(config, "DWELL_CLICK_ENABLED", False)
            or getattr(config, "ADAPTIVE_DWELL_CLICK_ENABLED", False)
        )
        self._dwell_block: Optional[int] = None
        self._dwell_start_time: float = 0.0
        self._dwell_progress: float = 0.0
        self._dwell_fired: bool = False

        # Visual Theme Support (OLED Black WCAG AAA, Solarized Dark, Cyber Glass)
        self.current_theme: str = getattr(config, "DEFAULT_THEME", "CYBER_GLASS")

        # Interactive 3-Step Guided Onboarding Mini-Tutorial
        self.show_tutorial_modal: bool = False
        self.tutorial_modal_close_rect: QRectF = QRectF()
        self.tutorial_step: int = 1  # 1: Dwell, 2: MAR/Wink, 3: Rest, 4: Done
        self.tutorial_step_progress: float = 0.0
        self._tutorial_rest_start: float = 0.0
        self._last_mouth_click_time: float = 0.0

        # Gaze Estimator reference for micro-recalibration
        self.gaze_estimator: Optional[Any] = None

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
        self._font_modal_close = QFont("Segoe UI", 10, QFont.Weight.Bold)

        # Header / command bar styles (Sleek Cyber-Glass)
        self._brush_header_bg = QBrush(QColor(10, 15, 29, 225))
        self._pen_header_border = QPen(QColor(30, 41, 59, 200), 1.0)
        self._pen_header_left = QPen(QColor(148, 163, 184))
        self._pen_header_center = QPen(QColor(248, 113, 113))
        self._pen_header_right = QPen(QColor(96, 165, 250))

        # Focus hierarchy: neutral inactive cards, theme-colored active card.
        self._brush_card_inactive = QBrush(QColor(10, 15, 29, 220))
        self._pen_card_inactive = QPen(QColor(30, 41, 59, 180), 1.0)
        self._brush_card_active = QBrush(QColor(15, 23, 42, 235))
        self._pen_card_active = QPen(QColor("#3b82f6"), 2.0)
        self._pen_card_danger = QPen(QColor(239, 68, 68), 2.0)
        self._brush_band_inactive = QBrush(QColor(10, 15, 29, 230))
        self._brush_band_active = QBrush(QColor(15, 23, 42, 240))
        self._color_card_text_inactive = QColor(226, 232, 240, 255)
        self._color_card_text_active = QColor(248, 250, 252, 255)
        self._color_card_subtitle = QColor(148, 163, 184, 220)
        self._color_card_subtitle_inactive = QColor(148, 163, 184, 255)
        self._pen_badge_active = QPen(QColor(255, 255, 255, 90), 1.0)
        self._brush_badge_active = QBrush(QColor(255, 255, 255, 28))
        self._brush_badge_inactive = QBrush(QColor(255, 255, 255, 12))
        self._brush_status_pill = QBrush(QColor(37, 99, 235, 25))
        self._pen_status_pill = QPen(QColor(59, 130, 246, 80), 1.0)
        self._brush_btn_idle = QBrush(QColor(30, 41, 59, 90))
        self._pen_btn_idle = QPen(QColor(30, 41, 59, 180), 1.0)
        self._brush_help_idle = QBrush(QColor(37, 99, 235, 25))
        self._pen_help_idle = QPen(QColor(59, 130, 246, 120), 1.0)
        self._brush_exit_idle = QBrush(QColor(239, 68, 68, 28))
        self._pen_exit_idle = QPen(QColor(239, 68, 68, 105), 1.0)
        self._brush_exit_glow = QBrush(QColor(239, 68, 68, 55))
        self._brush_help_glow = QBrush(QColor(37, 99, 235, 65))
        self._color_exit_text = QColor(254, 202, 202)
        self._color_help_text = QColor(219, 234, 254)
        self._brush_mode_idle = QBrush(QColor(37, 99, 235, 30))
        self._pen_mode_idle = QPen(QColor("#3b82f6"), 1.0)
        self._brush_mode_glow = QBrush(QColor(59, 130, 246, 60))
        self._color_mode_text = QColor(239, 246, 255)

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
            "MODE": QPen(QColor(59, 130, 246, 200), 1.8),
            "SNIPER": QPen(QColor(244, 63, 94, 210), 1.8),
            "DEFAULT": self._pen_default,
        }
        self._cat_top_pens = {
            "FLOW": QPen(QColor(59, 130, 246, 220), 2.5),
            "STRUCT": QPen(QColor(251, 191, 36, 220), 2.5),
            "OPERATORS": QPen(QColor(192, 132, 252, 220), 2.5),
            "NAV": QPen(QColor(96, 165, 250, 220), 2.5),
            "PAUSE": QPen(QColor(52, 211, 153, 230), 2.5),
            "BACK": QPen(QColor(244, 114, 182, 220), 2.5),
            "EDIT": QPen(QColor(129, 140, 248, 220), 2.5),
            "AI": QPen(QColor(240, 171, 252, 220), 2.5),
            "EXIT": QPen(QColor(248, 113, 113, 220), 2.5),
            "LANG": QPen(QColor(168, 85, 247, 220), 2.5),
            "MODE": QPen(QColor(59, 130, 246, 220), 2.5),
            "SNIPER": QPen(QColor(244, 63, 94, 230), 2.5),
            "DEFAULT": QPen(QColor(100, 116, 139, 180), 2.0),
        }
        self._cat_badges = {
            "FLOW": ("LÓGICA", QColor(59, 130, 246)),
            "STRUCT": ("FUNCIONES", QColor(251, 191, 36)),
            "OPERATORS": ("SÍMBOLOS", QColor(192, 132, 252)),
            "NAV": ("NAVEGACIÓN", QColor(96, 165, 250)),
            "PAUSE": ("REPOSO", QColor(52, 211, 153)),
            "BACK": ("VOLVER", QColor(244, 114, 182)),
            "EDIT": ("EDICIÓN", QColor(129, 140, 248)),
            "AI": ("SUGERENCIAS", QColor(240, 171, 252)),
            "EXIT": ("SALIR", QColor(248, 113, 113)),
            "LANG": ("LENGUAJE", QColor(168, 85, 247)),
            "MODE": ("MODO", QColor(59, 130, 246)),
            "SNIPER": ("SECTOR", QColor(244, 63, 94)),
            "DEFAULT": ("ACCIÓN", QColor(148, 163, 184)),
        }

        # Dynamic reticle: clean center point + thin outer ring + MAR progress arc.
        self._brush_pointer_glow = QBrush(QColor(59, 130, 246, 40))
        self._pen_pointer_ring = QPen(QColor(248, 250, 252, 210), 1.8)
        self._brush_pointer_dot = QBrush(QColor(248, 250, 252, 245))
        self._pen_pointer_progress = QPen(QColor(59, 130, 246), 2.2)
        self._color_progress_cool = QColor(59, 130, 246)
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
        self.theme_color = str(theme_color or "#3b82f6")
        color = QColor(self.theme_color)
        self._pen_card_active = QPen(color, 2.0)
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
        self._right_margin_target = float(target)
        animation.finished.connect(self._on_right_margin_finished)
        self._right_margin_animation = animation
        animation.start()

    def _on_right_margin_finished(self) -> None:
        try:
            self._animated_right_margin = float(self._right_margin_target)
            self._update_header_exit_rect()
            self.update()
        except RuntimeError:
            pass

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
        if getattr(self, "hud_layout_mode", "FULL_GRID") == "RIGHT_DOCK":
            dock_w = max(
                float(getattr(self, "right_dock_min_w", 460.0)),
                min(
                    float(getattr(self, "right_dock_max_w", 500.0)),
                    w * float(getattr(self, "right_dock_ratio", 0.30)),
                ),
            )
            dock_w = min(dock_w, max(120.0, w - 2.0 * self.margin))
            left = max(self.margin, w - self.margin - dock_w)
            right = w - self.margin
        else:
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

    @staticmethod
    def _wrapped_text_height(font: QFont, text: str, width: float) -> int:
        fm = QFontMetrics(font)
        rect = fm.boundingRect(
            QRect(0, 0, max(20, int(width)), 0),
            Qt.TextFlag.TextWordWrap,
            str(text),
        )
        return max(fm.height(), int(rect.height()))

    def _help_modal_layout(self, w: float, h: float) -> Dict[str, Any]:
        """Computes a height that fits every wrapped row inside the modal."""
        card_w = min(1180.0, max(720.0, w - 60.0))
        margin = 24.0
        gap = 14.0
        col_w = max(160.0, (card_w - 2.0 * margin - 2.0 * gap) / 3.0)

        gesture_rows = []
        for title, action, desc in HELP_GESTURES:
            title_h = QFontMetrics(self._font_modal_item_title).height()
            action_h = QFontMetrics(self._font_modal_item_desc).height()
            desc_h = self._wrapped_text_height(self._font_modal_item_desc, desc, col_w - 28.0)
            gesture_rows.append((title, action, desc, title_h, action_h, desc_h,
                                 title_h + action_h + desc_h + 12.0))

        half = (len(HELP_SHORTCUTS) + 1) // 2
        shortcut_cols = [list(HELP_SHORTCUTS[:half]), list(HELP_SHORTCUTS[half:])]
        shortcut_heights = []
        for column in shortcut_cols:
            total = 0.0
            heights = []
            for key, name, desc in column:
                desc_h = self._wrapped_text_height(self._font_modal_item_desc, desc, col_w - 28.0)
                row_h = 16.0 + 16.0 + desc_h + 6.0
                heights.append((key, name, desc, desc_h, row_h))
                total += row_h
            shortcut_heights.append((heights, total))

        content_h = max(
            sum(row[6] for row in gesture_rows),
            max((total for _, total in shortcut_heights), default=0.0),
        )
        card_h = min(max(420.0, h - 24.0), max(440.0, content_h + 190.0))
        card_x = (w - card_w) * 0.5
        card_y = (h - card_h) * 0.5
        card_rect = QRectF(card_x, card_y, card_w, card_h)
        col_y = card_y + 80.0
        col_content_h = max(80.0, card_h - 80.0 - 58.0)
        columns = [
            QRectF(card_x + margin, col_y, col_w, col_content_h),
            QRectF(card_x + margin + col_w + gap, col_y, col_w, col_content_h),
            QRectF(card_x + margin + 2.0 * (col_w + gap), col_y, col_w, col_content_h),
        ]
        return {
            "card": card_rect,
            "columns": columns,
            "gesture_rows": gesture_rows,
            "shortcut_columns": shortcut_heights,
            "col_w": col_w,
        }

    def _update_help_modal_rect(self) -> None:
        """Computes the modal card, its columns and the close-button target."""
        w = float(self.width()) if self.width() > 0 else 1920.0
        h = float(self.height()) if self.height() > 0 else 1080.0
        layout = self._help_modal_layout(w, h)
        card = layout["card"]
        self.help_modal_rect = card
        close_btn_h = 42.0
        button_gap = 12.0
        row_margin = 24.0
        available = max(300.0, card.width() - row_margin * 2.0 - 2.0 * button_gap)
        guide_btn_w = min(280.0, available * 0.36)
        tutorial_btn_w = min(230.0, available * 0.28)
        close_btn_w = max(160.0, available - guide_btn_w - tutorial_btn_w)
        row_y = card.y() + card.height() - close_btn_h - 14.0
        self.help_modal_guide_rect = QRectF(
            card.x() + row_margin, row_y, guide_btn_w, close_btn_h
        )
        self.help_modal_tutorial_rect = QRectF(
            self.help_modal_guide_rect.right() + button_gap, row_y, tutorial_btn_w, close_btn_h
        )
        self.help_modal_close_rect = QRectF(
            self.help_modal_tutorial_rect.right() + button_gap, row_y, close_btn_w, close_btn_h
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
        if getattr(self, "hud_layout_mode", "FULL_GRID") == "RIGHT_DOCK":
            dock_w = max(
                float(getattr(self, "right_dock_min_w", 460.0)),
                min(
                    float(getattr(self, "right_dock_max_w", 500.0)),
                    w * float(getattr(self, "right_dock_ratio", 0.30)),
                ),
            )
            dock_w = min(dock_w, max(120.0, w - 2.0 * self.margin))
            grid_left = max(self.margin, w - self.margin - dock_w)
            right_margin = 0.0
        else:
            right_margin = self._get_effective_right_margin(w)
            grid_left = self._get_grid_left(w, right_margin)
        brand_w = float(QFontMetrics(self._font_header_bold_btn).horizontalAdvance("IDEye"))
        ws_full_w = float(QFontMetrics(self._font_header_left).horizontalAdvance("VS Code")) + 11.0
        layout = HeaderLayout.compute(
            width=w,
            margin=self.margin,
            header_height=self.breadcrumb_height,
            right_margin=right_margin,
            grid_left=grid_left,
            show_last_action=self._should_show_last_action(),
            screen_count=self.screen_count,
            mode_id=self.current_context_mode_id,
            brand_text_width=brand_w,
            ws_full_width=ws_full_w,
        )
        self.header_rect = layout.header
        self._header_logo_rect = layout.logo
        self._header_breadcrumb_rect = layout.breadcrumb
        self._header_status_rect = layout.status
        self.header_exit_rect = layout.exit
        self.header_help_rect = layout.help
        self.header_lang_rect = layout.lang
        self.header_mode_rect = layout.mode
        self._last_action_pill_rect = layout.last_action
        self._sniper_action_pill_rect = layout.sniper_action
        self.header_screen_rect = layout.screen
        self._header_exit_w = layout.exit_w
        self._header_help_w = layout.help_w
        self._header_lang_w = layout.lang_w
        self._header_mode_w = layout.mode_w
        self._header_ws_dot_only = layout.ws_dot_only
        self._header_ws_show = layout.ws_show
        if not self.header_screen_rect.isValid():
            self.hovered_header_screen = False
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
            available = max_right - start_x - 10.0
            if available < 18.0:
                break
            text = fm.elidedText(str(label), Qt.TextElideMode.ElideRight, int(available))
            text_w = fm.horizontalAdvance(text)
            chip_w = float(text_w) + 10.0
            chip_rect = QRectF(start_x, y, chip_w, chip_h)
            painter.setBrush(QColor(255, 255, 255, 12))
            painter.setPen(QPen(QColor(255, 255, 255, 28), 1.0))
            painter.drawRoundedRect(chip_rect, radius, radius)
            painter.setPen(QColor(203, 213, 225))
            painter.drawText(chip_rect, Qt.AlignmentFlag.AlignCenter, text)
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
            if ctx_name != "GENERAL":
                try:
                    dyn_action = get_dynamic_ast_action_for_context(ctx_info, self.current_language, "9")
                    if len(node.items) > 8:
                        items_copy = list(node.items)
                        items_copy[8] = dyn_action
                        node = MenuNode(
                            id=node.id,
                            title=node.title,
                            breadcrumb_label=node.breadcrumb_label,
                            items=items_copy,
                            parent_id=node.parent_id,
                            sticky=node.sticky,
                        )
                except Exception:
                    pass
            if self.macro_manager is not None:
                try:
                    node = self.macro_manager.apply_overrides(node, "coding")
                except Exception:
                    pass
            self._cached_adaptive_node = node
            self._last_ast_eval_time = now
            return node
        return self.menu_tree.get(self.current_node_id, self.menu_tree.get("ROOT"))

    def set_clipboard_manager(self, manager: Optional[Any]) -> None:
        """Connects the Phase 9 clipboard history manager and injector lock."""
        self.clipboard_manager = manager
        if hasattr(self.code_injector, "set_clipboard_history"):
            self.code_injector.set_clipboard_history(manager)
        if manager is not None and hasattr(manager, "history_changed"):
            try:
                manager.history_changed.connect(self.refresh_clipboard_menu)
            except (TypeError, RuntimeError):
                pass
        self.refresh_clipboard_menu()

    def refresh_clipboard_menu(self) -> None:
        if self.clipboard_manager is None:
            return
        node = self.menu_tree.get("CLIPBOARD_HISTORY")
        parent_id = node.parent_id if node is not None and node.parent_id else "ROOT"
        try:
            self.menu_tree["CLIPBOARD_HISTORY"] = (
                self.clipboard_manager.get_clipboard_menu_node(parent_id=parent_id)
            )
            if self.current_node_id == "CLIPBOARD_HISTORY":
                self.update()
        except Exception as exc:
            logger.warning("Could not refresh clipboard menu: %s", exc)

    def open_clipboard_history(self) -> bool:
        if self.clipboard_manager is None:
            return False
        current = self.current_node_id if self.current_node_id != "CLIPBOARD_HISTORY" else "ROOT"
        try:
            self.menu_tree["CLIPBOARD_HISTORY"] = (
                self.clipboard_manager.get_clipboard_menu_node(parent_id=current)
            )
        except Exception as exc:
            logger.warning("Could not open clipboard history: %s", exc)
            return False
        return self.navigate_to("CLIPBOARD_HISTORY")

    def set_screen_info(self, index: int, count: int) -> None:
        """Updates the compact multi-monitor selector in the command bar."""
        self.screen_count = max(1, int(count))
        self.screen_index = max(0, min(int(index), self.screen_count - 1))
        self._update_header_exit_rect()
        self.update()

    def set_macro_manager(self, manager: Optional[Any]) -> None:
        self.macro_manager = manager
        self._apply_macro_overrides()
        self.update()

    def _apply_macro_overrides(self) -> None:
        if self.macro_manager is None:
            return
        mode_id = getattr(self, "current_context_mode_id", "coding")
        try:
            if "ROOT" in self.menu_tree:
                self.menu_tree["ROOT"] = self.macro_manager.apply_overrides(
                    self.menu_tree["ROOT"], mode_id
                )
            if "MENU_STANDARD" in self.menu_tree:
                self.menu_tree["MENU_STANDARD"] = self.macro_manager.apply_overrides(
                    self.menu_tree["MENU_STANDARD"], mode_id
                )
        except Exception as exc:
            logger.warning(f"[Overlay] Warning: could not apply custom macros: {exc}")
        self._cached_adaptive_node = None
        self._last_ast_eval_time = 0.0

    def refresh_custom_macros(self, mode_id: Optional[str] = None) -> None:
        """Re-applies custom macros after the editor saves."""
        if mode_id is not None and str(mode_id).lower() != str(
            getattr(self, "current_context_mode_id", "coding")
        ).lower():
            return
        self._apply_macro_overrides()
        self.update()

    @pyqtSlot(str)
    def on_file_linked(self, file_path: str) -> None:
        """Called when a user explicitly links a Python script."""
        self._cached_adaptive_node = None
        self._last_ast_eval_time = 0.0
        if self.context_reader:
            self.context_reader.set_active_file(file_path)
            self.last_action_desc = f"Vinculado: {os.path.basename(file_path)}"
            self.update()

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
            old_worker = self.ai_predictor_worker
            try:
                old_worker.predictions_ready.disconnect()
                old_worker.status_changed.disconnect()
                old_worker.prediction_failed.disconnect()
                old_worker.finished.disconnect()
            except Exception:
                pass
            try:
                old_worker.wait(250)
                old_worker.deleteLater()
            except Exception:
                pass
            self.ai_predictor_worker = None

        loading_preds = [
            "Analizando...",
            "Analizando...",
            "Analizando...",
            "Analizando...",
            "Analizando...",
            "Analizando...",
        ]
        if self.menu_tree and "SNIPPETS" in self.menu_tree:
            self.menu_tree["SNIPPETS"].items = populate_ai_prediction_items(loading_preds, parent_id="ROOT")
        self.is_ai_predicting = True
        self.last_action_desc = "Buscando sugerencias..."
        self.ai_status_updated.emit("Buscando sugerencias...")
        self.update()

        editor_ctx = self.context_reader.get_editor_context() if self.context_reader else {}
        pref = editor_ctx.get("prefix_lines") or []
        curr = editor_ctx.get("current_line") or ""
        live_context = ""
        if pref or curr:
            combo = list(pref[-30:])
            if curr:
                combo.append(curr)
            live_context = "\n".join(combo)
        live_symbols = editor_ctx.get("local_symbols") or []

        self.ai_predictor_worker = AIPredictorWorker(
            context_text=live_context,
            local_symbols=live_symbols,
            provider=getattr(config, "LLM_PROVIDER", "ollama"),
            endpoint=getattr(config, "LLM_ENDPOINT", "http://localhost:11434/api/generate"),
            model=getattr(config, "LLM_MODEL", "codellama"),
            timeout=getattr(config, "LLM_TIMEOUT_SEC", 2.5),
            api_key=getattr(config, "LLM_API_KEY", ""),
            temperature=getattr(config, "LLM_TEMPERATURE", 0.2),
            context_reader=self.context_reader,
            document_context=bool(getattr(self.context_reader, "document_context_active", False)),
            document_title=str(getattr(getattr(self.context_reader, "document_buffer", None), "title", "")),
            parent=self,
        )
        self.ai_predictor_worker.predictions_ready.connect(self._on_ai_predictions_ready)
        self.ai_predictor_worker.status_changed.connect(self._on_ai_status_changed)
        self.ai_predictor_worker.prediction_failed.connect(self._on_ai_prediction_failed)
        self.ai_predictor_worker.finished.connect(self._on_ai_worker_finished)
        self.ai_predictor_worker.start()

    @pyqtSlot(list)
    def _on_ai_predictions_ready(self, predictions: List[str]) -> None:
        """Called when AIPredictorWorker finishes with 6 suggestions."""
        if self.menu_tree and "SNIPPETS" in self.menu_tree:
            self.menu_tree["SNIPPETS"].items = populate_ai_prediction_items(predictions, parent_id="ROOT")
        self.diagnostics_fixer.set_ai_suggestions(predictions)
        if self._active_diagnostics:
            self.set_diagnostics(self._active_diagnostics)
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
            if node_id in ("SNIPPETS", "AI_PREDICT"):
                self._trigger_ai_prediction()
            self._dwell_start_time = time.time()
            self._dwell_progress = 0.0
            self._dwell_fired = False
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
        try:
            gx = float(gx)
            gy = float(gy)
        except (TypeError, ValueError, OverflowError):
            return
        if not (math.isfinite(gx) and math.isfinite(gy)):
            return
        self.current_gaze = (gx, gy)
        self._apply_gaze_scroll(gy)

        # FreeLook: header remains interactive; the rest of the screen moves
        # the real OS cursor directly and hides the 3x3 grid.
        if (
            self.current_context_mode_id == "sniper"
            and self.current_node_id != "MODE_SELECT"
            and not self.show_help_modal
            and not self.reading_mode
        ):
            screen_w, screen_h = self._get_screen_size()
            mx, my = self._freelook_screen_coords(gx, gy, screen_w, screen_h)
            px = mx * (max(1.0, float(self.width())) / max(1.0, float(screen_w)))
            py = my * (max(1.0, float(self.height())) / max(1.0, float(screen_h)))
            header_targets = (
                ("hovered_header_exit", self.header_exit_rect),
                ("hovered_header_help", self.header_help_rect),
                ("hovered_header_mode", self.header_mode_rect),
                ("hovered_header_lang", self.header_lang_rect),
                ("hovered_header_screen", self.header_screen_rect),
                ("hovered_sniper_action", self._sniper_action_pill_rect),
                ("hovered_gaming_toggle", self._gaming_toggle_rect),
            )
            active_target = next(
                (attr for attr, _ in header_targets if getattr(self, attr, False)),
                None,
            )
            for attr, rect in header_targets:
                if not rect.isValid():
                    continue
                pad = 24.0 if attr == active_target else 15.0
                if rect.adjusted(-pad, -pad, pad, pad).contains(px, py):
                    for other, _ in header_targets:
                        setattr(self, other, other == attr)
                    self.hovered_block = None
                    self._wake_ghost_peek()
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

        # If cheat sheet modal is open, hit test its buttons (Guide, Tutorial, Close)
        if self.show_help_modal:
            guide_hit = (
                self.help_modal_guide_rect.isValid()
                and self.help_modal_guide_rect.adjusted(-12.0, -12.0, 12.0, 12.0).contains(px, py)
            )
            tutorial_hit = (
                hasattr(self, "help_modal_tutorial_rect")
                and self.help_modal_tutorial_rect.isValid()
                and self.help_modal_tutorial_rect.adjusted(-12.0, -12.0, 12.0, 12.0).contains(px, py)
            )
            close_hit = (
                self.help_modal_close_rect.isValid()
                and self.help_modal_close_rect.adjusted(-12.0, -12.0, 12.0, 12.0).contains(px, py)
            )
            self.hovered_help_modal_guide = bool(guide_hit)
            self.hovered_help_modal_tutorial = bool(tutorial_hit and not guide_hit)
            self.hovered_help_modal_close = bool(close_hit and not guide_hit and not tutorial_hit)
            self.hovered_header_exit = False
            self.hovered_header_help = False
            self.hovered_block = None
            if guide_hit or tutorial_hit or close_hit:
                self._wake_ghost_peek()
            self.update()
            return

        self.hovered_help_modal_close = False
        self.hovered_help_modal_tutorial = False

        # Check if gaze is targeting the prominent header exit button (+15px buffer)
        if not self.reading_mode and self.header_exit_rect.isValid():
            expanded_exit_rect = self.header_exit_rect.adjusted(-15.0, -15.0, 15.0, 15.0)
            if expanded_exit_rect.contains(px, py):
                self.hovered_header_exit = True
                self.hovered_header_help = False
                self.hovered_block = None
                self._wake_ghost_peek()
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
                self._wake_ghost_peek()
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
                self._wake_ghost_peek()
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
                self._wake_ghost_peek()
                self.update()
                return

        self.hovered_header_lang = False

        # Multi-monitor selector pill (between language and help).
        if (
            not self.reading_mode
            and self.header_screen_rect.isValid()
            and self.header_screen_rect.adjusted(-12.0, -12.0, 12.0, 12.0).contains(px, py)
        ):
            self.hovered_header_screen = True
            self.hovered_block = None
            self._wake_ghost_peek()
            self.update()
            return
        self.hovered_header_screen = False

        # Sniper action selector pill (between language and help).
        if (
            self.current_context_mode_id == "sniper"
            and self._sniper_action_pill_rect.isValid()
            and self._sniper_action_pill_rect.adjusted(-10.0, -10.0, 10.0, 10.0).contains(px, py)
        ):
            self.hovered_sniper_action = True
            self.hovered_block = None
            self._wake_ghost_peek()
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
            if getattr(self, "hud_layout_mode", "FULL_GRID") == "RIGHT_DOCK":
                w = float(self.width()) if self.width() > 0 else 1920.0
                dock_w = max(
                    float(getattr(self, "right_dock_min_w", 460.0)),
                    min(
                        float(getattr(self, "right_dock_max_w", 500.0)),
                        w * float(getattr(self, "right_dock_ratio", 0.30)),
                    ),
                )
                dock_w = min(dock_w, max(120.0, w - 2.0 * self.margin))
                dock_left = max(self.margin, w - self.margin - dock_w)
                if px < dock_left - 15.0:
                    self.hovered_block = None
                    self._dwell_block = None
                    self._dwell_progress = 0.0
                    self._dwell_fired = False
                    if getattr(self, "show_tutorial_modal", False):
                        self._update_mini_tutorial_gaze(gx, gy)
                    self.update()
                    return
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

        # Wake ghost mode instantly when interacting with HUD
        if self.hovered_block is not None:
            self._wake_ghost_peek()

        # Update adaptive dwell engine
        self._update_adaptive_dwell(self.hovered_block)

        # Update mini-tutorial gaze
        if getattr(self, "show_tutorial_modal", False):
            self._update_mini_tutorial_gaze(gx, gy)

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
        # Block 5 (index 4) has an expanded magnetic capture zone for safe rest
        if block_idx == 4:
            if not (0.10 <= rel_x <= 0.90 and 0.10 <= rel_y <= 0.90):
                self._gravity_since = now
                return gx, gy
            strength = float(getattr(config, "CELL_MAGNETISM_STRENGTH", 0.15)) * 1.8
        else:
            if not (0.18 <= rel_x <= 0.82 and 0.18 <= rel_y <= 0.82):
                self._gravity_since = now
                return gx, gy
            strength = float(getattr(config, "CELL_MAGNETISM_STRENGTH", 0.15))
        center = rect.center()
        cx = center.x() / max(1.0, self.width())
        cy = center.y() / max(1.0, self.height())
        return gx + (cx - gx) * strength, gy + (cy - gy) * strength

    def _clear_header_exit_flash(self) -> None:
        self.active_click_header_exit = False
        self.update()

    def _disarm_exit(self) -> None:
        """Clears the two-click exit arm after the confirmation window expires."""
        if time.time() < self._exit_armed_until:
            return
        self._exit_armed_until = 0.0
        if self.last_action_desc.startswith("SALIR:"):
            self.last_action_desc = "Listo"
        self.update()

    def release_freelook_controls(self) -> None:
        """Releases any FreeLook mouse/key hold before pausing or shutting down."""
        controller = self.mouse_controller
        try:
            if controller is not None and getattr(self, "_gaming_right_held", False):
                controller.mouse_up("right")
            if controller is not None and getattr(self, "_hold_started", False):
                if getattr(self, "_gaming_mode", False):
                    controller.key_up("w")
                else:
                    controller.mouse_up("left")
        except Exception:
            pass
        self._gaming_right_held = False
        self._hold_started = False
        self._mouth_active = False
        self._jaw_locked = False
        self._jaw_lock_pos = None
        self._reset_freelook_edge_scroll()
        self.release_all_game_keys()

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
        self._mar_rest_window.clear()
        self._mar_rest_baseline = max(
            0.15,
            min(
                0.60,
                max(
                    float(getattr(config, "MAR_REST_THRESHOLD", 0.20)),
                    self.mar_threshold - 0.18,
                ),
            ),
        )
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
        self.release_freelook_controls()
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
            painter.setBrush(QColor(244, 63, 94, 45) if selected else QColor(10, 15, 29, 45))
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
        painter.setBrush(QColor(10, 15, 29, 235))
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
    def _reset_freelook_edge_scroll(self) -> None:
        self._edge_scroll_direction = 0
        self._edge_scroll_since = 0.0
        self._edge_scroll_last = 0.0

    def _update_strategy_edge_scroll(self, gx: float, gy: float, now: Optional[float] = None) -> bool:
        """Pan the cursor/camera near the 20 px screen borders in strategy profiles."""
        if self._game_profile_name != "strategy_rpg" or not self._gaming_mode:
            return False
        sw, sh = self._get_screen_size()
        x, y = self._freelook_screen_coords(gx, gy, sw, sh)
        margin = 20
        dx = -8 if x <= margin else 8 if x >= sw - margin else 0
        dy = -8 if y <= margin else 8 if y >= sh - margin else 0
        if dx == 0 and dy == 0:
            self._edge_scroll_last = 0.0
            return False
        timestamp = time.time() if now is None else float(now)
        if timestamp - self._edge_scroll_last < 0.08:
            return True
        controller = self.mouse_controller
        if controller is None:
            return False
        px, py = self._freelook_last_pos
        nx = max(0, min(sw - 1, px + dx))
        ny = max(0, min(sh - 1, py + dy))
        try:
            controller.move_direct(nx, ny)
            self._freelook_last_pos = (nx, ny)
        except Exception:
            pass
        self._edge_scroll_last = timestamp
        self.last_action_desc = "Edge-Scroll activo"
        return True

    def _update_freelook_edge_scroll(self, gy: float, now: Optional[float] = None) -> int:
        """Scroll while the gaze rests near the top/bottom edge in desktop FreeLook."""
        if (
            (self._gaming_mode and self._game_profile_name != "strategy_rpg")
            or self._jaw_locked
            or not bool(getattr(config, "FREELOOK_EDGE_SCROLL_ENABLED", True))
        ):
            self._reset_freelook_edge_scroll()
            return 0
        zone = max(0.02, min(0.20, float(getattr(config, "FREELOOK_EDGE_SCROLL_ZONE", 0.075))))
        if gy <= zone:
            direction = 1
        elif gy >= 1.0 - zone:
            direction = -1
        else:
            self._reset_freelook_edge_scroll()
            return 0

        timestamp = time.time() if now is None else float(now)
        if direction != self._edge_scroll_direction:
            self._edge_scroll_direction = direction
            self._edge_scroll_since = timestamp
            self._edge_scroll_last = 0.0
            return 0

        delay = max(0.05, float(getattr(config, "FREELOOK_EDGE_SCROLL_DELAY_SEC", 0.30)))
        interval = max(0.04, float(getattr(config, "FREELOOK_EDGE_SCROLL_INTERVAL_SEC", 0.11)))
        if timestamp - self._edge_scroll_since < delay:
            return 0
        if self._edge_scroll_last and timestamp - self._edge_scroll_last < interval:
            return 0

        controller = self.mouse_controller
        if controller is None:
            controller = OSMouseController()
            self.mouse_controller = controller
        step = max(1, int(getattr(config, "FREELOOK_EDGE_SCROLL_STEP", 3)))
        try:
            controller.scroll(direction * step)
        except Exception:
            pass
        self._edge_scroll_last = timestamp
        self.last_action_desc = "Scroll \u2191" if direction > 0 else "Scroll \u2193"
        return direction

    def _freelook_prethreshold(self) -> float:
        return max(0.01, float(getattr(self, "mar_threshold", 0.45)) * 0.55)

    def _freelook_jaw_threshold(self) -> float:
        """Mouth opening that freezes the pointer before a click.

        The old 55% threshold was close to a relaxed mouth for many users,
        which made the cursor stop and swallowed intentional clicks.
        """
        rest = max(
            float(getattr(config, "MAR_REST_THRESHOLD", 0.20)),
            float(getattr(self, "_mar_rest_baseline", 0.20)),
        )
        minimum = float(getattr(config, "FREELOOK_JAW_LOCK_MIN_MAR", 0.27))
        return max(self._freelook_prethreshold(), rest + 0.08, minimum)

    def set_mar_threshold(self, value: float, calibrated: Optional[bool] = None) -> None:
        """Keeps FreeLook click thresholds aligned with calibration/settings."""
        try:
            mar = max(0.10, min(0.90, float(value)))
        except (TypeError, ValueError, OverflowError):
            return
        self.mar_threshold = mar
        if calibrated is not None:
            self.mar_calibrated = bool(calibrated)
        self._mar_rest_window.clear()
        self._mar_rest_baseline = max(
            0.15,
            min(
                0.60,
                max(
                    float(getattr(config, "MAR_REST_THRESHOLD", 0.20)),
                    mar - 0.18,
                ),
            ),
        )

    def _freelook_screen_coords(
        self, gx: float, gy: float, screen_w: int, screen_h: int
    ) -> Tuple[int, int]:
        """Maps normalized gaze to the full physical screen with edge overscan.

        The grid still lives inside availableGeometry; only FreeLook uses the
        full geometry so the taskbar, tray and maximized-window close button
        remain reachable.
        """
        try:
            gx = float(gx)
            gy = float(gy)
        except (TypeError, ValueError, OverflowError):
            return (0, 0)
        if not (math.isfinite(gx) and math.isfinite(gy)):
            return (0, 0)
        margin_x = max(0.0, min(0.20, float(getattr(config, "OVERSCAN_MARGIN_X", 0.04))))
        margin_top = max(0.0, min(0.20, float(getattr(config, "OVERSCAN_MARGIN_Y_TOP", 0.04))))
        margin_bottom = max(0.0, min(0.25, float(getattr(config, "OVERSCAN_MARGIN_Y_BOTTOM", 0.07))))
        span_x = max(1e-6, 1.0 - 2.0 * margin_x)
        span_y = max(1e-6, 1.0 - margin_top - margin_bottom)
        nx = max(0.0, min(1.0, (float(gx) - margin_x) / span_x))
        ny = max(0.0, min(1.0, (float(gy) - margin_top) / span_y))
        x = int(round(nx * max(0, screen_w - 1)))
        y = int(round(ny * max(0, screen_h - 1)))

        # Top magnet: comfortable upward gaze rarely reaches the extreme top
        # of the screen. Pull the cursor into the command bar before applying
        # the taskbar rail so the header, mode selector and exit stay usable.
        top_zone = max(0.0, min(0.35, float(getattr(config, "FREELOOK_TOP_MAGNET_ZONE", 0.18))))
        top_pull = max(0.0, min(1.0, float(getattr(config, "FREELOOK_TOP_MAGNET_PULL", 0.94))))
        gaze_y = max(0.0, min(1.0, float(gy)))
        if top_zone > 0.0 and gaze_y < top_zone:
            strength = max(0.0, 1.0 - (gaze_y / top_zone))
            y = int(round(y * (1.0 - top_pull * strength)))

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
        if self._gaming_mode and self._gaming_control_state == "JOYSTICK":
            self._update_gameplay_joystick(gx, gy)
            return
        screen_w, screen_h = self._get_screen_size()
        x, y = self._freelook_screen_coords(gx, gy, screen_w, screen_h)
        pre = self._freelook_prethreshold()
        jaw_threshold = self._freelook_jaw_threshold()
        now = time.time()
        max_lock = max(0.5, float(getattr(config, "FREELOOK_JAW_LOCK_MAX_SEC", 2.0)))

        if self._jaw_locked and self._jaw_lock_since > 0.0 and now - self._jaw_lock_since > max_lock:
            # Safety watchdog: a stuck jaw-lock must never leave the pointer
            # frozen at a corner indefinitely.
            self._jaw_locked = False
            self._jaw_lock_pos = None
            self._jaw_lock_since = 0.0
            self._mouth_active = False

        if self.current_mar >= jaw_threshold:
            if not self._jaw_locked:
                self._jaw_locked = True
                self._jaw_lock_pos = self._freelook_last_pos
                self._jaw_lock_since = now
            if self._jaw_lock_pos is not None:
                x, y = self._jaw_lock_pos
        else:
            self._jaw_locked = False
            self._jaw_lock_pos = None
            self._jaw_lock_since = 0.0
            self._freelook_last_pos = (x, y)
            controller = self.mouse_controller
            if controller is not None:
                try:
                    controller.move_direct(x, y)
                except Exception:
                    pass

        self.sniper_lens.update_gaze(x, y)
        if self.sniper_lens.active:
            px, py = self._freelook_last_pos
            x = int(round(px + (x - px) * self.sniper_lens.movement_multiplier))
            y = int(round(py + (y - py) * self.sniper_lens.movement_multiplier))
            self._capture_sniper_lens()
        self._update_strategy_edge_scroll(gx, gy)
        self._update_freelook_edge_scroll(gy)
        normalized = (x / float(screen_w), y / float(screen_h))
        if normalized != self.current_gaze:
            self.current_gaze = normalized
            self.update()

    def _update_gameplay_joystick(self, gx: float, gy: float) -> None:
        """Maps head position to WASD with a comfortable central deadzone."""
        dx = float(gx) - 0.5
        dy = float(gy) - 0.5
        deadzone = float(getattr(config, "GAMING_DEADZONE", 0.14))
        desired = set()
        if dy < -deadzone:
            desired.add("w")
        elif dy > deadzone:
            desired.add("s")
        if dx < -deadzone:
            desired.add("a")
        elif dx > deadzone:
            desired.add("d")

        controller = self.mouse_controller
        if controller is None:
            controller = OSMouseController()
            self.mouse_controller = controller
        had_keys = bool(self._game_keys_down)
        for key in ("w", "a", "s", "d"):
            if key in desired and key not in self._game_keys_down:
                try:
                    controller.key_down(key)
                except Exception:
                    pass
                self._game_keys_down.add(key)
            elif key not in desired and key in self._game_keys_down:
                try:
                    controller.key_up(key)
                except Exception:
                    pass
                self._game_keys_down.discard(key)
        if had_keys and not desired:
            self.release_all_game_keys()
        mode = self._sniper_mode()
        if mode is not None and getattr(mode, "is_twin_stick", False):
            sw, sh = self._get_screen_size()
            tx, ty = self._freelook_screen_coords(gx, gy, sw, sh)
            try:
                controller.move_direct(tx, ty)
                self._freelook_last_pos = (tx, ty)
            except Exception:
                pass
        self.current_gaze = (float(gx), float(gy))
        self.update()

    def release_all_game_keys(self) -> None:
        """Guarantees that movement keys and mouse buttons are released."""
        controller = self.mouse_controller
        if controller is not None:
            try:
                controller.release_all_game_keys(tuple(self._game_keys_down) + ("w", "a", "s", "d", " "))
            except Exception:
                pass
            try:
                controller.release_all_buttons()
            except Exception:
                pass
        self._game_keys_down.clear()
        self._gaming_right_held = False
        self._hold_started = False
        self._jaw_locked = False
        self._jaw_lock_pos = None
        self._jaw_lock_since = 0.0
        self._mouth_active = False
        try:
            self.gaze_scroller.stop()
        except Exception:
            pass
        if getattr(self, "_gaze_scroll_enabled", False):
            self._gaze_scroll_enabled = False
            try:
                self.gaze_scroll_toggled.emit(False)
            except Exception:
                pass

    def reset_freelook_pointer(self) -> None:
        """Centers FreeLook and clears any frozen pointer state after face loss."""
        if self.current_context_mode_id != "sniper":
            return
        self.release_all_game_keys()
        sw, sh = self._get_screen_size()
        center = (max(0, sw // 2), max(0, sh // 2))
        self._freelook_last_pos = center
        self.current_gaze = (0.5, 0.5)
        controller = self.mouse_controller
        if controller is not None:
            try:
                controller.move_direct(*center)
            except Exception:
                pass
        self.update()

    def _freelook_click(self) -> None:
        now = time.time()
        if now - float(getattr(self, "_last_freelook_click_ts", 0.0)) < 0.12:
            return
        self._last_freelook_click_ts = now
        mode = self._sniper_mode()
        action = getattr(mode, "get_action", lambda: "LEFT_CLICK")() if mode else "LEFT_CLICK"
        x, y = self._jaw_lock_pos or self._freelook_last_pos
        controller = self.mouse_controller
        if controller is None:
            controller = OSMouseController()
            self.mouse_controller = controller
        if action == "RIGHT_CLICK":
            try:
                controller.right_click(x, y)
            except Exception:
                pass
        elif action == "DOUBLE_CLICK":
            try:
                controller.double_click(x, y)
            except Exception:
                pass
        elif action == "SCROLL_UP":
            try:
                controller.scroll_at(x, y, 3)
            except Exception:
                pass
        elif action == "SCROLL_DOWN":
            try:
                controller.scroll_at(x, y, -3)
            except Exception:
                pass
        else:
            try:
                controller.left_click(x, y)
            except Exception:
                pass
        self._play_sound("click")
        self.last_action_desc = f"FreeLook: {getattr(mode, 'action_label', 'Clic Izq')}"
        self.sniper_lens.deactivate()
        if (
            self._gaming_mode
            and self._gaming_control_state == "MENU_CURSOR"
            and getattr(config, "GAMING_AUTO_RETURN_AFTER_CLICK", False)
        ):
            self._gaming_control_state = "JOYSTICK"
            self.release_all_game_keys()

    def _update_freelook_mouth(self, mar: float) -> None:
        pre = self._freelook_prethreshold()
        threshold = float(getattr(self, "mar_threshold", 0.45))
        baseline = max(
            float(getattr(config, "MAR_REST_THRESHOLD", 0.20)),
            float(getattr(self, "_mar_rest_baseline", 0.20)),
        )
        trigger_ratio = max(0.35, min(0.95, float(getattr(config, "FREELOOK_MOUTH_TRIGGER_RATIO", 0.78))))
        release_ratio = max(0.25, min(0.90, float(getattr(config, "FREELOOK_MOUTH_RELEASE_RATIO", 0.48))))
        trigger = max(pre + 0.01, threshold * trigger_ratio, baseline + 0.08)
        release = max(pre, threshold * release_ratio, baseline + 0.035)
        release = min(trigger - 0.01, release)
        now = time.time()

        # In gameplay, mouth = click at the current pointer; never move it.
        if self._gaming_mode and self._gaming_control_state == "JOYSTICK":
            controller = self.mouse_controller
            if mar >= trigger and not self._mouth_active:
                self._mouth_active = True
                self._mouth_start = now
                self.update()
                return
            if self._mouth_active and mar < release:
                self._mouth_active = False
                self._hold_started = False
                if controller is not None:
                    try:
                        controller.left_click_current()
                    except Exception:
                        pass
                self._play_sound("click")
                self.last_action_desc = "Gaming: clic"
                self.update()
            return

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

        if mar < release:
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

    def set_game_profile(self, profile_name: str) -> None:
        """Applies a dynamic game/application profile without restarting."""
        labels = {
            "sandbox_3d": "Sandbox 3D",
            "twin_stick_roguelike": "Twin-Stick",
            "strategy_rpg": "Estrategia / RPG",
            "default_desktop": "Escritorio",
        }
        name = str(profile_name or "default_desktop")
        self._game_profile_name = name
        self._game_profile_label = labels.get(name, name)
        mode = self._sniper_mode()
        if mode is not None and hasattr(mode, "set_game_profile"):
            mode.set_game_profile(name)
        self.set_gaming_profile(name != "default_desktop")
        if name == "strategy_rpg":
            self._gaming_control_state = "MENU_CURSOR"
        self.last_action_desc = f"Perfil: {self._game_profile_label}"
        self.update()

    def set_gaming_profile(self, enabled: bool) -> None:
        """Applies the watcher's gaming/desktop FreeLook sub-profile."""
        enabled = bool(enabled)
        if enabled == self._gaming_mode:
            return
        if self._gaming_mode:
            self.release_freelook_controls()
        self._gaming_mode = enabled
        self._gaming_control_state = "JOYSTICK"
        self._game_keys_down.clear()
        self.last_action_desc = f"FreeLook: {'GAMING' if enabled else 'ESCRITORIO'}"
        self.update()

    def toggle_gaming_mode(self) -> bool:
        if self._gaming_mode:
            self.release_freelook_controls()
        self._gaming_mode = not self._gaming_mode
        self._gaming_control_state = "JOYSTICK"
        self._game_keys_down.clear()
        self.last_action_desc = f"FreeLook: {'GAMING' if self._gaming_mode else 'ESCRITORIO'}"
        self._play_sound("mode")
        self.update()
        return self._gaming_mode

    def _toggle_gaming_right(self) -> None:
        """Right wink switches between head-joystick and menu cursor."""
        if not self._gaming_mode:
            return
        if self._gaming_control_state == "JOYSTICK":
            self.release_all_game_keys()
            self._gaming_control_state = "MENU_CURSOR"
            self.last_action_desc = "Gaming: Cursor de menú"
        else:
            self._gaming_control_state = "JOYSTICK"
            self.release_all_game_keys()
            self.last_action_desc = "Gaming: Joystick de cabeza"
        self._play_sound("mode")
        self.update()

    def _capture_sniper_lens(self) -> None:
        if not self.sniper_lens.active or self.sniper_lens.target is None:
            return
        target = self.sniper_lens.target
        if self._lens_capture_target is not None:
            if ((target[0] - self._lens_capture_target[0]) ** 2 + (target[1] - self._lens_capture_target[1]) ** 2) < 225:
                return
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        self._lens_capture_in_progress = True
        try:
            # Do not touch window opacity: hiding the whole HUD caused the
            # command bar to flash on every lens refresh.
            QApplication.processEvents()
            self._lens_pixmap = screen.grabWindow(0, int(target[0]) - 40, int(target[1]) - 40, 80, 80)
            self._lens_capture_target = (target[0], target[1])
        except Exception:
            pass
        finally:
            self._lens_capture_in_progress = False

    def activate_sniper_lens(self) -> None:
        if self.current_context_mode_id != "sniper":
            return
        target = self._freelook_last_pos
        self.sniper_lens.activate(float(target[0]), float(target[1]))
        self._capture_sniper_lens()
        self.last_action_desc = "Lupa Sniper: ON"
        self.update()

    def toggle_sniper_lens(self) -> None:
        if self.current_context_mode_id != "sniper":
            return
        target = self._freelook_last_pos
        active = self.sniper_lens.toggle(float(target[0]), float(target[1]))
        self.last_action_desc = "Lupa Sniper: ON" if active else "Lupa Sniper: OFF"
        if active:
            self._capture_sniper_lens()
        self.update()

    def _paint_sniper_lens(self, painter: QPainter) -> None:
        if not self.sniper_lens.active or self.sniper_lens.target is None:
            return
        tx, ty = self.sniper_lens.target
        cx = tx - float(self.x())
        cy = ty - float(self.y())
        radius = 110.0
        center = QPointF(cx, cy)
        painter.save()
        path = QPainterPath()
        path.addEllipse(center, radius, radius)
        painter.setClipPath(path)
        if self._lens_pixmap is not None and not self._lens_pixmap.isNull():
            size = 80.0 * self.sniper_lens.zoom
            painter.drawPixmap(QRectF(cx - size / 2, cy - size / 2, size, size), self._lens_pixmap, QRectF(self._lens_pixmap.rect()))
        painter.setClipping(False)

        # Outer cyber sapphire precision ring
        painter.setBrush(QColor(10, 15, 29, 30))
        painter.setPen(QPen(QColor(59, 130, 246, 230), 2.5))
        painter.drawEllipse(center, radius, radius)

        # Concentric inner ring with cyan aperture ticks
        inner_r = radius - 10.0
        painter.setPen(QPen(QColor(96, 165, 250, 140), 1.0, Qt.PenStyle.DashLine))
        painter.drawEllipse(center, inner_r, inner_r)

        # Precision crosshairs with center aperture clearance
        painter.setPen(QPen(QColor(96, 165, 250, 200), 1.2))
        painter.drawLine(QPointF(cx - radius + 4.0, cy), QPointF(cx - 10.0, cy))
        painter.drawLine(QPointF(cx + 10.0, cy), QPointF(cx + radius - 4.0, cy))
        painter.drawLine(QPointF(cx, cy - radius + 4.0), QPointF(cx, cy - 10.0))
        painter.drawLine(QPointF(cx, cy + 10.0), QPointF(cx, cy + radius - 4.0))

        # Center sub-pixel aperture target
        painter.setPen(QPen(QColor(248, 250, 252, 230), 1.0))
        painter.drawLine(QPointF(cx - 5.0, cy), QPointF(cx + 5.0, cy))
        painter.drawLine(QPointF(cx, cy - 5.0), QPointF(cx, cy + 5.0))
        painter.setBrush(QBrush(QColor(59, 130, 246)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(center, 2.0, 2.0)
        painter.restore()

    def _paint_freelook_overlay(self, painter: QPainter) -> None:
        """Draws the compact FreeLook status, gaming crosshair and mode switch."""
        mode = self._sniper_mode()
        action = getattr(mode, "action_label", "Clic Izq") if mode else "Clic Izq"
        painter.save()
        if not self._gaming_mode:
            self._gaming_toggle_rect = QRectF()
            self.hovered_gaming_toggle = False
            profile = "ESCRITORIO"
            text = f"FREELOOK → {profile} → {action}"
            hint = "Mira al borde superior o inferior para hacer scroll"
            fm = QFontMetrics(self._font_freelook_hint)
            width = min(520.0, max(260.0, max(fm.horizontalAdvance(text), fm.horizontalAdvance(hint)) + 30.0))
            rect = QRectF(
                self.width() * 0.5 - width * 0.5,
                self.header_rect.bottom() + 8.0,
                width,
                44.0,
            )
            painter.setBrush(QColor(10, 15, 29, 225))
            painter.setPen(QPen(QColor(244, 63, 94, 180), 1.0))
            painter.drawRoundedRect(rect, 8.0, 8.0)
            painter.setPen(QColor(254, 205, 211))
            painter.setFont(self._font_freelook_hint)
            painter.drawText(rect.adjusted(0.0, 5.0, 0.0, -20.0), Qt.AlignmentFlag.AlignCenter, text)
            painter.setPen(QColor(148, 163, 184))
            painter.drawText(rect.adjusted(0.0, 21.0, 0.0, -4.0), Qt.AlignmentFlag.AlignCenter, hint)
            painter.restore()
            return

        state_label = "JOYSTICK" if self._gaming_control_state == "JOYSTICK" else "CURSOR"
        button_text = f"MODO JUEGO: {state_label} → {'CURSOR' if state_label == 'JOYSTICK' else 'JOYSTICK'}"
        fm = QFontMetrics(self._font_freelook_hint)
        width = min(520.0, max(320.0, fm.horizontalAdvance(button_text) + 34.0))
        self._gaming_toggle_rect = QRectF(
            self.width() * 0.5 - width * 0.5,
            self.header_rect.bottom() + 8.0,
            width,
            30.0,
        )
        hovered = getattr(self, "hovered_gaming_toggle", False)
        painter.setBrush(QColor(16, 185, 129, 55) if hovered else QColor(10, 15, 29, 225))
        painter.setPen(QPen(QColor(52, 211, 153, 230), 1.6))
        painter.drawRoundedRect(self._gaming_toggle_rect, 9.0, 9.0)
        painter.setPen(QColor(209, 250, 229))
        painter.setFont(self._font_freelook_hint)
        painter.drawText(self._gaming_toggle_rect, Qt.AlignmentFlag.AlignCenter, button_text)

        if self._gaming_control_state == "JOYSTICK":
            center = QPointF(self.width() * 0.5, self.height() * 0.5)
            radius = 40.0
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(52, 211, 153, 80), 1.4))
            painter.drawEllipse(center, radius + 8.0, radius + 8.0)
            painter.setPen(QPen(QColor(52, 211, 153, 150), 1.2))
            painter.drawLine(QPointF(center.x() - 12, center.y()), QPointF(center.x() + 12, center.y()))
            painter.drawLine(QPointF(center.x(), center.y() - 12), QPointF(center.x(), center.y() + 12))
            gx, gy = self.current_gaze
            dot = QPointF(
                center.x() + max(-1.0, min(1.0, (gx - 0.5) * 3.0)) * radius,
                center.y() + max(-1.0, min(1.0, (gy - 0.5) * 3.0)) * radius,
            )
            painter.setBrush(QColor(52, 211, 153, 230))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(dot, 6.0, 6.0)
            painter.setPen(QColor(167, 243, 208))
            painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            painter.drawText(
                QRectF(center.x() - 90.0, center.y() + 54.0, 180.0, 18.0),
                Qt.AlignmentFlag.AlignCenter,
                "mueve la cabeza → boca = clic → guiño der = cursor",
            )
        painter.restore()

    def show_health_alert(self, message: str) -> None:
        """Shows a non-intrusive 4-second health reminder in the command bar."""
        self.last_action_desc = str(message)
        self.update()
        QTimer.singleShot(4000, self._clear_health_alert)

    def _clear_health_alert(self) -> None:
        if str(self.last_action_desc).startswith(("Vista fija", "Demasiado cerca")):
            self.last_action_desc = "Listo"
            self.update()

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
        if not math.isfinite(self.current_mar):
            self.current_mar = 0.0
        self._mar_rest_window.append(self.current_mar)
        if len(self._mar_rest_window) >= 20:
            values = sorted(self._mar_rest_window)
            baseline = values[max(0, int(len(values) * 0.10) - 1)]
            self._mar_rest_baseline = max(0.10, min(0.60, float(baseline)))
        mouth_rest = max(0.0, float(getattr(config, "MAR_REST_THRESHOLD", 0.20)))
        if self.current_mar > mouth_rest + 0.04:
            self._wake_ghost_peek()
        if (
            self.current_context_mode_id == "sniper"
            and self.current_node_id != "MODE_SELECT"
            and not self.show_help_modal
            and not self.reading_mode
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
        self._wake_ghost_peek()
        if gesture_name in ("MOUTH_CLICK", "WINK_LEFT", "WINK_RIGHT"):
            self.gaze_scroller.stop()
            if self._gaze_scroll_enabled:
                self._gaze_scroll_enabled = False
                self.gaze_scroll_toggled.emit(False)
        if getattr(self, "show_tutorial_modal", False):
            if self.tutorial_step == 2:
                self.tutorial_step = 3
                self.tutorial_step_progress = 0.0
                self._tutorial_rest_start = time.time()
                self._play_sound("confirm")
                self.update()
                return
            elif self.tutorial_step == 4:
                self.show_tutorial_modal = False
                self.update()
                return

        if self.show_help_modal and gesture_name == "MOUTH_CLICK":
            self.mouth_clicked.emit(self.hovered_block if self.hovered_block is not None else -1)
            open_guide = bool(getattr(self, "hovered_help_modal_guide", False))
            start_tut = bool(getattr(self, "hovered_help_modal_tutorial", False))
            self.show_help_modal = False
            self.hovered_help_modal_guide = False
            self.hovered_help_modal_tutorial = False
            self.hovered_help_modal_close = False
            if open_guide:
                self.last_action_desc = "Abriendo Manual Interactivo"
                self.interactive_guide_requested.emit()
            elif start_tut:
                self.start_mini_tutorial()
            else:
                self.last_action_desc = "Cerrar Ayuda"
            self.update()
            return

        if gesture_name == "BROW_RAISE":
            if self.current_context_mode_id == "sniper":
                if bool(getattr(config, "SNIPER_LENS_BROW_TRIGGER_ENABLED", False)) and (
                    not self._gaming_mode or self._gaming_control_state == "MENU_CURSOR"
                ):
                    self.activate_sniper_lens()
                return
            if self._active_diagnostics and "AUTO_FIX" in self.menu_tree:
                self.navigate_to("AUTO_FIX")
                self.last_action_desc = "Auto-Fix: elige reparaci?n"
            else:
                self._trigger_ai_prediction()
                self.last_action_desc = "Sugerencias de contexto"
            self.update()
            return

        if gesture_name in ("HEAD_TILT_RIGHT", "HEAD_TILT_LEFT"):
            if self.current_context_mode_id in ("coding", "writing", "terminal"):
                key = "TAB" if gesture_name == "HEAD_TILT_RIGHT" else "SHIFT_TAB"
                try:
                    self.code_injector.send_key(key)
                except Exception:
                    pass
                self.last_action_desc = "Indentar" if key == "TAB" else "Des-indentar"
                self._play_sound("click")
                self.update()
            return

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
            if self.sniper_lens.active:
                self.sniper_lens.deactivate()
                self.last_action_desc = "Lupa Sniper: OFF"
                self.update()
                return
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
                self.trigger_undo()
                self.block_activated.emit(0, "ACTION_UNDO")
                return

        if gesture_name != "MOUTH_CLICK":
            return

        self._last_mouth_click_time = time.time()
        self.mouth_clicked.emit(self.hovered_block if self.hovered_block is not None else -1)

        # Dismiss cheat sheet modal if open
        if self.show_help_modal:
            self.show_help_modal = False
            self.last_action_desc = "Cerrar Ayuda"
            self.update()
            return

        self._play_sound("click")

        # Hands-free header exit: first click arms, second click exits.
        if self.hovered_header_exit:
            self.hovered_header_exit = False
            self.active_click_header_exit = True
            QTimer.singleShot(int(config.CLICK_FLASH_DURATION_SEC * 1000), self._clear_header_exit_flash)
            now = time.time()
            if now < self._exit_armed_until:
                self._exit_armed_until = 0.0
                self.last_action_desc = "Saliendo..."
                self.update()
                self.exit_requested.emit()
                return
            arm_sec = float(getattr(config, "EXIT_DOUBLE_CLICK_SEC", 1.5))
            self._exit_armed_until = now + arm_sec
            self.last_action_desc = "SALIR: pulsa otra vez para confirmar"
            QTimer.singleShot(int(arm_sec * 1000), self._disarm_exit)
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

        # Multi-monitor selector
        if getattr(self, "hovered_header_screen", False):
            self.hovered_header_screen = False
            self.screen_cycle_requested.emit()
            return

        # In-game Joystick / Menu-cursor switch.
        if getattr(self, "hovered_gaming_toggle", False):
            self.hovered_gaming_toggle = False
            self._toggle_gaming_right()
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
        # Confirmed MOUTH_CLICK is a fallback when MAR sampling misses a quick
        # opening; duplicate suppression lives in _freelook_click.
        if self.current_context_mode_id == "sniper" and self.current_node_id != "MODE_SELECT":
            if not self.reading_mode and not self._mouth_active and not self._hold_started:
                self._freelook_click()
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
        # Writing mode queues full-word insertions without blocking on each paste.
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

        # 3b. Writing-mode complete words and phrases
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
            detected_lang = self.context_reader.get_active_language() if self.context_reader else "PYTHON"
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
            "WRITING_AI",
        }:
            # Selecting a whole phrase also starts a new word context.
            if self.current_node_id == "WRITING_WORDS" and action_type == "SNIPPET":
                mode = self._writing_mode()
                if mode is not None:
                    mode.reset_prefix()
                    self._refresh_writing_predictions()
            return False

        mode = self._writing_mode()
        if mode is None:
            return False

        if action_type == "WRITING_AI":
            cmd = getattr(item, "snippet", "") or "rephrase"
            self._execute_writing_ai(cmd, item, target_block)
            return True

        if action_type == "WRITING_LETTER":
            text = mode.record_letter(item.snippet or "")
            if text:
                self.code_injector.insert_snippet(text)
                self.text_injected.emit(len(text))
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
                self.text_injected.emit(len(word) + 1)
            mode.reset_prefix()
            self._refresh_writing_predictions()
            self.navigate_to("WRITING_T9")
            self.last_action_desc = f"Palabra: {word}" if word else "Palabra"
            self.action_executed.emit(item.id, self.last_action_desc)
            self.block_activated.emit(target_block, item.id)
            return True

        if action_type == "WRITING_SPACE":
            self.code_injector.insert_snippet(" ")
            self.text_injected.emit(1)
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

    def _execute_writing_ai(self, cmd: str, item: MenuAction, target_block: int = 0) -> None:
        """Executes real AI writing assist (rephrase, correct, summarize, etc.) hands-free."""
        try:
            from ideye.modes.writing_mode import WRITING_AI_PROMPTS, correct_writing_text, rephrase_writing_text
        except ImportError:
            WRITING_AI_PROMPTS = {}
            correct_writing_text = lambda s: s
            rephrase_writing_text = lambda s: s

        target_text = ""
        has_active_selection = False
        if self._vscode_editor_state:
            target_text = str(self._vscode_editor_state.get("selection") or "").strip()
            if target_text:
                has_active_selection = True
        if not target_text and self.context_reader:
            ctx = self.context_reader.get_editor_context()
            target_text = str(ctx.get("active_selection") or "").strip()
            if target_text:
                has_active_selection = True
            elif ctx.get("current_line"):
                target_text = str(ctx.get("current_line") or "").strip()
        if not target_text and self.context_reader:
            target_text = self.context_reader.get_last_line()
        if not target_text:
            mode = self._writing_mode()
            target_text = getattr(mode, "_prefix", "") if mode else ""

        ws = getattr(self.code_injector, "websocket_bridge", None)
        ws_connected = ws is not None and getattr(ws, "is_connected", False)

        if cmd in ("correct", "rephrase") and target_text:
            transformed = correct_writing_text(target_text) if cmd == "correct" else rephrase_writing_text(target_text)
            if transformed and transformed != target_text:
                if ws_connected:
                    if has_active_selection:
                        ws.send_insert_snippet(snippet=transformed)
                    else:
                        line_no = 1
                        if self._vscode_editor_state and isinstance(self._vscode_editor_state.get("cursor"), dict):
                            line_no = max(1, int(self._vscode_editor_state["cursor"].get("line", 0)) + 1)
                        ws.send_apply_line_fix(line=line_no, replacement=transformed)
                else:
                    self.code_injector.insert_snippet(transformed)

                self.last_action_desc = "Texto corregido" if cmd == "correct" else "Texto reformulado"
                self.action_executed.emit(item.id, self.last_action_desc)
                self.block_activated.emit(target_block, item.id)
                self.update()
                return

        sample = target_text or "el texto seleccionado"
        template = WRITING_AI_PROMPTS.get(cmd, "Reformula o asiste en la redacción del siguiente texto:\n\n{text}")
        prompt = template.format(text=sample)

        if ws_connected:
            if hasattr(self, "agentic_launcher") and self.agentic_launcher is not None:
                self.agentic_launcher.dispatch(cmd, prompt, bridge=ws, selection_only=bool(target_text))
            elif hasattr(ws, "send_trigger_agent_prompt"):
                ws.send_trigger_agent_prompt(action_id=cmd, prompt=prompt, selection_only=bool(target_text))
            self.last_action_desc = f"IA: {item.hint} enviado a VS Code"
        else:
            if hasattr(self, "copy_agentic_prompt"):
                self.copy_agentic_prompt(prompt)
            elif hasattr(self.code_injector, "clipboard") and hasattr(self.code_injector.clipboard, "copy"):
                self.code_injector.clipboard.copy(prompt)
            self.last_action_desc = f"Prompt de {item.hint} en portapapeles"

        self.action_executed.emit(item.id, self.last_action_desc)
        self.block_activated.emit(target_block, item.id)
        self.update()

    def _restore_autofix_slot(self) -> None:
        saved = self._autofix_slot8_saved
        root = self.menu_tree.get("ROOT") if hasattr(self, "menu_tree") else None
        if saved and root and len(root.items) >= 8:
            slot = root.items[7]
            for key, value in saved.items():
                try:
                    setattr(slot, key, value)
                except Exception:
                    pass
        self._autofix_slot8_saved = None

    def set_diagnostics(self, diagnostics: List[Dict[str, Any]]) -> None:
        """Publishes live diagnostics and exposes the one-click Auto-Fix menu."""
        self._active_diagnostics = [d for d in (diagnostics or []) if isinstance(d, dict)]
        self.diagnostics_fixer.last_diagnostics = list(self._active_diagnostics)
        self.diagnostics_fixer.build_fixes(self._active_diagnostics, {
            "symbols": self.context_reader.extract_local_symbols() if self.context_reader else [],
            "ai_suggestions": self.diagnostics_fixer.ai_suggestions,
        })
        root = self.menu_tree.get("ROOT") if hasattr(self, "menu_tree") else None
        if self.current_context_mode_id == "coding" and self._active_diagnostics and root and len(root.items) >= 8:
            if self._autofix_slot8_saved is None:
                slot = root.items[7]
                self._autofix_slot8_saved = {
                    "label": slot.label, "hint": slot.hint, "action_type": slot.action_type,
                    "snippet": slot.snippet, "key_name": slot.key_name,
                    "submenu_id": slot.submenu_id, "icon": slot.icon,
                }
            slot = root.items[7]
            slot.label = "8: AUTO-FIX"
            slot.hint = self.diagnostics_fixer.badge_text(self._active_diagnostics) or "Reparar el error actual"
            slot.action_type = "SUBMENU"
            slot.submenu_id = "AUTO_FIX"
            slot.snippet = None
            slot.key_name = None
            slot.icon = "edit"
            self.menu_tree["AUTO_FIX"] = self.diagnostics_fixer.get_autofix_menu_node(parent_id="ROOT")
        else:
            self._restore_autofix_slot()
        self.update()

    def open_ast_symbols(self, refresh: bool = True) -> None:
        """Builds the current file symbol map and opens its 3x3 page."""
        symbols = self.ast_code_jumper.extract_symbols() if refresh else self.ast_code_jumper.symbols
        if not symbols:
            self.last_action_desc = "AST: sin s?mbolos en el archivo activo"
            self.update()
            return
        self._ast_page = 0
        self.menu_tree["AST_SYMBOLS"] = self.ast_code_jumper.get_symbols_menu_node(
            symbols, self._ast_page, parent_id="ROOT"
        )
        self.navigate_to("AST_SYMBOLS")
        self.last_action_desc = f"AST: {len(symbols)} s?mbolos"
        self.update()

    def open_agentic_launcher(self, refresh: bool = True) -> None:
        """Opens the six-action Agentic Prompt Launcher from any mode."""
        self.menu_tree["AGENTIC_LAUNCHER"] = self.agentic_launcher.get_agentic_menu_node(
            parent_id="ROOT"
        )
        self.navigate_to("AGENTIC_LAUNCHER")
        self.last_action_desc = "Agentic: elige una orden de ingeniería"
        self.update()

    def copy_agentic_prompt(self, prompt: str) -> bool:
        """Copies a rich agentic prompt to the system clipboard."""
        try:
            clipboard = QGuiApplication.clipboard()
            if clipboard is not None:
                clipboard.setText(str(prompt or ""))
                return True
        except Exception:
            pass
        return False

    def _current_agentic_context(self) -> Dict[str, Any]:
        state = getattr(self, "_vscode_editor_state", {}) or {}
        cursor = state.get("cursor") if isinstance(state, dict) else None
        cursor_line = None
        if isinstance(cursor, dict):
            try:
                cursor_line = int(cursor.get("line", 0)) + 1
            except (TypeError, ValueError):
                cursor_line = None
        return {
            "file_path": self.context_reader.get_active_file() if self.context_reader else "",
            "source_code": self.context_reader.read_file_content() if self.context_reader else "",
            "language": self.context_reader.get_active_language() if self.context_reader else "",
            "cursor_line": cursor_line,
            "diagnostics": list(getattr(self, "_active_diagnostics", []) or []),
        }

    def execute_action(self, item: MenuAction, target_block: int = 0) -> None:
        """Programmatically executes a MenuAction directly on the overlay."""
        if getattr(item, "action_type", "") == "AUTOFIX":
            fix = self.diagnostics_fixer._fixes_by_id.get(str(item.id))
            if fix is not None:
                self.autofix_requested.emit(fix)
            self.last_action_desc = f"Auto-Fix: {item.label}"
            self.action_executed.emit(item.id, self.last_action_desc)
            self.block_activated.emit(target_block, item.id)
            return

        if getattr(item, "action_type", "") == "AST_JUMP":
            try:
                self.ast_jump_requested.emit(int(item.snippet or 1))
            except (TypeError, ValueError):
                pass
            self.last_action_desc = f"AST: saltar a {item.hint}"
            self.action_executed.emit(item.id, self.last_action_desc)
            self.block_activated.emit(target_block, item.id)
            return

        if getattr(item, "action_type", "") == "AST_NEXT_PAGE":
            self._ast_page = int(item.snippet or 0)
            self.menu_tree["AST_SYMBOLS"] = self.ast_code_jumper.get_symbols_menu_node(
                self.ast_code_jumper.symbols, self._ast_page, parent_id="ROOT"
            )
            self.navigate_to("AST_SYMBOLS")
            self.last_action_desc = f"AST p?gina {self._ast_page + 1}"
            self.update()
            return

        if getattr(item, "action_type", "") == "AST_REFRESH":
            self.open_ast_symbols(refresh=True)
            self.block_activated.emit(target_block, item.id)
            return

        if item.action_type in ("AGENTIC_PROMPT", "AGENTIC_SEND"):
            queue_only = item.action_type == "AGENTIC_SEND"
            action_id = (
                self._last_agentic_action_id
                if queue_only
                else str(item.snippet or "refactor_clean")
            )
            prompt = self.agentic_launcher.build_prompt(
                action_id,
                context=self._current_agentic_context(),
            )
            self._last_agentic_action_id = action_id
            self.agentic_prompt_requested.emit(action_id, prompt, bool(queue_only))
            label = self.agentic_launcher.get_action_label(action_id)
            self.last_action_desc = (
                f"Orden IA en cola MCP: {label}"
                if queue_only
                else f"Orden IA: {label}"
            )
            self.action_executed.emit(item.id, self.last_action_desc)
            self.block_activated.emit(target_block, item.id)
            self.update()
            return

        if item.action_type == "GAZE_SCROLL":
            enabled = self.toggle_gaze_scroll()
            self.last_action_desc = (
                "Scroll continuo: ON" if enabled else "Scroll continuo: OFF"
            )
            self.action_executed.emit(item.id, self.last_action_desc)
            self.block_activated.emit(target_block, item.id)
            self.update()
            return

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
            detected_lang = self.context_reader.get_active_language() if self.context_reader else "PYTHON"
            self.set_language(detected_lang)
            if self.current_node_id == "LANG_SELECT":
                self.navigate_to("ROOT")
            self.block_activated.emit(target_block, item.id)
            return

        if item.action_type == "CLIPBOARD":
            text = item.snippet or ""
            if text:
                self.code_injector.insert_snippet(text)
                self.text_injected.emit(len(text))
            self.last_action_desc = f"Pegado: {len(text)} chars"
            self.action_executed.emit(item.id, self.last_action_desc)
            self.block_activated.emit(target_block, item.id)
            return

        if item.action_type == "CLIPBOARD_COPY":
            if self.clipboard_manager is not None:
                self.clipboard_manager.copy_selection()
            self.last_action_desc = "Copiando selección..."
            self.action_executed.emit(item.id, self.last_action_desc)
            self.block_activated.emit(target_block, item.id)
            return

        if item.id in ("CMD_UNDO", "EDIT_UNDO", "ACTION_UNDO") or getattr(item, "key_name", "") == "UNDO":
            self.trigger_undo(item.id)
            self.block_activated.emit(target_block, item.id)
            return

        if item.id == "CMD_TUTORIAL":
            self.start_mini_tutorial()
            self.last_action_desc = "Tutorial guiado de inicio"
            self.action_executed.emit(item.id, self.last_action_desc)
            self.block_activated.emit(target_block, item.id)
            return

        if item.id == "CMD_SNAP_CARET":
            self.snap_to_caret()
            self.last_action_desc = "Snap Caret: Micro-recalibrado"
            self.action_executed.emit(item.id, self.last_action_desc)
            self.block_activated.emit(target_block, item.id)
            return

        if item.id == "CMD_TOGGLE_DOCK":
            new_layout = self.toggle_hud_layout()
            self.last_action_desc = f"Layout: {new_layout}"
            self.action_executed.emit(item.id, self.last_action_desc)
            self.block_activated.emit(target_block, item.id)
            return

        if item.id == "CMD_TOGGLE_THEME":
            new_theme = self.toggle_theme()
            self.last_action_desc = f"Tema: {new_theme}"
            self.action_executed.emit(item.id, self.last_action_desc)
            self.block_activated.emit(target_block, item.id)
            return

        if item.action_type in ("SNIPPET", "KEY"):
            self.code_injector.execute_action(item)
            if item.action_type == "SNIPPET":
                self.text_injected.emit(len(item.snippet or ""))
            self.last_action_desc = _clean_action_label(item.label)
            self.action_executed.emit(item.id, self.last_action_desc)
            self.block_activated.emit(target_block, item.id)
            return

        if item.action_type == "EXIT" or item.id in ("CONFIRM_EXIT", "ACTION_EXIT"):
            self.exit_requested.emit()
            self.block_activated.emit(target_block, item.id)
            return

    def trigger_undo(self, action_id: str = "ACTION_UNDO") -> None:
        """Triggers Universal Undo (Ctrl+Z) in the active editor."""
        self._play_sound("undo")
        self.code_injector.send_key("UNDO")
        self.last_action_desc = "Deshacer (Ctrl+Z)"
        self.undo_requested.emit()
        self.action_executed.emit(action_id, self.last_action_desc)
        self.update()

    def set_gaze_estimator(self, estimator: Any) -> None:
        """Connects the GazeEstimator for 1-point micro-recalibration ('Snap to Caret')."""
        self.gaze_estimator = estimator

    def snap_to_caret(
        self,
        target_x: Optional[float] = None,
        target_y: Optional[float] = None,
    ) -> Tuple[float, float]:
        """
        Micro-recalibration 1-point ('Snap to Caret'):
        Re-centers gaze estimate without requiring a full 5-point recalibration.
        If target coordinates are not provided, aims at editor caret (0.35, 0.50) in
        RIGHT_DOCK or screen center (0.50, 0.50) in FULL_GRID.
        """
        if target_x is None:
            target_x = 0.35 if getattr(self, "hud_layout_mode", "FULL_GRID") == "RIGHT_DOCK" else 0.50
        if target_y is None:
            target_y = 0.50

        offset = (0.0, 0.0)
        if self.gaze_estimator is not None and hasattr(self.gaze_estimator, "micro_recalibrate"):
            offset = self.gaze_estimator.micro_recalibrate(target_x, target_y)

        self.micro_recalibration_requested.emit(target_x, target_y)
        self._play_sound("confirm")
        self.last_action_desc = "Snap Caret: Micro-recalibrado"
        self.update()
        return offset

    def set_hud_layout(self, layout: str) -> None:
        """Sets the HUD layout mode ('FULL_GRID' 100% or 'RIGHT_DOCK' 30% column)."""
        normalized = layout.upper().strip()
        if normalized in ("RIGHT_DOCK", "DOCK", "SIDE"):
            self.hud_layout_mode = "RIGHT_DOCK"
        else:
            self.hud_layout_mode = "FULL_GRID"
        self._update_header_exit_rect()
        self.layout_changed.emit(self.hud_layout_mode)
        self.update()

    def toggle_hud_layout(self) -> str:
        """Toggles between FULL_GRID (100%) and RIGHT_DOCK (30% column)."""
        if self.hud_layout_mode == "RIGHT_DOCK":
            self.set_hud_layout("FULL_GRID")
        else:
            self.set_hud_layout("RIGHT_DOCK")
        self._play_sound("nav")
        return self.hud_layout_mode

    def set_theme(self, theme_name: str) -> None:
        """Applies a visual theme (CYBER_GLASS, OLED_BLACK, SOLARIZED_DARK)."""
        normalized = theme_name.upper().strip()
        if "OLED" in normalized:
            self.current_theme = "OLED_BLACK"
            self._brush_header_bg = QBrush(QColor(0, 0, 0, 250))
            self._brush_card_inactive = QBrush(QColor(0, 0, 0, 240))
            self._brush_card_active = QBrush(QColor(15, 15, 15, 245))
            self._brush_band_inactive = QBrush(QColor(12, 12, 12, 255))
            self._brush_band_active = QBrush(QColor(20, 20, 20, 255))
            self._pen_card_inactive = QPen(QColor(255, 255, 255, 90), 1.5)
            self._color_card_text_active = QColor(255, 255, 255, 255)
            self._color_card_text_inactive = QColor(240, 240, 240, 255)
            self._color_card_subtitle = QColor(200, 200, 200, 240)
            self._color_card_subtitle_inactive = QColor(180, 180, 180, 240)
            self._set_theme_color("#00FF66")
        elif "SOLARIZED" in normalized:
            self.current_theme = "SOLARIZED_DARK"
            self._brush_header_bg = QBrush(QColor(0, 43, 54, 245))
            self._brush_card_inactive = QBrush(QColor(0, 43, 54, 210))
            self._brush_card_active = QBrush(QColor(7, 54, 66, 235))
            self._brush_band_inactive = QBrush(QColor(7, 54, 66, 245))
            self._brush_band_active = QBrush(QColor(14, 65, 78, 250))
            self._pen_card_inactive = QPen(QColor(88, 110, 117, 120), 1.2)
            self._color_card_text_active = QColor(253, 246, 227, 255)
            self._color_card_text_inactive = QColor(147, 161, 161, 255)
            self._color_card_subtitle = QColor(131, 148, 150, 240)
            self._color_card_subtitle_inactive = QColor(101, 123, 131, 240)
            self._set_theme_color("#268BD2")
        else:
            self.current_theme = "CYBER_GLASS"
            self._brush_header_bg = QBrush(QColor(10, 15, 29, 225))
            self._brush_card_inactive = QBrush(QColor(10, 15, 29, 220))
            self._brush_card_active = QBrush(QColor(15, 23, 42, 235))
            self._brush_band_inactive = QBrush(QColor(10, 15, 29, 230))
            self._brush_band_active = QBrush(QColor(15, 23, 42, 240))
            self._pen_card_inactive = QPen(QColor(30, 41, 59, 180), 1.0)
            self._color_card_text_active = QColor(248, 250, 252, 255)
            self._color_card_text_inactive = QColor(226, 232, 240, 255)
            self._color_card_subtitle = QColor(148, 163, 184, 220)
            self._color_card_subtitle_inactive = QColor(148, 163, 184, 255)
            self._set_theme_color("#3b82f6")
        self.theme_changed.emit(self.current_theme)
        self.update()

    def toggle_theme(self) -> str:
        """Cycles between CYBER_GLASS -> OLED_BLACK -> SOLARIZED_DARK."""
        cycle = ["CYBER_GLASS", "OLED_BLACK", "SOLARIZED_DARK"]
        curr = self.current_theme if self.current_theme in cycle else "CYBER_GLASS"
        nxt = cycle[(cycle.index(curr) + 1) % len(cycle)]
        self.set_theme(nxt)
        self._play_sound("nav")
        return self.current_theme

    def open_command_palette(self) -> None:
        """Navigates to the Gaze Command Palette (Spotlight)."""
        self.navigate_to("COMMAND_PALETTE")
        self._play_sound("nav")

    def get_adaptive_dwell_time(self, item: Any, block_idx: int) -> float:
        """Computes the required dwell time in seconds based on action ergonomics."""
        if block_idx == 4 or (item is not None and getattr(item, "action_type", "") == "PAUSE"):
            return float("inf")  # Safe Rest Zone: Midas Touch immune
        if item is None:
            return float(getattr(config, "DWELL_TIME_STANDARD_SEC", 0.45))
        atype = getattr(item, "action_type", "")
        item_id = str(getattr(item, "id", ""))
        if atype == "EXIT" or item_id in ("CONFIRM_EXIT", "ACTION_EXIT") or "DELETE" in item_id:
            return float(getattr(config, "DWELL_TIME_DANGER_SEC", 0.85))
        if atype in ("BACK", "KEY", "SUBMENU") or item_id.startswith(("NAV_", "CMD_")):
            return float(getattr(config, "DWELL_TIME_NAV_SEC", 0.30))
        return float(getattr(config, "DWELL_TIME_STANDARD_SEC", 0.45))

    def _update_adaptive_dwell(self, block_idx: Optional[int]) -> None:
        """Advances the adaptive dwell-time accumulator and triggers activation when complete."""
        if not getattr(self, "adaptive_dwell_enabled", True) or block_idx is None:
            self._dwell_block = None
            self._dwell_progress = 0.0
            self._dwell_fired = False
            return

        now = time.time()
        if self._dwell_block != block_idx:
            self._dwell_block = block_idx
            self._dwell_start_time = now
            self._dwell_progress = 0.0
            self._dwell_fired = False
            return

        if self._dwell_fired:
            return

        node = self.current_node
        item = node.items[block_idx] if (node and block_idx < len(node.items)) else None
        target_dwell = self.get_adaptive_dwell_time(item, block_idx)

        # When mouth gesture is uncalibrated, require real deliberate dwell (minimum 0.70s)
        # to prevent accidental entry into boxes simply by looking at them (Anti-Midas protection).
        if not getattr(self, "mar_calibrated", True) and not math.isinf(target_dwell):
            target_dwell = max(target_dwell, 0.70)

        if math.isinf(target_dwell):
            self._dwell_progress = 0.0
            return

        elapsed = now - self._dwell_start_time
        progress = max(0.0, min(1.0, elapsed / max(0.05, target_dwell)))
        self._dwell_progress = progress

        if progress >= 1.0:
            self._dwell_fired = True
            # Dwell auto-click is an opt-in accessibility feature (disabled by default).
            # By default (Zero-Dwell), looking at a box only focuses/highlights it.
            # Intentional confirmation via mouth click (MAR) or physical click is required.
            if getattr(self, "dwell_click_enabled", False) and not getattr(self, "show_tutorial_modal", False):
                self.trigger_click_flash(block_idx)
                if item is not None:
                    self._play_sound("confirm")
                    self.execute_action(item, target_block=block_idx)

    def set_dwell_click_enabled(self, enabled: bool) -> None:
        """Enables or disables auto-triggering actions on gaze dwell (accessibility fallback)."""
        self.dwell_click_enabled = bool(enabled)

    def start_mini_tutorial(self) -> None:
        """Starts the interactive 3-step mini-tutorial for gaze onboarding."""
        self.show_tutorial_modal = True
        self.tutorial_step = 1
        self.tutorial_step_progress = 0.0
        self._tutorial_rest_start = 0.0
        self._play_sound("nav")
        self.update()

    def start_tutorial(self) -> None:
        """Alias for start_mini_tutorial for external callers and test runners."""
        self.start_mini_tutorial()

    def close_mini_tutorial(self) -> None:
        """Closes the interactive tutorial modal."""
        self.show_tutorial_modal = False
        self.update()

    def close_tutorial(self) -> None:
        """Alias for close_mini_tutorial."""
        self.close_mini_tutorial()

    @property
    def _tutorial_active(self) -> bool:
        """True if the onboarding tutorial modal is currently displayed."""
        return bool(getattr(self, "show_tutorial_modal", False))

    @_tutorial_active.setter
    def _tutorial_active(self, value: bool) -> None:
        self.show_tutorial_modal = bool(value)

    def _update_mini_tutorial_gaze(self, gx: float, gy: float) -> None:
        """Tracks gaze and advances the 3-step interactive onboarding tutorial."""
        if not getattr(self, "show_tutorial_modal", False):
            return

        now = time.time()
        if self.tutorial_step == 1:
            if self.hovered_block is not None and self.hovered_block != 4:
                self.tutorial_step_progress = min(1.0, getattr(self, "_dwell_progress", 0.0))
                if self.tutorial_step_progress >= 0.95 or getattr(self, "_dwell_fired", False):
                    self.tutorial_step = 2
                    self.tutorial_step_progress = 0.0
                    self._play_sound("confirm")
            else:
                self.tutorial_step_progress = 0.0
        elif self.tutorial_step == 3:
            if self.hovered_block == 4 or self.hovered_block is None:
                if self._tutorial_rest_start == 0.0:
                    self._tutorial_rest_start = now
                elapsed = now - self._tutorial_rest_start
                self.tutorial_step_progress = min(1.0, elapsed / 1.0)
                if self.tutorial_step_progress >= 1.0:
                    self.tutorial_step = 4
                    self.tutorial_step_progress = 1.0
                    self._play_sound("confirm")
            else:
                self._tutorial_rest_start = 0.0
                self.tutorial_step_progress = 0.0

    def _paint_tutorial_modal(self, painter: QPainter, w: float, h: float) -> None:
        """Renders the high-contrast 3-step interactive onboarding tutorial modal."""
        painter.save()
        try:
            modal_w = min(620.0, w - 40.0)
            modal_h = 240.0
            modal_x = (w - modal_w) * 0.5
            modal_y = (h - modal_h) * 0.5
            modal_rect = QRectF(modal_x, modal_y, modal_w, modal_h)

            painter.setBrush(QBrush(QColor(10, 15, 29, 245)))
            theme_col = QColor(self.theme_color or "#3b82f6")
            painter.setPen(QPen(theme_col, 1.5))
            painter.drawRoundedRect(modal_rect, 12.0, 12.0)

            # Close button in top-right of tutorial modal
            self.tutorial_modal_close_rect = QRectF(modal_x + modal_w - 38.0, modal_y + 14.0, 24.0, 24.0)
            painter.setBrush(QBrush(QColor(255, 255, 255, 20)))
            painter.setPen(QPen(QColor(255, 255, 255, 120), 1.0))
            painter.drawRoundedRect(self.tutorial_modal_close_rect, 4.0, 4.0)
            painter.setPen(QColor(220, 220, 220))
            painter.setFont(self._font_header_bold_btn)
            painter.drawText(self.tutorial_modal_close_rect, Qt.AlignmentFlag.AlignCenter, "X")

            step = int(getattr(self, "tutorial_step", 1))
            badge_text = f"PASO {step} DE 3" if step <= 3 else "TUTORIAL COMPLETADO"
            badge_rect = QRectF(modal_x + 24.0, modal_y + 20.0, 180.0, 26.0)
            painter.setBrush(QBrush(QColor(theme_col.red(), theme_col.green(), theme_col.blue(), 45)))
            painter.setPen(QPen(theme_col, 1.2))
            painter.drawRoundedRect(badge_rect, 6.0, 6.0)
            painter.setPen(theme_col)
            painter.setFont(self._font_header_bold_btn)
            painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, badge_text)

            titles = {
                1: "1. Fijacion de la mirada (Adaptive Dwell)",
                2: "2. Confirmacion por Gesto (MAR / Clic)",
                3: "3. Zona de Reposo (Safe Rest Anti-Midas)",
                4: "Listo para programar con IDEye!",
            }
            subtitles = {
                1: "Posiciona tu mirada en cualquier celda para cargar el anillo de fijacion progresivo.",
                2: "Abre levemente la boca o pulsa clic/Enter para confirmar una seleccion activa.",
                3: "Coloca tu mirada en la celda central 5 o en el editor para reposar sin disparos accidentales.",
                4: "Has completado los fundamentos de control ocular. Pulsa F2 o parpadea para cerrar.",
            }

            title = titles.get(step, "")
            subtitle = subtitles.get(step, "")

            painter.setPen(QColor(255, 255, 255))
            painter.setFont(self._font_modal_title)
            painter.drawText(
                QRectF(modal_x + 24.0, modal_y + 58.0, modal_w - 48.0, 32.0),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                title,
            )

            painter.setPen(QColor(203, 213, 225))
            painter.setFont(self._font_modal_item_title)
            painter.drawText(
                QRectF(modal_x + 24.0, modal_y + 96.0, modal_w - 48.0, 52.0),
                Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap,
                subtitle,
            )

            bar_x = modal_x + 24.0
            bar_y = modal_y + 165.0
            bar_w = modal_w - 48.0
            bar_h = 10.0
            painter.setBrush(QBrush(QColor(30, 41, 59, 200)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(QRectF(bar_x, bar_y, bar_w, bar_h), 5.0, 5.0)

            prog = max(0.0, min(1.0, float(getattr(self, "tutorial_step_progress", 0.0))))
            if prog > 0.01:
                painter.setBrush(QBrush(theme_col))
                painter.drawRoundedRect(QRectF(bar_x, bar_y, bar_w * prog, bar_h), 5.0, 5.0)

            painter.setPen(QColor(148, 163, 184))
            painter.setFont(self._font_modal_item_desc)
            painter.drawText(
                QRectF(modal_x + 24.0, modal_y + 190.0, modal_w - 48.0, 24.0),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                "Pulsa F2 o Escape para salir del tutorial",
            )
        except Exception as exc:
            logger.warning(f"Error rendering tutorial modal: {exc}")
        finally:
            painter.restore()

    def mousePressEvent(self, event) -> None:
        """Handles physical mouse clicks for testing, headless runners, and assistive caregivers."""
        pos = event.position() if hasattr(event, "position") else event.pos()
        px, py = float(pos.x()), float(pos.y())

        # Check tutorial modal dismiss and step confirmation if active
        if getattr(self, "show_tutorial_modal", False):
            if (
                hasattr(self, "tutorial_modal_close_rect")
                and self.tutorial_modal_close_rect.isValid()
                and self.tutorial_modal_close_rect.adjusted(-8.0, -8.0, 8.0, 8.0).contains(px, py)
            ):
                self.close_mini_tutorial()
                event.accept()
                return

            if getattr(self, "tutorial_step", 1) == 2:
                self.tutorial_step = 3
                self.tutorial_step_progress = 0.0
                self._tutorial_rest_start = time.time()
                self._play_sound("confirm")
                self.update()
                event.accept()
                return
            elif getattr(self, "tutorial_step", 1) == 4:
                self.close_mini_tutorial()
                event.accept()
                return

            event.accept()
            return

        # Check the help modal actions if open.
        if self.show_help_modal:
            open_guide = (
                self.help_modal_guide_rect.isValid()
                and self.help_modal_guide_rect.adjusted(-12.0, -12.0, 12.0, 12.0).contains(px, py)
            )
            start_tutorial = (
                hasattr(self, "help_modal_tutorial_rect")
                and self.help_modal_tutorial_rect.isValid()
                and self.help_modal_tutorial_rect.adjusted(-12.0, -12.0, 12.0, 12.0).contains(px, py)
            )
            self.show_help_modal = False
            self.hovered_help_modal_guide = False
            self.hovered_help_modal_tutorial = False
            self.hovered_help_modal_close = False
            if open_guide:
                self.last_action_desc = "Abriendo Manual Interactivo"
                self.interactive_guide_requested.emit()
            elif start_tutorial:
                self.start_mini_tutorial()
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
        elif event.key() == Qt.Key.Key_B:
            self.open_clipboard_history()
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
        elif event.key() == Qt.Key.Key_Escape and getattr(self, "show_tutorial_modal", False):
            self.show_tutorial_modal = False
            self.update()
            event.accept()
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space) and getattr(self, "show_tutorial_modal", False):
            if getattr(self, "tutorial_step", 1) == 2:
                self.tutorial_step = 3
                self.tutorial_step_progress = 0.0
                self._tutorial_rest_start = time.time()
                self._play_sound("confirm")
                self.update()
                event.accept()
            elif getattr(self, "tutorial_step", 1) == 4:
                self.close_mini_tutorial()
                event.accept()
        elif event.key() == Qt.Key.Key_F2:
            self.show_tutorial_modal = not getattr(self, "show_tutorial_modal", False)
            if self.show_tutorial_modal:
                self.start_mini_tutorial()
            self.update()
            event.accept()
        elif event.key() == Qt.Key.Key_D:
            self.toggle_hud_layout()
            event.accept()
        elif event.key() == Qt.Key.Key_P:
            self.open_command_palette()
            event.accept()
        elif event.key() == Qt.Key.Key_Z:
            self.trigger_undo()
            event.accept()
        elif event.key() == Qt.Key.Key_C:
            self.snap_to_caret()
            event.accept()
        elif event.key() == Qt.Key.Key_O:
            self.toggle_theme()
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
                if len(std_items) > 8:
                    std_items[8] = create_adaptive_menu_action("9")
                else:
                    std_items.append(create_adaptive_menu_action("9"))
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
        self._apply_macro_overrides()
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
            if was_sniper:
                self.release_freelook_controls()
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
                if len(std_items) > 8:
                    std_items[8] = create_adaptive_menu_action("9")
                else:
                    std_items.append(create_adaptive_menu_action("9"))
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
        self._apply_macro_overrides()

        # Keep the mode hub open when an automatic editor-state change arrives.
        # When the user explicitly picked a mode, _activate_mode() sets the flag
        # and we enter that mode's ROOT instead.
        if self.current_node_id == "MODE_SELECT" and not self._mode_selection_in_progress:
            self.current_node_id = "MODE_SELECT"
        else:
            self.current_node_id = "ROOT"
        self._dwell_start_time = time.time()
        self._dwell_progress = 0.0
        self._dwell_fired = False
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

        # EXIT_CONFIRM must exist in every mode, not only in the coding tree.
        if "EXIT_CONFIRM" not in self.menu_tree:
            self.menu_tree["EXIT_CONFIRM"] = MenuNode(
                id="EXIT_CONFIRM",
                title="CONFIRMAR SALIDA",
                breadcrumb_label="SALIR",
                items=populate_exit_confirm_items(parent_id="ROOT"),
                parent_id="ROOT",
                sticky=False,
            )

        # Gaze Command Palette (Spotlight) auxiliary node
        if "COMMAND_PALETTE" not in self.menu_tree:
            self.menu_tree["COMMAND_PALETTE"] = MenuNode(
                id="COMMAND_PALETTE",
                title="PALETA DE COMANDOS",
                breadcrumb_label="SPOTLIGHT",
                items=populate_command_palette_items(parent_id="ROOT"),
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
        if previous_mode == "sniper" and mode_id != "sniper":
            self.release_freelook_controls()
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
        """True when gaze is on the top command bar (plain-key hotkey gate)."""
        gaze = getattr(self, "current_gaze", None)
        if not gaze:
            return False
        try:
            gx, gy = gaze
            w = max(1.0, float(self.width()))
            h = max(1.0, float(self.height()))
            px, py = gx * w, gy * h
            header = getattr(self, "header_rect", None)
            if header is not None and header.isValid() and header.adjusted(
                -18.0, -12.0, 18.0, 14.0
            ).contains(px, py):
                return True
            rect = getattr(self, "header_mode_rect", None)
            if rect is not None and rect.isValid() and rect.adjusted(
                -24.0, -18.0, 24.0, 18.0
            ).contains(px, py):
                return True
            return False
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

    def _ghost_card_opacity(self) -> float:
        """Returns the live card-only opacity used by Ghost-Peek."""
        return float(max(0.15, min(1.0, self._ghost_opacity))) if self.ghost_peek_enabled else 1.0

    def update_ghost_peek(
        self,
        now: Optional[float] = None,
        idle_seconds: Optional[float] = None,
        target_opacity: float = 0.15,
    ) -> float:
        """Advances the Ghost-Peek fade and wake animation."""
        if not self.ghost_peek_enabled:
            self._ghost_opacity = 1.0
            return 1.0
        timestamp = time.time() if now is None else float(now)
        idle_threshold = (
            self.ghost_peek_idle_seconds
            if idle_seconds is None
            else max(2.0, float(idle_seconds))
        )
        idle = max(0.0, timestamp - self._last_ghost_interaction)
        if idle >= idle_threshold:
            target = max(0.15, min(1.0, float(target_opacity)))
            if self._ghost_opacity > target:
                self._ghost_opacity = max(target, self._ghost_opacity - 0.08)
            else:
                self._ghost_opacity = target
        elif self._ghost_opacity < 1.0:
            self._ghost_opacity = 1.0
        return self._ghost_opacity

    def _tick_ghost_peek(self) -> None:
        before = self._ghost_opacity
        self.update_ghost_peek()
        if abs(self._ghost_opacity - before) > 1e-4:
            self.update()

    def _wake_ghost_peek(self) -> None:
        self._last_ghost_interaction = time.time()
        if self._ghost_opacity < 1.0:
            self._ghost_opacity = 1.0
            self.update()

    def set_ghost_peek_enabled(self, enabled: bool, emit_signal: bool = True) -> None:
        self.ghost_peek_enabled = bool(enabled)
        if not self.ghost_peek_enabled:
            self._ghost_opacity = 1.0
        else:
            self._last_ghost_interaction = time.time()
        if emit_signal:
            self.ghost_peek_toggled.emit(self.ghost_peek_enabled)

    def set_ghost_peek_idle_seconds(self, seconds: float) -> float:
        """Sets the minimum idle time before Ghost-Peek starts fading."""
        try:
            value = float(seconds)
        except (TypeError, ValueError, OverflowError):
            value = 30.0
        self.ghost_peek_idle_seconds = max(2.0, value)
        self.update()
        return self.ghost_peek_idle_seconds

    def toggle_ghost_peek(self) -> bool:
        self.set_ghost_peek_enabled(not self.ghost_peek_enabled)
        return self.ghost_peek_enabled

    def toggle_gaze_scroll(self, enabled: Optional[bool] = None) -> bool:
        """Toggles proportional inertial scrolling for the current gaze."""
        next_state = (not self._gaze_scroll_enabled) if enabled is None else bool(enabled)
        if next_state:
            self.gaze_scroller.activate()
            self._last_ghost_interaction = time.time()
        else:
            self.gaze_scroller.stop()
        self._gaze_scroll_enabled = next_state
        self.gaze_scroll_toggled.emit(next_state)
        self.last_action_desc = "Scroll ocular: ON" if next_state else "Scroll ocular: OFF"
        self.update()
        return next_state

    def _apply_gaze_scroll(self, gy: float) -> None:
        if not self._gaze_scroll_enabled or self.reading_mode or self.show_help_modal:
            return
        if self.current_context_mode_id == "sniper":
            return
        if self.mouse_controller is None:
            return
        try:
            self.gaze_scroller.update(float(gy), dt=1.0 / 60.0, active=True)
            steps = int(self.gaze_scroller.last_steps)
            horizontal = int(self.gaze_scroller.last_horizontal_steps)
            if steps:
                self.mouse_controller.scroll(steps)
            if horizontal:
                self.mouse_controller.scroll_horizontal(horizontal)
        except Exception:
            pass

    def toggle_reading_mode(self) -> None:
        """Toggles between Active HUD mode and Hidden/Reading Mode (Option B: full hide)."""
        self.reading_mode = not self.reading_mode
        self.current_opacity = config.OVERLAY_OPACITY_READING if self.reading_mode else config.OVERLAY_OPACITY_ACTIVE
        if self.reading_mode:
            self.release_freelook_controls()
            self.gaze_scroller.stop()
            self._gaze_scroll_enabled = False
            self.hovered_block = None
            self._dwell_block = None
            self._dwell_progress = 0.0
            self._dwell_fired = False
            self.hide()
        else:
            self._dwell_start_time = time.time()
            self._dwell_progress = 0.0
            self._dwell_fired = False
            self.show()
            self.raise_()
            self._wake_ghost_peek()
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
        if sub_id == "STRUCT" or "STRUCT" in curr_id or any(k in act_id for k in ("FUNC", "CLASS", "DEF", "STRUCT", "DATA", "LIST", "DICT", "CTX_FN", "CTX_CLS")):
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
        if getattr(self, "_lens_capture_in_progress", False):
            painter.end()
            return

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
        screen_pill_rect = self.header_screen_rect

        painter.setOpacity(0.95 if not self.reading_mode else 0.30)

        dpr = self.devicePixelRatioF() or 1.0

        # Unified floating command bar (Dynamic Island / Linear style)
        painter.setBrush(self._brush_header_bg)
        painter.setPen(self._pen_header_border)
        painter.drawRoundedRect(header_rect, 10.0, 10.0)

        IconManager.instance().render_icon(painter, "ideye_logo", logo_rect, dpr=dpr)

        # Brand + WS status (left side). Clip both to the space before the
        # mode selector so "Local"/"VS Code" can never run under it.
        brand_x = logo_rect.right() + 8.0
        status_right = self.header_mode_rect.left() - 8.0
        available_w = max(0.0, status_right - brand_x)
        painter.setFont(self._font_header_left)
        ws_text = "VS Code" if self._ws_connected else "Local"
        ws_text_w = float(painter.fontMetrics().horizontalAdvance(ws_text))
        show_ws = bool(getattr(self, "_header_ws_show", False)) and available_w > 50.0
        ws_reserve = (11.0 + ws_text_w + 6.0) if show_ws else 0.0
        brand_draw_w = max(0.0, available_w - ws_reserve - 10.0)
        painter.setPen(self._color_card_text_active)
        painter.setFont(self._font_header_bold_btn)
        if brand_draw_w >= 20.0:
            brand_text = painter.fontMetrics().elidedText(
                "IDEye", Qt.TextElideMode.ElideRight, int(brand_draw_w)
            )
            painter.drawText(
                QRectF(brand_x, header_rect.y() + 6.0, brand_draw_w, pill_h),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                brand_text,
            )
        if show_ws:
            ws_x = brand_x + brand_draw_w + 10.0
            if ws_x + 6.0 <= status_right:
                ws_color = QColor(34, 197, 94) if self._ws_connected else QColor(148, 163, 184)
                painter.setBrush(QBrush(ws_color))
                painter.setPen(Qt.PenStyle.NoPen)
                y = header_rect.y() + 6.0 + (pill_h - 6.0) * 0.5
                painter.drawEllipse(QRectF(ws_x, y, 6.0, 6.0))
                if not getattr(self, "_header_ws_dot_only", False):
                    text_w = max(0.0, status_right - (ws_x + 11.0))
                    if text_w > 10.0:
                        painter.setPen(self._pen_header_left)
                        painter.setFont(self._font_header_left)
                        painter.drawText(
                            QRectF(ws_x + 11.0, header_rect.y() + 6.0, text_w, pill_h),
                            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                            painter.fontMetrics().elidedText(
                                ws_text, Qt.TextElideMode.ElideRight, int(text_w)
                            ),
                        )

        # Multi-monitor selector.
        if screen_pill_rect.isValid():
            painter.setBrush(QBrush(QColor(37, 99, 235, 30)))
            painter.setPen(QPen(QColor(59, 130, 246, 180), 1.0))
            painter.drawRoundedRect(screen_pill_rect, 7.0, 7.0)
            painter.setPen(QColor(219, 234, 254))
            painter.setFont(self._font_header_bold_btn)
            painter.drawText(
                screen_pill_rect,
                Qt.AlignmentFlag.AlignCenter,
                f"MON {self.screen_index + 1}/{self.screen_count}",
            )
        # Sniper action selector, or compact last-action status.
        elif sniper_pill_rect.isValid():
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
        painter.drawRoundedRect(self.header_exit_rect, 10.0, 10.0)
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
            "SALIR?" if time.time() < self._exit_armed_until else "SALIR",
        )

        # Help
        if self.active_click_header_help:
            help_brush, help_pen, help_text_color = self._brush_click, self._pen_click, self._color_click_text
        elif self.hovered_header_help:
            painter.setBrush(self._brush_help_glow)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(self.header_help_rect.adjusted(-4.0, -4.0, 4.0, 4.0), 10.0, 10.0)
            help_brush, help_pen, help_text_color = QBrush(QColor(37, 99, 235, 230)), QPen(QColor(219, 234, 254), 2.0), QColor(255, 255, 255)
        else:
            help_brush, help_pen, help_text_color = self._brush_help_idle, self._pen_help_idle, self._color_help_text
        painter.setBrush(help_brush)
        painter.setPen(help_pen)
        painter.drawRoundedRect(self.header_help_rect, 10.0, 10.0)
        help_vpad = 2.0
        help_icon_rect = QRectF(
            self.header_help_rect.x() + 12.0,
            self.header_help_rect.y() + (pill_h - icon_size) * 0.5,
            icon_size,
            icon_size,
        )
        IconManager.instance().render_icon(painter, "help", help_icon_rect, color="#93C5FD", dpr=dpr)
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
            painter.drawRoundedRect(self.header_mode_rect.adjusted(-4.0, -4.0, 4.0, 4.0), 10.0, 10.0)
            mode_brush, mode_pen, mode_text_color = self._brush_mode_idle, QPen(QColor(96, 165, 250, 220), 1.5), QColor(255, 255, 255)
        else:
            mode_brush, mode_pen, mode_text_color = self._brush_mode_idle, self._pen_mode_idle, self._color_mode_text
        painter.setBrush(mode_brush)
        painter.setPen(mode_pen)
        painter.drawRoundedRect(self.header_mode_rect, 10.0, 10.0)
        mode_icon_rect = QRectF(
            self.header_mode_rect.x() + 9.0,
            self.header_mode_rect.y() + (pill_h - 18.0) * 0.5,
            18.0,
            18.0,
        )
        mode_icon_color = self.theme_color or "#3b82f6"
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
            lang_brush, lang_pen, lang_text_color = QBrush(QColor(37, 99, 235, 180)), QPen(QColor(191, 219, 254), 1.6), QColor(255, 255, 255)
        else:
            lang_brush, lang_pen, lang_text_color = self._brush_btn_idle, self._pen_btn_idle, QColor(147, 197, 253)
        painter.setBrush(lang_brush)
        painter.setPen(lang_pen)
        painter.drawRoundedRect(self.header_lang_rect, 10.0, 10.0)
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
                color = QColor(self.theme_color or "#3b82f6")
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
        # Live diagnostics badge (amber/coral, non-blocking).
        if self._active_diagnostics and not self.reading_mode:
            badge = self.diagnostics_fixer.badge_text(self._active_diagnostics)
            fm = QFontMetrics(self._font_header_bold_btn)
            bw = min(560.0, max(300.0, fm.horizontalAdvance(badge) + 30.0))
            self.autofix_badge_rect = QRectF(w * 0.5 - bw * 0.5, header_rect.bottom() + 8.0, bw, 30.0)
            painter.setBrush(QColor(120, 53, 15, 235))
            painter.setPen(QPen(QColor(251, 146, 60, 245), 1.6))
            painter.drawRoundedRect(self.autofix_badge_rect, 8.0, 8.0)
            painter.setPen(QColor(255, 237, 213))
            painter.setFont(self._font_header_bold_btn)
            painter.drawText(self.autofix_badge_rect, Qt.AlignmentFlag.AlignCenter, badge)
        else:
            self.autofix_badge_rect = QRectF()

        # Active game/app profile badge.
        if self._game_profile_name != "default_desktop":
            profile_text = f"PERFIL: {self._game_profile_label}"
            fm_profile = QFontMetrics(self._font_header_bold_btn)
            pw = min(260.0, max(170.0, fm_profile.horizontalAdvance(profile_text) + 24.0))
            self.game_profile_badge_rect = QRectF(header_rect.left() + 8.0, header_rect.bottom() + 8.0, pw, 28.0)
            painter.setBrush(QColor(10, 15, 29, 235))
            painter.setPen(QPen(QColor(59, 130, 246, 230), 1.4))
            painter.drawRoundedRect(self.game_profile_badge_rect, 7.0, 7.0)
            painter.setPen(QColor(219, 234, 254))
            painter.setFont(self._font_header_bold_btn)
            painter.drawText(self.game_profile_badge_rect, Qt.AlignmentFlag.AlignCenter, profile_text)
        else:
            self.game_profile_badge_rect = QRectF()

        # 2. 3x3 Grid Category Cards
        # =====================================================================
        icon_map = {
            "FLOW": "flow",
            "STRUCT": "function",
            "OPERATORS": "operators",
            "NAV": "navigation",
            "PAUSE": "pause_eye",
            "BACK": "arrow_left",
            "EDIT": "edit",
            "FORMAT": "format",
            "AI": "ai_spark",
            "EXIT": "exit",
            "MODE": "mode",
            "SNIPER": "crosshair",
        }

        painter.save()
        card_alpha = self._ghost_card_opacity()
        painter.setOpacity(card_alpha)
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
            painter.setOpacity(card_alpha)
            painter.setBrush(body_brush)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(rect, 10.0, 10.0)

            # 2. Focused card gets a subtle sapphire glow and 2px soft halo
            if is_active and not self.reading_mode:
                theme = border_pen.color()
                # 2px soft halo around card perimeter
                halo_pen = QPen(QColor(theme.red(), theme.green(), theme.blue(), 50), 2.0)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(halo_pen)
                painter.drawRoundedRect(rect.adjusted(-2.0, -2.0, 2.0, 2.0), 10.0, 10.0)

                # Micro-elevation top highlight shimmer
                gradient = QLinearGradient(rect.x(), rect.y(), rect.right(), rect.y())
                transparent = QColor(theme)
                transparent.setAlpha(0)
                middle = QColor(theme)
                middle.setAlpha(120)
                gradient.setColorAt(0.0, transparent)
                gradient.setColorAt(0.5, middle)
                gradient.setColorAt(1.0, transparent)
                painter.fillRect(
                    QRectF(rect.x() + 10.0, rect.y() + 1.0, max(1.0, rect.width() - 20.0), 2.5),
                    QBrush(gradient),
                )

            # 3. Neutral 1px frame, or 2px theme frame for the focused card.
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(border_pen)
            painter.drawRoundedRect(rect, 10.0, 10.0)

            # 4. High-contrast header band with rounded top corners.
            band_h = min(52.0, rect.height())
            if band_h > 4.0:
                radius = 10.0
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
            painter.setOpacity(text_opacity * card_alpha)

            number = i + 1
            number_rect = QRectF(rect.x() + 10.0, rect.y() + 8.0, 24.0, 24.0)
            painter.setBrush(self._brush_badge_theme if is_active else self._brush_badge_inactive)
            painter.setPen(self._pen_badge_theme if is_active else self._pen_badge_active)
            painter.drawRoundedRect(number_rect, 7.0, 7.0)
            painter.setPen(self._color_theme_text if is_active else self._color_card_text_inactive)
            painter.setFont(self._font_card_number)
            painter.drawText(number_rect, Qt.AlignmentFlag.AlignCenter, str(number))

            # Card activation progress indicator (top-left badge)
            # Only visible when the user actively attempts to access the cell/mode:
            # - Intentional facial confirmation (mouth opening / MAR towards threshold)
            # - Intentional dwell auto-click (if dwell_click_enabled is explicitly active)
            # - Interactive onboarding tutorial (step 1 gaze fixation)
            activation_progress = 0.0
            if is_active and i != 4:
                # 1. Mouth opening gesture: user deliberately confirming access to this card/mode
                mar_threshold = max(0.01, float(getattr(self, "mar_threshold", 0.35)))
                mar_rest = float(getattr(self, "_mar_rest_baseline", 0.20))
                current_mar = float(getattr(self, "current_mar", 0.0))
                if current_mar > mar_rest + 0.015:
                    mar_ratio = max(0.0, min(1.0, (current_mar - mar_rest) / max(0.01, mar_threshold - mar_rest)))
                    if mar_ratio > 0.08:
                        activation_progress = mar_ratio

                # 2. Dwell-click enabled (accessibility opt-in) or tutorial step 1
                if activation_progress == 0.0:
                    is_tutorial_dwell = bool(getattr(self, "show_tutorial_modal", False) and getattr(self, "tutorial_step", 0) == 1)
                    is_dwell_click_active = bool(getattr(self, "dwell_click_enabled", False))
                    if (is_dwell_click_active or is_tutorial_dwell) and getattr(self, "adaptive_dwell_enabled", True):
                        activation_progress = float(getattr(self, "_dwell_progress", 0.0))

            if activation_progress > 0.0:
                dwell_rect = number_rect.adjusted(-3.0, -3.0, 3.0, 3.0)
                theme_accent = QColor(self.theme_color or "#3b82f6")
                dwell_pen = QPen(QColor(theme_accent.red(), theme_accent.green(), theme_accent.blue(), 230), 2.5)
                if is_danger:
                    dwell_pen.setColor(QColor(239, 68, 68, 230))
                painter.setPen(dwell_pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                span_angle = int(-activation_progress * 360 * 16)
                painter.drawArc(dwell_rect, 90 * 16, span_angle)

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
            self._paint_sniper_lens(painter)

        # =====================================================================
        # 4. Refined High-Visibility Dual-Ring Reticle with Glow Aura
        # =====================================================================
        self._paint_gaze_scroll_indicators(painter, w, h)
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

        # 5. Interactive 3-step onboarding mini-tutorial modal
        if getattr(self, "show_tutorial_modal", False):
            self._paint_tutorial_modal(painter, w, h)

        painter.end()
    def _paint_gaze_scroll_indicators(self, painter: QPainter, w: float, h: float) -> None:
        """Draws subtle top/bottom velocity indicators while gaze scroll is active."""
        if not getattr(self, "_gaze_scroll_enabled", False):
            return
        try:
            speed = float(self.gaze_scroller.speed())
        except Exception:
            return
        if abs(speed) < 0.01:
            return
        intensity = min(1.0, abs(speed) / max(1e-6, self.gaze_scroller.max_scroll_rate))
        color = QColor(getattr(self, "theme_color", "#22d3ee"))
        color.setAlpha(int(45 + 150 * intensity))
        painter.save()
        painter.setPen(QPen(color, 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        cx = w * 0.5
        span = 26.0
        if speed > 0:
            y = h - 54.0
            painter.drawLine(QPointF(cx - span, y - 8.0), QPointF(cx, y))
            painter.drawLine(QPointF(cx, y), QPointF(cx + span, y - 8.0))
            painter.drawLine(QPointF(cx, y + 10.0), QPointF(cx, y + 2.0))
        else:
            y = 54.0
            painter.drawLine(QPointF(cx - span, y + 8.0), QPointF(cx, y))
            painter.drawLine(QPointF(cx, y), QPointF(cx + span, y + 8.0))
            painter.drawLine(QPointF(cx, y - 10.0), QPointF(cx, y - 2.0))
        painter.restore()

    def _paint_help_modal(self, painter: QPainter, w: float, h: float) -> None:
        """Paints a wrapped, height-fitted gesture and shortcut cheat sheet."""
        painter.fillRect(QRectF(0, 0, w, h), QColor(10, 15, 29, 230))
        layout = self._help_modal_layout(w, h)
        card = layout["card"]
        columns = layout["columns"]
        col_w = layout["col_w"]
        self.help_modal_rect = card

        painter.setBrush(QBrush(QColor(10, 15, 29, 252)))
        painter.setPen(QPen(QColor(59, 130, 246, 200), 1.5))
        painter.drawRoundedRect(card, 12.0, 12.0)
        painter.save()
        painter.setClipRect(card.adjusted(2.0, 2.0, -2.0, -2.0))

        icon_rect = QRectF(card.x() + 24.0, card.y() + 18.0, 28.0, 28.0)
        IconManager.instance().render_icon(painter, "help", icon_rect)
        painter.setFont(self._font_modal_title)
        painter.setPen(QColor(248, 250, 252))
        painter.drawText(
            QRectF(card.x() + 60.0, card.y() + 12.0, card.width() - 84.0, 32.0),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            | Qt.TextFlag.TextWordWrap,
            "GUÍA RÁPIDA DE GESTOS Y ATAJOS",
        )
        painter.setFont(self._font_modal_subtitle)
        painter.setPen(QColor(148, 163, 184))
        painter.drawText(
            QRectF(card.x() + 60.0, card.y() + 44.0, card.width() - 84.0, 30.0),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
            | Qt.TextFlag.TextWordWrap,
            "Control asistivo integral manos libres mediante seguimiento ocular y gestos faciales",
        )
        painter.setPen(QPen(QColor(30, 41, 59, 200), 1.0))
        painter.drawLine(int(card.x() + 24.0), int(card.y() + 76.0),
                         int(card.right() - 24.0), int(card.y() + 76.0))

        # Column 1: gestures.
        gesture_col = columns[0]
        painter.setBrush(QBrush(QColor(15, 23, 42, 210)))
        painter.setPen(QPen(QColor(59, 130, 246, 120), 1.0))
        painter.drawRoundedRect(gesture_col, 8.0, 8.0)
        painter.setFont(self._font_modal_section)
        painter.setPen(QColor(96, 165, 250))
        painter.drawText(
            QRectF(gesture_col.x() + 14.0, gesture_col.y() + 8.0, col_w - 28.0, 22.0),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            "GESTOS FACIALES Y OCULARES",
        )
        y = gesture_col.y() + 36.0
        for title, action, desc, title_h, action_h, desc_h, row_h in layout["gesture_rows"]:
            painter.setFont(self._font_modal_item_title)
            painter.setPen(QColor(253, 224, 71))
            painter.drawText(
                QRectF(gesture_col.x() + 14.0, y, col_w - 28.0, title_h),
                Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap, title)
            painter.setFont(self._font_modal_item_desc)
            painter.setPen(QColor(52, 211, 153))
            painter.drawText(
                QRectF(gesture_col.x() + 14.0, y + title_h, col_w - 28.0, action_h),
                Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap, f"• {action}")
            painter.setPen(QColor(148, 163, 184))
            painter.drawText(
                QRectF(gesture_col.x() + 14.0, y + title_h + action_h,
                       col_w - 28.0, max(14.0, desc_h)),
                Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap, desc)
            y += row_h

        # Columns 2-3: shortcuts split evenly, each row wrapped.
        shortcut_titles = ("ATAJOS DE TECLADO", "MÁS ATAJOS")
        for col_index, (rows, _total) in enumerate(layout["shortcut_columns"], start=1):
            column = columns[col_index]
            painter.setBrush(QBrush(QColor(15, 23, 42, 210)))
            painter.setPen(QPen(QColor(30, 41, 59, 200), 1.0))
            painter.drawRoundedRect(column, 8.0, 8.0)
            painter.setFont(self._font_modal_section)
            painter.setPen(QColor(148, 163, 184))
            painter.drawText(
                QRectF(column.x() + 14.0, column.y() + 8.0, col_w - 28.0, 22.0),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                shortcut_titles[col_index - 1],
            )
            row_y = column.y() + 36.0
            for key, name, desc, desc_h, row_h in rows:
                painter.setFont(self._font_modal_item_title)
                painter.setPen(QColor(248, 113, 113))
                painter.drawText(
                    QRectF(column.x() + 14.0, row_y, col_w - 28.0, 16.0),
                    Qt.AlignmentFlag.AlignLeft,
                    QFontMetrics(self._font_modal_item_title).elidedText(
                        key, Qt.TextElideMode.ElideRight, int(col_w - 28.0)),
                )
                painter.setPen(QColor(241, 245, 249))
                painter.drawText(
                    QRectF(column.x() + 14.0, row_y + 16.0, col_w - 28.0, 16.0),
                    Qt.AlignmentFlag.AlignLeft,
                    QFontMetrics(self._font_modal_item_title).elidedText(
                        name, Qt.TextElideMode.ElideRight, int(col_w - 28.0)),
                )
                painter.setFont(self._font_modal_item_desc)
                painter.setPen(QColor(148, 163, 184))
                painter.drawText(
                    QRectF(column.x() + 14.0, row_y + 32.0,
                           col_w - 28.0, max(14.0, desc_h)),
                    Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap, desc)
                row_y += row_h

        painter.restore()

        self._update_help_modal_rect()
        if getattr(self, "hovered_help_modal_guide", False):
            painter.setBrush(QBrush(QColor(37, 99, 235, 90)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(self.help_modal_guide_rect.adjusted(-4.0, -4.0, 4.0, 4.0), 10.0, 10.0)
            guide_brush = QBrush(QColor(29, 78, 216, 245))
            guide_pen = QPen(QColor(191, 219, 254), 2.0)
        else:
            guide_brush = QBrush(QColor(30, 41, 59, 220))
            guide_pen = QPen(QColor(59, 130, 246, 160), 1.0)
        painter.setBrush(guide_brush)
        painter.setPen(guide_pen)
        painter.drawRoundedRect(self.help_modal_guide_rect, 8.0, 8.0)
        painter.setFont(self._font_modal_close)
        painter.setPen(QColor(245, 243, 255))
        painter.drawText(
            self.help_modal_guide_rect,
            Qt.AlignmentFlag.AlignCenter,
            " ABRIR MANUAL INTERACTIVO",
        )

        if getattr(self, "hovered_help_modal_tutorial", False):
            painter.setBrush(QBrush(QColor(37, 99, 235, 90)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(self.help_modal_tutorial_rect.adjusted(-4.0, -4.0, 4.0, 4.0), 10.0, 10.0)
            tut_brush = QBrush(QColor(37, 99, 235, 245))
            tut_pen = QPen(QColor(191, 219, 254), 2.0)
        else:
            tut_brush = QBrush(QColor(30, 41, 59, 220))
            tut_pen = QPen(QColor(59, 130, 246, 160), 1.0)
        painter.setBrush(tut_brush)
        painter.setPen(tut_pen)
        painter.drawRoundedRect(self.help_modal_tutorial_rect, 8.0, 8.0)
        painter.setFont(self._font_modal_close)
        painter.setPen(QColor(240, 249, 255))
        painter.drawText(
            self.help_modal_tutorial_rect,
            Qt.AlignmentFlag.AlignCenter,
            "INICIAR TUTORIAL (F2)",
        )

        if getattr(self, "hovered_help_modal_close", False):
            painter.setBrush(QBrush(QColor(16, 185, 129, 70)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(self.help_modal_close_rect.adjusted(-4.0, -4.0, 4.0, 4.0), 10.0, 10.0)
            close_brush = QBrush(QColor(16, 185, 129, 245))
            close_pen = QPen(QColor(209, 250, 229), 2.0)
        else:
            close_brush = QBrush(QColor(6, 78, 59, 220))
            close_pen = QPen(QColor(16, 185, 129, 180), 1.0)
        painter.setBrush(close_brush)
        painter.setPen(close_pen)
        painter.drawRoundedRect(self.help_modal_close_rect, 8.0, 8.0)
        painter.setFont(self._font_modal_close)
        painter.setPen(QColor(236, 253, 245))
        painter.drawText(
            self.help_modal_close_rect,
            Qt.AlignmentFlag.AlignCenter,
            "CERRAR GUÍA (Mire aquí o abra la boca)",
        )

    def closeEvent(self, event) -> None:
        """Safely stops background code injector and AI worker threads on window close without terminate()."""
        if self._right_margin_animation is not None:
            try:
                self._right_margin_animation.stop()
            except Exception:
                pass
            self._right_margin_animation = None
        if hasattr(self, "ai_predictor_worker") and self.ai_predictor_worker is not None:
            try:
                if self.ai_predictor_worker.isRunning():
                    self.ai_predictor_worker.stop()
                    self.ai_predictor_worker.wait(2000)
            except Exception:
                pass
        try:
            self.release_all_game_keys()
        except Exception:
            pass
        if hasattr(self, "code_injector") and self.code_injector is not None:
            self.code_injector.stop()
        super().closeEvent(event)
