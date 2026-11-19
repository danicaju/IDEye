"""Heuristic (offline) code and document suggestion engine."""

import json
import re
from typing import List, Optional, Any

try:
    import ideye.config as config
except ImportError:
    import config


def generate_document_predictions(context_text: str, title: str = "") -> List[str]:
    """Six coherent writing suggestions for Google Docs, Notion or Overleaf."""
    text = str(context_text or "").strip()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    last = lines[-1] if lines else ""
    subject = "el documento" if not title else f"'{title[:40]}'"
    if last.endswith(("?", "¿")):
        first = "Responder a la pregunta planteada con una tesis clara"
    elif last.endswith((".", "!", ":")):
        first = "Continuar la idea con una frase de desarrollo"
    elif last:
        first = "Completar la frase actual de forma coherente"
    else:
        first = f"Introducir {subject} con una tesis breve"
    suggestions = [
        first,
        "Desarrollar el párrafo con un argumento técnico y un ejemplo",
        "Sintetizar la idea en una lista de puntos clave",
        "Redactar una conclusión o transición hacia la siguiente sección",
        "Insertar un conector formal para enlazar el argumento anterior",
        "Resumir o reformatear la selección actual",
    ]
    while len(suggestions) < 6:
        suggestions.append("Añadir una frase de cierre")
    return suggestions[:6]


def generate_heuristic_predictions(
    context_text: str,
    local_symbols: Optional[List[str]] = None,
) -> List[str]:
    """
    Local heuristic fallback engine.
    Analyzes the last line and structure of recent code context and injects
    smart, context-relevant suggestions using actual local symbols.
    Guarantees returning EXACTLY 6 distinct, ready-to-use code suggestions.
    """
    distinct_syms: List[str] = []
    pool = [s for s in (local_symbols or []) if s and isinstance(s, str) and s.isidentifier()] + [
        "data", "result", "item", "i", "val", "x", "count", "res", "obj"
    ]
    for s in pool:
        if s not in distinct_syms:
            distinct_syms.append(s)
    v1, v2, v3, v4 = distinct_syms[0], distinct_syms[1], distinct_syms[2], distinct_syms[3]

    # Find the last non-empty line
    lines = [line.rstrip() for line in (context_text or "").splitlines() if line.strip()]
    last_line = lines[-1].strip() if lines else ""

    suggestions: List[str] = []

    # Heuristic 1: Function / Method definition
    if last_line.startswith("def "):
        suggestions = [
            f'"""Docstring explicativo."""',
            f"{v2} = None",
            f"if {v1}:",
            f"for {v3} in {v1}:",
            f"return {v2}",
            "pass",
        ]

    # Heuristic 2: Class definition
    elif last_line.startswith("class "):
        suggestions = [
            f"def __init__(self, {v1}):\n    self.{v1} = {v1}",
            f"def process(self):\n    return self.{v1}",
            f"def get_{v1}(self):\n    return self.{v1}",
            f"def __repr__(self):\n    return f'{v1}={{self.{v1}}}'",
            "pass",
            '"""Clase principal."""',
        ]

    # Heuristic 3: If / Elif statement
    elif last_line.startswith("if ") or last_line.startswith("elif ") or last_line.startswith("if(") or last_line.startswith("elif("):
        clean_header = last_line.rstrip()
        # Case A: Inside parentheses or incomplete condition (e.g. `if ()`, `if (`, `if `)
        if clean_header.endswith("()") or clean_header.endswith("(") or not (clean_header.endswith(":") or clean_header.endswith("{")):
            cond_var = v1
            cond_target = v2 if v2 != v1 else "None"
            suggestions = [
                f"if {cond_var} is not None:",
                f"if len({cond_var}) > 0:",
                f"if not {cond_var}:",
                f"if {cond_var} == {cond_target}:",
                f"if {cond_var} > 0:",
                f"if {v3} in {cond_var}:",
            ]
        else:
            # Case B: Header completed (ends with : or {), suggest block body
            suggestions = [
                f"return {v1}",
                f"{v2} = {v1}",
                f"print(f'{v1}: {{{v1}}}')",
                f"raise ValueError('Error con {v1}')",
                "return True",
                "pass",
            ]

    # Heuristic 4: For loop header
    elif last_line.startswith("for "):
        loop_match = re.search(r"for\s+([A-Za-z_]\w*)\s+in\s+([A-Za-z_]\w*)", last_line)
        loop_var = loop_match.group(1) if loop_match else v3
        iterable = loop_match.group(2) if loop_match else v1
        suggestions = [
            f"print({loop_var})",
            f"if {loop_var}:",
            f"{v2}.append({loop_var})",
            f"total += {loop_var}",
            f"{loop_var} = process({loop_var})",
            f"if not {iterable}: break",
        ]

    # Heuristic 5: While loop header
    elif last_line.startswith("while "):
        suggestions = [
            f"if not {v1}: break",
            f"{v4} += 1",
            f"print({v1})",
            f"{v2} = process({v1})",
            "break",
            "time.sleep(0.1)",
        ]

    # Heuristic 6: Try block
    elif last_line.startswith("try:"):
        suggestions = [
            f"{v2} = process({v1})",
            f"{v1}.load()",
            f"{v2} = {v1}.read()",
            f"connect_service({v1})",
            "pass",
            f"validate({v1})",
        ]

    # Heuristic 7: Except block
    elif last_line.startswith("except"):
        suggestions = [
            "print(f'Error: {e}')",
            "logger.error(str(e))",
            "return None",
            f"{v2} = None",
            "raise",
            "pass",
        ]

    # Heuristic 8: With context manager
    elif last_line.startswith("with "):
        suggestions = [
            "content = f.read()",
            "data = json.load(f)",
            f"f.write({v1})",
            "for line in f:",
            f"{v2} = f.readlines()",
            "pass",
        ]

    # Heuristic 9: Incomplete assignment (e.g. `x = ` or `total += `)
    elif re.search(r'[\+\-\*/]?=\s*$', last_line):
        suggestions = [
            f"{v1}",
            f"len({v1})",
            f"[{v3} for {v3} in {v1}]",
            f"{v1}.copy()",
            "[]",
            "{}",
        ]

    # Heuristic 10: Dot access (e.g. `data.` or `self.`)
    elif last_line.endswith("."):
        suggestions = [
            "append()",
            "get()",
            "items()",
            "split()",
            "strip()",
            "copy()",
        ]

    # Heuristic 11: Return statement
    elif last_line.startswith("return"):
        suggestions = [
            f"{v2}",
            f"{v1}",
            "True",
            "False",
            "None",
            "0",
        ]

    # General Fallback: Smart statements using actual local symbols
    if len(suggestions) < 6:
        # Avoid self-loops and self-assignments (e.g. for item in item, result = result)
        loop_target = v1 if v3 != v1 else (v2 if v2 != v3 else "items")
        assign_source = v1 if v2 != v1 else (v3 if v3 != v2 else "val")
        defaults = [
            f"if {v1}:",
            f"for {v3} in {loop_target}:",
            f"{v2} = {assign_source}",
            f"return {v1}",
            f"print({v1})",
            f"self.{v1} = {v1}",
        ]
        for d in defaults:
            if d not in suggestions:
                suggestions.append(d)
            if len(suggestions) == 6:
                break

    # Guaranteed length 6
    while len(suggestions) < 6:
        suggestions.append("pass")

    return suggestions[:6]
