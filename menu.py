import pygame
import assets
import save_load
from settings import BOARD_WIDTH, BOARD_HEIGHT, OFFSET_X, OFFSET_Y, CELL_SIZE, DIR_UP, DIR_DOWN, DIR_LEFT, DIR_RIGHT
from tank import Tank
from bullet import Bullet
from blocks import PixelBlock

SLOT_COUNT = 99

draw_player = False
draw_bullet = False
draw_enemy = False
draw_boss = False

center_gx, center_gy = 5, 8

player_x, player_y = center_gx - 1, center_gy + 4
player_dir = DIR_UP

bullet_x, bullet_y = player_x, player_y - 3

enemy_x, enemy_y = center_gx, center_gy - 1
enemy_dir = DIR_DOWN

boss_x, boss_y = center_gx - 1, 3 
boss_dir = DIR_DOWN

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
            "MODE_C": ["C01"],
            # "MODE_D": ["D01", "D02"]
        }
        
        self.g_save = save_load.load_global_save()
        
        self.anim_timer = 0
        self.frame = 0
        self.frame_duration = 1000 

        self.letter_a_frames = getattr(assets, "A_MODE_IMGS", [])
        self.letter_b_frames = getattr(assets, "B_MODE_IMGS", [])
        self.letter_c_frames = getattr(assets, "C_MODE_IMGS", [])
        self.letter_d_frames = getattr(assets, "D_MODE_IMGS", [])
        
        self.letter_anim_timer = 0
        self.letter_frame = 0
        self.letter_frame_duration = 300 
        self.letter_anim_dir = 1 

    @property
    def selected_mode(self) -> str:
        current_state = self.prev_state if self.state == "SLOT" else self.state
        
        if current_state in self.MODE_MAPPING:
            return self.MODE_MAPPING[current_state][self.sub_mode_index - 1]
        return "A01"

    def update(self, dt_ms) -> bool:
        frame_changed = False
        state_to_check = self.prev_state if self.state == "SLOT" else self.state
        
        if state_to_check in self.MODE_MAPPING:
            self.anim_timer += dt_ms
            if self.anim_timer >= self.frame_duration:
                self.anim_timer = 0
                self.frame += 1
                frame_changed = True

                match self.selected_mode:
                    case 'A01' | 'A02' | "B01" | "B02" | 'C01': max_frames = 5
                    case _: max_frames = 1
                    
                if self.frame >= max_frames:
                    self.frame = 0
            
            self.letter_anim_timer += dt_ms
            if self.letter_anim_timer >= self.letter_frame_duration:
                self.letter_anim_timer = 0
                
                frames_list = []
                if state_to_check == "MODE_A": frames_list = self.letter_a_frames
                elif state_to_check == "MODE_B": frames_list = self.letter_b_frames
                elif state_to_check == "MODE_C": frames_list = self.letter_c_frames
                elif state_to_check == "MODE_D": frames_list = self.letter_d_frames
                
                max_frame = len(frames_list) - 1 if frames_list else 0
                
                if max_frame > 0:
                    self.letter_frame += self.letter_anim_dir
                    
                    if self.letter_frame >= max_frame:
                        self.letter_frame = max_frame
                        self.letter_anim_dir = -1
                    elif self.letter_frame <= 0:
                        self.letter_frame = 0
                        self.letter_anim_dir = 1
                else:
                    self.letter_frame = 0

        return frame_changed

    def change_state(self, new_state):
        self.state = new_state
        self.sub_mode_index = 1
        self.reset_animation(True)

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            states_order = ["MODE_A", "MODE_B", "MODE_C", "SETTINGS"]
            
            if self.state in self.MODE_MAPPING:
                idx = states_order.index(self.state)
                options = self.MODE_MAPPING[self.state]
                
                if event.key in (pygame.K_DOWN, pygame.K_s):
                    self.change_state(states_order[(idx + 1) % len(states_order)])
                elif event.key in (pygame.K_UP, pygame.K_w):
                    self.change_state(states_order[(idx - 1) % len(states_order)])
                elif event.key in (pygame.K_LEFT, pygame.K_a):
                    self.sub_mode_index -= 1
                    if self.sub_mode_index < 1: 
                        self.sub_mode_index = len(options)
                    self.reset_animation(True)
                elif event.key in (pygame.K_RIGHT, pygame.K_d):
                    self.sub_mode_index += 1
                    if self.sub_mode_index > len(options): 
                        self.sub_mode_index = 1
                    self.reset_animation(True)
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    if self.selected_mode == "C01":
                        self.selected_slot = 1
                        return "start_slot", (self.selected_mode, 1)
                    else:
                        self.prev_state = self.state
                        self.state = "SLOT"
                        return "mode_selected", self.selected_mode

            elif self.state == "SETTINGS":
                if event.key in (pygame.K_DOWN, pygame.K_s):
                    self.change_state("MODE_A")
                elif event.key in (pygame.K_UP, pygame.K_w):
                    self.change_state("MODE_C")
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    return "open_settings", None

            elif self.state == "SLOT":
                if event.key in (pygame.K_DOWN, pygame.K_LEFT, pygame.K_s, pygame.K_a):
                    self.selected_slot -= 1
                    if self.selected_slot < 1: self.selected_slot = SLOT_COUNT
                elif event.key in (pygame.K_UP, pygame.K_RIGHT, pygame.K_w, pygame.K_d):
                    self.selected_slot += 1
                    if self.selected_slot > SLOT_COUNT: self.selected_slot = 1
                elif event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                    self.state = self.prev_state
                    self.reset_animation(True)
                    return "back_to_mode", None
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    return "start_slot", (self.selected_mode, self.selected_slot)
                elif event.key == pygame.K_r:
                    return "reset_slot", None
        return None

    def reset_animation(self, globaling:bool = False) -> None:
        global draw_player, draw_bullet, draw_enemy, draw_boss 
        global center_gx, center_gy
        global player_x, player_y, player_dir
        global bullet_x, bullet_y
        global enemy_x, enemy_y, enemy_dir
        global boss_x, boss_y, boss_dir

        player_x, player_y = center_gx - 1, center_gy + 4
        player_dir = DIR_UP

        bullet_x, bullet_y = player_x, player_y - 3

        enemy_x, enemy_y = center_gx, center_gy - 1
        enemy_dir = DIR_DOWN

        boss_x, boss_y = center_gx - 1, 3 
        boss_dir = DIR_DOWN

        if globaling:
            self.frame = 0
            self.anim_timer = 0
            self.letter_frame = 0
            self.letter_anim_timer = 0
            self.letter_anim_dir = 1

    def draw(self) -> None:
        state_to_draw = self.prev_state if self.state == "SLOT" else self.state
        
        if state_to_draw in self.MODE_MAPPING:
            self.numbers_init()
            self.draw_animation()

            frames_list = []
            if state_to_draw == "MODE_A": frames_list = self.letter_a_frames
            elif state_to_draw == "MODE_B": frames_list = self.letter_b_frames
            elif state_to_draw == "MODE_C": frames_list = self.letter_c_frames
            elif state_to_draw == "MODE_D": frames_list = self.letter_d_frames

            if frames_list and self.letter_frame < len(frames_list):
                img = frames_list[self.letter_frame]
                self.screen.blit(img, (OFFSET_X + 2 * CELL_SIZE, OFFSET_Y))

        elif self.state == "SETTINGS":
            gear_sprite = pygame.sprite.Group()
            gear = [
                PixelBlock(4, 5), PixelBlock(5, 5),
                PixelBlock(1, 6), PixelBlock(2, 6), PixelBlock(4, 6), PixelBlock(5, 6), PixelBlock(7, 6), PixelBlock(8, 6),
                PixelBlock(1, 7), PixelBlock(2, 7), PixelBlock(3, 7), PixelBlock(6, 7), PixelBlock(7, 7), PixelBlock(8, 7),
                PixelBlock(2, 8), PixelBlock(7, 8),
                PixelBlock(0, 9), PixelBlock(1, 9), PixelBlock(4, 9), PixelBlock(5, 9), PixelBlock(8, 9), PixelBlock(9, 9),
                PixelBlock(0, 10), PixelBlock(1, 10), PixelBlock(4, 10), PixelBlock(5, 10), PixelBlock(8, 10), PixelBlock(9, 10),
                PixelBlock(2, 11), PixelBlock(7, 11),
                PixelBlock(1, 12), PixelBlock(2, 12), PixelBlock(3, 12), PixelBlock(6, 12), PixelBlock(7, 12), PixelBlock(8, 12),
                PixelBlock(1, 13), PixelBlock(2, 13), PixelBlock(4, 13), PixelBlock(5, 13), PixelBlock(7, 13), PixelBlock(8, 13),
                PixelBlock(4, 14), PixelBlock(5, 14),
            ]
            gear_sprite.add(*gear)
            gear_sprite.draw(self.screen)

    def draw_animation(self) -> None:
        global draw_player, draw_bullet, draw_enemy, draw_boss 
        global center_gx, center_gy
        global player_x, player_y, player_dir
        global bullet_x, bullet_y
        global enemy_x, enemy_y, enemy_dir
        global boss_x, boss_y, boss_dir
        anim_group = pygame.sprite.Group()
        block:bool = False

        state_to_draw = self.prev_state if self.state == "SLOT" else self.state

        match state_to_draw:
            case 'MODE_A':
                match self.frame:
                    case 0:
                        draw_player = draw_bullet = draw_enemy = True
                        draw_boss = False
                    case 1:
                        bullet_x, bullet_y = player_x, player_y - 4
                    case 2:
                        draw_bullet = draw_enemy = False
                        draw_player = True
                    case 3:
                        draw_enemy = True
                        player_x, player_y = center_gx - 1, center_gy + 3
                        enemy_x, enemy_y = center_gx + 3, center_gy - 1
                        enemy_dir = DIR_LEFT
                    case 4:    
                        self.reset_animation()

                match self.selected_mode:
                    case 'A01': block = True
                    case 'A02': block = False

                if block and assets.PIXEL_IMG_RAW:
                    blocks = [
                        PixelBlock(8, 10), PixelBlock(9, 10), 
                        PixelBlock(8, 11), PixelBlock(9, 11),
                        PixelBlock(8, 12), PixelBlock(9, 12),

                        PixelBlock(0, 6), PixelBlock(1, 6), 
                        PixelBlock(0, 7),
                    ]
                    anim_group.add(*blocks)
            case 'MODE_B':
                match self.frame:
                    case 0:
                        draw_player = draw_bullet = draw_enemy = True
                        draw_boss = False
                    case 1:
                        bullet_x, bullet_y = player_x, player_y - 4
                    case 2:
                        draw_bullet = draw_enemy = False
                        draw_player = True
                    case 3:
                        draw_enemy = True
                        player_x, player_y = center_gx - 1, center_gy + 3
                        enemy_x, enemy_y = center_gx + 3, center_gy - 1
                        enemy_dir = DIR_LEFT
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
                        draw_player = draw_bullet = draw_enemy = True
                        draw_boss = False
                    case 1:
                        bullet_x, bullet_y = player_x, player_y - 4
                    case 2:
                        draw_bullet = draw_enemy = False
                        draw_player = True
                    case 3:
                        draw_enemy = True
                        player_x, player_y = center_gx - 1, center_gy + 3
                        enemy_x, enemy_y = center_gx + 3, center_gy - 1
                        enemy_dir = DIR_LEFT
                    case 4:    
                        self.reset_animation()

                if assets.PIXEL_IMG_RAW:
                    blocks = [
                        PixelBlock(0, 6), PixelBlock(1, 6), 
                        PixelBlock(1, 7),
                        PixelBlock(2, 7),

                        PixelBlock(8, 11), PixelBlock(9, 11), 
                        PixelBlock(8, 12), PixelBlock(9, 12),
                    ]
                anim_group.add(*blocks)
            case 'MODE_D':
                pass
            case 'MODE_E':
                pass

        if draw_player:
            player = Tank(player_x, player_y, assets.PLAYER_BASE_IMG)
            player.set_direction(player_dir)
            anim_group.add(player)
        
        if draw_bullet:
            custom_tank_enabled = self.g_save.get("custom_tank", {}).get("enabled", False)
            bullet_color = self.g_save.get("rgb", [0, 0, 0]) if (self.g_save.get("paint_tank", False) and custom_tank_enabled) else None
            
            bullet = Bullet(player, player_dir, assets.PIXEL_IMG_RAW, is_player=True, custom_color=bullet_color)
            bullet.grid_x = bullet_x
            bullet.grid_y = bullet_y
            bullet.update_position()
            anim_group.add(bullet)
            
        if draw_enemy:
            enemy = Tank(enemy_x, enemy_y, assets.ENEMY_BASE_IMG)
            enemy.set_direction(enemy_dir)
            anim_group.add(enemy)
            
        if draw_boss:
            boss = Tank(boss_x, boss_y, assets.DEFAULT_BOSS_FRAMES)
            boss.set_direction(boss_dir)
            anim_group.add(boss)            

        anim_group.draw(self.screen)
    
    def numbers_init(self) -> None:
        left_digit = self.sub_mode_index // 10
        right_digit = self.sub_mode_index % 10

        if assets.MODE_NUM_IMGS and len(assets.MODE_NUM_IMGS) == 10:
            img_left = assets.MODE_NUM_IMGS[left_digit]
            rect_left = img_left.get_rect(bottomleft=(OFFSET_X + CELL_SIZE, OFFSET_Y + BOARD_HEIGHT * CELL_SIZE))
            self.screen.blit(img_left, rect_left)

            img_right = assets.MODE_NUM_IMGS[right_digit]
            rect_right = img_right.get_rect(bottomright=(OFFSET_X + (BOARD_WIDTH - 2) * CELL_SIZE, OFFSET_Y + BOARD_HEIGHT * CELL_SIZE))
            self.screen.blit(img_right, rect_right)
