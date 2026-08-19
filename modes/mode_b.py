from modes.base_mode import BaseMode
from modes.mode_a import ModeA02

import random
import settings
import json
from settings import BOARD_WIDTH, BOARD_HEIGHT, DIR_UP, DIR_LEFT, DIR_RIGHT
from blocks import spawn_blocks
from save_load import save_game, load_game
from tank import DefaultBoss

class ModeB01(BaseMode):
    TARGET_KILLS:int = 20
    def __init__(self, game_state) -> None:
        super().__init__(game_state)
        self.mode_id = "B01"
        self.target_kills = self.TARGET_KILLS
        self.max_levels = 10

    def setup_level(self, is_new_level=False) -> None:
        player = self.state["player"]
        player.grid_x, player.grid_y = random.choice(settings.PLAYER_SPAWN_POINTS)
        player.update_position()
        
        if is_new_level or not self.blocks_generated:
            for b in self.state["blocks"]:
                b.kill()
            
            target_clusters = random.randint(2, 5) # От 2 до 5 кластеров
            spawn_blocks(self.state, BOARD_WIDTH, BOARD_HEIGHT, target_clusters)
            self.blocks_generated = True

    def modify_spawn_params(self, max_enemies, spawn_delay):
        computed_max = min(4, self.state["level"])
        return computed_max, spawn_delay

    def check_conditions(self):
        if self.state["kills_this_level"] >= self.target_kills:
            self.state["level"] += 1
            self.state["kills_this_level"] = 0
            
            # Увеличение скорости за каждый пройденный уровень
            self.extra_speed += round(random.uniform(0.1, 0.3), 1)
            
            if self.state["level"] > self.max_levels:
                return "WIN_SCREEN"
            return "NEXT_LEVEL"
        return None


# ==========================================
# РЕЖИМ B - 02
# ==========================================
class ModeB02(ModeA02):
    TARGET_KILLS:int = 15
    def __init__(self, game_state) -> None:
        super().__init__(game_state)
        self.mode_id = "B02"
        self.target_kills = self.TARGET_KILLS
        self.next_speed_threshold = 10

    def apply_spawns(self) -> None:
        super().apply_spawns()
        settings.PLAYER_SPAWN_POINTS.extend([
            (BOARD_WIDTH // 2 - 2, BOARD_HEIGHT // 2 - 2),
            (BOARD_WIDTH // 2 + 2, BOARD_HEIGHT // 2 + 2),
            (BOARD_WIDTH // 2 - 2, BOARD_HEIGHT // 2 + 2),
            (BOARD_WIDTH // 2 + 2, BOARD_HEIGHT // 2 - 2),
        ])
        settings.ENEMY_SPAWN_POINTS.extend([
            (3, 3), (BOARD_WIDTH - 4, 3),
            (3, BOARD_HEIGHT - 4), (BOARD_WIDTH - 4, BOARD_HEIGHT - 4)
        ])

    def setup_level(self, is_new_level = False) -> None:
        if getattr(self, 'is_boss_phase', False):
            return 

        super().setup_level(is_new_level)
        self.next_speed_threshold = 10 

        if is_new_level or not getattr(self, "blocks_generated", False):
            for b in self.state["blocks"]:
                b.kill()

            current_level = self.state["level"]
            target_clusters = int(min(current_level * 1.2, 8))

            if current_level == 6:
                target_clusters = 0

            spawn_blocks(self.state, BOARD_WIDTH, BOARD_HEIGHT, num_clusters=target_clusters)
            self.blocks_generated = True

    def modify_spawn_params(self, max_enemies, spawn_delay):
        if self.is_boss_phase:
            return 0, spawn_delay
        return min(4, self.state["level"]), 750

    def check_conditions(self):
        if not self.is_boss_phase:
            if self.state["kills_this_level"] >= self.next_speed_threshold and self.next_speed_threshold < self.target_kills:
                self.extra_speed += round(random.uniform(0.1, 0.2), 1)
                self.next_speed_threshold += 10

            if self.state["kills_this_level"] >= self.target_kills:
                self.state["level"] += 1
                self.state["kills_this_level"] = 0
                self.next_speed_threshold = 10
                
                if self.state["level"] > 5:
                    self.start_boss_phase()
                    return "BOSS_PHASE_START"
                return "NEXT_LEVEL"
        else:
            if self.boss.hp <= 0:
                return "WIN_SCREEN"
        return None

    def start_boss_phase(self) -> None:
        super().start_boss_phase()