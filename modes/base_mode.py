import settings
from settings import BOARD_WIDTH, BOARD_HEIGHT

class BaseMode:
    def __init__(self, game_state) -> None:
        self.state = game_state
        self.mode_id = "Q99"

        self.enhanced_bullet_collision = False
        self.blocks_generated = False
        self.target_kills = 50
        self.extra_speed = 0.0

        self.is_boss_phase = False
        self.boss_bonus_given = False
        self.boss = None

        self.apply_spawns()
    
    def apply_spawns(self) -> None:
        settings.PLAYER_SPAWN_POINTS.clear()
        settings.PLAYER_SPAWN_POINTS.append((BOARD_WIDTH // 2, BOARD_HEIGHT // 2))

        settings.ENEMY_SPAWN_POINTS.clear()
        settings.ENEMY_SPAWN_POINTS.extend([
            (1, 1), (BOARD_WIDTH - 2, 1),
            (1, BOARD_HEIGHT - 2), (BOARD_WIDTH - 2, BOARD_HEIGHT - 2)
        ])

    def setup_level(self, is_new_level = False) -> None:
        if is_new_level:
            self.blocks_generated = False
            self.boss_bonus_given = False

    def check_conditions(self) -> str:
        return None

    def restrict_player_keys(self, event_key) -> bool:
        return True

    def get_custom_hud_goal(self) -> None:
        return None

    def modify_spawn_params(self, max_enemies, spawn_delay):
        return max_enemies, spawn_delay