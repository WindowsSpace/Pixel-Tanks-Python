import pygame
import io
from PIL import Image
import os
from settings import INACTIVE_COLOR

def pil_to_surface(path) -> pygame.Surface:
    pil_img = Image.open(path)
    temp = io.BytesIO()
    pil_img.save(temp, format='PNG')
    temp.seek(0)
    return pygame.image.load(temp)

def colorize_icon(surface, color):
    mask = pygame.mask.from_surface(surface)
    new_surf = surface.copy()
    new_surf.fill((0, 0, 0, 0))
    mask.to_surface(new_surf, setcolor=color, unsetcolor=(0, 0, 0, 0))
    return new_surf

def load_surface_safe(path, size=(50, 50)) -> pygame.Surface:
    try:
        return pil_to_surface(path)
    except Exception:
        surf = pygame.Surface(size, pygame.SRCALPHA) # Заглушка, если файла нет
        surf.fill((255, 0, 255, 128))
        return surf

def scale_icon_in_place(surface, scale_factor):
    icon_rect = surface.get_bounding_rect()
    
    if icon_rect.width == 0 or icon_rect.height == 0:
        return surface 
        
    icon_surface = surface.subsurface(icon_rect).copy()

    new_size = (int(icon_rect.width * scale_factor), int(icon_rect.height * scale_factor))
    scaled_icon = pygame.transform.scale(icon_surface, new_size)
    new_surface = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    scaled_rect = scaled_icon.get_rect(center=icon_rect.center)
    new_surface.blit(scaled_icon, scaled_rect)

    return new_surface

_PLAYER_IMG_RAW = load_surface_safe('assets/sprites/player.png')
_ENEMY_IMG_RAW = load_surface_safe('assets/sprites/enemy.png')
_BULLET_IMG_RAW = load_surface_safe('assets/sprites/pixel.png')
_BACKGROUND_IMG_RAW = load_surface_safe('assets/sprites/menu/background.png')

_PAUSE_IMG_RAW = load_surface_safe('assets/sprites/menu/pause.png')
_SOUNDS_IMG_RAW = load_surface_safe('assets/sprites/menu/sounds.png')

_SLOT_IMG_RAW = load_surface_safe('assets/sprites/menu/slot.png')
_NUM1_IMG_RAW = load_surface_safe('assets/sprites/menu/1.png')
_NUM2_IMG_RAW = load_surface_safe('assets/sprites/menu/2.png')
_NUM3_IMG_RAW = load_surface_safe('assets/sprites/menu/3.png')

_TRANSITIONS_RAW = [load_surface_safe(f'assets/sprites/animations/transitions/transition{i}.png') for i in range(1, 11)]
_EXPLOSIONS_RAW = [load_surface_safe(f'assets/sprites/animations/explosion/explosion{i}.png', (172, 172)) for i in range(1, 3)]

# Глобальные переменные изображений
PLAYER_BASE_IMG, ENEMY_BASE_IMG = None, None
BULLET_IMG_RAW, BACKGROUND_IMG = None, None
PAUSE_IMG_BLACK, PAUSE_IMG_INACTIVE = None, None
SOUNDS_IMG_BLACK, SOUNDS_IMG_INACTIVE = None, None
SLOT_IMG = None
NUM_IMGS = []
TRANSITION_IMGS = []
EXPLOSION_IMGS = []

PLAYER_SHOOT_SOUND, EXPLOSION_SOUND, EVENT_SOUND = None, None, None
SOUNDS_IMG_BASE = None
CUSTOM_FONT = None

def convert_assets() -> None:
    global PLAYER_BASE_IMG, ENEMY_BASE_IMG, BULLET_IMG_RAW, BACKGROUND_IMG
    global PAUSE_IMG_BLACK, PAUSE_IMG_INACTIVE, SOUNDS_IMG_BLACK, SOUNDS_IMG_INACTIVE
    global SLOT_IMG, NUM_IMGS, TRANSITION_IMGS, EXPLOSION_IMGS
    global PLAYER_SHOOT_SOUND, EXPLOSION_SOUND, EVENT_SOUND
    global SOUNDS_IMG_BASE
    global CUSTOM_FONT

    PLAYER_BASE_IMG = _PLAYER_IMG_RAW.convert_alpha()
    ENEMY_BASE_IMG = _ENEMY_IMG_RAW.convert_alpha()
    BULLET_IMG_RAW = _BULLET_IMG_RAW.convert_alpha()
    BACKGROUND_IMG = _BACKGROUND_IMG_RAW.convert_alpha()

    pause_base = _PAUSE_IMG_RAW.convert_alpha()
    sounds_base = _SOUNDS_IMG_RAW.convert_alpha()

    scale_multiplier = 2.0 
    pause_base = scale_icon_in_place(pause_base, scale_multiplier)
    sounds_base = scale_icon_in_place(sounds_base, scale_multiplier)

    SOUNDS_IMG_BASE = sounds_base.copy()
    
    PAUSE_IMG_BLACK = colorize_icon(pause_base, (0, 0, 0, 255))
    PAUSE_IMG_INACTIVE = colorize_icon(pause_base, (*INACTIVE_COLOR, 255))
    
    SOUNDS_IMG_BLACK = colorize_icon(sounds_base, (0, 0, 0, 255))
    SOUNDS_IMG_INACTIVE = colorize_icon(sounds_base, (*INACTIVE_COLOR, 255))

    SLOT_IMG = _SLOT_IMG_RAW.convert_alpha()
    NUM_IMGS = [_NUM1_IMG_RAW.convert_alpha(), _NUM2_IMG_RAW.convert_alpha(), _NUM3_IMG_RAW.convert_alpha()]
    TRANSITION_IMGS = [t.convert_alpha() for t in _TRANSITIONS_RAW]
    EXPLOSION_IMGS = [e.convert_alpha() for e in _EXPLOSIONS_RAW]

    pygame.mixer.init()
    if os.path.exists('assets/sounds/shoot.ogg'):
        PLAYER_SHOOT_SOUND = pygame.mixer.Sound('assets/sounds/shoot.ogg')
    if os.path.exists('assets/sounds/explosion.ogg'):
        EXPLOSION_SOUND = pygame.mixer.Sound('assets/sounds/explosion.ogg')
    if os.path.exists('assets/sounds/Evynt_Otsilka.wav'):
        EVENT_SOUND = pygame.mixer.Sound('assets/sounds/Evynt_Otsilka.wav')

    try:
        CUSTOM_FONT = pygame.font.Font('assets/font/DS-DIGII.TTF', 40)
    except FileNotFoundError:
        CUSTOM_FONT = pygame.font.SysFont("arial", 40, bold=True)

def play_sound(sound_obj, sounds_enabled) -> None:
    if sound_obj and sounds_enabled:
        sound_obj.play()
