import json
import os
from pathlib import Path

from settings import DIR_UP, DIR_DOWN, DIR_LEFT, DIR_RIGHT

SAVE_DIR = Path("saves")
SAVE_DIR.mkdir(exist_ok=True)

DIRECTION_TO_NAME = {
    DIR_UP: "up",
    DIR_DOWN: "down",
    DIR_LEFT: "left",
    DIR_RIGHT: "right",
}

NAME_TO_DIRECTION = {v: k for k, v in DIRECTION_TO_NAME.items()}


def save_game(slot, player, enemy_manager):
    # Сохраняет игру в указанный слот (1..3)
    data = {
        "player": {
            "grid_x": player.grid_x,
            "grid_y": player.grid_y,
            "direction": DIRECTION_TO_NAME[player.direction],
        },
        "enemies": [
            {
                "grid_x": e.grid_x,
                "grid_y": e.grid_y,
                "direction": DIRECTION_TO_NAME[e.direction],
            }
            for e in enemy_manager.enemies_group
        ],
        "total_spawned": enemy_manager.total_spawned,
        "total_destroyed": enemy_manager.total_destroyed,
    }

    filepath = SAVE_DIR / f"slot_{slot}.json"
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_game(slot):
    # Загружает данные слота
    filepath = SAVE_DIR / f"slot_{slot}.json"
    if not filepath.exists():
        return None
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)
