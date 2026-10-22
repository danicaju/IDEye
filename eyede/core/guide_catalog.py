"""Single source of truth for IDEye's interactive Game Manual.

The guide is intentionally data-driven: update the page/card catalog and run
``generate_interactive_guide()`` after any user-facing feature change.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from eyede.core.hotkey_manager import HOTKEY_ACTIONS
    from eyede.core.gesture_detector import GestureDetector
    from eyede.modes.mode_manager import MODE_ORDER, ModeManager
except ImportError:  # pragma: no cover
    from core.hotkey_manager import HOTKEY_ACTIONS
    from core.gesture_detector import GestureDetector
    from modes.mode_manager import MODE_ORDER, ModeManager

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DOCS_DIR = ROOT_DIR / "docs"
GUIDE_PATH = DOCS_DIR / "guia_interactiva.html"

SHORTCUT_LABELS = {
    "q": ("Salida de emergencia", "Cierra IDEye de inmediato desde cualquier ventana."),
    "r": ("Reset de calibración", "Limpia la calibración y vuelve a un mapeo neutral seguro."),
    "v": ("Selector de modos", "Abre el hub de 6 modos para elegir el contexto de trabajo."),
    "k": ("Auto-switch", "Activa o desactiva el cambio automático según la ventana activa."),
    "a": ("Menús inteligentes", "Adapta las casillas al AST y al contexto del editor."),
    "b": ("Portapapeles 3x3", "Abre las últimas 6 copias para reinyectarlas con un gesto."),
    "t": ("Modo de tracking", "Alterna Cabeza, Híbrido e Iris puro."),
    "c": ("Calibrar centro", "Fija la mirada actual como centro neutro."),
    "p": ("Pausa / lectura", "Oculta el HUD para leer o descansar la vista."),
    "m": ("Monitor", "Colapsa o expande el panel de depuración."),
    "n": ("Siguiente pantalla", "Mueve HUD y mapeo de mirada al siguiente monitor."),
    "l": ("Cambiar lenguaje", "Cicla Python, TypeScript, Rust, C++, Go."),
    "h": ("Ayuda", "Abre o cierra la guía rápida de gestos y atajos."),
    "s": ("Sonido", "Activa o silencia la retroalimentación acústica."),
    "f": ("FreeLook", "Activa el ratón directo por mirada."),
    "g": ("Gaming", "Entra en el perfil Gaming con head-joystick."),
}

PAGES: List[Dict[str, Any]] = [
    {
        "id": "basics",
        "tab": "🌟 Explorando IDEye",
        "title": "¡Bienvenido a IDEye!",
        "kicker": "TU CENTRO DE MANDO OCULAR",
        "ribbon": "#fb7185",
        "intro": "Un IDE asistivo que convierte la mirada en intención y la boca en confirmación. Sin teclado, sin ratón, sin voz obligatoria.",
        "cards": [
            {
                "icon": "face",
                "badge": "01",
                "title": "Mira para mover",
                "text": "El cursor ocular sigue tu mirada con filtrado One Euro. Mirar solo ilumina: nunca activa una acción por sí solo.",
                "chip": "Seguimiento < 35 ms",
            },
            {
                "icon": "calibration",
                "badge": "02",
                "title": "Calibración 5 + 1",
                "text": "Mira al centro y a las cuatro esquinas; el sexto paso mide tu MAR para ajustar el clic de boca a tu rostro.",
                "chip": "Perfil por monitor",
            },
            {
                "icon": "mouth",
                "badge": "03",
                "title": "Abre la boca para confirmar",
                "text": "Una apertura breve equivale a un clic. Mantenerla activa el arrastre Jaw-Lock. Nada de dwell-time accidental.",
                "chip": "Clic sin manos",
            },
            {
                "icon": "rest",
                "badge": "04",
                "title": "Descansa la vista",
                "text": "Pausa el HUD con Ctrl+Alt+P o un guiño derecho. Las zonas de reposo evitan el efecto Midas mientras lees.",
                "chip": "Lectura segura",
            },
        ],
    },
    {
        "id": "gestures",
        "tab": "👀 Dominando los Gestos",
        "title": "Tu cara es el mando",
        "kicker": "BOCA, OJOS Y CABEZA",
        "ribbon": "#22d3ee",
        "intro": "Tres canales de entrada, una sola intención. Aprende el timing y el HUD responderá como un gamepad orgánico.",
        "cards": [
            {
                "icon": "mouth",
                "badge": "MAR",
                "title": "¡Dispara el clic con la boca!",
                "text": "Abre la boca por encima del umbral MAR durante un instante: IDEye inyecta el snippet o activa la casilla enfocada.",
                "chip": "Zero-dwell click",
            },
            {
                "icon": "jaw",
                "badge": "55%",
                "title": "Jaw-Lock: arrastra sin soltar",
                "text": "Mantén la boca abierta para entrar en modo arrastre. Suelta para cerrar el gesto. Ideal para seleccionar bloques.",
                "chip": "Drag & drop",
            },
            {
                "icon": "wink",
                "badge": "R",
                "title": "Guiño derecho: pausa",
                "text": "Cierra el ojo derecho ~200 ms para ocultar el HUD o despertarlo. En Gaming alterna joystick y cursor de menú.",
                "chip": "Pausa / Gaming",
            },
            {
                "icon": "wink-left",
                "badge": "L",
                "title": "Guiño izquierdo: atrás",
                "text": "Un guiño izquierdo vuelve al menú anterior, deshace o hace saltar al personaje según el modo activo.",
                "chip": "Back / Undo / Jump",
            },
        ],
    },
    {
        "id": "modes",
        "tab": "🎛️ Los 6 Modos de Poder",
        "title": "Seis formas de trabajar",
        "kicker": "ELIGE TU PODER",
        "ribbon": "#fbbf24",
        "intro": "Cada modo reconfigura las 9 casillas para el contexto correcto. Prueba el simulador y descubre qué hace cada celda.",
        "cards": [
            {
                "icon": "code",
                "badge": "01",
                "title": "Código",
                "text": "Árboles AST, snippets, operadores, variables locales y predicción IA para programar sin teclear.",
                "chip": "AST + IA",
            },
            {
                "icon": "writing",
                "badge": "02",
                "title": "Redacción",
                "text": "Teclado de letras con ñ y acentos, predicción de palabras y frases completas para documentar.",
                "chip": "Letras + palabras",
            },
            {
                "icon": "terminal",
                "badge": "03",
                "title": "Terminal / Git",
                "text": "Comandos, ramas, commits y reparaciones de Git en una cuadrícula táctil ocular.",
                "chip": "Git sin teclado",
            },
            {
                "icon": "data",
                "badge": "04",
                "title": "Datos / Mates",
                "text": "SQL, JSON, YAML, fórmulas y operadores matemáticos agrupados por intención.",
                "chip": "SQL / LaTeX",
            },
            {
                "icon": "navigation",
                "badge": "05",
                "title": "Navegación",
                "text": "Salta a definiciones, archivos, símbolos y paneles de VS Code con la mirada.",
                "chip": "Ir a…",
            },
            {
                "icon": "mouse",
                "badge": "06",
                "title": "FreeLook",
                "text": "Ratón directo por mirada a 60 Hz, con overscan y carril magnético para la barra de tareas.",
                "chip": "60 Hz",
            },
        ],
    },
    {
        "id": "gaming",
        "tab": "🎮 Modo Gaming & Roblox",
        "title": "Juega con la cabeza",
        "kicker": "HEAD-JOYSTICK EDITION",
        "ribbon": "#a78bfa",
        "intro": "Sin mareos: la cabeza mueve al personaje y la boca dispara. El cursor de menú queda para los botones del juego.",
        "cards": [
            {
                "icon": "gamepad",
                "badge": "WASD",
                "title": "Head-Joystick",
                "text": "Mueve la cabeza dentro del área de juego para generar W/A/S/D con zona muerta central. El cursor no se mueve.",
                "chip": "WASD analógico",
            },
            {
                "icon": "cursor",
                "badge": "R",
                "title": "Guiño derecho: cambia de control",
                "text": "Alterna entre joystick de cabeza y cursor de menú para pulsar botones, tiendas o inventarios.",
                "chip": "Joystick ⇄ cursor",
            },
            {
                "icon": "click",
                "badge": "MAR",
                "title": "Boca = clic actual",
                "text": "En modo joystick, la boca hace clic donde está el cursor del juego sin moverlo. En cursor, apunta y confirma.",
                "chip": "Clic sin ratón",
            },
            {
                "icon": "release",
                "badge": "SAFE",
                "title": "Salida segura",
                "text": "Al pausar, cambiar de modo o salir de Gaming se liberan todas las teclas y botones para evitar atascos.",
                "chip": "Release-all",
            },
        ],
    },
    {
        "id": "custom",
        "tab": "🛠️ Personalización",
        "title": "Hazlo tuyo",
        "kicker": "MACROS, PANTALLAS Y PORTAPAPELES",
        "ribbon": "#34d399",
        "intro": "IDEye se adapta a tu flujo: macros propias, varios monitores y una máquina del tiempo para el portapapeles.",
        "cards": [
            {
                "icon": "grid",
                "badge": "3×3",
                "title": "Editor de Macros",
                "text": "Asigna snippets, comandos o teclas del sistema a las 9 celdas. Los cambios se guardan en custom_macros.json.",
                "chip": "Persistente",
            },
            {
                "icon": "monitor",
                "badge": "N",
                "title": "Multi-Monitor",
                "text": "Ctrl+Alt+N mueve el HUD y el mapeo al siguiente monitor. Cada pantalla conserva su perfil de calibración.",
                "chip": "Handover",
            },
            {
                "icon": "clipboard",
                "badge": "6",
                "title": "Máquina del Tiempo",
                "text": "Ctrl+Alt+B abre las últimas seis copias en 3×3. Las escrituras internas de IDEye no contaminan el historial.",
                "chip": "3×3 history",
            },
            {
                "icon": "telemetry",
                "badge": "L2C",
                "title": "Telemetría Look-To-Code",
                "text": "Consulta clics de boca, caracteres inyectados, teclas ahorradas y el mapa de calor de tus celdas.",
                "chip": "Ahorro visible",
            },
        ],
    },
]

GESTURES: List[Dict[str, str]] = [
    {
        "name": "Apertura de boca (MAR)",
        "action": "Clic / inyectar / navegar",
        "description": "Abre la boca brevemente para activar la casilla enfocada.",
        "icon": "mouth",
    },
    {
        "name": "Jaw-Lock",
        "action": "Arrastrar / seleccionar",
        "description": "Mantén la boca abierta para arrastrar sin botones.",
        "icon": "jaw",
    },
    {
        "name": "Guiño derecho",
        "action": "Pausa / Gaming: joystick ⇄ cursor",
        "description": "Cierra el ojo derecho ~200 ms para ocultar el HUD o cambiar el control de juego.",
        "icon": "wink",
    },
    {
        "name": "Guiño izquierdo",
        "action": "Volver / deshacer / saltar",
        "description": "Cierra el ojo izquierdo ~200 ms para retroceder o deshacer.",
        "icon": "wink-left",
    },
    {
        "name": "Head-Joystick",
        "action": "WASD en Gaming",
        "description": "Mueve la cabeza fuera de la zona muerta para caminar sin tocar el cursor.",
        "icon": "gamepad",
    },
]

FALLBACK_SIMULATOR: Dict[str, Dict[str, Any]] = {
    "coding": {
        "name": "Código",
        "cells": [
            {"label": "FLUJO", "hint": "if / for / while"},
            {"label": "FUNC", "hint": "def / class"},
            {"label": "OPERADORES", "hint": "símbolos y comparaciones"},
            {"label": "CURSOR", "hint": "movimiento y selección"},
            {"label": "PAUSA", "hint": "modo lectura"},
            {"label": "KEYWORDS", "hint": "return / import / pass"},
            {"label": "EDIT", "hint": "deshacer y borrar"},
            {"label": "ENTER/TAB", "hint": "saltos y sangría"},
            {"label": "IA", "hint": "predicciones de código"},
        ],
    },
    "writing": {
        "name": "Redacción",
        "cells": [
            {"label": "CONECTORES", "hint": "además, sin embargo…"},
            {"label": "FORMATO", "hint": "títulos y Markdown"},
            {"label": "PUNTUACIÓN", "hint": "signos y comillas"},
            {"label": "CURSOR", "hint": "mover y seleccionar"},
            {"label": "PAUSA", "hint": "descanso visual"},
            {"label": "LETRAS", "hint": "teclado a-z + ñ"},
            {"label": "BORRAR", "hint": "deshacer y borrar"},
            {"label": "SALTOS", "hint": "enter, tab, párrafo"},
            {"label": "IA", "hint": "sugerencias de redacción"},
        ],
    },
    "terminal": {
        "name": "Terminal",
        "cells": [
            {"label": "GIT", "hint": "status / add / commit"},
            {"label": "RAMAS", "hint": "checkout / merge"},
            {"label": "ARCHIVOS", "hint": "ls / cd / cat"},
            {"label": "CURSOR", "hint": "movimiento de línea"},
            {"label": "PAUSA", "hint": "descanso visual"},
            {"label": "COMANDOS", "hint": "pip / npm / make"},
            {"label": "BORRAR", "hint": "limpiar y deshacer"},
            {"label": "EJECUTAR", "hint": "enter y flags"},
            {"label": "AYUDA", "hint": "git help y man"},
        ],
    },
    "sniper": {
        "name": "Gaming",
        "cells": [
            {"label": "W", "hint": "avanzar"},
            {"label": "A", "hint": "izquierda"},
            {"label": "S", "hint": "retroceder"},
            {"label": "D", "hint": "derecha"},
            {"label": "PAUSA", "hint": "descanso visual"},
            {"label": "SALTO", "hint": "guiño izquierdo"},
            {"label": "CLIC", "hint": "boca / clic actual"},
            {"label": "CURSOR", "hint": "guiño derecho"},
            {"label": "360°", "hint": "cámara con mirada"},
        ],
    },
}


def _display_shortcuts() -> List[Dict[str, str]]:
    shortcuts: List[Dict[str, str]] = []
    for spec, _handler in HOTKEY_ACTIONS.items():
        key = spec.rsplit("+", 1)[-1].replace(">", "")
        label, description = SHORTCUT_LABELS.get(
            key, (key.upper(), "Atajo global de IDEye.")
        )
        shortcuts.append(
            {
                "key": f"Ctrl+Alt+{key.upper()}",
                "label": label,
                "description": description,
            }
        )
    return shortcuts


def _display_modes() -> List[Dict[str, str]]:
    modes: List[Dict[str, str]] = []
    try:
        manager = ModeManager(initial_mode="coding", auto_switch_enabled=False)
        for mode_id in MODE_ORDER:
            mode = manager.modes.get(mode_id)
            if mode is None:
                continue
            modes.append(
                {
                    "id": mode_id,
                    "name": str(getattr(mode, "display_name", mode_id)),
                    "color": str(getattr(mode, "theme_color", "#38bdf8")),
                }
            )
    except Exception:
        for mode_id in MODE_ORDER:
            modes.append({"id": mode_id, "name": mode_id.replace("_", " ").title(), "color": "#38bdf8"})
    return modes


def _simulator() -> Dict[str, Dict[str, Any]]:
    simulator = {key: {"name": value["name"], "cells": list(value["cells"])} for key, value in FALLBACK_SIMULATOR.items()}
    try:
        manager = ModeManager(initial_mode="coding", auto_switch_enabled=False)
        for mode_id in ("coding", "writing", "terminal"):
            mode = manager.modes.get(mode_id)
            if mode is None or not hasattr(mode, "get_root_menu"):
                continue
            root = mode.get_root_menu()
            cells = [
                {"label": str(getattr(item, "label", "—")), "hint": str(getattr(item, "hint", "Acción del modo"))}
                for item in root.items
            ]
            if len(cells) == 9:
                simulator[mode_id] = {"name": str(getattr(mode, "display_name", mode_id)), "cells": cells}
    except Exception:
        pass
    return simulator


def _gesture_thresholds() -> Dict[str, Any]:
    try:
        detector = GestureDetector()
        return {
            "mar_threshold": round(float(detector.mar_threshold), 3),
            "ear_close": round(float(detector.ear_close_threshold), 3),
            "wink_ms": int(round(float(detector.wink_min_hold_sec) * 1000)),
            "wink_max_ms": int(round(float(detector.wink_max_hold_sec) * 1000)),
        }
    except Exception:
        return {"mar_threshold": 0.45, "ear_close": 0.16, "wink_ms": 150, "wink_max_ms": 450}


def build_catalog() -> Dict[str, Any]:
    """Builds the live catalog consumed by the HTML builder."""
    return {
        "pages": PAGES,
        "gestures": GESTURES,
        "gesture_thresholds": _gesture_thresholds(),
        "shortcuts": _display_shortcuts(),
        "modes": _display_modes(),
        "simulator": _simulator(),
    }


def generate_interactive_guide(path: Optional[os.PathLike | str] = None) -> Path:
    """Regenerates the self-contained interactive guide and returns its path."""
    from eyede.core.guide_builder import build_interactive_guide_html

    target = Path(path) if path is not None else GUIDE_PATH
    html_text = build_interactive_guide_html(build_catalog())
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(html_text, encoding="utf-8")
    except OSError:
        target = Path(tempfile.gettempdir()) / "IDEye" / "guia_interactiva.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(html_text, encoding="utf-8")
    return target


__all__ = ["GUIDE_PATH", "build_catalog", "generate_interactive_guide"]
