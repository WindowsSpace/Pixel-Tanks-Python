import random
import pygame

from core.controls import Controls
from core import assets
from services import save_load
from core.settings import BOARD_WIDTH, BOARD_HEIGHT, OFFSET_X, OFFSET_Y, CELL_SIZE, DIR_UP, DIR_DOWN, DIR_LEFT, DIR_RIGHT
from entities.tank import Tank
from entities.bullet import Bullet
from entities.blocks import PixelBlock
from core.grid import get_cell_topleft
from models import generate_blocks_from_model
import models

SLOT_COUNT = 99

# блоки из меню A01, их же ставим как пометку "в режиме есть блоки"
WALL_MODEL = ["XX", "XX", "XX"]
CORNER_MODEL = ["XX", "X "]

# E: бесконечный режим, враги выезжают по очереди
E_LANES = (3, 6)
E_BLOCK_MODES = ("E02", "E03", "E05")

# F01: коридор 10x5 на всю ширину поля, танк едет по средней линии
F01_CORRIDOR = [
    "XXXXXXXXXX",
    "          ",
    "          ",
    "          ",
    "XXXXXXXXXX",
]
F01_CORRIDOR_Y = 7

# F02: блоки по полю, танк объезжает их стороной
F02_BLOCKS = [
    (3, 6), (4, 6), (5, 6),
    (8, 6), (9, 6), (9, 7),
    (7, 8), (8, 8), (7, 9), (8, 9),
    (0, 10), (0, 11),
    (0, 12), (1, 12), (0, 13), (1, 13),
]
F02_ROUTE = [(1, 8), (2, 8), (3, 8), (4, 8), (5, 8), (5, 9), (5, 10), (5, 11), (6, 11), (7, 11), (8, 11)]


def build_loop(cells):
    # туда и обратно, на концах танк разворачивается на месте
    pos = cells + cells[::-1]
    loop = []
    for i, (x, y) in enumerate(pos):
        px, py = pos[i - 1]
        if (px, py) == (x, y):
            nx, ny = pos[(i + 1) % len(pos)]
            move = (nx - x, ny - y)
        else:
            move = (x - px, y - py)
        loop.append((x, y, move))
    return loop


F01_LOOP = build_loop([(x, F01_CORRIDOR_Y + 2) for x in range(1, 9)])
F02_LOOP = build_loop(F02_ROUTE)

LETTER_GY = 0
DIGIT_GY = 15
DIGIT_GAP = 2

class MainMenu:
    def __init__(self, screen, font) -> None:
        self.screen = screen
        self.font = font
        
        self.state = "MODE_A"
        self.sub_mode_index = 1 
        self.selected_slot = 1
        self.prev_state = "MODE_A" 

        self.MODE_MAPPING = {
            "MODE_A": ["A01", "A02"],
            "MODE_B": ["B01", "B02"],
            "MODE_C": ["C01", 'C02'],
            # "MODE_D": ["D01", "D02", "D03"],
            "MODE_E": ['E01', 'E02', 'E03', 'E04', 'E05'],
            "MODE_F": ['F01', 'F02'],
        }
        
        self.g_save = save_load.load_global_save()
        self.controls = Controls(self.g_save)  # app.py подставляет общий экземпляр
        self.colorless = False  # True на время шторки: танк и пуля в меню без краски
        
        # Настройки анимации текста
        self.mode_anim_frames = []
        self.mode_anim_index = 0
        self.letter_anim_timer = 0
        self.letter_frame_duration = 300
        
        # Настройки покадровой анимации сцены (танков)
        self.frame = 0
        self.anim_timer = 0
        self.tick_timer = 0  # тик для HUD, не зависит от скорости кадров сцены
        self.cycle = 0  # сколько кругов анимации прошло
        self.frame_duration = 1000  # мс на кадр
        self.anim_direction = 1

        # D01 пройден: в меню квадрат 5x5 из блоков и чёрный танк внутри
        self.d01_dir = DIR_DOWN
        self.d01_turn_timer = 0
        self.d01_turn_ms = 600
        self._black_tank_img = None

        # Координаты центра для анимации
        self.center_gx = 5
        self.center_gy = 8

        # Инициализация всех координат и флагов (замена global)
        self.reset_animation(True)

    def create_mode_text(self) -> None:
        mode = self.selected_mode

        letter_char = mode[0]
        d1_char = mode[1]
        d2_char = mode[2]

        self.letter_frames = models.generate_animated_text(letter_char, assets.PIXEL_IMG_RAW)
        self.d1_frames = models.generate_animated_text(d1_char, assets.PIXEL_IMG_RAW)
        self.d2_frames = models.generate_animated_text(d2_char, assets.PIXEL_IMG_RAW)

    @property
    def selected_mode(self) -> str:
        current_state = self.prev_state if self.state == "SLOT" else self.state
        
        if current_state in self.MODE_MAPPING:
            modes = self.MODE_MAPPING[current_state]
            idx = max(0, min(self.sub_mode_index - 1, len(modes) - 1))
            return modes[idx]
        return "A01"

    def d01_completed(self) -> bool:
        # Режим D01 уже пройден (меняется анимация выбора D01)
        return bool(self.g_save.get("completed", {}).get("D01", False))

    def _turn_black_tank(self, dt_ms) -> None:
        # Чёрный танк в квадрате D01 поворачивается в случайную сторону
        self.d01_turn_timer += dt_ms
        if self.d01_turn_timer >= self.d01_turn_ms:
            self.d01_turn_timer = 0
            self.d01_turn_ms = random.randint(350, 900)
            self.d01_dir = random.choice([d for d in (DIR_UP, DIR_DOWN, DIR_LEFT, DIR_RIGHT) if d != self.d01_dir])

    def anim_timing(self) -> tuple[int, int]:
        # (мс на кадр, число кадров) для выбранного режима
        mode = self.selected_mode
        if mode in ('D01', 'D02', 'D03'):
            return self.frame_duration, 3
        if mode.startswith('E'):
            return self.frame_duration, 4
        if mode == 'F01':
            return 300, len(F01_LOOP)
        if mode == 'F02':
            return 350, len(F02_LOOP)
        return self.frame_duration, 5

    def update(self, dt_ms) -> bool:
        frame_changed = False
        state_to_check = self.prev_state if self.state == "SLOT" else self.state

        if state_to_check == "MODE_D" and self.selected_mode == "D01" and self.d01_completed():
            self._turn_black_tank(dt_ms)

        if state_to_check in self.MODE_MAPPING:
            # Обновление анимации танков в фоне
            duration, max_frames = self.anim_timing()
            self.anim_timer += dt_ms
            if self.anim_timer >= duration:
                self.anim_timer = 0
                self.frame += 1
                if self.frame >= max_frames:
                    self.frame = 0
                    self.cycle += 1

            self.tick_timer += dt_ms
            if self.tick_timer >= self.frame_duration:
                self.tick_timer = 0
                frame_changed = True

            self.letter_anim_timer += dt_ms
            if self.letter_anim_timer >= self.letter_frame_duration:
                self.letter_anim_timer = 0

                if hasattr(self, 'letter_frames') and self.letter_frames and len(self.letter_frames) > 1:
                    self.mode_anim_index += self.anim_direction

                    if self.mode_anim_index >= len(self.letter_frames) - 1:
                        self.mode_anim_index = len(self.letter_frames) - 1
                        self.anim_direction = -1 
                    elif self.mode_anim_index <= 0:
                        self.mode_anim_index = 0
                        self.anim_direction = 1

        return frame_changed

    def unlock_mode_d(self) -> None:
        # Открывает в меню режим D (пока только D01; D02/D03 - добавить в список)
        self.MODE_MAPPING["MODE_D"] = ["D01"]

    def open_mode(self, state, index = 1) -> None:
        # Сразу показывает в меню режим state (например "MODE_D") и его номер index
        self.state = state
        self.prev_state = state
        self.sub_mode_index = index
        self.reset_animation(True)

    def change_state(self, new_state) -> None:
        self.state = new_state
        self.sub_mode_index = 1
        self.reset_animation(True)

    def handle_event(self, event):
        # Стрелки/WASD/Enter/Space/Esc/Backspace работают всегда, плюс ваши бинды
        act = self.controls.menu_action(event)
        is_reset_key = event.type == pygame.KEYDOWN and event.key == pygame.K_r
        if act or is_reset_key:
            # MODE_D появляется в списке, только если он открыт (unlock_mode_d)
            states_order = [st for st in ("MODE_A", "MODE_B", "MODE_C", "MODE_D", "MODE_E", "MODE_F")
                            if st in self.MODE_MAPPING] + ["SETTINGS"]
            
            if self.state in self.MODE_MAPPING:
                idx = states_order.index(self.state)
                options = self.MODE_MAPPING[self.state]
                
                if act == "down":
                    assets.play_sound(assets.SCROLL_SOUND, True)
                    self.change_state(states_order[(idx + 1) % len(states_order)])
                elif act == "up":
                    assets.play_sound(assets.SCROLL_SOUND, True)
                    self.change_state(states_order[(idx - 1) % len(states_order)])
                elif act == "left":
                    self.sub_mode_index -= 1
                    if self.sub_mode_index < 1: 
                        self.sub_mode_index = len(options)
                    self.reset_animation(True)
                elif act == "right":
                    self.sub_mode_index += 1
                    if self.sub_mode_index > len(options): 
                        self.sub_mode_index = 1
                    self.reset_animation(True)
                elif act == "confirm":
                    self.prev_state = self.state
                    if self.selected_mode.startswith('E'):
                        self.selected_slot = 1
                        return "start_slot", (self.selected_mode, 1)
                    else:
                        self.state = "SLOT"
                        return "mode_selected", self.selected_mode

            elif self.state == "SETTINGS":
                if act == "down":
                    assets.play_sound(assets.SCROLL_SOUND, True)
                    self.change_state("MODE_A")
                elif act == "up":
                    assets.play_sound(assets.SCROLL_SOUND, True)
                    self.change_state("MODE_F")
                elif act == "confirm":
                    return "open_settings", None

            elif self.state == "SLOT":
                if act in ("down", "left"):
                    self.selected_slot -= 1
                    if self.selected_slot < 1: self.selected_slot = SLOT_COUNT
                elif act in ("up", "right"):
                    self.selected_slot += 1
                    if self.selected_slot > SLOT_COUNT: self.selected_slot = 1
                elif act == "back":
                    self.state = self.prev_state
                    self.reset_animation(True)
                    return "back_to_mode", None
                elif act == "confirm":
                    return "start_slot", (self.selected_mode, self.selected_slot)
                elif is_reset_key:
                    return "reset_slot", None
        return None

    def reset_animation(self, globaling: bool = False) -> None:
        self.player_x, self.player_y = self.center_gx - 1, self.center_gy + 4
        self.player_dir = DIR_UP

        self.bullet_x, self.bullet_y = self.player_x, self.player_y - 3

        self.enemy_x, self.enemy_y = self.center_gx, self.center_gy - 1
        self.enemy_dir = DIR_DOWN

        self.boss_x, self.boss_y = self.center_gx - 1, 3 
        self.boss_dir = DIR_DOWN

        if globaling:
            self.draw_player = False
            self.draw_bullet = False
            self.draw_enemy = False
            self.draw_boss = False
            
            self.frame = 0
            self.cycle = 0
            self.anim_timer = 0
            self.tick_timer = 0
            self.letter_anim_timer = 0
            self.mode_anim_index = 0
            self.anim_direction = 1
            self.create_mode_text()

    def draw(self) -> None:
        state_to_draw = self.prev_state if self.state == "SLOT" else self.state
        
        if state_to_draw in self.MODE_MAPPING:
            self.draw_animation()

            if hasattr(self, 'letter_frames') and self.letter_frames:
                letter_surf = self.letter_frames[self.mode_anim_index]
                letter_w_cells = letter_surf.get_width() // CELL_SIZE
            
                letter_gx = (BOARD_WIDTH - letter_w_cells) // 2
                px, py = get_cell_topleft(letter_gx, LETTER_GY)
                self.screen.blit(letter_surf, (px, py))

            if hasattr(self, 'd1_frames') and self.d1_frames and hasattr(self, 'd2_frames') and self.d2_frames:
                d1_surf = self.d1_frames[self.mode_anim_index % len(self.d1_frames)]
                d2_surf = self.d2_frames[self.mode_anim_index % len(self.d2_frames)]

                d1_w_cells = d1_surf.get_width() // CELL_SIZE
                d2_w_cells = d2_surf.get_width() // CELL_SIZE

                total_w_cells = d1_w_cells + DIGIT_GAP + d2_w_cells
                
                d1_gx = (BOARD_WIDTH - total_w_cells) // 2
                d2_gx = d1_gx + d1_w_cells + DIGIT_GAP

                px1, py1 = get_cell_topleft(d1_gx, DIGIT_GY)
                self.screen.blit(d1_surf, (px1, py1))

                px2, py2 = get_cell_topleft(d2_gx, DIGIT_GY)
                self.screen.blit(d2_surf, (px2, py2))

        elif self.state == "SETTINGS":
            gear_sprite = pygame.sprite.Group()
            gear = models.generate_blocks_from_model(models.SETTINGS_MODEL, PixelBlock, 0, 5)
            gear_sprite.add(*gear)
            gear_sprite.draw(self.screen)

    def side_blocks(self) -> list:
        # стенка справа внизу и уголок слева сверху
        blocks = generate_blocks_from_model(WALL_MODEL, PixelBlock, 8, 10)
        blocks += generate_blocks_from_model(CORNER_MODEL, PixelBlock, 0, 6)
        return blocks

    def make_bullet(self, owner, direction, gx, gy) -> Bullet:
        custom_tank_enabled = self.g_save.get("custom_tank", {}).get("enabled", False)
        painted = self.g_save.get("paint_tank", False) and custom_tank_enabled and not self.colorless
        color = self.g_save.get("rgb", [0, 0, 0]) if painted else None

        bullet = Bullet(owner, direction, assets.PIXEL_IMG_RAW, is_player=True, custom_color=color)
        bullet.grid_x = gx
        bullet.grid_y = gy
        bullet.update_position()
        return bullet

    def draw_endless(self, group) -> None:
        # враг выезжает сверху, игрок сбивает его и сдвигается на другую линию
        lane = E_LANES[self.cycle % 2]
        next_lane = E_LANES[(self.cycle + 1) % 2]
        step = self.frame % 4

        player = Tank(next_lane if step == 3 else lane, 12, assets.PLAYER_BASE_IMG)
        player.set_direction(DIR_UP)
        group.add(player)

        if step in (0, 1):
            enemy = Tank(lane, 7 + step, assets.ENEMY_BASE_IMG)
            enemy.set_direction(DIR_DOWN)
            group.add(enemy)
        if step == 1:
            group.add(self.make_bullet(player, DIR_UP, lane, 10))

        # блоки как пометка, что на уровне они есть
        if self.selected_mode in E_BLOCK_MODES and assets.PIXEL_IMG_RAW:
            group.add(*self.side_blocks())

    def draw_maze(self, group) -> None:
        if not assets.PIXEL_IMG_RAW:
            return
        if self.selected_mode == 'F01':
            loop = F01_LOOP
            group.add(*generate_blocks_from_model(F01_CORRIDOR, PixelBlock, 0, F01_CORRIDOR_Y))
        else:
            loop = F02_LOOP
            group.add(*[PixelBlock(x, y) for x, y in F02_BLOCKS])

        x, y, move = loop[self.frame % len(loop)]
        tank = Tank(x, y, assets.PLAYER_BASE_IMG)
        tank.set_direction(move)
        group.add(tank)

    def draw_animation(self) -> None:
        anim_group = pygame.sprite.Group()
        block: bool = False

        state_to_draw = self.prev_state if self.state == "SLOT" else self.state

        match state_to_draw:
            case 'MODE_A':
                match self.frame:
                    case 0:
                        self.draw_player = self.draw_bullet = self.draw_enemy = True
                        self.draw_boss = False
                    case 1:
                        self.bullet_x, self.bullet_y = self.player_x, self.player_y - 4
                    case 2:
                        self.draw_bullet = self.draw_enemy = False
                        self.draw_player = True
                    case 3:
                        self.draw_enemy = True
                        self.player_x, self.player_y = self.center_gx - 1, self.center_gy + 3
                        self.enemy_x, self.enemy_y = self.center_gx + 3, self.center_gy - 1
                        self.enemy_dir = DIR_LEFT
                    case 4:
                        self.reset_animation()

                match self.selected_mode:
                    case 'A01': block = True
                    case 'A02': block = False

                if block and assets.PIXEL_IMG_RAW:
                    anim_group.add(*self.side_blocks())

            case 'MODE_B':
                match self.frame:
                    case 0:
                        self.draw_player = self.draw_bullet = self.draw_enemy = True
                        self.draw_boss = False
                    case 1:
                        self.bullet_x, self.bullet_y = self.player_x, self.player_y - 4
                    case 2:
                        self.draw_bullet = self.draw_enemy = False
                        self.draw_player = True
                    case 3:
                        self.draw_enemy = True
                        self.player_x, self.player_y = self.center_gx - 1, self.center_gy + 3
                        self.enemy_x, self.enemy_y = self.center_gx + 3, self.center_gy - 1
                        self.enemy_dir = DIR_LEFT
                    case 4:
                        self.reset_animation()

                if assets.PIXEL_IMG_RAW:
                    blocks = [
                        PixelBlock(0, 6), PixelBlock(0, 7), PixelBlock(0, 8),
                        PixelBlock(1, 8),
                        PixelBlock(7, 10), PixelBlock(8, 10), 
                        PixelBlock(7, 11), PixelBlock(8, 11),
                    ]
                    anim_group.add(*blocks)

            case 'MODE_C':
                match self.frame:
                    case 0:
                        self.draw_player = self.draw_bullet = self.draw_enemy = True
                        self.draw_boss = False
                    case 1:
                        self.bullet_x, self.bullet_y = self.player_x, self.player_y - 4
                    case 2:
                        self.draw_bullet = self.draw_enemy = False
                        self.draw_player = True
                    case 3:
                        self.draw_enemy = True
                        self.player_x, self.player_y = self.center_gx - 1, self.center_gy + 3
                        self.enemy_x, self.enemy_y = self.center_gx + 3, self.center_gy - 1
                        self.enemy_dir = DIR_LEFT
                    case 4:
                        self.reset_animation()

                if assets.PIXEL_IMG_RAW:
                    blocks = [
                        PixelBlock(0, 6), PixelBlock(1, 6), 
                        PixelBlock(1, 7), PixelBlock(2, 7),
                        PixelBlock(8, 11), PixelBlock(9, 11), 
                        PixelBlock(8, 12), PixelBlock(9, 12),
                    ]
                    anim_group.add(*blocks)

            case 'MODE_D' if self.selected_mode == 'D01' and self.d01_completed():
                # Пройденный D01: квадрат 5x5 из обычных блоков, внутри - чёрный танк (3x3)
                self.draw_player = self.draw_bullet = self.draw_enemy = self.draw_boss = False
                if assets.PIXEL_IMG_RAW:
                    square_model = [
                        "XXXXX",
                        "X   X",
                        "X   X",
                        "X   X",
                        "XXXXX",
                    ]
                    anim_group.add(*generate_blocks_from_model(square_model, PixelBlock, self.center_gx - 3, 7))
                    if self._black_tank_img is None and assets.BLACK_CELL_IMG is not None:
                        self._black_tank_img = assets.make_black_copy(assets.DEFAULT_PLAYER_BASE_IMG or assets.PLAYER_BASE_IMG)
                    if self._black_tank_img is not None:
                        black_tank = Tank(self.center_gx - 1, 9, self._black_tank_img)
                        black_tank.set_direction(self.d01_dir)
                        anim_group.add(black_tank)

            case 'MODE_D':
                match self.frame:
                    case 0:
                        self.draw_player = self.draw_bullet = self.draw_enemy = self.draw_boss = False
                        if assets.PIXEL_IMG_RAW:
                            blocks = [PixelBlock(4, 10)]
                            anim_group.add(*blocks)
                    case 1:
                        if assets.PIXEL_IMG_RAW:
                            blocks = [PixelBlock(3, 10), PixelBlock(5, 10)]
                            anim_group.add(*blocks)
                    case 2:
                        if assets.PIXEL_IMG_RAW:
                            blocks = [PixelBlock(2, 10), PixelBlock(4, 10), PixelBlock(6, 10)]
                            anim_group.add(*blocks)
            case 'MODE_E':
                self.draw_player = self.draw_bullet = self.draw_enemy = self.draw_boss = False
                self.draw_endless(anim_group)
            case 'MODE_F':
                self.draw_player = self.draw_bullet = self.draw_enemy = self.draw_boss = False
                self.draw_maze(anim_group)

        if self.draw_player:
            player = Tank(self.player_x, self.player_y, assets.PLAYER_BASE_IMG)
            player.set_direction(self.player_dir)
            anim_group.add(player)
        
        if self.draw_bullet:
            anim_group.add(self.make_bullet(player, self.player_dir, self.bullet_x, self.bullet_y))
            
        if self.draw_enemy:
            enemy = Tank(self.enemy_x, self.enemy_y, assets.ENEMY_BASE_IMG)
            enemy.set_direction(self.enemy_dir)
            anim_group.add(enemy)
            
        if self.draw_boss:
            boss = Tank(self.boss_x, self.boss_y, assets.DEFAULT_BOSS_FRAMES)
            boss.set_direction(self.boss_dir)
            anim_group.add(boss)            

        anim_group.draw(self.screen)