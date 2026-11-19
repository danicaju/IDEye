"""Mathematical validation and breadcrumb helpers for menu trees."""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple, Set, Union, Any

try:
    from ideye.actions.language_support import (
        LANG_PYTHON,
        LANG_TYPESCRIPT,
        LANG_RUST,
        LANG_CPP,
        LANG_GO,
        SUPPORTED_LANGUAGES,
        LANGUAGE_DISPLAY_NAMES,
        LANGUAGE_BADGES,
        normalize_language,
        get_language_display_name,
        get_language_badge,
    )
except ImportError:
    from actions.language_support import (
        LANG_PYTHON,
        LANG_TYPESCRIPT,
        LANG_RUST,
        LANG_CPP,
        LANG_GO,
        SUPPORTED_LANGUAGES,
        LANGUAGE_DISPLAY_NAMES,
        LANGUAGE_BADGES,
        normalize_language,
        get_language_display_name,
        get_language_badge,
    )

from ideye.actions.trees_model import *  # noqa: F401,F403

def validate_menu_tree(tree: Dict[str, MenuNode]) -> Tuple[bool, List[str]]:
    """
    Performs rigorous mathematical validation on the menu tree hierarchy.
    Checks:
    1. 'ROOT' node exists.
    2. Every node has exactly 9 elements (indices 0..8).
    3. Index 4 is ALWAYS Pause across every node.
    4. Index 6 is ALWAYS Back in every submenu (id != 'ROOT').
    5. Back points to a valid parent_id.
    6. All submenu_id references point to existing nodes (0 orphan references).
    7. All parent_id references point to existing nodes.
    8. No cycles without a path leading back to 'ROOT'.

    Returns:
        (is_valid, list_of_error_messages)
    """
    errors: List[str] = []

    if "ROOT" not in tree:
        errors.append("Fatal: Tree does not contain 'ROOT' node.")
        return False, errors

    for node_id, node in tree.items():
        # Check exactly 9 items
        if len(node.items) != 9:
            errors.append(f"Node '{node_id}' has {len(node.items)} items (expected exactly 9).")

        # Check Index 4 is ALWAYS Pause
        if len(node.items) > 4:
            item_4 = node.items[4]
            if item_4.action_type != "PAUSE":
                errors.append(
                    f"Node '{node_id}' index 4 action_type is '{item_4.action_type}' (expected 'PAUSE')."
                )

        # Check Index 6 is ALWAYS Back for all submenus (excluding MENU_STANDARD which is an alternate root)
        if node_id not in ("ROOT", "MENU_STANDARD") and len(node.items) > 6:
            item_6 = node.items[6]
            if item_6.action_type != "BACK":
                errors.append(
                    f"Submenu '{node_id}' index 6 action_type is '{item_6.action_type}' (expected 'BACK')."
                )
            if item_6.submenu_id != node.parent_id:
                errors.append(
                    f"Submenu '{node_id}' back target '{item_6.submenu_id}' does not match parent '{node.parent_id}'."
                )

        # Check parent_id exists
        if node.parent_id is not None and node.parent_id not in tree:
            errors.append(f"Node '{node_id}' has invalid parent_id '{node.parent_id}' (not in tree).")

        # Check submenu references
        for idx, item in enumerate(node.items):
            if item.action_type == "SUBMENU":
                if not item.submenu_id:
                    errors.append(f"Node '{node_id}' item {idx} has SUBMENU type with empty submenu_id.")
                elif item.submenu_id not in tree:
                    errors.append(
                        f"Node '{node_id}' item {idx} references non-existent submenu '{item.submenu_id}'."
                    )

    # Verify every node can reach 'ROOT' via back navigation
    for node_id, node in tree.items():
        curr = node_id
        visited: Set[str] = set()
        while curr != "ROOT":
            if curr in visited:
                errors.append(f"Cycle detected leading away from ROOT starting at '{node_id}'.")
                break
            visited.add(curr)
            curr_node = tree.get(curr)
            if curr_node is None or curr_node.parent_id is None:
                errors.append(f"Node '{node_id}' has no path back to ROOT.")
                break
            curr = curr_node.parent_id

    return len(errors) == 0, errors


def get_breadcrumb_path(tree: Dict[str, MenuNode], current_node_id: str) -> str:
    """
    Computes a human-readable breadcrumb trail from ROOT to the current node.
    Example: 'RAÍZ > FLUJO / LÓGICA > TRY/RET'
    """
    if current_node_id not in tree:
        return "RAÍZ"

    path_nodes = []
    curr: Optional[str] = current_node_id
    visited: Set[str] = set()

    while curr is not None and curr in tree:
        if curr in visited:
            break
        visited.add(curr)
        node = tree[curr]
        path_nodes.append(node.breadcrumb_label or node.title)
        curr = node.parent_id

    path_nodes.reverse()
    return " > ".join(path_nodes)
