# Босс по умолчанию (DefaultBoss)


import pygame
import random

from core import assets
from core.grid import grid_to_pixel_center
from core.settings import BOARD_HEIGHT, BOARD_WIDTH, CELL_SIZE, DIR_DOWN, DIR_LEFT, DIR_RIGHT
from entities.bullet import Bullet
from entities.tank.base import Tank


class DefaultBoss(Tank):
    is_boss = True  # по этому признаку приложение узнаёт босса

    def __init__(self, gx, gy, frames_dict = None, hp:int = 2, max_hp:int = None) -> None:
        if frames_dict is None:
            frames_dict = assets.DEFAULT_BOSS_FRAMES
        max_hp_val = max_hp if max_hp is not None else hp
        super().__init__(gx, gy, frames_dict, hp=hp, max_hp=max_hp_val)
        
        self.set_direction(DIR_DOWN)
        
        self.move_timer = 500
        
        # Таймеры стрельбы
        self.shoot_timer = 2000
        self.burst_count = 0  # Количество пуль в текущей очереди
        self.burst_timer = 500  # Задержка между пулями в очереди
        
        self.current_move_dir = DIR_LEFT
        
        # Переопределяем хитбокс
        self.hurt_hitbox = pygame.Rect(0, 0, 6, self.rect.height)
        self.update_position()
    
    def _board_dims(self):
        # Размер поля, по которому ходит босс: реальная карта
        b = self.board
        if b:
            return max(len(r) for r in b), len(b)
        return BOARD_WIDTH, BOARD_HEIGHT

    def update_position(self) -> None:
        super().update_position()
        bw, _ = self._board_dims()
        self.set_state(
            "left1" if self.grid_x <= 1 else
            "left0" if self.grid_x <= 2 else
            "right1" if self.grid_x >= bw - 2 else
            "right0" if self.grid_x >= bw - 3 else
            "idle"
        )
    
    def can_move_to(self, gx, gy, collision_group = None) -> bool:
        bw, bh = self._board_dims()
        if gx < 1 or gx > bw - 2:
            return False

        cell_radius = self.rect.width // CELL_SIZE // 2
        if gy - cell_radius < 0 or gy + cell_radius >= bh:
            return False
            
        if collision_group:
            old_center = self.rect.center
            self.rect.center = grid_to_pixel_center(gx, gy)
            
            if not hasattr(self, 'mask'):
                self.mask = pygame.mask.from_surface(self.image)
                
            for sprite in collision_group:
                if sprite is not self:
                    if not hasattr(sprite, 'mask'):
                        sprite.mask = pygame.mask.from_surface(sprite.image)
                    if pygame.sprite.collide_mask(self, sprite):
                        self.rect.center = old_center
                        return False
            self.rect.center = old_center
        return True

    def update_ai(self, dt_ms, player, collision_group, bullets_group, all_sprites_group, speed_mult=1.0, blocks_group=None) -> None:
        self.move_timer -= dt_ms * (speed_mult / 2)
        if self.move_timer <= 0:
            if random.random() < 0.3:
                self.current_move_dir = random.choice([DIR_LEFT, DIR_RIGHT])
            
            dx, dy = self.current_move_dir
            if self.can_move_to(self.grid_x + dx, self.grid_y + dy, collision_group):
                self.grid_x += dx
                self.grid_y += dy
            else:
                self.current_move_dir = DIR_RIGHT if self.current_move_dir == DIR_LEFT else DIR_LEFT
                
            self.update_position()
            self.move_timer = 600

        # Логика стрельбы
        if self.burst_count > 0:
            self.burst_timer -= dt_ms * (speed_mult / 2)
            if self.burst_timer <= 0:
                orig_center = self.rect.center

                self.rect.center = (self.hurt_hitbox.centerx, self.hurt_hitbox.bottom)
                b = Bullet(self, DIR_DOWN, assets.PIXEL_IMG_RAW, is_player=False)
                
                self.rect.center = orig_center 
                
                bullets_group.add(b)
                all_sprites_group.add(b)
                
                self.burst_count -= 1
                if self.burst_count > 0:
                    self.burst_timer = 500  # Время в миллисекундах между пулями в очереди
                else:
                    self.shoot_timer = 2000  # Задержка до следующей атаки
        else:
            self.shoot_timer -= dt_ms * speed_mult
            if self.shoot_timer <= 0:
                self.burst_count = 2  # Выпускаем 2 пули по очереди
                self.burst_timer = 0
