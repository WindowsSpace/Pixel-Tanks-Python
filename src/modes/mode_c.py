from modes.base_mode import BaseMode
from modes.mode_a import ModeA02

import random
from core import settings
import json
from core.settings import BOARD_WIDTH, BOARD_HEIGHT, DIR_UP, DIR_LEFT, DIR_RIGHT
from entities.blocks import spawn_blocks
from services.save_load import save_game, load_game
from entities.tank import DefaultBoss

class ModeC01(BaseMode):
    TARGET_KILLS:int = 20
    def __init__(self, game_state) -> None:
        super().__init__(game_state)
        self.mode_id = "C01"
        self.target_kills = self.TARGET_KILLS
        self.max_levels = 10
        self.restore_blocks_on_respawn = True

    def setup_level(self, is_new_level=False) -> None:
        player = self.state["player"]
        player.grid_x, player.grid_y = random.choice(settings.PLAYER_SPAWN_POINTS)
        player.update_position()
        
        if is_new_level or not self.blocks_generated:
            for b in list(self.state["blocks"]):
                b.kill()
            
            target_clusters = random.randint(1, 3)
            spawn_blocks(self.state, self.bw, self.bh, self.scale_clusters(target_clusters))
            self.blocks_generated = True
            self.save_block_snapshot()

        elif getattr(self, "restore_blocks_on_respawn", False):
            self.restore_block_snapshot()

    def modify_spawn_params(self, max_enemies, spawn_delay):
        computed_max = min(4, self.level_number)
        return computed_max, random.randint(1000, 1500)

    def check_conditions(self):
        if self.state["kills_this_level"] >= self.target_kills:
            self.advance_level()
            self.state["kills_this_level"] = 0

            self.extra_speed += 0.1
            
            if self.level_number > self.max_levels:
                return "WIN_SCREEN"
            return "NEXT_LEVEL"
        return None

class ModeC02(ModeA02):
    TARGET_KILLS:int = 15
    def __init__(self, game_state) -> None:
        super().__init__(game_state)
        self.mode_id = "C02"
        self.target_kills = self.TARGET_KILLS
        self.next_speed_threshold = 10
        self.restore_blocks_on_respawn = True

    def apply_spawns(self) -> None:
        super().apply_spawns()
        settings.PLAYER_SPAWN_POINTS.extend([
            (self.bw // 2 - 2, self.bh // 2 - 2),
            (self.bw // 2 + 2, self.bh // 2 + 2),
            (self.bw // 2 - 2, self.bh // 2 + 2),
            (self.bw // 2 + 2, self.bh // 2 - 2),
        ])
        settings.ENEMY_SPAWN_POINTS.extend([
            (3, 3), (self.bw - 4, 3),
            (3, self.bh - 4), (self.bw - 4, self.bh - 4)
        ])

    def setup_level(self, is_new_level = False) -> None:
        if getattr(self, 'is_boss_phase', False):
            return 

        super().setup_level(is_new_level)

        if is_new_level or not getattr(self, "blocks_generated", False):
            for b in list(self.state["blocks"]):
                b.kill()

            current_level = self.level_number
            target_clusters = random.randint(1, 6)

            if current_level == 6:
                target_clusters = 0

            spawn_blocks(self.state, self.bw, self.bh, num_clusters=self.scale_clusters(target_clusters))
            self.blocks_generated = True
            self.save_block_snapshot()

        elif getattr(self, "restore_blocks_on_respawn", False):
            self.restore_block_snapshot()

    def modify_spawn_params(self, max_enemies, spawn_delay):
        if self.is_boss_phase:
            return 0, spawn_delay
        return min(4, self.level_number), random.randint(1000, 1500)

    def check_conditions(self):
        if not self.is_boss_phase:
            if self.state["kills_this_level"] >= self.next_speed_threshold and self.next_speed_threshold < self.target_kills:
                self.extra_speed += 0.1
                self.next_speed_threshold += 10

            if self.state["kills_this_level"] >= self.target_kills:
                self.advance_level()
                self.state["kills_this_level"] = 0
                self.next_speed_threshold = 10
                
                if self.level_number > 5:
                    self.start_boss_phase()
                    return "BOSS_PHASE_START"
                return "NEXT_LEVEL"
        else:
            if self.boss.hp <= 0:
                return "WIN_SCREEN"
        return None

    def start_boss_phase(self) -> None:
        super().start_boss_phase()