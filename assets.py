import pygame
import io
import os

from typing import Any
from PIL import Image

from settings import INACTIVE_COLOR
from models import *

def pil_to_surface(path:Any) -> pygame.Surface:
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
_BACKGROUND_IMG_RAW = load_surface_safe('assets/sprites/menu/background.png')

_PAUSE_IMG_RAW = load_surface_safe('assets/sprites/menu/pause.png')
_SOUNDS_IMG_RAW = load_surface_safe('assets/sprites/menu/sounds.png')

_WIN_IMG_RAW = load_surface_safe('assets/sprites/menu/WIN.png')

_MODE_IMG_RAW = [load_surface_safe(f'assets/sprites/menu/numbers/{i}.png') for i in range(0, 10)]

_A_MODE_IMG_RAW = [load_surface_safe(f'assets/sprites/menu/letters/A/{i}.png') for i in range(0, 3)]
_B_MODE_IMG_RAW = [load_surface_safe(f'assets/sprites/menu/letters/B/{i}.png') for i in range(0, 5)]
_C_MODE_IMG_RAW = [load_surface_safe(f'assets/sprites/menu/letters/C/{i}.png') for i in range(0, 5)]
_D_MODE_IMG_RAW = [load_surface_safe(f'assets/sprites/menu/letters/D/{i}.png') for i in range(0, 5)]
_E_MODE_IMG_RAW = [load_surface_safe(f'assets/sprites/menu/letters/E/{i}.png') for i in range(0, 5)]

_EXPLOSIONS_RAW = [load_surface_safe(f'assets/sprites/animations/explosion/explosion{i}.png') for i in range(1, 3)]

PLAYER_BASE_IMG, ENEMY_BASE_IMG = None, None
PIXEL_COLOR_IMG_RAW, DEFAULT_PLAYER_BASE_IMG = None, None

BULLET_IMG_RAW, BACKGROUND_IMG = None, None
PAUSE_IMG_BLACK, PAUSE_IMG_INACTIVE = None, None
SOUNDS_IMG_BLACK, SOUNDS_IMG_INACTIVE = None, None
SLOT_IMG, WIN_IMG = None, None
MODE_NUM_IMGS = []
A_MODE_IMGS, B_MODE_IMGS, C_MODE_IMGS, D_MODE_IMGS, E_MODE_IMGS = [], [], [], [], []
TRANSITION_IMGS, EXPLOSION_IMGS = [], []

PLAYER_SHOOT_SOUND, EXPLOSION_SOUND, EVENT_SOUND = None, None, None
SOUNDS_IMG_BASE = None

DEFAULT_BOSS_FRAMES = {}

def convert_assets() -> None:
    global PLAYER_BASE_IMG, ENEMY_BASE_IMG, DEFAULT_BOSS_FRAMES, DEFAULT_PLAYER_BASE_IMG
    global PIXEL_IMG_RAW, PIXEL_COLOR_IMG_RAW, BACKGROUND_IMG
    global PAUSE_IMG_BLACK, PAUSE_IMG_INACTIVE, SOUNDS_IMG_BLACK, SOUNDS_IMG_INACTIVE
    global WIN_IMG, MODE_NUM_IMGS, EXPLOSION_IMGS
    global A_MODE_IMGS, B_MODE_IMGS, C_MODE_IMGS, D_MODE_IMGS, E_MODE_IMGS
    global PLAYER_SHOOT_SOUND, EXPLOSION_SOUND
    global EVENT_SOUND
    global SOUNDS_IMG_BASE

    PIXEL_IMG_RAW = _PIXEL_IMG_RAW.convert_alpha()
    PIXEL_COLOR_IMG_RAW = _PIXEL_COLOR_IMG_RAW.convert_alpha()
    BACKGROUND_IMG = _BACKGROUND_IMG_RAW.convert_alpha()

    PLAYER_BASE_IMG = generate_model_surface(PLAYER_MODEL, PIXEL_IMG_RAW)
    DEFAULT_PLAYER_BASE_IMG = PLAYER_BASE_IMG.copy()

    ENEMY_BASE_IMG = generate_model_surface(ENEMY_MODEL, PIXEL_IMG_RAW)
    DEFAULT_BOSS_FRAMES = {k: v for k, v in generate_states_surfaces(DEFAULT_BOSS_MODELS, PIXEL_IMG_RAW).items()}

    pause_base = _PAUSE_IMG_RAW.convert_alpha()
    sounds_base = _SOUNDS_IMG_RAW.convert_alpha()

    pause_base = scale_icon_in_place(pause_base, 2.0)
    sounds_base = scale_icon_in_place(sounds_base, 2.5)

    SOUNDS_IMG_BASE = sounds_base.copy()
    PAUSE_IMG_BLACK = colorize_icon(pause_base, (0, 0, 0, 255))
    PAUSE_IMG_INACTIVE = colorize_icon(pause_base, (*INACTIVE_COLOR, 255))
    SOUNDS_IMG_BLACK = colorize_icon(sounds_base, (0, 0, 0, 255))
    SOUNDS_IMG_INACTIVE = colorize_icon(sounds_base, (*INACTIVE_COLOR, 255))

    WIN_IMG = _WIN_IMG_RAW.convert_alpha()

    A_MODE_IMGS = [t.convert_alpha() for t in _A_MODE_IMG_RAW]
    B_MODE_IMGS = [t.convert_alpha() for t in _B_MODE_IMG_RAW]
    C_MODE_IMGS = [t.convert_alpha() for t in _C_MODE_IMG_RAW]
    D_MODE_IMGS = [t.convert_alpha() for t in _D_MODE_IMG_RAW]
    E_MODE_IMGS = [t.convert_alpha() for t in _E_MODE_IMG_RAW]

    MODE_NUM_IMGS = [t.convert_alpha() for t in _MODE_IMG_RAW]
    EXPLOSION_IMGS = [t.convert_alpha() for t in _EXPLOSIONS_RAW]

    pygame.mixer.init()
    if os.path.exists('assets/sounds/shoot.ogg'):
        PLAYER_SHOOT_SOUND = pygame.mixer.Sound('assets/sounds/shoot.ogg')
    if os.path.exists('assets/sounds/explosion.ogg'):
        EXPLOSION_SOUND = pygame.mixer.Sound('assets/sounds/explosion.ogg')
    if os.path.exists('assets/sounds/Evynt_Otsilka.wav'):
        EVENT_SOUND = pygame.mixer.Sound('assets/sounds/Evynt_Otsilka.wav')

def play_sound(sound_obj, sounds_enabled) -> None:
    if sound_obj and sounds_enabled:
        sound_obj.play()
