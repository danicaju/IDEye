"""
Internal helpers for building validated 3x3 mode menu trees.
"""

from __future__ import annotations

from typing import List, Optional

try:
    from eyede.actions.menu_trees import MenuNode, MenuAction, create_pause_action, create_back_action
except ImportError:  # pragma: no cover
    from actions.menu_trees import MenuNode, MenuAction, create_pause_action, create_back_action


def make_submenu(
    submenu_id: str,
    title: str,
    actions: List[MenuAction],
    parent_id: str = "ROOT",
) -> MenuNode:
    """Builds a validated 9-item submenu from up to 7 content actions."""
    content = list(actions or [])
    # Pad to 7 content slots (0,1,2,3,5,7,8)
    while len(content) < 7:
        content.append(
            MenuAction(
                id=f"{submenu_id}_FILL_{len(content)}",
                label=f"{len(content) + 1}: ACCIÓN",
                hint="Acción del modo",
                action_type="SNIPPET",
                snippet="",
                icon="",
            )
        )
    content = content[:7]

    items = [
        content[0],
        content[1],
        content[2],
        content[3],
        create_pause_action("5"),
        content[4],
        create_back_action(parent_id, "7"),
        content[5],
        content[6],
    ]
    return MenuNode(
        id=submenu_id,
        title=title,
        breadcrumb_label=title,
        items=items,
        parent_id=parent_id,
        sticky=False,
    )


def make_root(
    title: str,
    items: List[MenuAction],
) -> MenuNode:
    """Builds a 9-item root node (no back requirement)."""
    content = list(items or [])
    while len(content) < 9:
        content.append(
            MenuAction(
                id=f"ROOT_FILL_{len(content)}",
                label=f"{len(content) + 1}: ACCIÓN",
                hint="Acción del modo",
                action_type="SNIPPET",
                snippet="",
                icon="",
            )
        )
    content = content[:9]
    # Force center pause at index 4
    content[4] = create_pause_action("5")
    return MenuNode(
        id="ROOT",
        title=title,
        breadcrumb_label=title,
        items=content,
        parent_id=None,
        sticky=False,
    )
