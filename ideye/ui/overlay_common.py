"""Shared imports, constants and helpers for the overlay window modules."""


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
from ideye.ui.design_tokens import (
    ACCENT_HEX,
    INACTIVE_OUTLINE_ALPHA,
    MOTION_FOCUS_MS,
    RADIUS_L,
    RADIUS_S,
    duration,
)

# Extra header-band height reserved for the command-preview chip row.
_CHIP_BAND_EXTRA = 28.0

logger = get_logger(__name__)

def _clean_action_label(label: str) -> str:
    """Removes the numeric slot prefix from a menu label for status messages.

    Example: ``"8: Espacios y saltos"`` -> ``"Espacios y saltos"``.
    """
    head, sep, tail = (label or "").partition(": ")
    if sep and head.strip().isdigit():
        return tail
    return label or ""


def _soften_caps(text: str) -> str:
    """Turns SHOUTED menu labels into sentence case, keeping short acronyms (SQL, JSON)."""
    words = text.split(" ")
    if not any(len(w) > 4 and w.isupper() for w in words):
        return text
    small = {"Y", "E", "O", "U", "A", "DE", "EN", "EL", "LA", "AL", "DEL", "CON", "POR", "LOS", "LAS"}
    out = [
        w.lower() if w.isupper() and (len(w) > 4 or w in small) else w
        for w in words
    ]
    if out and out[0] and out[0][0].isalpha():
        out[0] = out[0][0].upper() + out[0][1:]
    return " ".join(out)


def _menu_card_label(item) -> str:
    """Returns the human-facing card label, never the internal icon id.

    Icon identifiers such as ``format`` or ``ai_spark`` are implementation
    details and must not leak into the HUD text.
    """
    return getattr(item, "label", "") or ""


MODE_SHORT_LABELS = {
    "coding": "Código",
    "writing": "Redacción",
    "terminal": "Terminal",
    "data_math": "Datos",
    "navigation": "Navegación",
    "sniper": "FreeLook",
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
