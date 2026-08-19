import pygame
from typing import Any

# Разрешение игры/окна
WIDTH:int = 774
WIDTH_ALT:int = 1204
HEIGHT:int = 946

# Задний фон
BACKGROUND_COLOR:tuple[int, int, int] = (137, 145, 113)
INACTIVE_COLOR:tuple[int, int, int] = (129, 136, 111)

# Поле и размер клетки
BOARD_WIDTH:int = 10
BOARD_WIDTH_ALT:int = 20
BOARD_HEIGHT:int = 20
CELL_SIZE:int = 43

OFFSET_X:int = 43
OFFSET_Y:int = 43

# Координаты мини-поля
HUD_START_X:int = OFFSET_X + (BOARD_WIDTH * CELL_SIZE) + (2 * CELL_SIZE)
HUD_BOARD_Y:int = OFFSET_Y + (7 * CELL_SIZE)

# Направления
DIR_UP:tuple[int, int] = (0, -1)
DIR_DOWN:tuple[int, int] = (0, 1)
DIR_LEFT:tuple[int, int] = (-1, 0)
DIR_RIGHT:tuple[int, int] = (1, 0)

# Направления
DIR_TO_ANGLE:dict[Any, int] = {
    DIR_UP: 0,
    DIR_RIGHT: -90,
    DIR_DOWN: 180,
    DIR_LEFT: 90,
}

# Управление
PLAYER_MOVE_KEYS:dict[int, Any] = {
    pygame.K_w: DIR_UP, pygame.K_UP: DIR_UP,
    pygame.K_s: DIR_DOWN, pygame.K_DOWN: DIR_DOWN,
    pygame.K_a: DIR_LEFT, pygame.K_LEFT: DIR_LEFT,
    pygame.K_d: DIR_RIGHT, pygame.K_RIGHT: DIR_RIGHT,
}
PLAYER_SHOOT_KEYS:set[int] = {pygame.K_SPACE, pygame.K_RETURN}
PLAYER_MOVE_DELAY_MS:int = 150

# Случайные спавны игрока (редактируемые с помощью режимов)
PLAYER_SPAWN_POINTS:list[tuple[int, int]] = [
    (5, 11)
]

# Случайные спавны противника (редактируемые с помощью режимов)
ENEMY_SPAWN_POINTS:list[tuple[int, int]] = [
    (1, 1),
    (BOARD_WIDTH - 2, 1),
    (1, BOARD_HEIGHT - 2),
    (BOARD_WIDTH - 2, BOARD_HEIGHT - 2)
]

# Фигуры блоков
BLOCK_SHAPES:list[list[tuple[int, int]]] = [
    [(0, 0), (1, 0), (0, 1), (1, 1)],         # Квадрат 2x2
    [(0, 0), (1, 0), (2, 0)],                 # Горизонтальная линия 1x3
    [(0, 0), (0, 1), (0, 2)],                 # Вертикальная линия 3x1
    [(0, 0), (1, 0), (2, 0), (1, 1)],         # Т-образная
    [(0, 0), (0, 1), (0, 2), (1, 2)],         # L-образная
    [(0, 0), (1, 0), (1, 1), (2, 1)],         # Z-образная
    [(1, 0), (0, 1), (1, 1), (2, 1), (1, 2)], # Плюс
    [(0, 0), (2, 0), (0, 1), (1, 1), (2, 1)], # U-образная арка
    [(0, 0), (1, 1), (2, 2)]                  # Диагональ
]
