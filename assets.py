import pygame
import io
from PIL import Image

from settings import CELL_SIZE

def pil_to_surface(path):
    pil_img = Image.open(path)
    temp = io.BytesIO()
    pil_img.save(temp, format='PNG')
    temp.seek(0)
    return pygame.image.load(temp)

# Загружаем "сырые" изображения без convert_alpha
_PLAYER_IMG_RAW = pil_to_surface('sprites/player.png')
_ENEMY_IMG_RAW = pil_to_surface('sprites/enemy.png')
_BACKGROUND_IMG_RAW = pil_to_surface('sprites/background.png')
_PAUSE_IMG_RAW = pil_to_surface('sprites/pause.png')

# Масштабируем
_PLAYER_IMG_RAW = pygame.transform.smoothscale(_PLAYER_IMG_RAW, (CELL_SIZE, CELL_SIZE))
_ENEMY_IMG_RAW = pygame.transform.smoothscale(_ENEMY_IMG_RAW, (CELL_SIZE, CELL_SIZE))

PLAYER_BASE_IMG = None
ENEMY_BASE_IMG = None
BACKGROUND_IMG = None
PAUSE_IMG = None

def convert_assets():
    global PLAYER_BASE_IMG, ENEMY_BASE_IMG, BACKGROUND_IMG, PAUSE_IMG
    PLAYER_BASE_IMG = _PLAYER_IMG_RAW.convert_alpha()
    ENEMY_BASE_IMG = _ENEMY_IMG_RAW.convert_alpha()
    BACKGROUND_IMG = _BACKGROUND_IMG_RAW.convert_alpha()
    PAUSE_IMG = _PAUSE_IMG_RAW.convert_alpha()