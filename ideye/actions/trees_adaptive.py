"""Adaptive AST context node for the 3x3 grid."""

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


def _lazy_build_menu_tree(lang):
    """Late import of the root builder (trees_root imports this module)."""
    from ideye.actions.trees_root import build_menu_tree

    return build_menu_tree(lang)

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
        return _lazy_build_menu_tree(lang)["ROOT"]

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
            return standard_root if standard_root is not None else _lazy_build_menu_tree(lang)["ROOT"]

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
            return standard_root if standard_root is not None else _lazy_build_menu_tree(lang)["ROOT"]

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
            return standard_root if standard_root is not None else _lazy_build_menu_tree(lang)["ROOT"]

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
            return standard_root if standard_root is not None else _lazy_build_menu_tree(lang)["ROOT"]

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
            return standard_root if standard_root is not None else _lazy_build_menu_tree(lang)["ROOT"]

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
