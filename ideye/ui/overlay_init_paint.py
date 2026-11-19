"""Pre-allocated fonts, pens, brushes and paint caches."""

from ideye.ui.overlay_common import *  # noqa: F401,F403


class OverlayInitPaintMixin:
    """Pre-allocated fonts, pens, brushes and paint caches."""

    def _init_part10(self):
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

    def _init_part11(self):
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

    def _init_part12(self):
        # Header / command bar styles (Sleek Cyber-Glass)
        self._brush_header_bg = QBrush(QColor(10, 15, 29, 225))
        self._pen_header_border = QPen(QColor(30, 41, 59, 200), 1.0)
        self._pen_header_left = QPen(QColor(148, 163, 184))
        self._pen_header_center = QPen(QColor(248, 113, 113))
        self._pen_header_right = QPen(QColor(96, 165, 250))

    def _init_part13(self):
        # Focus hierarchy: neutral inactive cards, theme-colored active card.
        self._brush_card_inactive = QBrush(QColor(10, 15, 29, 120))
        self._pen_card_inactive = QPen(QColor(148, 163, 184, INACTIVE_OUTLINE_ALPHA), 1.0)
        self._brush_card_active = QBrush(QColor(15, 23, 42, 235))
        self._pen_card_active = QPen(QColor(ACCENT_HEX), 2.0)
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
        self._brush_status_pill = QBrush(QColor(14, 116, 144, 40))
        self._pen_status_pill = QPen(QColor(59, 130, 246, 80), 1.0)
        self._brush_btn_idle = QBrush(QColor(30, 41, 59, 90))
        self._pen_btn_idle = QPen(QColor(30, 41, 59, 180), 1.0)
        self._brush_help_idle = QBrush(QColor(14, 116, 144, 40))
        self._pen_help_idle = QPen(QColor(34, 211, 238, 110), 1.0)
        self._brush_exit_idle = QBrush(QColor(239, 68, 68, 28))
        self._pen_exit_idle = QPen(QColor(239, 68, 68, 105), 1.0)
        self._brush_exit_glow = QBrush(QColor(239, 68, 68, 55))
        self._brush_help_glow = QBrush(QColor(14, 116, 144, 90))
        self._color_exit_text = QColor(254, 202, 202)
        self._color_help_text = QColor(207, 250, 254)
        self._brush_mode_idle = QBrush(QColor(14, 116, 144, 45))
        self._pen_mode_idle = QPen(QColor("#3b82f6"), 1.0)
        self._brush_mode_glow = QBrush(QColor(59, 130, 246, 60))
        self._color_mode_text = QColor(236, 254, 255)

        # Mode indicator pills
        self._brush_pill_edit = QBrush(QColor(16, 185, 129, 220))
        self._brush_pill_read = QBrush(QColor(245, 158, 11, 220))
        self._color_pill_text = QColor(10, 25, 20)

    def _init_part14(self):
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

    def _init_part15(self):
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

    def _init_part16(self):
        # Dynamic reticle: clean center point + thin outer ring + MAR progress arc.
        self._brush_pointer_glow = QBrush(QColor(59, 130, 246, 40))
        self._pen_pointer_ring = QPen(QColor(248, 250, 252, 210), 1.8)
        self._brush_pointer_dot = QBrush(QColor(248, 250, 252, 245))
        self._pen_pointer_progress = QPen(QColor(34, 211, 238), 2.2)
        self._color_progress_cool = QColor(34, 211, 238)
        self._color_progress_warm = QColor(251, 146, 60)
        self._set_theme_color(self.theme_color)
        self._update_header_exit_rect()
