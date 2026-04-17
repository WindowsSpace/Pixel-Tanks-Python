import pygame

# Окно
WIDTH = 700
HEIGHT = 700
BACKGROUND_COLOR = (137, 145, 113)

# Сетка
BOARD_WIDTH = 10
BOARD_HEIGHT = 18
CELL_SIZE = 43
OFFSET_X = 0
OFFSET_Y = 0

# Направления
DIR_UP = (0, -1)
DIR_DOWN = (0, 1)
DIR_LEFT = (-1, 0)
DIR_RIGHT = (1, 0)

DIR_TO_ANGLE = {
    DIR_UP: 0,
    DIR_RIGHT: -90,
    DIR_DOWN: 180,
    DIR_LEFT: 90,
}

# Управление
PLAYER_MOVE_KEYS = {
    pygame.K_w: DIR_UP,
    pygame.K_UP: DIR_UP,
    pygame.K_s: DIR_DOWN,
    pygame.K_DOWN: DIR_DOWN,
    pygame.K_a: DIR_LEFT,
    pygame.K_LEFT: DIR_LEFT,
    pygame.K_d: DIR_RIGHT,
    pygame.K_RIGHT: DIR_RIGHT,
}

PLAYER_SHOOT_KEYS = {pygame.K_SPACE, pygame.K_RETURN}

# Игровые параметры
PLAYER_START_GRID = (5, 3)  # стартовые координаты игрока (по сетке)

# Точки спавна по сетке
ENEMY_SPAWN_POINTS = [
    (0, 0),                      # левый верхний
    (BOARD_WIDTH // 2, 0),       # центр верх
    (BOARD_WIDTH - 1, 0),        # правый верхний
    (BOARD_WIDTH // 2 - 2, BOARD_HEIGHT // 2),  # слева от центра
    (BOARD_WIDTH // 2 + 2, BOARD_HEIGHT // 2),  # справа от центра
    (0, BOARD_HEIGHT - 1),       # слева снизу
    (BOARD_WIDTH // 2, BOARD_HEIGHT - 1),       # центр снизу
    (BOARD_WIDTH - 1, BOARD_HEIGHT - 1),        # справа снизу
]

MAX_ENEMIES_ON_FIELD = 3
TOTAL_ENEMIES_TO_DESTROY = 50

BULLET_SPEED = 5
PLAYER_MOVE_DELAY_MS = 150   # задержка при зажатой кнопке