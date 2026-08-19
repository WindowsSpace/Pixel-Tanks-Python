from modes.base_mode import BaseMode

import random
import settings
import json
from settings import BOARD_WIDTH, BOARD_HEIGHT, DIR_UP, DIR_LEFT, DIR_RIGHT
from blocks import spawn_blocks
from tank import DefaultBoss

class ModeA01(BaseMode):
    TARGET_KILLS:int = 20
    def __init__(self, game_state) -> None:
        super().__init__(game_state)
        self.mode_id = "A01"
        self.target_kills = self.TARGET_KILLS
        self.max_levels = 10
        self.extra_speed = 0.0 # Не даем скорость за уровни

    def setup_level(self, is_new_level=False) -> None:
        player = self.state["player"]
        player.grid_x, player.grid_y = random.choice(settings.PLAYER_SPAWN_POINTS)
        player.update_position()
        
        if is_new_level or not self.blocks_generated:
            for b in list(self.state["blocks"]):
                b.kill()
            
            current_level = int(self.state.get("level", 1))
            custom_shapes = self.get_scripted_blocks(current_level)
            
            spawn_blocks(self.state, BOARD_WIDTH, BOARD_HEIGHT, num_clusters=0, custom_shapes=custom_shapes)
            self.blocks_generated = True

    def get_scripted_blocks(self, level) -> list:
        match level:
            case 2:
                return [
                    {"shape": [(0, 0), (0, 1), (1, 1)], "x": 1, "y": 15},
                    {"shape": [(1, 0), (0, 1), (1, 1)], "x": 7, "y": 15},
                    {"shape": [(0, 0), (1, 0), (0, 1), (1, 1), (0, 2), (1, 2)], "x": 8, "y": 9}
                ]
            case 3:
                return [
                    {"shape": [(0, 0), (1, 0), (0, 1)], "x": 1, "y": 3},
                    {"shape": [(0, 0), (1, 0), (1, 1)], "x": 7, "y": 3},
                    {"shape": [(0, 0), (1, 0), (0, 1), (1, 1), (0, 2), (1, 2)], "x": 0, "y": 9}
                ]
            case 4:
                return [
                    {"shape": [(0, 0), (1, 0), (0, 1)], "x": 1, "y": 3},
                    {"shape": [(1, 0), (0, 1), (1, 1)], "x": 7, "y": 15},
                    {"shape": [(0, 0), (1, 0), (2, 0), (0, 1), (1, 1), (2, 1)], "x": 3, "y": 7}
                ]
            case 5:
                return [
                    {"shape": [(0, 0), (1, 0), (1, 1)], "x": 7, "y": 3},
                    {"shape": [(0, 0), (0, 1), (1, 1)], "x": 1, "y": 15}
                ]
            case 6:
                return [
                    {"shape": [(0, 0), (1, 0), (0, 1)], "x": 1, "y": 3},
                    {"shape": [(0, 0), (1, 0), (1, 1)], "x": 7, "y": 3},
                    {"shape": [(0, 0), (1, 0), (0, 1), (1, 1), (0, 2), (1, 2)], "x": 8, "y": 9},
                    {"shape": [(0, 0), (1, 0), (0, 1), (1, 1), (0, 2), (1, 2)], "x": 0, "y": 9},
                    {"shape": [(1, 0), (0, 1), (1, 1)], "x": 7, "y": 15}
                ]
            case 7:
                return [
                    {"shape": [(0, 0), (1, 0), (1, 1)], "x": 7, "y": 3},
                    {"shape": [(0, 0), (1, 0), (2, 0), (0, 1), (1, 1), (2, 1)], "x": 3, "y": 7},
                    {"shape": [(0, 0), (1, 0), (0, 1), (1, 1), (0, 2), (1, 2)], "x": 0, "y": 9},
                    {"shape": [(0, 0), (0, 1), (1, 1)], "x": 1, "y": 15},
                    {"shape": [(1, 0), (0, 1), (1, 1)], "x": 7, "y": 15}
                ]
            case 8:
                return [
                    {"shape": [(0, 0), (1, 0), (0, 1)], "x": 1, "y": 3},
                    {"shape": [(0, 0), (0, 1), (1, 1)], "x": 1, "y": 15},
                    {"shape": [(1, 0), (0, 1), (1, 1)], "x": 7, "y": 15},
                    {"shape": [(0, 0), (1, 0), (2, 0), (0, 1), (1, 1), (2, 1)], "x": 3, "y": 7}
                ]
            case 9:
                return [
                    {"shape": [(0, 0), (1, 0), (0, 1)], "x": 1, "y": 3},
                    {"shape": [(0, 0), (1, 0), (1, 1)], "x": 7, "y": 3},
                    {"shape": [(0, 0), (0, 1), (1, 1)], "x": 1, "y": 15},
                    {"shape": [(0, 0), (1, 0), (2, 0), (0, 1), (1, 1), (2, 1)], "x": 3, "y": 7},
                    {"shape": [(0, 0), (1, 0), (0, 1), (1, 1), (0, 2), (1, 2)], "x": 0, "y": 9},
                    {"shape": [(0, 0), (1, 0), (0, 1), (1, 1), (0, 2), (1, 2)], "x": 8, "y": 9}
                ]
            case 10:
                return [
                    {"shape": [(0, 0), (1, 0), (0, 1)], "x": 1, "y": 3},
                    {"shape": [(0, 0), (1, 0), (1, 1)], "x": 7, "y": 3},
                    {"shape": [(0, 0), (1, 0), (2, 0), (0, 1), (1, 1), (2, 1)], "x": 3, "y": 7},
                    {"shape": [(0, 0), (1, 0), (0, 1), (1, 1), (0, 2), (1, 2)], "x": 0, "y": 9},
                    {"shape": [(0, 0), (0, 1), (1, 1)], "x": 1, "y": 15},
                    {"shape": [(1, 0), (0, 1), (1, 1)], "x": 7, "y": 15}
                ]
        return []

    def modify_spawn_params(self, max_enemies, spawn_delay):
        return 3, random.randint(1500, 3000)

    def check_conditions(self):
        if self.state["kills_this_level"] >= self.target_kills:
            self.state["level"] += 1
            self.state["kills_this_level"] = 0
            
            if self.state["level"] > self.max_levels:
                return "WIN_SCREEN"
            return "NEXT_LEVEL"
        return None


# ==========================================
# РЕЖИМ A - 02
# ==========================================
class ModeA02(BaseMode):
    TARGET_KILLS:int = 50
    def __init__(self, game_state) -> None:
        super().__init__(game_state)
        self.mode_id = "A02"
        self.target_kills = self.TARGET_KILLS
        self.next_speed_threshold = 25

    def apply_spawns(self) -> None:
        settings.ENEMY_SPAWN_POINTS.clear()
        settings.ENEMY_SPAWN_POINTS.extend([
            (1, 1), (BOARD_WIDTH - 2, 1),
            (1, BOARD_HEIGHT - 2), (BOARD_WIDTH - 2, BOARD_HEIGHT - 2),
            (BOARD_WIDTH // 2, 1),
            (BOARD_WIDTH // 2, BOARD_HEIGHT - 2),
            (1, BOARD_HEIGHT // 2),
            (BOARD_WIDTH - 2, BOARD_HEIGHT // 2)
        ])

        settings.PLAYER_SPAWN_POINTS.clear()
        center_offsets = [
            (BOARD_WIDTH // 2, BOARD_HEIGHT // 2),
            (BOARD_WIDTH // 2 - 2, BOARD_HEIGHT // 2),
            (BOARD_WIDTH // 2 + 2, BOARD_HEIGHT // 2),
            (BOARD_WIDTH // 2, BOARD_HEIGHT // 2 - 2),
            (BOARD_WIDTH // 2, BOARD_HEIGHT // 2 + 2)
        ]
        settings.PLAYER_SPAWN_POINTS.extend(center_offsets + settings.ENEMY_SPAWN_POINTS)

    def setup_level(self, is_new_level = False) -> None:
        if is_new_level:
            self.blocks_generated = False
            self.boss_bonus_given = False
            self.is_boss_phase = False
        elif not getattr(self, 'is_boss_phase', False):
            self.is_boss_phase = False

    def modify_spawn_params(self, max_enemies, spawn_delay):
        if self.is_boss_phase:
            return 0, spawn_delay
        return 4, 750 

    def check_conditions(self):
        if not self.is_boss_phase:
            if self.state["kills_this_level"] >= self.next_speed_threshold and self.next_speed_threshold < self.target_kills:
                self.extra_speed += round(random.uniform(0.2, 0.5), 1)
                self.next_speed_threshold += 25

            if self.state["kills_this_level"] >= self.target_kills:
                self.start_boss_phase()
                return "BOSS_PHASE_START"
                
        if self.is_boss_phase and self.boss.hp <= 0:
            return "WIN_SCREEN"
        return None

    def start_boss_phase(self) -> None:
        from save_load import save_game, load_game
        self.enhanced_bullet_collision = self.is_boss_phase = True
        player = self.state["player"]
        player.grid_x, player.grid_y = BOARD_WIDTH // 2, BOARD_HEIGHT - 2
        player.set_direction(DIR_UP)
        player.update_position()
        player.fixed_direction = DIR_UP 
        
        if not getattr(self, "boss_bonus_given", False):
            self.state["lives"] += 1
            self.boss_bonus_given = True
            save_game(self.state.get("mode", "A02"), self.state.get("slot", 1), player, self.state.get("enemy_manager"), self.state)

        if getattr(self, "boss", None):
            self.boss.kill()

        calc_hp = max(2, int(self.extra_speed * 10))
        boss_hp = calc_hp
        boss_max_hp = calc_hp

        slot = self.state.get("slot", 1)
        mode = self.state.get("mode", "A02")
        data = load_game(mode, slot)

        if data and "boss" in data and data["boss"]:
            boss_hp = data["boss"].get("hp", calc_hp)
            boss_max_hp = data["boss"].get("max_hp", boss_hp)
            if not boss_max_hp or boss_max_hp <= 0:
                boss_max_hp = boss_hp

        self.boss = DefaultBoss(BOARD_WIDTH // 2, 3, None, hp = boss_hp, max_hp = boss_max_hp)
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
            return direction in (DIR_LEFT, DIR_RIGHT)
        return True

    def get_custom_hud_goal(self):
        if getattr(self, "is_boss_phase", False) and getattr(self, "boss", None):
            return ("HP BOSS", f"{self.boss.hp}/{self.boss.max_hp}")
        return None