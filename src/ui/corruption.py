# Хэллоуинское событие: "сбой игры" после выставления полностью чёрного

import math
import os
import random

import pygame

from core import assets
from core.settings import CELL_SIZE

# НАСТРОЙКИ
EVENT_TITLE = "Pixel Tanks has stopped working"
EVENT_MESSAGE = (
    "Fatal error 0xB1ACC7A4 in module TANK.\n\n"
    "The tank was painted black. It has noticed.\n\n"
    "Settings of this module have been [REDACTED].\n"
    "The game will now close."
)
EVENT_ICON = "error"  # иконка окна: "info" (i) | "warn" (!) | "error" (крестик)
EVENT_BUTTON = "OK"  # подпись кнопки

# После события меню открывается на D01: один раз
OPEN_D01_EVERY_LAUNCH = False

# Поведение "ожившего" танка
TURN_MIN_MS = 400  # как часто танк меняет направление (в начале события)
TURN_MAX_MS = 750  # ...со временем интервалы сокращаются (до 40 % от исходных)
JITTER_PX = 5  # дрожание танка при поворотах (0 - выключить)

# Чёрные клетки: во сколько раз число клеток за секунду может отличаться
CELLS_MIN_FACTOR = 0.3
CELLS_MAX_FACTOR = 1.7

FALLBACK_LENGTH_MS = 20000  # длина события, если файл Redacted.ogg не найден
END_GRACE_MS = 3000  # максимум ожидания конца аудио после расчётной длины
_ANGLES = (0, -90, 180, 90)  # вверх, вправо, вниз, влево (как DIR_TO_ANGLE)


class TankCorruption:
    # Состояние и отрисовка события. Создаётся в момент, когда цвет стал чёрным

    def __init__(self, tank_surface, screen_size, sound) -> None:
        self.tank = tank_surface
        self.sound = sound
        self.length_ms = int(sound.get_length() * 1000) if sound else FALLBACK_LENGTH_MS
        self.channel = sound.play() if sound else None

        self.elapsed = 0
        self.finished = False

        # "живой" танк
        self.angle = 0
        self.jitter = (0, 0)
        self.turn_timer = 0

        # чёрные клетки на весь экран, в случайном порядке
        cols = math.ceil(screen_size[0] / CELL_SIZE)
        rows = math.ceil(screen_size[1] / CELL_SIZE)
        self.cells = [(c, r) for r in range(rows) for c in range(cols)]
        random.shuffle(self.cells)
        self.shown = 0
        self.total_ticks = max(1, self.length_ms // 1000)
        self.tick = 0
        self._cell_img = None

    # логика
    def update(self, dt_ms) -> None:
        if self.finished:
            return
        self.elapsed += dt_ms
        progress = min(1.0, self.elapsed / max(1, self.length_ms))

        # танк: поворот в случайную сторону, интервалы всё короче
        self.turn_timer -= dt_ms
        if self.turn_timer <= 0:
            self.angle = random.choice([a for a in _ANGLES if a != self.angle])
            self.turn_timer = random.randint(TURN_MIN_MS, TURN_MAX_MS) * (1.0 - 0.6 * progress)
            j = JITTER_PX
            self.jitter = (random.randint(-j, j), random.randint(-j, j)) if j and random.random() < 0.5 else (0, 0)

        # клетки: раз в секунду - случайная порция
        while self.tick < self.total_ticks and self.elapsed >= (self.tick + 1) * 1000:
            self.tick += 1
            self._reveal_batch()

        if self.elapsed >= self.length_ms:
            self.shown = len(self.cells)
            busy = self.channel is not None and self.channel.get_busy()
            if not busy or self.elapsed >= self.length_ms + END_GRACE_MS:
                self.finished = True

    def _reveal_batch(self) -> None:
        left = len(self.cells) - self.shown
        ticks_left = self.total_ticks - self.tick + 1  # считая текущую секунду
        if left <= 0:
            return
        if ticks_left <= 1:
            n = left
        else:
            avg = left / ticks_left
            n = random.randint(max(1, int(avg * CELLS_MIN_FACTOR)), max(1, int(avg * CELLS_MAX_FACTOR)))
            n = min(n, left - (ticks_left - 1))  # каждой оставшейся секунде - хотя бы клетка
            n = max(1, n)
        self.shown += n

    # отрисовка
    def draw_tank(self, surface, topleft) -> None:
        # Танк игрока в области превью 3x3
        img = pygame.transform.rotate(self.tank, self.angle)
        size = 3 * CELL_SIZE
        rect = img.get_rect(center=(topleft[0] + size // 2 + self.jitter[0],
                                    topleft[1] + size // 2 + self.jitter[1]))
        surface.blit(img, rect)

    def _get_cell_img(self) -> pygame.Surface:
        if self._cell_img is None:
            img = pygame.Surface((CELL_SIZE, CELL_SIZE), pygame.SRCALPHA)
            black = (0, 0, 0, 255)
            if assets.PIXEL_COLOR_IMG_RAW:
                img.blit(assets.colorize_icon(assets.PIXEL_COLOR_IMG_RAW, black), (0, 0))
            if assets.PIXEL_IMG_RAW:
                img.blit(assets.colorize_icon(assets.PIXEL_IMG_RAW, black), (0, 0))
            if not (assets.PIXEL_COLOR_IMG_RAW or assets.PIXEL_IMG_RAW):
                img.fill(black)
            self._cell_img = img
        return self._cell_img

    def draw_overlay(self, surface) -> None:
        # Чёрные клетки поверх всего экрана
        img = self._get_cell_img()
        for c, r in self.cells[:self.shown]:
            surface.blit(img, (c * CELL_SIZE, r * CELL_SIZE))


def show_system_message(title=EVENT_TITLE, message=EVENT_MESSAGE, icon=EVENT_ICON, button=EVENT_BUTTON) -> None:
    # Системное окно (блокирует, пока его не закроют)
    try:
        from pygame._sdl2 import messagebox
        messagebox(title, message, info=(icon == "info"), warn=(icon == "warn"),
                   error=(icon == "error"), buttons=(button,))
        return
    except Exception:
        pass
    if os.name == "nt":
        try:
            import ctypes
            flags = {"info": 0x40, "warn": 0x30, "error": 0x10}.get(icon, 0x40)  # MB_ICON*
            ctypes.windll.user32.MessageBoxW(None, message, title, flags)
            return
        except Exception:
            pass
    print(f"[{title}]\n{message}")
