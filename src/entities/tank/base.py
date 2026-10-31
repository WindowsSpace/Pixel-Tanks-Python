# Базовый танк


from typing import Literal
import pygame
import random

from core import assets
from core import utils
from core.grid import grid_to_pixel_center, in_bounds
from core.settings import CELL_SIZE, DIR_DOWN, DIR_LEFT, DIR_RIGHT, DIR_TO_ANGLE, DIR_UP


class Tank(pygame.sprite.Sprite):
    def __init__(self, gx, gy, image_data, hp:int = 1, max_hp:int = 1) -> None:
        super().__init__()
        self.hp = hp
        self.max_hp = max_hp
        
        if isinstance(image_data, dict):
            if not image_data:
                self.frames_dict = {"default": assets.PIXEL_IMG_RAW}
            else:
                self.frames_dict = image_data
            
            self.current_state = "idle" if "idle" in self.frames_dict else list(self.frames_dict.keys())[0]
        elif isinstance(image_data, list):
            self.frames_dict = {"idle": image_data[0]}
            self.current_state = "idle"
        else:
            self.frames_dict = {"idle": image_data}
            self.current_state = "idle"
            
        self.base_image = self.frames_dict[self.current_state]
        self.image = self.base_image.copy()
        self.rect = self.image.get_rect()

        # Базовые хитбоксы
        self.hitbox = self.rect.copy()
        self.hurt_hitbox = self.hitbox.copy()  # Копия обычного хитбокса, доступная для ручного

        self.width_cells = 3 
        self.height_cells = 3
        self.board = None
        
        self.grid_x = gx
        self.grid_y = gy
        self.direction = random.choice([DIR_UP, DIR_DOWN, DIR_LEFT, DIR_RIGHT])
        self.angle = DIR_TO_ANGLE[self.direction]
        self.anim_timer = 0
        
        self.update_image()
        self.update_position()
    
    def set_state(self, new_state:Literal['idle', ''] = 'idle') -> None:
        if new_state in self.frames_dict and self.current_state != new_state:
            self.current_state = new_state
            self.base_image = self.frames_dict[self.current_state]
            self.update_image()

    def update_image(self) -> None:
        self.image = pygame.transform.rotate(self.base_image, self.angle)
        self.rect = self.image.get_rect(center=self.rect.center)
        self.mask = pygame.mask.from_surface(self.image)
        self._footprint = None  # форма пересчитается лениво (см. get_footprint)

    def get_footprint(self):
        # Клетки (dx, dy) относительно центра танка
        fp = getattr(self, "_footprint", None)
        if fp is not None:
            return fp

        mask = getattr(self, "mask", None)
        if mask is None:
            fp = [(dx, dy) for dy in (-1, 0, 1) for dx in (-1, 0, 1)]
            self._footprint = fp
            return fp

        w, h = mask.get_size()
        # положение изображения относительно левого верхнего угла клетки-центра
        origin = pygame.Rect(0, 0, w, h)
        origin.center = (CELL_SIZE // 2, CELL_SIZE // 2)
        left, top = origin.left, origin.top

        cell_mask = pygame.mask.Mask((CELL_SIZE, CELL_SIZE), fill=True)
        cx0, cx1 = left // CELL_SIZE, (left + w - 1) // CELL_SIZE
        cy0, cy1 = top // CELL_SIZE, (top + h - 1) // CELL_SIZE

        fp = []
        for cy in range(cy0, cy1 + 1):
            for cx in range(cx0, cx1 + 1):
                if mask.overlap_area(cell_mask, (cx * CELL_SIZE - left, cy * CELL_SIZE - top)) > 0:
                    fp.append((cx, cy))
        if not fp:
            fp = [(0, 0)]
        self._footprint = fp
        return fp

    def fits_board(self, gx, gy) -> bool:
        # Помещается ли танк своей реальной формой в клетку
        if self.board is None:
            return True
        return utils.are_cells_walkable(self.board, gx, gy, self.get_footprint())

    def update_position(self) -> None:
        cx, cy = grid_to_pixel_center(self.grid_x, self.grid_y)
        self.rect.centerx, self.rect.centery = cx, cy
        self.hitbox.centerx, self.hitbox.centery = cx, cy
        self.hurt_hitbox.centerx, self.hurt_hitbox.centery = cx, cy

    def set_direction(self, direction, collision_group = None) -> None:
        old_direction, old_angle = self.direction, self.angle
        self.direction = direction
        self.angle = DIR_TO_ANGLE[self.direction]
        self.update_image()

        # После поворота форма другая: если она задела стену карты
        if self.board is not None and not self.fits_board(self.grid_x, self.grid_y):
            for ox, oy in ((0, 1), (0, -1), (1, 0), (-1, 0), (1, 1), (-1, 1), (1, -1), (-1, -1)):
                if self.fits_board(self.grid_x + ox, self.grid_y + oy):
                    self.grid_x += ox
                    self.grid_y += oy
                    self.update_position()
                    break
            else:
                self.direction, self.angle = old_direction, old_angle
                self.update_image()
                return

        if collision_group:
            self.resolve_rotation_overlap(collision_group)
    
    def update_movement_anim(self, is_moving:bool, speed_rate:int = 15) -> None:
        if not is_moving:
            self.set_state("idle")
            return

        self.anim_timer += 1
        if (self.anim_timer // speed_rate) % 2 == 0:
            self.set_state("move0")
        else:
            self.set_state("move1")

    def can_move_to(self, gx, gy, collision_group = None) -> bool:
        cell_radius = self.width_cells // 2

        if self.board is not None:
            # is_area_walkable сам проверяет выход за пределы карты
            if not self.fits_board(gx, gy):
                return False
        else:
            # Fallback: используем хардкодные размеры из settings только если board
            if not (in_bounds(gx - cell_radius, gy - cell_radius) and
                    in_bounds(gx + cell_radius, gy + cell_radius)):
                return False

        if collision_group:
            old_center = self.rect.center
            self.rect.center = grid_to_pixel_center(gx, gy)
            
            if not hasattr(self, 'mask'):
                self.mask = pygame.mask.from_surface(self.image)
                
            for sprite in collision_group:
                # Игнорируем себя и блоки стен (стенами занимается is_area_walkable)
                if sprite is not self and not hasattr(sprite, 'is_block'):
                    if not hasattr(sprite, 'mask'):
                        sprite.mask = pygame.mask.from_surface(sprite.image)
                    if self.rect.colliderect(sprite.rect) and pygame.sprite.collide_mask(self, sprite):
                        self.rect.center = old_center
                        return False
            self.rect.center = old_center
        return True

    def move_step(self, collision_group = None) -> bool:
        new_x, new_y = self.grid_x + self.direction[0], self.grid_y + self.direction[1]
        if self.can_move_to(new_x, new_y, collision_group):
            self.grid_x, self.grid_y = new_x, new_y
            self.update_position()
            return True
        return False
    
    def resolve_rotation_overlap(self, collision_group) -> None:
        if not collision_group: return
        is_overlapping = any(sprite is not self and pygame.sprite.collide_mask(self, sprite) for sprite in collision_group)
        if not is_overlapping: return
            
        dx, dy = self.direction
        if self.can_move_to(self.grid_x + dx, self.grid_y + dy, collision_group):
            self.grid_x += dx
            self.grid_y += dy
            self.update_position()
            return
        if self.can_move_to(self.grid_x - dx, self.grid_y - dy, collision_group):
            self.grid_x -= dx
            self.grid_y -= dy
            self.update_position()
            return
