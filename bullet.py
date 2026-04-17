import pygame
from settings import BULLET_SPEED
from grid import in_bounds
from settings import BOARD_WIDTH, BOARD_HEIGHT, CELL_SIZE, OFFSET_X, OFFSET_Y

class Bullet(pygame.sprite.Sprite):
    def __init__(self, owner, direction, image = None):
        super().__init__()

        if image is None:
            self.image = pygame.Surface((CELL_SIZE // 3, CELL_SIZE // 3), pygame.SRCALPHA)
            self.image.fill((255, 255, 255))
        else:
            self.image = image

        self.rect = self.image.get_rect()

        self.dir_x, self.dir_y = direction
        self.speed = BULLET_SPEED

        # Стартовая позиция перед танка
        tank_center_x = owner.rect.centerx
        tank_center_y = owner.rect.centery
        offset_pixels = CELL_SIZE // 2
        start_x = tank_center_x + self.dir_x * offset_pixels
        start_y = tank_center_y + self.dir_y * offset_pixels
        self.rect.center = (start_x, start_y)

    def update(self):
        self.rect.x += self.dir_x * self.speed
        self.rect.y += self.dir_y * self.speed

        # Проверка выход за поле (по пикселям)
        left_limit = OFFSET_X
        right_limit = OFFSET_X + BOARD_WIDTH * CELL_SIZE
        top_limit = OFFSET_Y
        bottom_limit = OFFSET_Y + BOARD_HEIGHT * CELL_SIZE

        if (self.rect.right < left_limit or self.rect.left > right_limit or self.rect.bottom < top_limit or self.rect.top > bottom_limit):
            self.kill()
