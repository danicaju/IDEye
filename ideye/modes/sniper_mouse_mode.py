"""IDEye - Sniper Mouse Mode (Phase 7).

Two-step OS mouse targeting:
1. Pick one of the visible 3x3 macro sectors.
2. Pick one of nine precision sub-cells inside the locked sector.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

try:
    from ideye.actions.menu_trees import (
        MenuAction,
        MenuNode,
        create_back_action,
        create_pause_action,
    )
    from ideye.modes.base_mode import BaseMode
except ImportError:  # pragma: no cover - script-style imports
    from actions.menu_trees import (
        MenuAction,
        MenuNode,
        create_back_action,
        create_pause_action,
    )
    from modes.base_mode import BaseMode


class SniperMouseMode(BaseMode):
    """Precision OS mouse control using a two-step 3x3 fractal grid."""

    mode_id = "sniper"
    display_name = "FREELOOK (RATÓN)"
    theme_color = "#F43F5E"

    ACTION_LEFT = "LEFT_CLICK"
    ACTION_DOUBLE = "DOUBLE_CLICK"
    ACTION_RIGHT = "RIGHT_CLICK"
    ACTION_SCROLL_UP = "SCROLL_UP"
    ACTION_SCROLL_DOWN = "SCROLL_DOWN"
    CONTROL_JOYSTICK = "JOYSTICK"
    CONTROL_MENU_CURSOR = "MENU_CURSOR"
    GAMING_DEADZONE = 0.14
    SNIPER_ACTIONS = (
        ACTION_LEFT,
        ACTION_DOUBLE,
        ACTION_RIGHT,
        ACTION_SCROLL_UP,
        ACTION_SCROLL_DOWN,
    )

    ACTION_LABELS = {
        ACTION_LEFT: "Clic Izq",
        ACTION_DOUBLE: "Doble Clic",
        ACTION_RIGHT: "Clic Der",
        ACTION_SCROLL_UP: "Scroll ↑",
        ACTION_SCROLL_DOWN: "Scroll ↓",
    }

    # Sectors actually exposed in the 3x3 root. Center (4) is PAUSE and
    # bottom-left (6) is BACK, preserving the Golden Rules.
    VISIBLE_SECTORS = (0, 1, 2, 3, 5, 7, 8)

    def __init__(self, language: str = "PYTHON") -> None:
        super().__init__(language)
        self.current_action: str = self.ACTION_LEFT
        self.gaming_control_state: str = self.CONTROL_JOYSTICK
        self.game_profile_name: str = "default_desktop"
        self.edge_scroll_step: int = 8

    # ------------------------------------------------------------------ #
    # Mouse action selector
    # ------------------------------------------------------------------ #
    def set_action(self, action: str) -> str:
        key = str(action).strip().upper()
        aliases = {
            "LEFT": self.ACTION_LEFT,
            "LEFT_CLICK": self.ACTION_LEFT,
            "CLICK": self.ACTION_LEFT,
            "DOUBLE": self.ACTION_DOUBLE,
            "DOUBLE_CLICK": self.ACTION_DOUBLE,
            "RIGHT": self.ACTION_RIGHT,
            "RIGHT_CLICK": self.ACTION_RIGHT,
            "SCROLL": self.ACTION_SCROLL_UP,
            "SCROLL_UP": self.ACTION_SCROLL_UP,
            "SCROLL_DOWN": self.ACTION_SCROLL_DOWN,
        }
        self.current_action = aliases.get(key, self.ACTION_LEFT)
        return self.current_action

    def get_action(self) -> str:
        return self.current_action

    def set_game_profile(self, profile_name: str) -> str:
        self.game_profile_name = str(profile_name or "default_desktop")
        if self.game_profile_name == "strategy_rpg":
            self.gaming_control_state = self.CONTROL_MENU_CURSOR
        elif self.game_profile_name in ("sandbox_3d", "twin_stick_roguelike"):
            self.gaming_control_state = self.CONTROL_JOYSTICK
        return self.game_profile_name

    @property
    def is_twin_stick(self) -> bool:
        return self.game_profile_name == "twin_stick_roguelike"

    @property
    def is_strategy(self) -> bool:
        return self.game_profile_name == "strategy_rpg"

    def set_gaming_control_state(self, state: str) -> str:
        self.gaming_control_state = (
            self.CONTROL_MENU_CURSOR
            if str(state).upper() == self.CONTROL_MENU_CURSOR
            else self.CONTROL_JOYSTICK
        )
        return self.gaming_control_state

    def toggle_gaming_control_state(self) -> str:
        state = (
            self.CONTROL_MENU_CURSOR
            if self.gaming_control_state == self.CONTROL_JOYSTICK
            else self.CONTROL_JOYSTICK
        )
        return self.set_gaming_control_state(state)

    def cycle_action(self) -> str:
        try:
            idx = self.SNIPER_ACTIONS.index(self.current_action)
        except ValueError:
            idx = 0
        self.current_action = self.SNIPER_ACTIONS[(idx + 1) % len(self.SNIPER_ACTIONS)]
        return self.current_action

    @property
    def action_label(self) -> str:
        return self.ACTION_LABELS.get(self.current_action, "Clic Izq")

    # ------------------------------------------------------------------ #
    # Menu contract
    # ------------------------------------------------------------------ #
    def get_root_menu(self, language: Optional[str] = None) -> MenuNode:
        items: List[MenuAction] = []
        sector_slots = {
            0: 1,
            1: 2,
            2: 3,
            3: 4,
            5: 6,
            7: 8,
            8: 9,
        }

        for slot in range(9):
            if slot == 4:
                items.append(create_pause_action("5"))
                continue
            if slot == 6:
                items.append(create_back_action("ROOT", "7"))
                continue

            sector = slot
            position = sector_slots[sector]
            items.append(
                MenuAction(
                    id=f"SNIPER_SECTOR_{sector}",
                    label=f"{position}: Sector {sector + 1}",
                    hint="Mira y abre la boca",
                    action_type="SNIPER_SECTOR",
                    snippet=str(sector),
                    icon="crosshair",
                )
            )

        return MenuNode(
            id="ROOT",
            title="FREELOOK",
            breadcrumb_label="RATÓN",
            items=items,
            parent_id=None,
            sticky=False,
        )

    def get_ai_system_prompt(self, context_data: Optional[Dict[str, Any]] = None) -> str:
        return ""

    def get_heuristic_predictions(
        self, context_data: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        return [""] * 6


# Compatibility alias
SniperMode = SniperMouseMode
