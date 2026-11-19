"""Phase 12: deep semantic coding taxonomy and environment-aware mode trees.

The builders are pure and deterministic: they take the active language and
local symbols and return complete 3x3 ``MenuNode`` trees. The UI can rebuild a
tree at any time without restarting IDEye.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

try:
    from ideye.actions.menu_trees import (
        MenuAction,
        MenuNode,
        create_back_action,
        create_pause_action,
    )
except ImportError:  # pragma: no cover
    from actions.menu_trees import (  # type: ignore
        MenuAction,
        MenuNode,
        create_back_action,
        create_pause_action,
    )


from ideye.actions.taxonomy_templates import (  # noqa: F401
    CURSOR,
    SLOTS,
    KEY_LABELS,
    ROOT_KEY_LABELS,
    _slot_key,
    CATEGORY_SPECS,
    normalize_taxonomy_language,
    _clean_symbols,
    _singular,
    _pick_list,
    _pick_scalar,
    _lang_templates,
)



def _action(action_id: str, label: str, text: str, icon: str = "function", hint: str = "") -> MenuAction:
    clean = str(text)
    offset = 0
    marker = clean.find(CURSOR)
    if marker >= 0:
        clean = clean.replace(CURSOR, "", 1)
        offset = max(0, len(clean) - marker)
    return MenuAction(
        id=action_id,
        label=label,
        hint=hint or label,
        action_type="SNIPPET",
        snippet=clean,
        cursor_offset_left=offset,
        icon=icon,
    )



def _category_node(category_id: str, title: str, actions: List[MenuAction], parent_id: str = "ROOT") -> MenuNode:
    items: List[MenuAction] = [None] * 9  # type: ignore[list-item]
    for index, action in zip(SLOTS, actions[:6]):
        items[index] = action
    items[4] = create_pause_action("5")
    items[6] = create_back_action(parent_id, "7")
    items[8] = MenuAction(
        id=f"{category_id}_REFRESH",
        label="9: ACTUALIZAR",
        hint="Releer símbolos y contexto en vivo",
        action_type="SEMANTIC_REFRESH",
        icon="refresh",
    )
    return MenuNode(
        id=category_id,
        title=title,
        breadcrumb_label=title,
        items=items,
        parent_id=parent_id,
        sticky=False,
    )


def _ai_actions(suggestions: Optional[Sequence[str]], document_context: bool) -> List[MenuAction]:
    defaults = (
        ["Continuar la frase actual", "Desarrollar el párrafo con argumentos", "Sintetizar en puntos clave", "Redactar conclusión o transición", "Insertar conector formal", "Resumir la selección"]
        if document_context
        else ["Cerrar la lógica pendiente", "Completar la condición con variables locales", "Implementar el cuerpo de la función", "Corregir el error activo", "Añadir validación defensiva", "Extraer una función auxiliar"]
    )
    values = [str(s).strip() for s in (suggestions or []) if str(s).strip()]
    for fallback in defaults:
        if len(values) >= 6:
            break
        if fallback not in values:
            values.append(fallback)
    actions: List[MenuAction] = []
    for index, value in enumerate(values[:6]):
        actions.append(_action(f"SEM_AI_{index + 1}", f"{KEY_LABELS[index]}: {value[:30]}", value, "ai_spark", value))
    return actions


def build_semantic_coding_tree(
    language: str = "PYTHON",
    symbols: Optional[Sequence[Any]] = None,
    ai_suggestions: Optional[Sequence[str]] = None,
    document_context: bool = False,
) -> Dict[str, MenuNode]:
    """Builds the deep Phase 12 coding taxonomy for the active language."""
    lang = normalize_taxonomy_language(language)
    syms = _clean_symbols(symbols)
    templates = _lang_templates(lang, syms)
    tree: Dict[str, MenuNode] = {}
    root_items: List[MenuAction] = [None] * 9  # type: ignore[list-item]
    for slot, spec in zip((0, 1, 2, 3, 5, 6, 7, 8), CATEGORY_SPECS):
        category_id, title, icon, _ = spec
        actions = [
            _action(f"{category_id}_{index + 1}", f"{KEY_LABELS[index]}: {label}", text, action_icon)
            for index, (label, text, action_icon) in enumerate(templates.get(category_id, [])[:6])
        ]
        if category_id == "SEM_AI":
            actions = _ai_actions(ai_suggestions, document_context)
        tree[category_id] = _category_node(category_id, title, actions)
        root_items[slot] = MenuAction(
            id=category_id,
            label=f"{_slot_key(slot)}: {title}",
            hint=f"Abrir {title.lower()}",
            action_type="SUBMENU",
            submenu_id=category_id,
            icon=icon,
        )
    root_items[4] = create_pause_action("5")
    tree["ROOT"] = MenuNode(
        id="ROOT",
        title="CÓDIGO / TAXONOMÍA",
        breadcrumb_label="CÓDIGO",
        items=root_items,
        parent_id=None,
        sticky=False,
    )
    return tree


_PROJECT_CONTEXT_CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}
_CACHE_TTL_SEC: float = 5.0


def clear_project_context_cache() -> None:
    """Clears the cached git project context (useful for testing or manual refresh)."""
    _PROJECT_CONTEXT_CACHE.clear()


def detect_project_context(
    workspace_dir: Optional[str] = None, force_refresh: bool = False
) -> Dict[str, Any]:
    """Safe, bounded inspection of the current repository for Terminal mode.

    Caches results per workspace root to avoid repeated git execution.
    On Windows, uses CREATE_NO_WINDOW and hidden STARTUPINFO to prevent
    console window popups.
    """
    root = os.path.abspath(workspace_dir or os.getcwd())
    now = time.time()
    if not force_refresh and root in _PROJECT_CONTEXT_CACHE:
        cached_time, cached_val = _PROJECT_CONTEXT_CACHE[root]
        if now - cached_time < _CACHE_TTL_SEC:
            return dict(cached_val)

    result: Dict[str, Any] = {
        "root": root,
        "branch": "",
        "status": [],
        "project_type": "generic",
        "files": [],
    }
    for marker, kind in (
        ("pyproject.toml", "python"),
        ("package.json", "node"),
        ("Cargo.toml", "rust"),
        ("Makefile", "make"),
        ("pom.xml", "java"),
        ("build.gradle", "java"),
    ):
        if os.path.isfile(os.path.join(root, marker)):
            result["project_type"] = kind
            result["files"].append(marker)

    subp_kwargs: Dict[str, Any] = {
        "cwd": root,
        "capture_output": True,
        "text": True,
        "timeout": 2,
        "check": False,
    }
    if sys.platform == "win32":
        subp_kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        si = subprocess.STARTUPINFO()
        si.dwFlags |= getattr(subprocess, "STARTF_USESHOWWINDOW", 1)
        si.wShowWindow = 0  # SW_HIDE
        subp_kwargs["startupinfo"] = si

    try:
        branch = subprocess.run(
            ["git", "branch", "--show-current"],
            **subp_kwargs,
        )
        result["branch"] = (branch.stdout or "").strip()
        status = subprocess.run(
            ["git", "status", "--short"],
            **subp_kwargs,
        )
        result["status"] = [
            line for line in (status.stdout or "").splitlines() if line.strip()
        ][:12]
    except (OSError, subprocess.SubprocessError):
        pass

    _PROJECT_CONTEXT_CACHE[root] = (now, dict(result))
    return result


def build_terminal_semantic_tree(project_context: Optional[Dict[str, Any]] = None) -> Dict[str, MenuNode]:
    ctx = project_context or detect_project_context()
    branch = str(ctx.get("branch") or "sin rama")
    modified = len(ctx.get("status") or [])
    tree: Dict[str, MenuNode] = {}
    specs = [
        ("TERM_SMART_GIT", "GIT INTELIGENTE", [("Estado", "git status --short", "flow"), ("Añadir todo", "git add .", "flow"), ("Commit", 'git commit -m "[[CURSOR]]"', "format"), ("Push", "git push", "format"), ("Pull", "git pull", "format"), ("Rama actual", f"git branch --show-current", "navigation")]),
        ("TERM_BUILD", "EJECUTAR Y COMPILAR", [("Ejecutar", "python main.py", "terminal"), ("Compilar", "python -m compileall .", "terminal"), ("Instalar", "pip install -r requirements.txt", "terminal"), ("Build", "python build_app.py", "terminal"), ("Test rápido", "pytest -q", "test"), ("Limpiar", "python -m compileall -q .", "terminal")]),
        ("TERM_TEST", "PYTEST Y COBERTURA", [("Pytest", "pytest -v", "test"), ("Cobertura", "pytest --cov=. --cov-report=term-missing", "test"), ("Un test", "pytest -q -k [[CURSOR]]", "test"), ("Fallos", "pytest -x --tb=short", "test"), ("Watch", "pytest -f", "test"), ("Reporte", "coverage html", "test")]),
        ("TERM_ENV", "ENTORNOS Y PAQUETES", [("Activar venv", "venv\\Scripts\\activate", "terminal"), ("Pip list", "pip list", "terminal"), ("Instalar", "pip install [[CURSOR]]", "terminal"), ("Procesos", "tasklist", "terminal"), ("Python", "python --version", "terminal"), ("Entorno", "set", "terminal")]),
        ("TERM_PATHS", "RUTAS Y ARCHIVOS", [("Listar", "dir", "navigation"), ("Subir", "cd ..", "navigation"), ("Crear", "mkdir [[CURSOR]]", "navigation"), ("Ruta", "cd [[CURSOR]]", "navigation"), ("Actual", "cd", "navigation"), ("Árbol", "tree /F", "navigation")]),
        ("TERM_CLEAN", "LIMPIEZA Y SEÑALES", [("Limpiar", "cls", "edit"), ("Cancelar", "CTRL_C", "edit"), ("Salir", "exit", "edit"), ("Borrar", "del [[CURSOR]]", "edit"), ("Historial", "doskey /history", "navigation"), ("Reset", "git restore .", "edit")]),
        ("TERM_PIPE", "TUBERÍAS Y FLAGS", [("Pipe", " | ", "operators"), ("Y lógico", " && ", "operators"), ("Redirigir", " > ", "operators"), ("Append", " >> ", "operators"), ("Ayuda", " --help", "operators"), ("Fondo", " &", "operators")]),
        ("TERM_AI", "SUGERENCIAS IA", [("Estado", "git status", "ai_spark"), ("Commit", 'git commit -m "feat: [[CURSOR]]"', "ai_spark"), ("Test", "pytest -q", "ai_spark"), ("Build", "python build_app.py", "ai_spark"), ("Rama", f"git checkout -b feature/{branch}", "ai_spark"), ("Diff", "git diff --stat", "ai_spark")]),
    ]
    root_items: List[MenuAction] = [None] * 9  # type: ignore[list-item]
    for slot, (node_id, title, actions) in zip((0, 1, 2, 3, 5, 6, 7, 8), specs):
        menu_actions = [_action(f"{node_id}_{i+1}", f"{KEY_LABELS[i]}: {label}", text, icon) for i, (label, text, icon) in enumerate(actions)]
        tree[node_id] = _category_node(node_id, title, menu_actions)
        root_items[slot] = MenuAction(
            id=node_id,
            label=f"{_slot_key(slot)}: {title}",
            hint=f"{branch} · {modified} cambios",
            action_type="SUBMENU",
            submenu_id=node_id,
            icon="terminal",
        )
    root_items[4] = create_pause_action("5")
    tree["ROOT"] = MenuNode(id="ROOT", title="TERMINAL INTELIGENTE", breadcrumb_label="TERMINAL", items=root_items, parent_id=None, sticky=False)
    return tree


def build_navigation_dual_tree(document_mode: bool = False) -> Dict[str, MenuNode]:
    tree: Dict[str, MenuNode] = {}
    if document_mode:
        specs = [
            ("NAV_DOC_HEAD", "ENCABEZADOS", [("H1", "CTRL_ALT_1", "navigation"), ("H2", "CTRL_ALT_2", "navigation"), ("H3", "CTRL_ALT_3", "navigation"), ("Título", "CTRL_ALT_0", "navigation"), ("Párrafo", "CTRL_ALT_0", "navigation"), ("Limpiar formato", "CTRL_BACKSLASH", "edit")]),
            ("NAV_DOC_LIST", "LISTAS", [("Viñetas", "CTRL_SHIFT_8", "navigation"), ("Numerada", "CTRL_SHIFT_7", "navigation"), ("Sangría", "TAB", "navigation"), ("Quitar sangría", "SHIFT_TAB", "navigation"), ("Checklist", "CTRL_SHIFT_9", "navigation"), ("Cita", "CTRL_SHIFT_9", "navigation")]),
            ("NAV_DOC_FIND", "BUSCAR", [("Buscar", "CTRL_F", "navigation"), ("Siguiente", "F3", "navigation"), ("Anterior", "SHIFT_F3", "navigation"), ("Reemplazar", "CTRL_H", "navigation"), ("Ir a", "CTRL_G", "navigation"), ("Cerrar", "ESC", "navigation")]),
            ("NAV_DOC_TABS", "PESTAÑAS", [("Siguiente", "CTRL_TAB", "navigation"), ("Anterior", "CTRL_SHIFT_TAB", "navigation"), ("Nueva", "CTRL_T", "navigation"), ("Cerrar", "CTRL_W", "navigation"), ("Reabrir", "CTRL_SHIFT_T", "navigation"), ("Ventana", "CTRL_N", "navigation")]),
            ("NAV_DOC_ZOOM", "ZOOM Y LECTURA", [("Acercar", "CTRL_PLUS", "navigation"), ("Alejar", "CTRL_MINUS", "navigation"), ("100%", "CTRL_0", "navigation"), ("Pantalla", "F11", "navigation"), ("Scroll arriba", "PAGE_UP", "navigation"), ("Scroll abajo", "PAGE_DOWN", "navigation")]),
            ("NAV_DOC_EDIT", "EDICIÓN", [("Deshacer", "CTRL_Z", "edit"), ("Rehacer", "CTRL_Y", "edit"), ("Copiar", "CTRL_C", "edit"), ("Pegar", "CTRL_V", "edit"), ("Seleccionar todo", "CTRL_A", "edit"), ("Comentar", "CTRL_ALT_M", "edit")]),
            ("NAV_DOC_SCROLL", "SCROLL SUAVE", [("Arriba", "PAGE_UP", "navigation"), ("Abajo", "PAGE_DOWN", "navigation"), ("Inicio", "CTRL_HOME", "navigation"), ("Fin", "CTRL_END", "navigation"), ("Scroll ocular", "GAZE_SCROLL", "navigation"), ("Centrar", "CTRL_HOME", "navigation")]),
            ("NAV_DOC_AI", "IA DE DOCUMENTO", [("Continuar", "continuar la frase", "ai_spark"), ("Desarrollar", "desarrollar el párrafo", "ai_spark"), ("Resumir", "resumir la selección", "ai_spark"), ("Conclusión", "redactar conclusión", "ai_spark"), ("Conector", "insertar conector formal", "ai_spark"), ("Formato", "formatear selección", "ai_spark")]),
        ]
    else:
        specs = [
            ("NAV_GOTO", "SALTAR", [("Definición", "F12", "navigation"), ("Referencias", "SHIFT_F12", "navigation"), ("Símbolo", "CTRL_SHIFT_O", "navigation"), ("Archivo", "CTRL_P", "navigation"), ("Línea", "CTRL_G", "navigation"), ("Atrás", "ALT_LEFT", "navigation")]),
            ("NAV_FOLD", "PLEGAR / DIVIDIR", [("Plegar", "CTRL_SHIFT_LBRACKET", "navigation"), ("Desplegar", "CTRL_SHIFT_RBRACKET", "navigation"), ("Plegar todo", "CTRL_K_CTRL_0", "navigation"), ("Desplegar todo", "CTRL_K_CTRL_J", "navigation"), ("Dividir editor", "CTRL_BACKSLASH", "navigation"), ("Cerrar grupo", "CTRL_W", "navigation")]),
            ("NAV_RECENT", "ARCHIVOS RECIENTES", [("Reciente 1", "CTRL_TAB", "navigation"), ("Reciente 2", "CTRL_SHIFT_TAB", "navigation"), ("Reabrir", "CTRL_SHIFT_T", "navigation"), ("Explorador", "CTRL_SHIFT_E", "navigation"), ("Guardar", "CTRL_S", "navigation"), ("Guardar todo", "CTRL_K_S", "navigation")]),
            ("NAV_SCROLL", "SCROLL OCULAR", [("Arriba", "PAGE_UP", "navigation"), ("Abajo", "PAGE_DOWN", "navigation"), ("Inicio", "CTRL_HOME", "navigation"), ("Fin", "CTRL_END", "navigation"), ("Scroll continuo", "GAZE_SCROLL", "navigation"), ("Centrar", "CTRL_HOME", "navigation")]),
            ("NAV_SEARCH", "BUSCAR", [("Buscar", "CTRL_F", "navigation"), ("Archivos", "CTRL_SHIFT_F", "navigation"), ("Reemplazar", "CTRL_H", "navigation"), ("Global", "CTRL_SHIFT_H", "navigation"), ("Siguiente", "F3", "navigation"), ("Anterior", "SHIFT_F3", "navigation")]),
            ("NAV_TABS", "PESTAÑAS", [("Siguiente", "CTRL_TAB", "navigation"), ("Anterior", "CTRL_SHIFT_TAB", "navigation"), ("Cerrar", "CTRL_W", "navigation"), ("Reabrir", "CTRL_SHIFT_T", "navigation"), ("Nueva", "CTRL_T", "navigation"), ("Foco lateral", "CTRL_1", "navigation")]),
            ("NAV_EDIT", "EDICIÓN", [("Deshacer", "CTRL_Z", "edit"), ("Rehacer", "CTRL_Y", "edit"), ("Formatear", "SHIFT_ALT_F", "edit"), ("Renombrar", "F2", "edit"), ("Quick fix", "CTRL_DOT", "edit"), ("Comandos", "CTRL_SHIFT_P", "edit")]),
            ("NAV_AI", "IA DE CÓDIGO", [("Explicar", "explicar el código", "ai_spark"), ("Referencias", "buscar referencias", "ai_spark"), ("Tests", "generar tests", "ai_spark"), ("Docs", "generar documentación", "ai_spark"), ("Refactor", "refactorizar", "ai_spark"), ("Optimizar", "optimizar", "ai_spark")]),
        ]
    root_items: List[MenuAction] = [None] * 9  # type: ignore[list-item]
    for slot, (node_id, title, actions) in zip((0, 1, 2, 3, 5, 6, 7, 8), specs):
        menu_actions = []
        for i, (label, value, icon) in enumerate(actions):
            if value in {"GAZE_SCROLL"}:
                action = MenuAction(f"{node_id}_{i+1}", f"{KEY_LABELS[i]}: {label}", label, "GAZE_SCROLL", icon=icon)
            elif value.isupper() or "_" in value:
                action = MenuAction(f"{node_id}_{i+1}", f"{KEY_LABELS[i]}: {label}", label, "KEY", key_name=value, icon=icon)
            else:
                action = _action(f"{node_id}_{i+1}", f"{KEY_LABELS[i]}: {label}", value, icon)
            menu_actions.append(action)
        tree[node_id] = _category_node(node_id, title, menu_actions)
        root_items[slot] = MenuAction(node_id, f"{_slot_key(slot)}: {title}", f"Abrir {title.lower()}", "SUBMENU", submenu_id=node_id, icon="navigation")
    root_items[4] = create_pause_action("5")
    title = "LECTURA / DOCUMENTO" if document_mode else "NAVEGACIÓN / IDE"
    tree["ROOT"] = MenuNode(id="ROOT", title=title, breadcrumb_label=title, items=root_items, parent_id=None, sticky=False)
    return tree


def build_debug_semantic_tree(symbols: Optional[Sequence[Any]] = None) -> Dict[str, MenuNode]:
    syms = _clean_symbols(symbols) or ["value", "result", "item"]
    inspect_actions = [("Inspeccionar", f"print({name})", "terminal") for name in syms[:6]]
    specs = [
        ("DBG_LOCALS", "INSPECCIONAR VARIABLES", inspect_actions),
        ("DBG_BREAK", "BREAKPOINTS CONDICIONALES", [("Breakpoint", "F9", "shield"), ("Condicional", "SHIFT_F9", "shield"), ("Logpoint", "CTRL_SHIFT_F9", "shield"), ("Eliminar", "CTRL_SHIFT_F9", "shield"), ("Desactivar", "CTRL_F9", "shield"), ("Listar", "CTRL_SHIFT_F8", "shield")]),
        ("DBG_STEP", "PASO A PASO", [("Step over", "F10", "navigation"), ("Step into", "F11", "navigation"), ("Step out", "SHIFT_F11", "navigation"), ("Continuar", "F5", "navigation"), ("Pausar", "F6", "navigation"), ("Reiniciar", "CTRL_SHIFT_F5", "navigation")]),
        ("DBG_STACK", "PILA DE LLAMADAS", [("Subir", "UP", "navigation"), ("Bajar", "DOWN", "navigation"), ("Marco actual", "ENTER", "navigation"), ("Copiar pila", "CTRL_C", "navigation"), ("Reiniciar", "CTRL_SHIFT_F5", "navigation"), ("Cerrar", "SHIFT_F5", "navigation")]),
        ("DBG_WATCH", "WATCH", [("Añadir", "watch", "variables"), ("Editar", "edit watch", "variables"), ("Eliminar", "remove watch", "variables"), ("Evaluar", "evaluate", "variables"), ("Copiar", "copy value", "variables"), ("Limpiar", "clear watches", "variables")]),
        ("DBG_CONSOLE", "CONSOLA", [("Abrir", "CTRL_SHIFT_Y", "terminal"), ("Limpiar", "clear", "terminal"), ("Ejecutar", "ENTER", "terminal"), ("Historial", "UP", "terminal"), ("Copiar", "CTRL_C", "terminal"), ("Cerrar", "ESC", "terminal")]),
        ("DBG_SESSION", "SESIONES Y CONFIG", [("Iniciar", "F5", "shield"), ("Detener", "SHIFT_F5", "shield"), ("Reiniciar", "CTRL_SHIFT_F5", "shield"), ("Configurar", "edit configuration", "shield"), ("Guardar log", "save log", "shield"), ("Abrir panel", "CTRL_SHIFT_D", "shield")]),
        ("DBG_AI", "IA DE DEBUG", [("Explicar fallo", "explicar el fallo", "ai_spark"), ("Causa raíz", "analizar causa raíz", "ai_spark"), ("Fix", "proponer fix", "ai_spark"), ("Test", "generar test de regresión", "ai_spark"), ("Logs", "añadir logs", "ai_spark"), ("Resumen", "resumir la pila", "ai_spark")]),
    ]
    tree: Dict[str, MenuNode] = {}
    root_items: List[MenuAction] = [None] * 9  # type: ignore[list-item]
    for slot, (node_id, title, actions) in zip((0, 1, 2, 3, 5, 6, 7, 8), specs):
        menu_actions = []
        for i, (label, value, icon) in enumerate(actions):
            if value.isupper() or "_" in value:
                menu_actions.append(MenuAction(f"{node_id}_{i+1}", f"{KEY_LABELS[i]}: {label}", label, "KEY", key_name=value, icon=icon))
            else:
                menu_actions.append(_action(f"{node_id}_{i+1}", f"{KEY_LABELS[i]}: {label}", value, icon))
        tree[node_id] = _category_node(node_id, title, menu_actions)
        root_items[slot] = MenuAction(node_id, f"{_slot_key(slot)}: {title}", f"Abrir {title.lower()}", "SUBMENU", submenu_id=node_id, icon="shield")
    root_items[4] = create_pause_action("5")
    tree["ROOT"] = MenuNode(id="ROOT", title="DEBUG / INSPECCIÓN", breadcrumb_label="DEBUG", items=root_items, parent_id=None, sticky=False)
    return tree
