"""
Automated Forensic Test Suite: Menu Integrity (Phase Extra)
Recursively audits the entire 3x3 hierarchical menu tree structure in menu_trees.py,
verifying that every node contains exactly 9 items, cell 4 is Pause/Reading Mode,
cell 6 is Back Navigation for all submenus, and all breadcrumbs and links resolve cleanly.
"""

import os
import sys
import unittest
from typing import Set, Dict

# Ensure project root is in sys.path
_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_EYEDE_DIR = os.path.join(_ROOT_DIR, "eyede")
for p in (_ROOT_DIR, _EYEDE_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

from eyede.actions.menu_trees import (
    MenuNode,
    MenuAction,
    build_menu_tree,
    validate_menu_tree,
    get_breadcrumb_path,
    populate_ai_prediction_items,
    populate_local_symbol_items,
    create_pause_action,
    create_back_action,
)


class TestMenuIntegrity(unittest.TestCase):
    """Forensic integrity audit for all 3x3 menu trees and golden ergonomic rules."""

    def setUp(self):
        self.tree: Dict[str, MenuNode] = build_menu_tree()

    def test_tree_contains_root_and_validates(self):
        """The built menu tree must contain ROOT and pass built-in validation."""
        self.assertIn("ROOT", self.tree)
        valid, errors = validate_menu_tree(self.tree)
        self.assertTrue(valid, f"Menu validation errors found: {errors}")
        self.assertEqual(len(errors), 0)

    def test_every_node_has_exactly_nine_items(self):
        """Golden Rule 1: Every single menu node in the tree must have exactly 9 children (0..8)."""
        for node_id, node in self.tree.items():
            self.assertEqual(
                len(node.items),
                9,
                f"Node '{node_id}' has {len(node.items)} items instead of exactly 9.",
            )

    def test_center_cell_four_is_always_pause_in_all_nodes(self):
        """Golden Rule 2: Cell index 4 is strictly reserved for 'PAUSE / MODO LECTURA' across ALL nodes."""
        for node_id, node in self.tree.items():
            cell_4 = node.items[4]
            self.assertEqual(
                cell_4.action_type,
                "PAUSE",
                f"Node '{node_id}' cell 4 action_type is '{cell_4.action_type}' (expected 'PAUSE').",
            )
            self.assertIn(
                "PAUSA",
                cell_4.label.upper(),
                f"Node '{node_id}' cell 4 label does not mention PAUSA: '{cell_4.label}'",
            )

    def test_cell_six_is_always_back_in_all_submenus(self):
        """Golden Rule 3: For all submenus (node_id != 'ROOT'), Cell index 6 is strictly 'VOLVER ATRÁS'."""
        for node_id, node in self.tree.items():
            if node_id == "ROOT":
                continue

            cell_6 = node.items[6]
            self.assertEqual(
                cell_6.action_type,
                "BACK",
                f"Submenu '{node_id}' cell 6 action_type is '{cell_6.action_type}' (expected 'BACK').",
            )
            self.assertIn(
                "VOLVER",
                cell_6.label.upper(),
                f"Submenu '{node_id}' cell 6 label does not mention VOLVER: '{cell_6.label}'",
            )
            self.assertEqual(
                cell_6.submenu_id,
                node.parent_id,
                f"Submenu '{node_id}' back target '{cell_6.submenu_id}' does not match parent '{node.parent_id}'.",
            )

    def test_recursive_tree_traversal_from_root(self):
        """Recursively traverses all submenus from ROOT, verifying zero unreachable nodes and valid references."""
        visited: Set[str] = set()

        def _traverse(node_id: str):
            self.assertIn(node_id, self.tree, f"Referenced node '{node_id}' is missing from menu tree.")
            visited.add(node_id)
            node = self.tree[node_id]

            for item in node.items:
                if item.action_type == "SUBMENU":
                    target_id = item.submenu_id
                    self.assertIsNotNone(target_id, f"SUBMENU item in '{node_id}' has None submenu_id.")
                    if target_id not in visited:
                        _traverse(target_id)

        _traverse("ROOT")
        self.assertGreater(len(visited), 10, "Tree has too few reachable nodes.")
        # All standard nodes in the tree should be reachable from ROOT (except aliases/aux nodes)
        expected_aux_or_alias = {"AI_PREDICT", "HELP", "LANG_SELECT"}
        unreachable = set(self.tree.keys()) - visited
        self.assertEqual(unreachable - expected_aux_or_alias, set(), f"Unexpected unreachable nodes: {unreachable}")

    def test_every_submenu_has_valid_return_path_to_root(self):
        """Every node must be able to climb back to 'ROOT' via parent_id without infinite loops."""
        for node_id, node in self.tree.items():
            curr = node_id
            climb_visited = set()
            while curr != "ROOT":
                self.assertNotIn(curr, climb_visited, f"Cycle detected when navigating back from '{node_id}'.")
                climb_visited.add(curr)
                curr_node = self.tree.get(curr)
                self.assertIsNotNone(curr_node, f"Broken link to parent in tree at '{curr}'.")
                self.assertIsNotNone(curr_node.parent_id, f"Node '{curr}' has no parent_id and cannot reach ROOT.")
                curr = curr_node.parent_id

    def test_dynamic_ai_prediction_items_integrity(self):
        """populate_ai_prediction_items() must always construct exactly 9 items meeting golden rules."""
        # 1. With empty predictions
        items_empty = populate_ai_prediction_items([], parent_id="ROOT")
        self.assertEqual(len(items_empty), 9)
        self.assertEqual(items_empty[4].action_type, "PAUSE")
        self.assertEqual(items_empty[6].action_type, "BACK")
        self.assertEqual(items_empty[6].submenu_id, "ROOT")
        self.assertEqual(items_empty[8].id, "AI_REGENERATE")

        # 2. With 6 custom predictions
        custom_preds = ["def foo():", "for x in data:", "print(val)", "return True", "x = 42", "pass"]
        items_custom = populate_ai_prediction_items(custom_preds, parent_id="SNIPPETS")
        self.assertEqual(len(items_custom), 9)
        self.assertEqual(items_custom[4].action_type, "PAUSE")
        self.assertEqual(items_custom[6].action_type, "BACK")
        self.assertEqual(items_custom[6].submenu_id, "SNIPPETS")
        # Check prediction slots
        pred_indices = [0, 1, 2, 3, 5, 7]
        for idx, expected in zip(pred_indices, custom_preds):
            self.assertEqual(items_custom[idx].action_type, "SNIPPET")
            self.assertEqual(items_custom[idx].snippet, expected)

    def test_dynamic_local_symbols_items_integrity(self):
        """populate_local_symbol_items() must always construct exactly 9 items meeting golden rules."""
        symbols = ["counter", "user_id", "items_list", "total"]
        items = populate_local_symbol_items(symbols, parent_id="ROOT")
        self.assertEqual(len(items), 9)
        self.assertEqual(items[4].action_type, "PAUSE")
        self.assertEqual(items[6].action_type, "BACK")
        self.assertEqual(items[6].submenu_id, "ROOT")

    def test_breadcrumb_trail_generation(self):
        """get_breadcrumb_path() must generate correct directional path strings."""
        self.assertEqual(get_breadcrumb_path(self.tree, "ROOT"), "RAÍZ")
        self.assertIn("RAÍZ", get_breadcrumb_path(self.tree, "FLOW"))
        self.assertIn("FLUJO", get_breadcrumb_path(self.tree, "FLOW"))

        # Deep node
        if "FLOW_IF" in self.tree:
            trail = get_breadcrumb_path(self.tree, "FLOW_IF")
            self.assertTrue(trail.startswith("RAÍZ > "))
            self.assertIn("IF / ELIF", trail)

    def test_help_menu_node_integrity_and_golden_rules(self):
        """Verifies tree['HELP'] node integrity and Golden Ergonomic Rules."""
        self.assertIn("HELP", self.tree)
        help_node = self.tree["HELP"]
        self.assertEqual(len(help_node.items), 9)
        self.assertEqual(help_node.parent_id, "ROOT")
        self.assertEqual(help_node.items[4].action_type, "PAUSE")
        self.assertEqual(help_node.items[6].action_type, "BACK")
        self.assertEqual(help_node.items[6].submenu_id, "ROOT")
        self.assertEqual(help_node.items[8].action_type, "BACK")
        self.assertEqual(help_node.items[8].submenu_id, "ROOT")


if __name__ == "__main__":
    unittest.main()
