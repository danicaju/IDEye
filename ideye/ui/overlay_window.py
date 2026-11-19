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

from ideye.ui.overlay_common import *  # noqa: F401,F403
from ideye.ui.overlay_common import (  # noqa: F401
    _CHIP_BAND_EXTRA,
    _clean_action_label,
    _menu_card_label,
    _soften_caps,
)
from ideye.ui.overlay_init_state import OverlayInitStateMixin
from ideye.ui.overlay_init_paint import OverlayInitPaintMixin
from ideye.ui.overlay_layout import OverlayLayoutMixin
from ideye.ui.overlay_header import OverlayHeaderMixin
from ideye.ui.overlay_data import OverlayDataMixin
from ideye.ui.overlay_gaze import OverlayGazeMixin
from ideye.ui.overlay_sniper import OverlaySniperMixin
from ideye.ui.overlay_freelook import OverlayFreelookMixin
from ideye.ui.overlay_freelook_click import OverlayFreelookClickMixin
from ideye.ui.overlay_gesture import OverlayGestureMixin
from ideye.ui.overlay_writing import OverlayWritingMixin
from ideye.ui.overlay_actions import OverlayActionsMixin
from ideye.ui.overlay_theme import OverlayThemeMixin
from ideye.ui.overlay_input import OverlayInputMixin
from ideye.ui.overlay_modes import OverlayModesMixin
from ideye.ui.overlay_ghost import OverlayGhostMixin
from ideye.ui.overlay_paint_header import OverlayPaintHeaderMixin
from ideye.ui.overlay_paint_grid import OverlayPaintGridMixin
from ideye.ui.overlay_paint_modals import OverlayPaintModalsMixin


class OverlayWindow(
    OverlayInitStateMixin,
    OverlayInitPaintMixin,
    OverlayLayoutMixin,
    OverlayHeaderMixin,
    OverlayDataMixin,
    OverlayGazeMixin,
    OverlaySniperMixin,
    OverlayFreelookMixin,
    OverlayFreelookClickMixin,
    OverlayGestureMixin,
    OverlayWritingMixin,
    OverlayActionsMixin,
    OverlayThemeMixin,
    OverlayInputMixin,
    OverlayModesMixin,
    OverlayGhostMixin,
    OverlayPaintHeaderMixin,
    OverlayPaintGridMixin,
    OverlayPaintModalsMixin,
    QWidget,
):
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
    reduced_motion_toggled = pyqtSignal(bool)
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
        self._init_body(
            parent, code_injector, menu_tree, context_reader,
            mode_manager, macro_manager, start_in_mode_selector,
        )

    def _init_body(
        self,
        parent,
        code_injector,
        menu_tree,
        context_reader,
        mode_manager,
        macro_manager,
        start_in_mode_selector,
    ) -> None:
        """Builds state, subsystems and pre-allocated paint objects."""
        self._init_part01()
        self._init_part02()
        self._init_part03(code_injector, context_reader, menu_tree, mode_manager)
        self._init_part04()
        self._init_part05(macro_manager)
        self._init_part06()
        self._init_part07(start_in_mode_selector)
        self._init_part08()
        self._init_part09()
        self._init_part10()
        self._init_part11()
        self._init_part12()
        self._init_part13()
        self._init_part14()
        self._init_part15()
        self._init_part16()


    # ------------------------------------------------------------------ #
    # Phase 7: sound feedback
    # ------------------------------------------------------------------ #

    # ------------------------------------------------------------------ #
    # Phase 7.5: FreeLook / direct OS mouse
    # ------------------------------------------------------------------ #


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
