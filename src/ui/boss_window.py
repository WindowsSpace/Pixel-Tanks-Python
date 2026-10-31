# Окна ОС для босса за краем поля и его пуль
import pygame

from core import assets, settings
from ui import hud, os_hud

REFRESH_MS = 500  # перерисовывать окна даже без изменений
MAX_BULLET_WINDOWS = 8  # сколько окон-пуль может быть одновременно


def _make_top_window(v, title, size, pos):
    # Безрамочное окно (без заголовка и кнопок) без значка в панели задач
    attempts = [
        dict(resizable=False, borderless=True, utility=True, always_on_top=True),
        dict(resizable=False, borderless=True, always_on_top=True),
        dict(resizable=False, borderless=True),
        dict(borderless=True),
        dict(),
    ]
    last = None
    for kw in attempts:
        try:
            win = v.Window(title, size=size, position=pos, **kw)
            try:
                win.always_on_top = True
            except Exception:
                pass
            return win
        except Exception as e:
            last = e
    raise last


class _Win:
    # Одно окно: окно ОС + рендерер + готовая текстура со статичным содержимым

    def __init__(self, v, title, logical, scale, pos, content) -> None:
        self._v = v
        self.logical = logical  # размер в логических px (без масштаба)
        self.px = max(8, int(logical * scale))
        self.win = _make_top_window(v, title, (self.px, self.px), pos)
        self.renderer = v.Renderer(self.win)
        surf = pygame.Surface((logical, logical))
        content(surf)
        if surf.get_size() != (self.px, self.px):
            surf = pygame.transform.scale(surf, (self.px, self.px))
        self.texture = v.Texture.from_surface(self.renderer, surf)
        self.pos = pos
        self.shown = True
        self.last = 0
        self.draw(pygame.time.get_ticks())

    def set_content(self, content) -> None:
        # Заменяет картинку окна (босс повернулся), не пересоздавая окно ОС
        surf = pygame.Surface((self.logical, self.logical))
        content(surf)
        if surf.get_size() != (self.px, self.px):
            surf = pygame.transform.scale(surf, (self.px, self.px))
        self.texture = self._v.Texture.from_surface(self.renderer, surf)
        self.draw(pygame.time.get_ticks())

    def draw(self, now) -> None:
        self.renderer.clear()
        self.texture.draw()
        self.renderer.present()
        self.last = now

    def move(self, pos) -> None:
        if pos != self.pos:
            self.win.position = pos
            self.pos = pos

    def show(self, now) -> None:
        if not self.shown:
            self.win.show()
            self.shown = True
            self.draw(now)

    def hide(self) -> None:
        if self.shown:
            self.win.hide()
            self.shown = False

    def destroy(self) -> None:
        self.texture = None  # сначала текстура и рендерер, затем окно (как в os_hud)
        self.renderer = None
        try:
            self.win.destroy()
        except Exception:
            pass


class BossWindow:
    def __init__(self) -> None:
        self.disabled = False
        self.boss = None  # _Win босса
        self.boss_key = None
        self.bullets = []  # пул _Win для пуль
        self.scale = None

    def has_windows(self) -> bool:
        return self.boss is not None or bool(self.bullets)

    # жизненный цикл
    def close(self) -> None:
        for w in ([self.boss] if self.boss else []) + self.bullets:
            w.destroy()
        self.boss = None
        self.boss_key = None
        self.bullets = []

    def _fail(self, where: str) -> None:
        os_hud.log_error("boss window: " + where)
        self.close()
        self.disabled = True  # больше не пробуем: без окон бой идёт как обычно

    # раз в кадр
    def frame(self, info, bullet_cells, scale, cell_px, monitor, fullscreen=False) -> None:
        # info - (картинка босса, центр клетки gx, gy) или None; bullet_cells
        if self.disabled:
            return
        if fullscreen or (info is None and not bullet_cells):
            if self.has_windows():
                self._hide_or_close(fullscreen)
            return
        try:
            self._frame(info, bullet_cells or [], scale, cell_px, monitor)
        except Exception:
            self._fail("frame")

    def _hide_or_close(self, fullscreen) -> None:
        if fullscreen:
            self.close()
            return
        now = pygame.time.get_ticks()
        if self.boss is not None:  # босс вернулся на поле: окно закрываем, оно создаётся быстро
            self.boss.destroy()
            self.boss, self.boss_key = None, None
        for w in self.bullets:  # окна пуль остаются в пуле спрятанными
            w.hide()

    @staticmethod
    def _place(logical, scale, cell_px, gx, gy, monitor, px):
        # Левый верхний угол окна на экране: окно центрировано на клетке (gx, gy)
        C = settings.CELL_SIZE
        lx, ly = cell_px(gx, gy)
        cx, cy = lx + C / 2.0, ly + C / 2.0
        x = int(main_pos()[0] + (cx - logical / 2.0) * scale)
        y = int(main_pos()[1] + (cy - logical / 2.0) * scale)
        return max(0, min(x, monitor[0] - px)), max(0, min(y, monitor[1] - px))

    def _frame(self, info, bullet_cells, scale, cell_px, monitor) -> None:
        if not hud.os_available():
            self.disabled = True
            return
        v = os_hud._video()
        if v is None:
            self.disabled = True
            return
        main = os_hud._main_ref if os_hud._main_ref is not None else os_hud._main_window(v)
        if self.scale is not None and abs(self.scale - scale) > 1e-6:
            self.close()  # масштаб игры изменился - окна пересоздаются под него
        self.scale = scale
        now = pygame.time.get_ticks()
        C, M = settings.CELL_SIZE, hud.M
        new_shown = False

        # босс
        if info is not None:
            image, gx, gy = info
            logical = 3 * C + 2 * M
            key = id(image)

            def content(surf, image=image):
                rect = surf.get_rect()
                hud._draw_window(surf, rect)  # та же рамка, что у окон HUD и окна игры
                surf.blit(image, image.get_rect(center=rect.center))

            if self.boss is not None and self.boss_key != key:
                self.boss.set_content(content)  # повернулся - меняем только картинку
                self.boss_key = key
            if self.boss is None:
                px = max(8, min(int(logical * scale), monitor[0] // 2, monitor[1] // 2))
                pos = self._place(logical, scale, cell_px, gx, gy, monitor, px)
                self.boss = _Win(v, "Y0U", logical, scale, pos, content)
                self.boss_key = key
                new_shown = True
            else:
                self.boss.move(self._place(logical, scale, cell_px, gx, gy, monitor, self.boss.px))
                if now - self.boss.last >= REFRESH_MS:
                    self.boss.draw(now)
        elif self.boss is not None:
            self.boss.destroy()
            self.boss, self.boss_key = None, None

        # пули
        cells = list(bullet_cells)[:MAX_BULLET_WINDOWS]
        logical = C + 2 * M
        for i, (gx, gy) in enumerate(cells):
            if i >= len(self.bullets):
                px = max(8, int(logical * scale))
                pos = self._place(logical, scale, cell_px, gx, gy, monitor, px)

                def content(surf):
                    rect = surf.get_rect()
                    hud._draw_window(surf, rect)
                    cell = assets.BLACK_CELL_IMG
                    if cell is not None:
                        surf.blit(cell, cell.get_rect(center=rect.center))

                self.bullets.append(_Win(v, "", logical, scale, pos, content))
                new_shown = True
            else:
                w = self.bullets[i]
                was_hidden = not w.shown
                w.move(self._place(logical, scale, cell_px, gx, gy, monitor, w.px))
                w.show(now)
                new_shown = new_shown or was_hidden
                if now - w.last >= REFRESH_MS:
                    w.draw(now)
        for w in self.bullets[len(cells):]:
            w.hide()

        if new_shown:
            try:
                main.focus()  # клавиатура остаётся у игры
            except Exception:
                pass


def main_pos():
    # Положение клиентской области главного окна игры на экране
    return tuple(os_hud._main_ref.position) if os_hud._main_ref is not None else (0, 0)


WINDOW = BossWindow()
