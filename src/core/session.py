# Создание игровой сессии (состояния игры) и загрузка слота


import pygame
import random

from core import assets
from core import settings
from core.utils import generate_lives_positions
from entities.enemy_manager import EnemyManager
from entities.tank.player import PlayerTank
from modes.mode_config import get_mode_class
from services import save_load
from services.save_load import load_game, load_hi_score


def get_difficulty_params(game_state):
    if not game_state:
        return 4, 1.0, 1000

    max_enemies = 4
    speed_multiplier = 1.0
    spawn_delay = 1000

    if game_state.get("logic_mode"):
        mode = game_state["logic_mode"]
        speed_multiplier = 1.0 + mode.extra_speed
        max_enemies, spawn_delay = mode.modify_spawn_params(max_enemies, spawn_delay)
        
    return max_enemies, speed_multiplier, spawn_delay

def create_new_game(mode, slot, previous_data = None):
    all_sprites = pygame.sprite.Group()
    bullets = pygame.sprite.Group()
    enemies = pygame.sprite.Group()
    blocks = pygame.sprite.Group()

    state = {
        "mode": mode,
        "slot": slot,
        "all_sprites": all_sprites,
        "bullets": bullets,
        "enemies": enemies,
        "blocks": blocks,
        "logic_mode": None,
        "paused": False,
        "sounds_enabled": True,
        "lives": 4,
        "score": 0,
        "level": 1,
        "target_enemies": 10,
        "kills_this_level": 0,
        "global_kills": 0,
        "hi_score": load_hi_score(mode),
        "lives_positions": generate_lives_positions(4)
    }

    mode_class = get_mode_class(mode)
    logic_mode = mode_class(state)

    state["logic_mode"] = logic_mode
    state["target_enemies"] = state["logic_mode"].target_kills
    # Стартовые жизни задаёт режим (self.start_lives)
    state["lives"] = max(1, int(getattr(logic_mode, "start_lives", 4)))
    state["lives_positions"] = generate_lives_positions(state["lives"])

    if getattr(logic_mode, "is_random_map", False) and getattr(logic_mode, "player_spawn_point", None) is not None:
        px, py = logic_mode.player_spawn_point
    else:
        px, py = random.choice(settings.PLAYER_SPAWN_POINTS)
        
    if getattr(logic_mode, "is_random_map", False) and hasattr(logic_mode, "enemy_spawn_points"):
        settings.set_enemy_spawn_points(logic_mode.enemy_spawn_points)

    player = PlayerTank(px, py, assets.PLAYER_BASE_IMG)
    all_sprites.add(player)
    
    state["player"] = player
    enemy_params = getattr(logic_mode, "enemy_params", {})
    enemy_manager = EnemyManager(assets.enemy_image(getattr(logic_mode, "enemy_skin", None)), enemies, all_sprites, player,
                                 enemy_params=enemy_params)
    enemy_manager.bullet_color = getattr(logic_mode, "enemy_bullet_color", None)
    state["enemy_manager"] = enemy_manager

    if previous_data:
        stats = previous_data.get("stats", {})
        state["lives"] = stats.get("lives", 4)
        state["score"] = stats.get("score", 0)
        state["level"] = stats.get("level", 1)
        state["target_enemies"] = stats.get("target", 10)
        state["kills_this_level"] = stats.get("kills_this_level", 0)
        state["global_kills"] = stats.get("global_kills", 0)
        state["lives_positions"] = generate_lives_positions(state["lives"])
        if "level_number" in stats:
            state["level_number"] = stats["level_number"]

    # Номер уровня (число) и настройки этого уровня: вид HUD, размер поля
    logic_mode.restore_level()
    logic_mode.configure_level()

    return state

def load_game_slot(mode, slot):
    data = load_game(mode, slot)
    state = create_new_game(mode, slot, data)

    if data is None:
        return state

    save_load.load_game_into_slot(state, data) 
    return state
