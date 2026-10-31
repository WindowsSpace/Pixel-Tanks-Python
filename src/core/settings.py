import pygame
from typing import Any

# Разрешение игры/окна
WIDTH:int = 774
HEIGHT:int = 946

# Задний фон
BACKGROUND_COLOR:tuple[int, int, int] = (137, 145, 113)
INACTIVE_COLOR:tuple[int, int, int] = (129, 136, 111)

# Поле и размер клетки
BOARD_WIDTH:int = 10
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

# Клавиши и кнопки мыши настраиваются в игре (настройки -> CONTROLS)
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


# Эталонные (обычные) точки спавна для режимов A-E
DEFAULT_PLAYER_SPAWN_POINTS:list[tuple[int, int]] = list(PLAYER_SPAWN_POINTS)
DEFAULT_ENEMY_SPAWN_POINTS:list[tuple[int, int]] = list(ENEMY_SPAWN_POINTS)

def reset_spawn_points() -> None:
    # Возвращает точки спавна к значениям по умолчанию (списки меняются на месте)
    PLAYER_SPAWN_POINTS[:] = DEFAULT_PLAYER_SPAWN_POINTS
    ENEMY_SPAWN_POINTS[:] = DEFAULT_ENEMY_SPAWN_POINTS

def set_enemy_spawn_points(points) -> None:
    # Подставляет точки спавна врагов (режим F) без замены самого списка
    ENEMY_SPAWN_POINTS[:] = list(points)


# Иконки самостоятельных окон HUD (hud = "OS_WINDOWS")
OS_ICON_DIR = "assets/sprites/os_icons"
OS_WINDOW_ICONS = {}  # например
GAME_ICON = "assets/PT64ALT.ico"


# Discord Rich Presence (discord_activity.DiscordActivity)
DISCORD_ENABLED = True
DISCORD_CLIENT_ID = "1539607326724718754"
DISCORD_MIN_INTERVAL = 4.0  # не чаще одного обновления статуса за столько секунд
# Картинки из Discord Developer Portal -> Rich Presence -> Art Assets
DISCORD_ASSETS = {"large": "tt-icon", "large_text": "Pixel Console", "small": {}}


# Случайные кластеры блоков в режимах A-E (spawn_blocks(num_clusters=...))
RANDOM_CLUSTERS_ENABLED = True
RANDOM_CLUSTERS_SCALE = 1.0
RANDOM_CLUSTERS_SAFE_RADIUS = 2  # вокруг точек спавна ВРАГОВ кластеры не ставятся (в клетках)
RANDOM_CLUSTERS_PLAYER_SAFE_RADIUS = 0  # вокруг запасных точек спавна игрока
