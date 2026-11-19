"""
IDEye - Hierarchical 3x3 Menu Trees Module (Phase 3)
Defines MenuAction and MenuNode dataclasses, complete 3x3 navigation hierarchy,
sticky mode transitions, and mathematical validation protocol.

Golden Rules of Gaze Ergonomics:
1. Every grid layout has EXACTLY 9 cells (indices 0 to 8).
2. The Center Cell (Index 4) is ALWAYS ' PAUSA / MODO LECTURA' across all menus.
3. In any submenu (Level >= 2), the Bottom-Left Cell (Index 6) is ALWAYS ' VOLVER ATRÁS'.
4. Sticky Submenus (NAV, EDIT, FORMAT) stay active for repetitive actions until 'VOLVER' is chosen.
5. Non-sticky actions automatically return to 'ROOT' after injecting a snippet.
"""


from ideye.actions.trees_model import (  # noqa: F401
    MenuAction,
    MenuNode,
    create_pause_action,
    create_back_action,
)
from ideye.actions.trees_populators import (  # noqa: F401
    populate_ai_prediction_items,
    populate_local_symbol_items,
    populate_exit_confirm_items,
    populate_help_items,
    populate_lang_select_items,
    create_standard_menu_action,
    create_adaptive_menu_action,
    get_dynamic_ast_action_for_context,
)
from ideye.actions.trees_adaptive import (  # noqa: F401
    get_adaptive_context_node,
)
from ideye.actions.trees_builders import (  # noqa: F401
    _build_flow_items,
    _build_flow_try_items,
    _build_struct_items,
    _build_struct_import_items,
    _build_op_items,
    _build_op_logical_items,
    _build_op_delim_items,
    _build_op_punct_items,
)
from ideye.actions.trees_root import (  # noqa: F401
    build_menu_tree,
    populate_command_palette_items,
)
from ideye.actions.trees_validation import (  # noqa: F401
    validate_menu_tree,
    get_breadcrumb_path,
)
