"""Static action catalog for the agentic prompt launcher."""

from __future__ import annotations

from typing import Dict, Sequence


AGENTIC_ACTIONS: Dict[str, Dict[str, str]] = {
    "refactor_clean": {
        "label": "REFACTOR",
        "title": "Refactor limpio",
        "instruction": (
            "Refactoriza la función o selección actual aplicando principios SOLID, "
            "tipado estricto y eliminación de código duplicado sin alterar su "
            "contrato público."
        ),
        "contract": (
            "Devuelve el código completo de la función refactorizada, una lista "
            "breve de cambios estructurales y cualquier riesgo de compatibilidad."
        ),
        "icon": "wand",
        "hint": "SOLID, tipado y sin duplicación",
    },
    "generate_pytest": {
        "label": "GEN PYTEST",
        "title": "Generar tests pytest",
        "instruction": (
            "Genera tests unitarios deterministas con pytest para la función activa. "
            "Cubre el camino feliz, valores nulos, bordes, excepciones y errores de "
            "entrada sin depender de red, tiempo real ni estado global."
        ),
        "contract": (
            "Devuelve un archivo de test ejecutable con imports completos, fixtures "
            "mínimas y aserciones explícitas para cada caso."
        ),
        "icon": "test-tube",
        "hint": "Camino feliz, nulos y bordes",
    },
    "fix_and_harden": {
        "label": "FIX & HARDEN",
        "title": "Corregir y blindar",
        "instruction": (
            "Corrige todos los diagnósticos activos del bloque actual y blinda el "
            "código frente a condiciones de carrera, divisiones por cero, fugas de "
            "recursos y entradas inválidas."
        ),
        "contract": (
            "Devuelve el parche completo, explica cada diagnóstico resuelto y añade "
            "las guardas o context managers necesarios."
        ),
        "icon": "shield-lock",
        "hint": "Diagnósticos y robustez",
    },
    "optimize_complexity": {
        "label": "OPTIMIZE O(N)",
        "title": "Optimizar complejidad",
        "instruction": (
            "Analiza la complejidad algorítmica y de memoria de la función actual y "
            "reescríbela optimizando los cuellos de botella sin cambiar su contrato."
        ),
        "contract": (
            "Incluye la complejidad antes y después, el código optimizado y una nota "
            "sobre los compromisos de legibilidad o memoria."
        ),
        "icon": "gauge",
        "hint": "Tiempo, memoria y cuellos de botella",
    },
    "write_docstring": {
        "label": "DOCSTRING",
        "title": "Escribir docstring",
        "instruction": (
            "Genera e inyecta el docstring técnico completo de la función activa con "
            "argumentos, tipo de retorno, excepciones y complejidad, siguiendo el "
            "estilo del proyecto."
        ),
        "contract": (
            "Devuelve la función completa con el docstring insertado y sin modificar "
            "la lógica ejecutable."
        ),
        "icon": "file-text",
        "hint": "Args, retorno, excepciones y O(N)",
    },
    "explain_architecture": {
        "label": "EXPLAIN",
        "title": "Explicar arquitectura",
        "instruction": (
            "Explica el flujo de datos y las dependencias de este bloque dentro de la "
            "arquitectura general del módulo, señalando acoplamientos y riesgos."
        ),
        "contract": (
            "Devuelve una explicación breve con entradas, salidas, dependencias, "
            "efectos secundarios y puntos de extensión."
        ),
        "icon": "network",
        "hint": "Flujo, dependencias y riesgos",
    },
}

ACTION_SLOTS: Sequence[str] = (
    "refactor_clean",
    "generate_pytest",
    "fix_and_harden",
    "optimize_complexity",
    "write_docstring",
    "explain_architecture",
)
SLOT_INDEXES = (0, 1, 2, 3, 5, 7)

_KEY_LABELS = ("1", "2", "3", "4", "6", "8")
