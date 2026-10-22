"""IDEye - Writing / Documentation context mode.

Writing uses complete words, useful phrases and Markdown blocks. It never
exposes a letter-by-letter keyboard or single-letter submenu.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from eyede.actions.menu_trees import (
    MenuAction,
    MenuNode,
    create_pause_action,
)
from eyede.actions.text_predictor import predict_words

try:
    from eyede.modes._helpers import make_root, make_submenu
except ImportError:  # pragma: no cover
    from modes._helpers import make_root, make_submenu

from .base_mode import BaseMode


def _act(
    slot: str,
    aid: str,
    label: str,
    snippet: Optional[str],
    key_name: Optional[str] = None,
    action_type: str = "SNIPPET",
) -> MenuAction:
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
    display_name = "Redacción"
    theme_color = "#10B981"

    def __init__(self, language: str = "PYTHON") -> None:
        super().__init__(language)

    # ------------------------------------------------------------------ #
    # Menu tree
    # ------------------------------------------------------------------ #
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
        tree["WRITING_CONNECTORS"] = make_submenu(
            "WRITING_CONNECTORS", "CONECTORES", connectors
        )

        words = [
            _act("1", "W_WORD_1", "Por favor", "por favor"),
            _act("2", "W_WORD_2", "Muchas gracias", "muchas gracias"),
            _act("3", "W_WORD_3", "Quedo atento", "Quedo atento a tus comentarios."),
            _act("4", "W_WORD_4", "Adjunto documento", "Adjunto el documento para revisión."),
            _act("6", "W_WORD_5", "Estimado equipo", "Estimado equipo:"),
            _act("8", "W_WORD_6", "Saludos cordiales", "Saludos cordiales,"),
            _act("9", "W_WORD_7", "Reunión", "reunión"),
        ]
        tree["WRITING_WORDS"] = make_submenu(
            "WRITING_WORDS", "PALABRAS Y FRASES", words
        )

        markdown = [
            _act("1", "W_MD_1", "Título H1", "# "),
            _act("2", "W_MD_2", "Título H2", "## "),
            _act("3", "W_MD_3", "Negrita", "**|>**"),
            _act("4", "W_MD_4", "Cursiva", "*|>*"),
            _act("6", "W_MD_5", "Lista", "- "),
            _act("8", "W_MD_6", "Código", "```|>|\n```"),
            _act("9", "W_MD_7", "Enlace", "[|>](url)"),
        ]
        tree["WRITING_MARKDOWN"] = make_submenu(
            "WRITING_MARKDOWN", "FORMATO DE TEXTO", markdown
        )

        punctuation = [
            _act("1", "W_PUNCT_1", "Punto", ". "),
            _act("2", "W_PUNCT_2", "Coma", ", "),
            _act("3", "W_PUNCT_3", "Dos puntos", ": "),
            _act("4", "W_PUNCT_4", "Punto y coma", "; "),
            _act("6", "W_PUNCT_5", "Pregunta", "¿|>?"),
            _act("8", "W_PUNCT_6", "Exclamación", "¡|>!"),
            _act("9", "W_PUNCT_7", "Comillas", "(\"|>\")"),
        ]
        tree["WRITING_PUNCTUATION"] = make_submenu(
            "WRITING_PUNCTUATION", "PUNTUACIÓN", punctuation
        )

        cursor = [
            _act("1", "W_CUR_1", "Palabra anterior", None, key_name="LEFT_WORD"),
            _act("2", "W_CUR_2", "Palabra siguiente", None, key_name="RIGHT_WORD"),
            _act("3", "W_CUR_3", "Seleccionar línea", None, key_name="SELECT_LINE"),
            _act("4", "W_CUR_4", "Inicio", None, key_name="HOME"),
            _act("6", "W_CUR_5", "Fin", None, key_name="END"),
            _act("8", "W_CUR_6", "Seleccionar todo", None, key_name="SELECT_ALL"),
            MenuAction(
                "WRITING_CLIPBOARD",
                "9: PORTAPAPELES",
                "Historial de copias",
                "SUBMENU",
                submenu_id="CLIPBOARD_HISTORY",
                icon="edit",
            ),
        ]
        for action in cursor:
            if action.key_name:
                action.action_type = "KEY"
                action.snippet = None
        tree["WRITING_CURSOR"] = make_submenu(
            "WRITING_CURSOR", "CURSOR / SELECCIÓN", cursor
        )
        try:
            from eyede.actions.clipboard_history import get_clipboard_history_manager

            tree["CLIPBOARD_HISTORY"] = (
                get_clipboard_history_manager().get_clipboard_menu_node(
                    parent_id="WRITING_CURSOR"
                )
            )
        except Exception:
            pass

        delete = [
            _act("1", "W_DEL_1", "Borrar palabra", None, key_name="DELETE_WORD"),
            _act("2", "W_DEL_2", "Borrar carácter", None, key_name="BACKSPACE"),
            _act("3", "W_DEL_3", "Deshacer", None, key_name="UNDO"),
            _act("4", "W_DEL_4", "Rehacer", None, key_name="REDO"),
            _act("6", "W_DEL_5", "Borrar línea", None, key_name="DELETE_LINE"),
            _act("8", "W_DEL_6", "Limpiar", None, key_name="CLEAR_LINE"),
            _act("9", "W_DEL_7", "Volver", None, action_type="BACK"),
        ]
        for action in delete:
            if action.key_name:
                action.action_type = "KEY"
                action.snippet = None
        tree["WRITING_DELETE"] = make_submenu(
            "WRITING_DELETE", "BORRAR / DESHACER", delete
        )

        jump = [
            _act("1", "W_JMP_1", "Enter", None, key_name="ENTER"),
            _act("2", "W_JMP_2", "Doble Enter", None, key_name="DOUBLE_ENTER"),
            _act("3", "W_JMP_3", "Tab", None, key_name="TAB"),
            _act("4", "W_JMP_4", "Espacio", None, key_name="SPACE"),
            _act("6", "W_JMP_5", "Arriba", None, key_name="UP"),
            _act("8", "W_JMP_6", "Abajo", None, key_name="DOWN"),
            _act("9", "W_JMP_7", "Inicio párrafo", None, key_name="PARA_START"),
        ]
        for action in jump:
            if action.key_name:
                action.action_type = "KEY"
                action.snippet = None
        tree["WRITING_JUMP"] = make_submenu(
            "WRITING_JUMP", "SALTO / PÁRRAFO", jump
        )

        ai = [
            _act("1", "W_AI_1", "Continuar frase", "continuar la frase actual"),
            _act("2", "W_AI_2", "Cerrar párrafo", "cerrar el párrafo actual"),
            _act("3", "W_AI_3", "Reformular", "reformular de forma más clara"),
            _act("4", "W_AI_4", "Resumir", "resumir el texto anterior"),
            _act("6", "W_AI_5", "Expandir", "expandir con más detalle"),
            _act("8", "W_AI_6", "Corregir", "corregir ortografía y gramática"),
            _act("9", "W_AI_7", "Traducir EN", "traducir al inglés"),
        ]
        tree["WRITING_AI"] = make_submenu(
            "WRITING_AI", "SUGERENCIAS DE REDACCIÓN", ai
        )

        root_items = [
            MenuAction(
                "WRITING_CONNECTORS",
                "1: CONECTORES",
                "Conectores y transiciones",
                "SUBMENU",
                submenu_id="WRITING_CONNECTORS",
                icon="flow",
            ),
            MenuAction(
                "WRITING_WORDS",
                "2: Palabras y frases",
                "Vocabulario y frases completas",
                "SUBMENU",
                submenu_id="WRITING_WORDS",
                icon="format",
            ),
            MenuAction(
                "WRITING_MARKDOWN",
                "3: Formato de texto",
                "Títulos, listas y negritas",
                "SUBMENU",
                submenu_id="WRITING_MARKDOWN",
                icon="format",
            ),
            MenuAction(
                "WRITING_PUNCTUATION",
                "4: Puntuación",
                "Signos de puntuación",
                "SUBMENU",
                submenu_id="WRITING_PUNCTUATION",
                icon="operators",
            ),
            create_pause_action("5"),
            MenuAction(
                "WRITING_CURSOR",
                "6: Cursor / selección",
                "Movimiento y selección",
                "SUBMENU",
                submenu_id="WRITING_CURSOR",
                icon="navigation",
            ),
            MenuAction(
                "WRITING_DELETE",
                "7: Borrar y deshacer",
                "Borrado y deshacer",
                "SUBMENU",
                submenu_id="WRITING_DELETE",
                icon="edit",
            ),
            MenuAction(
                "WRITING_JUMP",
                "8: Saltos y párrafos",
                "Saltos y párrafos",
                "SUBMENU",
                submenu_id="WRITING_JUMP",
                icon="navigation",
            ),
            MenuAction(
                "WRITING_AI",
                "9: Sugerencias",
                "Ideas para seguir escribiendo",
                "SUBMENU",
                submenu_id="WRITING_AI",
                icon="ai_spark",
            ),
        ]
        tree["ROOT"] = make_root("REDACCIÓN / DOCS", root_items)
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
        return predict_words("", limit=6)


WritingModeAlias = WritingMode
DocMode = WritingMode
WRITING_MODE = WritingMode
Writing = WritingMode
