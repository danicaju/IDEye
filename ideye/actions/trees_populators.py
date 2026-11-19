"""Dynamic item populators (AI, symbols, help, exit, language)."""

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
            label="4: Atajos de modos y menús",
            hint="Ctrl+Alt+A menús inteligentes, Ctrl+Alt+T seguimiento, Ctrl+Alt+V elegir modo",
            action_type="INFO",
            icon="",
        ),
        create_pause_action("5"),
        MenuAction(
            id="HELP_SHORTCUTS_2",
            label="6: Atajos de pantalla y calibración",
            hint="Ctrl+Alt+M monitor, Ctrl+Alt+N siguiente pantalla, Ctrl+Alt+C calibrar centro, Ctrl+Alt+K cambio automático",
            action_type="INFO",
            icon="",
        ),
        create_back_action(parent_id, "7"),
        MenuAction(
            id="HELP_SHORTCUTS_3",
            label="8: Atajos de pausa y lenguaje",
            hint="Ctrl+Alt+P pausa, Ctrl+Alt+B portapapeles, Ctrl+Alt+L lenguaje, Ctrl+Alt+S sonido, Ctrl+Alt+F FreeLook, Ctrl+Alt+G Gaming, Ctrl+Alt+Q salida de emergencia",
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


def get_dynamic_ast_action_for_context(
    context_info: Union[Dict[str, Any], str],
    language: str = "PYTHON",
    key_num: str = "9",
) -> MenuAction:
    """
    Returns an immediate dynamic AST action for Block 9 based on real-time cursor context.
    Provides 1-dwell activation of the most relevant syntax construct or spotlight.
    """
    lang = normalize_language(language)
    if isinstance(context_info, str):
        ctx_type = context_info.upper()
    elif isinstance(context_info, dict):
        ctx_type = str(context_info.get("context", "GENERAL")).upper()
    else:
        ctx_type = "GENERAL"

    if ctx_type == "FUNCTION_SIGNATURE":
        if lang == LANG_TYPESCRIPT:
            return MenuAction("DYN_TS_RETURN", f"{key_num}: return", "Sentencia return", "SNIPPET", snippet="return ", icon="flow")
        elif lang == LANG_RUST:
            return MenuAction("DYN_RS_OK", f"{key_num}: Ok(())", "Resultado exitoso", "SNIPPET", snippet="Ok(())", icon="flow")
        return MenuAction("DYN_PY_DOCSTRING", f"{key_num}: docstring", "Documentar función", "SNIPPET", snippet='"""\nArgs:\n    \nReturns:\n    \n"""\n', icon="function")

    elif ctx_type == "TRY_BLOCK":
        if lang == LANG_TYPESCRIPT:
            return MenuAction("DYN_TS_CATCH", f"{key_num}: catch (err)", "Capturar error", "SNIPPET", snippet="catch (error) {\n    console.error(error);\n}", icon="flow")
        elif lang == LANG_RUST:
            return MenuAction("DYN_RS_MATCH", f"{key_num}: match res", "Coincidencia de patrones", "SNIPPET", snippet="match res {\n    Ok(val) => val,\n    Err(e) => return Err(e),\n}", icon="flow")
        return MenuAction("DYN_PY_EXCEPT", f"{key_num}: except Exception", "Captura segura", "SNIPPET", snippet="except Exception as exc:\n    logger.error(f'Error: {exc}')\n    raise", icon="flow")

    elif ctx_type == "LOOP_BLOCK":
        return MenuAction("DYN_LOOP_BREAK", f"{key_num}: break / cont", "Control de bucle", "SNIPPET", snippet="break;", icon="flow")

    elif ctx_type == "IF_BLOCK":
        if lang == LANG_TYPESCRIPT:
            return MenuAction("DYN_TS_ELSE", f"{key_num}: else", "Rama alternativa", "SNIPPET", snippet="else {\n    \n}", cursor_offset_up=1, icon="flow")
        return MenuAction("DYN_PY_ELIF", f"{key_num}: elif / else", "Rama condicional", "SNIPPET", snippet="elif :\n    pass", cursor_offset_up=1, cursor_offset_left=5, icon="flow")

    elif ctx_type == "CLASS_BODY":
        if lang == LANG_TYPESCRIPT:
            return MenuAction("DYN_TS_CTOR", f"{key_num}: constructor()", "Constructor de clase", "SNIPPET", snippet="constructor() {\n    super();\n}", icon="function")
        elif lang == LANG_RUST:
            return MenuAction("DYN_RS_NEW", f"{key_num}: pub fn new()", "Constructor new", "SNIPPET", snippet="pub fn new() -> Self {\n    Self {}\n}", icon="function")
        return MenuAction("DYN_PY_INIT", f"{key_num}: def __init__", "Constructor Python", "SNIPPET", snippet="def __init__(self) -> None:\n    super().__init__()\n", icon="function")

    # Default fallback: Gaze Command Palette / Spotlight
    return MenuAction(
        id="SWITCH_COMMAND_PALETTE",
        label=f"{key_num}: SPOTLIGHT",
        hint="Paleta de comandos por mirada",
        action_type="SUBMENU",
        submenu_id="COMMAND_PALETTE",
        icon="wand",
        sticky=False,
    )
