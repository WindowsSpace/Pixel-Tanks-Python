import pygame
from settings import DIR_TO_ANGLE, DIR_UP, DIR_DOWN, DIR_LEFT, DIR_RIGHT, BOARD_WIDTH, BOARD_HEIGHT, PLAYER_MOVE_DELAY_MS
from grid import grid_to_pixel_center, in_bounds

class Tank(pygame.sprite.Sprite):
    def __init__(self, gx, gy, base_image):
        super().__init__()
        self.base_image = base_image
        self.image = self.base_image.copy()
        self.rect = self.image.get_rect()

        # Координаты по сетке
        self.grid_x = gx
        self.grid_y = gy

        # Направление
        self.direction = DIR_UP
        self.angle = DIR_TO_ANGLE[self.direction]

        self.update_image()
        self.update_position()

    def update_image(self):
        # Повернуть спрайт в нужную сторону и сохранить центр
        center = self.rect.center
        self.image = pygame.transform.rotate(self.base_image, self.angle)
        self.rect = self.image.get_rect(center=center)

    def update_position(self):
        # Обновление позиции в пикселях на основе координат сетки
        self.rect.centerx, self.rect.centery = grid_to_pixel_center(self.grid_x, self.grid_y)

    def set_direction(self, direction):
        self.direction = direction
        self.angle = DIR_TO_ANGLE[self.direction]
        self.update_image()

    def can_move_to(self, gx, gy, collision_group = None):
        # Проверка: можно ли зайти в клетку (границы + коллизия с другими танками).
        if not in_bounds(gx, gy):
            return False
        if collision_group:
            # Временный rect для проверки коллизии
            old_center = self.rect.center
            temp_rect = self.image.get_rect()
            temp_rect.center = grid_to_pixel_center(gx, gy)
            for sprite in collision_group:
                if sprite is self:
                    continue
                if temp_rect.colliderect(sprite.rect):
                    return False
            self.rect.center = old_center
        return True

    def move_step(self, collision_group = None) -> bool:
        # Шаг на одну клетку в текущем направлении. Возвращает True, если шаг выполнен.
        dx, dy = self.direction
        new_x = self.grid_x + dx
        new_y = self.grid_y + dy

        if self.can_move_to(new_x, new_y, collision_group):
            self.grid_x = new_x
            self.grid_y = new_y
            self.update_position()
            return True
        return False


class PlayerTank(Tank):
    def __init__(self, gx, gy, base_image):
        super().__init__(gx, gy, base_image)

        # Для логики зажатой кнопки
        self.current_move_dir = None
        self.key_held = False
        self.time_since_last_step = 0
        self.has_turned_for_current_dir = False

    def handle_keydown(self, direction: tuple[int, int]):
        # При нажатии клавиши направления.
        self.current_move_dir = direction
        self.key_held = True
        self.time_since_last_step = 0

        # Если уже смотрим в эту сторону — сразу делаем шаг.
        if self.direction == direction:
            self.has_turned_for_current_dir = True
        else:
            self.set_direction(direction)
            self.has_turned_for_current_dir = True  # повернулись, следующий шаг будет через задержку

    def handle_keyup(self, direction):
        # При отпускании клавиши направления (если это текущая).
        if self.current_move_dir == direction:
            self.key_held = False
            self.current_move_dir = None
            self.time_since_last_step = 0
            self.has_turned_for_current_dir = False

    def update_movement(self, dt_ms, collision_group = None):
        # Обновление движения при зажатой кнопке.
        # dt_ms — миллисекунд с прошлого кадра.
        if not self.key_held or self.current_move_dir is None:
            return

        # Если направление сменилось, но мы ещё не смотрим в эту сторону, то только поворачиваем.
        if self.direction != self.current_move_dir:
            self.set_direction(self.current_move_dir)
            self.has_turned_for_current_dir = True
            self.time_since_last_step = 0
            return

        # Иначе, мы уже повернуты в нужную сторону:
        self.time_since_last_step += dt_ms
        if self.time_since_last_step >= PLAYER_MOVE_DELAY_MS:
            self.time_since_last_step = 0
            # Пробуем сделать шаг, если упираемся в стену/танк — останавливаемся.
            moved = self.move_step(collision_group)
            if not moved:
                self.key_held = False
                self.current_move_dir = None

class EnemyTank(Tank):
    def __init__(self, gx, gy, base_image):
        super().__init__(gx, gy, base_image)
