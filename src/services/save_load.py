import os
import json

from pathlib import Path
from core.settings import DIR_UP, DIR_DOWN, DIR_LEFT, DIR_RIGHT
from entities.tank import DefaultBoss
from core.utils import generate_lives_positions
from modes.mode_config import get_mode_class, all_mode_ids
from core.utils import level_to_int
from entities.blocks import PixelBlock

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

def default_completed() -> dict:
    return {mode_id: False for mode_id in all_mode_ids()}

def default_global_save() -> dict:
    # Общие настройки по умолчанию (новый словарь при каждом вызове)
    return {
        "volume": 1.0,
        "scale": 1.0,
        "curtain_style": "RIGHT_TO_LEFT",
        "completed": default_completed(),
        "paint_tank": False,
        "tank_corrupted": False,
        "corrupted_menu_seen": False,
        "tank_restored": False,  # победа над боссом D01: вкладка TANK вернулась
        "font": "DS-DIGI",
        "rgb": [0, 0, 0],
        "custom_tank": {
            "enabled": False,
            "pixels": [
                [1,0], [0,1], [1,1], [2,1], [0,2], [2,2]
            ]
        }
    }

def load_global_save() -> dict:
    path = get_global_save_path()
    default_save = default_global_save()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            return default_save
        if not isinstance(data, dict):
            return default_save
        for k, v in default_save.items():
            if k not in data:
                data[k] = v

        done = data["completed"] if isinstance(data["completed"], dict) else {}
        data["completed"] = {**default_save["completed"], **done}
        return data
    return default_save

def save_global_save(data:dict) -> None:
    path = get_global_save_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def random_tank_color(step: int = 15) -> list:
    # Случайный яркий цвет танка (не чёрный и не тёмный)
    import colorsys
    import random
    r, g, b = colorsys.hsv_to_rgb(random.random(), random.uniform(0.6, 1.0), random.uniform(0.7, 1.0))
    return [min(255, int(round(c * 255 / step)) * step) for c in (r, g, b)]

def grant_tank_reward(g_save: dict) -> bool:
    # Награда за победу над боссом D01 (один раз)
    if g_save.get("tank_restored", False):
        return False
    g_save["tank_restored"] = True
    g_save["rgb"] = random_tank_color()
    g_save["paint_tank"] = True
    custom = g_save.setdefault("custom_tank", {"enabled": False, "pixels": []})
    custom["enabled"] = True  # без кастомного танка краска не применяется
    if not custom.get("pixels"):
        custom["pixels"] = [[1, 0], [0, 1], [1, 1], [2, 1], [0, 2], [2, 2]]
    return True

def mark_mode_completed(mode_id, g_save: dict = None) -> None:
    # g_save - живые настройки из памяти, чтобы следующая запись их не затёрла
    data = g_save if g_save is not None else load_global_save()
    data.setdefault("completed", {})[str(mode_id)] = True
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
            for e in enemy_manager.enemies_group if not getattr(e, "is_boss", False)
        ],
        "blocks": [{"grid_x": b.grid_x, "grid_y": b.grid_y} for b in game_state["blocks"]],
        "stats": {
            "lives": game_state.get("lives", 4),
            "score": game_state.get("score", 0),
            "level": game_state.get("level", 1),
            "level_number": game_state.get("level_number", level_to_int(game_state.get("level"), 1)),
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
            if getattr(sprite, "is_boss", False):
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
    
    # Случайная карта режима (если режим просит её сохранять: self.save_map)
    logic = game_state.get("logic_mode")
    if logic and getattr(logic, "save_map", False) and hasattr(logic, "export_map"):
        map_data = logic.export_map()
        if map_data:
            data["map"] = map_data

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

_probe_cache = {}

def _probe_mode(mode_class):
    # Экземпляр режима "вхолостую" - меню узнаёт его настройки
    if mode_class in _probe_cache:
        return _probe_cache[mode_class]
    from core import settings
    saved = (list(settings.PLAYER_SPAWN_POINTS), list(settings.ENEMY_SPAWN_POINTS))
    try:
        probe = mode_class({"level": 1, "lives": 4})
    except Exception:
        probe = None
    finally:
        settings.PLAYER_SPAWN_POINTS[:] = saved[0]
        settings.ENEMY_SPAWN_POINTS[:] = saved[1]
    _probe_cache[mode_class] = probe
    return probe

def _probe_level_label(mode_class):
    probe = _probe_mode(mode_class)
    return getattr(probe, "level_label", None)

def _probe_start_lives(mode_class) -> int:
    probe = _probe_mode(mode_class)
    return int(getattr(probe, "start_lives", 4))

def get_menu_stats(mode, slot):
    data = load_game(mode, slot)
    hi_score = load_hi_score(mode)
    mode_class = get_mode_class(mode)
    mode_target = getattr(mode_class, 'TARGET_KILLS', 0)
    mode_label = _probe_level_label(mode_class)
    mode_lives = _probe_start_lives(mode_class)
    mode_level = mode_label or 1

    stats = {
        "score": 0, 
        "hi_score": hi_score, 
        "kills_this_level": 0,
        "global_kills": 0,
        "target_enemies": mode_target,
        "level": mode_level,
        "speed_multiplier": 1.0,
        "lives": mode_lives, 
        "lives_positions": generate_lives_positions(mode_lives)
    }

    if data and "stats" in data:
        s = data.get("stats", {})
        lives = s.get("lives", mode_lives)
        
        is_boss = s.get("is_boss_phase", False) or ("boss" in data)
        boss_data = data.get("boss", {})
        boss_hp = boss_data.get("hp", 0)
        boss_max_hp = boss_data.get("max_hp", boss_hp)

        stats.update({
            "score": s.get("score", 0),
            "kills_this_level": s.get("kills_this_level", 0),
            "global_kills": s.get("global_kills", 0),
            "target_enemies": s.get("target", mode_target),
            "level": mode_label or s.get("level", mode_level),
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
    mode_target = getattr(mode_class, 'TARGET_KILLS', 0)
    mode_label = _probe_level_label(mode_class)
    mode_lives = _probe_start_lives(mode_class)
    mode_level = mode_label or 1
    
    best_stats = {
        "score": 0, 
        "hi_score": hi_score, 
        "kills_this_level": 0,
        "global_kills": 0,
        "target_enemies": mode_target, 
        "level": mode_level,
        "speed_multiplier": 1.0,
        "lives": mode_lives,
        "lives_positions": generate_lives_positions(mode_lives)
    }

    best_score = -1

    for slot in range(1, 4):
        data = load_game(mode, slot)
        if data and "stats" in data:
            s = data["stats"]
            current_score = s.get("score", 0)
            if current_score > best_score:
                best_score = current_score
                lives = s.get("lives", mode_lives)
                
                is_boss = s.get("is_boss_phase", False) or ("boss" in data)
                boss_data = data.get("boss", {})
                boss_hp = boss_data.get("hp", 0)
                boss_max_hp = boss_data.get("max_hp", boss_hp)
                
                best_stats.update({
                    "score": current_score,
                    "kills_this_level": s.get("kills_this_level", 0),
                    "global_kills": s.get("global_kills", 0),
                    "target_enemies": s.get("target", mode_target), 
                    "level": mode_label or s.get("level", mode_level),
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

    # Сохранённая карта возвращается
    logic = state.get("logic_mode")
    if logic and "map" in data and getattr(logic, "save_map", False) and hasattr(logic, "import_map"):
        logic.import_map(data["map"])

    if "boss" in data:
        b_data = data["boss"]
        boss_hp = b_data["hp"]
        boss_max_hp = b_data.get("max_hp", boss_hp)
        if not boss_max_hp or boss_max_hp <= 0:
            boss_max_hp = boss_hp
        
        if state.get("logic_mode"):
            boss = state["logic_mode"].make_boss(b_data["grid_x"], b_data["grid_y"], boss_hp, boss_max_hp)
        else:
            boss = DefaultBoss(b_data["grid_x"], b_data["grid_y"], hp=boss_hp, max_hp=boss_max_hp)
        state["enemies"].add(boss)
        state["all_sprites"].add(boss)
        if state.get("logic_mode"):
            state["logic_mode"].boss = boss
            if getattr(state["logic_mode"], "lock_player_in_boss", True):
                player.fixed_direction = DIR_UP

def calculate_speed(stats):
    return 1.0 + stats.get("extra_speed", 0.0)