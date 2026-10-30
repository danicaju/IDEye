"""Semantic AST symbol map for one-click VS Code jumping."""

from __future__ import annotations

import ast
from typing import Any, Dict, List, Optional

try:
    from ideye.actions.menu_trees import MenuAction, MenuNode, create_back_action, create_pause_action
except ImportError:  # pragma: no cover
    from actions.menu_trees import MenuAction, MenuNode, create_back_action, create_pause_action  # type: ignore


class _SymbolVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.symbols: List[Dict[str, Any]] = []
        self._classes: List[str] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.symbols.append({"name": node.name, "type": "Clase", "line": int(node.lineno), "kind": "class"})
        self._classes.append(node.name)
        self.generic_visit(node)
        self._classes.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._add_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._add_function(node)

    def _add_function(self, node: Any) -> None:
        is_method = bool(self._classes)
        self.symbols.append({
            "name": node.name,
            "type": "Método" if is_method else "Función",
            "line": int(node.lineno),
            "kind": "method" if is_method else "function",
        })
        self.generic_visit(node)


class ASTCodeJumper:
    """Extracts classes/functions and maps six symbols per 3x3 page."""

    SYMBOL_SLOTS = (0, 1, 2, 3, 5, 7)

    def __init__(self, context_reader: Optional[Any] = None) -> None:
        self.context_reader = context_reader
        self.symbols: List[Dict[str, Any]] = []
        self.current_page: int = 0

    def extract_symbols(self, source_code: Optional[str] = None, file_path: Optional[str] = None) -> List[Dict[str, Any]]:
        content = source_code
        if content is None and self.context_reader is not None:
            try:
                content = self.context_reader.read_file_content(file_path)
            except Exception:
                content = ""
        if not content:
            self.symbols = []
            return []
        try:
            tree = ast.parse(content)
        except (SyntaxError, ValueError):
            self.symbols = []
            return []
        visitor = _SymbolVisitor()
        visitor.visit(tree)
        self.symbols = sorted(visitor.symbols, key=lambda item: (int(item["line"]), int(item["kind"] == "class")))
        return list(self.symbols)

    def page_count(self, symbols_list: Optional[List[Dict[str, Any]]] = None) -> int:
        symbols = self.symbols if symbols_list is None else symbols_list
        return max(1, (len(symbols) + 5) // 6)

    def get_symbols_menu_node(
        self,
        symbols_list: Optional[List[Dict[str, Any]]] = None,
        current_page: int = 0,
        parent_id: str = "ROOT",
    ) -> MenuNode:
        symbols = list(self.symbols if symbols_list is None else symbols_list)
        pages = self.page_count(symbols)
        page = max(0, min(pages - 1, int(current_page)))
        start = page * 6
        page_symbols = symbols[start:start + 6]
        items: List[Optional[MenuAction]] = [None] * 9
        for index, symbol in enumerate(page_symbols):
            slot = self.SYMBOL_SLOTS[index]
            name = str(symbol.get("name", "?"))[:20]
            items[slot] = MenuAction(
                id=f"AST_SYMBOL_{symbol.get('line', 0)}_{index}",
                label=f"{slot + 1}: {name}",
                hint=f"{symbol.get('type', 'Función')} - L{symbol.get('line', 0)}",
                action_type="AST_JUMP",
                snippet=str(symbol.get("line", 1)),
                icon="function",
            )
        for index in range(len(page_symbols), 6):
            slot = self.SYMBOL_SLOTS[index]
            items[slot] = MenuAction(
                id=f"AST_EMPTY_{page}_{index}",
                label=f"{slot + 1}: ?",
                hint="Sin símbolo en esta ranura",
                action_type="NOOP",
                snippet="",
            )
        items[4] = create_pause_action("5")
        items[6] = create_back_action(parent_id, "7")
        if pages > 1 and page < pages - 1:
            items[8] = MenuAction(
                id="AST_NEXT_PAGE",
                label="9: Siguiente página",
                hint=f"Símbolos {start + 7}-{min(len(symbols), start + 12)} de {len(symbols)}",
                action_type="AST_NEXT_PAGE",
                snippet=str(page + 1),
                icon="navigation",
            )
        else:
            items[8] = MenuAction(
                id="AST_REFRESH",
                label="9: Refrescar AST",
                hint="Volver a analizar el archivo activo",
                action_type="AST_REFRESH",
                snippet="",
                icon="ai_spark",
            )
        return MenuNode(
            id="AST_SYMBOLS",
            title="SALTAR A SÍMBOLO",
            breadcrumb_label=f"AST {page + 1}/{pages}",
            items=[item for item in items if item is not None],
            parent_id=parent_id,
            sticky=True,
        )

    def next_page_node(self, parent_id: str = "ROOT") -> MenuNode:
        self.current_page = (self.current_page + 1) % self.page_count()
        return self.get_symbols_menu_node(self.symbols, self.current_page, parent_id)
