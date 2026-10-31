# Отрисовка: HUD, текст, шторка, спрайты со сдвигом камеры


import pygame

from core import assets
from core import settings
from core.settings import CELL_SIZE, HUD_BOARD_Y, HUD_START_X, OFFSET_Y
from core.utils import level_to_int


ABOVE_Y = HUD_BOARD_Y + (4 / CELL_SIZE) - OFFSET_Y
BELOW_Y = HUD_BOARD_Y + (4 * CELL_SIZE) + OFFSET_Y
LABEL_X = HUD_START_X
VALUE_X = HUD_START_X + (4 * CELL_SIZE)

def draw_group_culled(surface, group, cam_x, cam_y) -> None:
    # Group.draw со сдвигом на камеру: рисуются только спрайты, попавшие в кадр
    view = pygame.Rect(cam_x, cam_y, surface.get_width(), surface.get_height())
    blits = [(spr.image, (spr.rect.x - cam_x, spr.rect.y - cam_y))
             for spr in group.sprites() if spr.rect.colliderect(view)]
    if blits:
        surface.blits(blits, False)

def visible_curtain_cells(board, board_px, rc) -> dict:
    # Клетки карты, на которые ложится шторка: только видимые в кадре
    cols_total = max((len(r) for r in board), default=0)
    c0 = max(0, (rc.left - board_px.x) // CELL_SIZE)
    c1 = min(cols_total, -(-(rc.right - board_px.x) // CELL_SIZE))
    r0 = max(0, (rc.top - board_px.y) // CELL_SIZE)
    r1 = min(len(board), -(-(rc.bottom - board_px.y) // CELL_SIZE))

    def has(r, c):
        row = board[r]
        return c < len(row) and row[c] not in (' ', '.', '\n')

    return {
        "cols": [c for c in range(c0, c1) if any(has(r, c) for r in range(r0, r1))],
        "rows": [r for r in range(r0, r1) if any(has(r, c) for c in range(c0, c1))],
        "r0": r0, "r1": r1, "c0": c0, "c1": c1,
        "origin": (board_px.x, board_px.y), "has": has,
    }

def render_text(screen, font, text, x = None, y = None, align = "center", color = (0, 0, 0)) -> None:
    surf = font.render(text, True, color)
    rect = surf.get_rect()
    
    if x is None:
        x = HUD_START_X + (4 * CELL_SIZE) // 2
        
    if align == "center":
        rect.center = (x, y)
    elif align == "left":
        rect.topleft = (x, y)
    elif align == "right":
        rect.topright = (x, y)
    
    screen.blit(surf, rect)

def render_hud(screen, font, stats, sound_img, paused, pause_rect, sound_rect, custom_goal = None, is_settings = False, hud_start_x = None) -> None:
    if hud_start_x is None:
        hud_start_x = settings.HUD_START_X

    LABEL_X = hud_start_x
    VALUE_X = hud_start_x + (4 * settings.CELL_SIZE)
    CENTER_X = hud_start_x + (4 * settings.CELL_SIZE) // 2  # центр колонки HUD (текст по центру)
    ABOVE_Y = settings.HUD_BOARD_Y + (4 / settings.CELL_SIZE) - settings.OFFSET_Y
    BELOW_Y = settings.HUD_BOARD_Y + (4 * settings.CELL_SIZE) + settings.OFFSET_Y

    if is_settings:
        for lx in range(4):
            for ly in range(4):
                screen.blit(assets.PIXEL_IMG_RAW, (hud_start_x + lx * CELL_SIZE, HUD_BOARD_Y + ly * CELL_SIZE))

        render_text(screen, font, "SETTINGS", CENTER_X, BELOW_Y + 21)

        screen.blit(assets.PAUSE_IMG_BLACK if paused else assets.PAUSE_IMG_INACTIVE, pause_rect)
        screen.blit(sound_img, sound_rect)
        return

    hidden = stats.get("hide_panels") or ()
    if "SCORE" not in hidden:
        render_text(screen, font, "SCORE", CENTER_X, ABOVE_Y - 215)
        render_text(screen, font, str(stats["score"]), CENTER_X, ABOVE_Y - 172)
    if "HI-SCORE" not in hidden:
        render_text(screen, font, "HI-SCORE", CENTER_X, ABOVE_Y - 129)
        render_text(screen, font, str(stats["hi_score"]), CENTER_X, ABOVE_Y - 86)
    
    if custom_goal:
        render_text(screen, font, custom_goal[0], CENTER_X, ABOVE_Y - 43)
        render_text(screen, font, custom_goal[1], CENTER_X, ABOVE_Y)
    else:
        render_text(screen, font, "G O A L", CENTER_X, ABOVE_Y - 43)
        render_text(screen, font, f'{stats["kills_this_level"]}/{stats["target_enemies"]}', CENTER_X, ABOVE_Y)

    for lx, ly in stats["lives_positions"]:
        screen.blit(assets.PIXEL_IMG_RAW, (hud_start_x + lx * CELL_SIZE, HUD_BOARD_Y + ly * CELL_SIZE))

    if "LEVEL" not in hidden:
        if stats.get("is_boss_phase") or str(stats.get("level")) == "BOSS":
            render_text(screen, font, "BOSS", CENTER_X, BELOW_Y + 21)
        elif level_to_int(stats.get("level")) is None:
            # Свой текст вместо номера уровня (ENDLESS, MAZE, ...) - по центру
            render_text(screen, font, str(stats.get("level")), CENTER_X, BELOW_Y + 21)
        else:
            render_text(screen, font, "LEVEL", LABEL_X, BELOW_Y, align="left")
            render_text(screen, font, str(stats.get("level", 1)), VALUE_X, BELOW_Y, align="right")
        render_text(screen, font, "SPEED", LABEL_X, BELOW_Y + 43, align="left")
        render_text(screen, font, f'{stats["speed_multiplier"]:g}', VALUE_X, BELOW_Y + 43, align="right")

    screen.blit(assets.PAUSE_IMG_BLACK if paused else assets.PAUSE_IMG_INACTIVE, pause_rect)
    screen.blit(sound_img, sound_rect)

def draw_procedural_outer_frame(surface, width, height, border_size = 4) -> None:
    border_color = (70, 77, 51)
    pygame.draw.rect(surface, border_color, (0, 0, width, height), border_size)
