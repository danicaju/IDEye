"""
IDEye - IDE Navigation / Reading Context Mode (Phase 6)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from eyede.actions.menu_trees import MenuAction, MenuNode

try:
    from eyede.modes._helpers import make_root, make_submenu
except ImportError:  # pragma: no cover
    from modes._helpers import make_root, make_submenu

from .base_mode import BaseMode


def _act(slot, aid, label, snippet=None, key_name=None, action_type="SNIPPET"):
    ma = MenuAction(id=aid, label=f"{slot}: {label}", hint=label, action_type=action_type, snippet=snippet, key_name=key_name, icon="")
    if key_name:
        ma.action_type = "KEY"
        ma.snippet = None
    return ma


class IdeNavMode(BaseMode):
    mode_id = "navigation"
    display_name = "LECTURA / IDE"
    theme_color = "#E2E8F0"

    def get_menu_tree(self, language: Optional[str] = None) -> Dict[str, MenuNode]:
        tree: Dict[str, MenuNode] = {}

        scroll = [
            _act("1", "N_SCROLL_UP", "Scroll arriba", None, key_name="PAGE_UP"),
            _act("2", "N_SCROLL_DOWN", "Scroll abajo", None, key_name="PAGE_DOWN"),
            _act("3", "N_SCROLL_TOP", "Ir arriba", None, key_name="CTRL_HOME"),
            _act("4", "N_SCROLL_BOTTOM", "Ir abajo", None, key_name="CTRL_END"),
            _act("6", "N_LINE_UP", "Línea arriba", None, key_name="UP"),
            _act("8", "N_LINE_DOWN", "Línea abajo", None, key_name="DOWN"),
            _act("9", "N_CENTER", "Centrar cursor", None, key_name="CTRL_L"),
        ]
        tree["NAV_SCROLL"] = make_submenu("NAV_SCROLL", "SCROLL", scroll)

        goto = [
            _act("1", "N_GOTO_DEF", "Ir a definición (F12)", None, key_name="F12"),
            _act("2", "N_GO_BACK", "Volver posición (Alt+←)", None, key_name="ALT_LEFT"),
            _act("3", "N_GO_FWD", "Adelante (Alt+→)", None, key_name="ALT_RIGHT"),
            _act("4", "N_NEXT_ERR", "Siguiente error", None, key_name="F8"),
            _act("6", "N_PREV_ERR", "Error anterior", None, key_name="SHIFT_F8"),
            _act("8", "N_REVEAL", "Revelar en explorer", None, key_name="ALT_SHIFT_O"),
            _act("9", "N_SYMBOLS", "Ir a símbolo", None, key_name="CTRL_SHIFT_O"),
        ]
        tree["NAV_GOTO"] = make_submenu("NAV_GOTO", "IR A", goto)

        tabs = [
            _act("1", "N_TAB_NEXT", "Pestaña siguiente", None, key_name="CTRL_TAB"),
            _act("2", "N_TAB_PREV", "Pestaña anterior", None, key_name="CTRL_SHIFT_TAB"),
            _act("3", "N_CLOSE_TAB", "Cerrar pestaña", None, key_name="CTRL_W"),
            _act("4", "N_REOPEN_TAB", "Reabrir pestaña", None, key_name="CTRL_SHIFT_T"),
            _act("6", "N_SPLIT", "Dividir editor", None, key_name="CTRL_BACKSLASH"),
            _act("8", "N_FOCUS_SIDE", "Enfocar lateral", None, key_name="CTRL_1"),
            _act("9", "N_ZOOM", "Zoom", None, key_name="CTRL_PLUS"),
        ]
        tree["NAV_TABS"] = make_submenu("NAV_TABS", "PESTAÑAS", tabs)

        search = [
            _act("1", "N_FIND", "Buscar (Ctrl+F)", None, key_name="CTRL_F"),
            _act("2", "N_FIND_NEXT", "Siguiente coincidencia", None, key_name="F3"),
            _act("3", "N_FIND_PREV", "Anterior coincidencia", None, key_name="SHIFT_F3"),
            _act("4", "N_REPLACE", "Reemplazar", None, key_name="CTRL_H"),
            _act("6", "N_GLOBAL_SEARCH", "Buscar en archivos", None, key_name="CTRL_SHIFT_F"),
            _act("8", "N_GLOBAL_REPLACE", "Reemplazar global", None, key_name="CTRL_SHIFT_H"),
            _act("9", "N_CLOSE_SEARCH", "Cerrar búsqueda", None, key_name="ESC"),
        ]
        tree["NAV_SEARCH"] = make_submenu("NAV_SEARCH", "BÚSQUEDA", search)

        fold = [
            _act("1", "N_FOLD", "Plegar bloque", None, key_name="CTRL_SHIFT_LBRACKET"),
            _act("2", "N_UNFOLD", "Desplegar bloque", None, key_name="CTRL_SHIFT_RBRACKET"),
            _act("3", "N_FOLD_ALL", "Plegar todo", None, key_name="CTRL_K_CTRL_0"),
            _act("4", "N_UNFOLD_ALL", "Desplegar todo", None, key_name="CTRL_K_CTRL_J"),
            _act("6", "N_TOGGLE_FOLD", "Alternar plegado", None, key_name="CTRL_K_CTRL_L"),
            _act("8", "N_RECURSIVE_FOLD", "Plegado recursivo", None, key_name="CTRL_K_CTRL_LBRACKET"),
            _act("9", "N_RECURSIVE_UNFOLD", "Desplegado recursivo", None, key_name="CTRL_K_CTRL_RBRACKET"),
        ]
        tree["NAV_FOLD"] = make_submenu("NAV_FOLD", "PLEGAR / DESPLEGAR", fold)

        terminal = [
            _act("1", "N_TOGGLE_TERM", "Abrir/cerrar terminal", None, key_name="CTRL_BACKTICK"),
            _act("2", "N_NEW_TERM", "Nueva terminal", None, key_name="CTRL_SHIFT_BACKTICK"),
            _act("3", "N_FOCUS_TERM", "Enfocar terminal", None, key_name="CTRL_BACKTICK"),
            _act("4", "N_KILL_TERM", "Matar terminal", None, key_name="CTRL_C"),
            _act("6", "N_CLEAR_TERM", "Limpiar terminal", None, key_name="CTRL_L"),
            _act("8", "N_SCROLL_TERM", "Scroll terminal", None, key_name="SHIFT_PAGE_UP"),
            _act("9", "N_COPY_TERM", "Copiar terminal", None, key_name="CTRL_SHIFT_C"),
        ]
        tree["NAV_TERMINAL"] = make_submenu("NAV_TERMINAL", "TERMINAL", terminal)

        delete = [
            _act("1", "N_UNDO", "Deshacer", None, key_name="CTRL_Z"),
            _act("2", "N_REDO", "Rehacer", None, key_name="CTRL_Y"),
            _act("3", "N_SAVE", "Guardar", None, key_name="CTRL_S"),
            _act("4", "N_FORMAT", "Formatear", None, key_name="SHIFT_ALT_F"),
            _act("6", "N_RENAME", "Renombrar símbolo", None, key_name="F2"),
            _act("8", "N_QUICK_FIX", "Quick fix", None, key_name="CTRL_DOT"),
            _act("9", "N_COMMAND_PALETTE", "Paleta de comandos", None, key_name="CTRL_SHIFT_P"),
        ]
        tree["NAV_EDIT"] = make_submenu("NAV_EDIT", "EDICIÓN / IDE", delete)

        ai = [
            _act("1", "N_AI_EXPLAIN", "Explicar código", "explicar el código seleccionado"),
            _act("2", "N_AI_FIND", "Buscar referencias", "find references"),
            _act("3", "N_AI_RENAME", "Renombrar sugerido", "rename symbol"),
            _act("4", "N_AI_TESTS", "Generar tests", "generate tests"),
            _act("6", "N_AI_DOCS", "Generar docs", "generate documentation"),
            _act("8", "N_AI_REFACTOR", "Refactorizar", "refactor code"),
            _act("9", "N_AI_OPTIMIZE", "Optimizar", "optimize performance"),
        ]
        tree["NAV_AI"] = make_submenu("NAV_AI", "IA NAVEGACIÓN", ai)

        root_items = [
            MenuAction("NAV_SCROLL", "1: SCROLL", "Scroll y navegación", "SUBMENU", submenu_id="NAV_SCROLL", icon="navigation"),
            MenuAction("NAV_GOTO", "2: IR A", "Ir a definición", "SUBMENU", submenu_id="NAV_GOTO", icon="navigation"),
            MenuAction("NAV_TABS", "3: PESTAÑAS", "Gestión de pestañas", "SUBMENU", submenu_id="NAV_TABS", icon="navigation"),
            MenuAction("NAV_SEARCH", "4: BÚSQUEDA", "Buscar y reemplazar", "SUBMENU", submenu_id="NAV_SEARCH", icon="navigation"),
            None,
            MenuAction("NAV_FOLD", "6: PLEGAR", "Plegar y desplegar", "SUBMENU", submenu_id="NAV_FOLD", icon="navigation"),
            MenuAction("NAV_TERMINAL", "7: TERMINAL", "Terminal integrada", "SUBMENU", submenu_id="NAV_TERMINAL", icon="navigation"),
            MenuAction("NAV_EDIT", "8: EDICIÓN / IDE", "Edición y comandos", "SUBMENU", submenu_id="NAV_EDIT", icon="navigation"),
            MenuAction("NAV_AI", "9: IA NAVEGACIÓN", "IA para navegación", "SUBMENU", submenu_id="NAV_AI", icon="ai_spark"),
        ]
        from eyede.actions.menu_trees import create_pause_action
        root_items[4] = create_pause_action("5")
        root = make_root("LECTURA / IDE", root_items)
        tree["ROOT"] = root
        return tree

    def get_root_menu(self, language: Optional[str] = None) -> MenuNode:
        return self.get_menu_tree(language)["ROOT"]

    def get_ai_system_prompt(self, context_data: Optional[Dict[str, Any]] = None) -> str:
        return (
            "You are an IDE navigation assistant for a disabled programmer using eye-tracking. "
            "Suggest navigation commands, search, refactoring, and code understanding actions. "
            "Return ONLY a JSON array of exactly 6 strings."
        )

    def get_heuristic_predictions(
        self, context_data: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        return [
            "Ir a definición (F12)",
            "Volver posición (Alt+←)",
            "Buscar en archivos (Ctrl+Shift+F)",
            "Plegar bloque",
            "Abrir terminal (Ctrl+`)",
            "Paleta de comandos (Ctrl+Shift+P)",
        ]


NavigationMode = IdeNavMode
NavMode = IdeNavMode
IDE_NAV_MODE = IdeNavMode
Navigation = IdeNavMode
ReadMode = IdeNavMode
IdeNav = IdeNavMode
NAVIGATION_MODE = IdeNavMode
NAVIGATION_READ_MODE = IdeNavMode
IdeNavMode = IdeNavMode
