# Финал D01: игрок и его пули - отдельные безрамочные окна ОС
import pygame

from core import assets, settings
from core.settings import DIR_DOWN, DIR_LEFT, DIR_RIGHT, DIR_TO_ANGLE, DIR_UP
from entities.blocks import color_cell_image
from ui import hud, os_hud
from ui.boss_window import _Win, main_pos

BULLET_STEP_MS = 90  # пуля шагает ровно на клетку раз в столько мс
MAX_SHOTS = 3  # пуль-окон одновременно
FIRE_COOLDOWN_MS = 500  # перезарядка выстрела игрока в финале (спамом босса не убить)
RAISE_EVERY_MS = 250  # как часто окна заново "прижимаются" поверх остальных

_VEC = {DIR_UP: (0, -1), DIR_DOWN: (0, 1), DIR_LEFT: (-1, 0), DIR_RIGHT: (1, 0)}


class FinalWindows:
    def __init__(self) -> None:
        self.disabled = False
        self.player = None
        self.pos = None  # левый верхний угол окна игрока, float (экранные px)
        self.face = DIR_UP
        self.face_key = None
        self.shots = []  # {"win", "x", "y", "dx", "dy", "t"}
        self.pool = []  # свободные окна-пули
        self.scale = None
        self.last_ms = None
        self.pending = []  # запросы выстрела (цвет пули или None)
        self.cell = None  # клетка игрока [cx, cy] в координатах карты
        self.step_t = 0.0  # секунд с последнего шага
        self.prev_dir = None
        self.last_fire = -10 ** 9
        self.last_raise = 0
        self.main_size = None  # размер главного окна: когда оно меняется (финал сжимает его)

    def has_windows(self) -> bool:
        return self.player is not None or bool(self.shots) or bool(self.pool)

    def request_fire(self, color=None) -> None:
        now = pygame.time.get_ticks()
        if self.pending or now - self.last_fire < FIRE_COOLDOWN_MS:
            return  # перезарядка: быстрый спам не накапливается
        self.last_fire = now
        self.pending.append(color)

    def _raise_all(self, now) -> None:
        # Окна игрока и пуль всегда поверх остальных (в том числе поверх окна игры)
        for w in [self.player] + [s["win"] for s in self.shots] + self.pool:
            if w is not None and w.shown:
                try:
                    w.win.always_on_top = True
                except Exception:
                    pass
        self.last_raise = now

    def close(self) -> None:
        for w in [self.player] + [s["win"] for s in self.shots] + self.pool:
            if w is not None:
                w.destroy()
        self.player, self.shots, self.pool, self.pending = None, [], [], []
        self.pos, self.scale, self.last_ms, self.face_key = None, None, None, None
        self.cell, self.step_t, self.prev_dir = None, 0.0, None

    def reset(self) -> None:
        # Новая игра: можно снова пробовать окна
        self.close()
        self.disabled = False

    def frame(self, held_dirs, field_cells, scale, cell_px, monitor, fullscreen, player_img, paused=False) -> bool:
        # held_dirs - зажатые направления; field_cells
        if self.disabled or fullscreen:
            if fullscreen:
                self.disabled = True
            return False
        try:
            return self._frame(held_dirs, field_cells, scale, cell_px, monitor, player_img, paused)
        except Exception:
            self.disabled = True
            try:
                self.close()
            except Exception:
                pass
            return False

    def _frame(self, held_dirs, field_cells, scale, cell_px, monitor, player_img, paused=False) -> bool:
        if not hud.os_available():
            self.disabled = True
            return False
        v = os_hud._video()
        if v is None:
            self.disabled = True
            return False
        main = os_hud._main_ref if os_hud._main_ref is not None else os_hud._main_window(v)
        if self.scale is not None and abs(self.scale - scale) > 1e-6:
            self.close()
        self.scale = scale
        C, M = settings.CELL_SIZE, hud.M
        now = pygame.time.get_ticks()
        dt = 0.0 if self.last_ms is None else min(0.05, (now - self.last_ms) / 1000.0)
        self.last_ms = now
        if paused:  # пауза: игрок стоит, пули замерли, выстрелы не копятся
            dt = 0.0
            held_dirs = []
            self.pending.clear()
            self.prev_dir, self.step_t = None, 0.0
        try:
            msz = main.size
        except Exception:
            msz = None
        size_changed = msz != self.main_size
        self.main_size = msz

        # прямоугольник поля босса на экране
        x0, y0, w, h = field_cells
        lx, ly = cell_px(x0, y0)
        mx, my = main_pos()
        field = pygame.Rect(int(mx + lx * scale), int(my + ly * scale), int(w * C * scale), int(h * C * scale))

        # игрок
        logical = 3 * C + 2 * M
        px = max(8, int(logical * scale))
        cs = C * scale  # клетка на экране (px)
        c0x, c0y = cell_px(0, 0)
        ox, oy = mx + c0x * scale, my + c0y * scale  # левый верхний угол клетки (0, 0) карты на экране

        if self.cell is None:  # старт: под полем босса, по центру
            self.cell = [x0 + w // 2, y0 + h + 3]
            self.step_t, self.prev_dir = 0.0, None

        # ходит как обычный танк: нажатие в другую сторону - только поворот
        step_s = settings.PLAYER_MOVE_DELAY_MS / 1000.0
        d = held_dirs[-1] if held_dirs else None
        stepped = False
        if d is None:
            self.prev_dir, self.step_t = None, 0.0
        else:
            if d != self.prev_dir:
                self.prev_dir = d
                if self.face == d:
                    self.step_t = step_s  # нажал в ту же сторону - шаг сразу
                else:
                    self.face, self.step_t = d, 0.0  # повернулся на месте
            self.step_t += dt
            if self.step_t >= step_s:
                self.step_t = 0.0
                stepped = True
        if stepped:
            self.cell[0] += _VEC[self.face][0]
            self.cell[1] += _VEC[self.face][1]
        # окно не должно уехать за экран: границы в клетках
        min_cx = int(-(-((px / 2.0 - ox) / cs - 0.5) // 1))
        max_cx = int(((monitor[0] - px / 2.0 - ox) / cs - 0.5) // 1)
        min_cy = int(-(-((px / 2.0 - oy) / cs - 0.5) // 1))
        max_cy = int(((monitor[1] - px / 2.0 - oy) / cs - 0.5) // 1)
        self.cell[0] = max(min_cx, min(self.cell[0], max_cx))
        self.cell[1] = max(min_cy, min(self.cell[1], max_cy))
        key = (self.face, id(player_img))

        def content(surf):
            rect = surf.get_rect()
            hud._draw_window(surf, rect)
            if player_img is not None:
                img = pygame.transform.rotate(player_img, DIR_TO_ANGLE[self.face])
                surf.blit(img, img.get_rect(center=rect.center))

        self.pos = [ox + (self.cell[0] + 0.5) * cs - px / 2.0, oy + (self.cell[1] + 0.5) * cs - px / 2.0]
        new_shown = False
        if self.player is None:
            self.player = _Win(v, "", logical, scale, (int(self.pos[0]), int(self.pos[1])), content)
            self.face_key = key
            new_shown = True
        elif self.face_key != key:
            self.player.set_content(content)
            self.face_key = key
        px = self.player.px
        self.player.move((int(self.pos[0]), int(self.pos[1])))
        if now - self.player.last >= 500:
            self.player.draw(now)

        # выстрелы
        bl = C + 2 * M
        bpx = max(8, int(bl * scale))
        while self.pending:
            color = self.pending.pop(0)
            if len(self.shots) >= MAX_SHOTS:
                continue
            dx, dy = _VEC[self.face]
            # пуля стартует в клетке сразу перед корпусом
            cx = ox + (self.cell[0] + dx * 2 + 0.5) * cs
            cy = oy + (self.cell[1] + dy * 2 + 0.5) * cs

            def bcontent(surf, color=color):
                rect = surf.get_rect()
                hud._draw_window(surf, rect)
                img = color_cell_image(color) if color else assets.PIXEL_IMG_RAW
                surf.blit(img, img.get_rect(center=rect.center))

            pos = (int(cx - bpx / 2), int(cy - bpx / 2))
            win = self.pool.pop() if self.pool else None
            if win is None:
                win = _Win(v, "", bl, scale, pos, bcontent)
                new_shown = True
            else:
                win.set_content(bcontent)
                win.move(pos)
                win.show(now)
            self.shots.append({"win": win, "x": cx - bpx / 2, "y": cy - bpx / 2, "dx": dx, "dy": dy, "t": 0.0})

        hit = False
        for s in list(self.shots):
            s["t"] += dt * 1000.0
            while s["t"] >= BULLET_STEP_MS:  # шаг ровно на клетку, как у обычной пули
                s["t"] -= BULLET_STEP_MS
                s["x"] += s["dx"] * cs
                s["y"] += s["dy"] * cs
            win = s["win"]
            rect = pygame.Rect(int(s["x"]), int(s["y"]), win.px, win.px)
            win.move((rect.x, rect.y))
            if now - win.last >= 500:
                win.draw(now)
            if rect.colliderect(field):
                hit = True
            if hit or rect.right < 0 or rect.bottom < 0 or rect.x > monitor[0] or rect.y > monitor[1]:
                win.hide()
                self.pool.append(win)
                self.shots.remove(s)
        if new_shown or size_changed or now - self.last_raise >= RAISE_EVERY_MS:
            self._raise_all(now)  # всегда поверх остальных окон
        if new_shown:
            try:
                main.focus(input_only=True)  # клавиатура остаётся у игры
            except TypeError:
                try:
                    main.focus()
                except Exception:
                    pass
            except Exception:
                pass
            self._raise_all(now)
        return hit


FINAL = FinalWindows()
