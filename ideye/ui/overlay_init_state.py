"""Construction of window state and subsystems."""

from ideye.ui.overlay_common import *  # noqa: F401,F403


class OverlayInitStateMixin:
    """Construction of window state and subsystems."""

    def _init_part01(self):
        app_icon = IconManager.instance().get_app_icon()
        if not app_icon.isNull():
            self.setWindowIcon(app_icon)

    def _init_part02(self):
        # Win32 OS-level non-activation protection
        if sys.platform == "win32":
            self._apply_win32_no_activate()

    def _init_part03(self, code_injector, context_reader, menu_tree, mode_manager):
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

    def _init_part04(self):
        # One accent for the whole HUD; the mode's own color is only a small dot.
        self.theme_color: str = ACCENT_HEX
        self.mode_color: str = (
            getattr(self.mode_manager, "current_mode", None).theme_color
            if getattr(self.mode_manager, "current_mode", None) is not None
            else ACCENT_HEX
        )
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

    def _init_part05(self, macro_manager):
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

    def _init_part06(self):
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

    def _init_part07(self, start_in_mode_selector):
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
            self._mode_banner_text = "Elige un modo"
            try:
                self._mode_banner_start = time.time()
                self._mode_banner_until = self._mode_banner_start + 3.0
            except Exception:
                self._mode_banner_until = 0.0

    def _init_part08(self):
        # 3. State tracking
        self.reading_mode: bool = False
        self.current_opacity: float = config.OVERLAY_OPACITY_ACTIVE
        self.hovered_block: Optional[int] = None
        self.active_click_block: Optional[int] = None
        self.current_gaze: Tuple[float, float] = (0.5, 0.5)
        self.gaze_scroller = GazeScroller()
        self._gaze_scroll_enabled: bool = bool(getattr(config, "GAZE_SCROLL_ENABLED", True))
        self.ghost_peek_enabled: bool = bool(getattr(config, "GHOST_PEEK_ENABLED", True))
        self.reduced_motion: bool = bool(getattr(config, "REDUCED_MOTION", False))
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

    def _init_part09(self):
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
