import pygame
import io
import os

from typing import Any
from PIL import Image

from core.settings import INACTIVE_COLOR, CELL_SIZE
from models import \
    PLAYER_MODEL, ENEMY_MODEL, DEFAULT_BOSS_MODELS, \
    generate_model_surface, generate_states_surfaces
import models

def pil_to_surface(path:str) -> pygame.Surface:
    pil_img = Image.open(path)
    temp = io.BytesIO()
    pil_img.save(temp, format='PNG')
    temp.seek(0)
    return pygame.image.load(temp)

def colorize_icon(surface:pygame.Surface, color:Any) -> Any:
    mask = pygame.mask.from_surface(surface)
    new_surf = surface.copy()
    new_surf.fill((0, 0, 0, 0))
    mask.to_surface(new_surf, setcolor = color, unsetcolor = (0, 0, 0, 0))
    return new_surf

def load_surface_safe(path:str) -> pygame.Surface:
    try:
        return pil_to_surface(path)
    except Exception:
        return pil_to_surface('assets/sprites/pixel.png')

def scale_icon_in_place(surface:pygame.Surface, scale_factor:float) -> pygame.Surface:
    icon_rect = surface.get_bounding_rect()
    
    if icon_rect.width == 0 or icon_rect.height == 0:
        return surface 
    
    icon_content = surface.subsurface(icon_rect).copy()
    new_size = (int(icon_rect.width * scale_factor), int(icon_rect.height * scale_factor))
    scaled_content = pygame.transform.scale(icon_content, new_size)

    new_surface = pygame.Surface(new_size, pygame.SRCALPHA)
    scaled_rect = scaled_content.get_rect(center=(new_size[0] // 2, new_size[1] // 2))
    new_surface.blit(scaled_content, scaled_rect)
    
    return new_surface

_PIXEL_IMG_RAW = load_surface_safe('assets/sprites/pixel.png')
_PIXEL_COLOR_IMG_RAW = load_surface_safe('assets/sprites/pixel-color.png')

_PAUSE_IMG_RAW = load_surface_safe('assets/sprites/menu/pause.png')
_SOUNDS_IMG_RAW = load_surface_safe('assets/sprites/menu/sounds.png')

PLAYER_BASE_IMG, ENEMY_BASE_IMG = None, None
BLACK_CELL_IMG, BLACK_ENEMY_BASE_IMG = None, None  # "повреждённые" танки режима D01
PIXEL_COLOR_IMG_RAW, DEFAULT_PLAYER_BASE_IMG = None, None

BULLET_IMG_RAW, BACKGROUND_IMG, BACKGROUND_ALT_IMG, OUTER_BG_IMG = None, None, None, None
PAUSE_IMG_BLACK, PAUSE_IMG_INACTIVE = None, None
SOUNDS_IMG_BLACK, SOUNDS_IMG_INACTIVE = None, None
SLOT_IMG, WIN_IMG = None, None
TRANSITION_IMGS, EXPLOSION_IMGS = [], []

PLAYER_SHOOT_SOUND, EXPLOSION_SOUND, EVENT_SOUND = None, None, None
ENEMY_EXPLOSION_SOUND = None  # взрыв обычных врагов (Boom); у игрока и босса свои звуки
VOLUME_UP_SOUND, VOLUME_DOWN_SOUND, SCROLL_SOUND = None, None, None  # звуки интерфейса
BOSS_EXPLOSION_SOUND, REDACTED_SOUND = None, None  # папка sounds/Boss
SOUNDS_IMG_BASE = None

DEFAULT_BOSS_FRAMES = {}

def convert_assets() -> None:
    global PLAYER_BASE_IMG, ENEMY_BASE_IMG, DEFAULT_BOSS_FRAMES, DEFAULT_PLAYER_BASE_IMG
    global BLACK_CELL_IMG, BLACK_ENEMY_BASE_IMG
    global PIXEL_IMG_RAW, PIXEL_COLOR_IMG_RAW, BACKGROUND_IMG, BACKGROUND_ALT_IMG, OUTER_BG_IMG
    global PAUSE_IMG_BLACK, PAUSE_IMG_INACTIVE, SOUNDS_IMG_BLACK, SOUNDS_IMG_INACTIVE

    global WIN_IMG, EXPLOSION_IMGS, SETTINGS_IMG

    global PLAYER_SHOOT_SOUND, EXPLOSION_SOUND, ENEMY_EXPLOSION_SOUND
    global EVENT_SOUND
    global VOLUME_UP_SOUND, VOLUME_DOWN_SOUND, SCROLL_SOUND
    global BOSS_EXPLOSION_SOUND, REDACTED_SOUND
    global SOUNDS_IMG_BASE


    PIXEL_IMG_RAW = _PIXEL_IMG_RAW.convert_alpha()
    PIXEL_COLOR_IMG_RAW = _PIXEL_COLOR_IMG_RAW.convert_alpha()

    PLAYER_BASE_IMG = generate_model_surface(PLAYER_MODEL, PIXEL_IMG_RAW)
    DEFAULT_PLAYER_BASE_IMG = PLAYER_BASE_IMG.copy()

    ENEMY_BASE_IMG = generate_model_surface(ENEMY_MODEL, PIXEL_IMG_RAW)

    # Полностью чёрная клетка: чёрная подложка + обычный пиксель сверху
    BLACK_CELL_IMG = pygame.Surface((CELL_SIZE, CELL_SIZE), pygame.SRCALPHA)
    BLACK_CELL_IMG.blit(colorize_icon(PIXEL_COLOR_IMG_RAW, (0, 0, 0, 255)), (0, 0))
    BLACK_CELL_IMG.blit(PIXEL_IMG_RAW, (0, 0))
    BLACK_ENEMY_BASE_IMG = generate_model_surface(ENEMY_MODEL, BLACK_CELL_IMG)
    DEFAULT_BOSS_FRAMES = {
        k: v for k, v in generate_states_surfaces(DEFAULT_BOSS_MODELS, PIXEL_IMG_RAW).items()
    }


    WIN_IMG = generate_model_surface(models.WIN_MODEL, PIXEL_IMG_RAW)
    SETTINGS_IMG = generate_model_surface(models.SETTINGS_MODEL, PIXEL_IMG_RAW)
    
    EXPLOSION_IMGS = [
        generate_model_surface(frame, PIXEL_IMG_RAW) 
        for frame in models.EXPLOSION_MODELS
    ]


    pause_base = _PAUSE_IMG_RAW.convert_alpha()
    sounds_base = _SOUNDS_IMG_RAW.convert_alpha()

    pause_base = scale_icon_in_place(pause_base, 2.0)
    sounds_base = scale_icon_in_place(sounds_base, 2.5)

    SOUNDS_IMG_BASE = sounds_base.copy()
    PAUSE_IMG_BLACK = colorize_icon(pause_base, (0, 0, 0, 255))
    PAUSE_IMG_INACTIVE = colorize_icon(pause_base, (*INACTIVE_COLOR, 255))
    SOUNDS_IMG_BLACK = colorize_icon(sounds_base, (0, 0, 0, 255))
    SOUNDS_IMG_INACTIVE = colorize_icon(sounds_base, (*INACTIVE_COLOR, 255))

    pygame.mixer.init()
    PLAYER_SHOOT_SOUND = _load_sound('assets/sounds/shoot.ogg')
    EXPLOSION_SOUND = _load_sound('assets/sounds/explosion.ogg')
    ENEMY_EXPLOSION_SOUND = _load_sound('assets/sounds/Boom.ogg') or EXPLOSION_SOUND
    EVENT_SOUND = _load_sound('assets/sounds/Evynt_Otsilka.wav')

    VOLUME_UP_SOUND = _load_sound('assets/sounds/VolumeUp.ogg')
    VOLUME_DOWN_SOUND = _load_sound('assets/sounds/VolumeDown.ogg')
    SCROLL_SOUND = _load_sound('assets/sounds/Scroll.ogg')
    BOSS_EXPLOSION_SOUND = _load_sound('assets/sounds/Boss/Expole.ogg')
    REDACTED_SOUND = _load_sound('assets/sounds/Boss/Redacted.ogg')


def _find_file(path:str):
    # Путь к файлу без учёта регистра букв
    if os.path.exists(path):
        return path
    folder, name = os.path.split(path)
    try:
        for f in os.listdir(folder or '.'):
            if f.lower() == name.lower():
                return os.path.join(folder, f)
    except OSError:
        pass
    return None

def _load_sound(path:str):
    # pygame.mixer.Sound или None, если файла нет / он не читается
    real = _find_file(path)
    if real is None:
        return None
    try:
        return pygame.mixer.Sound(real)
    except pygame.error:
        return None


def play_sound(sound_obj, sounds_enabled) -> None:
    if sound_obj and sounds_enabled:
        sound_obj.play()


def enemy_image(skin=None):
    # Картинка врага по "скину" режима: None - обычный, "BLACK"
    if skin == "BLACK" and BLACK_ENEMY_BASE_IMG is not None:
        return BLACK_ENEMY_BASE_IMG
    return ENEMY_BASE_IMG


def make_black_copy(surface) -> pygame.Surface:
    # Тот же силуэт (по клеткам), но каждая клетка полностью чёрная
    cols = max(1, surface.get_width() // CELL_SIZE)
    rows = max(1, surface.get_height() // CELL_SIZE)
    out = pygame.Surface((cols * CELL_SIZE, rows * CELL_SIZE), pygame.SRCALPHA)
    for r in range(rows):
        for c in range(cols):
            if surface.get_at((c * CELL_SIZE + CELL_SIZE // 2, r * CELL_SIZE + CELL_SIZE // 2)).a > 0:
                out.blit(BLACK_CELL_IMG, (c * CELL_SIZE, r * CELL_SIZE))
    return out


def build_explosion_imgs(color=None) -> list:
    # Кадры взрыва игрока
    underlay = None
    if color is not None and PIXEL_COLOR_IMG_RAW is not None:
        underlay = colorize_icon(PIXEL_COLOR_IMG_RAW, (*color, 255))
    frames = []
    for frame in models.EXPLOSION_MODELS:
        rows = len(frame)
        cols = max(len(r) for r in frame)
        surf = pygame.Surface((cols * CELL_SIZE, rows * CELL_SIZE), pygame.SRCALPHA)
        for r, row in enumerate(frame):
            for c, ch in enumerate(row):
                if ch in (' ', '.'):
                    continue
                pos = (c * CELL_SIZE, r * CELL_SIZE)
                if underlay is not None:
                    surf.blit(underlay, pos)
                surf.blit(PIXEL_IMG_RAW, pos)
        frames.append(surf)
    return frames
