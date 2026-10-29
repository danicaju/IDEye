"""
IDEye - Hierarchical 3x3 Menu Trees Module (Phase 3)
Defines MenuAction and MenuNode dataclasses, complete 3x3 navigation hierarchy,
sticky mode transitions, and mathematical validation protocol.

Golden Rules of Gaze Ergonomics:
1. Every grid layout has EXACTLY 9 cells (indices 0 to 8).
2. The Center Cell (Index 4) is ALWAYS ' PAUSA / MODO LECTURA' across all menus.
3. In any submenu (Level >= 2), the Bottom-Left Cell (Index 6) is ALWAYS ' VOLVER ATRÁS'.
4. Sticky Submenus (NAV, EDIT, FORMAT) stay active for repetitive actions until 'VOLVER' is chosen.
5. Non-sticky actions automatically return to 'ROOT' after injecting a snippet.
"""

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
    icon: str = ""
    mode_id: Optional[str] = None


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
        label=f"{key_num}: Pausa / Descanso",
        hint="Descansa la vista (mira y abre la boca)",
        action_type="PAUSE",
        icon="",
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
        icon="",
        sticky=False,
    )


def populate_ai_prediction_items(
    predictions: Optional[List[str]] = None,
    parent_id: str = "ROOT",
    language: str = "PYTHON",
) -> List[MenuAction]:
    """
    Constructs exactly 9 MenuAction items for the AI prediction menu (SNIPPETS).
    Slots 0, 1, 2, 3, 5, 7: 6 AI suggestions
    Slot 4: Center Pause action
    Slot 6: Back action (to parent_id)
    Slot 8: Regenerate / Refresh action
    """
    safe_preds = list(predictions or [])
    lang = normalize_language(language)

    if lang == LANG_TYPESCRIPT:
        default_fallbacks = [
            'const [state, setState] = useState();',
            'async function fetchData() {\n    \n}',
            'new Promise((resolve, reject) => {\n    \n})',
            'JSON.stringify(data, null, 2)',
            'try {\n    \n} catch (error) {\n    console.error(error);\n}',
            'export default function Component() {\n    return null;\n}',
        ]
    elif lang == LANG_RUST:
        default_fallbacks = [
            'fn main() -> Result<(), Box<dyn std::error::Error>> {\n    Ok(())\n}',
            '#[derive(Debug, Clone, PartialEq)]',
            'match result {\n    Ok(val) => val,\n    Err(e) => return Err(e),\n}',
            'vec![]',
            'println!("{:#?}", data);',
            'impl Default for MyStruct {\n    fn default() -> Self {\n        Self {}\n    }\n}',
        ]
    elif lang == LANG_CPP:
        default_fallbacks = [
            'int main(int argc, char* argv[]) {\n    return 0;\n}',
            'std::vector<int> items;',
            'std::make_unique<MyClass>();',
            'std::cout << "Debug: " << val << std::endl;',
            'for (const auto& item : items) {\n    \n}',
            '#pragma once\n',
        ]
    elif lang == LANG_GO:
        default_fallbacks = [
            'func main() {\n    \n}',
            'if err != nil {\n    return err\n}',
            'go func() {\n    \n}()',
            'make([]string, 0)',
            'fmt.Printf("%+v\\n", data)',
            'defer func() {\n    if r := recover(); r != nil {\n    }\n}()',
        ]
    else:
        default_fallbacks = [
            'if __name__ == "__main__":\n    ',
            '[x for x in list]',
            '{k: v for k, v in .items()}',
            'with open("", "r") as f:',
            'try:\n    \nfinally:\n    ',
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
            icon="",
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
            icon="",
        ),
    ]


def populate_local_symbol_items(
    symbols: Optional[List[str]] = None,
    parent_id: str = "ROOT",
) -> List[MenuAction]:
    """
    Constructs exactly 9 MenuAction items for local symbols.
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
            icon="",
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


def populate_exit_confirm_items(parent_id: str = "ROOT") -> List[MenuAction]:
    """
    Constructs exactly 9 MenuAction items for safe, hands-free eye-controlled exit confirmation.
    Slot 0: CONFIRMAR SALIR (Action: EXIT)
    Slots 1, 2, 3, 5, 7, 8: CANCELAR (Action: BACK to parent_id)
    Slot 4: Center Pause action (Golden Rule 2)
    Slot 6: Back action (Golden Rule 3)
    """
    def _make_cancel(slot_num: str, item_id: str) -> MenuAction:
        return MenuAction(
            id=item_id,
            label=f"{slot_num}: CANCELAR",
            hint="Permanecer en IDEye (Seguro)",
            action_type="BACK",
            submenu_id=parent_id,
            icon="",
            sticky=False,
        )

    return [
        MenuAction(
            id="CONFIRM_EXIT",
            label="1: CONFIRMAR SALIR",
            hint="Cerrar IDEye definitivamente",
            action_type="EXIT",
            icon="",
            sticky=False,
        ),
        _make_cancel("2", "CANCEL_EXIT_2"),
        _make_cancel("3", "CANCEL_EXIT_3"),
        _make_cancel("4", "CANCEL_EXIT_4"),
        create_pause_action("5"),
        _make_cancel("6", "CANCEL_EXIT_6"),
        create_back_action(parent_id, "7"),
        _make_cancel("8", "CANCEL_EXIT_8"),
        _make_cancel("9", "CANCEL_EXIT_9"),
    ]


def populate_help_items(parent_id: str = "ROOT") -> List[MenuAction]:
    """
    Constructs exactly 9 MenuAction items for the integrated In-App Gesture & Shortcut Guide.
    Follows all Golden Rules (Index 4 is Pause, Index 6 is Back).
    """
    return [
        MenuAction(
            id="HELP_MOUTH",
            label="1: BOCA (MAR)",
            hint="Abrir boca = Clic / Inyectar código",
            action_type="INFO",
            icon="",
        ),
        MenuAction(
            id="HELP_WINK_R",
            label="2: GUIÑO DERECHO",
            hint="Pausar / Ocultar HUD totalmente / Despertar",
            action_type="INFO",
            icon="",
        ),
        MenuAction(
            id="HELP_WINK_L",
            label="3: GUIÑO IZQUIERDO",
            hint="Volver atrás / Deshacer (Ctrl+Z)",
            action_type="INFO",
            icon="",
        ),
        MenuAction(
            id="HELP_SHORTCUTS_1",
            label="4: Ctrl+Alt+A SMART | Ctrl+Alt+T TRACK | Ctrl+Alt+V MODOS",
            hint="Ctrl+Alt+A: Menús inteligentes | Ctrl+Alt+T: Modo Gaze | Ctrl+Alt+V: Elegir modo",
            action_type="INFO",
            icon="",
        ),
        create_pause_action("5"),
        MenuAction(
            id="HELP_SHORTCUTS_2",
            label="6: Ctrl+Alt+M MONIT | Ctrl+Alt+N PANT | Ctrl+Alt+C CALIB",
            hint="Ctrl+Alt+M: Monitor | Ctrl+Alt+N: Pantalla | Ctrl+Alt+C: Calibrar centro | Ctrl+Alt+K: Auto-switch",
            action_type="INFO",
            icon="",
        ),
        create_back_action(parent_id, "7"),
        MenuAction(
            id="HELP_SHORTCUTS_3",
            label="8: Ctrl+Alt+P PAUSA | Ctrl+Alt+B PORTAP | Ctrl+Alt+L LENGUAJE",
            hint="Ctrl+Alt+P: Pausa | Ctrl+Alt+B: Portapapeles | Ctrl+Alt+L: Lenguaje | Ctrl+Alt+S: Sonido | Ctrl+Alt+F: FreeLook | Ctrl+Alt+G: Gaming | Ctrl+Alt+Q: Emergencia",
            action_type="INFO",
            icon="",
        ),
        MenuAction(
            id="HELP_CLOSE",
            label="9: CERRAR GUÍA",
            hint="Regresar a la navegación principal",
            action_type="BACK",
            submenu_id=parent_id,
            icon="",
        ),
    ]


def populate_lang_select_items(parent_id: str = "ROOT") -> List[MenuAction]:
    """
    Constructs exactly 9 MenuAction items for the multi-language selection grid.
    Follows all Golden Rules of Gaze Ergonomics (Slot 4 is Pause, Slot 6 is Back).
    """
    return [
        MenuAction("LANG_SET_PYTHON", "1: PYTHON", "Sintaxis Python", "LANG_CHANGE", snippet="PYTHON", icon="language"),
        MenuAction("LANG_SET_TYPESCRIPT", "2: TYPESCRIPT / JS", "Sintaxis TypeScript / JavaScript", "LANG_CHANGE", snippet="TYPESCRIPT", icon="language"),
        MenuAction("LANG_SET_RUST", "3: RUST", "Sintaxis Rust", "LANG_CHANGE", snippet="RUST", icon="language"),
        MenuAction("LANG_SET_CPP", "4: C / C++", "Sintaxis C y C++", "LANG_CHANGE", snippet="CPP", icon="language"),
        create_pause_action("5"),
        MenuAction("LANG_SET_GO", "6: GO", "Sintaxis Golang", "LANG_CHANGE", snippet="GO", icon="language"),
        create_back_action(parent_id, "7"),
        MenuAction("LANG_SET_AUTO", "8: AUTO-DETECTAR", "Detectar según archivo o VS Code", "LANG_AUTO", icon="ai_spark"),
        MenuAction("LANG_CLOSE", "9: CERRAR", "Volver al menú principal", "BACK", submenu_id=parent_id, icon="navigation"),
    ]


def create_standard_menu_action(key_num: str = "9") -> MenuAction:
    """Returns the standardized action to switch to the full 3x3 Standard Menu Tree."""
    return MenuAction(
        id="SWITCH_MENU_STANDARD",
        label=f"{key_num}: MENÚ ESTÁNDAR",
        hint="Abrir menú estándar 3x3 completo",
        action_type="SUBMENU",
        submenu_id="MENU_STANDARD",
        icon="navigation",
        sticky=False,
    )


def create_adaptive_menu_action(key_num: str = "9") -> MenuAction:
    """Returns the standardized action to switch back to the dynamic adaptive context menu."""
    return MenuAction(
        id="SWITCH_ADAPTIVE_MENU",
        label=f"{key_num}: MENÚ ADAPTATIVO",
        hint="Volver a los menús contextuales adaptativos",
        action_type="SUBMENU",
        submenu_id="ROOT",
        icon="ai_spark",
        sticky=False,
    )


def get_adaptive_context_node(
    context_info: Union[Dict[str, Any], str],
    standard_root: Optional[MenuNode] = None,
    switch_slot: int = 8,
    language: str = "PYTHON",
) -> MenuNode:
    """
    Constructs an adaptive 3x3 MenuNode based on the detected syntactic context.
    Cuts eye dwell cycles by dynamically surfacing contextual snippets and tokens.

    Golden Rules of Gaze Ergonomics:
    1. Exactly 9 items (indices 0 to 8).
    2. Index 4 is ALWAYS create_pause_action("5").
    3. One designated slot (default Index 8, or Index 6) allows one-click switching to MENU_STANDARD.
    4. Precise cursor offsets (cursor_offset_left, cursor_offset_up).
    5. Clean labels, zero emojis, vector icons.
    """
    lang = normalize_language(language)

    if isinstance(context_info, str):
        ctx_type = context_info.upper()
        line_text = ""
    elif isinstance(context_info, dict):
        ctx_type = str(context_info.get("context", "GENERAL")).upper()
        line_text = str(context_info.get("line", ""))
    else:
        ctx_type = "GENERAL"
        line_text = ""

    # If context is general or unknown, return the standard root node
    if ctx_type in ("GENERAL", "UNKNOWN", ""):
        if standard_root is not None:
            return standard_root
        return build_menu_tree(lang)["ROOT"]

    standard_switch_key = "9" if switch_slot == 8 else "7"
    switch_item = create_standard_menu_action(standard_switch_key)

    title = f"CONTEXTO: {ctx_type}"
    breadcrumb = f"RAÍZ [{get_language_badge(lang)}: {ctx_type}]"

    # Multi-language contextual actions dispatch
    if lang == LANG_TYPESCRIPT:
        if ctx_type == "FUNCTION_SIGNATURE":
            actions_7 = [
                MenuAction("CTX_TS_COMMA", "1: ,", "Separador", "SNIPPET", snippet=", ", icon="operators"),
                MenuAction("CTX_TS_STR", "2: : string", "Tipo string", "SNIPPET", snippet=": string", icon="variables"),
                MenuAction("CTX_TS_NUM", "3: : number", "Tipo number", "SNIPPET", snippet=": number", icon="variables"),
                MenuAction("CTX_TS_VOID", "4: : void => {", "Retorno void", "SNIPPET", snippet=": void => {\n    \n}", cursor_offset_up=1, icon="function"),
                MenuAction("CTX_TS_PROMISE", "6: : Promise<void>", "Retorno Promise", "SNIPPET", snippet=": Promise<void> => {\n    \n}", cursor_offset_up=1, icon="function"),
                MenuAction("CTX_TS_RETURN", "7: return", "Sentencia return", "SNIPPET", snippet="return ", icon="flow"),
                MenuAction("CTX_TS_CLOSE", "8: ) {", "Cerrar y abrir cuerpo", "SNIPPET", snippet=") {\n    \n}", cursor_offset_up=1, icon="function"),
            ]
            title = "CONTEXTO: FUNCIÓN (TS)"
        elif ctx_type == "TRY_BLOCK":
            actions_7 = [
                MenuAction("CTX_TS_CATCH", "1: catch (err) {", "Capturar error", "SNIPPET", snippet="catch (error) {\n    console.error(error);\n}", icon="flow"),
                MenuAction("CTX_TS_FINALLY", "2: finally {", "Bloque finally", "SNIPPET", snippet="finally {\n    \n}", cursor_offset_up=1, icon="flow"),
                MenuAction("CTX_TS_THROW_ERR", "3: throw new Error", "Lanzar error nuevo", "SNIPPET", snippet='throw new Error("");', cursor_offset_left=3, icon="flow"),
                MenuAction("CTX_TS_THROW", "4: throw error", "Relanzar error", "SNIPPET", snippet="throw error;", icon="flow"),
                MenuAction("CTX_TS_LOG_ERR", "6: console.error", "Imprimir error", "SNIPPET", snippet="console.error(error);", icon="function"),
                MenuAction("CTX_TS_RET_NULL", "7: return null", "Retorno null", "SNIPPET", snippet="return null;", icon="flow"),
                MenuAction("CTX_TS_TRY", "8: try {", "Bloque try", "SNIPPET", snippet="try {\n    \n}", cursor_offset_up=1, icon="flow"),
            ]
            title = "CONTEXTO: TRY/CATCH (TS)"
        elif ctx_type == "CLASS_BODY":
            actions_7 = [
                MenuAction("CTX_TS_CTOR", "1: constructor()", "Constructor", "SNIPPET", snippet="constructor() {\n    super();\n}", icon="function"),
                MenuAction("CTX_TS_PUB_METH", "2: public method()", "Método público", "SNIPPET", snippet="public method(): void {\n    \n}", cursor_offset_up=1, icon="function"),
                MenuAction("CTX_TS_PRIV_PROP", "3: private prop", "Propiedad privada", "SNIPPET", snippet="private : string;", cursor_offset_left=9, icon="variables"),
                MenuAction("CTX_TS_ASYNC_METH", "4: async method()", "Método async", "SNIPPET", snippet="async method(): Promise<void> {\n    \n}", cursor_offset_up=1, icon="function"),
                MenuAction("CTX_TS_SUPER", "6: super()", "Constructor base", "SNIPPET", snippet="super();\n", icon="function"),
                MenuAction("CTX_TS_THIS", "7: this.", "Referencia this", "SNIPPET", snippet="this.", icon="variables"),
                MenuAction("CTX_TS_RETURN", "8: return", "Sentencia return", "SNIPPET", snippet="return ;", cursor_offset_left=1, icon="flow"),
            ]
            title = "CONTEXTO: CLASE (TS)"
        elif ctx_type == "IF_BLOCK":
            actions_7 = [
                MenuAction("CTX_TS_ELSE_IF", "1: else if () {", "Condicional else if", "SNIPPET", snippet="else if () {\n    \n}", cursor_offset_up=1, cursor_offset_left=4, icon="flow"),
                MenuAction("CTX_TS_ELSE", "2: else {", "Rama else", "SNIPPET", snippet="else {\n    \n}", cursor_offset_up=1, icon="flow"),
                MenuAction("CTX_TS_EQ_NULL", "3: === null", "Igualdad null", "SNIPPET", snippet=" === null", icon="operators"),
                MenuAction("CTX_TS_NEQ_NULL", "4: !== null", "Desigualdad null", "SNIPPET", snippet=" !== null", icon="operators"),
                MenuAction("CTX_TS_AND", "6: &&", "Lógico Y", "SNIPPET", snippet=" && ", icon="operators"),
                MenuAction("CTX_TS_OR", "7: ||", "Lógico O", "SNIPPET", snippet=" || ", icon="operators"),
                MenuAction("CTX_TS_NOT", "8: !", "Negación lógica", "SNIPPET", snippet="!", icon="operators"),
            ]
            title = "CONTEXTO: IF/ELSE (TS)"
        elif ctx_type == "LOOP_BLOCK":
            actions_7 = [
                MenuAction("CTX_TS_BREAK", "1: break;", "Interrumpir bucle", "SNIPPET", snippet="break;", icon="flow"),
                MenuAction("CTX_TS_CONT", "2: continue;", "Siguiente iteración", "SNIPPET", snippet="continue;", icon="flow"),
                MenuAction("CTX_TS_FOR_OF", "3: for (const x of )", "Iterador colección", "SNIPPET", snippet="for (const item of ) {\n    \n}", cursor_offset_up=1, cursor_offset_left=4, icon="flow"),
                MenuAction("CTX_TS_FOR_I", "4: for (let i = 0...)", "Bucle numérico", "SNIPPET", snippet="for (let i = 0; i < ; i++) {\n    \n}", cursor_offset_up=1, cursor_offset_left=11, icon="flow"),
                MenuAction("CTX_TS_MAP", "6: .map()", "Transformar array", "SNIPPET", snippet=".map((x) => x)", cursor_offset_left=1, icon="function"),
                MenuAction("CTX_TS_FILTER", "7: .filter()", "Filtrar array", "SNIPPET", snippet=".filter((x) => )", cursor_offset_left=1, icon="function"),
                MenuAction("CTX_TS_FOREACH", "8: .forEach()", "Recorrer array", "SNIPPET", snippet=".forEach((x) => {\n    \n})", cursor_offset_up=1, icon="function"),
            ]
            title = "CONTEXTO: BUCLE (TS)"
        else:
            return standard_root if standard_root is not None else build_menu_tree(lang)["ROOT"]

    elif lang == LANG_RUST:
        if ctx_type == "FUNCTION_SIGNATURE":
            actions_7 = [
                MenuAction("CTX_RS_SELF", "1: &self", "Referencia self", "SNIPPET", snippet="&self", icon="variables"),
                MenuAction("CTX_RS_MUT_SELF", "2: &mut self", "Referencia mutable self", "SNIPPET", snippet="&mut self", icon="variables"),
                MenuAction("CTX_RS_RET_RES", "3: -> Result<()>", "Retorno Result", "SNIPPET", snippet=" -> Result<(), Box<dyn std::error::Error>>", icon="function"),
                MenuAction("CTX_RS_RET_BOOL", "4: -> bool", "Retorno bool", "SNIPPET", snippet=" -> bool", icon="function"),
                MenuAction("CTX_RS_OK", "6: Ok(())", "Resultado exitoso", "SNIPPET", snippet="Ok(())", icon="flow"),
                MenuAction("CTX_RS_RETURN", "7: return", "Sentencia return", "SNIPPET", snippet="return ", icon="flow"),
                MenuAction("CTX_RS_CLOSE", "8: ) {", "Cerrar y abrir cuerpo", "SNIPPET", snippet=") {\n    \n}", cursor_offset_up=1, icon="function"),
            ]
            title = "CONTEXTO: FUNCIÓN (RS)"
        elif ctx_type == "TRY_BLOCK":
            actions_7 = [
                MenuAction("CTX_RS_QMARK", "1: ?", "Operador propagate ?", "SNIPPET", snippet="?", icon="operators"),
                MenuAction("CTX_RS_MATCH", "2: match res {", "Coincidencia de patrones", "SNIPPET", snippet="match res {\n    Ok(val) => val,\n    Err(e) => return Err(e),\n}", icon="flow"),
                MenuAction("CTX_RS_OK_VAL", "3: Ok(val)", "Constructor Ok", "SNIPPET", snippet="Ok()", cursor_offset_left=1, icon="flow"),
                MenuAction("CTX_RS_ERR_VAL", "4: Err(e)", "Constructor Err", "SNIPPET", snippet="Err()", cursor_offset_left=1, icon="flow"),
                MenuAction("CTX_RS_PANIC", "6: panic!()", "Pánico crítico", "SNIPPET", snippet='panic!("");', cursor_offset_left=3, icon="flow"),
                MenuAction("CTX_RS_IF_LET", "7: if let Err(e)", "Comprobar error", "SNIPPET", snippet="if let Err(e) =  {\n    \n}", cursor_offset_up=1, cursor_offset_left=4, icon="flow"),
                MenuAction("CTX_RS_RET_ERR", "8: return Err(e)", "Retorno error", "SNIPPET", snippet="return Err(e);", icon="flow"),
            ]
            title = "CONTEXTO: MATCH / RESULT (RS)"
        elif ctx_type == "CLASS_BODY":
            actions_7 = [
                MenuAction("CTX_RS_FN_NEW", "1: pub fn new()", "Constructor new", "SNIPPET", snippet="pub fn new() -> Self {\n    Self {}\n}", icon="function"),
                MenuAction("CTX_RS_PUB_FN", "2: pub fn", "Método público", "SNIPPET", snippet="pub fn (&self) {\n    \n}", cursor_offset_up=1, cursor_offset_left=11, icon="function"),
                MenuAction("CTX_RS_SELF_DOT", "3: self.", "Acceso a campo", "SNIPPET", snippet="self.", icon="variables"),
                MenuAction("CTX_RS_SELF_SCOPE", "4: Self::", "Llamada estática", "SNIPPET", snippet="Self::", icon="variables"),
                MenuAction("CTX_RS_DERIVE", "6: #[derive(..)]", "Derivar rasgos", "SNIPPET", snippet="#[derive(Debug, Clone)]\n", icon="function"),
                MenuAction("CTX_RS_PUB_FIELD", "7: pub field:", "Campo público", "SNIPPET", snippet="pub : String,", cursor_offset_left=9, icon="variables"),
                MenuAction("CTX_RS_LET_MUT", "8: let mut", "Variable mutable", "SNIPPET", snippet="let mut ", icon="variables"),
            ]
            title = "CONTEXTO: STRUCT / IMPL (RS)"
        elif ctx_type == "IF_BLOCK":
            actions_7 = [
                MenuAction("CTX_RS_ELSE_IF", "1: else if {", "Condicional else if", "SNIPPET", snippet="else if  {\n    \n}", cursor_offset_up=1, cursor_offset_left=4, icon="flow"),
                MenuAction("CTX_RS_ELSE", "2: else {", "Rama else", "SNIPPET", snippet="else {\n    \n}", cursor_offset_up=1, icon="flow"),
                MenuAction("CTX_RS_IF_SOME", "3: if let Some(x)", "Extracción Some", "SNIPPET", snippet="if let Some(x) =  {\n    \n}", cursor_offset_up=1, cursor_offset_left=4, icon="flow"),
                MenuAction("CTX_RS_IF_OK", "4: if let Ok(x)", "Extracción Ok", "SNIPPET", snippet="if let Ok(x) =  {\n    \n}", cursor_offset_up=1, cursor_offset_left=4, icon="flow"),
                MenuAction("CTX_RS_AND", "6: &&", "Lógico Y", "SNIPPET", snippet=" && ", icon="operators"),
                MenuAction("CTX_RS_OR", "7: ||", "Lógico O", "SNIPPET", snippet=" || ", icon="operators"),
                MenuAction("CTX_RS_NOT", "8: !", "Negación lógica", "SNIPPET", snippet="!", icon="operators"),
            ]
            title = "CONTEXTO: IF/MATCH (RS)"
        elif ctx_type == "LOOP_BLOCK":
            actions_7 = [
                MenuAction("CTX_RS_BREAK", "1: break;", "Interrumpir bucle", "SNIPPET", snippet="break;", icon="flow"),
                MenuAction("CTX_RS_CONT", "2: continue;", "Siguiente iteración", "SNIPPET", snippet="continue;", icon="flow"),
                MenuAction("CTX_RS_ITER", "3: .iter()", "Iterador inmutable", "SNIPPET", snippet=".iter()", icon="function"),
                MenuAction("CTX_RS_FOR_IN", "4: for x in 0..", "Bucle de rango", "SNIPPET", snippet="for i in 0.. {\n    \n}", cursor_offset_up=1, cursor_offset_left=4, icon="flow"),
                MenuAction("CTX_RS_ENUM", "6: .enumerate()", "Iterador con índice", "SNIPPET", snippet=".enumerate()", icon="function"),
                MenuAction("CTX_RS_LOOP", "7: loop {", "Bucle continuo", "SNIPPET", snippet="loop {\n    \n}", cursor_offset_up=1, icon="flow"),
                MenuAction("CTX_RS_INTO_ITER", "8: .into_iter()", "Iterador con consumo", "SNIPPET", snippet=".into_iter()", icon="function"),
            ]
            title = "CONTEXTO: BUCLE (RS)"
        else:
            return standard_root if standard_root is not None else build_menu_tree(lang)["ROOT"]

    elif lang == LANG_CPP:
        if ctx_type == "FUNCTION_SIGNATURE":
            actions_7 = [
                MenuAction("CTX_CPP_CONST_REF", "1: const auto&", "Referencia constante", "SNIPPET", snippet="const auto& ", icon="variables"),
                MenuAction("CTX_CPP_VOID", "2: void", "Tipo void", "SNIPPET", snippet="void ", icon="variables"),
                MenuAction("CTX_CPP_INT", "3: int", "Tipo int", "SNIPPET", snippet="int ", icon="variables"),
                MenuAction("CTX_CPP_BOOL", "4: bool", "Tipo bool", "SNIPPET", snippet="bool ", icon="variables"),
                MenuAction("CTX_CPP_OVERRIDE", "6: override", "Sobrescritura virtual", "SNIPPET", snippet=" override", icon="function"),
                MenuAction("CTX_CPP_RETURN", "7: return", "Sentencia return", "SNIPPET", snippet="return ", icon="flow"),
                MenuAction("CTX_CPP_CLOSE", "8: ) {", "Cerrar y abrir cuerpo", "SNIPPET", snippet=") {\n    \n}", cursor_offset_up=1, icon="function"),
            ]
            title = "CONTEXTO: FUNCIÓN (C++)"
        elif ctx_type == "TRY_BLOCK":
            actions_7 = [
                MenuAction("CTX_CPP_CATCH_EXC", "1: catch (const std::exception&)", "Capturar excepción estándar", "SNIPPET", snippet="catch (const std::exception& e) {\n    std::cerr << e.what() << std::endl;\n}", icon="flow"),
                MenuAction("CTX_CPP_CATCH_ALL", "2: catch (...)", "Capturar cualquier excepción", "SNIPPET", snippet="catch (...) {\n    \n}", cursor_offset_up=1, icon="flow"),
                MenuAction("CTX_CPP_THROW_EXC", "3: throw runtime_error", "Lanzar std::runtime_error", "SNIPPET", snippet='throw std::runtime_error("");', cursor_offset_left=3, icon="flow"),
                MenuAction("CTX_CPP_THROW", "4: throw;", "Relanzar excepción activa", "SNIPPET", snippet="throw;", icon="flow"),
                MenuAction("CTX_CPP_RET_NULLPTR", "6: return nullptr;", "Retorno puntero nulo", "SNIPPET", snippet="return nullptr;", icon="flow"),
                MenuAction("CTX_CPP_TRY", "7: try {", "Nuevo bloque try", "SNIPPET", snippet="try {\n    \n}", cursor_offset_up=1, icon="flow"),
                MenuAction("CTX_CPP_BREAK", "8: break;", "Sentencia break", "SNIPPET", snippet="break;", icon="flow"),
            ]
            title = "CONTEXTO: TRY/CATCH (C++)"
        elif ctx_type == "CLASS_BODY":
            actions_7 = [
                MenuAction("CTX_CPP_PUBLIC", "1: public:", "Sección pública", "SNIPPET", snippet="public:\n    ", icon="function"),
                MenuAction("CTX_CPP_PRIVATE", "2: private:", "Sección privada", "SNIPPET", snippet="private:\n    ", icon="function"),
                MenuAction("CTX_CPP_THIS", "3: this->", "Puntero this", "SNIPPET", snippet="this->", icon="variables"),
                MenuAction("CTX_CPP_VIRTUAL", "4: virtual", "Método virtual", "SNIPPET", snippet="virtual ", icon="function"),
                MenuAction("CTX_CPP_UNIQUE", "6: make_unique", "Puntero único moderno", "SNIPPET", snippet="std::make_unique<>()", cursor_offset_left=2, icon="function"),
                MenuAction("CTX_CPP_SHARED", "7: make_shared", "Puntero compartido moderno", "SNIPPET", snippet="std::make_shared<>()", cursor_offset_left=2, icon="function"),
                MenuAction("CTX_CPP_RETURN", "8: return;", "Retorno de función", "SNIPPET", snippet="return;", icon="flow"),
            ]
            title = "CONTEXTO: CLASE (C++)"
        elif ctx_type == "IF_BLOCK":
            actions_7 = [
                MenuAction("CTX_CPP_ELSE_IF", "1: else if () {", "Condicional else if", "SNIPPET", snippet="else if () {\n    \n}", cursor_offset_up=1, cursor_offset_left=4, icon="flow"),
                MenuAction("CTX_CPP_ELSE", "2: else {", "Rama else", "SNIPPET", snippet="else {\n    \n}", cursor_offset_up=1, icon="flow"),
                MenuAction("CTX_CPP_EQ_NULL", "3: == nullptr", "Comparar con nullptr", "SNIPPET", snippet=" == nullptr", icon="operators"),
                MenuAction("CTX_CPP_NEQ_NULL", "4: != nullptr", "Comparar no nullptr", "SNIPPET", snippet=" != nullptr", icon="operators"),
                MenuAction("CTX_CPP_AND", "6: &&", "Lógico Y", "SNIPPET", snippet=" && ", icon="operators"),
                MenuAction("CTX_CPP_OR", "7: ||", "Lógico O", "SNIPPET", snippet=" || ", icon="operators"),
                MenuAction("CTX_CPP_NOT", "8: !", "Negación lógica", "SNIPPET", snippet="!", icon="operators"),
            ]
            title = "CONTEXTO: IF/ELSE (C++)"
        elif ctx_type == "LOOP_BLOCK":
            actions_7 = [
                MenuAction("CTX_CPP_BREAK", "1: break;", "Interrumpir bucle", "SNIPPET", snippet="break;", icon="flow"),
                MenuAction("CTX_CPP_CONT", "2: continue;", "Siguiente iteración", "SNIPPET", snippet="continue;", icon="flow"),
                MenuAction("CTX_CPP_FOR_AUTO", "3: for (auto& x : )", "Range-based for", "SNIPPET", snippet="for (const auto& item : ) {\n    \n}", cursor_offset_up=1, cursor_offset_left=4, icon="flow"),
                MenuAction("CTX_CPP_FOR_I", "4: for (size_t i...)", "Bucle indexado", "SNIPPET", snippet="for (size_t i = 0; i < ; ++i) {\n    \n}", cursor_offset_up=1, cursor_offset_left=12, icon="flow"),
                MenuAction("CTX_CPP_SIZE", "6: .size()", "Tamaño de contenedor", "SNIPPET", snippet=".size()", icon="function"),
                MenuAction("CTX_CPP_BEGIN", "7: .begin()", "Iterador inicial", "SNIPPET", snippet=".begin()", icon="function"),
                MenuAction("CTX_CPP_END", "8: .end()", "Iterador final", "SNIPPET", snippet=".end()", icon="function"),
            ]
            title = "CONTEXTO: BUCLE (C++)"
        else:
            return standard_root if standard_root is not None else build_menu_tree(lang)["ROOT"]

    elif lang == LANG_GO:
        if ctx_type == "FUNCTION_SIGNATURE":
            actions_7 = [
                MenuAction("CTX_GO_ERR", "1: err error", "Parámetro de error", "SNIPPET", snippet="err error", icon="variables"),
                MenuAction("CTX_GO_CTX", "2: ctx context.Context", "Parámetro de contexto", "SNIPPET", snippet="ctx context.Context", icon="variables"),
                MenuAction("CTX_GO_RET_ERR", "3: error", "Tipo retorno error", "SNIPPET", snippet=" error", icon="function"),
                MenuAction("CTX_GO_RET_PAIR", "4: (string, error)", "Retorno valor y error", "SNIPPET", snippet=" (string, error)", icon="function"),
                MenuAction("CTX_GO_RET_NIL", "6: return nil", "Retorno nil", "SNIPPET", snippet="return nil", icon="flow"),
                MenuAction("CTX_GO_RETURN", "7: return", "Sentencia return", "SNIPPET", snippet="return ", icon="flow"),
                MenuAction("CTX_GO_CLOSE", "8: ) {", "Cerrar y abrir cuerpo", "SNIPPET", snippet=") {\n    \n}", cursor_offset_up=1, icon="function"),
            ]
            title = "CONTEXTO: FUNCIÓN (GO)"
        elif ctx_type == "TRY_BLOCK":
            actions_7 = [
                MenuAction("CTX_GO_IF_ERR", "1: if err != nil", "Comprobación canónica err", "SNIPPET", snippet="if err != nil {\n    return err\n}", icon="flow"),
                MenuAction("CTX_GO_RET_ERR2", "2: return err", "Retorno de error", "SNIPPET", snippet="return err", icon="flow"),
                MenuAction("CTX_GO_RET_NIL_ERR", "3: return nil, err", "Retorno nulo con error", "SNIPPET", snippet="return nil, err", icon="flow"),
                MenuAction("CTX_GO_WRAP_ERR", "4: fmt.Errorf(%w)", "Envolver error", "SNIPPET", snippet='fmt.Errorf(": %w", err)', cursor_offset_left=9, icon="function"),
                MenuAction("CTX_GO_PANIC", "6: panic(err)", "Pánico", "SNIPPET", snippet="panic(err)", icon="flow"),
                MenuAction("CTX_GO_DEFER", "7: defer", "Sentencia defer", "SNIPPET", snippet="defer ", icon="flow"),
                MenuAction("CTX_GO_RECOVER", "8: recover()", "Recuperación de pánico", "SNIPPET", snippet="if r := recover(); r != nil {\n    \n}", cursor_offset_up=1, icon="flow"),
            ]
            title = "CONTEXTO: MANEJO ERRORES (GO)"
        elif ctx_type == "CLASS_BODY":
            actions_7 = [
                MenuAction("CTX_GO_METH", "1: func (s *T) M()", "Método receptor", "SNIPPET", snippet="func (s *) () {\n    \n}", cursor_offset_up=1, cursor_offset_left=11, icon="function"),
                MenuAction("CTX_GO_STRUCT_DEF", "2: type S struct", "Declaración de estructura", "SNIPPET", snippet="type  struct {\n    \n}", cursor_offset_up=1, cursor_offset_left=11, icon="function"),
                MenuAction("CTX_GO_SELF_DOT", "3: s.", "Acceso a campo de receptor", "SNIPPET", snippet="s.", icon="variables"),
                MenuAction("CTX_GO_INST", "4: &Type{}", "Instanciación con puntero", "SNIPPET", snippet="&{}", cursor_offset_left=2, icon="variables"),
                MenuAction("CTX_GO_VAR", "6: var", "Declaración de variable", "SNIPPET", snippet="var ", icon="variables"),
                MenuAction("CTX_GO_RET_S", "7: return s", "Retorno de receptor", "SNIPPET", snippet="return s", icon="flow"),
                MenuAction("CTX_GO_IFACE", "8: type I interface", "Declaración de interfaz", "SNIPPET", snippet="type  interface {\n    \n}", cursor_offset_up=1, cursor_offset_left=14, icon="function"),
            ]
            title = "CONTEXTO: STRUCT / MÉTODO (GO)"
        elif ctx_type == "IF_BLOCK":
            actions_7 = [
                MenuAction("CTX_GO_ELSE_IF", "1: else if {", "Condicional else if", "SNIPPET", snippet="else if  {\n    \n}", cursor_offset_up=1, cursor_offset_left=4, icon="flow"),
                MenuAction("CTX_GO_ELSE", "2: else {", "Rama else", "SNIPPET", snippet="else {\n    \n}", cursor_offset_up=1, icon="flow"),
                MenuAction("CTX_GO_EQ_NIL", "3: == nil", "Comprobación nil", "SNIPPET", snippet=" == nil", icon="operators"),
                MenuAction("CTX_GO_NEQ_NIL", "4: != nil", "Comprobación no nil", "SNIPPET", snippet=" != nil", icon="operators"),
                MenuAction("CTX_GO_AND", "6: &&", "Lógico Y", "SNIPPET", snippet=" && ", icon="operators"),
                MenuAction("CTX_GO_OR", "7: ||", "Lógico O", "SNIPPET", snippet=" || ", icon="operators"),
                MenuAction("CTX_GO_NOT", "8: !", "Negación lógica", "SNIPPET", snippet="!", icon="operators"),
            ]
            title = "CONTEXTO: IF/ELSE (GO)"
        elif ctx_type == "LOOP_BLOCK":
            actions_7 = [
                MenuAction("CTX_GO_BREAK", "1: break", "Interrumpir bucle", "SNIPPET", snippet="break", icon="flow"),
                MenuAction("CTX_GO_CONT", "2: continue", "Siguiente iteración", "SNIPPET", snippet="continue", icon="flow"),
                MenuAction("CTX_GO_RANGE", "3: for _, x := range", "Iterador de colección", "SNIPPET", snippet="for _, item := range  {\n    \n}", cursor_offset_up=1, cursor_offset_left=4, icon="flow"),
                MenuAction("CTX_GO_FOR_I", "4: for i := 0; ...", "Bucle numérico", "SNIPPET", snippet="for i := 0; i < ; i++ {\n    \n}", cursor_offset_up=1, cursor_offset_left=10, icon="flow"),
                MenuAction("CTX_GO_FOR_INF", "6: for {", "Bucle infinito", "SNIPPET", snippet="for {\n    \n}", cursor_offset_up=1, icon="flow"),
                MenuAction("CTX_GO_SELECT", "7: select {", "Multiplexión de canales", "SNIPPET", snippet="select {\ncase :\n    \n}", cursor_offset_up=2, cursor_offset_left=5, icon="flow"),
                MenuAction("CTX_GO_LEN", "8: len()", "Longitud de slice/map", "SNIPPET", snippet="len()", cursor_offset_left=1, icon="function"),
            ]
            title = "CONTEXTO: BUCLE (GO)"
        else:
            return standard_root if standard_root is not None else build_menu_tree(lang)["ROOT"]

    else:  # PYTHON default
        if ctx_type == "FUNCTION_SIGNATURE":
            has_self = "self" in line_text
            if has_self:
                slot_0 = MenuAction("CTX_FN_COMMA", "1: ,", "Separador de parámetros", "SNIPPET", snippet=", ", icon="operators")
                slot_1 = MenuAction("CTX_FN_ARGS", "2: *args", "Argumentos posicionales", "SNIPPET", snippet="*args", icon="variables")
            else:
                slot_0 = MenuAction("CTX_FN_SELF", "1: self", "Parámetro self", "SNIPPET", snippet="self", icon="variables")
                slot_1 = MenuAction("CTX_FN_ARGS", "2: *args", "Argumentos posicionales", "SNIPPET", snippet="*args", icon="variables")

            slot_2 = MenuAction("CTX_FN_KWARGS", "3: **kwargs", "Argumentos clave-valor", "SNIPPET", snippet="**kwargs", icon="variables")
            slot_3 = MenuAction("CTX_FN_RET_NONE", "4: -> None:", "Anotación retorno None", "SNIPPET", snippet=" -> None:", icon="function")
            slot_5 = MenuAction("CTX_FN_RET_BOOL", "6: -> bool:", "Anotación retorno bool", "SNIPPET", snippet=" -> bool:", icon="function")
            slot_6 = MenuAction("CTX_FN_RETURN", "7: return", "Sentencia return", "SNIPPET", snippet="return ", icon="flow")
            slot_7 = MenuAction("CTX_FN_CLOSE", "8: ):", "Cerrar firma y nueva línea", "SNIPPET", snippet="):\n    ", icon="function")

            actions_7 = [slot_0, slot_1, slot_2, slot_3, slot_5, slot_6, slot_7]
            title = "CONTEXTO: FUNCIÓN"
            breadcrumb = "RAÍZ [CONTEXTO: FUNCIÓN]"

        elif ctx_type == "TRY_BLOCK":
            actions_7 = [
                MenuAction("CTX_TRY_EXC_GEN", "1: except Exception:", "Capturar Exception", "SNIPPET", snippet="except Exception as e:\n    ", icon="flow"),
                MenuAction("CTX_TRY_EXC_VAL", "2: except ValueError:", "Capturar ValueError", "SNIPPET", snippet="except ValueError:\n    ", icon="flow"),
                MenuAction("CTX_TRY_EXC_KEY", "3: except KeyError:", "Capturar KeyError", "SNIPPET", snippet="except KeyError:\n    ", icon="flow"),
                MenuAction("CTX_TRY_FINALLY", "4: finally:", "Bloque de finalización limpia", "SNIPPET", snippet="finally:\n    ", icon="flow"),
                MenuAction("CTX_TRY_RAISE", "6: raise", "Relanzar o disparar excepción", "SNIPPET", snippet="raise ", icon="flow"),
                MenuAction("CTX_TRY_PASS", "7: pass", "Sentencia pass no-op", "SNIPPET", snippet="pass", icon="flow"),
                MenuAction("CTX_TRY_BLOCK", "8: try:", "Nuevo bloque try con indentación", "SNIPPET", snippet="try:\n    ", icon="flow"),
            ]
            title = "CONTEXTO: TRY/EXCEPT"
            breadcrumb = "RAÍZ [CONTEXTO: TRY/EXCEPT]"

        elif ctx_type == "CLASS_BODY":
            actions_7 = [
                MenuAction("CTX_CLS_INIT", "1: def __init__", "Constructor inicializador", "SNIPPET", snippet="def __init__(self):\n    ", icon="function"),
                MenuAction("CTX_CLS_REPR", "2: def __repr__", "Representación en string", "SNIPPET", snippet="def __repr__(self):\n    return f\"{self.__class__.__name__}()\"\n", icon="function"),
                MenuAction("CTX_CLS_PROP", "3: @property", "Decorador @property", "SNIPPET", snippet="@property\n", icon="function"),
                MenuAction("CTX_CLS_METH", "4: @classmethod", "Decorador @classmethod", "SNIPPET", snippet="@classmethod\n", icon="function"),
                MenuAction("CTX_CLS_SUPER", "6: super().__init__", "Constructor padre", "SNIPPET", snippet="super().__init__()\n    ", icon="function"),
                MenuAction("CTX_CLS_SELF", "7: self.", "Acceso a atributo de instancia", "SNIPPET", snippet="self.", icon="variables"),
                MenuAction("CTX_CLS_PASS", "8: pass", "Sentencia pass", "SNIPPET", snippet="pass", icon="flow"),
            ]
            title = "CONTEXTO: CLASE"
            breadcrumb = "RAÍZ [CONTEXTO: CLASE]"

        elif ctx_type == "IF_BLOCK":
            actions_7 = [
                MenuAction("CTX_IF_ELIF", "1: elif ...:", "Condicional elif con cursor", "SNIPPET", snippet="elif :", cursor_offset_left=1, icon="flow"),
                MenuAction("CTX_IF_ELSE", "2: else:", "Rama else alternativa", "SNIPPET", snippet="else:\n    ", icon="flow"),
                MenuAction("CTX_IF_IS_NONE", "3: is None", "Comprobación de valor nulo", "SNIPPET", snippet="is None", icon="operators"),
                MenuAction("CTX_IF_NOT_NONE", "4: is not None", "Comprobación de no nulidad", "SNIPPET", snippet="is not None", icon="operators"),
                MenuAction("CTX_IF_AND", "6: and", "Operador lógico Y", "SNIPPET", snippet="and ", icon="operators"),
                MenuAction("CTX_IF_OR", "7: or", "Operador lógico O", "SNIPPET", snippet="or ", icon="operators"),
                MenuAction("CTX_IF_NOT", "8: not", "Operador lógico NO", "SNIPPET", snippet="not ", icon="operators"),
            ]
            title = "CONTEXTO: IF/ELIF"
            breadcrumb = "RAÍZ [CONTEXTO: IF/ELIF]"

        elif ctx_type == "LOOP_BLOCK":
            actions_7 = [
                MenuAction("CTX_LOOP_BREAK", "1: break", "Interrumpir bucle", "SNIPPET", snippet="break", icon="flow"),
                MenuAction("CTX_LOOP_CONT", "2: continue", "Saltar a siguiente iteración", "SNIPPET", snippet="continue", icon="flow"),
                MenuAction("CTX_LOOP_ENUM", "3: enumerate()", "Iterador con índice", "SNIPPET", snippet="enumerate()", cursor_offset_left=1, icon="function"),
                MenuAction("CTX_LOOP_RANGE", "4: range()", "Generador de rango", "SNIPPET", snippet="range()", cursor_offset_left=1, icon="function"),
                MenuAction("CTX_LOOP_ITEMS", "6: .items()", "Pares clave-valor", "SNIPPET", snippet=".items()", icon="function"),
                MenuAction("CTX_LOOP_ZIP", "7: zip()", "Iteración múltiple combinada", "SNIPPET", snippet="zip()", cursor_offset_left=1, icon="function"),
                MenuAction("CTX_LOOP_IN", "8: in", "Operador de pertenencia", "SNIPPET", snippet="in ", icon="operators"),
            ]
            title = "CONTEXTO: BUCLE"
            breadcrumb = "RAÍZ [CONTEXTO: BUCLE]"

        elif ctx_type == "WITH_BLOCK":
            actions_7 = [
                MenuAction("CTX_WITH_OPEN", "1: open() as f", "Apertura de archivo con cursor", "SNIPPET", snippet='open("", "r") as f:', cursor_offset_left=14, icon="function"),
                MenuAction("CTX_WITH_AS", "2: as", "Alias de context manager", "SNIPPET", snippet="as ", icon="operators"),
                MenuAction("CTX_WITH_PASS", "3: pass", "Sentencia pass", "SNIPPET", snippet="pass", icon="flow"),
                MenuAction("CTX_WITH_STMT", "4: with ...:", "Sentencia with con cursor", "SNIPPET", snippet="with :", cursor_offset_left=1, icon="flow"),
                MenuAction("CTX_WITH_READ", "6: f.read()", "Lectura completa de archivo", "SNIPPET", snippet="f.read()", icon="function"),
                MenuAction("CTX_WITH_WRITE", "7: f.write()", "Escritura de archivo con cursor", "SNIPPET", snippet='f.write("")', cursor_offset_left=2, icon="function"),
                MenuAction("CTX_WITH_SELF", "8: self.", "Acceso a objeto de contexto", "SNIPPET", snippet="self.", icon="variables"),
            ]
            title = "CONTEXTO: WITH"
            breadcrumb = "RAÍZ [CONTEXTO: WITH]"

        else:
            return standard_root if standard_root is not None else build_menu_tree(lang)["ROOT"]

    pause_action = create_pause_action("5")
    if switch_slot == 8:
        raw_items = [
            actions_7[0],
            actions_7[1],
            actions_7[2],
            actions_7[3],
            pause_action,
            actions_7[4],
            actions_7[5],
            actions_7[6],
            switch_item,
        ]
    else:
        raw_items = [
            actions_7[0],
            actions_7[1],
            actions_7[2],
            actions_7[3],
            pause_action,
            actions_7[4],
            switch_item,
            actions_7[5],
            actions_7[6],
        ]

    # Normalize 1-based key numbering according to 3x3 slot index
    key_numbers = ["1", "2", "3", "4", "5", "6", "7", "8", "9"]
    items: List[MenuAction] = []
    for idx, it in enumerate(raw_items):
        prefix = f"{key_numbers[idx]}: "
        lbl = it.label
        if len(lbl) >= 3 and lbl[0].isdigit() and lbl[1:3] == ": ":
            lbl = prefix + lbl[3:]
        elif not lbl.startswith(prefix):
            lbl = prefix + lbl
        items.append(MenuAction(
            id=it.id,
            label=lbl,
            hint=it.hint,
            action_type=it.action_type,
            snippet=it.snippet,
            key_name=it.key_name,
            cursor_offset_left=it.cursor_offset_left,
            cursor_offset_up=it.cursor_offset_up,
            sticky=it.sticky,
            submenu_id=it.submenu_id,
            icon=it.icon,
        ))

    return MenuNode(
        id=f"ADAPTIVE_{ctx_type}",
        title=title,
        breadcrumb_label=breadcrumb,
        items=items,
        parent_id=None,
        sticky=False,
    )


def _build_flow_items(lang: str) -> List[MenuAction]:
    """Builds the 9 items for the FLOW submenu for the specified language."""
    if lang == LANG_TYPESCRIPT:
        return [
            MenuAction("FLOW_IF", "1: if () {", "Condicional if", "SNIPPET", snippet="if () {\n    \n}", cursor_offset_up=1, cursor_offset_left=4, icon="flow"),
            MenuAction("FLOW_ELIF", "2: else if () {", "Condicional else if", "SNIPPET", snippet="else if () {\n    \n}", cursor_offset_up=1, cursor_offset_left=4, icon="flow"),
            MenuAction("FLOW_ELSE", "3: else {", "Rama else", "SNIPPET", snippet="else {\n    \n}", cursor_offset_up=1, icon="flow"),
            MenuAction("FLOW_FOR_RANGE", "4: for (let i = 0...)", "Bucle indexado", "SNIPPET", snippet="for (let i = 0; i < ; i++) {\n    \n}", cursor_offset_up=1, cursor_offset_left=11, icon="flow"),
            create_pause_action("5"),
            MenuAction("FLOW_FOR_LIST", "6: for (const x of )", "Iterador de colección", "SNIPPET", snippet="for (const item of ) {\n    \n}", cursor_offset_up=1, cursor_offset_left=4, icon="flow"),
            create_back_action("ROOT", "7"),
            MenuAction("FLOW_WHILE", "8: while () {", "Bucle while", "SNIPPET", snippet="while () {\n    \n}", cursor_offset_up=1, cursor_offset_left=4, icon="flow"),
            MenuAction("FLOW_TRY_RET_SUB", "9: TRY / CATCH / RET", "try-catch, return, throw", "SUBMENU", submenu_id="FLOW_TRY_RET", icon="flow"),
        ]
    elif lang == LANG_RUST:
        return [
            MenuAction("FLOW_IF", "1: if {", "Condicional if", "SNIPPET", snippet="if  {\n    \n}", cursor_offset_up=1, cursor_offset_left=4, icon="flow"),
            MenuAction("FLOW_ELIF", "2: else if {", "Condicional else if", "SNIPPET", snippet="else if  {\n    \n}", cursor_offset_up=1, cursor_offset_left=4, icon="flow"),
            MenuAction("FLOW_ELSE", "3: else {", "Rama else", "SNIPPET", snippet="else {\n    \n}", cursor_offset_up=1, icon="flow"),
            MenuAction("FLOW_FOR_RANGE", "4: for i in 0.. {", "Bucle de rango", "SNIPPET", snippet="for i in 0.. {\n    \n}", cursor_offset_up=1, cursor_offset_left=4, icon="flow"),
            create_pause_action("5"),
            MenuAction("FLOW_FOR_LIST", "6: for x in .iter() {", "Iterador de colección", "SNIPPET", snippet="for x in .iter() {\n    \n}", cursor_offset_up=1, cursor_offset_left=11, icon="flow"),
            create_back_action("ROOT", "7"),
            MenuAction("FLOW_WHILE", "8: while {", "Bucle while", "SNIPPET", snippet="while  {\n    \n}", cursor_offset_up=1, cursor_offset_left=4, icon="flow"),
            MenuAction("FLOW_TRY_RET_SUB", "9: MATCH / RESULT / RET", "match, Result, return", "SUBMENU", submenu_id="FLOW_TRY_RET", icon="flow"),
        ]
    elif lang == LANG_CPP:
        return [
            MenuAction("FLOW_IF", "1: if () {", "Condicional if", "SNIPPET", snippet="if () {\n    \n}", cursor_offset_up=1, cursor_offset_left=4, icon="flow"),
            MenuAction("FLOW_ELIF", "2: else if () {", "Condicional else if", "SNIPPET", snippet="else if () {\n    \n}", cursor_offset_up=1, cursor_offset_left=4, icon="flow"),
            MenuAction("FLOW_ELSE", "3: else {", "Rama else", "SNIPPET", snippet="else {\n    \n}", cursor_offset_up=1, icon="flow"),
            MenuAction("FLOW_FOR_RANGE", "4: for (int i = 0...)", "Bucle numérico", "SNIPPET", snippet="for (int i = 0; i < ; ++i) {\n    \n}", cursor_offset_up=1, cursor_offset_left=12, icon="flow"),
            create_pause_action("5"),
            MenuAction("FLOW_FOR_LIST", "6: for (auto& x : )", "Range-based for", "SNIPPET", snippet="for (const auto& item : ) {\n    \n}", cursor_offset_up=1, cursor_offset_left=4, icon="flow"),
            create_back_action("ROOT", "7"),
            MenuAction("FLOW_WHILE", "8: while () {", "Bucle while", "SNIPPET", snippet="while () {\n    \n}", cursor_offset_up=1, cursor_offset_left=4, icon="flow"),
            MenuAction("FLOW_TRY_RET_SUB", "9: TRY / CATCH / RET", "try-catch, return, throw", "SUBMENU", submenu_id="FLOW_TRY_RET", icon="flow"),
        ]
    elif lang == LANG_GO:
        return [
            MenuAction("FLOW_IF", "1: if {", "Condicional if", "SNIPPET", snippet="if  {\n    \n}", cursor_offset_up=1, cursor_offset_left=4, icon="flow"),
            MenuAction("FLOW_ELIF", "2: else if {", "Condicional else if", "SNIPPET", snippet="else if  {\n    \n}", cursor_offset_up=1, cursor_offset_left=4, icon="flow"),
            MenuAction("FLOW_ELSE", "3: else {", "Rama else", "SNIPPET", snippet="else {\n    \n}", cursor_offset_up=1, icon="flow"),
            MenuAction("FLOW_FOR_RANGE", "4: for i := 0; ...", "Bucle indexado", "SNIPPET", snippet="for i := 0; i < ; i++ {\n    \n}", cursor_offset_up=1, cursor_offset_left=10, icon="flow"),
            create_pause_action("5"),
            MenuAction("FLOW_FOR_LIST", "6: for _, x := range", "Iterador range", "SNIPPET", snippet="for _, item := range  {\n    \n}", cursor_offset_up=1, cursor_offset_left=4, icon="flow"),
            create_back_action("ROOT", "7"),
            MenuAction("FLOW_WHILE", "8: for {", "Bucle infinito", "SNIPPET", snippet="for {\n    \n}", cursor_offset_up=1, icon="flow"),
            MenuAction("FLOW_TRY_RET_SUB", "9: ERR / RET / DEFER", "err != nil, return, defer", "SUBMENU", submenu_id="FLOW_TRY_RET", icon="flow"),
        ]
    else:  # PYTHON
        return [
            MenuAction(id="FLOW_IF", label="1: if ...:", hint="Condicional if", action_type="SNIPPET", snippet="if :", cursor_offset_left=1, icon="flow"),
            MenuAction(id="FLOW_ELIF", label="2: elif ...:", hint="Condicional elif", action_type="SNIPPET", snippet="elif :", cursor_offset_left=1, icon="flow"),
            MenuAction(id="FLOW_ELSE", label="3: else:", hint="Rama else con salto", action_type="SNIPPET", snippet="else:\n    ", icon="flow"),
            MenuAction(id="FLOW_FOR_RANGE", label="4: for i in range():", hint="Bucle indexado", action_type="SNIPPET", snippet="for i in range():", cursor_offset_left=2, icon="flow"),
            create_pause_action("5"),
            MenuAction(id="FLOW_FOR_LIST", label="6: for x in lista:", hint="Iterador de colección", action_type="SNIPPET", snippet="for x in :", cursor_offset_left=1, icon="flow"),
            create_back_action("ROOT", "7"),
            MenuAction(id="FLOW_WHILE", label="8: while ...:", hint="Bucle while", action_type="SNIPPET", snippet="while :", cursor_offset_left=1, icon="flow"),
            MenuAction(id="FLOW_TRY_RET_SUB", label="9: TRY / EXCEPT / RET", hint="try-except, return, raise", action_type="SUBMENU", submenu_id="FLOW_TRY_RET", icon="flow"),
        ]


def _build_flow_try_items(lang: str) -> List[MenuAction]:
    """Builds the 9 items for the FLOW_TRY_RET submenu for the specified language."""
    if lang == LANG_TYPESCRIPT:
        return [
            MenuAction("TRY_CATCH", "1: try / catch", "Bloque try-catch", "SNIPPET", snippet="try {\n    \n} catch (error) {\n    console.error(error);\n}", cursor_offset_up=3, icon="flow"),
            MenuAction("RET_VAL", "2: return", "Sentencia return", "SNIPPET", snippet="return ", icon="flow"),
            MenuAction("RET_NULL", "3: return null;", "Retorno null", "SNIPPET", snippet="return null;", icon="flow"),
            MenuAction("RET_TRUE", "4: return true;", "Retorno booleano true", "SNIPPET", snippet="return true;", icon="flow"),
            create_pause_action("5"),
            MenuAction("RET_FALSE", "6: return false;", "Retorno booleano false", "SNIPPET", snippet="return false;", icon="flow"),
            create_back_action("FLOW", "7"),
            MenuAction("THROW_ERR", "8: throw Error", "Lanzar error nuevo", "SNIPPET", snippet='throw new Error("");', cursor_offset_left=3, icon="flow"),
            MenuAction("RET_UNDEF", "9: return undefined;", "Retorno undefined", "SNIPPET", snippet="return undefined;", icon="flow"),
        ]
    elif lang == LANG_RUST:
        return [
            MenuAction("TRY_MATCH", "1: match res {", "Bloque match de Result", "SNIPPET", snippet="match res {\n    Ok(val) => val,\n    Err(e) => return Err(e),\n}", icon="flow"),
            MenuAction("RET_VAL", "2: return", "Sentencia return", "SNIPPET", snippet="return ", icon="flow"),
            MenuAction("RET_OK", "3: Ok(())", "Resultado Ok unit", "SNIPPET", snippet="Ok(())", icon="flow"),
            MenuAction("RET_TRUE", "4: return true;", "Retorno bool true", "SNIPPET", snippet="return true;", icon="flow"),
            create_pause_action("5"),
            MenuAction("RET_FALSE", "6: return false;", "Retorno bool false", "SNIPPET", snippet="return false;", icon="flow"),
            create_back_action("FLOW", "7"),
            MenuAction("RAISE_PANIC", "8: panic!()", "Pánico crítico", "SNIPPET", snippet='panic!("");', cursor_offset_left=3, icon="flow"),
            MenuAction("PROPAGATE_Q", "9: ?", "Operador propagate ?", "SNIPPET", snippet="?", icon="operators"),
        ]
    elif lang == LANG_CPP:
        return [
            MenuAction("TRY_CATCH", "1: try / catch", "Bloque try-catch", "SNIPPET", snippet="try {\n    \n} catch (const std::exception& e) {\n    std::cerr << e.what() << std::endl;\n}", cursor_offset_up=3, icon="flow"),
            MenuAction("RET_VAL", "2: return", "Sentencia return", "SNIPPET", snippet="return ", icon="flow"),
            MenuAction("RET_NULLPTR", "3: return nullptr;", "Retorno puntero nulo", "SNIPPET", snippet="return nullptr;", icon="flow"),
            MenuAction("RET_TRUE", "4: return true;", "Retorno bool true", "SNIPPET", snippet="return true;", icon="flow"),
            create_pause_action("5"),
            MenuAction("RET_FALSE", "6: return false;", "Retorno bool false", "SNIPPET", snippet="return false;", icon="flow"),
            create_back_action("FLOW", "7"),
            MenuAction("THROW_ERR", "8: throw runtime_error", "Lanzar std::runtime_error", "SNIPPET", snippet='throw std::runtime_error("");', cursor_offset_left=3, icon="flow"),
            MenuAction("BREAK_STMT", "9: break;", "Sentencia break", "SNIPPET", snippet="break;", icon="flow"),
        ]
    elif lang == LANG_GO:
        return [
            MenuAction("IF_ERR", "1: if err != nil", "Comprobar error", "SNIPPET", snippet="if err != nil {\n    return err\n}", icon="flow"),
            MenuAction("RET_VAL", "2: return", "Sentencia return", "SNIPPET", snippet="return ", icon="flow"),
            MenuAction("RET_NIL", "3: return nil", "Retorno nil", "SNIPPET", snippet="return nil", icon="flow"),
            MenuAction("RET_TRUE", "4: return true", "Retorno bool true", "SNIPPET", snippet="return true", icon="flow"),
            create_pause_action("5"),
            MenuAction("RET_FALSE", "6: return false", "Retorno bool false", "SNIPPET", snippet="return false", icon="flow"),
            create_back_action("FLOW", "7"),
            MenuAction("RAISE_PANIC", "8: panic()", "Llamada panic", "SNIPPET", snippet='panic("")', cursor_offset_left=2, icon="flow"),
            MenuAction("DEFER_STMT", "9: defer", "Sentencia defer", "SNIPPET", snippet="defer ", icon="flow"),
        ]
    else:  # PYTHON
        return [
            MenuAction(id="TRY_EXCEPT", label="1: try / except", hint="Bloque try-except", action_type="SNIPPET", snippet="try:\n    \nexcept Exception as e:\n    ", cursor_offset_up=2, icon="flow"),
            MenuAction(id="RET_VAL", label="2: return", hint="Retorno con espacio", action_type="SNIPPET", snippet="return ", icon="flow"),
            MenuAction(id="RET_NONE", label="3: return None", hint="Retorno nulo", action_type="SNIPPET", snippet="return None", icon="flow"),
            MenuAction(id="RET_TRUE", label="4: return True", hint="Retorno booleano True", action_type="SNIPPET", snippet="return True", icon="flow"),
            create_pause_action("5"),
            MenuAction(id="RET_FALSE", label="6: return False", hint="Retorno booleano False", action_type="SNIPPET", snippet="return False", icon="flow"),
            create_back_action("FLOW", "7"),
            MenuAction(id="RAISE_EXC", label="8: raise Exception", hint="Lanzar excepción", action_type="SNIPPET", snippet='raise Exception("")', cursor_offset_left=2, icon="flow"),
            MenuAction(id="PASS_STMT", label="9: pass", hint="Sentencia pass", action_type="SNIPPET", snippet="pass", icon="flow"),
        ]


def _build_struct_items(lang: str) -> List[MenuAction]:
    """Builds the 9 items for the STRUCT submenu for the specified language."""
    if lang == LANG_TYPESCRIPT:
        return [
            MenuAction("STRUCT_DEF", "1: function () {", "Declaración de función", "SNIPPET", snippet="function () {\n    \n}", cursor_offset_up=1, cursor_offset_left=5, icon="function"),
            MenuAction("STRUCT_CLASS", "2: class Name {", "Definición de clase", "SNIPPET", snippet="class  {\n    \n}", cursor_offset_up=1, cursor_offset_left=4, icon="function"),
            MenuAction("STRUCT_IMPORT_SUB", "3: IMPORTAR", "import, export", "SUBMENU", submenu_id="STRUCT_IMPORT", icon="function"),
            MenuAction("STRUCT_ARROW", "4: const fn = () =>", "Función flecha", "SNIPPET", snippet="const  = () => {\n    \n};", cursor_offset_up=1, cursor_offset_left=12, icon="function"),
            create_pause_action("5"),
            MenuAction("STRUCT_PRINT", "6: console.log()", "Imprimir por consola", "SNIPPET", snippet="console.log();", cursor_offset_left=2, icon="function"),
            create_back_action("ROOT", "7"),
            MenuAction("STRUCT_LEN", "8: .length", "Propiedad de longitud", "SNIPPET", snippet=".length", icon="function"),
            MenuAction("STRUCT_IFACE", "9: interface Name {", "Definición de interfaz", "SNIPPET", snippet="interface  {\n    \n}", cursor_offset_up=1, cursor_offset_left=4, icon="function"),
        ]
    elif lang == LANG_RUST:
        return [
            MenuAction("STRUCT_DEF", "1: fn name() -> {", "Definición de función", "SNIPPET", snippet="fn () {\n    \n}", cursor_offset_up=1, cursor_offset_left=5, icon="function"),
            MenuAction("STRUCT_CLASS", "2: struct Name {", "Definición de struct", "SNIPPET", snippet="struct  {\n    \n}", cursor_offset_up=1, cursor_offset_left=4, icon="function"),
            MenuAction("STRUCT_IMPORT_SUB", "3: IMPORTAR", "use, pub use, mod", "SUBMENU", submenu_id="STRUCT_IMPORT", icon="function"),
            MenuAction("STRUCT_IMPL", "4: impl Name {", "Bloque de implementación", "SNIPPET", snippet="impl  {\n    \n}", cursor_offset_up=1, cursor_offset_left=4, icon="function"),
            create_pause_action("5"),
            MenuAction("STRUCT_PRINT", "6: println!()", "Macro de impresión", "SNIPPET", snippet='println!("{}", );', cursor_offset_left=3, icon="function"),
            create_back_action("ROOT", "7"),
            MenuAction("STRUCT_LEN", "8: .len()", "Longitud de colección", "SNIPPET", snippet=".len()", icon="function"),
            MenuAction("STRUCT_PUB_FN", "9: pub fn", "Función pública", "SNIPPET", snippet="pub fn () {\n    \n}", cursor_offset_up=1, cursor_offset_left=5, icon="function"),
        ]
    elif lang == LANG_CPP:
        return [
            MenuAction("STRUCT_DEF", "1: void func() {", "Definición de función", "SNIPPET", snippet="void () {\n    \n}", cursor_offset_up=1, cursor_offset_left=5, icon="function"),
            MenuAction("STRUCT_CLASS", "2: class Name {", "Definición de clase", "SNIPPET", snippet="class  {\npublic:\n    \n};", cursor_offset_up=1, cursor_offset_left=12, icon="function"),
            MenuAction("STRUCT_IMPORT_SUB", "3: IMPORTAR", "#include, using", "SUBMENU", submenu_id="STRUCT_IMPORT", icon="function"),
            MenuAction("STRUCT_STRUCT", "4: struct Name {", "Definición de estructura", "SNIPPET", snippet="struct  {\n    \n};", cursor_offset_up=1, cursor_offset_left=5, icon="function"),
            create_pause_action("5"),
            MenuAction("STRUCT_PRINT", "6: std::cout <<", "Impresión en stream", "SNIPPET", snippet="std::cout <<  << std::endl;", cursor_offset_left=14, icon="function"),
            create_back_action("ROOT", "7"),
            MenuAction("STRUCT_LEN", "8: .size()", "Tamaño de contenedor", "SNIPPET", snippet=".size()", icon="function"),
            MenuAction("STRUCT_TEMPLATE", "9: template<typename T>", "Plantilla genérica", "SNIPPET", snippet="template<typename T>\n", icon="function"),
        ]
    elif lang == LANG_GO:
        return [
            MenuAction("STRUCT_DEF", "1: func name() {", "Definición de función", "SNIPPET", snippet="func () {\n    \n}", cursor_offset_up=1, cursor_offset_left=5, icon="function"),
            MenuAction("STRUCT_CLASS", "2: type S struct {", "Definición de struct", "SNIPPET", snippet="type  struct {\n    \n}", cursor_offset_up=1, cursor_offset_left=11, icon="function"),
            MenuAction("STRUCT_IMPORT_SUB", "3: IMPORTAR", "import packages", "SUBMENU", submenu_id="STRUCT_IMPORT", icon="function"),
            MenuAction("STRUCT_METHOD", "4: func (s *T) m()", "Método con receptor", "SNIPPET", snippet="func (s *) () {\n    \n}", cursor_offset_up=1, cursor_offset_left=11, icon="function"),
            create_pause_action("5"),
            MenuAction("STRUCT_PRINT", "6: fmt.Println()", "Impresión en consola", "SNIPPET", snippet="fmt.Println()", cursor_offset_left=1, icon="function"),
            create_back_action("ROOT", "7"),
            MenuAction("STRUCT_LEN", "8: len()", "Función built-in len", "SNIPPET", snippet="len()", cursor_offset_left=1, icon="function"),
            MenuAction("STRUCT_IFACE", "9: type I interface", "Definición de interfaz", "SNIPPET", snippet="type  interface {\n    \n}", cursor_offset_up=1, cursor_offset_left=14, icon="function"),
        ]
    else:  # PYTHON
        return [
            MenuAction(id="STRUCT_DEF", label="1: def func():", hint="Definición de función", action_type="SNIPPET", snippet="def ():", cursor_offset_left=3, icon="function"),
            MenuAction(id="STRUCT_CLASS", label="2: class Nombre:", hint="Definición de clase", action_type="SNIPPET", snippet="class :", cursor_offset_left=1, icon="function"),
            MenuAction(id="STRUCT_IMPORT_SUB", label="3: IMPORTAR", hint="import, from ... import", action_type="SUBMENU", submenu_id="STRUCT_IMPORT", icon="function"),
            MenuAction(id="STRUCT_LAMBDA", label="4: lambda", hint="Función anónima", action_type="SNIPPET", snippet="lambda : ", cursor_offset_left=2, icon="function"),
            create_pause_action("5"),
            MenuAction(id="STRUCT_PRINT", label="6: print()", hint="Impresión por consola", action_type="SNIPPET", snippet="print()", cursor_offset_left=1, icon="function"),
            create_back_action("ROOT", "7"),
            MenuAction(id="STRUCT_LEN", label="8: len()", hint="Longitud de contenedor", action_type="SNIPPET", snippet="len()", cursor_offset_left=1, icon="function"),
            MenuAction(id="STRUCT_SUPER", label="9: super().__init__()", hint="Constructor clase padre", action_type="SNIPPET", snippet="super().__init__()", icon="function"),
        ]


def _build_struct_import_items(lang: str) -> List[MenuAction]:
    """Builds the 9 items for the STRUCT_IMPORT submenu for the specified language."""
    if lang == LANG_TYPESCRIPT:
        return [
            MenuAction("IMP_NAMED", "1: import { } from", "Import nombrado", "SNIPPET", snippet='import {  } from "";', cursor_offset_left=11, icon="function"),
            MenuAction("IMP_ALL_AS", "2: import * as", "Import de namespace", "SNIPPET", snippet='import * as  from "";', cursor_offset_left=10, icon="function"),
            MenuAction("IMP_DEF", "3: import default", "Import por defecto", "SNIPPET", snippet='import  from "";', cursor_offset_left=10, icon="function"),
            MenuAction("EXP_CONST", "4: export const", "Exportación de constante", "SNIPPET", snippet="export const ", icon="function"),
            create_pause_action("5"),
            MenuAction("EXP_DEF", "6: export default", "Exportación por defecto", "SNIPPET", snippet="export default ", icon="function"),
            create_back_action("STRUCT", "7"),
            MenuAction("IMP_TYPE", "8: import type { }", "Import solo de tipos", "SNIPPET", snippet='import type {  } from "";', cursor_offset_left=11, icon="function"),
            MenuAction("EXP_NAMED", "9: export { }", "Exportación nombrada", "SNIPPET", snippet="export {  };", cursor_offset_left=3, icon="function"),
        ]
    elif lang == LANG_RUST:
        return [
            MenuAction("IMP_USE_STD", "1: use std::", "Import estándar", "SNIPPET", snippet="use std::;", cursor_offset_left=1, icon="function"),
            MenuAction("IMP_USE_CRATE", "2: use crate::", "Import local de crate", "SNIPPET", snippet="use crate::;", cursor_offset_left=1, icon="function"),
            MenuAction("IMP_PUB_USE", "3: pub use", "Re-exportación pública", "SNIPPET", snippet="pub use ;", cursor_offset_left=1, icon="function"),
            MenuAction("IMP_MOD", "4: mod name;", "Declaración de módulo", "SNIPPET", snippet="mod ;", cursor_offset_left=1, icon="function"),
            create_pause_action("5"),
            MenuAction("IMP_COLLECTIONS", "6: use collections::", "Estructuras de datos", "SNIPPET", snippet="use std::collections::;", cursor_offset_left=1, icon="function"),
            create_back_action("STRUCT", "7"),
            MenuAction("IMP_SYNC", "8: use sync::{Arc, Mutex}", "Primitivas de concurrencia", "SNIPPET", snippet="use std::sync::{Arc, Mutex};\n", icon="function"),
            MenuAction("IMP_EXTERN", "9: extern crate", "Crate externa", "SNIPPET", snippet="extern crate ;", cursor_offset_left=1, icon="function"),
        ]
    elif lang == LANG_CPP:
        return [
            MenuAction("INC_IOSTREAM", "1: #include <iostream>", "Stream de E/S estándar", "SNIPPET", snippet="#include <iostream>\n", icon="function"),
            MenuAction("INC_VECTOR", "2: #include <vector>", "Contenedor vector", "SNIPPET", snippet="#include <vector>\n", icon="function"),
            MenuAction("INC_STRING", "3: #include <string>", "Clase std::string", "SNIPPET", snippet="#include <string>\n", icon="function"),
            MenuAction("INC_MEMORY", "4: #include <memory>", "Punteros inteligentes", "SNIPPET", snippet="#include <memory>\n", icon="function"),
            create_pause_action("5"),
            MenuAction("INC_USING_STD", "6: using namespace std;", "Namespace estándar", "SNIPPET", snippet="using namespace std;\n", icon="function"),
            create_back_action("STRUCT", "7"),
            MenuAction("INC_LOCAL", '8: #include ""', "Header local", "SNIPPET", snippet='#include ""\n', cursor_offset_left=2, icon="function"),
            MenuAction("INC_PRAGMA", "9: #pragma once", "Guarda de inclusión única", "SNIPPET", snippet="#pragma once\n", icon="function"),
        ]
    elif lang == LANG_GO:
        return [
            MenuAction("IMP_FMT", '1: import "fmt"', "Paquete de formateo", "SNIPPET", snippet='import "fmt"\n', icon="function"),
            MenuAction("IMP_OS", '2: import "os"', "Paquete de sistema operativo", "SNIPPET", snippet='import "os"\n', icon="function"),
            MenuAction("IMP_SYNC", '3: import "sync"', "Paquete de sincronización", "SNIPPET", snippet='import "sync"\n', icon="function"),
            MenuAction("IMP_TIME", '4: import "time"', "Paquete de tiempo y reloj", "SNIPPET", snippet='import "time"\n', icon="function"),
            create_pause_action("5"),
            MenuAction("IMP_HTTP", '6: import "net/http"', "Cliente y servidor HTTP", "SNIPPET", snippet='import "net/http"\n', icon="function"),
            create_back_action("STRUCT", "7"),
            MenuAction("IMP_JSON", '8: import "encoding/json"', "Serialización JSON", "SNIPPET", snippet='import "encoding/json"\n', icon="function"),
            MenuAction("IMP_MULTI", "9: import ( ... )", "Bloque múltiple de imports", "SNIPPET", snippet='import (\n    ""\n)', cursor_offset_up=1, cursor_offset_left=2, icon="function"),
        ]
    else:  # PYTHON
        return [
            MenuAction(id="IMP_DIRECT", label="1: import", hint="Sentencia import", action_type="SNIPPET", snippet="import ", icon="function"),
            MenuAction(id="IMP_FROM", label="2: from ... import", hint="Importación selectiva", action_type="SNIPPET", snippet="from  import ", cursor_offset_left=8, icon="function"),
            MenuAction(id="IMP_SYS_OS", label="3: import sys, os", hint="Imports del sistema", action_type="SNIPPET", snippet="import sys, os\n", icon="function"),
            MenuAction(id="IMP_NUMPY", label="4: import numpy as np", hint="Import numpy", action_type="SNIPPET", snippet="import numpy as np\n", icon="function"),
            create_pause_action("5"),
            MenuAction(id="IMP_AS", label="6:  as", hint="Alias de módulo", action_type="SNIPPET", snippet=" as ", icon="function"),
            create_back_action("STRUCT", "7"),
            MenuAction(id="IMP_TYPING", label="8: from typing import", hint="Tipado estático", action_type="SNIPPET", snippet="from typing import ", icon="function"),
            MenuAction(id="IMP_ALL", label="9: __all__ = []", hint="Exports públicos", action_type="SNIPPET", snippet="__all__ = []", cursor_offset_left=1, icon="function"),
        ]


def _build_op_items(lang: str) -> List[MenuAction]:
    """Builds the 9 items for the OPERATORS submenu for the specified language."""
    if lang == LANG_GO:
        slot_0 = MenuAction("OP_ASSIGN_SHORT", "1: :=", "Asignación corta", "SNIPPET", snippet=" := ", icon="operators")
    else:
        slot_0 = MenuAction("OP_ASSIGN", "1: =", "Asignación", "SNIPPET", snippet=" = ", icon="operators")

    if lang == LANG_TYPESCRIPT:
        slot_1 = MenuAction("OP_EQ_STRICT", "2: ===", "Igualdad estricta", "SNIPPET", snippet=" === ", icon="operators")
        slot_2 = MenuAction("OP_NEQ_STRICT", "3: !==", "Desigualdad estricta", "SNIPPET", snippet=" !== ", icon="operators")
        slot_5 = MenuAction("OP_LOGICAL_SUB", "6: && / ||", "Operadores lógicos", "SUBMENU", submenu_id="OP_LOGICAL", icon="operators")
    else:
        slot_1 = MenuAction("OP_EQ", "2: ==", "Comparación igualdad", "SNIPPET", snippet=" == ", icon="operators")
        slot_2 = MenuAction("OP_NEQ", "3: !=", "Comparación desigualdad", "SNIPPET", snippet=" != ", icon="operators")
        if lang == LANG_PYTHON:
            slot_5 = MenuAction("OP_LOGICAL_SUB", "6: and / or", "Operadores lógicos", "SUBMENU", submenu_id="OP_LOGICAL", icon="operators")
        else:
            slot_5 = MenuAction("OP_LOGICAL_SUB", "6: && / ||", "Operadores lógicos", "SUBMENU", submenu_id="OP_LOGICAL", icon="operators")

    slot_3 = MenuAction("OP_PLUSEQ", "4: +=", "Suma acumulativa", "SNIPPET", snippet=" += ", icon="operators")
    pause_slot = create_pause_action("5")
    back_slot = create_back_action("ROOT", "7")
    slot_7 = MenuAction("OP_DELIMITERS_SUB", '8: () [] {} / ""', "Delimitadores y cadenas", "SUBMENU", submenu_id="OP_DELIMITERS", icon="operators")
    slot_8 = MenuAction("OP_PUNCT_SUB", "9: : / , / . / ;", "Puntuación y acceso", "SUBMENU", submenu_id="OP_PUNCT", icon="operators")

    return [slot_0, slot_1, slot_2, slot_3, pause_slot, slot_5, back_slot, slot_7, slot_8]


def _build_op_logical_items(lang: str) -> List[MenuAction]:
    """Builds the 9 items for the OP_LOGICAL submenu for the specified language."""
    pause_slot = create_pause_action("5")
    back_slot = create_back_action("OPERATORS", "7")

    if lang == LANG_PYTHON:
        return [
            MenuAction("OP_AND", "1: and", "Lógico AND", "SNIPPET", snippet=" and ", icon="operators"),
            MenuAction("OP_OR", "2: or", "Lógico OR", "SNIPPET", snippet=" or ", icon="operators"),
            MenuAction("OP_NOT", "3: not", "Lógico NOT", "SNIPPET", snippet="not ", icon="operators"),
            MenuAction("OP_IN", "4: in", "Pertenencia in", "SNIPPET", snippet=" in ", icon="operators"),
            pause_slot,
            MenuAction("OP_IS", "6: is", "Identidad is", "SNIPPET", snippet=" is ", icon="operators"),
            back_slot,
            MenuAction("OP_IS_NOT", "8: is not", "Identidad no es", "SNIPPET", snippet=" is not ", icon="operators"),
            MenuAction("OP_NOT_IN", "9: not in", "No pertenencia", "SNIPPET", snippet=" not in ", icon="operators"),
        ]
    elif lang == LANG_TYPESCRIPT:
        return [
            MenuAction("OP_AND", "1: &&", "Lógico Y", "SNIPPET", snippet=" && ", icon="operators"),
            MenuAction("OP_OR", "2: ||", "Lógico O", "SNIPPET", snippet=" || ", icon="operators"),
            MenuAction("OP_NOT", "3: !", "Negación lógica", "SNIPPET", snippet="!", icon="operators"),
            MenuAction("OP_TYPEOF", "4: typeof", "Comprobación de tipo", "SNIPPET", snippet="typeof ", icon="operators"),
            pause_slot,
            MenuAction("OP_INSTANCEOF", "6: instanceof", "Instancia de clase", "SNIPPET", snippet=" instanceof ", icon="operators"),
            back_slot,
            MenuAction("OP_NULLISH", "8: ??", "Coalescencia nula", "SNIPPET", snippet=" ?? ", icon="operators"),
            MenuAction("OP_TERNARY", "9: ? :", "Operador ternario", "SNIPPET", snippet=" ?  : ", cursor_offset_left=3, icon="operators"),
        ]
    else:  # RUST, CPP, GO
        return [
            MenuAction("OP_AND", "1: &&", "Lógico Y", "SNIPPET", snippet=" && ", icon="operators"),
            MenuAction("OP_OR", "2: ||", "Lógico O", "SNIPPET", snippet=" || ", icon="operators"),
            MenuAction("OP_NOT", "3: !", "Negación lógica", "SNIPPET", snippet="!", icon="operators"),
            MenuAction("OP_LT", "4: <", "Menor que", "SNIPPET", snippet=" < ", icon="operators"),
            pause_slot,
            MenuAction("OP_GT", "6: >", "Mayor que", "SNIPPET", snippet=" > ", icon="operators"),
            back_slot,
            MenuAction("OP_LTE", "8: <=", "Menor o igual", "SNIPPET", snippet=" <= ", icon="operators"),
            MenuAction("OP_GTE", "9: >=", "Mayor o igual", "SNIPPET", snippet=" >= ", icon="operators"),
        ]


def _build_op_delim_items(lang: str) -> List[MenuAction]:
    """Builds the 9 items for the OP_DELIMITERS submenu for the specified language."""
    pause_slot = create_pause_action("5")
    back_slot = create_back_action("OPERATORS", "7")

    p0 = MenuAction("DELIM_PAREN", "1: ()", "Paréntesis con cursor centrado", "SNIPPET", snippet="()", cursor_offset_left=1, icon="operators")
    p1 = MenuAction("DELIM_BRACKET", "2: []", "Corchetes con cursor centrado", "SNIPPET", snippet="[]", cursor_offset_left=1, icon="operators")
    p2 = MenuAction("DELIM_BRACE", "3: {}", "Llaves con cursor centrado", "SNIPPET", snippet="{}", cursor_offset_left=1, icon="operators")
    p3 = MenuAction("DELIM_DQUOTE", '4: ""', "Comillas dobles centradas", "SNIPPET", snippet='""', cursor_offset_left=1, icon="operators")
    p5 = MenuAction("DELIM_SQUOTE", "6: ''", "Comillas simples centradas", "SNIPPET", snippet="''", cursor_offset_left=1, icon="operators")

    if lang == LANG_PYTHON:
        p7 = MenuAction("DELIM_FSTR", '8: f""', "F-string con cursor centrado", "SNIPPET", snippet='f""', cursor_offset_left=1, icon="operators")
        p8 = MenuAction("DELIM_DOCSTR", '9: """..."""', "Docstring triple centrado", "SNIPPET", snippet='""""""', cursor_offset_left=3, icon="operators")
    elif lang == LANG_TYPESCRIPT:
        p7 = MenuAction("DELIM_BQUOTE", "8: ``", "Template literal centrado", "SNIPPET", snippet="``", cursor_offset_left=1, icon="operators")
        p8 = MenuAction("DELIM_INTERP", "9: ${}", "Interpolación de template", "SNIPPET", snippet="${}", cursor_offset_left=1, icon="operators")
    elif lang == LANG_RUST:
        p7 = MenuAction("DELIM_REF", "8: &", "Préstamo / referencia", "SNIPPET", snippet="&", icon="operators")
        p8 = MenuAction("DELIM_RAWSTR", '9: r#""#', "String cruda", "SNIPPET", snippet='r#""#', cursor_offset_left=2, icon="operators")
    elif lang == LANG_CPP:
        p7 = MenuAction("DELIM_DEREF", "8: *", "Puntero / desreferencia", "SNIPPET", snippet="*", icon="operators")
        p8 = MenuAction("DELIM_ARROW", "9: ->", "Acceso a miembro por puntero", "SNIPPET", snippet="->", icon="operators")
    elif lang == LANG_GO:
        p7 = MenuAction("DELIM_RAWSTR", "8: ``", "String multilínea cruda", "SNIPPET", snippet="``", cursor_offset_left=1, icon="operators")
        p8 = MenuAction("DELIM_CHAN", "9: <-", "Envío / recepción de canal", "SNIPPET", snippet="<-", icon="operators")
    else:
        p7 = MenuAction("DELIM_FSTR", '8: f""', "F-string", "SNIPPET", snippet='f""', cursor_offset_left=1, icon="operators")
        p8 = MenuAction("DELIM_DOCSTR", '9: """..."""', "Docstring", "SNIPPET", snippet='""""""', cursor_offset_left=3, icon="operators")

    return [p0, p1, p2, p3, pause_slot, p5, back_slot, p7, p8]


def _build_op_punct_items(lang: str) -> List[MenuAction]:
    """Builds the 9 items for the OP_PUNCT submenu for the specified language."""
    pause_slot = create_pause_action("5")
    back_slot = create_back_action("OPERATORS", "7")

    p0 = MenuAction("PUNCT_COLON", "1: :", "Dos puntos con espacio", "SNIPPET", snippet=": ", icon="operators")
    p1 = MenuAction("PUNCT_COMMA", "2: ,", "Coma con espacio", "SNIPPET", snippet=", ", icon="operators")
    p2 = MenuAction("PUNCT_DOT", "3: .", "Punto de acceso", "SNIPPET", snippet=".", icon="operators")
    p3 = MenuAction("PUNCT_ARROW", "4: ->", "Retorno o puntero flecha", "SNIPPET", snippet=" -> ", icon="operators")
    p5 = MenuAction("PUNCT_UNDERSCORE", "6: _", "Guion bajo / variable muda", "SNIPPET", snippet="_", icon="operators")
    p7 = MenuAction("PUNCT_SEMICOLON", "8: ;", "Punto y coma", "SNIPPET", snippet=";", icon="operators")

    if lang in (LANG_RUST, LANG_CPP):
        p8 = MenuAction("PUNCT_SCOPE", "9: ::", "Resolución de ámbito", "SNIPPET", snippet="::", icon="operators")
    elif lang == LANG_GO:
        p8 = MenuAction("PUNCT_CHAN_ARROW", "9: <-", "Operador de canal", "SNIPPET", snippet=" <- ", icon="operators")
    else:
        p8 = MenuAction("PUNCT_SCOPE", "9: ::", "Resolución de ámbito", "SNIPPET", snippet="::", icon="operators")

    return [p0, p1, p2, p3, pause_slot, p5, back_slot, p7, p8]


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

        # Check Index 6 is ALWAYS Back for all submenus (excluding MENU_STANDARD which is an alternate root)
        if node_id not in ("ROOT", "MENU_STANDARD") and len(node.items) > 6:
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
