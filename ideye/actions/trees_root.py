"""Root menu tree assembly (build_menu_tree) and command palette."""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple, Set, Union, Any

try:
    from ideye.actions.language_support import (
        LANG_PYTHON,
        LANG_TYPESCRIPT,
        LANG_RUST,
        LANG_CPP,
        LANG_GO,
        SUPPORTED_LANGUAGES,
        LANGUAGE_DISPLAY_NAMES,
        LANGUAGE_BADGES,
        normalize_language,
        get_language_display_name,
        get_language_badge,
    )
except ImportError:
    from actions.language_support import (
        LANG_PYTHON,
        LANG_TYPESCRIPT,
        LANG_RUST,
        LANG_CPP,
        LANG_GO,
        SUPPORTED_LANGUAGES,
        LANGUAGE_DISPLAY_NAMES,
        LANGUAGE_BADGES,
        normalize_language,
        get_language_display_name,
        get_language_badge,
    )

from ideye.actions.trees_model import *  # noqa: F401,F403
from ideye.actions.trees_populators import *  # noqa: F401,F403
from ideye.actions.trees_adaptive import *  # noqa: F401,F403
from ideye.actions.trees_builders import (  # noqa: F401
    _build_flow_items,
    _build_flow_try_items,
    _build_struct_items,
    _build_struct_import_items,
    _build_op_items,
    _build_op_logical_items,
    _build_op_delim_items,
    _build_op_punct_items,
)

def build_menu_tree(language: str = "PYTHON") -> Dict[str, MenuNode]:
    """
    Constructs and returns the full hierarchical menu tree for IDEye Phase 5.
    Dynamically tailors syntax constructs, operators, snippets, and identifiers
    to the active programming language (Python, TypeScript, Rust, C++, Go).
    Guarantees every node has exactly 9 items, Index 4 is Pause, and Index 6 in submenus is Back.
    """
    tree: Dict[str, MenuNode] = {}
    lang = normalize_language(language)

    # =========================================================================
    # 1. ROOT MENU (Nivel 1)
    # =========================================================================
    root_items = [
        MenuAction(
            id="INSERT_IF_ELSE",
            label="1: Lógica y control",
            hint="Condiciones, bucles y bloques",
            action_type="SUBMENU",
            submenu_id="FLOW",
            icon="flow",
        ),
        MenuAction(
            id="INSERT_LOOP",
            label="2: Funciones y clases",
            hint="Funciones, tipos, clases e imports",
            action_type="SUBMENU",
            submenu_id="STRUCT",
            icon="function",
        ),
        MenuAction(
            id="INSERT_OPERATORS",
            label="3: Símbolos",
            hint="Operadores, paréntesis y corchetes",
            action_type="SUBMENU",
            submenu_id="OPERATORS",
            icon="operators",
        ),
        MenuAction(
            id="INSERT_VARS",
            label="4: Mover el cursor",
            hint="Flechas, Inicio y Fin (fijo)",
            action_type="SUBMENU",
            submenu_id="NAV",
            icon="navigation",
        ),
        create_pause_action("5"),
        MenuAction(
            id="ACTION_KEYWORDS",
            label="6: Palabras clave",
            hint="Estructuras y palabras clave completas",
            action_type="SUBMENU",
            submenu_id="KEYWORDS",
            icon="variables",
        ),
        MenuAction(
            id="ACTION_BACKSPACE",
            label="7: Borrar y deshacer",
            hint="Borrar, deshacer y rehacer (fijo)",
            action_type="SUBMENU",
            submenu_id="EDIT",
            icon="edit",
        ),
        MenuAction(
            id="ACTION_ENTER_TAB",
            label="8: Espacios y saltos",
            hint="Enter, Tab y espacios (fijo)",
            action_type="SUBMENU",
            submenu_id="FORMAT",
            icon="format",
        ),
        MenuAction(
            id="MENU_SNIPPETS",
            label="9: Sugerencias",
            hint="Ideas de código y plantillas",
            action_type="SUBMENU",
            submenu_id="SNIPPETS",
            icon="ai_spark",
        ),
    ]

    tree["ROOT"] = MenuNode(
        id="ROOT",
        title="RAÍZ",
        breadcrumb_label="RAÍZ",
        items=root_items,
        parent_id=None,
        sticky=False,
    )

    # =========================================================================
    # 2. FLOW / LOGIC SUBMENUS
    # =========================================================================
    tree["FLOW"] = MenuNode(
        id="FLOW",
        title="FLUJO / LÓGICA",
        breadcrumb_label="FLUJO",
        items=_build_flow_items(lang),
        parent_id="ROOT",
        sticky=False,
    )

    tree["FLOW_TRY_RET"] = MenuNode(
        id="FLOW_TRY_RET",
        title="TRY / RETURN",
        breadcrumb_label="TRY/RET",
        items=_build_flow_try_items(lang),
        parent_id="FLOW",
        sticky=False,
    )

    # =========================================================================
    # 3. STRUCTURES / FUNCTIONS SUBMENUS
    # =========================================================================
    tree["STRUCT"] = MenuNode(
        id="STRUCT",
        title="ESTRUCTURAS / FUNC",
        breadcrumb_label="ESTRUCTURAS",
        items=_build_struct_items(lang),
        parent_id="ROOT",
        sticky=False,
    )

    tree["STRUCT_IMPORT"] = MenuNode(
        id="STRUCT_IMPORT",
        title="IMPORTACIONES",
        breadcrumb_label="IMPORT",
        items=_build_struct_import_items(lang),
        parent_id="STRUCT",
        sticky=False,
    )

    # =========================================================================
    # 4. OPERATORS / SYMBOLS SUBMENUS
    # =========================================================================
    tree["OPERATORS"] = MenuNode(
        id="OPERATORS",
        title="OPERADORES / SÍMBOLOS",
        breadcrumb_label="OPERADORES",
        items=_build_op_items(lang),
        parent_id="ROOT",
        sticky=False,
    )

    tree["OP_LOGICAL"] = MenuNode(
        id="OP_LOGICAL",
        title="LÓGICOS & COMPARADORES",
        breadcrumb_label="LÓGICOS",
        items=_build_op_logical_items(lang),
        parent_id="OPERATORS",
        sticky=False,
    )

    tree["OP_DELIMITERS"] = MenuNode(
        id="OP_DELIMITERS",
        title="DELIMITADORES & PARES",
        breadcrumb_label="DELIMITADORES",
        items=_build_op_delim_items(lang),
        parent_id="OPERATORS",
        sticky=False,
    )

    tree["OP_PUNCT"] = MenuNode(
        id="OP_PUNCT",
        title="PUNTUACIÓN & SÍMBOLOS",
        breadcrumb_label="PUNTUACIÓN",
        items=_build_op_punct_items(lang),
        parent_id="OPERATORS",
        sticky=False,
    )

    # =========================================================================
    # 5. CURSOR NAVIGATION (STICKY SUBMENU)
    # =========================================================================
    nav_items = [
        MenuAction(id="NAV_UP", label="1: Arriba", hint="Flecha Arriba", action_type="KEY", key_name="UP", sticky=True, icon="navigation"),
        MenuAction(id="NAV_DOWN", label="2: Abajo", hint="Flecha Abajo", action_type="KEY", key_name="DOWN", sticky=True, icon="navigation"),
        MenuAction(id="NAV_LEFT", label="3: Izquierda", hint="Flecha Izquierda", action_type="KEY", key_name="LEFT", sticky=True, icon="navigation"),
        MenuAction(id="NAV_RIGHT", label="4: Derecha", hint="Flecha Derecha", action_type="KEY", key_name="RIGHT", sticky=True, icon="navigation"),
        create_pause_action("5"),
        MenuAction(id="NAV_HOME", label="6: Inicio Línea", hint="Tecla Home / Inicio", action_type="KEY", key_name="HOME", sticky=True, icon="navigation"),
        create_back_action("ROOT", "7"),
        MenuAction(id="NAV_END", label="8: Fin Línea", hint="Tecla End / Fin", action_type="KEY", key_name="END", sticky=True, icon="navigation"),
        MenuAction(id="NAV_WORD", label="9: Saltar Palabra", hint="Ctrl + Derecha", action_type="KEY", key_name="WORD_RIGHT", sticky=True, icon="navigation"),
    ]

    tree["NAV"] = MenuNode(
        id="NAV",
        title="NAVEGACIÓN CURSOR",
        breadcrumb_label="NAVEGACIÓN",
        items=nav_items,
        parent_id="ROOT",
        sticky=True,
    )

    # =========================================================================
    # 6. EDITING / DELETION (STICKY SUBMENU)
    # =========================================================================
    edit_items = [
        MenuAction(id="EDIT_BACKSPACE", label="1: Borrar Carácter", hint="Backspace", action_type="KEY", key_name="BACKSPACE", sticky=True, icon="edit"),
        MenuAction(id="EDIT_DEL_WORD", label="2: Borrar Palabra", hint="Ctrl + Backspace", action_type="KEY", key_name="CTRL_BACKSPACE", sticky=True, icon="edit"),
        MenuAction(id="EDIT_DEL_LINE", label="3: Borrar Línea", hint="Ctrl+Shift+K", action_type="KEY", key_name="DELETE_LINE", sticky=True, icon="edit"),
        MenuAction(id="EDIT_UNDO", label="4: Deshacer", hint="Ctrl + Z", action_type="KEY", key_name="UNDO", sticky=True, icon="edit"),
        create_pause_action("5"),
        MenuAction(id="EDIT_REDO", label="6: Rehacer", hint="Ctrl + Y", action_type="KEY", key_name="REDO", sticky=True, icon="edit"),
        create_back_action("ROOT", "7"),
        MenuAction(id="EDIT_CLIPBOARD", label="8: PORTAPAPELES", hint="Historial de copias (6)", action_type="SUBMENU", submenu_id="CLIPBOARD_HISTORY", sticky=True, icon="edit"),
        MenuAction(id="ACTION_EXIT_MENU", label="9: SALIR", hint="Cerrar IDEye (Confirmación)", action_type="SUBMENU", submenu_id="EXIT_CONFIRM", icon="exit"),
    ]

    tree["EDIT"] = MenuNode(
        id="EDIT",
        title="EDICIÓN / BORRADO",
        breadcrumb_label="EDICIÓN",
        items=edit_items,
        parent_id="ROOT",
        sticky=True,
    )
    try:
        from ideye.actions.clipboard_history import get_clipboard_history_manager

        tree["CLIPBOARD_HISTORY"] = get_clipboard_history_manager().get_clipboard_menu_node(
            parent_id="EDIT"
        )
    except Exception:
        pass

    # =========================================================================
    # 7. SPACE / FORMATTING (STICKY SUBMENU)
    # =========================================================================
    format_items = [
        MenuAction(id="FMT_ENTER", label="1: ENTER", hint="Salto de línea", action_type="KEY", key_name="ENTER", sticky=True, icon="format"),
        MenuAction(id="FMT_TAB", label="2: TAB", hint="Tabulador / Indentar", action_type="KEY", key_name="TAB", sticky=True, icon="format"),
        MenuAction(id="FMT_UNINDENT", label="3: SHIFT + TAB", hint="Des-indentar", action_type="KEY", key_name="SHIFT_TAB", sticky=True, icon="format"),
        MenuAction(id="FMT_SPACE", label="4: ESPACIO", hint="Barra espaciadora", action_type="KEY", key_name="SPACE", sticky=True, icon="format"),
        create_pause_action("5"),
        MenuAction(id="FMT_2ENTER", label="6: 2x ENTER", hint="Doble salto de línea", action_type="KEY", key_name="ENTER_TWICE", sticky=True, icon="format"),
        create_back_action("ROOT", "7"),
        MenuAction(id="FMT_4SPACES", label="8: 4x ESPACIOS", hint="Indentación manual", action_type="SNIPPET", snippet="    ", sticky=True, icon="format"),
        MenuAction(id="FMT_COLON_ENTER", label="9: : + ENTER", hint="Dos puntos y salto indentado", action_type="SNIPPET", snippet=":\n    ", sticky=True, icon="format"),
    ]

    tree["FORMAT"] = MenuNode(
        id="FORMAT",
        title="ESPACIOS Y SALTOS",
        breadcrumb_label="ESPACIOS",
        items=format_items,
        parent_id="ROOT",
        sticky=True,
    )

    # =========================================================================
    # 8. RAPID SNIPPETS / TEMPLATES & AI PREDICTIONS
    # =========================================================================
    snippets_items = populate_ai_prediction_items(None, parent_id="ROOT", language=lang)

    tree["SNIPPETS"] = MenuNode(
        id="SNIPPETS",
        title="SUGERENCIAS",
        breadcrumb_label="SUGERENCIAS",
        items=snippets_items,
        parent_id="ROOT",
        sticky=False,
    )
    # Alias for AI_PREDICT
    tree["AI_PREDICT"] = tree["SNIPPETS"]

    # =========================================================================
    # 9. LANGUAGE KEYWORDS (complete words, no letter-by-letter submenu)
    # =========================================================================
    keyword_items = [
        MenuAction(id="KW_DEF", label="1: def", hint="Definir función", action_type="SNIPPET", snippet="def ", icon="function"),
        MenuAction(id="KW_CLASS", label="2: class", hint="Definir clase", action_type="SNIPPET", snippet="class ", icon="struct"),
        MenuAction(id="KW_RETURN", label="3: return", hint="Devolver valor", action_type="SNIPPET", snippet="return ", icon="flow"),
        MenuAction(id="KW_IF", label="4: if", hint="Condición", action_type="SNIPPET", snippet="if ", icon="flow"),
        create_pause_action("5"),
        MenuAction(id="KW_FOR", label="6: for", hint="Bucle for", action_type="SNIPPET", snippet="for ", icon="flow"),
        create_back_action("ROOT", "7"),
        MenuAction(id="KW_WHILE", label="8: while", hint="Bucle while", action_type="SNIPPET", snippet="while ", icon="flow"),
        MenuAction(id="KW_IMPORT", label="9: import", hint="Importar módulo", action_type="SNIPPET", snippet="import ", icon="struct"),
    ]
    tree["KEYWORDS"] = MenuNode(
        id="KEYWORDS",
        title="PALABRAS CLAVE",
        breadcrumb_label="PALABRAS",
        items=keyword_items,
        parent_id="ROOT",
        sticky=True,
    )

    # =========================================================================
    # 10. SAFE EXIT CONFIRMATION SUBMENU
    # =========================================================================
    tree["EXIT_CONFIRM"] = MenuNode(
        id="EXIT_CONFIRM",
        title="¿SALIR DE IDEye?",
        breadcrumb_label="CONFIRMAR SALIDA",
        items=populate_exit_confirm_items(parent_id="ROOT"),
        parent_id="ROOT",
        sticky=False,
    )

    # =========================================================================
    # 11. IN-APP GESTURE & SHORTCUT GUIDE MENU (ACCESSIBLE VIA OVERLAY / HUD)
    # =========================================================================
    tree["HELP"] = MenuNode(
        id="HELP",
        title="GUÍA DE GESTOS Y ATAJOS",
        breadcrumb_label="AYUDA / GESTOS",
        items=populate_help_items(parent_id="ROOT"),
        parent_id="ROOT",
        sticky=False,
    )

    # =========================================================================
    # 12. MULTI-LANGUAGE SELECTION MENU (ACCESSIBLE VIA OVERLAY / HEADER)
    # =========================================================================
    tree["LANG_SELECT"] = MenuNode(
        id="LANG_SELECT",
        title="SELECCIONAR LENGUAJE",
        breadcrumb_label="LENGUAJE",
        items=populate_lang_select_items(parent_id="ROOT"),
        parent_id="ROOT",
        sticky=False,
    )

    # =========================================================================
    # 13. GAZE COMMAND PALETTE (SPOTLIGHT)
    # =========================================================================
    tree["COMMAND_PALETTE"] = MenuNode(
        id="COMMAND_PALETTE",
        title="PALETA DE COMANDOS",
        breadcrumb_label="SPOTLIGHT",
        items=populate_command_palette_items(parent_id="ROOT"),
        parent_id="ROOT",
        sticky=False,
    )

    return tree


def populate_command_palette_items(parent_id: str = "ROOT") -> List[MenuAction]:
    """Populates the 9 items for the 3x3 Gaze Command Palette (Spotlight)."""
    return [
        MenuAction("CMD_SAVE", "1: Guardar", "Ctrl+S", "KEY", key_name="SAVE", icon="edit"),
        MenuAction("CMD_FORMAT", "2: Formatear", "Shift+Alt+F", "KEY", key_name="FORMAT", icon="format"),
        MenuAction("CMD_TOGGLE_THEME", "3: Tema HUD", "Conmutar tema", "ACTION", icon="palette"),
        MenuAction("CMD_UNDO", "4: Deshacer", "Ctrl+Z", "KEY", key_name="UNDO", sticky=True, icon="edit"),
        create_pause_action("5"),
        MenuAction("CMD_TERMINAL", "6: Terminal", "Ctrl+`", "KEY", key_name="TERMINAL", icon="terminal"),
        create_back_action(parent_id=parent_id, key_num="7"),
        MenuAction("CMD_SNAP_CARET", "8: Snap Caret", "Micro-calibrar", "ACTION", icon="calibration"),
        MenuAction("CMD_TOGGLE_DOCK", "9: Dock 30% / 100%", "Conmutar layout", "ACTION", icon="grid"),
    ]
