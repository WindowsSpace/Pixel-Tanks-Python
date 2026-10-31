import random
from core import settings
from entities.tank import EnemyTank


class EnemyManager:
    def __init__(self, enemy_image, enemies_group, all_sprites_group, player,
                 enemy_params=None) -> None:
        self.enemy_image       = enemy_image
        self.enemies_group     = enemies_group
        self.all_sprites_group = all_sprites_group
        self.player            = player
        self.spawn_timer       = 1000
        self.bullet_color      = None  # цвет пуль новых врагов (режим D01: чёрный)
        # Параметры ИИ для каждого нового EnemyTank.
        # Любой именованный аргумент EnemyTank.__init__ подходит:
        #   {"intelligence": 0.7, "aggressiveness": 0.5, "patrol_chance": 0.2, ...}
        # Пустой dict (по умолчанию) -> стандартные значения EnemyTank.
        self.enemy_params = dict(enemy_params) if enemy_params else {}

    def spawn_enemy_if_needed(self, dt_ms, max_enemies, spawn_delay) -> None:
        if len(self.enemies_group) >= max_enemies:
            return

        self.spawn_timer -= dt_ms
        if self.spawn_timer > 0:
            return

        available_points = []
        for gx, gy in settings.ENEMY_SPAWN_POINTS:
            occupied = any(
                abs(e.grid_x - gx) < 3 and abs(e.grid_y - gy) < 3
                for e in self.enemies_group
            )
            if occupied:
                continue
            if abs(self.player.grid_x - gx) < 3 and abs(self.player.grid_y - gy) < 3:
                continue
            available_points.append((gx, gy))

        if not available_points:
            return

        spawn_gx, spawn_gy = random.choice(available_points)
        enemy = EnemyTank(spawn_gx, spawn_gy, self.enemy_image, **self.enemy_params)
        enemy.bullet_color = self.bullet_color
        self.enemies_group.add(enemy)
        self.all_sprites_group.add(enemy)
        self.spawn_timer = spawn_delay

    def clear_enemies(self) -> None:
        for e in self.enemies_group:
            e.kill()
