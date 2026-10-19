"""
IDEye - Writing / Documentation Context Mode (Phase 6)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from eyede.actions.menu_trees import MenuAction, MenuNode

try:
    from eyede.modes._helpers import make_root, make_submenu
except ImportError:  # pragma: no cover
    from modes._helpers import make_root, make_submenu

from .base_mode import BaseMode


def _act(slot: str, aid: str, label: str, snippet: str, key_name: Optional[str] = None, action_type: str = "SNIPPET") -> MenuAction:
    return MenuAction(
        id=aid,
        label=f"{slot}: {label}",
        hint=label,
        action_type=action_type,
        snippet=snippet,
        key_name=key_name,
        icon="",
    )


class WritingMode(BaseMode):
    mode_id = "writing"
    display_name = "REDACCIÓN / DOCS"
    theme_color = "#10B981"

    def get_menu_tree(self, language: Optional[str] = None) -> Dict[str, MenuNode]:
        tree: Dict[str, MenuNode] = {}

        connectors = [
            _act("1", "W_CONN_1", "Además", "Además, "),
            _act("2", "W_CONN_2", "Sin embargo", "Sin embargo, "),
            _act("3", "W_CONN_3", "Por lo tanto", "Por lo tanto, "),
            _act("4", "W_CONN_4", "En conclusión", "En conclusión, "),
            _act("6", "W_CONN_5", "Por ejemplo", "Por ejemplo, "),
            _act("8", "W_CONN_6", "Es decir", "Es decir, "),
            _act("9", "W_CONN_7", "No obstante", "No obstante, "),
        ]
        tree["WRITING_CONNECTORS"] = make_submenu("WRITING_CONNECTORS", "CONECTORES", connectors)

        markdown = [
            _act("1", "W_MD_1", "H1", "# "),
            _act("2", "W_MD_2", "H2", "## "),
            _act("3", "W_MD_3", "Negrita", "**|>**"),
            _act("4", "W_MD_4", "Cursiva", "*|>*"),
            _act("6", "W_MD_5", "Checkbox", "- [ ] "),
            _act("8", "W_MD_6", "Código", "```|>|\n```"),
            _act("9", "W_MD_7", "Enlace", "[|>](url)"),
        ]
        tree["WRITING_MARKDOWN"] = make_submenu("WRITING_MARKDOWN", "MARKDOWN / DOCS", markdown)

        punctuation = [
            _act("1", "W_PUNCT_1", "Punto", ". "),
            _act("2", "W_PUNCT_2", "Coma", ", "),
            _act("3", "W_PUNCT_3", "Dos puntos", ": "),
            _act("4", "W_PUNCT_4", "Punto y coma", "; "),
            _act("6", "W_PUNCT_5", "Pregunta", "¿|>?"),
            _act("8", "W_PUNCT_6", "Exclamación", "¡|>!"),
            _act("9", "W_PUNCT_7", "Comillas", "(\"|>\")"),
        ]
        tree["WRITING_PUNCTUATION"] = make_submenu("WRITING_PUNCTUATION", "PUNTUACIÓN", punctuation)

        cursor = [
            _act("1", "W_CUR_1", "Palabra ant.", None, key_name="LEFT_WORD"),
            _act("2", "W_CUR_2", "Palabra sig.", None, key_name="RIGHT_WORD"),
            _act("3", "W_CUR_3", "Sel. línea", None, key_name="SELECT_LINE"),
            _act("4", "W_CUR_4", "Inicio", None, key_name="HOME"),
            _act("6", "W_CUR_5", "Fin", None, key_name="END"),
            _act("8", "W_CUR_6", "Sel. todo", None, key_name="SELECT_ALL"),
            _act("9", "W_CUR_7", "Buscar", None, key_name="FIND"),
        ]
        for a in cursor:
            if a.key_name:
                a.action_type = "KEY"
                a.snippet = None
        tree["WRITING_CURSOR"] = make_submenu("WRITING_CURSOR", "CURSOR / SELECCIÓN", cursor)

        t9 = [
            _act("1", "W_T9_1", "el/la", "el "),
            _act("2", "W_T9_2", "de", "de "),
            _act("3", "W_T9_3", "que", "que "),
            _act("4", "W_T9_4", "y", "y "),
            _act("6", "W_T9_5", "en", "en "),
            _act("8", "W_T9_6", "a", "a "),
            _act("9", "W_T9_7", "es", "es "),
        ]
        tree["WRITING_T9"] = make_submenu("WRITING_T9", "TECLADO T9 / PALABRAS", t9)

        delete = [
            _act("1", "W_DEL_1", "Borrar palabra", None, key_name="DELETE_WORD"),
            _act("2", "W_DEL_2", "Borrar char", None, key_name="BACKSPACE"),
            _act("3", "W_DEL_3", "Deshacer", None, key_name="UNDO"),
            _act("4", "W_DEL_4", "Rehacer", None, key_name="REDO"),
            _act("6", "W_DEL_5", "Borrar línea", None, key_name="DELETE_LINE"),
            _act("8", "W_DEL_6", "Limpiar", None, key_name="CLEAR_LINE"),
            _act("9", "W_DEL_7", "Volver", None, action_type="BACK"),
        ]
        for a in delete:
            if a.key_name:
                a.action_type = "KEY"
                a.snippet = None
        # Ensure slot 6 (index 6) remains BACK handled by make_submenu? We put back at slot 7? make_submenu expects 7 content; back auto at index6. Our list has 7; content[4] at index5 etc, content[6] at index8. Fine. But last action "Volver" is not needed; back auto. okay.
        tree["WRITING_DELETE"] = make_submenu("WRITING_DELETE", "BORRAR / DESHACER", delete)

        jump = [
            _act("1", "W_JMP_1", "Enter", None, key_name="ENTER"),
            _act("2", "W_JMP_2", "Doble Enter", None, key_name="DOUBLE_ENTER"),
            _act("3", "W_JMP_3", "Tab", None, key_name="TAB"),
            _act("4", "W_JMP_4", "Espacio", None, key_name="SPACE"),
            _act("6", "W_JMP_5", "Arriba", None, key_name="UP"),
            _act("8", "W_JMP_6", "Abajo", None, key_name="DOWN"),
            _act("9", "W_JMP_7", "Inicio párrafo", None, key_name="PARA_START"),
        ]
        for a in jump:
            if a.key_name:
                a.action_type = "KEY"
                a.snippet = None
        tree["WRITING_JUMP"] = make_submenu("WRITING_JUMP", "SALTO / PÁRRAFO", jump)

        ai = [
            _act("1", "W_AI_1", "Continuar frase", "continuar la frase actual"),
            _act("2", "W_AI_2", "Cerrar párrafo", "cerrar el párrafo actual"),
            _act("3", "W_AI_3", "Reformular", "reformular de forma más clara"),
            _act("4", "W_AI_4", "Resumir", "resumir el texto anterior"),
            _act("6", "W_AI_5", "Expandir", "expandir con más detalle"),
            _act("8", "W_AI_6", "Corregir", "corregir ortografía y gramática"),
            _act("9", "W_AI_7", "Traducir EN", "traducir al inglés"),
        ]
        tree["WRITING_AI"] = make_submenu("WRITING_AI", "IA REDACCIÓN", ai)

        root_items = [
            MenuAction("WRITING_CONNECTORS", "1: CONECTORES", "Conectores y transiciones", "SUBMENU", submenu_id="WRITING_CONNECTORS", icon="flow"),
            MenuAction("WRITING_MARKDOWN", "2: MARKDOWN / DOCS", "Formato Markdown y documentación", "SUBMENU", submenu_id="WRITING_MARKDOWN", icon="format"),
            MenuAction("WRITING_PUNCTUATION", "3: PUNTUACIÓN", "Signos de puntuación", "SUBMENU", submenu_id="WRITING_PUNCTUATION", icon="operators"),
            MenuAction("WRITING_CURSOR", "4: CURSOR / SELECCIÓN", "Movimiento y selección", "SUBMENU", submenu_id="WRITING_CURSOR", icon="navigation"),
            None,  # pause placeholder
            MenuAction("WRITING_T9", "6: TECLADO T9", "Palabras frecuentes", "SUBMENU", submenu_id="WRITING_T9", icon="variables"),
            MenuAction("WRITING_DELETE", "7: BORRAR / DESHACER", "Borrado y deshacer", "SUBMENU", submenu_id="WRITING_DELETE", icon="edit"),
            MenuAction("WRITING_JUMP", "8: SALTO / PÁRRAFO", "Saltos y párrafos", "SUBMENU", submenu_id="WRITING_JUMP", icon="navigation"),
            MenuAction("WRITING_AI", "9: IA REDACCIÓN", "Predicción de prosa", "SUBMENU", submenu_id="WRITING_AI", icon="ai_spark"),
        ]
        # fix labels numbering via make_root? make_root forces pause at index4 but keeps labels as provided. Need labels correspond. Our list indices: 0 label 1 ok; 1 label2; 2 label3; 3 label4; 4 pause; 5 label6; 6 label7; 7 label8; 8 label9. Good.
        from eyede.actions.menu_trees import create_pause_action
        root_items[4] = create_pause_action("5")
        root = make_root("REDACCIÓN / DOCS", root_items)
        tree["ROOT"] = root
        return tree

    def get_root_menu(self, language: Optional[str] = None) -> MenuNode:
        return self.get_menu_tree(language)["ROOT"]

    def get_ai_system_prompt(self, context_data: Optional[Dict[str, Any]] = None) -> str:
        return (
            "You are a writing assistant for a disabled programmer using eye-tracking. "
            "Continue the current sentence naturally, improve clarity, and suggest connectors, "
            "Markdown, punctuation, and paragraph transitions. Return ONLY a JSON array of exactly 6 strings."
        )

    def get_heuristic_predictions(
        self, context_data: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        return [
            "Además, ",
            "Sin embargo, ",
            "Por lo tanto, ",
            "En conclusión, ",
            "Por ejemplo, ",
            "Es decir, ",
        ]


WritingModeAlias = WritingMode
DocMode = WritingMode
WRITING_MODE = WritingMode
Writing = WritingMode
