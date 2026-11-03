"""
IDEye - Writing / Documentation Context Mode (Phase 6)
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from ideye.actions.menu_trees import (
    MenuAction,
    MenuNode,
    create_back_action,
    create_pause_action,
)
from ideye.actions.text_predictor import predict_words

try:
    from ideye.modes._helpers import make_root, make_submenu
except ImportError:  # pragma: no cover
    from modes._helpers import make_root, make_submenu

from .base_mode import BaseMode


WRITING_AI_PROMPTS = {
    "continue": "Continúa de forma natural, fluida y coherente la siguiente frase o texto:\n\n{text}",
    "close_paragraph": "Añade una frase de cierre concisa y adecuada para concluir el párrafo actual:\n\n{text}",
    "rephrase": "Reformula el siguiente texto para que sea más claro, fluido, conciso y profesional, manteniendo su significado original:\n\n{text}",
    "summarize": "Sintetiza el siguiente texto en una o dos frases claras con los puntos esenciales:\n\n{text}",
    "expand": "Desarrolla y expande el siguiente texto con más detalle, argumentos y claridad explicativa:\n\n{text}",
    "correct": "Corrige la ortografía, puntuación, acentuación y gramática del siguiente texto sin alterar su sentido ni estilo:\n\n{text}",
    "translate_en": "Traduce el siguiente texto al inglés de manera natural, idiomática y profesional:\n\n{text}",
}


def correct_writing_text(text: str) -> str:
    """Corrects common punctuation, spacing, and capitalization flaws in Spanish/English text."""
    if not text:
        return ""
    res = text
    # Fix duplicate adjacent words (e.g. "de de" -> "de", "la la" -> "la")
    res = re.sub(r'\b([A-Za-zñáéíóúÁÉÍÓÚ]+)\s+\1\b', r'\1', res, flags=re.IGNORECASE)
    # Common Spanish accent fixes
    accent_map = {
        r'\btambien\b': 'también',
        r'\bdespues\b': 'después',
        r'\bademas\b': 'además',
        r'\bfacil\b': 'fácil',
        r'\bdificil\b': 'difícil',
        r'\bestaria\b': 'estaría',
        r'\bhabria\b': 'habría',
        r'\bseria\b': 'sería',
    }
    for pat, rep in accent_map.items():
        res = re.sub(pat, rep, res, flags=re.IGNORECASE)
    # Fix spaces before punctuation
    res = re.sub(r'\s+([,.:;?!])', r'\1', res)
    # Ensure a single space after punctuation if followed by a word character
    res = re.sub(r'([,.:;?!])([^\s0-9])', r'\1 \2', res)
    lines = res.splitlines()
    corrected_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            corrected_lines.append(line)
            continue
        first_char = stripped[0]
        if first_char.isalpha():
            stripped = first_char.upper() + stripped[1:]
        elif len(stripped) > 1 and stripped[0] in {"¿", "¡", '"', "'"} and stripped[1].isalpha():
            stripped = stripped[0] + stripped[1].upper() + stripped[2:]

        if stripped.endswith("?") and "¿" not in stripped:
            stripped = "¿" + stripped
        elif stripped.endswith("!") and "¡" not in stripped:
            stripped = "¡" + stripped

        corrected_lines.append(stripped)
    return "\n".join(corrected_lines)


def rephrase_writing_text(text: str, style: str = "clear") -> str:
    """Rephrases conversational or informal Spanish text into clear, professional prose."""
    if not text:
        return ""
    cleaned = text.strip()
    # Spanish conversational cleanup
    replacements = [
        (r'\bqueria saber si\b', 'quisiera consultar si'),
        (r'\ba ver si podemos\b', 'para confirmar si es posible'),
        (r'\bte escribo para decirte que\b', 'te escribo para informarte de que'),
        (r'\bo sea\b', 'es decir'),
        (r'\bmas o menos\b', 'aproximadamente'),
        (r'\bporfa\b', 'por favor'),
    ]
    for pat, rep in replacements:
        cleaned = re.sub(pat, rep, cleaned, flags=re.IGNORECASE)
    return correct_writing_text(cleaned)


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
    display_name = "Redacción"
    theme_color = "#10B981"

    def __init__(self, language: str = "PYTHON") -> None:
        super().__init__(language)
        self._prefix: str = ""
        self._uppercase: bool = False

    # ------------------------------------------------------------------ #
    # T9 state
    # ------------------------------------------------------------------ #
    def reset_prefix(self) -> None:
        self._prefix = ""

    def record_letter(self, char: str) -> str:
        """Records a T9 letter and returns the text to insert."""
        if not char:
            return ""
        self._prefix += char.lower()
        return char.upper() if self._uppercase else char

    def record_space(self) -> None:
        self._prefix = ""

    def record_backspace(self) -> None:
        self._prefix = self._prefix[:-1]

    def toggle_uppercase(self) -> bool:
        self._uppercase = not self._uppercase
        return self._uppercase

    def apply_case_to_word(self, word: str) -> str:
        return word.upper() if self._uppercase else word

    def predictions(self) -> List[str]:
        return predict_words(self._prefix, limit=6)

    def _letter_action(self, slot: int, char: str) -> MenuAction:
        return MenuAction(
            id=f"W_LET_{char}",
            label=f"{slot}: {char}",
            hint=f"Insertar {char}",
            action_type="WRITING_LETTER",
            snippet=char,
            icon="variables",
            sticky=True,
        )

    # ------------------------------------------------------------------ #
    # T9 menus
    # ------------------------------------------------------------------ #
    def _build_letter_group(
        self,
        node_id: str,
        title: str,
        breadcrumb: str,
        letters: List[str],
        slot8_letter: Optional[str] = None,
    ) -> MenuNode:
        items: List[Optional[MenuAction]] = [None] * 9
        positions = [0, 1, 2, 3, 5]
        for pos, char in zip(positions, letters[:5]):
            items[pos] = self._letter_action(pos + 1, char)

        items[4] = create_pause_action("5")
        items[6] = create_back_action("WRITING_T9", "7")

        if slot8_letter:
            items[7] = self._letter_action(8, slot8_letter)
            items[8] = MenuAction(
                id=f"{node_id}_SPACE",
                label="9: Espacio",
                hint="Insertar un espacio",
                action_type="WRITING_SPACE",
                icon="format",
            )
        else:
            items[7] = MenuAction(
                id=f"{node_id}_WORDS",
                label="8: Palabras",
                hint="Predicciones para lo que llevas escrito",
                action_type="SUBMENU",
                submenu_id="WRITING_PREDICT",
                icon="ai_spark",
            )
            items[8] = MenuAction(
                id=f"{node_id}_SPACE",
                label="9: Espacio",
                hint="Insertar un espacio",
                action_type="WRITING_SPACE",
                icon="format",
            )

        return MenuNode(
            id=node_id,
            title=title,
            breadcrumb_label=breadcrumb,
            items=[item for item in items if item is not None],
            parent_id="WRITING_T9",
            sticky=True,
        )

    def build_prediction_items(self) -> List[MenuAction]:
        """Builds the 9-slot prediction panel for the current prefix."""
        words = self.predictions()
        positions = [0, 1, 2, 3, 5, 7]
        items: List[Optional[MenuAction]] = [None] * 9

        for pos, word in zip(positions, words):
            items[pos] = MenuAction(
                id=f"W_PRED_{pos}",
                label=f"{pos + 1}: {word}",
                hint=f"Insertar «{word}»",
                action_type="WRITING_WORD",
                snippet=word,
                icon="ai_spark",
                sticky=True,
            )

        for pos in positions:
            if items[pos] is None:
                items[pos] = MenuAction(
                    id=f"W_PRED_EMPTY_{pos}",
                    label=f"{pos + 1}: —",
                    hint="Sin coincidencias",
                    action_type="NOOP",
                    snippet="",
                    icon="",
                    sticky=True,
                )

        items[4] = create_pause_action("5")
        items[6] = create_back_action("WRITING_T9", "7")
        items[8] = MenuAction(
            id="W_PRED_BACKSPACE",
            label="9: Borrar",
            hint="Borrar el último carácter",
            action_type="WRITING_BACKSPACE",
            icon="edit",
        )
        return [item for item in items if item is not None]

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
        tree["WRITING_CONNECTORS"] = make_submenu("WRITING_CONNECTORS", "CONECTORES", connectors)

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
            "WRITING_WORDS", "PALABRAS Y FRASES", words, parent_id="WRITING_T9"
        )

        markdown = [
            _act("1", "W_MD_1", "H1", "# "),
            _act("2", "W_MD_2", "H2", "## "),
            _act("3", "W_MD_3", "Negrita", "**|>**"),
            _act("4", "W_MD_4", "Cursiva", "*|>*"),
            _act("6", "W_MD_5", "Checkbox", "- [ ] "),
            _act("8", "W_MD_6", "Código", "```|>|\n```"),
            _act("9", "W_MD_7", "Enlace", "[|>](url)"),
        ]
        tree["WRITING_MARKDOWN"] = make_submenu("WRITING_MARKDOWN", "FORMATO DE TEXTO", markdown)

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
            MenuAction("WRITING_CLIPBOARD", "9: PORTAPAPELES", "Historial de copias", "SUBMENU", submenu_id="CLIPBOARD_HISTORY", icon="edit"),
        ]
        for a in cursor:
            if a.key_name:
                a.action_type = "KEY"
                a.snippet = None
        tree["WRITING_CURSOR"] = make_submenu("WRITING_CURSOR", "CURSOR / SELECCIÓN", cursor)
        try:
            from ideye.actions.clipboard_history import get_clipboard_history_manager

            tree["CLIPBOARD_HISTORY"] = get_clipboard_history_manager().get_clipboard_menu_node(
                parent_id="WRITING_CURSOR"
            )
        except Exception:
            pass

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
            _act("1", "W_AI_1", "Continuar frase", "continue", action_type="WRITING_AI"),
            _act("2", "W_AI_2", "Cerrar párrafo", "close_paragraph", action_type="WRITING_AI"),
            _act("3", "W_AI_3", "Reformular", "rephrase", action_type="WRITING_AI"),
            _act("4", "W_AI_4", "Resumir", "summarize", action_type="WRITING_AI"),
            _act("6", "W_AI_5", "Expandir", "expand", action_type="WRITING_AI"),
            _act("8", "W_AI_6", "Corregir", "correct", action_type="WRITING_AI"),
            _act("9", "W_AI_7", "Traducir EN", "translate_en", action_type="WRITING_AI"),
        ]
        tree["WRITING_AI"] = make_submenu("WRITING_AI", "SUGERENCIAS DE REDACCIÓN", ai)

        # Full T9 keyboard: five letter groups plus predictions, accents and
        # uppercase. Every letter action remains in its group so the user can
        # type several letters without returning to the root on each dwell.
        ae = self._build_letter_group("WRITING_AE", "LETRAS: A - E", "a-e", ["a", "b", "c", "d", "e"])
        fj = self._build_letter_group("WRITING_FJ", "LETRAS: F - J", "f-j", ["f", "g", "h", "i", "j"])
        ko = self._build_letter_group("WRITING_KO", "LETRAS: K - O", "k-o", ["k", "l", "m", "n", "o"], slot8_letter="ñ")
        pt = self._build_letter_group("WRITING_PT", "LETRAS: P - T", "p-t", ["p", "q", "r", "s", "t"])
        uz = self._build_letter_group("WRITING_UZ", "LETRAS: U - Z", "u-z", ["u", "v", "w", "x", "y", "z"], slot8_letter="z")

        tree["WRITING_AE"] = ae
        tree["WRITING_FJ"] = fj
        tree["WRITING_KO"] = ko
        tree["WRITING_PT"] = pt
        tree["WRITING_UZ"] = uz

        more = [
            self._letter_action(1, "á"),
            self._letter_action(2, "é"),
            self._letter_action(3, "í"),
            self._letter_action(4, "ó"),
            None,  # pause
            self._letter_action(6, "ú"),
            create_back_action("WRITING_T9", "7"),
            self._letter_action(8, "ü"),
            MenuAction(
                id="W_CASE",
                label="9: Mayús ON/OFF",
                hint="Alternar mayúsculas",
                action_type="WRITING_CASE",
                icon="format",
            ),
        ]
        more[4] = create_pause_action("5")
        tree["WRITING_MORE"] = MenuNode(
            id="WRITING_MORE",
            title="ACENTOS / MAYÚSCULAS",
            breadcrumb_label="ACENTOS",
            items=[item for item in more if item is not None],
            parent_id="WRITING_T9",
            sticky=True,
        )

        tree["WRITING_PREDICT"] = MenuNode(
            id="WRITING_PREDICT",
            title="PALABRAS SUGERIDAS",
            breadcrumb_label="PALABRAS",
            items=self.build_prediction_items(),
            parent_id="WRITING_T9",
            sticky=True,
        )

        t9_root_items = [
            MenuAction("W_T9_AE", "1: a - e", "Letras a, b, c, d, e", "SUBMENU", submenu_id="WRITING_AE", icon="variables"),
            MenuAction("W_T9_FJ", "2: f - j", "Letras f, g, h, i, j", "SUBMENU", submenu_id="WRITING_FJ", icon="variables"),
            MenuAction("W_T9_KO", "3: k - o", "Letras k, l, m, n, ñ, o", "SUBMENU", submenu_id="WRITING_KO", icon="variables"),
            MenuAction("W_T9_PT", "4: p - t", "Letras p, q, r, s, t", "SUBMENU", submenu_id="WRITING_PT", icon="variables"),
            create_pause_action("5"),
            MenuAction("W_T9_UZ", "6: u - z", "Letras u, v, w, x, y, z", "SUBMENU", submenu_id="WRITING_UZ", icon="variables"),
            create_back_action("ROOT", "7"),
            MenuAction("W_T9_WORDS", "8: Palabras/frases", "Predicciones y frases completas", "SUBMENU", submenu_id="WRITING_WORDS", icon="ai_spark"),
            MenuAction("W_T9_MORE", "9: Acentos", "Acentos, ñ, ü y mayúsculas", "SUBMENU", submenu_id="WRITING_MORE", icon="format"),
        ]
        tree["WRITING_T9"] = MenuNode(
            id="WRITING_T9",
            title="TECLADO DE LETRAS",
            breadcrumb_label="LETRAS / PALABRAS",
            items=t9_root_items,
            parent_id="ROOT",
            sticky=True,
        )

        root_items = [
            MenuAction("WRITING_CONNECTORS", "1: CONECTORES", "Conectores y transiciones", "SUBMENU", submenu_id="WRITING_CONNECTORS", icon="flow"),
            MenuAction("WRITING_MARKDOWN", "2: Formato de texto", "Títulos, listas y negritas", "SUBMENU", submenu_id="WRITING_MARKDOWN", icon="format"),
            MenuAction("WRITING_PUNCTUATION", "3: PUNTUACIÓN", "Signos de puntuación", "SUBMENU", submenu_id="WRITING_PUNCTUATION", icon="operators"),
            MenuAction("WRITING_CURSOR", "4: CURSOR / SELECCIÓN", "Movimiento y selección", "SUBMENU", submenu_id="WRITING_CURSOR", icon="navigation"),
            None,  # pause placeholder
            MenuAction("WRITING_T9", "6: Escribir letras", "Teclado de letras, acentos y predicción", "SUBMENU", submenu_id="WRITING_T9", icon="variables"),
            MenuAction("WRITING_DELETE", "7: Borrar y deshacer", "Borrado y deshacer", "SUBMENU", submenu_id="WRITING_DELETE", icon="edit"),
            MenuAction("WRITING_JUMP", "8: Saltos y párrafos", "Saltos y párrafos", "SUBMENU", submenu_id="WRITING_JUMP", icon="navigation"),
            MenuAction("WRITING_AI", "9: Sugerencias", "Ideas para seguir escribiendo", "SUBMENU", submenu_id="WRITING_AI", icon="ai_spark"),
        ]
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
        return self.predictions()


WritingModeAlias = WritingMode
DocMode = WritingMode
WRITING_MODE = WritingMode
Writing = WritingMode
