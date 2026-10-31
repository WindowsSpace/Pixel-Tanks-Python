import pygame
from core import assets
from core.settings import CELL_SIZE
from core.grid import in_bounds, get_cell_topleft

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
        self.outside = False  # пуля босса ещё летит снаружи поля (в окне ОС)
        self.bounces_left = 0  # сколько раз пуля отскочит от края/стены поля

        self.update_position()

    def update_curtain_shading(self, colorless: bool) -> None:
        if colorless:
            self.image = self.default_image
        else:
            self.image = self.colored_image if self.custom_color else self.default_image

    def update_position(self) -> None:
        tx, ty = get_cell_topleft(self.grid_x, self.grid_y)
        
        self.rect.x = tx + (CELL_SIZE - self.rect.width) // 2
        self.rect.y = ty + (CELL_SIZE - self.rect.height) // 2
        
        self.hitbox.center = self.rect.center

    def update(self, dt_ms, board: list[str] = None) -> None:
        self.move_timer += dt_ms
        if self.move_timer >= self.step_delay:
            self.move_timer = 0
            self.grid_x += self.dir_x
            self.grid_y += self.dir_y
            self.update_position()

        if self.outside:
            if in_bounds(self.grid_x, self.grid_y, board):
                self.outside = False  # влетела в поле - дальше обычная пуля
            else:
                return

        # Проверка вылета за границы динамической карты
        if not in_bounds(self.grid_x, self.grid_y, board):
            if self._ricochet():
                return
            self.kill()
            return

        # Проверка врезания в стены уровня ('X')
        if board and board[self.grid_y][self.grid_x] == ' ':
            if self._ricochet():
                return
            self.kill()

    def _ricochet(self) -> bool:
        # Отскок: разворачиваем пулю и возвращаем в клетку, откуда она вылетела
        if self.bounces_left <= 0:
            return False
        self.bounces_left -= 1
        self.dir_x, self.dir_y = -self.dir_x, -self.dir_y
        self.grid_x += self.dir_x
        self.grid_y += self.dir_y
        self.update_position()
        return True


class _Anchor:
    def __init__(self, gx, gy) -> None:
        self.grid_x, self.grid_y = gx, gy


class BeamCell(Bullet):
    # Одна клетка луча (атака "линия" босса)

    def __init__(self, gx, gy, ttl_ms=260) -> None:
        super().__init__(_Anchor(gx, gy), (0, 0), assets.PIXEL_IMG_RAW, is_player=False)
        self.grid_x, self.grid_y = gx, gy
        self.ttl = ttl_ms
        self._expired = False
        self.update_position()

    def update(self, dt_ms, board=None) -> None:
        self.ttl -= dt_ms
        if self.ttl <= 0:
            self._expired = True
            super().kill()

    def kill(self) -> None:
        if self._expired:
            super().kill()

    def purge(self) -> None:
        # Убрать луч немедленно (шторка, сброс боя): обычный kill() его не берёт
        self._expired = True
        super().kill()
