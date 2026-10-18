"""
EyeDE - Hierarchical 3x3 Menu Trees Module (Phase 3)
Defines MenuAction and MenuNode dataclasses, complete 3x3 navigation hierarchy,
sticky mode transitions, and mathematical validation protocol.

Golden Rules of Gaze Ergonomics:
1. Every grid layout has EXACTLY 9 cells (indices 0 to 8).
2. The Center Cell (Index 4) is ALWAYS '👁️ PAUSA / MODO LECTURA' across all menus.
3. In any submenu (Level >= 2), the Bottom-Left Cell (Index 6) is ALWAYS '⬅ VOLVER ATRÁS'.
4. Sticky Submenus (NAV, EDIT, FORMAT) stay active for repetitive actions until 'VOLVER' is chosen.
5. Non-sticky actions automatically return to 'ROOT' after injecting a snippet.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple, Set


@dataclass
class MenuAction:
    """Represents a selectable action or submenu launcher in a 3x3 grid."""
    id: str
    label: str
    hint: str = ""
    action_type: str = "SNIPPET"  # "SNIPPET", "KEY", "SUBMENU", "PAUSE", "BACK", "EXIT"
    snippet: Optional[str] = None
    key_name: Optional[str] = None
    cursor_offset_left: int = 0
    cursor_offset_up: int = 0
    sticky: bool = False
    submenu_id: Optional[str] = None
    icon: str = "⚡"


@dataclass
class MenuNode:
    """Represents a 3x3 grid menu state containing exactly 9 items."""
    id: str
    title: str
    items: List[MenuAction]
    parent_id: Optional[str] = None
    sticky: bool = False
    breadcrumb_label: str = ""

    def __post_init__(self):
        if not self.breadcrumb_label:
            self.breadcrumb_label = self.title


def create_pause_action(key_num: str = "5") -> MenuAction:
    """Returns the standardized Center (Index 4) Pause/Reading Mode action."""
    return MenuAction(
        id="PAUSE_RESUME",
        label=f"{key_num}: PAUSA / LECTURA",
        hint="Zona de Reposo (Mire y Clic)",
        action_type="PAUSE",
        icon="👁️",
        sticky=False,
    )


def create_back_action(parent_id: str = "ROOT", key_num: str = "7") -> MenuAction:
    """Returns the standardized Bottom-Left (Index 6) Back navigation action."""
    return MenuAction(
        id="ACTION_BACK",
        label=f"{key_num}: VOLVER ATRÁS",
        hint="Regresar al nivel anterior",
        action_type="BACK",
        submenu_id=parent_id,
        icon="⬅",
        sticky=False,
    )


def populate_ai_prediction_items(
    predictions: Optional[List[str]] = None,
    parent_id: str = "ROOT",
) -> List[MenuAction]:
    """
    Constructs exactly 9 MenuAction items for the AI prediction menu (SNIPPETS).
    Slots 0, 1, 2, 3, 5, 7: 6 AI suggestions
    Slot 4: Center Pause action
    Slot 6: Back action (to parent_id)
    Slot 8: Regenerate / Refresh action
    """
    safe_preds = list(predictions or [])
    default_fallbacks = [
        'if __name__ == "__main__":\\n    ',
        '[x for x in list]',
        '{k: v for k, v in .items()}',
        'with open("", "r") as f:',
        'try:\\n    \\nfinally:\\n    ',
        '{"": }',
    ]
    for d in default_fallbacks:
        if len(safe_preds) >= 6:
            break
        safe_preds.append(d)

    slot_keys = [("1", 0), ("2", 1), ("3", 2), ("4", 3), ("6", 4), ("8", 5)]
    pred_actions: Dict[int, MenuAction] = {}
    for slot_idx, (key_label, pred_idx) in enumerate(slot_keys):
        pred_text = safe_preds[pred_idx]
        display_label = pred_text.replace("\n", " ").strip()[:24]
        pred_actions[pred_idx] = MenuAction(
            id=f"AI_PRED_{pred_idx + 1}",
            label=f"{key_label}: {display_label}",
            hint="Sugerencia IA / Snippet",
            action_type="SNIPPET",
            snippet=pred_text,
            icon="⚡",
        )

    return [
        pred_actions[0],
        pred_actions[1],
        pred_actions[2],
        pred_actions[3],
        create_pause_action("5"),
        pred_actions[4],
        create_back_action(parent_id, "7"),
        pred_actions[5],
        MenuAction(
            id="AI_REGENERATE",
            label="9: REGENERAR IA",
            hint="Re-ejecutar predicciones contextuales",
            action_type="AI_REFRESH",
            icon="🔄",
        ),
    ]


def populate_local_symbol_items(
    symbols: Optional[List[str]] = None,
    parent_id: str = "T9",
) -> List[MenuAction]:
    """
    Constructs exactly 9 MenuAction items for local symbols (T9_LOCAL_VARS).
    Slots 0, 1, 2, 3, 5, 7, 8: up to 7 distinct user variables/functions
    Slot 4: Center Pause action
    Slot 6: Back action (to parent_id)
    """
    defaults = ["data", "result", "item", "val", "count", "res", "obj"]
    clean_syms = [s for s in (symbols or []) if s and isinstance(s, str)]
    for d in defaults:
        if len(clean_syms) >= 7:
            break
        if d not in clean_syms:
            clean_syms.append(d)

    def _make_action(idx: int, slot_num: str, sym: str) -> MenuAction:
        disp = sym if len(sym) <= 20 else sym[:18] + ".."
        return MenuAction(
            id=f"LVAR_{idx}",
            label=f"{slot_num}: {disp}",
            hint="Variable local",
            action_type="SNIPPET",
            snippet=sym,
            icon="⚡",
        )

    return [
        _make_action(1, "1", clean_syms[0]),
        _make_action(2, "2", clean_syms[1]),
        _make_action(3, "3", clean_syms[2]),
        _make_action(4, "4", clean_syms[3]),
        create_pause_action("5"),
        _make_action(5, "6", clean_syms[4]),
        create_back_action(parent_id, "7"),
        _make_action(6, "8", clean_syms[5]),
        _make_action(7, "9", clean_syms[6]),
    ]


def build_menu_tree() -> Dict[str, MenuNode]:
    """
    Constructs and returns the full hierarchical menu tree for EyeDE Phase 3.
    Guarantees every node has exactly 9 items, Index 4 is Pause, and Index 6 in submenus is Back.
    """
    tree: Dict[str, MenuNode] = {}

    # =========================================================================
    # 1. ROOT MENU (Nivel 1)
    # =========================================================================
    root_items = [
        MenuAction(
            id="INSERT_IF_ELSE",
            label="1: FLUJO / LÓGICA",
            hint="if, elif, else, for, while, try",
            action_type="SUBMENU",
            submenu_id="FLOW",
            icon="📁",
        ),
        MenuAction(
            id="INSERT_LOOP",
            label="2: ESTRUCTURAS / FUNC",
            hint="def, class, import, lambda",
            action_type="SUBMENU",
            submenu_id="STRUCT",
            icon="📁",
        ),
        MenuAction(
            id="INSERT_OPERATORS",
            label="3: OPERADORES / SÍMB",
            hint="=, ==, !=, +, and, (), []",
            action_type="SUBMENU",
            submenu_id="OPERATORS",
            icon="📁",
        ),
        MenuAction(
            id="INSERT_VARS",
            label="4: NAVEGACIÓN CURSOR",
            hint="⬆ ⬇ ⬅ ➡ Home End (Sticky)",
            action_type="SUBMENU",
            submenu_id="NAV",
            icon="📁",
        ),
        create_pause_action("5"),
        MenuAction(
            id="ACTION_T9",
            label="6: TECLADO T9 / IDENT",
            hint="Letras, vars (i, data, self)",
            action_type="SUBMENU",
            submenu_id="T9",
            icon="📁",
        ),
        MenuAction(
            id="ACTION_BACKSPACE",
            label="7: EDICIÓN / BORRADO",
            hint="Borrar, Undo, Redo (Sticky)",
            action_type="SUBMENU",
            submenu_id="EDIT",
            icon="📁",
        ),
        MenuAction(
            id="ACTION_ENTER_TAB",
            label="8: ESPACIO / FORMATO",
            hint="Enter, Tab, Espacio (Sticky)",
            action_type="SUBMENU",
            submenu_id="FORMAT",
            icon="📁",
        ),
        MenuAction(
            id="MENU_SNIPPETS",
            label="9: IA / PREDICCIÓN",
            hint="Predicción contextual y snippets",
            action_type="SUBMENU",
            submenu_id="SNIPPETS",
            icon="⚡",
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
    flow_items = [
        MenuAction(
            id="FLOW_IF",
            label="1: if ...:",
            hint="Condicional if",
            action_type="SNIPPET",
            snippet="if :",
            cursor_offset_left=1,
            icon="⚡",
        ),
        MenuAction(
            id="FLOW_ELIF",
            label="2: elif ...:",
            hint="Condicional elif",
            action_type="SNIPPET",
            snippet="elif :",
            cursor_offset_left=1,
            icon="⚡",
        ),
        MenuAction(
            id="FLOW_ELSE",
            label="3: else:",
            hint="Rama else con salto",
            action_type="SNIPPET",
            snippet="else:\n    ",
            icon="⚡",
        ),
        MenuAction(
            id="FLOW_FOR_RANGE",
            label="4: for i in range():",
            hint="Bucle indexado",
            action_type="SNIPPET",
            snippet="for i in range():",
            cursor_offset_left=2,
            icon="⚡",
        ),
        create_pause_action("5"),
        MenuAction(
            id="FLOW_FOR_LIST",
            label="6: for x in lista:",
            hint="Iterador de colección",
            action_type="SNIPPET",
            snippet="for x in :",
            cursor_offset_left=1,
            icon="⚡",
        ),
        create_back_action("ROOT", "7"),
        MenuAction(
            id="FLOW_WHILE",
            label="8: while ...:",
            hint="Bucle while",
            action_type="SNIPPET",
            snippet="while :",
            cursor_offset_left=1,
            icon="⚡",
        ),
        MenuAction(
            id="FLOW_TRY_RET_SUB",
            label="9: TRY / EXCEPT / RET",
            hint="try-except, return, raise",
            action_type="SUBMENU",
            submenu_id="FLOW_TRY_RET",
            icon="📁",
        ),
    ]

    tree["FLOW"] = MenuNode(
        id="FLOW",
        title="FLUJO / LÓGICA",
        breadcrumb_label="FLUJO",
        items=flow_items,
        parent_id="ROOT",
        sticky=False,
    )

    flow_try_items = [
        MenuAction(
            id="TRY_EXCEPT",
            label="1: try / except",
            hint="Bloque try-except",
            action_type="SNIPPET",
            snippet="try:\n    \nexcept Exception as e:\n    ",
            cursor_offset_up=2,
            icon="⚡",
        ),
        MenuAction(
            id="RET_VAL",
            label="2: return ",
            hint="Retorno con espacio",
            action_type="SNIPPET",
            snippet="return ",
            icon="⚡",
        ),
        MenuAction(
            id="RET_NONE",
            label="3: return None",
            hint="Retorno nulo",
            action_type="SNIPPET",
            snippet="return None",
            icon="⚡",
        ),
        MenuAction(
            id="RET_TRUE",
            label="4: return True",
            hint="Retorno booleano True",
            action_type="SNIPPET",
            snippet="return True",
            icon="⚡",
        ),
        create_pause_action("5"),
        MenuAction(
            id="RET_FALSE",
            label="6: return False",
            hint="Retorno booleano False",
            action_type="SNIPPET",
            snippet="return False",
            icon="⚡",
        ),
        create_back_action("FLOW", "7"),
        MenuAction(
            id="RAISE_EXC",
            label="8: raise Exception",
            hint="Lanzar excepción",
            action_type="SNIPPET",
            snippet='raise Exception("")',
            cursor_offset_left=2,
            icon="⚡",
        ),
        MenuAction(
            id="PASS_STMT",
            label="9: pass",
            hint="Sentencia pass",
            action_type="SNIPPET",
            snippet="pass",
            icon="⚡",
        ),
    ]

    tree["FLOW_TRY_RET"] = MenuNode(
        id="FLOW_TRY_RET",
        title="TRY / RETURN",
        breadcrumb_label="TRY/RET",
        items=flow_try_items,
        parent_id="FLOW",
        sticky=False,
    )

    # =========================================================================
    # 3. STRUCTURES / FUNCTIONS SUBMENUS
    # =========================================================================
    struct_items = [
        MenuAction(
            id="STRUCT_DEF",
            label="1: def func():",
            hint="Definición de función",
            action_type="SNIPPET",
            snippet="def ():",
            cursor_offset_left=3,
            icon="⚡",
        ),
        MenuAction(
            id="STRUCT_CLASS",
            label="2: class Nombre:",
            hint="Definición de clase",
            action_type="SNIPPET",
            snippet="class :",
            cursor_offset_left=1,
            icon="⚡",
        ),
        MenuAction(
            id="STRUCT_IMPORT_SUB",
            label="3: IMPORTAR 📁",
            hint="import, from ... import",
            action_type="SUBMENU",
            submenu_id="STRUCT_IMPORT",
            icon="📁",
        ),
        MenuAction(
            id="STRUCT_LAMBDA",
            label="4: lambda ",
            hint="Función anónima",
            action_type="SNIPPET",
            snippet="lambda : ",
            cursor_offset_left=2,
            icon="⚡",
        ),
        create_pause_action("5"),
        MenuAction(
            id="STRUCT_PRINT",
            label="6: print()",
            hint="Impresión por consola",
            action_type="SNIPPET",
            snippet="print()",
            cursor_offset_left=1,
            icon="⚡",
        ),
        create_back_action("ROOT", "7"),
        MenuAction(
            id="STRUCT_LEN",
            label="8: len()",
            hint="Longitud de contenedor",
            action_type="SNIPPET",
            snippet="len()",
            cursor_offset_left=1,
            icon="⚡",
        ),
        MenuAction(
            id="STRUCT_SUPER",
            label="9: super().__init__()",
            hint="Constructor clase padre",
            action_type="SNIPPET",
            snippet="super().__init__()",
            icon="⚡",
        ),
    ]

    tree["STRUCT"] = MenuNode(
        id="STRUCT",
        title="ESTRUCTURAS / FUNC",
        breadcrumb_label="ESTRUCTURAS",
        items=struct_items,
        parent_id="ROOT",
        sticky=False,
    )

    struct_import_items = [
        MenuAction(
            id="IMP_DIRECT",
            label="1: import ",
            hint="Sentencia import",
            action_type="SNIPPET",
            snippet="import ",
            icon="⚡",
        ),
        MenuAction(
            id="IMP_FROM",
            label="2: from ... import ",
            hint="Importación selectiva",
            action_type="SNIPPET",
            snippet="from  import ",
            cursor_offset_left=8,
            icon="⚡",
        ),
        MenuAction(
            id="IMP_SYS_OS",
            label="3: import sys, os",
            hint="Imports del sistema",
            action_type="SNIPPET",
            snippet="import sys, os\n",
            icon="⚡",
        ),
        MenuAction(
            id="IMP_NUMPY",
            label="4: import numpy as np",
            hint="Import numpy",
            action_type="SNIPPET",
            snippet="import numpy as np\n",
            icon="⚡",
        ),
        create_pause_action("5"),
        MenuAction(
            id="IMP_AS",
            label="6:  as ",
            hint="Alias de módulo",
            action_type="SNIPPET",
            snippet=" as ",
            icon="⚡",
        ),
        create_back_action("STRUCT", "7"),
        MenuAction(
            id="IMP_TYPING",
            label="8: from typing import ",
            hint="Tipado estático",
            action_type="SNIPPET",
            snippet="from typing import ",
            icon="⚡",
        ),
        MenuAction(
            id="IMP_ALL",
            label="9: __all__ = []",
            hint="Exports públicos",
            action_type="SNIPPET",
            snippet="__all__ = []",
            cursor_offset_left=1,
            icon="⚡",
        ),
    ]

    tree["STRUCT_IMPORT"] = MenuNode(
        id="STRUCT_IMPORT",
        title="IMPORTACIONES",
        breadcrumb_label="IMPORT",
        items=struct_import_items,
        parent_id="STRUCT",
        sticky=False,
    )

    # =========================================================================
    # 4. OPERATORS / SYMBOLS SUBMENUS
    # =========================================================================
    op_items = [
        MenuAction(
            id="OP_ASSIGN",
            label="1: =",
            hint="Asignación",
            action_type="SNIPPET",
            snippet=" = ",
            icon="⚡",
        ),
        MenuAction(
            id="OP_EQ",
            label="2: ==",
            hint="Comparación igualdad",
            action_type="SNIPPET",
            snippet=" == ",
            icon="⚡",
        ),
        MenuAction(
            id="OP_NEQ",
            label="3: !=",
            hint="Comparación desigualdad",
            action_type="SNIPPET",
            snippet=" != ",
            icon="⚡",
        ),
        MenuAction(
            id="OP_PLUSEQ",
            label="4: +=",
            hint="Suma acumulativa",
            action_type="SNIPPET",
            snippet=" += ",
            icon="⚡",
        ),
        create_pause_action("5"),
        MenuAction(
            id="OP_LOGICAL_SUB",
            label="6: and / or 📁",
            hint="Operadores lógicos",
            action_type="SUBMENU",
            submenu_id="OP_LOGICAL",
            icon="📁",
        ),
        create_back_action("ROOT", "7"),
        MenuAction(
            id="OP_DELIMITERS_SUB",
            label='8: () [] {} / "" \'\' 📁',
            hint="Delimitadores, llaves y comillas",
            action_type="SUBMENU",
            submenu_id="OP_DELIMITERS",
            icon="📁",
        ),
        MenuAction(
            id="OP_PUNCT_SUB",
            label="9: : / , / . 📁",
            hint="Dos puntos, coma, punto",
            action_type="SUBMENU",
            submenu_id="OP_PUNCT",
            icon="📁",
        ),
    ]

    tree["OPERATORS"] = MenuNode(
        id="OPERATORS",
        title="OPERADORES / SÍMBOLOS",
        breadcrumb_label="OPERADORES",
        items=op_items,
        parent_id="ROOT",
        sticky=False,
    )

    op_logical_items = [
        MenuAction(id="OP_AND", label="1: and", hint="Lógico AND", action_type="SNIPPET", snippet=" and ", icon="⚡"),
        MenuAction(id="OP_OR", label="2: or", hint="Lógico OR", action_type="SNIPPET", snippet=" or ", icon="⚡"),
        MenuAction(id="OP_NOT", label="3: not", hint="Lógico NOT", action_type="SNIPPET", snippet="not ", icon="⚡"),
        MenuAction(id="OP_IN", label="4: in", hint="Pertenencia in", action_type="SNIPPET", snippet=" in ", icon="⚡"),
        create_pause_action("5"),
        MenuAction(id="OP_IS", label="6: is", hint="Identidad is", action_type="SNIPPET", snippet=" is ", icon="⚡"),
        create_back_action("OPERATORS", "7"),
        MenuAction(id="OP_IS_NOT", label="8: is not", hint="Identidad no es", action_type="SNIPPET", snippet=" is not ", icon="⚡"),
        MenuAction(id="OP_NOT_IN", label="9: not in", hint="No pertenencia", action_type="SNIPPET", snippet=" not in ", icon="⚡"),
    ]

    tree["OP_LOGICAL"] = MenuNode(
        id="OP_LOGICAL",
        title="LÓGICOS & COMPARADORES",
        breadcrumb_label="LÓGICOS",
        items=op_logical_items,
        parent_id="OPERATORS",
        sticky=False,
    )

    op_delim_items = [
        MenuAction(id="DELIM_PAREN", label="1: ()", hint="Paréntesis con cursor centrado", action_type="SNIPPET", snippet="()", cursor_offset_left=1, icon="⚡"),
        MenuAction(id="DELIM_BRACKET", label="2: []", hint="Corchetes con cursor centrado", action_type="SNIPPET", snippet="[]", cursor_offset_left=1, icon="⚡"),
        MenuAction(id="DELIM_BRACE", label="3: {}", hint="Llaves con cursor centrado", action_type="SNIPPET", snippet="{}", cursor_offset_left=1, icon="⚡"),
        MenuAction(id="DELIM_DQUOTE", label='4: ""', hint="Comillas dobles centradas", action_type="SNIPPET", snippet='""', cursor_offset_left=1, icon="⚡"),
        create_pause_action("5"),
        MenuAction(id="DELIM_SQUOTE", label="6: ''", hint="Comillas simples centradas", action_type="SNIPPET", snippet="''", cursor_offset_left=1, icon="⚡"),
        create_back_action("OPERATORS", "7"),
        MenuAction(id="DELIM_FSTR", label='8: f""', hint="F-string con cursor centrado", action_type="SNIPPET", snippet='f""', cursor_offset_left=1, icon="⚡"),
        MenuAction(id="DELIM_DOCSTR", label='9: """..."""', hint="Docstring triple centrado", action_type="SNIPPET", snippet='""""""', cursor_offset_left=3, icon="⚡"),
    ]

    tree["OP_DELIMITERS"] = MenuNode(
        id="OP_DELIMITERS",
        title="DELIMITADORES & PARES",
        breadcrumb_label="DELIMITADORES",
        items=op_delim_items,
        parent_id="OPERATORS",
        sticky=False,
    )

    op_punct_items = [
        MenuAction(id="PUNCT_COLON", label="1: :", hint="Dos puntos con espacio", action_type="SNIPPET", snippet=": ", icon="⚡"),
        MenuAction(id="PUNCT_COMMA", label="2: ,", hint="Coma con espacio", action_type="SNIPPET", snippet=", ", icon="⚡"),
        MenuAction(id="PUNCT_DOT", label="3: .", hint="Punto de acceso", action_type="SNIPPET", snippet=".", icon="⚡"),
        MenuAction(id="PUNCT_ARROW", label="4: ->", hint="Retorno de tipo flecha", action_type="SNIPPET", snippet=" -> ", icon="⚡"),
        create_pause_action("5"),
        MenuAction(id="PUNCT_UNDERSCORE", label="6: _", hint="Guion bajo", action_type="SNIPPET", snippet="_", icon="⚡"),
        create_back_action("OPERATORS", "7"),
        MenuAction(id="PUNCT_SEMICOLON", label="8: ;", hint="Punto y coma", action_type="SNIPPET", snippet="; ", icon="⚡"),
        MenuAction(id="PUNCT_SCOPE", label="9: ::", hint="Resolución de ámbito", action_type="SNIPPET", snippet="::", icon="⚡"),
    ]

    tree["OP_PUNCT"] = MenuNode(
        id="OP_PUNCT",
        title="PUNTUACIÓN & SÍMBOLOS",
        breadcrumb_label="PUNTUACIÓN",
        items=op_punct_items,
        parent_id="OPERATORS",
        sticky=False,
    )

    # =========================================================================
    # 5. CURSOR NAVIGATION (STICKY SUBMENU)
    # =========================================================================
    nav_items = [
        MenuAction(id="NAV_UP", label="1: ⬆ Arriba", hint="Flecha Arriba", action_type="KEY", key_name="UP", sticky=True, icon="⚡"),
        MenuAction(id="NAV_DOWN", label="2: ⬇ Abajo", hint="Flecha Abajo", action_type="KEY", key_name="DOWN", sticky=True, icon="⚡"),
        MenuAction(id="NAV_LEFT", label="3: ⬅ Izquierda", hint="Flecha Izquierda", action_type="KEY", key_name="LEFT", sticky=True, icon="⚡"),
        MenuAction(id="NAV_RIGHT", label="4: ➡ Derecha", hint="Flecha Derecha", action_type="KEY", key_name="RIGHT", sticky=True, icon="⚡"),
        create_pause_action("5"),
        MenuAction(id="NAV_HOME", label="6: Inicio Línea", hint="Tecla Home / Inicio", action_type="KEY", key_name="HOME", sticky=True, icon="⚡"),
        create_back_action("ROOT", "7"),
        MenuAction(id="NAV_END", label="8: Fin Línea", hint="Tecla End / Fin", action_type="KEY", key_name="END", sticky=True, icon="⚡"),
        MenuAction(id="NAV_WORD", label="9: Saltar Palabra", hint="Ctrl + Derecha", action_type="KEY", key_name="WORD_RIGHT", sticky=True, icon="⚡"),
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
        MenuAction(id="EDIT_BACKSPACE", label="1: Borrar Carácter", hint="Backspace", action_type="KEY", key_name="BACKSPACE", sticky=True, icon="⚡"),
        MenuAction(id="EDIT_DEL_WORD", label="2: Borrar Palabra", hint="Ctrl + Backspace", action_type="KEY", key_name="CTRL_BACKSPACE", sticky=True, icon="⚡"),
        MenuAction(id="EDIT_DEL_LINE", label="3: Borrar Línea", hint="Ctrl+Shift+K", action_type="KEY", key_name="DELETE_LINE", sticky=True, icon="⚡"),
        MenuAction(id="EDIT_UNDO", label="4: Deshacer", hint="Ctrl + Z", action_type="KEY", key_name="UNDO", sticky=True, icon="⚡"),
        create_pause_action("5"),
        MenuAction(id="EDIT_REDO", label="6: Rehacer", hint="Ctrl + Y", action_type="KEY", key_name="REDO", sticky=True, icon="⚡"),
        create_back_action("ROOT", "7"),
        MenuAction(id="EDIT_COMMENT", label="8: Comentar", hint="Ctrl + /", action_type="KEY", key_name="COMMENT", sticky=True, icon="⚡"),
        MenuAction(id="EDIT_SAVE", label="9: Guardar", hint="Ctrl + S", action_type="KEY", key_name="SAVE", sticky=True, icon="⚡"),
    ]

    tree["EDIT"] = MenuNode(
        id="EDIT",
        title="EDICIÓN / BORRADO",
        breadcrumb_label="EDICIÓN",
        items=edit_items,
        parent_id="ROOT",
        sticky=True,
    )

    # =========================================================================
    # 7. SPACE / FORMATTING (STICKY SUBMENU)
    # =========================================================================
    format_items = [
        MenuAction(id="FMT_ENTER", label="1: ENTER", hint="Salto de línea", action_type="KEY", key_name="ENTER", sticky=True, icon="⚡"),
        MenuAction(id="FMT_TAB", label="2: TAB", hint="Tabulador / Indentar", action_type="KEY", key_name="TAB", sticky=True, icon="⚡"),
        MenuAction(id="FMT_UNINDENT", label="3: SHIFT + TAB", hint="Des-indentar", action_type="KEY", key_name="SHIFT_TAB", sticky=True, icon="⚡"),
        MenuAction(id="FMT_SPACE", label="4: ESPACIO", hint="Barra espaciadora", action_type="KEY", key_name="SPACE", sticky=True, icon="⚡"),
        create_pause_action("5"),
        MenuAction(id="FMT_2ENTER", label="6: 2x ENTER", hint="Doble salto de línea", action_type="KEY", key_name="ENTER_TWICE", sticky=True, icon="⚡"),
        create_back_action("ROOT", "7"),
        MenuAction(id="FMT_4SPACES", label="8: 4x ESPACIOS", hint="Indentación manual", action_type="SNIPPET", snippet="    ", sticky=True, icon="⚡"),
        MenuAction(id="FMT_COLON_ENTER", label="9: : + ENTER", hint="Dos puntos y salto indentado", action_type="SNIPPET", snippet=":\n    ", sticky=True, icon="⚡"),
    ]

    tree["FORMAT"] = MenuNode(
        id="FORMAT",
        title="ESPACIO / FORMATO",
        breadcrumb_label="FORMATO",
        items=format_items,
        parent_id="ROOT",
        sticky=True,
    )

    # =========================================================================
    # 8. RAPID SNIPPETS / TEMPLATES & AI PREDICTIONS
    # =========================================================================
    snippets_items = populate_ai_prediction_items(None, parent_id="ROOT")

    tree["SNIPPETS"] = MenuNode(
        id="SNIPPETS",
        title="IA / PREDICCIÓN",
        breadcrumb_label="IA",
        items=snippets_items,
        parent_id="ROOT",
        sticky=False,
    )
    # Alias for AI_PREDICT
    tree["AI_PREDICT"] = tree["SNIPPETS"]

    # =========================================================================
    # 9. T9 KEYBOARD & IDENTIFIERS (2-HOP HIERARCHY)
    # =========================================================================
    t9_root_items = [
        MenuAction(id="T9_GRP_AE", label="1: a - e 📁", hint="Letras a, b, c, d, e", action_type="SUBMENU", submenu_id="T9_AE", icon="📁"),
        MenuAction(id="T9_GRP_FJ", label="2: f - j 📁", hint="Letras f, g, h, i, j", action_type="SUBMENU", submenu_id="T9_FJ", icon="📁"),
        MenuAction(id="T9_GRP_KO", label="3: k - o 📁", hint="Letras k, l, m, n, o", action_type="SUBMENU", submenu_id="T9_KO", icon="📁"),
        MenuAction(id="T9_GRP_PT", label="4: p - t 📁", hint="Letras p, q, r, s, t", action_type="SUBMENU", submenu_id="T9_PT", icon="📁"),
        create_pause_action("5"),
        MenuAction(id="T9_GRP_UZ", label="6: u - z 📁", hint="Letras u, v, w, x, y, z", action_type="SUBMENU", submenu_id="T9_UZ", icon="📁"),
        create_back_action("ROOT", "7"),
        MenuAction(id="T9_GRP_LOCAL_VARS", label="8: VARIABLES ARCHIVO 📁", hint="Símbolos del archivo actual", action_type="SUBMENU", submenu_id="T9_LOCAL_VARS", icon="📁"),
        MenuAction(id="T9_GRP_VARS", label="9: VARS: i, x, self 📁", hint="Variables habituales", action_type="SUBMENU", submenu_id="T9_VARS", icon="📁"),
    ]

    tree["T9"] = MenuNode(
        id="T9",
        title="TECLADO T9 / IDENTIFICADORES",
        breadcrumb_label="T9",
        items=t9_root_items,
        parent_id="ROOT",
        sticky=False,
    )

    tree["T9_LOCAL_VARS"] = MenuNode(
        id="T9_LOCAL_VARS",
        title="VARIABLES DEL ARCHIVO",
        breadcrumb_label="LOCALES",
        items=populate_local_symbol_items(None, parent_id="T9"),
        parent_id="T9",
        sticky=False,
    )

    # T9 Frequent Variables (i, j, x, data, result, self)
    t9_vars_items = [
        MenuAction(id="VAR_I", label="1: i", hint="Variable contador i", action_type="SNIPPET", snippet="i", icon="⚡"),
        MenuAction(id="VAR_J", label="2: j", hint="Variable contador j", action_type="SNIPPET", snippet="j", icon="⚡"),
        MenuAction(id="VAR_X", label="3: x", hint="Variable x", action_type="SNIPPET", snippet="x", icon="⚡"),
        MenuAction(id="VAR_SELF", label="4: self", hint="Referencia de instancia", action_type="SNIPPET", snippet="self", icon="⚡"),
        create_pause_action("5"),
        MenuAction(id="VAR_DATA", label="6: data", hint="Identificador data", action_type="SNIPPET", snippet="data", icon="⚡"),
        create_back_action("T9", "7"),
        MenuAction(id="VAR_RESULT", label="8: result", hint="Identificador result", action_type="SNIPPET", snippet="result", icon="⚡"),
        MenuAction(id="VAR_ITEM", label="9: item", hint="Identificador item", action_type="SNIPPET", snippet="item", icon="⚡"),
    ]

    tree["T9_VARS"] = MenuNode(
        id="T9_VARS",
        title="VARIABLES FRECUENTES",
        breadcrumb_label="VARS",
        items=t9_vars_items,
        parent_id="T9",
        sticky=False,
    )

    # T9 Frequent Values (True, False, None, 0, 1, [], {})
    t9_vals_items = [
        MenuAction(id="VAL_TRUE", label="1: True", hint="Booleano True", action_type="SNIPPET", snippet="True", icon="⚡"),
        MenuAction(id="VAL_FALSE", label="2: False", hint="Booleano False", action_type="SNIPPET", snippet="False", icon="⚡"),
        MenuAction(id="VAL_NONE", label="3: None", hint="Valor None", action_type="SNIPPET", snippet="None", icon="⚡"),
        MenuAction(id="VAL_ZERO", label="4: 0", hint="Entero cero", action_type="SNIPPET", snippet="0", icon="⚡"),
        create_pause_action("5"),
        MenuAction(id="VAL_ONE", label="6: 1", hint="Entero uno", action_type="SNIPPET", snippet="1", icon="⚡"),
        create_back_action("T9", "7"),
        MenuAction(id="VAL_EMPTY_LIST", label="8: []", hint="Lista vacía", action_type="SNIPPET", snippet="[]", cursor_offset_left=1, icon="⚡"),
        MenuAction(id="VAL_EMPTY_DICT", label="9: {}", hint="Diccionario vacío", action_type="SNIPPET", snippet="{}", cursor_offset_left=1, icon="⚡"),
    ]

    tree["T9_VALS"] = MenuNode(
        id="T9_VALS",
        title="VALORES Y CONSTANTES",
        breadcrumb_label="VALORES",
        items=t9_vals_items,
        parent_id="T9",
        sticky=False,
    )

    # T9 Letters A-E
    tree["T9_AE"] = MenuNode(
        id="T9_AE",
        title="LETRAS: A - E",
        breadcrumb_label="a-e",
        items=[
            MenuAction(id="CH_A", label="1: a", action_type="SNIPPET", snippet="a", icon="⚡"),
            MenuAction(id="CH_B", label="2: b", action_type="SNIPPET", snippet="b", icon="⚡"),
            MenuAction(id="CH_C", label="3: c", action_type="SNIPPET", snippet="c", icon="⚡"),
            MenuAction(id="CH_D", label="4: d", action_type="SNIPPET", snippet="d", icon="⚡"),
            create_pause_action("5"),
            MenuAction(id="CH_E", label="6: e", action_type="SNIPPET", snippet="e", icon="⚡"),
            create_back_action("T9", "7"),
            MenuAction(id="CH_UND_AE", label="8: _", hint="Guion bajo", action_type="SNIPPET", snippet="_", icon="⚡"),
            MenuAction(id="CH_SP_AE", label="9: ESPACIO", hint="Espacio", action_type="KEY", key_name="SPACE", icon="⚡"),
        ],
        parent_id="T9",
        sticky=False,
    )

    # T9 Letters F-J
    tree["T9_FJ"] = MenuNode(
        id="T9_FJ",
        title="LETRAS: F - J",
        breadcrumb_label="f-j",
        items=[
            MenuAction(id="CH_F", label="1: f", action_type="SNIPPET", snippet="f", icon="⚡"),
            MenuAction(id="CH_G", label="2: g", action_type="SNIPPET", snippet="g", icon="⚡"),
            MenuAction(id="CH_H", label="3: h", action_type="SNIPPET", snippet="h", icon="⚡"),
            MenuAction(id="CH_I", label="4: i", action_type="SNIPPET", snippet="i", icon="⚡"),
            create_pause_action("5"),
            MenuAction(id="CH_J", label="6: j", action_type="SNIPPET", snippet="j", icon="⚡"),
            create_back_action("T9", "7"),
            MenuAction(id="CH_UND_FJ", label="8: _", hint="Guion bajo", action_type="SNIPPET", snippet="_", icon="⚡"),
            MenuAction(id="CH_SP_FJ", label="9: ESPACIO", hint="Espacio", action_type="KEY", key_name="SPACE", icon="⚡"),
        ],
        parent_id="T9",
        sticky=False,
    )

    # T9 Letters K-O
    tree["T9_KO"] = MenuNode(
        id="T9_KO",
        title="LETRAS: K - O",
        breadcrumb_label="k-o",
        items=[
            MenuAction(id="CH_K", label="1: k", action_type="SNIPPET", snippet="k", icon="⚡"),
            MenuAction(id="CH_L", label="2: l", action_type="SNIPPET", snippet="l", icon="⚡"),
            MenuAction(id="CH_M", label="3: m", action_type="SNIPPET", snippet="m", icon="⚡"),
            MenuAction(id="CH_N", label="4: n", action_type="SNIPPET", snippet="n", icon="⚡"),
            create_pause_action("5"),
            MenuAction(id="CH_O", label="6: o", action_type="SNIPPET", snippet="o", icon="⚡"),
            create_back_action("T9", "7"),
            MenuAction(id="CH_UND_KO", label="8: _", hint="Guion bajo", action_type="SNIPPET", snippet="_", icon="⚡"),
            MenuAction(id="CH_SP_KO", label="9: ESPACIO", hint="Espacio", action_type="KEY", key_name="SPACE", icon="⚡"),
        ],
        parent_id="T9",
        sticky=False,
    )

    # T9 Letters P-T
    tree["T9_PT"] = MenuNode(
        id="T9_PT",
        title="LETRAS: P - T",
        breadcrumb_label="p-t",
        items=[
            MenuAction(id="CH_P", label="1: p", action_type="SNIPPET", snippet="p", icon="⚡"),
            MenuAction(id="CH_Q", label="2: q", action_type="SNIPPET", snippet="q", icon="⚡"),
            MenuAction(id="CH_R", label="3: r", action_type="SNIPPET", snippet="r", icon="⚡"),
            MenuAction(id="CH_S", label="4: s", action_type="SNIPPET", snippet="s", icon="⚡"),
            create_pause_action("5"),
            MenuAction(id="CH_T", label="6: t", action_type="SNIPPET", snippet="t", icon="⚡"),
            create_back_action("T9", "7"),
            MenuAction(id="CH_UND_PT", label="8: _", hint="Guion bajo", action_type="SNIPPET", snippet="_", icon="⚡"),
            MenuAction(id="CH_SP_PT", label="9: ESPACIO", hint="Espacio", action_type="KEY", key_name="SPACE", icon="⚡"),
        ],
        parent_id="T9",
        sticky=False,
    )

    # T9 Letters U-Z
    tree["T9_UZ"] = MenuNode(
        id="T9_UZ",
        title="LETRAS: U - Z",
        breadcrumb_label="u-z",
        items=[
            MenuAction(id="CH_U", label="1: u", action_type="SNIPPET", snippet="u", icon="⚡"),
            MenuAction(id="CH_V", label="2: v", action_type="SNIPPET", snippet="v", icon="⚡"),
            MenuAction(id="CH_W", label="3: w", action_type="SNIPPET", snippet="w", icon="⚡"),
            MenuAction(id="CH_X", label="4: x", action_type="SNIPPET", snippet="x", icon="⚡"),
            create_pause_action("5"),
            MenuAction(id="CH_Y", label="6: y", action_type="SNIPPET", snippet="y", icon="⚡"),
            create_back_action("T9", "7"),
            MenuAction(id="CH_Z", label="8: z", action_type="SNIPPET", snippet="z", icon="⚡"),
            MenuAction(id="CH_SP_UZ", label="9: ESPACIO", hint="Espacio", action_type="KEY", key_name="SPACE", icon="⚡"),
        ],
        parent_id="T9",
        sticky=False,
    )

    return tree


def validate_menu_tree(tree: Dict[str, MenuNode]) -> Tuple[bool, List[str]]:
    """
    Performs rigorous mathematical validation on the menu tree hierarchy.
    Checks:
    1. 'ROOT' node exists.
    2. Every node has exactly 9 elements (indices 0..8).
    3. Index 4 is ALWAYS Pause across every node.
    4. Index 6 is ALWAYS Back in every submenu (id != 'ROOT').
    5. Back points to a valid parent_id.
    6. All submenu_id references point to existing nodes (0 orphan references).
    7. All parent_id references point to existing nodes.
    8. No cycles without a path leading back to 'ROOT'.

    Returns:
        (is_valid, list_of_error_messages)
    """
    errors: List[str] = []

    if "ROOT" not in tree:
        errors.append("Fatal: Tree does not contain 'ROOT' node.")
        return False, errors

    for node_id, node in tree.items():
        # Check exactly 9 items
        if len(node.items) != 9:
            errors.append(f"Node '{node_id}' has {len(node.items)} items (expected exactly 9).")

        # Check Index 4 is ALWAYS Pause
        if len(node.items) > 4:
            item_4 = node.items[4]
            if item_4.action_type != "PAUSE":
                errors.append(
                    f"Node '{node_id}' index 4 action_type is '{item_4.action_type}' (expected 'PAUSE')."
                )

        # Check Index 6 is ALWAYS Back for all submenus
        if node_id != "ROOT" and len(node.items) > 6:
            item_6 = node.items[6]
            if item_6.action_type != "BACK":
                errors.append(
                    f"Submenu '{node_id}' index 6 action_type is '{item_6.action_type}' (expected 'BACK')."
                )
            if item_6.submenu_id != node.parent_id:
                errors.append(
                    f"Submenu '{node_id}' back target '{item_6.submenu_id}' does not match parent '{node.parent_id}'."
                )

        # Check parent_id exists
        if node.parent_id is not None and node.parent_id not in tree:
            errors.append(f"Node '{node_id}' has invalid parent_id '{node.parent_id}' (not in tree).")

        # Check submenu references
        for idx, item in enumerate(node.items):
            if item.action_type == "SUBMENU":
                if not item.submenu_id:
                    errors.append(f"Node '{node_id}' item {idx} has SUBMENU type with empty submenu_id.")
                elif item.submenu_id not in tree:
                    errors.append(
                        f"Node '{node_id}' item {idx} references non-existent submenu '{item.submenu_id}'."
                    )

    # Verify every node can reach 'ROOT' via back navigation
    for node_id, node in tree.items():
        curr = node_id
        visited: Set[str] = set()
        while curr != "ROOT":
            if curr in visited:
                errors.append(f"Cycle detected leading away from ROOT starting at '{node_id}'.")
                break
            visited.add(curr)
            curr_node = tree.get(curr)
            if curr_node is None or curr_node.parent_id is None:
                errors.append(f"Node '{node_id}' has no path back to ROOT.")
                break
            curr = curr_node.parent_id

    return len(errors) == 0, errors


def get_breadcrumb_path(tree: Dict[str, MenuNode], current_node_id: str) -> str:
    """
    Computes a human-readable breadcrumb trail from ROOT to the current node.
    Example: 'RAÍZ > FLUJO / LÓGICA > TRY/RET'
    """
    if current_node_id not in tree:
        return "RAÍZ"

    path_nodes = []
    curr: Optional[str] = current_node_id
    visited: Set[str] = set()

    while curr is not None and curr in tree:
        if curr in visited:
            break
        visited.add(curr)
        node = tree[curr]
        path_nodes.append(node.breadcrumb_label or node.title)
        curr = node.parent_id

    path_nodes.reverse()
    return " > ".join(path_nodes)
