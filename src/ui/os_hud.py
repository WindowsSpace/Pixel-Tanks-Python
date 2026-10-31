# Самостоятельные окна ОС для HUD (параметр hud = "OS_WINDOWS")
import os
import time
import traceback

import pygame

from core import settings
from ui import hud

REFRESH_MS = 500  # перерисовывать окно даже без изменений
SETTLE_STABLE = 4  # сколько кадров подряд главное окно должно стоять на месте
SETTLE_SIZE_WAIT = 20  # столько кадров ждём, пока главное окно примет нужный размер
SETTLE_MAX = 90  # предельное ожидание (около 1.5 с)
DECO_X = 14  # запас на рамки окон ОС по горизонтали (с каждой стороны)
DECO_TOP = 40  # запас на заголовок окна ОС
DECO_BOTTOM = 16
BARE_DECO = 2  # то же для окон без рамки ОС (borderless)
TASKBAR = 48  # запас снизу под панель задач
ICON_EXTS = (".png", ".ico", ".bmp", ".jpg", ".jpeg")


LOG_FILE = "os_hud_error.log"

_main_ref = None  # обёртка главного окна ДОЛЖНА жить всё время работы игры


def _video():
    try:
        import pygame._sdl2.video as video
        return video
    except Exception:
        return None


def _main_window(v):
    # Обёртка главного окна игры (Window.from_display_module)
    global _main_ref
    new = v.Window.from_display_module()
    _main_ref = new
    return new


def log_error(where: str) -> None:
    # Пишет текущее исключение в консоль и в файл os_hud_error.log рядом с игрой
    text = f"[os_hud] {where}\n{traceback.format_exc()}"
    try:
        print(text)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + text + "\n")
    except Exception:
        pass


# иконки окон
_icon_cache: dict = {}


def _load_file(path):
    try:
        if path and os.path.isfile(path):
            return pygame.image.load(path)
    except Exception:
        pass
    return None


def _fallback_icon() -> pygame.Surface:
    # Простая иконка в стиле игры (если нет ни своей, ни иконки игры)
    s = pygame.Surface((32, 32))
    s.fill(settings.BACKGROUND_COLOR)
    pygame.draw.rect(s, hud.BORDER_COLOR, (0, 0, 32, 32), 3)
    for x in (7, 18):
        for y in (7, 18):
            pygame.draw.rect(s, hud.BORDER_COLOR, (x, y, 7, 7))
    return s


def resolve_icon(name, overrides=None):
    # Иконка окна по имени
    overrides = overrides or {}
    key = (name, tuple(sorted((str(k), str(v)) for k, v in overrides.items())))
    if key in _icon_cache:
        return _icon_cache[key]

    surf = None
    low = name.lower()
    sources = [overrides.get(name), overrides.get(low), overrides.get("*"),
               getattr(settings, "OS_WINDOW_ICONS", {}).get(name),
               getattr(settings, "OS_WINDOW_ICONS", {}).get(low),
               getattr(settings, "OS_WINDOW_ICONS", {}).get("*")]
    for src in sources:
        if isinstance(src, pygame.Surface):
            surf = src
        elif isinstance(src, str):
            surf = _load_file(src)
        if surf is not None:
            break

    if surf is None:
        folder = getattr(settings, "OS_ICON_DIR", "assets/sprites/os_icons")
        for base in (low, "default"):
            for ext in ICON_EXTS:
                surf = _load_file(os.path.join(folder, base + ext))
                if surf is not None:
                    break
            if surf is not None:
                break

    if surf is None:
        surf = _load_file(getattr(settings, "GAME_ICON", "assets/PT64ALT.ico"))
    if surf is None:
        surf = _fallback_icon()
    _icon_cache[key] = surf
    return surf


class OSHud:
    def __init__(self) -> None:
        self.v = _video()
        self.items: dict = {}
        self.signature = None
        self.user_closed: set = set()
        self._settle_last = None  # (позиция, размер) главного окна на прошлом кадре ожидания
        self._settle_stable = 0
        self._settle_waited = 0
        self.anchor = None  # положение главного окна, к которому привязаны окна HUD

    # жизненный цикл
    def available(self) -> bool:
        return self.v is not None and hud.os_available()

    def close_all(self) -> None:
        for it in list(self.items.values()):
            self._destroy(it)
        self.items.clear()
        self.signature = None
        self.user_closed.clear()
        self.anchor = None

    def main_changed(self) -> None:
        # Вызывается ПЕРЕД изменением главного окна (размер/режим)
        self.close_all()
        self._settle_last, self._settle_stable, self._settle_waited = None, 0, 0

    def _main_settled(self, layout, scale) -> bool:
        # Главное окно готово: размер принят
        try:
            main = _main_window(self.v)
            state = (tuple(main.position), tuple(main.size))
        except Exception:
            return True
        self._settle_waited += 1
        if state == self._settle_last:
            self._settle_stable += 1
        else:
            self._settle_last, self._settle_stable = state, 0
        exp_w, exp_h = int(layout.win_w * scale), int(layout.win_h * scale)
        size_ok = abs(state[1][0] - exp_w) <= 2 and abs(state[1][1] - exp_h) <= 2
        done = self._settle_stable >= SETTLE_STABLE and (size_ok or self._settle_waited >= SETTLE_SIZE_WAIT)
        return done or self._settle_waited >= SETTLE_MAX

    def _follow_main(self) -> None:
        # Окна HUD едут вместе с главным окном (если его сдвинули мышью или ОС)
        if self.anchor is None or _main_ref is None:
            return
        try:
            pos = tuple(_main_ref.position)
        except Exception:
            return
        if pos != self.anchor:
            dx, dy = pos[0] - self.anchor[0], pos[1] - self.anchor[1]
            for it in self.items.values():
                try:
                    x, y = it["window"].position
                    it["window"].position = (x + dx, y + dy)
                except Exception:
                    pass
            self.anchor = pos

    @staticmethod
    def _destroy(it) -> None:
        # сначала текстура и рендерер (иначе они освободятся уже после окна)
        it["texture"] = None
        it["renderer"] = None
        try:
            it["window"].destroy()
        except Exception:
            pass

    def fail(self, where: str) -> None:
        # Любая ошибка в окнах ОС не должна ронять игру: логируем
        log_error(where)
        self.close_all()
        hud.disable_os_windows()

    def handle_event(self, event):
        # Событие закрытия окна: "hud" - закрыто одно из HUD-окон
        close_type = getattr(pygame, "WINDOWCLOSE", None)
        if close_type is None or event.type != close_type:
            return None
        win = getattr(event, "window", None)
        for name, it in list(self.items.items()):
            if win is not None and (it["window"] is win or it["window"] == win):
                self._destroy(it)
                del self.items[name]
                self.user_closed.add(name)
                return "hud"
        return "main"

    # создание окон
    def sync(self, layout, scale, monitor, fullscreen=False, icons=None) -> bool:
        # Создаёт/пересоздаёт окна, когда изменилась раскладка, масштаб
        if not self.available():
            return False
        try:
            return self._sync(layout, scale, monitor, fullscreen, icons)
        except Exception:
            self.fail("sync")
            return False

    def _sync(self, layout, scale, monitor, fullscreen, icons) -> bool:

        icons = icons or {}
        borderless = bool(getattr(layout, "os_borderless", False))
        deco_x, deco_top, deco_bottom = ((BARE_DECO,) * 3) if borderless else (DECO_X, DECO_TOP, DECO_BOTTOM)
        sig = (borderless, tuple((p["name"], p["size"], p["rel"]) for p in layout.os_panels),
               round(scale, 3), layout.win_w, layout.win_h, tuple(monitor), bool(fullscreen),
               tuple(sorted((str(k), str(v)) for k, v in icons.items())))
        if sig == self.signature:
            return True

        if self.signature is not None or self.items:
            self.close_all()  # раскладка изменилась - пересоздаём
        if not self._main_settled(layout, scale):
            return False  # сначала главное окно должно принять итоговый вид
        self._settle_last, self._settle_stable, self._settle_waited = None, 0, 0
        v = self.v
        mon_w, mon_h = monitor

        main = None
        mx, my, mw, mh = 80, 80, int(layout.win_w * scale), int(layout.win_h * scale)
        try:
            main = _main_window(v)
            mx, my = main.position
            mw, mh = main.size
        except Exception:
            main = None

        # размеры и смещения окон HUD (в физических пикселях)
        specs = []
        for p in layout.os_panels:
            w, h = p["size"]
            s = min(scale, (mon_w - 80) / w, (mon_h - 140) / h)  # окно не больше экрана
            pw, ph = max(1, int(w * s)), max(1, int(h * s))
            specs.append((p, pw, ph, int(p["rel"][0] * scale), int(p["rel"][1] * scale)))

        # вся группа (главное окно + HUD-окна с рамками ОС) должна поместиться
        if specs and not fullscreen:
            gl = min(0, min(rx for _, _, _, rx, _ in specs)) - deco_x
            gr = max(mw, max(rx + pw for _, pw, _, rx, _ in specs)) + deco_x
            gt = min(-deco_top, min(ry - deco_top for _, _, _, _, ry in specs))
            gb = max(mh, max(ry + ph for _, _, ph, _, ry in specs)) + deco_bottom
            nx, ny = mx, my
            if gr - gl > mon_w:
                nx = (mon_w - (gr - gl)) // 2 - gl
            elif mx + gl < 0:
                nx = -gl
            elif mx + gr > mon_w:
                nx = mon_w - gr
            if gb - gt > mon_h - TASKBAR:
                ny = -gt
            elif my + gt < 0:
                ny = -gt
            elif my + gb > mon_h - TASKBAR:
                ny = mon_h - TASKBAR - gb
            if (nx, ny) != (mx, my) and main is not None:
                try:
                    main.position = (nx, ny)
                    mx, my = nx, ny
                except Exception:
                    pass

        try:
            for p, pw, ph, rx, ry in specs:
                x = max(0, min(mx + rx, mon_w - pw))
                y = max(deco_top, min(my + ry, mon_h - ph - deco_bottom))
                win = self._make_window(v, p["name"], (pw, ph), (x, y), fullscreen, borderless)
                try:
                    win.set_icon(resolve_icon(p["name"], icons))  # свой значок вместо стандартного
                except Exception:
                    pass
                renderer = v.Renderer(win)
                self.items[p["name"]] = {
                    "window": win, "renderer": renderer, "texture": None,
                    "panel": p, "px": (pw, ph),
                    "key": None, "last": 0.0,
                }
        except Exception:
            # окна не поддерживаются на этой системе: возвращаем HUD внутрь окна игры
            self.fail("create windows")
            return False

        self.signature = sig
        self.anchor = (mx, my)
        try:
            pygame.mouse.set_visible(False)  # курсор над HUD-окнами не показываем
        except Exception:
            pass
        if main is not None:
            try:
                main.focus()  # клавиатура остаётся у игры
            except Exception:
                pass
        return True

    @staticmethod
    def _make_window(v, title, size, pos, fullscreen, borderless=False):
        attempts = []
        if borderless:  # окно без рамки ОС: без заголовка
            attempts += [
                dict(resizable=False, borderless=True, utility=True, always_on_top=bool(fullscreen)),
                dict(resizable=False, borderless=True),
                dict(borderless=True),
            ]
        attempts += [
            dict(resizable=False, utility=True, always_on_top=bool(fullscreen)),
            dict(resizable=False),
            dict(),
        ]
        last = None
        for kw in attempts:
            try:
                return v.Window(title, size=size, position=pos, **kw)
            except Exception as e:  # старые сборки не знают часть флагов
                last = e
        raise last

    # обновление
    def update(self, font, stats, custom_goal, paused, sound_img, pixel_img, pause_on, pause_off) -> None:
        if not self.items:
            return
        try:
            self._update(font, stats, custom_goal, paused, sound_img, pixel_img, pause_on, pause_off)
        except Exception:
            self.fail("update")

    def _update(self, font, stats, custom_goal, paused, sound_img, pixel_img, pause_on, pause_off) -> None:
        self._follow_main()
        v = self.v
        texts = hud.panel_texts(stats, custom_goal)
        cells = tuple(sorted(tuple(c) for c in stats.get("hp_cells", [])))
        now = time.monotonic()

        hidden = stats.get("hide_panels") or ()
        for name, it in list(self.items.items()):
            p = it["panel"]
            kind = p["kind"]
            if name in hidden:  # скрытое окно: прячем и не рисуем
                if not it.get("hidden"):
                    try:
                        it["window"].hide()
                        it["hidden"] = True
                    except Exception:
                        pass
                continue
            if it.get("hidden"):
                try:
                    it["window"].show()
                    it["hidden"] = False
                    it["key"] = None
                except Exception:
                    pass
            if kind == "text":
                key = texts[p["idx"]]
            elif kind == "hp":
                key = ("hp", stats.get("hp_model") or p["model"], cells, hud.hp_colors_key())
            elif kind == "sound":
                key = ("sound", id(sound_img))
            else:
                key = ("pause", bool(paused))

            changed = key != it["key"]
            if not changed and (now - it["last"]) * 1000 < REFRESH_MS:
                continue

            try:
                if changed or it["texture"] is None:
                    w, h = p["size"]
                    surf = pygame.Surface((w, h))
                    surf.fill(settings.BACKGROUND_COLOR)
                    rect = pygame.Rect(0, 0, w, h)
                    if kind == "text":
                        hud.draw_text_panel(surf, font, rect, key[0], key[1])
                    elif kind == "hp":
                        hud.draw_hp_panel(surf, rect, stats.get("hp_model") or p["model"], cells, pixel_img)
                    elif kind == "sound":
                        hud.draw_icon_panel(surf, rect, sound_img)
                    else:
                        hud.draw_icon_panel(surf, rect, pause_on if paused else pause_off)
                    if it["px"] != (w, h):
                        surf = pygame.transform.scale(surf, it["px"])
                    it["texture"] = v.Texture.from_surface(it["renderer"], surf)
                    it["key"] = key

                it["renderer"].clear()
                it["texture"].draw()
                it["renderer"].present()
                it["last"] = now
            except Exception:
                # одно окно сломалось - убираем его, остальные продолжают работать
                self._destroy(it)
                del self.items[name]
                self.user_closed.add(name)
