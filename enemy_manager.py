import random
import pygame

from settings import ENEMY_SPAWN_POINTS, MAX_ENEMIES_ON_FIELD, TOTAL_ENEMIES_TO_DESTROY
from grid import grid_to_pixel_center, in_bounds
from tank import EnemyTank

class EnemyManager:
    def __init__(self, enemy_image, enemies_group, all_sprites_group, player):
        self.enemy_image = enemy_image
        self.enemies_group = enemies_group
        self.all_sprites_group = all_sprites_group
        self.player = player

        self.total_spawned = 0
        self.total_destroyed = 0

    def spawn_enemy_if_needed(self):
        # Спавн врага, если меньше MAX_ENEMIES_ON_FIELD и не достигли лимита по общему количеству.
        if len(self.enemies_group) >= MAX_ENEMIES_ON_FIELD:
            return
        if self.total_spawned >= TOTAL_ENEMIES_TO_DESTROY:
            return

        # Выбираем доступные точки спавна, где нет врагов и игрок не рядом.
        available_points = []
        for gx, gy in ENEMY_SPAWN_POINTS:
            if not in_bounds(gx, gy):
                continue

            # Проверка: здесь уже стоит враг?
            occupied = False
            for e in self.enemies_group:
                if e.grid_x == gx and e.grid_y == gy:
                    occupied = True
                    break
            if occupied:
                continue

            # Игрок не должен быть рядом (расстояние <= 1 считаем рядом)
            if abs(self.player.grid_x - gx) <= 1 and abs(self.player.grid_y - gy) <= 1:
                continue

            available_points.append((gx, gy))

        if not available_points:
            return

        spawn_gx, spawn_gy = random.choice(available_points)
        enemy = EnemyTank(spawn_gx, spawn_gy, self.enemy_image)
        self.enemies_group.add(enemy)
        self.all_sprites_group.add(enemy)
        self.total_spawned += 1

    def enemy_destroyed(self, enemy):
        self.total_destroyed += 1
        enemy.kill()

    def is_level_completed(self):
        return self.total_destroyed >= TOTAL_ENEMIES_TO_DESTROY
