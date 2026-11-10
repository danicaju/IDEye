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
    from ideye.core.hotkey_manager import HOTKEY_ACTIONS
    from ideye.core.gesture_detector import GestureDetector
    from ideye.modes.mode_manager import MODE_ORDER, ModeManager
except ImportError:  # pragma: no cover
    from core.hotkey_manager import HOTKEY_ACTIONS
    from core.gesture_detector import GestureDetector
    from modes.mode_manager import MODE_ORDER, ModeManager

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DOCS_DIR = ROOT_DIR / "docs"
GUIDE_PATH = DOCS_DIR / "guia_interactiva.html"

SVG_ICONS: Dict[str, str] = {
    "compass": '<circle cx="12" cy="12" r="9"/><path d="m15.5 8.5-2.2 4.8-4.8 2.2 2.2-4.8 4.8-2.2Z"/>',
    "eye-scan": '<path d="M3 8V5a2 2 0 0 1 2-2h3M16 3h3a2 2 0 0 1 2 2v3M21 16v3a2 2 0 0 1-2 2h-3M8 21H5a2 2 0 0 1-2-2v-3"/><path d="M6 12c2-3 4-4.5 6-4.5s4 1.5 6 4.5c-2 3-4 4.5-6 4.5S8 15 6 12Z"/><circle cx="12" cy="12" r="2.2"/>',
    "grid-3x3": '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 3v18M15 3v18M3 9h18M3 15h18"/>',
    "gamepad": '<path d="M6 7h12c3 0 4 3 3.5 6l-1 4c-.5 2-2 2.5-3.5 1l-2-2H9l-2 2c-1.5 1.5-3 1-3.5-1l-1-4C2 10 3 7 6 7Z"/><path d="M7 11h4M9 9v4M16 10h.1M18 13h.1"/>',
    "sliders": '<path d="M4 6h10M18 6h2M4 12h2M10 12h10M4 18h8M16 18h4"/><circle cx="16" cy="6" r="2"/><circle cx="8" cy="12" r="2"/><circle cx="14" cy="18" r="2"/>',
    "printer": '<path d="M6 8V3h12v5M6 17H4a2 2 0 0 1-2-2v-4a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v4a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="7" rx="1"/><path d="M8 18h8"/>',
    "palette": '<path d="M12 3a9 9 0 1 0 0 18h1.5a1.8 1.8 0 0 0 0-3.6H12a2 2 0 0 1 0-4h4a5 5 0 0 0 0-10h-4Z"/><circle cx="7.5" cy="9" r="1"/><circle cx="9.5" cy="6" r="1"/><circle cx="14" cy="6" r="1"/>',
    "star-badge": '<path d="m12 3 2.7 5.5 6.1.9-4.4 4.3 1 6.1-5.4-2.9-5.4 2.9 1-6.1-4.4-4.3 6.1-.9L12 3Z"/>',
    "shield-lock": '<path d="M12 3 20 6v5c0 5-3.4 8.5-8 10-4.6-1.5-8-5-8-10V6l8-3Z"/><rect x="9" y="11" width="6" height="5" rx="1"/><path d="M10 11V9a2 2 0 0 1 4 0v2"/>',
    "heart-pulse": '<path d="M20.8 5.8a5.5 5.5 0 0 0-7.8 0L12 6.9l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8L12 22l8.8-8.4a5.5 5.5 0 0 0 0-7.8Z"/><path d="M3.5 12h4l1.5-3 3 6 2-4h5.5"/>',
    "sparkles": '<path d="m12 3 1.6 4.4L18 9l-4.4 1.6L12 15l-1.6-4.4L6 9l4.4-1.6L12 3ZM19 14l.8 2.2L22 17l-2.2.8L19 20l-.8-2.2L16 17l2.2-.8L19 14ZM5 14l.6 1.4L7 16l-1.4.6L5 18l-.6-1.4L3 16l1.4-.6L5 14Z"/>',
    "terminal": '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="m7 9 3 3-3 3M13 15h4"/>',
    "wand": '<path d="m4 20 11-11M12 4l1 2M4 12l2 1M18 10l2 1M14 3l1 2M19 18l1 2"/><path d="m14 6 4 4"/>',
    "volume-2": '<polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07M19.07 4.93a10 10 0 0 1 0 14.14"/>',
    "volume-x": '<polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><line x1="22" y1="9" x2="16" y2="15"/><line x1="16" y1="9" x2="22" y2="15"/>',
    "crosshair": '<circle cx="12" cy="12" r="10"/><line x1="22" y1="12" x2="18" y2="12"/><line x1="6" y1="12" x2="2" y2="12"/><line x1="12" y1="6" x2="12" y2="2"/><line x1="12" y1="22" x2="12" y2="18"/>',
    "trophy": '<path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6"/><path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18"/><path d="M4 22h16"/><path d="M10 14.66V17c0 .55-.45 1-1 1H8v4h8v-4h-1c-.55 0-1-.45-1-1v-2.34"/><path d="M6 4h12a2 2 0 0 1 2 2v3a6 6 0 0 1-6 6h0a6 6 0 0 1-6-6V6a2 2 0 0 1 2-2Z"/>',
    "check-circle": '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>',
    "code-bracket": '<polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/>',
    "cpu": '<rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/><path d="M9 1v3M15 1v3M9 20v3M15 20v3M20 9h3M20 14h3M1 9h3M1 14h3"/>',
    "zap": '<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>',
    "play": '<polygon points="5 3 19 12 5 21 5 3"/>',
    "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/>',
    "moon": '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>',
}


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
    "i": ("Agentic Launcher", "Ctrl+Alt+I abre las seis órdenes de ingeniería para VS Code y la cola MCP."),
    "w": ("Scroll ocular", "Ctrl+Alt+W activa o desactiva la rueda de scroll inercial por mirada."),
    "d": ("Dock 30% / 100%", "Ctrl+Alt+D alterna la columna lateral derecha 30% y la cuadrícula completa."),
    "o": ("Tema visual", "Ctrl+Alt+O alterna entre Cyber Glass, OLED Black y Solarized Dark."),
}

PAGES: List[Dict[str, Any]] = [
    {
        "id": "basics",
        "icon": "compass",
        "tab": "Explorando IDEye",
        "title": "¡Bienvenido a IDEye!",
        "kicker": "TU CENTRO DE MANDO OCULAR",
        "ribbon": "#0284c7",
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
                "text": "Mira al centro y a las cuatro esquinas; el mapeo se ancla al centro para que los bordes izquierdo y derecho sigan siendo alcanzables. El sexto paso mide tu MAR con 3 aperturas y cierres reales de boca o aprovecha la linea base adaptativa en reposo.",
                "chip": "Perfil por monitor",
            },
            {
                "icon": "mouth",
                "badge": "03",
                "title": "Abre la boca para confirmar",
                "text": "Una apertura breve equivale a un clic con proteccion anti-Midas adaptativa al reposo. Mantenerla activa el arrastre Jaw-Lock. Nada de dwell-time accidental.",
                "chip": "Clic sin manos",
            },
            {
                "icon": "rest",
                "badge": "04",
                "title": "Descansa la vista",
                "text": "Pausa el HUD con Ctrl+Alt+P o un guiño derecho. Las zonas de reposo evitan el efecto Midas mientras lees.",
                "chip": "Lectura segura",
            },
            {
                "icon": "scroll",
                "badge": "05",
                "title": "Scroll sin manos",
                "text": "En FreeLook, deja la mirada en el borde superior o inferior durante ~0.3 s para desplazar la página. Vuelve al centro para parar.",
                "chip": "Web / documentos",
            },
            {
                "icon": "shield-lock",
                "badge": "06",
                "title": "Eliminación Toque de Midas (Zero-Dwell)",
                "text": "La mirada solo orienta y enfoca el elemento; nunca dispara un clic por tiempo de fijación. La confirmación reside exclusivamente en el canal motor voluntario de la boca (MAR) o ratón.",
                "chip": "Anti-Midas absoluto",
            },
            {
                "icon": "mouth",
                "badge": "07",
                "title": "Línea Base MAR Adaptativa (Anti-Midas)",
                "text": "Mide continuamente la apertura en reposo de tus labios (~0.15). Si hablas o sonríes, el umbral se recalcula dinámicamente (+0.30 sobre reposo) evitando falsos clics sin fatiga.",
                "chip": "Baseline dinámico",
            },
            {
                "icon": "sparkles",
                "badge": "08",
                "title": "Filtro One Euro Adaptativo",
                "text": "Suprime el micro-temblor involuntario en fijaciones sin introducir retraso en sacadas rápidas. Respuesta instantánea bajo 35 ms.",
                "chip": "Suavizado dinámico",
            },
        ],
    },
    {
        "id": "gestures",
        "icon": "eye-scan",
        "tab": "Dominando los Gestos",
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
                "icon": "gamepad",
                "badge": "WASD",
                "title": "Head-Joystick Continuo",
                "text": "Inclina levemente la cabeza fuera de la zona muerta para emitir vectores analógicos de movimiento continuo sin tocar el teclado.",
                "chip": "Cabeza = joystick",
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
            {
                "icon": "brow",
                "badge": "18+",
                "title": "Micro-gestos expresivos",
                "text": "Levanta las cejas para abrir Auto-Fix o la IA. Inclina la cabeza a la derecha para indentar y a la izquierda para des-indentar.",
                "chip": "Cejas + tilt",
            },
        ],
    },
    {
        "id": "modes",
        "icon": "grid-3x3",
        "tab": "Los 6 Modos de Poder",
        "title": "Seis formas de trabajar",
        "kicker": "ELIGE TU PODER",
        "ribbon": "#fbbf24",
        "intro": "Cada modo reconfigura las 9 casillas para el contexto correcto. Prueba el simulador y descubre qué hace cada celda.",
        "cards": [
            {
                "icon": "code",
                "badge": "01",
                "title": "Código",
                "text": "Árboles AST, snippets y operadores con cursor inteligente: al insertar condicionales como if () el cursor se posiciona dentro de los paréntesis para escribir la condición al momento; al seleccionar una sugerencia relacionada con if, el prefijo previo se sustituye automáticamente.",
                "chip": "AST + IA",
            },
            {
                "icon": "writing",
                "badge": "02",
                "title": "Redacción",
                "text": "Teclado T9 con ñ, acentos y mayúsculas, predicción de palabras y asistente de redacción con IA para reformular, corregir ortografía/puntuación o expandir párrafos sin texto predeterminado.",
                "chip": "T9 + Asistencia IA",
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
                "text": "Ratón directo por mirada a 60 Hz con imán superior, umbral de boca adaptado a tu MAR de reposo y carril magnético para la barra de tareas.",
                "chip": "60 Hz",
            },
        ],
    },
    {
        "id": "gaming",
        "icon": "gamepad",
        "tab": "Modo Gaming & Roblox",
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
        "icon": "compass",
        "tab": "Personalización",
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
            {
                "icon": "edit",
                "badge": "FIX",
                "title": "Auto-Fix de Errores",
                "text": "Los diagnósticos de VS Code se convierten en reparaciones de un solo gesto: imports, dos puntos, paréntesis y sugerencias de IA.",
                "chip": "1 clic ocular",
            },
            {
                "icon": "health",
                "badge": "28 s",
                "title": "Health Guard",
                "text": "Avisa si pasas 28 s sin parpadear o si te acercas demasiado al monitor. Cuida ojos y cuello sin interrumpir tu flujo.",
                "chip": "Bienestar",
            },
            {
                "icon": "eye",
                "badge": "CLAHE",
                "title": "Visión Nocturna Adaptativa",
                "text": "Si la luz baja de 85 de luminancia, aplica CLAHE al canal L y una gamma suave. En buena luz no toca ni un píxel.",
                "chip": "Bajo consumo",
            },
            {
                "icon": "shield-lock",
                "badge": "CAP",
                "title": "Modo Gorra y Visera",
                "text": "Activa anclajes subnasales rígidos y compensación de sombras oculares (Eye ROI CLAHE). Permite programar con viseras o sombreros sin perder el iris ni sufrir falsos clics de cejas.",
                "chip": "Anti-sombra",
            },
            {
                "icon": "cursor",
                "badge": "3.5x",
                "title": "Lupa Sniper Zoom",
                "text": "Pulsa Ctrl+Alt+Z para ampliar 3.5x y reducir el cursor al 28% de velocidad. Se cierra con boca o guiño izquierdo; ya no se activa sola al fijar la mirada.",
                "chip": "Precisión subpíxel",
            },
            {
                "icon": "navigation",
                "badge": "AST",
                "title": "Salto Semántico AST",
                "text": "Ctrl+Alt+J extrae clases, métodos y funciones del archivo activo y los reparte en una cuadrícula 3x3 paginada. Un clic salta a la línea exacta.",
                "chip": "3x3 símbolos",
            },
            {
                "icon": "gamepad",
                "badge": "PROFILE",
                "title": "Perfiles de Juego Dinámicos",
                "text": "game_profiles.json adapta el control al género activo: sandbox 3D, twin-stick roguelike o estrategia/RPG con edge-scrolling y puntero táctico.",
                "chip": "Cambios automáticos",
            },
            {
                "icon": "wand",
                "badge": "AI",
                "title": "Agentic Prompt Launcher",
                "text": "Ctrl+Alt+I abre seis órdenes de ingeniería con el código, los símbolos AST y los diagnósticos del bloque activo. El prompt viaja al chat de VS Code o a la cola MCP local.",
                "chip": "VS Code + MCP",
            },
            {
                "icon": "shield-lock",
                "badge": "V1.0",
                "title": "Blindaje de Resiliencia",
                "text": "Landmarks no finitos, cámaras desconectadas, JSON corrupto, portapapeles bloqueado y teclas atascadas se recuperan sin cerrar la app ni perder el control ocular.",
                "chip": "Chaos tested",
            },
            {
                "icon": "scroll",
                "badge": "W",
                "title": "Gaze Scroll Wheel Elástico",
                "text": "Ctrl+Alt+W activa una rueda vertical y horizontal proporcional a la mirada. La zona central de lectura no desplaza y la inercia frena con suavidad al volver.",
                "chip": "Scroll inercial",
            },
            {
                "icon": "health",
                "badge": "ECO",
                "title": "Modo Eco-Sleep de Bajo Consumo",
                "text": "El pipeline baja a 10 FPS durante la pausa y a 2 FPS tras diez segundos sin rostro. Cualquier rostro detectado despierta de inmediato a máxima frecuencia.",
                "chip": "CPU casi cero",
            },
            {
                "icon": "mouse",
                "badge": "GHOST",
                "title": "Ghost-Peek HUD + System Tray",
                "text": "El grid se atenúa al 15% tras 30 segundos de lectura tranquila (configurable en user_settings.json) y reaparece al instante con un gesto o sácada. La bandeja nativa ofrece pausa, modos y calibración.",
                "chip": "HUD discreto",
            },
            {
                "icon": "eye-scan",
                "badge": "WINK",
                "title": "Guinos a prueba de parpadeos",
                "text": "Cada ojo aprende su propia apertura. Un parpadeo bilateral, una cara lejana, una cabeza muy girada o una apertura demasiado breve se descartan. Los guinos válidos duran 180-300 ms, tienen enfriamiento y un segundo guino confirma acciones delicadas.",
                "chip": "Anti-blink adaptativo",
            },
            {
                "icon": "grid-3x3",
                "badge": "PHASE 12",
                "title": "Taxonomía Semántica Profunda",
                "text": "Código se organiza en ocho categorías: condicionales, bucles, funciones, variables, errores, imports, operadores e IA en vivo. Cada categoría abre un 3x3 adaptado a Python, C, Java, JavaScript, SQL, GDScript y Lua.",
                "chip": "8 categorías",
            },
            {
                "icon": "eye-scan",
                "badge": "LIVE",
                "title": "Contexto en Vivo: VS Code y Google Docs",
                "text": "VS Code envía prefijo, línea actual, sufijo, selección, símbolos y diagnósticos. Google Docs, Notion, Overleaf y Word usan un búfer espejo para generar seis sugerencias de escritura coherentes.",
                "chip": "Código + redacción",
            },
            {
                "icon": "terminal",
                "badge": "ENV",
                "title": "Terminal, Navegación y Debug Conscientes",
                "text": "Terminal lee rama, estado Git y tipo de proyecto. Navegación cambia entre IDE y documento web. Debug inspecciona variables locales, breakpoints, pila y pasos con la mirada.",
                "chip": "Entorno real",
            },
            {
                "icon": "grid-3x3",
                "badge": "30%",
                "title": "Dock Lateral Derecho (30%)",
                "text": "Pulsa D o usa Spotlight para alternar el HUD como columna lateral derecha (~460-480px), dejando libre el 70% de la pantalla para el editor sin oclusiones visuales.",
                "chip": "Ergonomia visual",
            },
            {
                "icon": "eye-scan",
                "badge": "1-PUNTO",
                "title": "Snap to Caret (Micro-recalibracion)",
                "text": "Pulsa C o seleccionalo en Spotlight para reajustar al instante el offset de la mirada al cursor de VS Code sin repetir la calibracion de 5 puntos.",
                "chip": "Precision agil",
            },
            {
                "icon": "heart-pulse",
                "badge": "PRE-VUELO",
                "title": "Asistente Pre-Vuelo Ergonomico",
                "text": "La pantalla de calibracion supervisa distancia optima (50-70 cm) y luminosidad con distintivos visuales verdes antes de iniciar el seguimiento.",
                "chip": "Postura y luz",
            },
            {
                "icon": "shield-lock",
                "badge": "ADAPTIVE",
                "title": "Dwell Dinamico y Safe Rest",
                "text": "Fijacion rapida de 300 ms en navegacion, segura de 850 ms en acciones destructivas y desactivada en casilla 5 para descansar sin Toque de Midas.",
                "chip": "Anti-Midas Touch",
            },
            {
                "icon": "wand",
                "badge": "SPOTLIGHT",
                "title": "Gaze Command Palette (Spotlight)",
                "text": "Pulsa P o la casilla 9 para abrir la paleta 3x3 de comandos rapidos: guardar, formatear, terminal, deshacer universal y conmutar layouts.",
                "chip": "Acceso veloz",
            },
            {
                "icon": "palette",
                "badge": "WCAG AAA",
                "title": "Temas OLED Black y Solarized",
                "text": "Pulsa O para alternar entre Cyber Glass, negro puro OLED Black (WCAG AAA) para monitores OLED y Solarized Dark para sesiones prolongadas.",
                "chip": "Alto contraste",
            },
            {
                "icon": "compass",
                "badge": "F2",
                "title": "Mini-Tutorial Guiado de 3 Pasos",
                "text": "Pulsa F2 para repasar interactivamente la fijacion (Dwell), confirmacion por gesto bucal (MAR) y descanso seguro sin Midas Touch.",
                "chip": "Onboarding rapido",
            },
        ],
    },
]

GESTURES: List[Dict[str, str]] = [
    {
        "name": "Apertura de boca (MAR)",
        "action": "Clic / inyectar / navegar",
        "description": "Abre la boca brevemente para activar la casilla enfocada. Proteccion adaptativa al reposo anti-Midas.",
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

LEGAL_NOTICES: List[Dict[str, str]] = [
    {
        "icon": "shield-lock",
        "title": "100% Privado en RAM Local",
        "text": "Webcam y landmarks se procesan en memoria vol\u00e1til; IDEye no graba ni transmite datos biom\u00e9tricos.",
    },
    {
        "icon": "heart-pulse",
        "title": "Uso Ergon\u00f3mico / No M\u00e9dico",
        "text": "Herramienta de productividad, no un dispositivo m\u00e9dico. Haz pausas y det\u00e9n el uso si aparece fatiga mandibular, cervical u ocular.",
    },
    {
        "icon": "gamepad",
        "title": "Aviso Anti-Cheat en Juegos Competitivos",
        "text": "Gaming usa entrada sint\u00e9tica del SO; verifica compatibilidad antes de usarlo en multijugador con anti-cheat kernel.",
    },
]

FALLBACK_SIMULATOR: Dict[str, Dict[str, Any]] = {
    "coding": {
        "name": "Código",
        "cells": [
            {
                "label": "FLUJO",
                "hint": "if / for / while",
                "snippet": "if condition:\n    # Bloque condicional asistido por AST\n    process_stream()\n",
            },
            {
                "label": "FUNC",
                "hint": "def / class",
                "snippet": "def compute_gaze(landmarks: list) -> float:\n    \"\"\"Calcula apertura MAR sin manos.\"\"\"\n    return round(mar_ratio, 3)\n",
            },
            {
                "label": "OPERADORES",
                "hint": "símbolos y comparaciones",
                "snippet": "if mar > 0.45 and ear_score < 0.16:\n    trigger_click()\n",
            },
            {
                "label": "CURSOR",
                "hint": "movimiento y selección",
                "snippet": "# [Caret Jump] -> Línea 42, Columna 8\n",
            },
            {
                "label": "PAUSA",
                "hint": "modo lectura",
                "snippet": "# [HUD PAUSADO] Modo Lectura Activo (0% CPU)\n",
            },
            {
                "label": "KEYWORDS",
                "hint": "return / import / pass",
                "snippet": "import math\nfrom ideye.core import GestureDetector\n",
            },
            {
                "label": "EDIT",
                "hint": "deshacer y borrar",
                "snippet": "# [Deshacer] Última acción revertida con éxito\n",
            },
            {
                "label": "ENTER/TAB",
                "hint": "saltos y sangría",
                "snippet": "\n    # Bloque anidado con sangría de 4 espacios\n",
            },
            {
                "label": "IA",
                "hint": "predicciones de código",
                "snippet": "# [IA Prompt] Optimizar pipeline de visión con vectorización NumPy\n",
            },
        ],
    },
    "writing": {
        "name": "Redacción",
        "cells": [
            {
                "label": "CONECTORES",
                "hint": "además, sin embargo…",
                "snippet": "Por consiguiente, la tecnología de mirada sin dwell elimina la fatiga ocular.\n",
            },
            {
                "label": "FORMATO",
                "hint": "títulos y Markdown",
                "snippet": "## 1. Arquitectura del Sistema\n\nEl pipeline opera a 60 Hz estables.\n",
            },
            {
                "label": "PUNTUACIÓN",
                "hint": "signos y comillas",
                "snippet": "«IDEye: mirada como intención, boca como confirmación.»\n",
            },
            {
                "label": "CURSOR",
                "hint": "mover y seleccionar",
                "snippet": "[Cursor de texto: selección del párrafo anterior]\n",
            },
            {
                "label": "PAUSA",
                "hint": "descanso visual",
                "snippet": "[Pausa de redacción: descanso visual activo]\n",
            },
            {
                "label": "LETRAS",
                "hint": "teclado a-z + ñ",
                "snippet": "Árbol semántico adaptativo con teclado T9 y diccionario español.\n",
            },
            {
                "label": "BORRAR",
                "hint": "deshacer y borrar",
                "snippet": "[Retroceso de carácter: texto corregido]\n",
            },
            {
                "label": "SALTOS",
                "hint": "enter, tab, párrafo",
                "snippet": "\n\n### Nuevo Bloque Temático\n",
            },
            {
                "label": "IA",
                "hint": "sugerencias de redacción",
                "snippet": "[Asistente IA]: Sugerencia de estilo formal y conciso aplicada.\n",
            },
        ],
    },
    "terminal": {
        "name": "Terminal",
        "cells": [
            {
                "label": "GIT",
                "hint": "status / add / commit",
                "snippet": "$ git status\nOn branch main\nYour branch is up to date with 'origin/main'.\n",
            },
            {
                "label": "RAMAS",
                "hint": "checkout / merge",
                "snippet": "$ git checkout -b feat/interactive-dojo\nSwitched to a new branch 'feat/interactive-dojo'\n",
            },
            {
                "label": "ARCHIVOS",
                "hint": "ls / cd / cat",
                "snippet": "$ ls -lh docs/\n-rw-r--r-- 1 user 102K guia_interactiva.html\n",
            },
            {
                "label": "CURSOR",
                "hint": "movimiento de línea",
                "snippet": "$ [Cursor de terminal: inicio de comando]\n",
            },
            {
                "label": "PAUSA",
                "hint": "descanso visual",
                "snippet": "$ [Terminal pausada: modo reposo]\n",
            },
            {
                "label": "COMANDOS",
                "hint": "pip / npm / make",
                "snippet": "$ pytest tests/test_interactive_guide.py -v\n",
            },
            {
                "label": "BORRAR",
                "hint": "limpiar y deshacer",
                "snippet": "$ clear\n",
            },
            {
                "label": "EJECUTAR",
                "hint": "enter y flags",
                "snippet": "$ make run-dev\n[INFO] IDEye L2C Engine iniciado en puerto 8765...\n",
            },
            {
                "label": "AYUDA",
                "hint": "git help y man",
                "snippet": "$ git log --oneline -n 5\n",
            },
        ],
    },
    "sniper": {
        "name": "Gaming",
        "cells": [
            {
                "label": "W",
                "hint": "avanzar",
                "snippet": "[Head-Joystick] WASD: Avanzar (W activo)\n",
            },
            {
                "label": "A",
                "hint": "izquierda",
                "snippet": "[Head-Joystick] WASD: Desplazamiento lateral izquierdo (A activo)\n",
            },
            {
                "label": "S",
                "hint": "retroceder",
                "snippet": "[Head-Joystick] WASD: Retroceder (S activo)\n",
            },
            {
                "label": "D",
                "hint": "derecha",
                "snippet": "[Head-Joystick] WASD: Desplazamiento lateral derecho (D activo)\n",
            },
            {
                "label": "PAUSA",
                "hint": "descanso visual",
                "snippet": "[Gaming] Pausa segura: Todas las teclas sintéticas liberadas\n",
            },
            {
                "label": "SALTO",
                "hint": "guiño izquierdo",
                "snippet": "[Gaming] Guiño izquierdo: Salto / Acción secundaria\n",
            },
            {
                "label": "CLIC",
                "hint": "boca / clic actual",
                "snippet": "[Gaming] Clic mandibular MAR: Disparo / Acción principal sin mover cámara\n",
            },
            {
                "label": "CURSOR",
                "hint": "guiño derecho",
                "snippet": "[Gaming] Guiño derecho: Alternado a Cursor de Menú / HUD táctico\n",
            },
            {
                "label": "360°",
                "hint": "cámara con mirada",
                "snippet": "[Gaming] Mirada directa: Giro de cámara 360° a 60 Hz\n",
            },
        ],
    },
    "data_math": {
        "name": "Datos / Math",
        "cells": [
            {
                "label": "SQL BÁSICO",
                "hint": "SELECT / FROM / WHERE",
                "snippet": "SELECT id, user_name, mar_score, created_at\nFROM eye_tracking_sessions\nWHERE fps >= 60.0 AND zero_dwell = TRUE;\n",
            },
            {
                "label": "SQL AVANZ",
                "hint": "JOIN / GROUP / ORDER",
                "snippet": "SELECT session_id, AVG(mar_ratio) AS avg_mar\nFROM gaze_telemetry\nGROUP BY session_id\nHAVING COUNT(*) > 100\nORDER BY avg_mar DESC;\n",
            },
            {
                "label": "JSON/YAML",
                "hint": "objetos y arrays",
                "snippet": "{\n  \"mode\": \"data_math\",\n  \"calibration\": {\"mar_baseline\": 0.15, \"threshold\": 0.45},\n  \"zero_dwell\": true\n}\n",
            },
            {
                "label": "FÓRMULAS",
                "hint": "LaTeX frac y sum",
                "snippet": "# LaTeX Formula: One Euro Filter Cutoff\n# f_c = f_{min} + \\beta |\\dot{x}|\n# \\hat{x}_t = \\alpha x_t + (1 - \\alpha) \\hat{x}_{t-1}\n",
            },
            {
                "label": "PAUSA",
                "hint": "descanso visual",
                "snippet": "# [Datos / Math en pausa: descanso visual activo]\n",
            },
            {
                "label": "OPERADORES",
                "hint": "+ - * / ^ % ()",
                "snippet": "variance = math.sqrt(sum((x - mean) ** 2 for x in mar_samples) / n)\n",
            },
            {
                "label": "CURSOR",
                "hint": "navegación de celdas",
                "snippet": "# [Navegación SQL: salto a cláusula WHERE]\n",
            },
            {
                "label": "BORRAR",
                "hint": "retroceso y limpiar",
                "snippet": "-- [Query reseteada para nueva consulta]\n",
            },
            {
                "label": "IA SUGIERE",
                "hint": "consultas y LaTeX",
                "snippet": "-- [IA Query Optimizer]: Índice compuesto sugerido en (session_id, mar_ratio)\nEXPLAIN ANALYZE SELECT * FROM gaze_telemetry;\n",
            },
        ],
    },
}

DOJO_CHALLENGES: List[Dict[str, Any]] = [
    {
        "id": "zero-dwell",
        "num": "01",
        "title": "Fijación Zero-Dwell",
        "kicker": "EXPLORACIÓN OCULAR",
        "badge": "FIX",
        "desc": "Mueve el retículo sobre cualquier celda del HUD. Zero-Dwell garantiza que mirar solo enfoca e ilumina, NUNCA hace clic por dwell accidental.",
        "hint": "Pasa el ratón o mirada sobre 2 celdas del simulador",
        "action_label": "Probar Fijación",
    },
    {
        "id": "mar-click",
        "num": "02",
        "title": "Disparo MAR con la Boca",
        "kicker": "CONFIRMACIÓN SIN MANOS",
        "badge": "MAR",
        "desc": "Abre la boca o pulsa la barra espaciadora para superar el umbral MAR (0.45). Observa el Jaw-Meter dinámico y la onda expansiva.",
        "hint": "Pulsa [Espacio] o el botón de disparo MAR",
        "action_label": "Disparar MAR",
    },
    {
        "id": "code-inject",
        "num": "03",
        "title": "Inyección Atómica de Código",
        "kicker": "EDITOR VS CODE SIMULADO",
        "badge": "AST",
        "desc": "Enfoca y haz clic en una celda de Código (FLUJO, FUNC u OPERADORES) para inyectar sintaxis viva estructurada directamente en el editor.",
        "hint": "Haz clic en una celda de código para inyectarla",
        "action_label": "Inyectar Snippet",
    },
    {
        "id": "gaze-scroll",
        "num": "04",
        "title": "Scroll Ocular Inercial",
        "kicker": "DESPLAZAMIENTO ELÁSTICO",
        "badge": "W",
        "desc": "Activa el scroll ocular inercial proporcional a la mirada. La zona central de lectura no se mueve y los márgenes frenan con suavidad.",
        "hint": "Pulsa 'Scroll Ocular' o usa el atajo Ctrl+Alt+W",
        "action_label": "Probar Scroll",
    },
    {
        "id": "sniper-lens",
        "num": "05",
        "title": "Lupa Sniper Precisión x3.5",
        "kicker": "APUNTADO SUBPÍXEL",
        "badge": "3.5x",
        "desc": "Activa el modo Sniper para ampliar 3.5x la región del cursor y desacelerar la mirada al 28% para apuntar a caracteres individuales.",
        "hint": "Pulsa 'Sniper x3.5' o el atajo Ctrl+Alt+Z",
        "action_label": "Activar Sniper",
    },
    {
        "id": "agentic-mcp",
        "num": "06",
        "title": "Agentic Prompt Launcher & MCP",
        "kicker": "INGENIERÍA ASISTIDA & IA",
        "badge": "AI",
        "desc": "Dispara una orden estructurada con contexto AST, código y diagnósticos hacia el chat de IA de VS Code o la cola MCP local.",
        "hint": "Pulsa 'Agentic Launcher' o el atajo Ctrl+Alt+I",
        "action_label": "Lanzar Agentic",
    },
]


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
    simulator = {key: {"name": value["name"], "cells": [dict(c) for c in value["cells"]]} for key, value in FALLBACK_SIMULATOR.items()}
    try:
        manager = ModeManager(initial_mode="coding", auto_switch_enabled=False)
        for mode_id in ("coding", "writing", "terminal", "data_math"):
            mode = manager.modes.get(mode_id)
            if mode is None or not hasattr(mode, "get_root_menu"):
                continue
            root = mode.get_root_menu()
            fallback_cells = FALLBACK_SIMULATOR.get(mode_id, {}).get("cells", [])
            cells = []
            for i, item in enumerate(root.items):
                lbl = str(getattr(item, "label", "—"))
                hnt = str(getattr(item, "hint", "Acción del modo"))
                snp = fallback_cells[i].get("snippet", f"# {lbl}: {hnt}\n") if i < len(fallback_cells) else f"# {lbl}\n"
                cells.append({"label": lbl, "hint": hnt, "snippet": snp})
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
        "legal": LEGAL_NOTICES,
        "gesture_thresholds": _gesture_thresholds(),
        "shortcuts": _display_shortcuts(),
        "modes": _display_modes(),
        "simulator": _simulator(),
        "dojo_challenges": DOJO_CHALLENGES,
        "test_summary": "704 tests, 89 subtests, 16.55s",
    }


def generate_interactive_guide(path: Optional[os.PathLike | str] = None) -> Path:
    """Regenerates the self-contained interactive guide and returns its path."""
    from ideye.core.guide_builder import build_interactive_guide_html

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


__all__ = ["GUIDE_PATH", "LEGAL_NOTICES", "SVG_ICONS", "build_catalog", "generate_interactive_guide"]
