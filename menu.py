import pygame
from settings import WIDTH, HEIGHT, BACKGROUND_COLOR
import assets
from save_load import load_game

SLOT_COUNT = 3

class MainMenu:
    def __init__(self, screen, font):
        self.screen = screen
        self.font = font
        self.selected_slot = 1  # 1..3

        # Плейсхолдер-Прямоугольники для слотов
        self.slot_rects = []
        margin_top = 150
        slot_height = 60
        slot_width = 300
        spacing = 20
        x = WIDTH // 2 - slot_width // 2

        for i in range(SLOT_COUNT):
            y = margin_top + i * (slot_height + spacing)
            rect = pygame.Rect(x, y, slot_width, slot_height)
            self.slot_rects.append(rect)

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP:
                self.selected_slot = max(1, self.selected_slot - 1)
            elif event.key == pygame.K_DOWN:
                self.selected_slot = min(SLOT_COUNT, self.selected_slot + 1)

            elif event.key == pygame.K_RETURN:
                # Выбор слота подтверждается в game.py (там уже будет запуск игры)
                return "start_slot", self.selected_slot

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for i, rect in enumerate(self.slot_rects, start=1):
                if rect.collidepoint(event.pos):
                    self.selected_slot = i
                    return "start_slot", self.selected_slot

        return None

    def draw(self):
        # Рисуем то же поле
        self.screen.fill(BACKGROUND_COLOR)
        self.screen.blit(assets.BACKGROUND_IMG, (0, 0))

        title_surf = self.font.render("TANK GAME - MENU", True, (255, 255, 255))
        title_rect = title_surf.get_rect(center=(WIDTH // 2, 80))
        self.screen.blit(title_surf, title_rect)

        for i, rect in enumerate(self.slot_rects, start=1):
            # Проверка, есть ли сохранение
            data = load_game(i)
            has_save = data is not None

            # Цвет рамки
            if i == self.selected_slot:
                color = (255, 255, 0)
            else:
                color = (255, 255, 255)

            pygame.draw.rect(self.screen, color, rect, 3)

            if has_save:
                text = f"Slot {i}: CONTINUE"
            else:
                text = f"Slot {i}: NEW GAME"

            text_surf = self.font.render(text, True, (255, 255, 255))
            text_rect = text_surf.get_rect(center=rect.center)
            self.screen.blit(text_surf, text_rect)
