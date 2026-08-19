import pygame
import random

from discord_rpc import DiscordPresence
from pygame.font import Font

import assets
import settings

from utils import generate_lives_positions
from modes.mode_config import get_mode_class
from settings import WIDTH, HEIGHT, \
    BACKGROUND_COLOR, PLAYER_SPAWN_POINTS, \
    HUD_START_X, HUD_BOARD_Y, \
    CELL_SIZE, OFFSET_X, OFFSET_Y, \
    BOARD_WIDTH, BOARD_HEIGHT, \
    PLAYER_MOVE_KEYS, PLAYER_SHOOT_KEYS, \
    DIR_UP, DIR_DOWN, DIR_LEFT, DIR_RIGHT
from tank import PlayerTank, DefaultBoss
from bullet import Bullet
from enemy_manager import EnemyManager
from menu import MainMenu
from blocks import find_nearest_empty_cell

import save_load
from save_load import save_game, load_game, load_hi_score, save_hi_score, delete_save, get_menu_stats, get_best_mode_stats

LONG_ESC_MS = 800

DIRECTION_TO_NAME = {DIR_UP: "up", DIR_DOWN: "down", DIR_LEFT: "left", DIR_RIGHT: "right"}
NAME_TO_DIRECTION = {v: k for k, v in DIRECTION_TO_NAME.items()}

ABOVE_Y = HUD_BOARD_Y + (4 / CELL_SIZE) - OFFSET_Y
BELOW_Y = HUD_BOARD_Y + (4 * CELL_SIZE) + OFFSET_Y
LABEL_X = HUD_START_X  # Левая граница текста
VALUE_X = HUD_START_X + (4 * CELL_SIZE) # Правая граница, где должны заканчиваться числа

def apply_custom_tank(g_save, force_colorless=False) -> None:
    if g_save.get("custom_tank", {}).get("enabled", False):
        use_color = g_save.get("paint_tank", False) and not force_colorless
        rgb_val = g_save.get("rgb", [129, 136, 111])
        
        pixel_img = assets.PIXEL_IMG_RAW
        
        # Если включен кастомный цвет и нет принудительного обесцвечивания, красим подложку
        if use_color and assets.PIXEL_COLOR_IMG_RAW:
            color_underlay = assets.colorize_icon(assets.PIXEL_COLOR_IMG_RAW, (*rgb_val, 255))
        else:
            if assets.PIXEL_COLOR_IMG_RAW:
                color_underlay = assets.colorize_icon(assets.PIXEL_COLOR_IMG_RAW, (129, 136, 111, 255))
            else:
                color_underlay = None
            
        surf = pygame.Surface((3 * CELL_SIZE, 3 * CELL_SIZE), pygame.SRCALPHA)
        for px, py in g_save["custom_tank"].get("pixels", []):
            x, y = px * CELL_SIZE, py * CELL_SIZE
            if color_underlay:
                surf.blit(color_underlay, (x, y))
            if pixel_img:
                surf.blit(pixel_img, (x, y))
        assets.PLAYER_BASE_IMG = surf
    else:
        if hasattr(assets, 'DEFAULT_PLAYER_BASE_IMG') and assets.DEFAULT_PLAYER_BASE_IMG:
            assets.PLAYER_BASE_IMG = assets.DEFAULT_PLAYER_BASE_IMG

def get_difficulty_params(game_state):
    if not game_state:
        return 4, 1.0, 750

    max_enemies = 4
    speed_multiplier = 1.0
    spawn_delay = 750

    if game_state.get("logic_mode"):
        mode = game_state["logic_mode"]
        speed_multiplier = 1.0 + mode.extra_speed
        max_enemies, spawn_delay = mode.modify_spawn_params(max_enemies, spawn_delay)
        
    return max_enemies, speed_multiplier, spawn_delay

def create_new_game(mode, slot, previous_data = None):
    all_sprites = pygame.sprite.Group()
    bullets = pygame.sprite.Group()
    enemies = pygame.sprite.Group()
    blocks = pygame.sprite.Group()
    px, py = random.choice(PLAYER_SPAWN_POINTS)
    player = PlayerTank(px, py, assets.PLAYER_BASE_IMG)
    all_sprites.add(player)
    enemy_manager = EnemyManager(assets.ENEMY_BASE_IMG, enemies, all_sprites, player)

    state = {
        "mode": mode,
        "slot": slot,
        "player": player,
        "enemy_manager": enemy_manager,
        "all_sprites": all_sprites,
        "bullets": bullets,
        "enemies": enemies,
        "blocks": blocks,
        "logic_mode": None,
        "paused": False,
        "sounds_enabled": True,
        "lives": 4,
        "score": 0,
        "level": 1,
        "target_enemies": 10,
        "kills_this_level": 0,
        "global_kills": 0,
        "hi_score": load_hi_score(mode),
        "lives_positions": generate_lives_positions(4)
    }

    mode_class = get_mode_class(mode)
    state["logic_mode"] = mode_class(state)
    state["target_enemies"] = state["logic_mode"].target_kills

    if previous_data:
        stats = previous_data.get("stats", {})
        state["lives"] = stats.get("lives", 4)
        state["score"] = stats.get("score", 0)
        state["level"] = stats.get("level", 1)
        state["target_enemies"] = stats.get("target", 10)
        state["kills_this_level"] = stats.get("kills_this_level", 0)
        state["global_kills"] = stats.get("global_kills", 0)
        state["lives_positions"] = generate_lives_positions(state["lives"])

    return state

def load_game_slot(mode, slot):
    data = load_game(mode, slot)
    state = create_new_game(mode, slot, data)

    if data is None:
        return state

    save_load.load_game_into_slot(state, data) 
    return state

def hitbox_collide(sprite1, sprite2):
    return pygame.sprite.collide_mask(sprite1, sprite2) is not None

def bullet_collide(sprite1, sprite2):
    rect1 = sprite1.rect.inflate(0, 1)
    rect2 = sprite2.rect.inflate(0, 1)
    return rect1.colliderect(rect2)

def render_text(screen, font, text, x = None, y = None, align = "center", color = (0, 0, 0)) -> None:
    surf = font.render(text, True, color)
    rect = surf.get_rect()
    
    if x is None:
        x = HUD_START_X + (4 * CELL_SIZE) // 2
        
    if align == "center":
        rect.center = (x, y)
    elif align == "left":
        rect.topleft = (x, y)
    elif align == "right":
        rect.topright = (x, y)
    
    screen.blit(surf, rect)

def render_hud(screen, font, stats, sound_img, paused, pause_rect, sound_rect, custom_goal=None, is_settings=False) -> None:
    if is_settings:
        for lx in range(4):
            for ly in range(4):
                screen.blit(assets.PIXEL_IMG_RAW, (HUD_START_X + lx * CELL_SIZE, HUD_BOARD_Y + ly * CELL_SIZE))

        render_text(screen, font, "SETTINGS", None, BELOW_Y)

        screen.blit(assets.PAUSE_IMG_BLACK if paused else assets.PAUSE_IMG_INACTIVE, pause_rect)
        screen.blit(sound_img, sound_rect)
        return

    # Стандартный HUD
    render_text(screen, font, "SCORE", None, ABOVE_Y - 215)
    render_text(screen, font, str(stats["score"]), None, ABOVE_Y - 172)
    render_text(screen, font, "HI-SCORE", None, ABOVE_Y - 129)
    render_text(screen, font, str(stats["hi_score"]), None, ABOVE_Y - 86)
    
    if custom_goal:
        render_text(screen, font, custom_goal[0], None, ABOVE_Y - 43)
        render_text(screen, font, custom_goal[1], None, ABOVE_Y)
    else:
        render_text(screen, font, "G O A L", None, ABOVE_Y - 43)
        render_text(screen, font, f'{stats["kills_this_level"]}/{stats["target_enemies"]}', None, ABOVE_Y)

    for lx, ly in stats["lives_positions"]:
        screen.blit(assets.PIXEL_IMG_RAW, (HUD_START_X + lx * CELL_SIZE, HUD_BOARD_Y + ly * CELL_SIZE))

    if stats.get("is_boss_phase") or str(stats.get("level")) == "BOSS":
        render_text(screen, font, "BOSS", None, BELOW_Y + 21)
    elif str(stats.get("level")) == "ENDLESS":
        render_text(screen, font, "ENDLESS", None, BELOW_Y + 21)
    else:
        render_text(screen, font, "LEVEL", LABEL_X, BELOW_Y, align="left")
        render_text(screen, font, str(stats.get("level", 1)), VALUE_X, BELOW_Y, align="right")
    render_text(screen, font, "SPEED", LABEL_X, BELOW_Y + 43, align="left")
    render_text(screen, font, f'{stats["speed_multiplier"]:g}', VALUE_X, BELOW_Y + 43, align="right")

    screen.blit(assets.PAUSE_IMG_BLACK if paused else assets.PAUSE_IMG_INACTIVE, pause_rect)
    screen.blit(sound_img, sound_rect)

def main() -> None:
    global dt_ms

    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_icon(pygame.image.load("assets/PT64ALT.ico"))
    pygame.display.set_caption("Pixel Tanks")
    pygame.mouse.set_visible(False)
    assets.convert_assets()

    clock = pygame.time.Clock()
    dt_ms = 0

    discord_presence = DiscordPresence()
    rpc_timer = 0
    RPC_UPDATE_INTERVAL = 3000

    g_save = save_load.load_global_save()
    apply_custom_tank(g_save)
    def load_font_safe(font_name) -> Font:
        try:
            return pygame.font.Font(f"assets/font/{font_name}.TTF", 43)
        except:
            return pygame.font.SysFont("arial", 43, bold=True)

    font = load_font_safe(g_save.get("font", "DS-DIGI"))
    menu = MainMenu(screen, font)

    pause_rect = assets.PAUSE_IMG_BLACK.get_rect()
    sound_rect = assets.SOUNDS_IMG_BLACK.get_rect()

    ICONS_Y = BELOW_Y + 43 * 5.89
    sound_rect.topleft = (HUD_START_X, ICONS_Y)
    pause_rect.topright = (HUD_START_X + (4 * CELL_SIZE), ICONS_Y)
    
    app_state = "MENU"
    game_state = None
    sounds_enabled = True

    last_selected_slot = None
    last_selected_mode = None
    menu_just_opened = True

    curtain = 0       
    curtain_dir = 0   
    after_curtain = None 
    transition_timer = 0
    TRANSITION_SPEED_MS = 50

    g_save = save_load.load_global_save()
    apply_custom_tank(g_save)
    
    current_volume = g_save.get("volume", 1.0)
    saved_volume = current_volume if current_volume > 0 else 1.0
    is_muted = (current_volume == 0)
    TRANSITION_STYLE = g_save.get("curtain_style", "RIGHT_TO_LEFT")
    
    max_curtain = BOARD_WIDTH if TRANSITION_STYLE in ("RIGHT_TO_LEFT", "LEFT_TO_RIGHT") else BOARD_HEIGHT
    current_trans_speed = TRANSITION_SPEED_MS if max_curtain == BOARD_WIDTH else TRANSITION_SPEED_MS // 2
    
    settings_index = 0
    CURTAIN_OPTIONS = ["RIGHT_TO_LEFT", "LEFT_TO_RIGHT", "TOP_TO_BOTTOM", "BOTTOM_TO_TOP"]

    explosion_frame = 0 
    explosion_timer = 0
    EXPLOSION_SPEED_MS = 150
    explosion_rect = None
    win_timer = 0 # Таймер для экрана победы

    board_rect = pygame.Rect(OFFSET_X, OFFSET_Y, BOARD_WIDTH * CELL_SIZE, BOARD_HEIGHT * CELL_SIZE)

    last_menu_mode = None
    last_menu_slot = None
    current_menu_stats = get_best_mode_stats(menu.selected_mode)
    
    menu_lives_timer = 0
    MENU_LIVES_DELAY = 1000 

    esc_held = False
    esc_hold_timer = 0

    VOLUME_STEP = 0.1

    last_drawn_volume = -1.0 
    current_sound_img = None

    running = True
    while running:
        dt_ms = clock.tick(60)
        rpc_timer += dt_ms
        if rpc_timer >= RPC_UPDATE_INTERVAL:
            rpc_timer = 0
            current_mode = getattr(menu, 'selected_mode', 'A01') if 'menu' in locals() else 'A01'
            
            discord_presence.update(
                app_state=app_state,
                game_state=game_state if 'game_state' in locals() else None,
                current_mode=current_mode
            )

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                if app_state in ("PLAYING", "FROZEN_GAME", "EXPLODING") and game_state:
                    save_game(game_state["mode"], game_state["slot"], game_state["player"], game_state["enemy_manager"], game_state)
                running = False

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_0:
                    if is_muted:
                        is_muted = False
                        current_volume = saved_volume
                    else:
                        saved_volume = current_volume
                        current_volume = 0.0
                        is_muted = True
                    g_save["volume"] = current_volume
                    save_load.save_global_save(g_save)
                elif event.key in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS):
                    if is_muted:
                        is_muted = False
                        current_volume = min(1.0, saved_volume + VOLUME_STEP)
                    else:
                        current_volume = min(1.0, current_volume + VOLUME_STEP)
                    g_save["volume"] = current_volume
                    save_load.save_global_save(g_save)
                elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                    if is_muted:
                        is_muted = False
                        current_volume = max(0.0, saved_volume - VOLUME_STEP)
                    else:
                        current_volume = max(0.0, current_volume - VOLUME_STEP)
                    g_save["volume"] = current_volume
                    save_load.save_global_save(g_save)

            if app_state == "SETTINGS" and curtain_dir == 0:
                FONTS = ["DS-DIGI", "DS-DIGIB", "DS-DIGII", "DS-DIGIT"]
                CURTAIN_OPTIONS = ["RIGHT_TO_LEFT", "LEFT_TO_RIGHT", "TOP_TO_BOTTOM", "BOTTOM_TO_TOP"]
                
                # Динамический список активных пунктов меню
                layout_ids = ["FONT", "CURTAIN", "CUSTOM_TANK"]
                if g_save.get("paint_tank", False):
                    layout_ids.extend(["PAINT_TANK", "R", "G", "B"])
                else:
                    layout_ids.append("PAINT_TANK")
                    
                # Защита от выхода за границы при скрытии элементов
                settings_index = min(settings_index, len(layout_ids) - 1)
                
                if event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                        app_state = "MENU"
                        menu.state = "SETTINGS"
                        curtain_dir = -1
                        after_curtain = None
                        save_load.save_global_save(g_save)
                        pygame.mouse.set_visible(False)
                        apply_custom_tank(g_save)
                    elif event.key in (pygame.K_UP, pygame.K_w):
                        settings_index = (settings_index - 1) % len(layout_ids)
                    elif event.key in (pygame.K_DOWN, pygame.K_s):
                        settings_index = (settings_index + 1) % len(layout_ids)
                    elif event.key in (pygame.K_LEFT, pygame.K_a, pygame.K_RIGHT, pygame.K_d, pygame.K_RETURN, pygame.K_SPACE):
                        direction = -1 if event.key in (pygame.K_LEFT, pygame.K_a) else 1
                        current_id = layout_ids[settings_index]
                        
                        if current_id == "FONT":
                            idx = FONTS.index(g_save.get("font", "DS-DIGI"))
                            g_save["font"] = FONTS[(idx + direction) % len(FONTS)]
                            font = load_font_safe(g_save["font"])
                            menu.font = font
                        elif current_id == "CURTAIN":
                            idx = CURTAIN_OPTIONS.index(g_save.get("curtain_style", "RIGHT_TO_LEFT"))
                            g_save["curtain_style"] = CURTAIN_OPTIONS[(idx + direction) % len(CURTAIN_OPTIONS)]
                            TRANSITION_STYLE = g_save["curtain_style"]
                            
                            # Исправление размера занавеса при смене типа
                            max_curtain = BOARD_WIDTH if TRANSITION_STYLE in ("RIGHT_TO_LEFT", "LEFT_TO_RIGHT") else BOARD_HEIGHT
                            if curtain > 0:
                                curtain = max_curtain
                        elif current_id == "CUSTOM_TANK":
                            if event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_RIGHT, pygame.K_LEFT, pygame.K_d, pygame.K_a):
                                g_save["custom_tank"]["enabled"] = not g_save["custom_tank"].get("enabled", False)
                        elif current_id == "PAINT_TANK":
                            if event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_RIGHT, pygame.K_LEFT, pygame.K_d, pygame.K_a):
                                g_save["paint_tank"] = not g_save.get("paint_tank", False)
                        elif current_id == "R":
                            g_save["rgb"][0] = max(0, min(255, g_save["rgb"][0] + direction * 15))
                        elif current_id == "G":
                            g_save["rgb"][1] = max(0, min(255, g_save["rgb"][1] + direction * 15))
                        elif current_id == "B":
                            g_save["rgb"][2] = max(0, min(255, g_save["rgb"][2] + direction * 15))
                            
                if event.type == pygame.MOUSEBUTTONDOWN and g_save.get("custom_tank", {}).get("enabled", False):
                    mx, my = event.pos
                    ui_offset_x = (WIDTH - (WIDTH - 80)) // 2
                    ui_offset_y = (HEIGHT - (HEIGHT - 160)) // 2

                    preview_x = 80
                    preview_y = 200
                    
                    for cx in range(3):
                        for cy in range(3):
                            rect = pygame.Rect(ui_offset_x + preview_x + cx * CELL_SIZE, ui_offset_y + preview_y + cy * CELL_SIZE, CELL_SIZE, CELL_SIZE)
                            if rect.collidepoint(mx, my):
                                if event.button == 1:
                                    if [cx, cy] not in g_save["custom_tank"]["pixels"]:
                                        g_save["custom_tank"]["pixels"].append([cx, cy])
                                elif event.button == 3:
                                    if [cx, cy] in g_save["custom_tank"]["pixels"]:
                                        g_save["custom_tank"]["pixels"].remove([cx, cy])

            if app_state == "MENU" and curtain_dir == 0:
                result = menu.handle_event(event)
                if result:
                    action, data = result
                    if action == "open_settings":
                        curtain_dir = 1
                        after_curtain = "OPEN_SETTINGS"
                    elif action == "mode_selected":
                        last_menu_slot = menu.selected_slot
                        current_menu_stats = get_menu_stats(menu.selected_mode, menu.selected_slot)
                        menu_lives_timer = 0
                    elif action == "back_to_mode":
                        last_menu_mode = menu.selected_mode
                        current_menu_stats = get_best_mode_stats(menu.selected_mode)
                        menu_lives_timer = 0
                    elif action == "start_slot":
                        curtain_dir = 1
                        after_curtain = "INIT_GAME"
                    elif action == "reset_slot":
                        save_load.delete_save(menu.selected_mode, menu.selected_slot)
                        current_menu_stats = get_menu_stats(menu.selected_mode, menu.selected_slot)

            elif app_state == "PLAYING" and curtain_dir == 0:
                if event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                        esc_held = True

                if event.type == pygame.KEYUP:
                    if event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                        if esc_held and esc_hold_timer < LONG_ESC_MS:
                            game_state["paused"] = not game_state["paused"]
                        esc_held = False
                        esc_hold_timer = 0

                if not game_state["paused"]:
                    player = game_state["player"]
                    if event.type == pygame.KEYDOWN:
                        if event.key in PLAYER_MOVE_KEYS:
                            direction = PLAYER_MOVE_KEYS[event.key]
                            if game_state["logic_mode"].restrict_player_keys(direction):
                                # Создаем группу препятствий для игрока (враги + блоки)
                                obstacles = pygame.sprite.Group(game_state["enemies"].sprites() + game_state["blocks"].sprites())
                                player.handle_keydown(direction, obstacles)
                                
                        if event.key in PLAYER_SHOOT_KEYS:
                            active_player_bullets = sum(1 for b in game_state["bullets"] if b.is_player)
                            max_bullets = 1 if game_state.get("logic_mode") and game_state["logic_mode"].is_boss_phase else 4
                            if active_player_bullets < max_bullets:
                                custom_pixels = g_save.get("custom_tank", {}).get("pixels", [])
                                dir_x, dir_y = player.direction

                                offset_forward = 1 
                                
                                if custom_pixels and g_save.get("custom_tank", {}).get("enabled", False):
                                    axis_pixels = [p for p in custom_pixels if p[0] == 1]
                                    
                                    if axis_pixels:
                                        top_pixel = min(axis_pixels, key=lambda p: p[1])
                                        offset_forward = 1 - top_pixel[1]
                                    else:
                                        offset_forward = 0

                                bullet_grid_x = player.grid_x + (dir_x * offset_forward) + dir_x
                                bullet_grid_y = player.grid_y + (dir_y * offset_forward) + dir_y

                                custom_tank_enabled = g_save.get("custom_tank", {}).get("enabled", False)
                                bullet_color = g_save.get("rgb", [0, 0, 0]) if (g_save.get("paint_tank", False) and custom_tank_enabled) else None

                                bullet = Bullet(player, player.direction, assets.PIXEL_IMG_RAW, is_player=True, custom_color=bullet_color)
                                bullet.grid_x = bullet_grid_x
                                bullet.grid_y = bullet_grid_y
                                bullet.update_position()
                                
                                game_state["bullets"].add(bullet)
                                game_state["all_sprites"].add(bullet)
                                assets.play_sound(assets.PLAYER_SHOOT_SOUND, game_state["sounds_enabled"])

                    if event.type == pygame.KEYUP:
                        if event.key in PLAYER_MOVE_KEYS:
                            player.handle_keyup(PLAYER_MOVE_KEYS[event.key])
        
        for item in assets.__dict__.values():
            if isinstance(item, pygame.mixer.Sound):
                item.set_volume(current_volume)

        target_vol = 0.0 if is_muted else current_volume
        if target_vol != last_drawn_volume:
            last_drawn_volume = target_vol
            r, g, b = int(129 * (1.0 - target_vol)), int(136 * (1.0 - target_vol)), int(111 * (1.0 - target_vol))
            current_sound_img = assets.colorize_icon(assets.SOUNDS_IMG_BASE, (r, g, b, 255))
                
        if esc_held and app_state == "PLAYING" and curtain_dir == 0:
            esc_hold_timer += dt_ms
            if esc_hold_timer >= LONG_ESC_MS:
                esc_held = False
                esc_hold_timer = 0
                save_game(game_state["mode"], game_state["slot"], game_state["player"], game_state["enemy_manager"], game_state)
                app_state = "FROZEN_GAME"
                curtain_dir = 1
                after_curtain = "MENU_FROM_ESC"

        if curtain_dir != 0:
            max_curtain = BOARD_WIDTH if TRANSITION_STYLE in ("RIGHT_TO_LEFT", "LEFT_TO_RIGHT") else BOARD_HEIGHT
            current_trans_speed = TRANSITION_SPEED_MS if max_curtain == BOARD_WIDTH else TRANSITION_SPEED_MS // 2
            
            transition_timer += dt_ms
            if transition_timer >= current_trans_speed:
                transition_timer = 0
                curtain += curtain_dir
                
                if curtain >= max_curtain:
                    curtain = max_curtain
                    if after_curtain == "OPEN_SETTINGS":
                        app_state = "SETTINGS"
                        curtain_dir = 0
                        after_curtain = None
                        pygame.mouse.set_visible(True)
                        settings_index = 0
                    elif after_curtain == "CLOSE_SETTINGS":
                        app_state = "MENU"
                        menu.state = "SETTINGS"
                        curtain_dir = -1
                        after_curtain = None
                        pygame.mouse.set_visible(False)
                        apply_custom_tank(g_save)
                    elif after_curtain == "INIT_GAME":
                        game_state = load_game_slot(menu.selected_mode, menu.selected_slot)
                        game_state["sounds_enabled"] = sounds_enabled
                        if game_state.get("logic_mode"):
                            # Если блоки уже были сохранены и загружены, передаем False
                            is_new = not getattr(game_state["logic_mode"], "blocks_generated", False)
                            game_state["logic_mode"].setup_level(is_new_level=is_new)
                        app_state = "FROZEN_GAME"
                        curtain_dir = -1
                        after_curtain = "START_PLAYING"
                    
                    elif after_curtain == "NEXT_LEVEL_SETUP":
                        game_state["logic_mode"].setup_level(is_new_level=True)
                        game_state["enemy_manager"].clear_enemies()
                        for b in game_state["bullets"]:
                            b.kill()

                        player = game_state["player"]
                        player.grid_x, player.grid_y = random.choice(settings.PLAYER_SPAWN_POINTS)
                        player.update_position()

                        curtain_dir = -1
                        after_curtain = "START_PLAYING"

                    elif after_curtain == "MENU_FROM_ESC":
                        game_state = None
                        app_state = "MENU"
                        curtain_dir = -1
                        after_curtain = None
                        current_menu_stats = get_menu_stats(menu.selected_mode, menu.selected_slot)
                        
                    elif after_curtain == "GO_TO_WIN_PHASE":
                        app_state = "WIN_SHOW"
                        win_timer = 0
                        curtain_dir = -1
                        after_curtain = "WIN_VISIBLE"
                        
                        if game_state["mode"] in (1, 2, 3):
                            save_load.mark_mode_completed(game_state["mode"])
                            menu.g_save = save_load.load_global_save()
                        
                        # Очистка поля для чистого победного экрана
                        game_state["all_sprites"].empty()
                        game_state["blocks"].empty()
                        game_state["enemies"].empty()
                        game_state["bullets"].empty()
                        
                    elif after_curtain == "MENU_FROM_WIN":
                        delete_save(game_state["mode"], game_state["slot"])
                        game_state = None
                        app_state = "MENU"
                        curtain_dir = -1
                        after_curtain = None
                        
                    elif after_curtain == "RESPAWN_OR_GAMEOVER":
                        if game_state["lives"] > 0:
                            pygame.event.get(pygame.KEYDOWN)
                            pygame.event.get(pygame.KEYUP)
                            player = game_state["player"]
                            player.grid_x, player.grid_y = random.choice(PLAYER_SPAWN_POINTS)
                            player.set_direction(NAME_TO_DIRECTION["up"])
                            player.update_position()
                            
                            game_state["enemy_manager"].clear_enemies()
                            for b in game_state["bullets"]:
                                b.kill()
                            game_state["all_sprites"].add(player)
                            
                            # Восстановление босса, если игрок умер во время дуэли
                            if game_state.get("logic_mode"):
                                if game_state["logic_mode"].is_boss_phase:
                                    game_state["logic_mode"].start_boss_phase()
                                else:
                                    # Игрок умер, но уровень старый. Передаем False, чтобы не пересоздавать блоки
                                    game_state["logic_mode"].setup_level(is_new_level=False)
                            
                            app_state = "FROZEN_GAME"
                            curtain_dir = -1
                            after_curtain = "START_PLAYING"
                        else:
                            delete_save(game_state["mode"], game_state["slot"])
                            game_state = None
                            app_state = "MENU"
                            curtain_dir = -1
                            after_curtain = None
                            
                elif curtain <= 0:
                    curtain = 0
                    curtain_dir = 0
                    if after_curtain in ("START_PLAYING", "WIN_VISIBLE"):
                        if after_curtain == "START_PLAYING":
                            app_state = "PLAYING"
                        after_curtain = None
        if app_state == "MENU":
            if (menu_just_opened or 
                menu.selected_slot != last_selected_slot or 
                menu.selected_mode != last_selected_mode):
                
                current_menu_stats = get_menu_stats(menu.selected_mode, menu.selected_slot)
                
                last_selected_slot = menu.selected_slot
                last_selected_mode = menu.selected_mode
                menu_just_opened = False
                
            if current_menu_stats and current_menu_stats.get("is_boss_phase"):
                boss_hp = current_menu_stats.get("boss_hp", 0)
                boss_max_hp = current_menu_stats.get("boss_max_hp", boss_hp)
                if not boss_max_hp or boss_max_hp <= 0:
                    boss_max_hp = boss_hp
                current_goal = ("HP BOSS", f"{boss_hp}/{boss_max_hp}")
            else:
                current_goal = None

        else:
            menu_just_opened = True

        if app_state == "EXPLODING":
            explosion_timer += dt_ms
            if explosion_timer >= EXPLOSION_SPEED_MS:
                explosion_timer = 0
                explosion_frame += 1
                if explosion_frame >= 4:
                    curtain_dir = 1
                    after_curtain = "RESPAWN_OR_GAMEOVER"
                    app_state = "FROZEN_GAME"

        if app_state == "WIN_SHOW" and curtain_dir == 0:
            win_timer += dt_ms
            if win_timer >= 4000:
                curtain_dir = 1
                after_curtain = "MENU_FROM_WIN"

        if app_state == "PLAYING" and not game_state["paused"] and curtain_dir == 0:
            player = game_state["player"]
            bullets = game_state["bullets"]
            enemies = game_state["enemies"]
            enemy_manager = game_state["enemy_manager"]
            all_sprites = game_state["all_sprites"]

            max_enemies, speed_multiplier, spawn_delay = get_difficulty_params(game_state)
            player_obstacles = pygame.sprite.Group(enemies.sprites() + game_state["blocks"].sprites())

            player_stuck = False
            for sprite in player_obstacles:
                if pygame.sprite.collide_mask(player, sprite):
                    player_stuck = True
                    break
            
            if player_stuck:
                tanks_list = [player] + list(enemies)
                nx, ny = find_nearest_empty_cell(player, settings.BOARD_WIDTH, settings.BOARD_HEIGHT, game_state["blocks"], tanks_list)
                player.grid_x, player.grid_y = nx, ny
                player.update_position()

            player.update_movement(dt_ms, collision_group=player_obstacles)
            
            all_ai_obstacles = pygame.sprite.Group(enemies.sprites() + [player] + game_state["blocks"].sprites())
            for enemy in enemies:
                enemy.update_ai(dt_ms, player, all_ai_obstacles, bullets, all_sprites, speed_multiplier)

            bullets.update(dt_ms)

            player_bullets = [b for b in bullets if b.is_player]
            enemy_bullets = [b for b in bullets if not b.is_player]
            enemy_bullets_group = pygame.sprite.Group(enemy_bullets)

            for pb in player_bullets:
                collision_method = bullet_collide if game_state["logic_mode"].enhanced_bullet_collision else hitbox_collide  
                collided = pygame.sprite.spritecollide(pb, enemy_bullets_group, False, collision_method)
                if collided:
                    pb.kill()
                    for eb in collided:
                        eb.kill()

            for bullet in bullets.sprites():
                if not bullet.alive():
                    continue

                hit_blocks = pygame.sprite.spritecollide(bullet, game_state["blocks"], True, hitbox_collide)
                if hit_blocks:
                    bullet.kill()
                    continue

                if bullet.is_player:
                    hit_list = pygame.sprite.spritecollide(bullet, enemies, False, hitbox_collide)
                    if hit_list:
                        bullet.kill()
                        for e in hit_list:
                            if isinstance(e, DefaultBoss):
                                if e.hurt_hitbox.colliderect(bullet.rect):
                                    e.hp -= 1

                                    save_game(game_state["mode"], game_state["slot"], game_state["player"], game_state["enemy_manager"], game_state)
                                    
                                    if e.hp <= 0:
                                        e.kill()
                                    # assets.play_sound(assets.EXPLOSION_SOUND, game_state["sounds_enabled"])
                            else:
                                e.kill()
                                assets.play_sound(assets.EXPLOSION_SOUND, game_state["sounds_enabled"])
                                game_state["kills_this_level"] += 1
                                game_state["global_kills"] += 1
                                game_state["score"] += 100
                                if game_state["score"] > game_state["hi_score"]:
                                    game_state["hi_score"] = game_state["score"]
                                    save_hi_score(game_state["mode"], game_state["hi_score"])
                else:
                    if hitbox_collide(bullet, player):
                        bullet.kill()
                        all_sprites.remove(player)
                        assets.play_sound(assets.EXPLOSION_SOUND, game_state["sounds_enabled"])
                        game_state["lives"] -= 1
                        game_state["lives_positions"] = generate_lives_positions(game_state["lives"])

                        app_state = "EXPLODING"
                        explosion_frame, explosion_timer = 0, 0
                        explosion_rect = pygame.Rect(0, 0, 172, 172)
                        pixel_x = OFFSET_X + ((player.grid_x + random.choice([-2, -1])) * CELL_SIZE)
                        pixel_y = OFFSET_Y + ((player.grid_y + random.choice([-2, -1])) * CELL_SIZE)
                        explosion_rect.topleft = (pixel_x, pixel_y)
                        explosion_rect.clamp_ip(board_rect)
                        break

            if app_state == "PLAYING" and not game_state["logic_mode"].is_boss_phase:
                remaining_kills = game_state["target_enemies"] - game_state["kills_this_level"]
                actual_max = min(max_enemies, max(0, remaining_kills))
                enemy_manager.spawn_enemy_if_needed(dt_ms, actual_max, spawn_delay)

            if app_state == "PLAYING" and game_state.get("logic_mode"):
                action = game_state["logic_mode"].check_conditions()
                if action == "NEXT_LEVEL":
                    app_state = "FROZEN_GAME"
                    curtain_dir = 1
                    after_curtain = "NEXT_LEVEL_SETUP"
                elif action == "BOSS_PHASE_START":
                    pass 
                elif action == "WIN_SCREEN":
                    app_state = "FROZEN_GAME"
                    curtain_dir = 1
                    after_curtain = "GO_TO_WIN_PHASE"

        screen.fill(BACKGROUND_COLOR)
        screen.blit(assets.BACKGROUND_IMG, (0, 0))

        if app_state == "MENU":
            frame_changed = menu.update(dt_ms)

            if menu.selected_slot != last_menu_slot:
                last_menu_slot = menu.selected_slot

                old_lives_positions = current_menu_stats.get("lives_positions") if current_menu_stats else None
                old_lives_count = current_menu_stats.get("lives", 4) if current_menu_stats else 4

                current_menu_stats = get_menu_stats(menu.selected_mode, menu.selected_slot)
                if old_lives_positions and current_menu_stats.get("lives", 4) == old_lives_count:
                    current_menu_stats["lives_positions"] = old_lives_positions
                else:
                    current_menu_stats["lives_positions"] = generate_lives_positions(current_menu_stats.get("lives", 4))

            if frame_changed and current_menu_stats:
                current_menu_stats["lives_positions"] = generate_lives_positions(current_menu_stats.get("lives", 4))
            elif current_menu_stats and "lives_positions" not in current_menu_stats:
                current_menu_stats["lives_positions"] = generate_lives_positions(current_menu_stats.get("lives", 4))
            
            menu.draw()
            current_goal = None
            if current_menu_stats.get("is_boss_phase"):
                current_goal = ("HP BOSS", f"{current_menu_stats.get('boss_hp', 0)}/{current_menu_stats.get('boss_max_hp', 0)}")
            elif menu.selected_mode == 5:
                current_goal = ("G O A L", str(current_menu_stats.get("global_kills", 0)))
                
            is_settings_mode = (menu.state == "SETTINGS")
            render_hud(screen, font, current_menu_stats, current_sound_img, False, pause_rect, sound_rect, custom_goal=current_goal, is_settings=is_settings_mode)

            if menu.state == "SLOT" and curtain_dir == 0:
                box_width = 460
                box_height = 420
                ui_surf = pygame.Surface((box_width, box_height), pygame.SRCALPHA)
                pygame.draw.rect(ui_surf, (0, 0, 0, 220), ui_surf.get_rect(), border_radius=15)
                
                slot_str = f"< SLOT {menu.selected_slot:02d} >"
                slot_surf = font.render(slot_str, True, (255, 255, 0))
                ui_surf.blit(slot_surf, slot_surf.get_rect(center=(box_width//2, 30)))
                
                y_offset = 80
                line_spacing = 45
                
                def draw_stat(label, value, y):
                    lbl_s = font.render(label, True, (255, 255, 255))
                    val_s = font.render(str(value), True, (255, 255, 0))
                    ui_surf.blit(lbl_s, (40, y))
                    val_r = val_s.get_rect(topright=(box_width - 40, y))
                    ui_surf.blit(val_s, val_r)

                s = current_menu_stats
                draw_stat("SCORE:", s.get("score", 0), y_offset); y_offset += line_spacing
                draw_stat("HI-SCORE:", s.get("hi_score", 0), y_offset); y_offset += line_spacing
                
                if s.get("is_boss_phase"):
                    draw_stat("HP BOSS:", f"{s.get('boss_hp',0)}/{s.get('boss_max_hp',0)}", y_offset)
                else:
                    draw_stat("GOAL:", f"{s.get('kills_this_level',0)}/{s.get('target_enemies',0)}", y_offset)
                y_offset += line_spacing
                
                draw_stat("LIVES:", s.get("lives", 4), y_offset); y_offset += line_spacing
                
                lvl_str = "BOSS" if s.get("is_boss_phase") else ("ENDLESS" if str(s.get("level")) == "ENDLESS" else s.get("level", 1))
                draw_stat("LEVEL:", lvl_str, y_offset); y_offset += line_spacing
                
                draw_stat("SPEED:", f"{s.get('speed_multiplier', 1.0):g}", y_offset); y_offset += line_spacing
                
                hint_str = "PRESS [R] TO RESET"
                hint_surf = font.render(hint_str, True, (150, 150, 150))
                hint_rect = hint_surf.get_rect(center=(box_width//2, box_height - 30))
                ui_surf.blit(hint_surf, hint_rect)

                screen.blit(ui_surf, ((WIDTH - box_width) // 2, (HEIGHT - box_height) // 2))

        elif app_state in ("PLAYING", "FROZEN_GAME", "EXPLODING", "WIN_SHOW"):
            if game_state:
                is_curtain_active = (curtain > 0)
                
                if g_save.get("custom_tank", {}).get("enabled", False):
                    apply_custom_tank(g_save, force_colorless=is_curtain_active)
                    player = game_state["player"]
                    player.base_image = assets.PLAYER_BASE_IMG
                    player.update_image()
                
                for bullet in game_state["bullets"]:
                    if bullet.is_player and hasattr(bullet, "update_curtain_shading"):
                        bullet.update_curtain_shading(is_curtain_active)

                game_state["all_sprites"].draw(screen)
                game_state["blocks"].draw(screen)

                if app_state == "EXPLODING" and explosion_rect is not None:
                    img_idx = 0 if explosion_frame % 2 == 0 else 1
                    if len(assets.EXPLOSION_IMGS) > img_idx:
                        screen.blit(assets.EXPLOSION_IMGS[img_idx], explosion_rect)

                if app_state == "WIN_SHOW" and assets.WIN_IMG:
                    win_rect = assets.WIN_IMG.get_rect(center=(WIDTH // 2, HEIGHT // 2))
                    screen.blit(assets.WIN_IMG, win_rect)

                max_enemies, speed_multiplier, spawn_delay = get_difficulty_params(game_state)
                target_enemies = game_state["target_enemies"]
                
                if game_state.get("logic_mode"):
                    target_enemies = game_state["logic_mode"].target_kills
                    is_boss = game_state["logic_mode"].is_boss_phase
                    current_level = "BOSS" if is_boss else game_state["level"]
                else:
                    is_boss = False
                    current_level = game_state["level"]

                stats = {
                    "score": game_state["score"], 
                    "hi_score": game_state["hi_score"],
                    "kills_this_level": game_state["kills_this_level"], 
                    "target_enemies": target_enemies, 
                    "level": current_level,
                    "speed_multiplier": speed_multiplier,
                    "lives_positions": game_state["lives_positions"],
                    "is_boss_phase": is_boss
                }
                current_goal = game_state["logic_mode"].get_custom_hud_goal() if game_state.get("logic_mode") else None
                render_hud(screen, font, stats, current_sound_img, game_state["paused"], pause_rect, sound_rect, custom_goal=current_goal)
        
        if esc_hold_timer > 200 and app_state in ("PLAYING", "FROZEN_GAME"):
            opacity = min(255, int((esc_hold_timer / LONG_ESC_MS) * 255))
            text_str = "Returning to menu..."
            text_color = (83, 0, 255)
            text_surf = font.render(text_str, True, text_color)
            box_width = text_surf.get_width() + 20
            box_height = text_surf.get_height() + 10
            ui_surf = pygame.Surface((box_width, box_height), pygame.SRCALPHA)
            pygame.draw.rect(ui_surf, (0, 0, 0, opacity), ui_surf.get_rect(), border_radius=5)
            text_surf.set_alpha(opacity)
            ui_surf.blit(text_surf, (10, 5))
            screen.blit(ui_surf, (15, 15))

        if curtain > 0:
            t_img = assets._PIXEL_IMG_RAW

            if TRANSITION_STYLE == "RIGHT_TO_LEFT":
                for step in range(curtain):
                    col = BOARD_WIDTH - 1 - step
                    for row in range(BOARD_HEIGHT):
                        screen.blit(t_img, (OFFSET_X + col * CELL_SIZE, OFFSET_Y + row * CELL_SIZE))
                        
            elif TRANSITION_STYLE == "LEFT_TO_RIGHT":
                for step in range(curtain):
                    col = step
                    for row in range(BOARD_HEIGHT):
                        screen.blit(t_img, (OFFSET_X + col * CELL_SIZE, OFFSET_Y + row * CELL_SIZE))
                        
            elif TRANSITION_STYLE == "TOP_TO_BOTTOM":
                for step in range(curtain):
                    row = step
                    for col in range(BOARD_WIDTH):
                        screen.blit(t_img, (OFFSET_X + col * CELL_SIZE, OFFSET_Y + row * CELL_SIZE))
                        
            elif TRANSITION_STYLE == "BOTTOM_TO_TOP":
                for step in range(curtain):
                    row = BOARD_HEIGHT - 1 - step
                    for col in range(BOARD_WIDTH):
                        screen.blit(t_img, (OFFSET_X + col * CELL_SIZE, OFFSET_Y + row * CELL_SIZE))
        
        if app_state == "SETTINGS":
            render_hud(screen, font, {}, current_sound_img, False, pause_rect, sound_rect, is_settings=True)
            
            box_width = WIDTH - 80
            box_height = HEIGHT - 160
            ui_surf = pygame.Surface((box_width, box_height), pygame.SRCALPHA)
            pygame.draw.rect(ui_surf, (0, 0, 0, 200), ui_surf.get_rect(), border_radius=15)
            
            def draw_settings_text(text_str, y_pos, is_selected) -> None:
                color = (255, 255, 0) if is_selected else (255, 255, 255)
                tsurf = font.render(text_str, True, color)
                ui_surf.blit(tsurf, (40, y_pos))

            layout_ids = ["FONT", "CURTAIN", "CUSTOM_TANK"]
            if g_save.get("paint_tank", False):
                layout_ids.extend(["PAINT_TANK", "R", "G", "B"])
            else:
                layout_ids.append("PAINT_TANK")
                
            settings_index = min(settings_index, len(layout_ids) - 1)
            active_id = layout_ids[settings_index]

            current_y = 40
            draw_settings_text(f"FONT: < {g_save.get('font', 'DS-DIGI')} >", current_y, active_id == "FONT")
            current_y += 40
            
            draw_settings_text(f"CURTAIN: < {g_save.get('curtain_style', 'RIGHT_TO_LEFT')} >", current_y, active_id == "CURTAIN")
            current_y += 40
            
            draw_settings_text(f"CUSTOM TANK: {'[X]' if g_save.get('custom_tank', {}).get('enabled') else '[ ]'}", current_y, active_id == "CUSTOM_TANK")
            current_y += 40
            
            if g_save.get("custom_tank", {}).get("enabled", False):
                preview_x = 80
                preview_y = current_y + 10

                bg_rect = pygame.Rect(preview_x, preview_y, 3 * CELL_SIZE, 3 * CELL_SIZE)
                pygame.draw.rect(ui_surf, (137, 145, 113), bg_rect)

                empty_surf = pygame.Surface((CELL_SIZE, CELL_SIZE), pygame.SRCALPHA)                    
                if assets.PIXEL_IMG_RAW:
                    base_col = assets.colorize_icon(assets.PIXEL_IMG_RAW, (129, 136, 111, 255))
                    empty_surf.blit(base_col, (0, 0))
                
                for cx in range(3):
                    for cy in range(3):
                        x = preview_x + cx * CELL_SIZE
                        y = preview_y + cy * CELL_SIZE
                        ui_surf.blit(empty_surf, (x, y))
                        
                for px, py in g_save["custom_tank"].get("pixels", []):
                    x = preview_x + px * CELL_SIZE
                    y = preview_y + py * CELL_SIZE
                    
                    if g_save.get("paint_tank", False):
                        rgb = g_save.get("rgb", [129, 136, 111])
                        if assets.PIXEL_COLOR_IMG_RAW:
                            c_img = assets.colorize_icon(assets.PIXEL_COLOR_IMG_RAW, (*rgb, 255))
                            ui_surf.blit(c_img, (x, y))
                    else:
                        if assets.PIXEL_COLOR_IMG_RAW:
                            c_img = assets.colorize_icon(assets.PIXEL_COLOR_IMG_RAW, (129, 136, 111, 255))
                            ui_surf.blit(c_img, (x, y))
                            
                    if assets.PIXEL_IMG_RAW:
                        ui_surf.blit(assets.PIXEL_IMG_RAW, (x, y))

                current_y += 3 * CELL_SIZE + 20
            
            draw_settings_text(f"PAINT TANK: {'[X]' if g_save.get('paint_tank') else '[ ]'}", current_y, active_id == "PAINT_TANK")
            current_y += 40
            
            if g_save.get("paint_tank", False):
                rgb = g_save.get("rgb", [129, 136, 111])
                draw_settings_text(f"R: < {rgb[0]:03d} >", current_y, active_id == "R")
                current_y += 40
                draw_settings_text(f"G: < {rgb[1]:03d} >", current_y, active_id == "G")
                current_y += 40
                draw_settings_text(f"B: < {rgb[2]:03d} >", current_y, active_id == "B")
                current_y += 40

            screen.blit(ui_surf, ((WIDTH - box_width) // 2, (HEIGHT - box_height) // 2))

        pygame.display.flip()

    discord_presence.close()
    pygame.quit()

if __name__ == "__main__":
    main()
