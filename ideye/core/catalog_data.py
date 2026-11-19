"""Icons, shortcut labels, gestures and legal notices for the guide."""

from __future__ import annotations

from typing import Any, Dict, List


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
