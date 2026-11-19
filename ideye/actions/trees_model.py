"""Menu data model (MenuAction, MenuNode) and the mandatory pause/back cells."""

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



@dataclass
class MenuAction:
    """Represents a selectable action or submenu launcher in a 3x3 grid."""
    id: str
    label: str
    hint: str = ""
    action_type: str = "SNIPPET"  # "SNIPPET", "KEY", "SUBMENU", "PAUSE", "BACK", "EXIT"
    snippet: Optional[str] = None
    key_name: Optional[str] = None
    cursor_offset_left: int = 0
    cursor_offset_up: int = 0
    sticky: bool = False
    submenu_id: Optional[str] = None
    icon: str = ""
    mode_id: Optional[str] = None


@dataclass
class MenuNode:
    """Represents a 3x3 grid menu state containing exactly 9 items."""
    id: str
    title: str
    items: List[MenuAction]
    parent_id: Optional[str] = None
    sticky: bool = False
    breadcrumb_label: str = ""

    def __post_init__(self):
        if not self.breadcrumb_label:
            self.breadcrumb_label = self.title


def create_pause_action(key_num: str = "5") -> MenuAction:
    """Returns the standardized Center (Index 4) Pause/Reading Mode action."""
    return MenuAction(
        id="PAUSE_RESUME",
        label=f"{key_num}: Pausa / Descanso",
        hint="Descansa la vista (mira y abre la boca)",
        action_type="PAUSE",
        icon="",
        sticky=False,
    )


def create_back_action(parent_id: str = "ROOT", key_num: str = "7") -> MenuAction:
    """Returns the standardized Bottom-Left (Index 6) Back navigation action."""
    return MenuAction(
        id="ACTION_BACK",
        label=f"{key_num}: VOLVER ATRÁS",
        hint="Regresar al nivel anterior",
        action_type="BACK",
        submenu_id=parent_id,
        icon="",
        sticky=False,
    )
