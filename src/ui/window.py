# Размеры окна/мира и раскладка для текущего состояния игры


import models

from core import settings
from ui import hud


SETTINGS_PAGES = ("DISPLAY", "TANK", "CONTROLS")

def settings_pages(g_save=None) -> tuple:
    # Вкладки настроек
    if g_save and g_save.get("tank_corrupted", False) and not g_save.get("tank_restored", False):
        return tuple(p for p in SETTINGS_PAGES if p != "TANK")
    return SETTINGS_PAGES
CONTROL_ACTIONS = ("up", "down", "left", "right", "shoot", "pause", "vol_up", "vol_down", "mute")

def build_settings_layout(g_save, page=0):
    # Пункты страницы настроек сверху вниз (скрытые пункты в список не попадают)
    ids = ["PAGE"]
    pages = settings_pages(g_save)
    name = pages[page % len(pages)]
    if name == "DISPLAY":
        ids += ["SCALE", "FONT", "CURTAIN"]
    elif name == "TANK":
        ids.append("CUSTOM_TANK")
        if g_save.get("custom_tank", {}).get("enabled", False):
            ids.append("PAINT_TANK")
            if g_save.get("paint_tank", False):
                ids.extend(["R", "G", "B"])
    else:
        ids += [f"BIND:{a}" for a in CONTROL_ACTIONS]
    return ids

def settings_page_name_is_tank(page, g_save) -> bool:
    # Открыта ли вкладка TANK с включённым кастомным танком
    pages = settings_pages(g_save)
    return pages[page % len(pages)] == "TANK" and g_save.get("custom_tank", {}).get("enabled", False)


def get_layout_for_state(game_state=None):
    # Раскладка окна
    mode_obj = get_current_mode_obj(game_state)
    if mode_obj is None:
        return hud.get_layout(None)

    board = get_board_model_for_state(game_state)
    rows = len(board)
    cols = max((len(row) for row in board), default=0)
    if not rows or not cols:  # карта режима ещё не создана
        cols = getattr(mode_obj, "board_width", 0)
        rows = getattr(mode_obj, "board_height", 0)
    lc = mode_obj.layout_cells() if hasattr(mode_obj, "layout_cells") else None
    if lc:  # режим сам задаёт размер окна
        cols, rows = lc

    if hasattr(mode_obj, "get_hud_params"):
        board_mode, hud_mode, hp_style, hp_fill = mode_obj.get_hud_params()
    else:
        board_mode, hud_mode, hp_style, hp_fill = "CLASSIC", "ON", "4x4", "gauge"
    return hud.get_layout(board_mode, hud_mode, hp_style, hp_fill, cols, rows,
                          getattr(mode_obj, "board_model_name", "NORMAL"),
                          getattr(mode_obj, "os_borderless", False))

def get_window_logical_size(game_state=None):
    lay = get_layout_for_state(game_state)
    return lay.win_w, lay.win_h

def get_window_hud_x(game_state=None):
    return get_layout_for_state(game_state).hud_x

def get_current_mode_obj(game_state):
    if isinstance(game_state, dict):
        return game_state.get("logic_mode")
    return None

def get_board_model_for_state(game_state):
    mode_obj = get_current_mode_obj(game_state)
    if mode_obj and hasattr(mode_obj, 'get_board_model'):
        return mode_obj.get_board_model()
    return models.get_board_model("NORMAL")

def get_logical_size(game_state = None):
    # Размер МИРА (поле с отступами), без HUD
    board = get_board_model_for_state(game_state)

    rows = len(board)
    cols = max((len(row) for row in board), default=0)
    mode_obj = get_current_mode_obj(game_state)
    lc = mode_obj.layout_cells() if mode_obj is not None and hasattr(mode_obj, "layout_cells") else None
    if lc:
        cols, rows = lc

    total_w = settings.OFFSET_X * 2 + cols * settings.CELL_SIZE
    total_h = settings.OFFSET_Y * 2 + rows * settings.CELL_SIZE
    return total_w, total_h
