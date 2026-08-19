import pygame
import assets
from settings import CELL_SIZE
from grid import in_bounds, grid_to_pixel_center

class Bullet(pygame.sprite.Sprite):
    def __init__(self, owner, direction, image = None, colored_image = None, custom_color = None, is_player = True) -> None:
        super().__init__()
        self.is_player = is_player
        self.custom_color = custom_color

        self.default_image = image if image else pygame.Surface((CELL_SIZE // 3, CELL_SIZE // 3), pygame.SRCALPHA)
        
        if self.custom_color and assets.PIXEL_COLOR_IMG_RAW:
            surf = pygame.Surface(self.default_image.get_size(), pygame.SRCALPHA)
            color_underlay = assets.colorize_icon(assets.PIXEL_COLOR_IMG_RAW, (*self.custom_color, 255))
            surf.blit(color_underlay, (0, 0))
            surf.blit(self.default_image, (0, 0))
            
            self.colored_image = surf
        else:
            self.colored_image = colored_image if colored_image else self.default_image
        
        self.image = self.colored_image if self.custom_color else self.default_image
        self.rect = self.image.get_rect()
        self.hitbox = self.rect.copy() 
        
        self.dir_x, self.dir_y = direction
        self.grid_x = owner.grid_x + self.dir_x * 2
        self.grid_y = owner.grid_y + self.dir_y * 2

        self.move_timer = 0
        self.step_delay = 90

        self.update_position()

    def update_curtain_shading(self, colorless: bool) -> None:
        if colorless:
            self.image = self.default_image
        else:
            self.image = self.colored_image if self.custom_color else self.default_image

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
