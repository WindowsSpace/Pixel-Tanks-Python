from modes.base_mode import BaseMode

import random
import settings
import json
from settings import BOARD_WIDTH, BOARD_HEIGHT, DIR_UP, DIR_LEFT, DIR_RIGHT
from blocks import spawn_blocks
from save_load import save_game, load_game
from tank import DefaultBoss

class ModeC01(BaseMode):
    TARGET_KILLS:int = 50
    def __init__(self, game_state) -> None:
        super().__init__(game_state)
        self.mode_id = "C01"
        self.state["level"] = "ENDLESS"
        self.target_kills = self.TARGET_KILLS

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
        if is_new_level:
            self.blocks_generated = False
            self.boss_bonus_given = False
            self.is_boss_phase = False
            self.state["player"].fixed_direction = None
            self.enhanced_bullet_collision = False
        elif not getattr(self, 'is_boss_phase', False):
            self.is_boss_phase = False
            self.state["player"].fixed_direction = None
            self.enhanced_bullet_collision = False

        if is_new_level or not getattr(self, "blocks_generated", False):
            for b in self.state["blocks"]:
                b.kill()
            if self.extra_speed > 0:
                target_clusters = min(8, int(round(self.extra_speed * 10)))
                spawn_blocks(self.state, settings.BOARD_WIDTH, settings.BOARD_HEIGHT, num_clusters=target_clusters)
            self.blocks_generated = True

    def modify_spawn_params(self, max_enemies, spawn_delay):
        if self.is_boss_phase:
            return 0, spawn_delay
        computed_max = min(5, 1 + (self.state["kills_this_level"] // 10))
        return computed_max, spawn_delay

    def check_conditions(self):
        if not self.is_boss_phase:
            if self.state["kills_this_level"] >= self.target_kills:
                self.start_boss_phase()
                return "BOSS_PHASE_START"
        else:
            if self.boss.hp <= 0:
                self.extra_speed += 0.1
                self.state["kills_this_level"] = 0
                self.boss = None
                return "NEXT_LEVEL"
        return None

    def start_boss_phase(self) -> None:
        self.enhanced_bullet_collision = self.is_boss_phase = True
        player = self.state["player"]
        player.grid_x, player.grid_y = settings.BOARD_WIDTH // 2, settings.BOARD_HEIGHT - 2
        player.set_direction(settings.DIR_UP)
        player.update_position()
        player.fixed_direction = settings.DIR_UP 
        
        if not getattr(self, "boss_bonus_given", False):
            self.state["lives"] += 1
            self.boss_bonus_given = True
            save_game(self.state.get("mode", 5), self.state.get("slot", 1), player, self.state.get("enemy_manager"), self.state)

        if getattr(self, "boss", None):
            self.boss.kill()

        calc_hp = max(2, int(round(self.extra_speed * 10)) + 2)
        boss_hp = calc_hp
        boss_max_hp = calc_hp

        slot = self.state.get("slot", 1)
        mode = self.state.get("mode", "C01")
        data = load_game(mode, slot)

        if data and "boss" in data and data["boss"]:
            boss_hp = data["boss"].get("hp", calc_hp)
            boss_max_hp = data["boss"].get("max_hp", boss_hp)
            if not boss_max_hp or boss_max_hp <= 0:
                boss_max_hp = boss_hp

        self.boss = DefaultBoss(settings.BOARD_WIDTH // 2, 3, None, hp = boss_hp, max_hp = boss_max_hp)
        self.state["enemies"].add(self.boss)
        self.state["all_sprites"].add(self.boss)
        
        boss_x, boss_y = self.boss.grid_x, self.boss.grid_y
        player_x, player_y = player.grid_x, player.grid_y
        for block in list(self.state["blocks"]):
            if (abs(block.grid_x - boss_x) <= 2 or abs(block.grid_y - boss_y) <= 2 or 
                abs(block.grid_x - player_x) <= 1 or abs(block.grid_y - player_y) <= 1):
                block.kill()

    def restrict_player_keys(self, direction) -> bool:
        if self.is_boss_phase:
            return direction in (settings.DIR_LEFT, settings.DIR_RIGHT)
        return True

    def get_custom_hud_goal(self):
        if getattr(self, "is_boss_phase", False) and getattr(self, "boss", None):
            return ("HP BOSS", f"{self.boss.hp}/{self.boss.max_hp}")
        return ("G O A L", str(self.state["global_kills"]))