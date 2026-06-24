import pygame
from settings import CELL_SIZE
from grid import in_bounds, grid_to_pixel_center

class Bullet(pygame.sprite.Sprite):
    def __init__(self, owner, direction, image=None, is_player=True) -> None:
        super().__init__()
        self.is_player = is_player
        self.image = image if image else pygame.Surface((CELL_SIZE // 3, CELL_SIZE // 3), pygame.SRCALPHA)
        self.rect = self.image.get_rect()
        self.hitbox = self.rect.copy() 
        self.dir_x, self.dir_y = direction
        
        self.grid_x = owner.grid_x + self.dir_x * 2
        self.grid_y = owner.grid_y + self.dir_y * 2

        self.move_timer = 0
        self.step_delay = 90

        self.update_position()

    def update_position(self) -> None:
        cx, cy = grid_to_pixel_center(self.grid_x, self.grid_y)
        self.rect.center = (cx, cy)
        self.hitbox.center = (cx, cy)

    def update(self, dt_ms) -> None:
        self.move_timer += dt_ms
        if self.move_timer >= self.step_delay:
            self.move_timer = 0
            self.grid_x += self.dir_x
            self.grid_y += self.dir_y
            self.update_position()

        if not in_bounds(self.grid_x, self.grid_y):
            self.kill()
