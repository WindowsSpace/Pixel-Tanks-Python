import os
import json

from pathlib import Path
from settings import DIR_UP, DIR_DOWN, DIR_LEFT, DIR_RIGHT
from tank import DefaultBoss
from utils import generate_lives_positions
from modes.mode_config import get_mode_class
from blocks import PixelBlock

LOCAL_SAVE = False
BASE_DIR = None

def save_path(local = False) -> Path:
    global BASE_DIR
    if not local:
        appdata_route = os.environ.get("APPDATA")
        if appdata_route:
            BASE_DIR = Path(appdata_route) / "Pixel Tanks"
        else:
            BASE_DIR = Path.home() / ".pixel_tanks"
        BASE_DIR.mkdir(parents = True, exist_ok=  True)
    else:
        BASE_DIR = Path("saves")
        BASE_DIR.mkdir(exist_ok = True)
    return BASE_DIR

save_path(LOCAL_SAVE)

DIRECTION_TO_NAME = {DIR_UP: "up", DIR_DOWN: "down", DIR_LEFT: "left", DIR_RIGHT: "right"}
NAME_TO_DIRECTION = {v: k for k, v in DIRECTION_TO_NAME.items()}

def get_mode_directory(mode_id) -> str:
    mode_str = str(mode_id)

    if len(mode_str) >= 2 and mode_str[0].isalpha() and mode_str[1:].isdigit():
        group_folder = mode_str[0].upper()
        sub_folder = mode_str[1:]
        mode_dir = os.path.join(BASE_DIR, group_folder, sub_folder)
    else:
        mode_dir = os.path.join(BASE_DIR, mode_str)
        
    os.makedirs(mode_dir, exist_ok=True)
    return mode_dir

def get_global_save_path() -> str:
    return os.path.join(BASE_DIR, "settings.json")

def load_global_save() -> dict:
    path = get_global_save_path()
    default_save = {
        "volume": 1.0,
        "curtain_style": "RIGHT_TO_LEFT",
        "completed": {
            "A01": False, "A02": False, 
            "B01": False, "B02": False,
            "C01": False,
            "D01": False, "D02": False
        },
        "paint_tank": False,
        "font": "DS-DIGI",
        "rgb": [0, 0, 0],
        "custom_tank": {
            "enabled": False,
            "pixels": [
                [1,0], [0,1], [1,1], [2,1], [0,2], [2,2]
            ]
        }
    }
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for k, v in default_save.items():
                    if k not in data:
                        data[k] = v
                if "custom_tank" not in data:
                    data["custom_tank"] = default_save["custom_tank"]
                return data
        except:
            pass
    return default_save

def save_global_save(data:dict) -> None:
    path = get_global_save_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def mark_mode_completed(mode_id:str) -> None:
    data = load_global_save()
    if mode_id in data.get("completed", {}): 
        data["completed"][mode_id] = True
        save_global_save(data)

def get_save_path(mode_id, slot:int) -> str:
    mode_dir = get_mode_directory(mode_id)
    return os.path.join(mode_dir, f"save {slot}.json")

def get_hi_score_path(mode_id) -> str:
    mode_dir = get_mode_directory(mode_id)
    return os.path.join(mode_dir, "high score.json")

def load_hi_score(mode=1):
    path = get_hi_score_path(mode)
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                return json.load(f).get("hi_score", 0)
        except:
            pass
    return 0

def save_hi_score(mode, score) -> None:
    path = get_hi_score_path(mode)
    current_hi = load_hi_score(mode)
    
    if score > current_hi:
        with open(path, "w") as f:
            json.dump({"hi_score": score}, f)

def save_game(mode, slot, player, enemy_manager, game_state) -> None:
    path = get_save_path(mode, slot)

    data = {
        "mode": mode,
        "slot": slot,
        "player": {
            "grid_x": player.grid_x, "grid_y": player.grid_y,
            "direction": DIRECTION_TO_NAME.get(player.direction, "up"),
        },
        "enemies": [
            {
                "grid_x": e.grid_x, 
                "grid_y": e.grid_y, 
                "direction": DIRECTION_TO_NAME.get(getattr(e, 'direction', DIR_DOWN), "down")
            }
            for e in enemy_manager.enemies_group if not isinstance(e, DefaultBoss)
        ],
        "blocks": [{"grid_x": b.grid_x, "grid_y": b.grid_y} for b in game_state["blocks"]],
        "stats": {
            "lives": game_state.get("lives", 4),
            "score": game_state.get("score", 0),
            "level": game_state.get("level", 1),
            "target": game_state.get("target_enemies", 50),
            "kills_this_level": game_state.get("kills_this_level", 0),
            "global_kills": game_state.get("global_kills", 0)
        }
    }

    boss = None
    if game_state.get("logic_mode") and getattr(game_state["logic_mode"], "boss", None):
        boss = game_state["logic_mode"].boss
    if not boss:
        for sprite in game_state.get("enemies", []):
            if sprite.__class__.__name__ == "DefaultBoss":
                boss = sprite
                break

    if boss and boss.alive(): 
        data["boss"] = {
            "grid_x": boss.grid_x,
            "grid_y": boss.grid_y,
            "hp": boss.hp,
            "max_hp": getattr(boss, "max_hp", boss.hp),
            "direction": DIRECTION_TO_NAME.get(boss.direction, "down")
        }
    
    if game_state.get("logic_mode"):
        logic = game_state["logic_mode"]
        data["stats"]["extra_speed"] = getattr(logic, "extra_speed", 0.0)
        data["stats"]["is_boss_phase"] = getattr(logic, "is_boss_phase", False)
        data["stats"]["blocks_generated"] = getattr(logic, "blocks_generated", True)
        data["stats"]["boss_bonus_given"] = getattr(logic, "boss_bonus_given", False)
        if hasattr(logic, "next_speed_threshold"):
            data["stats"]["next_speed_threshold"] = logic.next_speed_threshold
    
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_game(mode, slot):
    path = get_save_path(mode, slot)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return None

def delete_save(mode, slot) -> None:
    path = get_save_path(mode, slot)
    if os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass

def get_menu_stats(mode, slot):
    data = load_game(mode, slot)
    hi_score = load_hi_score(mode)
    mode_class = get_mode_class(mode)
    mode_target = getattr(mode_class, 'TARGET_KILLS', 0) if mode_class else 0

    stats = {
        "score": 0, 
        "hi_score": hi_score, 
        "kills_this_level": 0,
        "global_kills": 0,
        "target_enemies": mode_target,
        "level": "ENDLESS" if mode == "C01" else 1,
        "speed_multiplier": 1.0,
        "lives": 4, 
        "lives_positions": generate_lives_positions(4)
    }

    if data and "stats" in data:
        s = data.get("stats", {})
        lives = s.get("lives", 4)
        
        is_boss = s.get("is_boss_phase", False) or ("boss" in data)
        boss_data = data.get("boss", {})
        boss_hp = boss_data.get("hp", 0)
        boss_max_hp = boss_data.get("max_hp", boss_hp)

        stats.update({
            "score": s.get("score", 0),
            "kills_this_level": s.get("kills_this_level", 0),
            "global_kills": s.get("global_kills", 0),
            "target_enemies": s.get("target", mode_target),
            "level": s.get("level", 1),
            "speed_multiplier": calculate_speed(stats=s),
            "lives": lives,
            "lives_positions": generate_lives_positions(lives),
            "is_boss_phase": is_boss,
            "boss_hp": boss_hp,
            "boss_max_hp": boss_max_hp
        })

    return stats

def get_best_mode_stats(mode):
    hi_score = load_hi_score(mode)
    mode_class = get_mode_class(mode)
    mode_target = getattr(mode_class, 'TARGET_KILLS', 0) if mode_class else 0
    
    best_stats = {
        "score": 0, 
        "hi_score": hi_score, 
        "kills_this_level": 0,
        "global_kills": 0,
        "target_enemies": mode_target, 
        "level": "ENDLESS" if mode == "C01" else 1,
        "speed_multiplier": 1.0,
        "lives": 4,
        "lives_positions": generate_lives_positions(4)
    }

    best_score = -1

    for slot in range(1, 4):
        data = load_game(mode, slot)
        if data and "stats" in data:
            s = data["stats"]
            current_score = s.get("score", 0)
            if current_score > best_score:
                best_score = current_score
                lives = s.get("lives", 4)
                
                is_boss = s.get("is_boss_phase", False) or ("boss" in data)
                boss_data = data.get("boss", {})
                boss_hp = boss_data.get("hp", 0)
                boss_max_hp = boss_data.get("max_hp", boss_hp)
                
                best_stats.update({
                    "score": current_score,
                    "kills_this_level": s.get("kills_this_level", 0),
                    "global_kills": s.get("global_kills", 0),
                    "target_enemies": s.get("target", mode_target), 
                    "level": s.get("level", 1),
                    "speed_multiplier": calculate_speed(stats = s),
                    "lives": lives,
                    "lives_positions": generate_lives_positions(lives),
                    "is_boss_phase": is_boss,
                    "boss_hp": boss_hp,
                    "boss_max_hp": boss_max_hp
                })

    if best_score == -1:
        best_stats["score"] = 0
        
    return best_stats

def load_game_into_slot(state, data) -> None:
    player = state["player"]
    player.grid_x = data["player"]["grid_x"]
    player.grid_y = data["player"]["grid_y"]
    player.set_direction(NAME_TO_DIRECTION.get(data["player"].get("direction", "up"), NAME_TO_DIRECTION["up"]))
    player.update_position()

    if "blocks" in data:
        for b_data in data["blocks"]:
            block = PixelBlock(b_data["grid_x"], b_data["grid_y"])
            state["blocks"].add(block)
            state["all_sprites"].add(block)
    
    if state.get("logic_mode") and "stats" in data:
        logic = state["logic_mode"]
        logic.extra_speed = data["stats"].get("extra_speed", 0.0)
        logic.is_boss_phase = data["stats"].get("is_boss_phase", False)
        logic.blocks_generated = data["stats"].get("blocks_generated", True)
        logic.boss_bonus_given = data["stats"].get("boss_bonus_given", False)
        if "next_speed_threshold" in data["stats"]:
            logic.next_speed_threshold = data["stats"]["next_speed_threshold"]

    if "boss" in data:
        b_data = data["boss"]
        boss_hp = b_data["hp"]
        boss_max_hp = b_data.get("max_hp", boss_hp)
        if not boss_max_hp or boss_max_hp <= 0:
            boss_max_hp = boss_hp
        
        boss = DefaultBoss(b_data["grid_x"], b_data["grid_y"], hp=boss_hp, max_hp=boss_max_hp)
        state["enemies"].add(boss)
        state["all_sprites"].add(boss)
        if state.get("logic_mode"):
            state["logic_mode"].boss = boss
            player.fixed_direction = DIR_UP

def calculate_speed(stats):
    return 1.0 + stats.get("extra_speed", 0.0)
