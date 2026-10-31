# Кастомный (покрашенный) танк игрока


import pygame

from core import assets
from core.settings import CELL_SIZE


def build_tank_surface(g_save, use_color = True) -> pygame.Surface:
    # Картинка кастомного танка игрока 3x3 клетки по текущим настройкам
    pixels = g_save.get("custom_tank", {}).get("pixels") or [[1, 0], [0, 1], [1, 1], [2, 1], [0, 2], [2, 2]]
    rgb_val = g_save.get("rgb", [129, 136, 111]) if use_color else [129, 136, 111]
    color_underlay = None
    if assets.PIXEL_COLOR_IMG_RAW:
        color_underlay = assets.colorize_icon(assets.PIXEL_COLOR_IMG_RAW, (*rgb_val, 255))

    surf = pygame.Surface((3 * CELL_SIZE, 3 * CELL_SIZE), pygame.SRCALPHA)
    for px, py in pixels:
        x, y = px * CELL_SIZE, py * CELL_SIZE
        if color_underlay:
            surf.blit(color_underlay, (x, y))
        if assets.PIXEL_IMG_RAW:
            surf.blit(assets.PIXEL_IMG_RAW, (x, y))
    return surf


def apply_custom_tank(g_save, force_colorless = False) -> None:
    if g_save.get("custom_tank", {}).get("enabled", False):
        if "pixels" not in g_save["custom_tank"] or not g_save["custom_tank"]["pixels"]:
            g_save["custom_tank"]["pixels"] = [[1, 0], [0, 1], [1, 1], [2, 1], [0, 2], [2, 2]]

        use_color = g_save.get("paint_tank", False) and not force_colorless
        rgb_val = g_save.get("rgb", [129, 136, 111])
        
        if use_color and assets.PIXEL_COLOR_IMG_RAW:
            color_underlay = assets.colorize_icon(assets.PIXEL_COLOR_IMG_RAW, (*rgb_val, 255))
        else:
            if assets.PIXEL_COLOR_IMG_RAW:
                color_underlay = assets.colorize_icon(assets.PIXEL_COLOR_IMG_RAW, (129, 136, 111, 255))
            else:
                color_underlay = None
            
        surf = pygame.Surface((3 * CELL_SIZE, 3 * CELL_SIZE), pygame.SRCALPHA)
        for px, py in g_save["custom_tank"].get("pixels", []):
            x, y = px * CELL_SIZE, py * CELL_SIZE
            if color_underlay:
                surf.blit(color_underlay, (x, y))
            if assets.PIXEL_IMG_RAW:
                surf.blit(assets.PIXEL_IMG_RAW, (x, y))
        assets.PLAYER_BASE_IMG = surf
    else:
        if hasattr(assets, 'DEFAULT_PLAYER_BASE_IMG') and assets.DEFAULT_PLAYER_BASE_IMG:
            assets.PLAYER_BASE_IMG = assets.DEFAULT_PLAYER_BASE_IMG
