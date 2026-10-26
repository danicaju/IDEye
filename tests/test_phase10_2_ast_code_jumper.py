"""Phase 10.2: Semantic AST Code Jumper symbol extraction and 3x3 map."""

import textwrap
import unittest

from eyede.actions.ast_code_jumper import ASTCodeJumper


SAMPLE = textwrap.dedent(
    """
    class Alpha:
        def first(self):
            pass

        async def second(self):
            pass

    def global_fn():
        pass

    class Beta:
        def third(self):
            pass

    async def async_global():
        pass
    """
).strip()


class TestASTCodeJumper(unittest.TestCase):
    def setUp(self):
        self.jumper = ASTCodeJumper()
        self.symbols = self.jumper.extract_symbols(SAMPLE)

    def test_extracts_classes_functions_and_methods_with_lines(self):
        names = [item["name"] for item in self.symbols]
        self.assertEqual(names, ["Alpha", "first", "second", "global_fn", "Beta", "third", "async_global"])
        self.assertEqual(self.symbols[0]["type"], "Clase")
        self.assertEqual(self.symbols[1]["type"], "M?todo")
        self.assertEqual(self.symbols[3]["type"], "Funci?n")
        self.assertEqual(self.symbols[0]["line"], 1)
        self.assertEqual(self.symbols[6]["type"], "Funci?n")

    def test_menu_has_nine_slots_and_invariants(self):
        node = self.jumper.get_symbols_menu_node(self.symbols, 0)
        self.assertEqual(len(node.items), 9)
        self.assertEqual(node.items[4].action_type, "PAUSE")
        self.assertEqual(node.items[6].action_type, "BACK")
        self.assertEqual(node.items[0].action_type, "AST_JUMP")
        self.assertEqual(node.items[0].snippet, "1")

    def test_pagination_and_refresh(self):
        node = self.jumper.get_symbols_menu_node(self.symbols, 0)
        self.assertEqual(node.items[8].action_type, "AST_NEXT_PAGE")
        last = self.jumper.get_symbols_menu_node(self.symbols, 1)
        self.assertEqual(last.items[8].action_type, "AST_REFRESH")
        self.assertEqual(last.items[0].snippet, str(self.symbols[6]["line"]))

    def test_empty_source_is_safe(self):
        self.assertEqual(self.jumper.extract_symbols(""), [])
        node = self.jumper.get_symbols_menu_node([], 0)
        self.assertEqual(node.items[4].action_type, "PAUSE")
        self.assertEqual(node.items[6].action_type, "BACK")


if __name__ == "__main__":
    unittest.main()
