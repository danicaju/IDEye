"""Dynamic game/application control profiles backed by game_profiles.json."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional


DEFAULT_PROFILES: Dict[str, Dict[str, Any]] = {
    "sandbox_3d": {
        "label": "Sandbox 3D",
        "games": ["minecraft", "roblox", "terraria", "fortnite", "gta", "red dead", "witcher", "skyrim", "fallout"],
        "movement": "head_joystick",
        "jump": "wink_left",
        "menu": "wink_right",
        "primary": "mouth_click",
        "aim": "gaze_cursor",
        "directions": 8,
        "edge_scroll_px": 0,
    },
    "twin_stick_roguelike": {
        "label": "Twin-Stick / Roguelike",
        "games": ["isaac", "gungeon", "hades", "dead cells", "deadcells", "vampire survivors", "risk of rain", "roguelike", "rogue"],
        "movement": "head_tilt",
        "jump": "wink_left",
        "menu": "wink_right",
        "primary": "mouth_click",
        "aim": "gaze",
        "directions": 8,
        "edge_scroll_px": 0,
    },
    "strategy_rpg": {
        "label": "Estrategia / RPG",
        "games": ["baldur", "civilization", "civ ", "xcom", "total war", "age of empires", "stellaris", "crusader kings", "divinity", "pillars of eternity", "rpg"],
        "movement": "edge_scroll",
        "jump": None,
        "menu": "wink_right",
        "primary": "jaw_lock",
        "aim": "gaze_cursor",
        "directions": 4,
        "edge_scroll_px": 20,
    },
    "default_desktop": {
        "label": "Escritorio",
        "games": [],
        "movement": "direct_pointer",
        "jump": None,
        "menu": "wink_right",
        "primary": "mouth_click",
        "aim": "gaze_cursor",
        "directions": 4,
        "edge_scroll_px": 20,
    },
}


def default_profiles_path() -> Path:
    root = Path(__file__).resolve().parent.parent.parent
    return root / "game_profiles.json"


class GameProfileManager:
    """Loads/saves profile mappings and resolves the active window profile."""

    def __init__(self, path: Optional[str] = None, auto_load: bool = True) -> None:
        self.path = Path(path) if path else default_profiles_path()
        self.profiles: Dict[str, Dict[str, Any]] = {}
        self.active_profile: str = "default_desktop"
        if auto_load:
            self.load()

    def load(self) -> Dict[str, Dict[str, Any]]:
        self.profiles = {name: dict(data) for name, data in DEFAULT_PROFILES.items()}
        try:
            if self.path.is_file():
                raw = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    for name, data in raw.items():
                        if isinstance(data, dict):
                            self.profiles[str(name)] = {**self.profiles.get(str(name), {}), **data}
            else:
                self.save()
        except Exception:
            pass
        return self.get_profiles()

    def save(self) -> bool:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = str(self.path) + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(self.profiles, fh, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)
            return True
        except Exception:
            return False

    def get_profiles(self) -> Dict[str, Dict[str, Any]]:
        return {name: dict(data) for name, data in self.profiles.items()}

    def get_profile(self, name: str) -> Dict[str, Any]:
        return dict(self.profiles.get(str(name), self.profiles.get("default_desktop", {})))

    def set_active(self, name: str) -> Dict[str, Any]:
        self.active_profile = str(name) if str(name) in self.profiles else "default_desktop"
        return self.get_profile(self.active_profile)

    def resolve_for_window(self, title: str, process_name: str) -> str:
        title_l = str(title or "").lower()
        process = os.path.basename(str(process_name or "")).lower()
        for name in ("twin_stick_roguelike", "strategy_rpg", "sandbox_3d"):
            data = self.profiles.get(name, {})
            for game in data.get("games", []):
                needle = str(game).lower().strip()
                if needle and (needle in title_l or needle in process):
                    self.set_active(name)
                    return name
        self.set_active("default_desktop")
        return "default_desktop"

    def active_label(self) -> str:
        return str(self.get_profile(self.active_profile).get("label", self.active_profile))
