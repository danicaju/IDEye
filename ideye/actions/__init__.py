"""
IDEye Actions Package - OS input and code injection (Phase 3-4)
"""

from ideye.actions.code_injector import (
    CodeInjector,
    DummyKeyboard,
    DummyClipboard,
)
from ideye.actions.menu_trees import (
    MenuAction,
    MenuNode,
    build_menu_tree,
    validate_menu_tree,
    get_breadcrumb_path,
    create_pause_action,
    create_back_action,
    populate_help_items,
)

__all__ = [
    "CodeInjector",
    "DummyKeyboard",
    "DummyClipboard",
    "MenuAction",
    "MenuNode",
    "build_menu_tree",
    "validate_menu_tree",
    "get_breadcrumb_path",
    "create_pause_action",
    "create_back_action",
    "populate_help_items",
]
