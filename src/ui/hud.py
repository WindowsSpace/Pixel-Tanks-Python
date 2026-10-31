# Режимы ДОСКИ и вид HUD
import random

import pygame

from core import assets, settings
import models
from core.utils import level_to_int

BOARD_MODES = ("CLASSIC", "CENTER", "TRIMMED", "DYNAMIC")
HUD_MODES = ("ON", "OFF", "WINDOWS", "OS_WINDOWS")
HP_FILLS = ("gauge", "scatter")

BORDER_COLOR = (70, 77, 51)
PAD, THICK = 3, 4  # зазор и толщина обводки (как в models.draw_smart_board)
M = PAD + THICK  # отступ рамки окна от текста/иконки: 3 px + сама рамка
HP_M = M + PAD  # у окна HP: 3 px до видимого поля клеток
FIELD_PAD = 7  # на столько обводка клеток выходит за клетку
FRAME_W = THICK  # толщина рамки вокруг отрисованного поля = обводка поля/окна
FIELD_BG = (137, 145, 113)  # цвет фона клеток поля (зазор 3 px между обводкой и клетками)
GAP = 12  # зазор между панелями внутри окна
ICON_GAP = 10  # зазор между окошками sounds и pause
ZONE_MARGIN = 8
OS_GAP = 64  # расстояние от главного окна до окон ОС
OS_V_GAP = 56  # минимум по вертикали между окнами ОС (под заголовок окна)
OS_GAP_BORDERLESS = 20  # то же для окон без рамки ОС
OS_V_GAP_BORDERLESS = 14

_cache: dict = {}
_scaled_cache: dict = {}
_icon_content = (76, 98)  # размер иконок sounds/pause (обновляется из game.py)
_os_ok = None
_docked_only = False  # True (например, в полноэкранном режиме) -> OS_WINDOWS


# вспомогательное
def os_available() -> bool:
    # Есть ли в этой сборке pygame самостоятельные окна (pygame._sdl2.video)
    global _os_ok
    if _os_ok is None:
        try:
            import pygame._sdl2.video as _v
            _os_ok = hasattr(_v, "Window") and hasattr(_v, "Renderer") and hasattr(_v, "Texture")
        except Exception:
            _os_ok = False
    return _os_ok


def set_docked_only(flag: bool) -> None:
    # Запрещает самостоятельные окна ОС (полноэкранный режим)
    global _docked_only
    if bool(flag) != _docked_only:
        _docked_only = bool(flag)
        _cache.clear()


def disable_os_windows() -> None:
    # Вызывается, если окна ОС не удалось создать
    global _os_ok
    _os_ok = False
    _cache.clear()


def set_icon_content_size(w: int, h: int) -> None:
    # Размер иконок sounds/pause (по ним считается размер их окошек)
    global _icon_content
    size = (max(1, int(w)), max(1, int(h)))
    if size != _icon_content:
        _icon_content = size
        _cache.clear()
        _scaled_cache.clear()


def normalize(board_mode, hud="ON", hp_style="4x4", hp_fill="gauge"):
    # Приводит параметры режима к допустимым значениям
    b = str(board_mode).upper() if board_mode is not None else "CLASSIC"
    if b not in BOARD_MODES:
        b = "CLASSIC"
    h = str(hud).upper() if hud is not None else "ON"
    if h not in HUD_MODES:
        h = "ON"
    if b in ("CENTER", "TRIMMED") and h in ("ON", "OFF"):
        h = "OFF"
    if h == "OS_WINDOWS" and (_docked_only or not os_available()):
        h = "WINDOWS"  # запасной вариант: панели внутри окна игры
    model = tuple(models.get_hp_model(hp_style))
    fill = str(hp_fill).lower() if hp_fill is not None else "gauge"
    if fill not in HP_FILLS:
        fill = "gauge"
    return b, h, model, fill


def cycle(value, options, direction):
    i = options.index(value) if value in options else 0
    return options[(i + direction) % len(options)]


# шкала HP
def hp_cells_all(model):
    # Все клетки шкалы: [(x, y), ...]
    return [(x, y) for y, row in enumerate(model) for x, ch in enumerate(row) if ch not in " ."]


class HpGauge:
    # Какие клетки шкалы сейчас "горят"

    def __init__(self, model, fill="gauge") -> None:
        self.cells = hp_cells_all(model)
        self.fill = fill
        self.on: set = set()

    def sync(self, lives):
        target = max(0, min(int(lives), len(self.cells)))
        while len(self.on) > target:
            if self.fill == "gauge":
                top = min(y for _, y in self.on)
                pool = [c for c in self.on if c[1] == top]
            else:
                pool = list(self.on)
            self.on.discard(random.choice(sorted(pool)))
        while len(self.on) < target:
            empty = [c for c in self.cells if c not in self.on]
            if self.fill == "gauge":
                low = max(y for _, y in empty)
                pool = [c for c in empty if c[1] == low]
            else:
                pool = empty
            self.on.add(random.choice(pool))
        return sorted(self.on)


def gauge_cells(game_state, model, fill="gauge"):
    # Активные клетки шкалы для текущего числа жизней
    key = (tuple(model), fill)
    g = game_state.get("_hp_gauge")
    if not g or g[0] != key:
        g = (key, HpGauge(model, fill))
        game_state["_hp_gauge"] = g
    return g[1].sync(game_state.get("lives", 0))


# раскладка
class Layout:
    # Всё, что нужно знать о расположении элементов в окне

    def __init__(self) -> None:
        self.kind = "classic"  # classic | none | windows | os
        self.board_mode = "CLASSIC"
        self.hud_mode = "ON"
        self.win_w = 0
        self.win_h = 0
        self.map_area = pygame.Rect(0, 0, 0, 0)  # где показывается карта (с полями OFFSET)
        self.hud_x = 0  # левый край классического HUD
        self.hp_model = tuple(models.HP_MODELS[models.HP_DEFAULT])
        self.std_cols = 10  # размер "стандартного" поля (модель карты режима) в клетках
        self.std_rows = 20  # по нему идёт шторка перехода между уровнями
        self.panels = []  # windows: панели внутри окна игры
        self.os_panels = []  # os: описания самостоятельных окон
        self.os_borderless = False  # os: окна без рамки ОС (без заголовка и кнопок)
        # Поле в точности как в меню: клетки + их обводка
        self.field_rect = pygame.Rect(0, 0, 0, 0)

    def place_icons(self, sound_rect, pause_rect) -> None:
        # Положение кликабельных иконок (используется меню; в игре иконки в HUD)
        C = settings.CELL_SIZE
        if self.kind == "classic":
            below_y = settings.HUD_BOARD_Y + 4 * C + settings.OFFSET_Y
            icons_y = below_y + C * 5.89
            sound_rect.topleft = (self.hud_x, icons_y)
            pause_rect.topright = (self.hud_x + 4 * C, icons_y)
        elif self.kind == "windows":
            for p in self.panels:
                if p["kind"] == "sound":
                    sound_rect.center = p["rect"].center
                elif p["kind"] == "pause":
                    pause_rect.center = p["rect"].center
        else:  # HUD нет - иконки уезжают за экран
            sound_rect.topleft = (-10000, -10000)
            pause_rect.topleft = (-10000, -10000)


def _stack(heights, total, max_gap):
    # Вертикальная стопка по центру: возвращает список y
    n = len(heights)
    free = total - sum(heights)
    gap = max(0, min(max_gap, free // (n + 1)))
    top = (free - gap * (n - 1)) // 2
    ys, y = [], top
    for h in heights:
        ys.append(y)
        y += h + gap
    return ys


def _panel(name, kind, idx, size):
    return {"name": name, "kind": kind, "idx": idx, "native": size,
            "rect": pygame.Rect(0, 0, *size), "scale": 1.0}


def _make_panels(hp_model, C):
    tw, th = 4 * C + 2 * M, 2 * C + 2 * M  # 4x2 клетки текста + отступ 3 px
    cols = max(len(r) for r in hp_model)
    hw, hh = cols * C + 2 * HP_M, len(hp_model) * C + 2 * HP_M  # поле HP + отступ 3 px
    iw, ih = _icon_content[0] + 2 * M, _icon_content[1] + 2 * M  # одинаковые окошки иконок
    texts = [_panel(n, "text", i, (tw, th)) for i, n in enumerate(("SCORE", "HI-SCORE", "GOAL", "LEVEL"))]
    hp = _panel("HP", "hp", 0, (hw, hh))
    snd = _panel("SOUNDS", "sound", 0, (iw, ih))
    pse = _panel("PAUSE", "pause", 0, (iw, ih))
    return texts, hp, snd, pse


# укладка панелей в области
def _item_size(item):
    w = sum(p["native"][0] for p in item) + ICON_GAP * (len(item) - 1)
    h = max(p["native"][1] for p in item)
    return w, h


def _group_size(columns):
    cw = [max(_item_size(i)[0] for i in col) for col in columns]
    ch = [sum(_item_size(i)[1] for i in col) + GAP * (len(col) - 1) for col in columns]
    return sum(cw) + GAP * (len(cw) - 1), max(ch), cw


def _fit_scale(region, columns, ms):
    gw, gh, _ = _group_size(columns)
    return min(1.0, (region.w - 2 * ms) / gw, (region.h - 2 * ms) / gh)


def _place(region, columns, s, ms):
    gw, _, cw = _group_size(columns)
    x = region.x + (region.w - gw * s) / 2
    for col, w in zip(columns, cw):
        heights = [round(_item_size(i)[1] * s) for i in col]
        ys = _stack(heights, region.h - 2 * ms, int(30 * s))
        for item, y, h in zip(col, ys, heights):
            gap = round(ICON_GAP * s)
            row_w = sum(round(p["native"][0] * s) for p in item) + gap * (len(item) - 1)
            ix = x + (w * s - row_w) / 2
            for p in item:
                pw, ph = round(p["native"][0] * s), round(p["native"][1] * s)
                p["rect"] = pygame.Rect(int(ix), region.y + ms + y + (h - ph) // 2, pw, ph)
                p["scale"] = s
                ix += pw + gap
        x += w * s + GAP * s


def _field_for(area):
    # Видимая часть поля внутри области карты: как поле в меню
    ix = max(0, settings.OFFSET_X - FIELD_PAD)
    iy = max(0, settings.OFFSET_Y - FIELD_PAD)
    return area.inflate(-2 * ix, -2 * iy)


def get_layout(board_mode=None, hud="ON", hp_style="4x4", hp_fill="gauge", cols=None, rows=None, std_model="NORMAL",
               os_borderless=False) -> Layout:
    # board_mode - режим доски
    C = settings.CELL_SIZE
    if board_mode is None:
        b, h, model = "CLASSIC", "ON", tuple(models.HP_MODELS[models.HP_DEFAULT])
        cols = rows = None
        std_model = "NORMAL"
    else:
        b, h, model, _ = normalize(board_mode, hud, hp_style, hp_fill)

    std = models.get_board_model(std_model)
    std_rows, std_cols = len(std), max((len(r) for r in std), default=1)
    if b == "DYNAMIC":
        vc = max(1, min(int(cols or std_cols), 20))
        vr = max(1, min(int(rows or std_rows), 20))
    else:
        vc, vr, cols, rows = std_cols, std_rows, None, None

    os_borderless = bool(os_borderless) and h == "OS_WINDOWS"
    key = (b, h, model, vc, vr, std_cols, std_rows, _icon_content, C, os_borderless)
    lay = _cache.get(key)
    if lay is not None:
        return lay

    ox, oy = settings.OFFSET_X, settings.OFFSET_Y
    std_map_w, std_map_h = 2 * ox + std_cols * C, 2 * oy + std_rows * C
    zone_w = 2 * C + len(models.HUD_MODEL[0]) * C  # место под классический HUD справа
    hud_min_h = 2 * oy + 20 * C  # классическому HUD нужна высота под 20 рядов
    classic_w, classic_h = std_map_w + zone_w, max(std_map_h, hud_min_h)
    map_w, map_h = 2 * ox + vc * C, 2 * oy + vr * C

    lay = Layout()
    lay.board_mode, lay.hud_mode, lay.hp_model = b, h, model
    lay.std_cols, lay.std_rows = std_cols, std_rows
    lay.hud_x = ox + vc * C + 2 * C
    texts, hp, snd, pse = _make_panels(model, C)
    docked = (h == "WINDOWS")

    if b == "CLASSIC":
        lay.win_w, lay.win_h = classic_w, classic_h
        lay.map_area = pygame.Rect(0, 0, std_map_w, classic_h)
        lay.hud_x = ox + std_cols * C + 2 * C
        if docked:
            zone = pygame.Rect(std_map_w, 0, zone_w, classic_h)
            single = [[[t] for t in texts] + [[hp], [snd, pse]]]
            split = [[[t] for t in texts] + [[snd, pse]], [[hp]]]
            best = max((single, split), key=lambda c: _fit_scale(zone, c, ZONE_MARGIN))
            _place(zone, best, _fit_scale(zone, best, ZONE_MARGIN), ZONE_MARGIN)

    elif b == "CENTER":
        lay.win_w, lay.win_h = classic_w, classic_h
        lay.map_area = pygame.Rect((classic_w - std_map_w) // 2, 0, std_map_w, classic_h)
        if docked:
            fr = _field_for(lay.map_area)
            left = pygame.Rect(0, 0, fr.left - FRAME_W - 3, classic_h)
            right = pygame.Rect(fr.right + FRAME_W + 3, 0, classic_w - fr.right - FRAME_W - 3, classic_h)
            lcols = [[[t] for t in texts]]
            rcols = [[[hp], [snd, pse]]]
            s = min(_fit_scale(left, lcols, 3), _fit_scale(right, rcols, 3))
            _place(left, lcols, s, 3)
            _place(right, rcols, s, 3)

    elif b == "TRIMMED":
        lay.win_w, lay.win_h = std_map_w, std_map_h
        lay.map_area = pygame.Rect(0, 0, std_map_w, std_map_h)

    else:  # DYNAMIC
        if h == "ON":
            lay.win_w, lay.win_h = map_w + zone_w, max(map_h, hud_min_h)
        else:
            lay.win_w, lay.win_h = map_w, map_h
        lay.map_area = pygame.Rect(0, 0, map_w, lay.win_h)

    # Окно растёт, чтобы вместить панели (DYNAMIC / TRIMMED)
    if docked and b in ("TRIMMED", "DYNAMIC"):
        ms = 8
        mh = map_h if b == "DYNAMIC" else std_map_h
        mw = map_w if b == "DYNAMIC" else std_map_w
        left_w = texts[0]["native"][0] + 2 * ms
        right_w = max(hp["native"][0], _item_size([snd, pse])[0]) + 2 * ms
        need_h = max(4 * texts[0]["native"][1] + 3 * GAP, hp["native"][1] + snd["native"][1] + GAP) + 2 * ms
        lay.win_h = max(mh, need_h)
        lay.win_w = left_w + mw + right_w
        lay.map_area = pygame.Rect(left_w, 0, mw, lay.win_h)
        _place(pygame.Rect(0, 0, left_w, lay.win_h), [[[t] for t in texts]], 1.0, ms)
        _place(pygame.Rect(lay.win_w - right_w, 0, right_w, lay.win_h), [[[hp], [snd, pse]]], 1.0, ms)

    lay.field_rect = _field_for(lay.map_area)

    if docked:
        lay.kind = "windows"
        lay.panels = texts + [hp, snd, pse]
    elif h == "OS_WINDOWS":
        lay.kind = "os"
        lay.os_borderless = os_borderless
        _build_os_panels(lay, texts, hp, snd, pse)
    elif h == "ON":
        lay.kind = "classic"
    else:
        lay.kind = "none"

    _cache[key] = lay
    return lay


def _build_os_panels(lay, texts, hp, snd, pse) -> None:
    # Самостоятельные окна ОС: rel
    mw, mh = lay.win_w, lay.win_h
    os_gap = OS_GAP_BORDERLESS if lay.os_borderless else OS_GAP
    v_gap = OS_V_GAP_BORDERLESS if lay.os_borderless else OS_V_GAP
    tw, th = texts[0]["native"]

    free = mh - 4 * th
    gap = max(v_gap, min(100, free // 5))
    y0 = (mh - (4 * th + 3 * gap)) // 2
    for i, t in enumerate(texts):
        lay.os_panels.append({"name": t["name"], "kind": "text", "idx": i, "size": t["native"],
                              "rel": (-(tw + os_gap), y0 + i * (th + gap))})

    hw, hh = hp["native"]
    iw, ih = snd["native"]
    right_x = mw + os_gap
    hp_y = max(0, (mh - (hh + v_gap + ih)) // 2) if mh > hh + OS_V_GAP + ih else 0
    lay.os_panels.append({"name": "HP", "kind": "hp", "idx": 0, "size": hp["native"], "model": lay.hp_model,
                          "rel": (right_x, hp_y)})
    ic_y = hp_y + hh + v_gap
    lay.os_panels.append({"name": "SOUNDS", "kind": "sound", "idx": 0, "size": snd["native"],
                          "rel": (right_x, ic_y)})
    lay.os_panels.append({"name": "PAUSE", "kind": "pause", "idx": 0, "size": pse["native"],
                          "rel": (right_x + iw + 16, ic_y)})


# отрисовка окон
def _draw_window(surface, rect: pygame.Rect) -> None:
    # Окно: фон + рамка по краю
    pygame.draw.rect(surface, settings.BACKGROUND_COLOR, rect)
    pygame.draw.rect(surface, BORDER_COLOR, rect, THICK)


def _blit_fit(surface, text_surf, center, max_w) -> None:
    if text_surf.get_width() > max_w > 0:
        k = max_w / text_surf.get_width()
        text_surf = pygame.transform.smoothscale(
            text_surf, (max_w, max(1, int(text_surf.get_height() * k))))
    surface.blit(text_surf, text_surf.get_rect(center=center))


def panel_texts(stats, custom_goal):
    # Тексты четырёх левых окон: [(строка1, строка2), ...]
    if custom_goal:
        goal = (str(custom_goal[0]), str(custom_goal[1]))
    else:
        goal = ("G O A L", f'{stats["kills_this_level"]}/{stats["target_enemies"]}')

    lvl = str(stats.get("level", 1))
    if stats.get("is_boss_phase") or lvl == "BOSS":
        level_line = "BOSS"
    elif level_to_int(stats.get("level")) is None:
        level_line = lvl  # любой свой текст: ENDLESS, MAZE
    else:
        level_line = f"LEVEL {lvl}"

    return [
        ("SCORE", str(stats["score"])),
        ("HI-SCORE", str(stats["hi_score"])),
        goal,
        (level_line, f'SPEED {stats["speed_multiplier"]:g}'),
    ]


def draw_text_panel(surface, font, rect: pygame.Rect, line1, line2) -> None:
    # Текстовое окно: рамка окна, а внутри на расстоянии 3 px
    C = settings.CELL_SIZE
    _draw_window(surface, rect)
    content = rect.inflate(-2 * M, -2 * M)
    _blit_fit(surface, font.render(line1, True, (0, 0, 0)), (content.centerx, content.top + C // 2), content.w)
    _blit_fit(surface, font.render(line2, True, (0, 0, 0)), (content.centerx, content.top + C + C // 2), content.w)


# Цвета клеток шкалы HP: {(x, y): (r, g, b)}
HP_CELL_COLORS: dict = {}


def hp_colors_key():
    # Ключ для кэша панелей: меняется, когда меняются цвета клеток шкалы
    return tuple(sorted(HP_CELL_COLORS.items()))


def draw_hp_panel(surface, rect: pygame.Rect, model, active_cells, pixel_img) -> None:
    # Окно HP: поле клеток без собственной обводки
    C = settings.CELL_SIZE
    _draw_window(surface, rect)
    ox, oy = rect.x + HP_M, rect.y + HP_M
    models.draw_smart_board(surface, model, ox, oy, pixel_img, outline=False)
    for x, y in active_cells:
        color = HP_CELL_COLORS.get((x, y))
        if color is not None and assets.PIXEL_COLOR_IMG_RAW is not None:
            surface.blit(assets.colorize_icon(assets.PIXEL_COLOR_IMG_RAW, (*color, 255)), (ox + x * C, oy + y * C))
        surface.blit(pixel_img, (ox + x * C, oy + y * C))


def draw_icon_panel(surface, rect: pygame.Rect, img) -> None:
    # Маленькое окошко с иконкой по центру (sounds / pause)
    _draw_window(surface, rect)
    surface.blit(img, img.get_rect(center=rect.center))


def drawn_field_rect(layout: Layout, board_px: pygame.Rect) -> pygame.Rect:
    # Прямоугольник реально отрисованного поля на экране: карта
    return board_px.inflate(2 * FIELD_PAD, 2 * FIELD_PAD).clip(layout.field_rect)


def draw_field_frame(screen, rect: pygame.Rect) -> None:
    # Рамка вокруг отрисованного поля такая же, как обводка поля в меню
    if rect.w > 0 and rect.h > 0:
        pygame.draw.rect(screen, BORDER_COLOR, rect, FRAME_W)
        inner = rect.inflate(-2 * FRAME_W, -2 * FRAME_W)
        if inner.w > 0 and inner.h > 0:
            pygame.draw.rect(screen, FIELD_BG, inner, PAD)


def _draw_scaled(screen, p, content_key, draw_fn) -> None:
    # Панель с масштабом < 1 рисуется в натуральную величину и ужимается
    rect = p["rect"]
    if p["scale"] >= 0.999:
        draw_fn(screen, rect)
        return
    key = (p["name"], content_key, rect.size)
    surf = _scaled_cache.get(key)
    if surf is None:
        if len(_scaled_cache) > 64:
            _scaled_cache.clear()
        nat = p["native"]
        tmp = pygame.Surface(nat)
        tmp.fill(settings.BACKGROUND_COLOR)
        draw_fn(tmp, pygame.Rect(0, 0, *nat))
        surf = pygame.transform.smoothscale(tmp, rect.size)
        _scaled_cache[key] = surf
    screen.blit(surf, rect.topleft)


def render_windows(screen, font, layout: Layout, stats, sound_img, paused, custom_goal, pixel_img, pause_img_on, pause_img_off) -> None:
    # HUD в рамочных панелях внутри окна игры (WINDOWS)
    texts = panel_texts(stats, custom_goal)
    cells = stats.get("hp_cells", [])
    pimg = pause_img_on if paused else pause_img_off
    hidden = stats.get("hide_panels") or ()
    for p in layout.panels:
        kind = p["kind"]
        if kind == "text":
            if p["name"] in hidden:
                continue  # панель скрыта режимом - не рисуем
            l1, l2 = texts[p["idx"]]
            _draw_scaled(screen, p, (l1, l2), lambda s, r, a=l1, b=l2: draw_text_panel(s, font, r, a, b))
        elif kind == "hp":
            hp_model = stats.get("hp_model") or layout.hp_model  # "сломанная" шкала подменяет модель
            _draw_scaled(screen, p, (tuple(cells), hp_model, hp_colors_key()), lambda s, r: draw_hp_panel(s, r, hp_model, cells, pixel_img))
        elif kind == "sound":
            _draw_scaled(screen, p, id(sound_img), lambda s, r: draw_icon_panel(s, r, sound_img))
        else:
            _draw_scaled(screen, p, id(pimg), lambda s, r: draw_icon_panel(s, r, pimg))
