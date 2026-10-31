# Отрисовка поля клетками (draw_smart_board) и перекраска клетки


import pygame

from core.settings import CELL_SIZE


_pixel_cache = {}

def get_recolored_pixel(pixel_img, color, size=(CELL_SIZE, CELL_SIZE)):
    if pixel_img is None:
        return None
        
    key = (id(pixel_img), color, size)
    if key in _pixel_cache:
        return _pixel_cache[key]

    scaled = pygame.transform.scale(pixel_img, size).convert_alpha()
    
    try:
        from core import assets
        tinted = assets.colorize_icon(scaled, color)
    except Exception:
        tinted = scaled

    _pixel_cache[key] = tinted
    return tinted

def draw_smart_board(surface, model, offset_x, offset_y, pixel_img = None, outline = True) -> None:
    # Рисует поле, но только те клетки, что попадают на surface
    _draw_smart_board_raw(surface, model, offset_x, offset_y, pixel_img, outline)

def _draw_smart_board_raw(surface, model, offset_x, offset_y, pixel_img = None, outline = True) -> None:
    pad = 3
    t = 4
    
    # Видимый диапазон клеток (запас в клетку с каждой стороны)
    sw, sh = surface.get_size()
    margin = pad + t
    c0 = max(0, (-offset_x - margin) // CELL_SIZE - 1)
    c1 = (sw - offset_x + margin) // CELL_SIZE + 2
    r0 = max(0, (-offset_y - margin) // CELL_SIZE - 1)
    r1 = min(len(model), (sh - offset_y + margin) // CELL_SIZE + 2)
    if r0 >= r1 or c1 <= c0:
        return

    border_color = (70, 77, 51)
    background_color = (137, 145, 113)
    inactive_color = (129, 136, 111)

    for r in (range(r0, r1) if outline else ()):  # outline=False - без внешней обводки клеток
        row = model[r]
        for c in range(c0, min(c1, len(row))):
            char = row[c]
            if char in (' ', '.', '\n'):
                continue

            x = offset_x + c * CELL_SIZE
            y = offset_y + r * CELL_SIZE
            rect = pygame.Rect(x - pad - t, y - pad - t, CELL_SIZE + 2 * (pad + t), CELL_SIZE + 2 * (pad + t))
            pygame.draw.rect(surface, border_color, rect)

    for r in range(r0, r1):
        row = model[r]
        for c in range(c0, min(c1, len(row))):
            char = row[c]
            if char in (' ', '.', '\n'):
                continue

            x = offset_x + c * CELL_SIZE
            y = offset_y + r * CELL_SIZE
            rect = pygame.Rect(x - pad, y - pad, CELL_SIZE + 2 * pad, CELL_SIZE + 2 * pad)
            pygame.draw.rect(surface, background_color, rect)

    recolored_pixel = get_recolored_pixel(pixel_img, inactive_color, (CELL_SIZE, CELL_SIZE))

    for r in range(r0, r1):
        row = model[r]
        for c in range(c0, min(c1, len(row))):
            char = row[c]
            if char in (' ', '.', '\n'):
                continue

            x = offset_x + c * CELL_SIZE
            y = offset_y + r * CELL_SIZE
            
            if recolored_pixel:
                surface.blit(recolored_pixel, (x, y))
            else:
                pygame.draw.rect(surface, inactive_color, (x, y, CELL_SIZE, CELL_SIZE))
