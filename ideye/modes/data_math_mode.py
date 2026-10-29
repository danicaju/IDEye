"""
IDEye - Data, SQL & Math Context Mode (Phase 6)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ideye.actions.menu_trees import MenuAction, MenuNode

try:
    from ideye.modes._helpers import make_root, make_submenu
except ImportError:  # pragma: no cover
    from modes._helpers import make_root, make_submenu

from .base_mode import BaseMode


def _act(slot, aid, label, snippet=None, key_name=None, action_type="SNIPPET"):
    ma = MenuAction(id=aid, label=f"{slot}: {label}", hint=label, action_type=action_type, snippet=snippet, key_name=key_name, icon="")
    if key_name:
        ma.action_type = "KEY"
        ma.snippet = None
    return ma


class DataMathMode(BaseMode):
    mode_id = "data_math"
    display_name = "Datos"
    theme_color = "#F59E0B"

    def get_menu_tree(self, language: Optional[str] = None) -> Dict[str, MenuNode]:
        tree: Dict[str, MenuNode] = {}

        sql_basic = [
            _act("1", "D_SQL_SELECT", "SELECT * FROM", "SELECT * FROM "),
            _act("2", "D_SQL_WHERE", "WHERE", " WHERE "),
            _act("3", "D_SQL_JOIN", "JOIN", " JOIN "),
            _act("4", "D_SQL_GROUP", "GROUP BY", " GROUP BY "),
            _act("6", "D_SQL_ORDER", "ORDER BY", " ORDER BY "),
            _act("8", "D_SQL_LIMIT", "LIMIT", " LIMIT "),
            _act("9", "D_SQL_FROM", "FROM", " FROM "),
        ]
        tree["DATA_SQL_BASIC"] = make_submenu("DATA_SQL_BASIC", "SQL BÁSICO", sql_basic)

        sql_advanced = [
            _act("1", "D_SQL_INSERT", "INSERT INTO", "INSERT INTO  () VALUES ();"),
            _act("2", "D_SQL_UPDATE", "UPDATE", "UPDATE  SET "),
            _act("3", "D_SQL_DELETE", "DELETE FROM", "DELETE FROM "),
            _act("4", "D_SQL_CREATE", "CREATE TABLE", "CREATE TABLE  ("),
            _act("6", "D_SQL_ALTER", "ALTER TABLE", "ALTER TABLE  "),
            _act("8", "D_SQL_HAVING", "HAVING", " HAVING "),
            _act("9", "D_SQL_UNION", "UNION", " UNION "),
        ]
        tree["DATA_SQL_ADV"] = make_submenu("DATA_SQL_ADV", "SQL AVANZADO", sql_advanced)

        json_yaml = [
            _act("1", "D_JSON_OBJ", "Objeto JSON", '{\n    "": \n}'),
            _act("2", "D_JSON_ARR", "Array JSON", "[\n    \n]"),
            _act("3", "D_YAML_KEY", "Clave YAML", ": "),
            _act("4", "D_YAML_LIST", "Lista YAML", "- "),
            _act("6", "D_JSON_QUOTE", "Comillas", "\"\""),
            _act("8", "D_JSON_COMMA", "Coma", ","),
            _act("9", "D_JSON_COLON", "Dos puntos", ": "),
        ]
        tree["DATA_JSON_YAML"] = make_submenu("DATA_JSON_YAML", "JSON / YAML", json_yaml)

        latex_basic = [
            _act("1", "D_LTX_INLINE", "Inline $", "$|$"),
            _act("2", "D_LTX_DISPLAY", "Display $$", "$$|>$$"),
            _act("3", "D_LTX_FRAC", "Fracción", r"\frac{|>}{ }"),
            _act("4", "D_LTX_SUM", "Sumatoria", r"\sum_{}^{}"),
            _act("6", "D_LTX_ALPHA", "α β γ", r"\alpha, \beta, \gamma"),
            _act("8", "D_LTX_ALIGN", "Align", r"\begin{align}|>\end{align}"),
            _act("9", "D_LTX_SQRT", "Raíz", r"\sqrt{|>}"),
        ]
        tree["DATA_LATEX"] = make_submenu("DATA_LATEX", "FÓRMULAS", latex_basic)

        math_ops = [
            _act("1", "D_MATH_PLUS", "+", " + "),
            _act("2", "D_MATH_MINUS", "-", " - "),
            _act("3", "D_MATH_MUL", "*", " * "),
            _act("4", "D_MATH_DIV", "/", " / "),
            _act("6", "D_MATH_POW", "^", " ** "),
            _act("8", "D_MATH_MOD", "%", " % "),
            _act("9", "D_MATH_PAREN", "()", "( )"),
        ]
        tree["DATA_MATH_OPS"] = make_submenu("DATA_MATH_OPS", "OPERADORES", math_ops)

        cursor = [
            _act("1", "D_CUR_LEFT", "Izquierda", None, key_name="LEFT"),
            _act("2", "D_CUR_RIGHT", "Derecha", None, key_name="RIGHT"),
            _act("3", "D_CUR_UP", "Arriba", None, key_name="UP"),
            _act("4", "D_CUR_DOWN", "Abajo", None, key_name="DOWN"),
            _act("6", "D_CUR_HOME", "Inicio", None, key_name="HOME"),
            _act("8", "D_CUR_END", "Fin", None, key_name="END"),
            MenuAction("DATA_CLIPBOARD", "9: PORTAPAPELES", "Historial de copias", "SUBMENU", submenu_id="CLIPBOARD_HISTORY", icon="edit"),
        ]
        tree["DATA_CURSOR"] = make_submenu("DATA_CURSOR", "CURSOR", cursor)
        try:
            from ideye.actions.clipboard_history import get_clipboard_history_manager

            tree["CLIPBOARD_HISTORY"] = get_clipboard_history_manager().get_clipboard_menu_node(
                parent_id="DATA_CURSOR"
            )
        except Exception:
            pass

        delete = [
            _act("1", "D_DEL_BACK", "Backspace", None, key_name="BACKSPACE"),
            _act("2", "D_DEL_WORD", "Borrar palabra", None, key_name="DELETE_WORD"),
            _act("3", "D_DEL_LINE", "Borrar línea", None, key_name="DELETE_LINE"),
            _act("4", "D_DEL_UNDO", "Deshacer", None, key_name="UNDO"),
            _act("6", "D_DEL_REDO", "Rehacer", None, key_name="REDO"),
            _act("8", "D_DEL_CLEAR", "Limpiar", None, key_name="CLEAR_LINE"),
            _act("9", "D_DEL_CANCEL", "Cancelar", None, key_name="CTRL_C"),
        ]
        tree["DATA_DELETE"] = make_submenu("DATA_DELETE", "BORRAR", delete)

        ai = [
            _act("1", "D_AI_QUERY", "Generar consulta", "SELECT * FROM table WHERE "),
            _act("2", "D_AI_JOIN", "Sugerir JOIN", "JOIN  ON "),
            _act("3", "D_AI_FORMULA", "Fórmula LaTeX", r"\frac{}{}"),
            _act("4", "D_AI_JSON", "JSON schema", '{\n    "id": 0,\n    "name": ""\n}'),
            _act("6", "D_AI_WHERE", "Condición WHERE", " WHERE  = "),
            _act("8", "D_AI_GROUP", "Agregación", " GROUP BY "),
            _act("9", "D_AI_ORDER", "Ordenación", " ORDER BY  ASC"),
        ]
        tree["DATA_AI"] = make_submenu("DATA_AI", "SUGERENCIAS DE DATOS", ai)

        root_items = [
            MenuAction("DATA_SQL_BASIC", "1: SQL básico", "Consultas SQL básicas", "SUBMENU", submenu_id="DATA_SQL_BASIC", icon="flow"),
            MenuAction("DATA_SQL_ADV", "2: SQL avanzado", "DDL y avanzado", "SUBMENU", submenu_id="DATA_SQL_ADV", icon="struct"),
            MenuAction("DATA_JSON_YAML", "3: JSON / YAML", "Datos estructurados", "SUBMENU", submenu_id="DATA_JSON_YAML", icon="variables"),
            MenuAction("DATA_LATEX", "4: Fórmulas", "Fórmulas matemáticas", "SUBMENU", submenu_id="DATA_LATEX", icon="operators"),
            None,
            MenuAction("DATA_MATH_OPS", "6: Operadores", "Operadores matemáticos", "SUBMENU", submenu_id="DATA_MATH_OPS", icon="operators"),
            MenuAction("DATA_CURSOR", "7: Mover cursor", "Navegación", "SUBMENU", submenu_id="DATA_CURSOR", icon="navigation"),
            MenuAction("DATA_DELETE", "8: Borrar", "Borrado", "SUBMENU", submenu_id="DATA_DELETE", icon="edit"),
            MenuAction("DATA_AI", "9: Sugerencias", "Consultas y fórmulas sugeridas", "SUBMENU", submenu_id="DATA_AI", icon="ai_spark"),
        ]
        from ideye.actions.menu_trees import create_pause_action
        root_items[4] = create_pause_action("5")
        root = make_root("SQL & LATEX", root_items)
        tree["ROOT"] = root
        return tree

    def get_root_menu(self, language: Optional[str] = None) -> MenuNode:
        return self.get_menu_tree(language)["ROOT"]

    def get_ai_system_prompt(self, context_data: Optional[Dict[str, Any]] = None) -> str:
        return (
            "You are a SQL, JSON, YAML, and LaTeX assistant for a disabled programmer using eye-tracking. "
            "Suggest queries, joins, aggregations, structured data snippets, and mathematical formulas. "
            "Return ONLY a JSON array of exactly 6 strings."
        )

    def get_heuristic_predictions(
        self, context_data: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        return [
            "SELECT * FROM ",
            "WHERE ",
            "JOIN  ON ",
            "GROUP BY ",
            "$$|>$$",
            r"\frac{|>}{ }",
        ]


DataMode = DataMathMode
MathMode = DataMathMode
DATA_MODE = DataMathMode
DataMath = DataMathMode
SqlMode = DataMathMode
LatexMode = DataMathMode
