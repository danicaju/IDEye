"""Fallback simulator menus and dojo challenges for the guide."""

from __future__ import annotations

from typing import Any, Dict, List


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
        "kicker": "Exploración ocular",
        "badge": "FIX",
        "desc": "Mueve el retículo sobre cualquier celda del HUD. Zero-Dwell garantiza que mirar solo enfoca e ilumina, NUNCA hace clic por dwell accidental.",
        "hint": "Pasa el ratón o mirada sobre 2 celdas del simulador",
        "action_label": "Probar Fijación",
    },
    {
        "id": "mar-click",
        "num": "02",
        "title": "Disparo MAR con la Boca",
        "kicker": "Confirmación sin manos",
        "badge": "MAR",
        "desc": "Abre la boca o pulsa la barra espaciadora para superar el umbral MAR (0.45). Observa el Jaw-Meter dinámico y la onda expansiva.",
        "hint": "Pulsa [Espacio] o el botón de disparo MAR",
        "action_label": "Disparar MAR",
    },
    {
        "id": "code-inject",
        "num": "03",
        "title": "Inyección Atómica de Código",
        "kicker": "Editor de VS Code simulado",
        "badge": "AST",
        "desc": "Enfoca y haz clic en una celda de Código (FLUJO, FUNC u OPERADORES) para inyectar sintaxis viva estructurada directamente en el editor.",
        "hint": "Haz clic en una celda de código para inyectarla",
        "action_label": "Inyectar Snippet",
    },
    {
        "id": "gaze-scroll",
        "num": "04",
        "title": "Scroll Ocular Inercial",
        "kicker": "Desplazamiento elástico",
        "badge": "W",
        "desc": "Activa el scroll ocular inercial proporcional a la mirada. La zona central de lectura no se mueve y los márgenes frenan con suavidad.",
        "hint": "Pulsa 'Scroll Ocular' o usa el atajo Ctrl+Alt+W",
        "action_label": "Probar Scroll",
    },
    {
        "id": "sniper-lens",
        "num": "05",
        "title": "Lupa Sniper Precisión x3.5",
        "kicker": "Apuntado subpíxel",
        "badge": "3.5x",
        "desc": "Activa el modo Sniper para ampliar 3.5x la región del cursor y desacelerar la mirada al 28% para apuntar a caracteres individuales.",
        "hint": "Pulsa 'Sniper x3.5' o el atajo Ctrl+Alt+Z",
        "action_label": "Activar Sniper",
    },
    {
        "id": "agentic-mcp",
        "num": "06",
        "title": "Agentic Prompt Launcher & MCP",
        "kicker": "Ingeniería asistida por IA",
        "badge": "AI",
        "desc": "Dispara una orden estructurada con contexto AST, código y diagnósticos hacia el chat de IA de VS Code o la cola MCP local.",
        "hint": "Pulsa 'Agentic Launcher' o el atajo Ctrl+Alt+I",
        "action_label": "Lanzar Agentic",
    },
]
