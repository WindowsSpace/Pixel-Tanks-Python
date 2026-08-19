import random
from settings import ENEMY_SPAWN_POINTS
from grid import in_bounds
from tank import EnemyTank

class EnemyManager:
    def __init__(self, enemy_image, enemies_group, all_sprites_group, player) -> None:
        self.enemy_image = enemy_image
        self.enemies_group = enemies_group
        self.all_sprites_group = all_sprites_group
        self.player = player
        self.spawn_timer = 1500

    def spawn_enemy_if_needed(self, dt_ms, max_enemies, spawn_delay) -> None:
        if len(self.enemies_group) >= max_enemies:
            return

        self.spawn_timer -= dt_ms
        if self.spawn_timer > 0:
            return

        available_points = []
        for gx, gy in ENEMY_SPAWN_POINTS:
            if not (in_bounds(gx - 1, gy - 1) and in_bounds(gx + 1, gy + 1)): continue
            
            occupied = any(abs(e.grid_x - gx) < 3 and abs(e.grid_y - gy) < 3 for e in self.enemies_group)
            if occupied: continue

            if abs(self.player.grid_x - gx) < 3 and abs(self.player.grid_y - gy) < 3:
                continue

            available_points.append((gx, gy))

        if not available_points:
            return

        spawn_gx, spawn_gy = random.choice(available_points)
        enemy = EnemyTank(spawn_gx, spawn_gy, self.enemy_image)
        self.enemies_group.add(enemy)
        self.all_sprites_group.add(enemy)
        self.spawn_timer = spawn_delay # Сбрасываем таймер спавна

    def clear_enemies(self) -> None:
        for e in self.enemies_group:
            e.kill()