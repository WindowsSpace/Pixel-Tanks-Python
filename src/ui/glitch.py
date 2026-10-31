# Дешёвый "шейдер" повреждения на CPU

import random

import pygame

# НАСТРОЙКИ
START_CHANCE_BASE = 0.010  # шанс начала глитча за кадр при strength = 0
START_CHANCE_GAIN = 0.080
FRAMES_MIN, FRAMES_MAX = 2, 5  # сколько кадров длится глитч
BAND_H_MIN, BAND_H_MAX = 6, 45  # высота полосы, px
SHIFT_MIN, SHIFT_GAIN = 8, 60  # сдвиг полосы: от SHIFT_MIN до SHIFT_MIN + SHIFT_GAIN *
INVERT_CHANCE_GAIN = 0.30  # шанс инверсии полосы = INVERT_CHANCE_GAIN * strength

class Glitch:
    def __init__(self) -> None:
        self.frames_left = 0
        self.bands = []
        self._band_size = None  # размер поверхности, под который выбраны полосы

    def kick(self, strength=0.5) -> None:
        self.frames_left = random.randint(FRAMES_MIN, FRAMES_MAX)
        self._new_bands(strength)

    def _new_bands(self, strength) -> None:
        self.bands = []
        self.strength = max(0.05, min(1.0, strength))

    def update(self, strength) -> None:
        # Раз в кадр: решает, начинать ли глитч
        if self.frames_left > 0:
            self.frames_left -= 1
            return
        if strength > 0 and random.random() < START_CHANCE_BASE + START_CHANCE_GAIN * strength:
            self.kick(strength)

    def apply(self, surface, strength) -> None:
        # Рисует текущий глитч на surface (если он идёт)
        if self.frames_left <= 0 or strength <= 0:
            return
        w, h = surface.get_size()
        if w < 16 or h < 16:
            return
        s = max(0.05, min(1.0, strength))
        if self._band_size != (w, h):  # поверхность сменила размер - старые полосы не годятся
            self.bands = []
            self._band_size = (w, h)
        if not self.bands:  # полосы выбираются один раз на весь глитч
            for _ in range(1 + int(s * 3)):
                bh = random.randint(BAND_H_MIN, min(BAND_H_MAX, h // 2))
                y = random.randint(0, h - bh)
                dx = random.choice((-1, 1)) * random.randint(SHIFT_MIN, SHIFT_MIN + int(SHIFT_GAIN * s))
                self.bands.append((y, bh, dx, random.random() < INVERT_CHANCE_GAIN * s))
        for y, bh, dx, invert in self.bands:
            rect = pygame.Rect(0, y, w, bh).clip(surface.get_rect())  # на всякий случай: только внутри поверхности
            if rect.h <= 0:
                continue
            y, bh = rect.y, rect.h
            strip = surface.subsurface(rect).copy()
            if invert:
                inv = pygame.Surface(strip.get_size())
                inv.fill((255, 255, 255))
                inv.blit(strip, (0, 0), special_flags=pygame.BLEND_RGB_SUB)  # 255 - цвет
                strip = inv
            surface.blit(strip, (dx, y))
        if self.frames_left == 1:
            self.bands = []  # глитч кончился - в следующий раз полосы будут другие
