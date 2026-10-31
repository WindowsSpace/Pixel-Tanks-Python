# Главный цикл игры. Запуск: python game.py из корня проекта

import pygame
import random
import os

from services.discord_activity import DiscordActivity
from pygame.font import Font

from core import assets
from core import settings

from core.utils import generate_lives_positions, level_to_int, find_explosion_spot
from core.grid import get_cell_topleft

from modes.mode_config import get_mode_class
from core.settings import WIDTH, HEIGHT, \
    PLAYER_SPAWN_POINTS, \
    HUD_START_X, HUD_BOARD_Y, \
    CELL_SIZE, OFFSET_X, OFFSET_Y, \
    BOARD_WIDTH, BOARD_HEIGHT, \
    DIR_UP, DIR_DOWN, DIR_LEFT, DIR_RIGHT
from core.controls import Controls, ACTION_LABELS, DUAL_ACTIONS, event_token, label as bind_label
from entities.tank import PlayerTank, DefaultBoss
from entities.bullet import Bullet
from entities.enemy_manager import EnemyManager
from ui.menu import MainMenu
from entities.blocks import find_nearest_empty_cell
import models
from ui import hud
from ui import os_hud
from ui import corruption as corruption_event

from services import save_load
from services import boss_music
from ui import hp_break
from ui import boss_window
from ui import final_windows
from services.save_load import save_game, load_game, load_hi_score, save_hi_score, delete_save, get_menu_stats, get_best_mode_stats

from core.collision import bullet_collide, hitbox_collide
from core.custom_tank import apply_custom_tank, build_tank_surface
from core.session import get_difficulty_params, load_game_slot
from ui.draw import draw_group_culled, draw_procedural_outer_frame, render_hud, visible_curtain_cells
from ui.window import settings_pages, CONTROL_ACTIONS, settings_page_name_is_tank, build_settings_layout, get_board_model_for_state, get_layout_for_state, get_logical_size, get_window_logical_size


LONG_ESC_MS = 800

DIRECTION_TO_NAME = {DIR_UP: "up", DIR_DOWN: "down", DIR_LEFT: "left", DIR_RIGHT: "right"}
NAME_TO_DIRECTION = {v: k for k, v in DIRECTION_TO_NAME.items()}

def main() -> None:
    global dt_ms

    pygame.init()

    infoObject = pygame.display.Info()
    monitor_w, monitor_h = infoObject.current_w, infoObject.current_h

    g_save = save_load.load_global_save()
    user_scale = g_save.get("scale", 1.0)
    hud.set_docked_only(g_save.get("fullscreen", False))  # в полноэкране окна ОС не используем
    os_hud_mgr = os_hud.OSHud()

    def apply_scale_and_mode(layout_state, scale):
        # Окно подстраивается под тип HUD и режим: layout_state - game_state или None
        base_w, base_h = get_window_logical_size(layout_state)
        is_fullscreen = g_save.get("fullscreen", False)
        
        if is_fullscreen:
            max_scale = min(monitor_w / base_w, monitor_h / base_h)
            aw, ah = int(base_w * max_scale), int(base_h * max_scale)
            r_screen = pygame.display.set_mode((monitor_w, monitor_h), pygame.FULLSCREEN)
            return r_screen, max_scale, aw, ah, base_w, base_h
        else:
            safe_w = monitor_w - 50
            safe_h = monitor_h - 100

            max_scale = int(min(safe_w / base_w, safe_h / base_h) * 10) / 10.0
            
            # Если окно (например, WINDOWS) не влезает - уменьшаем только на время игры
            if scale > max_scale:
                scale = max_scale

            aw, ah = int(base_w * scale), int(base_h * scale)
            
            os.environ['SDL_VIDEO_CENTERED'] = '1' 
            r_screen = pygame.display.set_mode((aw, ah))
            return r_screen, scale, aw, ah, base_w, base_h

    active_mode = "A01"
    real_screen, user_scale, actual_w, actual_h, base_w, base_h = apply_scale_and_mode(None, user_scale)
    ui_surface = pygame.Surface((base_w, base_h))
    virtual_screen = pygame.Surface((base_w, base_h))  # размер видимой области; пересоздаётся при рендере

    pygame.display.set_icon(pygame.image.load(settings.GAME_ICON))
    pygame.display.set_caption("Pixel Tanks")
    pygame.mouse.set_visible(False)

    clock = pygame.time.Clock()
    dt_ms = 0

    discord_activity = DiscordActivity()  # работает в фоновом потоке, игру не блокирует
    rpc_timer = 0
    RPC_UPDATE_INTERVAL = 1000

    assets.convert_assets()
    # размер окошек sounds/pause в HUD зависит от размера этих иконок
    hud.set_icon_content_size(max(assets.SOUNDS_IMG_BLACK.get_width(), assets.PAUSE_IMG_BLACK.get_width()),
                              max(assets.SOUNDS_IMG_BLACK.get_height(), assets.PAUSE_IMG_BLACK.get_height()))
    apply_custom_tank(g_save)

    def load_font_safe(font_name) -> Font:
        try:
            return pygame.font.Font(f"assets/font/{font_name}.TTF", 43)
        except:
            return pygame.font.SysFont("arial", 43, bold=True)

    font = load_font_safe(g_save.get("font", "DS-DIGI"))
    menu = MainMenu(ui_surface, font)
    controls = Controls(g_save)  # настраиваемое управление (по два бинда на действие)
    menu.controls = controls

    # После хэллоуинского "сбоя танка": режим D открыт
    if g_save.get("tank_corrupted", False):
        menu.unlock_mode_d()
        if corruption_event.OPEN_D01_EVERY_LAUNCH or not g_save.get("corrupted_menu_seen", False):
            menu.open_mode("MODE_D", 1)
            g_save["corrupted_menu_seen"] = True
            save_load.save_global_save(g_save)

    pause_rect = assets.PAUSE_IMG_BLACK.get_rect()
    sound_rect = assets.SOUNDS_IMG_BLACK.get_rect()

    get_layout_for_state(None).place_icons(sound_rect, pause_rect)
    
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
    
    current_volume = g_save.get("volume", 1.0)
    saved_volume = current_volume if current_volume > 0 else 1.0
    is_muted = (current_volume == 0)
    TRANSITION_STYLE = g_save.get("curtain_style", "RIGHT_TO_LEFT")
    
    # Шторка ложится на клетки САМОГО поля, которые сейчас видны в кадре
    curtain_cols, curtain_rows = BOARD_WIDTH, BOARD_HEIGHT
    curtain_rc = pygame.Rect(OFFSET_X, OFFSET_Y, BOARD_WIDTH * CELL_SIZE, BOARD_HEIGHT * CELL_SIZE)
    curtain_cells = {"cols": [], "rows": [], "r0": 0, "r1": 0, "c0": 0, "c1": 0, "origin": (0, 0), "board": []}
    max_curtain = curtain_cols if TRANSITION_STYLE in ("RIGHT_TO_LEFT", "LEFT_TO_RIGHT") else curtain_rows
    current_trans_speed = TRANSITION_SPEED_MS if TRANSITION_STYLE in ("RIGHT_TO_LEFT", "LEFT_TO_RIGHT") else TRANSITION_SPEED_MS // 2
    
    settings_index = 0
    settings_page = 0  # вкладка настроек: DISPLAY / TANK / CONTROLS
    bind_slot = 0  # какая из двух ячеек бинда выбрана
    bind_capture = None  # {"action", "slot", "esc_t"} - ждём новую клавишу/кнопку мыши
    bind_message, bind_message_until = "", 0
    ACTION_DIRS = {"up": DIR_UP, "down": DIR_DOWN, "left": DIR_LEFT, "right": DIR_RIGHT}
    DIR_ACTIONS = {v: k for k, v in ACTION_DIRS.items()}
    CURTAIN_OPTIONS = ["RIGHT_TO_LEFT", "LEFT_TO_RIGHT", "TOP_TO_BOTTOM", "BOTTOM_TO_TOP"]

    corruption = None  # TankCorruption - идёт событие "сбой танка"

    def start_corruption():
        # танк игрока по текущим настройкам (чёрный цвет)
        return corruption_event.TankCorruption(build_tank_surface(g_save, use_color=True),
                                               (base_w, base_h), assets.REDACTED_SOUND)

    explosion_frame = 0 
    explosion_timer = 0
    EXPLOSION_SPEED_MS = 150
    explosion_rect = None
    explosion_imgs = []  # кадры взрыва в цвет игрока (собираются в момент гибели)
    win_timer = 0  # Таймер для экрана победы

    board_rect = pygame.Rect(OFFSET_X, OFFSET_Y, BOARD_WIDTH * CELL_SIZE, BOARD_HEIGHT * CELL_SIZE)

    last_menu_slot = None
    current_menu_stats = get_best_mode_stats(menu.selected_mode)

    esc_held = False
    esc_hold_timer = 0

    VOLUME_STEP = 0.1

    last_drawn_volume = -1.0 
    current_sound_img = None

    running = True
    while running:
        dt_ms = clock.tick(60)

        active_mode = getattr(menu, 'selected_mode', 'A01')
        if game_state: active_mode = game_state["mode"]
            
        layout_top = get_layout_for_state(game_state)
        current_win_size = (layout_top.win_w, layout_top.win_h)

        # virtual_screen теперь размером с ВИДИМУЮ область (а не со всю карту)
            
        # Пересоздаем физическое окно, если изменились лимиты
        if current_win_size != (base_w, base_h):
            os_hud_mgr.main_changed()  # окна HUD убираем до смены окна и ставим после
            # user_scale не перезаписываем: это предпочтение пользователя, а не текущий
            real_screen, _eff_scale, actual_w, actual_h, base_w, base_h = apply_scale_and_mode(game_state, user_scale)
            ui_surface = pygame.Surface((base_w, base_h))
            menu.screen = ui_surface
            
        # Обновляем координаты кнопок HUD относительно окна
        current_hud_x = layout_top.hud_x
        layout_top.place_icons(sound_rect, pause_rect)

        rpc_timer += dt_ms
        if rpc_timer >= RPC_UPDATE_INTERVAL:
            rpc_timer = 0
            current_mode = getattr(menu, 'selected_mode', 'A01') if 'menu' in locals() else 'A01'
            
            discord_activity.update(
                app_state=app_state,
                game_state=game_state if 'game_state' in locals() else None,
                current_mode=current_mode
            )

        for event in pygame.event.get():
            close_kind = os_hud_mgr.handle_event(event)
            if close_kind == "hud":
                continue  # закрыли HUD-окно - игра идёт дальше
            if event.type == pygame.QUIT or (close_kind == "main" and os_hud_mgr.items):
                if app_state in ("PLAYING", "FROZEN_GAME", "EXPLODING") and game_state:
                    save_game(game_state["mode"], game_state["slot"], game_state["player"], game_state["enemy_manager"], game_state)
                running = False

            if corruption is not None:
                continue  # "сбой": все кнопки заблокированы

            # Настраиваемое управление: какое действие вызвало событие
            ctl_down = controls.action_down(event)
            ctl_up = controls.action_up(event)
            if event.type == getattr(pygame, "WINDOWFOCUSLOST", -1):
                controls.clear_held()

            # Отпускание клавиши движения доходит до танка ВСЕГДА - и во время шторки
            if ctl_up[0] in ACTION_DIRS and ctl_up[1] and game_state:
                game_state["player"].handle_keyup(ACTION_DIRS[ctl_up[0]])

            if bind_capture is None and ctl_down in ("mute", "vol_up", "vol_down"):
                if ctl_down == "mute":
                    if is_muted:
                        is_muted = False
                        current_volume = saved_volume
                    else:
                        saved_volume = current_volume
                        current_volume = 0.0
                        is_muted = True
                elif ctl_down == "vol_up":
                    if is_muted:
                        is_muted = False
                        current_volume = min(1.0, saved_volume + VOLUME_STEP)
                    else:
                        current_volume = min(1.0, current_volume + VOLUME_STEP)
                else:
                    if is_muted:
                        is_muted = False
                        current_volume = max(0.0, saved_volume - VOLUME_STEP)
                    else:
                        current_volume = max(0.0, current_volume - VOLUME_STEP)
                g_save["volume"] = current_volume
                save_load.save_global_save(g_save)
                if ctl_down == "vol_up":
                    assets.play_sound(assets.VOLUME_UP_SOUND, sounds_enabled)
                elif ctl_down == "vol_down":
                    assets.play_sound(assets.VOLUME_DOWN_SOUND, sounds_enabled)

            if app_state == "SETTINGS" and curtain_dir == 0:
                FONTS = ["DS-DIGI", "DS-DIGIB", "DS-DIGII", "DS-DIGIT"]
                CURTAIN_OPTIONS = ["RIGHT_TO_LEFT", "LEFT_TO_RIGHT", "TOP_TO_BOTTOM", "BOTTOM_TO_TOP"]

                layout_ids = build_settings_layout(g_save, settings_page)
                settings_index = min(settings_index, len(layout_ids) - 1)
                # Навигация - только по вашим биндам (клавиши и кнопки мыши)
                nav = controls.menu_action(event)
                if nav and event.type == pygame.MOUSEBUTTONDOWN and settings_page_name_is_tank(settings_page, g_save):
                    _mx, _my = int(event.pos[0] / user_scale), int(event.pos[1] / user_scale)
                    _px = (WIDTH - (WIDTH - 80)) // 2 + 80 + CELL_SIZE
                    _py = (HEIGHT - (HEIGHT - 160)) // 2 + 130 + CELL_SIZE
                    if _px <= _mx < _px + 3 * CELL_SIZE and _py <= _my < _py + 3 * CELL_SIZE:
                        nav = None

                if bind_capture is not None:
                    # ждём новую клавишу или кнопку мыши для выбранной ячейки
                    new_token = None
                    if event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_ESCAPE:
                            # короткое нажатие ESC - отмена, удержание ~0.8
                            bind_capture["esc_t"] = pygame.time.get_ticks()
                        else:
                            new_token = event_token(event)
                    elif event.type == pygame.KEYUP and event.key == pygame.K_ESCAPE:
                        bind_capture = None
                    elif event.type == pygame.MOUSEBUTTONDOWN:
                        new_token = event_token(event)  # колёсико (4/5) не назначается

                    if new_token and bind_capture is not None:
                        bind_message = controls.assign(bind_capture["action"], bind_capture["slot"], new_token) or "OK"
                        bind_message_until = pygame.time.get_ticks() + 2500
                        controls.save_to(g_save)
                        save_load.save_global_save(g_save)
                        bind_capture = None

                elif nav or (event.type == pygame.KEYDOWN and event.key in (pygame.K_DELETE, pygame.K_r)):
                    current_id = layout_ids[settings_index]

                    if event.type == pygame.KEYDOWN and event.key == pygame.K_r:
                        # R - сбросить настройки ТЕКУЩЕЙ вкладки до стандартных (как R в слотах меню)
                        defaults = save_load.default_global_save()
                        page_now = settings_pages(g_save)[settings_page]
                        if page_now == "CONTROLS":
                            controls.reset()
                            controls.save_to(g_save)
                        elif page_now == "TANK":
                            for key in ("paint_tank", "rgb", "custom_tank"):
                                g_save[key] = defaults[key]
                            apply_custom_tank(g_save)
                        else:
                            for key in ("font", "curtain_style"):
                                g_save[key] = defaults[key]
                            font = load_font_safe(g_save["font"])
                            menu.font = font
                            TRANSITION_STYLE = g_save["curtain_style"]
                            max_scale = min(monitor_w / base_w, monitor_h / base_h)
                            new_scale = min(1.0, max_scale)
                            if new_scale != user_scale:
                                user_scale = new_scale
                                os_hud_mgr.main_changed()
                                real_screen, user_scale, actual_w, actual_h, base_w, base_h = apply_scale_and_mode(game_state, user_scale)
                                ui_surface = pygame.Surface((base_w, base_h))
                                menu.screen = ui_surface
                            g_save["scale"] = user_scale
                        save_load.save_global_save(g_save)
                        bind_message = "SETTINGS RESET"
                        bind_message_until = pygame.time.get_ticks() + 2500
                    elif event.type == pygame.KEYDOWN and event.key == pygame.K_DELETE:
                        if current_id.startswith("BIND:"):
                            bind_message = controls.clear(current_id[5:], bind_slot) or "CLEARED"
                            bind_message_until = pygame.time.get_ticks() + 2500
                            controls.save_to(g_save)
                            save_load.save_global_save(g_save)
                    elif nav == "back":
                        app_state = "MENU"
                        menu.state = "SETTINGS"
                        curtain_dir = -1
                        after_curtain = None
                        bind_capture = None
                        controls.save_to(g_save)
                        save_load.save_global_save(g_save)
                        menu.g_save = g_save
                        pygame.mouse.set_visible(False)
                        apply_custom_tank(g_save)
                    elif nav == "up":
                        settings_index = (settings_index - 1) % len(layout_ids)
                    elif nav == "down":
                        settings_index = (settings_index + 1) % len(layout_ids)
                    elif nav in ("left", "right", "confirm"):
                        direction = -1 if nav == "left" else 1

                        if current_id == "PAGE":
                            settings_page = (settings_page + direction) % len(settings_pages(g_save))
                            settings_index, bind_slot = 0, 0
                        elif current_id.startswith("BIND:"):
                            action = current_id[5:]
                            slots_count = 2 if action in DUAL_ACTIONS else 1
                            bind_slot = min(bind_slot, slots_count - 1)
                            if nav == "confirm":
                                bind_capture = {"action": action, "slot": bind_slot, "esc_t": None}
                                controls.clear_held()
                            else:
                                bind_slot = (bind_slot + direction) % slots_count
                        elif current_id == "SCALE":
                            step = 0.1 * direction
                            new_scale = round(user_scale + step, 1)

                            max_scale = min(monitor_w / base_w, monitor_h / base_h)
                            new_scale = max(0.5, min(new_scale, max_scale))

                            if new_scale != user_scale:
                                user_scale = new_scale
                                g_save["scale"] = user_scale
                                os_hud_mgr.main_changed()
                                real_screen, user_scale, actual_w, actual_h, base_w, base_h = apply_scale_and_mode(game_state, user_scale)
                                ui_surface = pygame.Surface((base_w, base_h))
                                menu.screen = ui_surface
                        elif current_id == "FONT":
                            idx = FONTS.index(g_save.get("font", "DS-DIGI"))
                            g_save["font"] = FONTS[(idx + direction) % len(FONTS)]
                            font = load_font_safe(g_save["font"])
                            menu.font = font
                        elif current_id == "CURTAIN":
                            idx = CURTAIN_OPTIONS.index(g_save.get("curtain_style", "RIGHT_TO_LEFT"))
                            g_save["curtain_style"] = CURTAIN_OPTIONS[(idx + direction) % len(CURTAIN_OPTIONS)]
                            TRANSITION_STYLE = g_save["curtain_style"]

                            max_curtain = curtain_cols if TRANSITION_STYLE in ("RIGHT_TO_LEFT", "LEFT_TO_RIGHT") else curtain_rows
                            if curtain > 0:
                                curtain = max_curtain
                        elif current_id == "CUSTOM_TANK":
                            g_save["custom_tank"]["enabled"] = not g_save["custom_tank"].get("enabled", False)
                        elif current_id == "PAINT_TANK":
                            g_save["paint_tank"] = not g_save.get("paint_tank", False)
                        elif current_id in ("R", "G", "B"):
                            ch = "RGB".index(current_id)
                            old_val = g_save["rgb"][ch]
                            g_save["rgb"][ch] = max(0, min(255, old_val + direction * 15))
                            # Цвет стал полностью чёрным (именно из-за этого нажатия) - начинается "сбой"
                            if g_save["rgb"][ch] != old_val and not any(g_save["rgb"]):
                                if g_save.get("tank_restored", False):
                                    g_save["rgb"][ch] = old_val  # после победы над боссом чёрный больше не выставить
                                else:
                                    bind_capture = None
                                    corruption = start_corruption()

                if (event.type == pygame.MOUSEBUTTONDOWN and bind_capture is None and settings_pages(g_save)[settings_page] == "TANK"
                        and g_save.get("custom_tank", {}).get("enabled", False)):
                    mx, my = event.pos
                    mx = int(mx / user_scale)
                    my = int(my / user_scale)
                    
                    ui_offset_x = (WIDTH - (WIDTH - 80)) // 2
                    ui_offset_y = (HEIGHT - (HEIGHT - 160)) // 2

                    preview_x = 80 + CELL_SIZE
                    preview_y = 130 + CELL_SIZE
                    
                    for cx in range(3):
                            for cy in range(3):
                                rect_x = ui_offset_x + preview_x + (cx) * CELL_SIZE
                                rect_y = ui_offset_y + preview_y + (cy) * CELL_SIZE
                                rect = pygame.Rect(rect_x, rect_y, CELL_SIZE, CELL_SIZE)

                                if rect.collidepoint(mx, my):
                                    if event.button == 1:
                                        if [cx, cy] in g_save["custom_tank"]["pixels"]:
                                            g_save["custom_tank"]["pixels"].remove([cx, cy])
                                        else:
                                            g_save["custom_tank"]["pixels"].append([cx, cy])

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
                    elif action == "back_to_mode":
                        current_menu_stats = get_best_mode_stats(menu.selected_mode)
                    elif action == "start_slot":
                        curtain_dir = 1
                        after_curtain = "INIT_GAME"
                    elif action == "reset_slot":
                        save_load.delete_save(menu.selected_mode, menu.selected_slot)
                        current_menu_stats = get_menu_stats(menu.selected_mode, menu.selected_slot)

            elif app_state == "PLAYING" and curtain_dir == 0:
                # Пауза / выход: действие "pause" (две ячейки: клавиатура или кнопка мыши)
                if ctl_down == "pause":
                    esc_held = True

                if ctl_up[0] == "pause" and ctl_up[1]:  # отпущены все бинды паузы
                    if esc_held and esc_hold_timer < LONG_ESC_MS:
                        game_state["paused"] = not game_state["paused"]
                    esc_held = False
                    esc_hold_timer = 0

                if not game_state["paused"]:
                    player = game_state["player"]
                    if ctl_down == "shoot" and game_state["logic_mode"].final_active() and not game_state["logic_mode"].final_booming():
                        final_windows.FINAL.request_fire(game_state["logic_mode"].player_bullet_color(None))
                    if ctl_down and not game_state["logic_mode"].player_locked():
                        if ctl_down in ACTION_DIRS:
                            direction = ACTION_DIRS[ctl_down]
                            if game_state["logic_mode"].restrict_player_keys(direction):
                                # Создаем группу препятствий для игрока (враги + блоки)
                                obstacles = pygame.sprite.Group(game_state["enemies"].sprites() + game_state["blocks"].sprites())
                                player.handle_keydown(direction, obstacles)
                                
                        if ctl_down == "shoot":
                            active_player_bullets = sum(1 for b in game_state["bullets"] if b.is_player)
                            _lm = game_state.get("logic_mode")
                            max_bullets = getattr(_lm, "boss_max_player_bullets", 1) if _lm and _lm.is_boss_phase else 4
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
                                bullet_color = g_save.get("rgb", [0, 0, 0]) if (g_save.get("paint_tank", False) and custom_tank_enabled and not (_lm and _lm.plain_player(g_save))) else None

                                if _lm:
                                    bullet_color = _lm.player_bullet_color(bullet_color)
                                bullet = Bullet(player, player.direction, assets.PIXEL_IMG_RAW, is_player=True, custom_color=bullet_color)
                                bullet.grid_x = bullet_grid_x
                                bullet.grid_y = bullet_grid_y
                                bullet.update_position()
                                
                                game_state["bullets"].add(bullet)
                                game_state["all_sprites"].add(bullet)
                                assets.play_sound(assets.PLAYER_SHOOT_SOUND, game_state["sounds_enabled"])
        
        for item in assets.__dict__.values():
            if isinstance(item, pygame.mixer.Sound):
                item.set_volume(current_volume)

        # Музыка босса
        _lm = game_state.get("logic_mode") if game_state else None
        _want, _low = _lm.music_state() if _lm is not None else (None, False)
        boss_music.MUSIC.update(_want, _low, current_volume, bool(game_state and game_state.get("paused")))
        if _lm is not None and hasattr(_lm, "apply_final_audio"):
            _lm.apply_final_audio(0.0 if is_muted else current_volume, bool(game_state.get("paused")))

        if corruption is not None:
            corruption.update(dt_ms)

        target_vol = 0.0 if is_muted else current_volume
        if target_vol != last_drawn_volume:
            last_drawn_volume = target_vol
            r, g, b = int(129 * (1.0 - target_vol)), int(136 * (1.0 - target_vol)), int(111 * (1.0 - target_vol))
            current_sound_img = assets.colorize_icon(assets.SOUNDS_IMG_BASE, (r, g, b, 255))

        if bind_capture is not None and app_state == "SETTINGS":
            # удержание ESC ~0.8 с во время назначения - назначить саму клавишу ESC
            if bind_capture["esc_t"] is not None and pygame.time.get_ticks() - bind_capture["esc_t"] >= 800:
                bind_message = controls.assign(bind_capture["action"], bind_capture["slot"], "escape") or "OK"
                bind_message_until = pygame.time.get_ticks() + 2500
                controls.save_to(g_save)
                save_load.save_global_save(g_save)
                bind_capture = None
        elif bind_capture is not None:
            bind_capture = None

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
            max_curtain = curtain_cols if TRANSITION_STYLE in ("RIGHT_TO_LEFT", "LEFT_TO_RIGHT") else curtain_rows
            current_trans_speed = TRANSITION_SPEED_MS if TRANSITION_STYLE in ("RIGHT_TO_LEFT", "LEFT_TO_RIGHT") else TRANSITION_SPEED_MS // 2
            
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
                        settings_page, bind_slot, bind_capture = 0, 0, None
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
                        logic_mode = game_state["logic_mode"]
                        logic_mode.configure_level()  # HUD / размер поля / текст уровня нового уровня
                        logic_mode.setup_level(is_new_level=True)
                        game_state["enemy_manager"].clear_enemies()
                        for b in game_state["bullets"]:
                            b.kill()

                        player = game_state["player"]
                        if getattr(logic_mode, "is_random_map", False) and hasattr(logic_mode, "player_spawn_point"):
                            player.grid_x, player.grid_y = logic_mode.player_spawn_point
                        else:
                            player.grid_x, player.grid_y = random.choice(settings.PLAYER_SPAWN_POINTS)

                        if getattr(logic_mode, "is_random_map", False) and hasattr(logic_mode, "enemy_spawn_points"):
                            settings.set_enemy_spawn_points(logic_mode.enemy_spawn_points)
                        player.update_position()
                        logic_mode.after_level_reset()  # режим может поставить то, что должно пережить очистку

                        curtain_dir = -1
                        after_curtain = "START_PLAYING"

                    elif after_curtain == "MENU_FROM_ESC":
                        game_state = None
                        app_state = "MENU"
                        menu.state = menu.prev_state
                        curtain_dir = -1
                        after_curtain = None
                        apply_custom_tank(g_save)
                        current_menu_stats = get_menu_stats(menu.selected_mode, menu.selected_slot)

                    elif after_curtain == "MENU_FROM_WIN":
                        delete_save(game_state["mode"], game_state["slot"])
                        game_state = None
                        app_state = "MENU"
                        menu.state = menu.prev_state
                        curtain_dir = -1
                        after_curtain = None
                        apply_custom_tank(g_save)

                    elif after_curtain == "GO_TO_WIN_PHASE":
                        # любой пройденный режим отмечается сам
                        save_load.mark_mode_completed(game_state["mode"], g_save)
                        if game_state["mode"] == "D01":
                            # D01 пройден: игрок снова может быть окрашен
                            save_load.grant_tank_reward(g_save)  # вкладка TANK + случайный цвет танка
                            save_load.save_global_save(g_save)
                        menu.g_save = save_load.load_global_save()

                        if getattr(game_state.get("logic_mode"), "skip_win_screen", False):
                            # Победный экран отключён параметром режима: занавес закрыт - сразу в меню
                            delete_save(game_state["mode"], game_state["slot"])
                            game_state = None
                            app_state = "MENU"
                            menu.state = menu.prev_state
                            curtain_dir = -1
                            after_curtain = None
                            apply_custom_tank(g_save)
                            current_menu_stats = get_menu_stats(menu.selected_mode, menu.selected_slot)
                        else:
                            app_state = "WIN_SHOW"
                            win_timer = 0
                            curtain_dir = -1
                            after_curtain = "WIN_VISIBLE"

                            game_state["logic_mode"].on_win_screen()  # режим меняет раскладку (D01: классическое поле и HUD)

                            # Очистка поля для чистого победного экрана
                            game_state["all_sprites"].empty()
                            game_state["blocks"].empty()
                            game_state["enemies"].empty()
                            game_state["bullets"].empty()
                        
                    elif after_curtain == "RESPAWN_OR_GAMEOVER":
                        if game_state["lives"] <= 0 and game_state["logic_mode"].try_revive():
                            game_state["lives_positions"] = generate_lives_positions(game_state["lives"])
                        if game_state["lives"] > 0:
                            pygame.event.get(pygame.KEYDOWN)
                            pygame.event.get(pygame.KEYUP)
                            player = game_state["player"]

                            # Сбрасываем внутреннее состояние движения игрока
                            if hasattr(player, "moving_dirs"):
                                player.moving_dirs.clear()
                            if hasattr(player, "is_moving"):
                                player.is_moving = False
                            if hasattr(player, "velocity"):
                                player.velocity = [0, 0]

                            logic_mode = game_state["logic_mode"]

                            if hasattr(logic_mode, "get_respawn_point"):
                                # Случайное безопасное место (режимы со случайной картой)
                                player.grid_x, player.grid_y = logic_mode.get_respawn_point()
                            elif getattr(logic_mode, "is_random_map", False) and hasattr(logic_mode, "player_spawn_point"):
                                player.grid_x, player.grid_y = logic_mode.player_spawn_point
                            else:
                                player.grid_x, player.grid_y = random.choice(settings.PLAYER_SPAWN_POINTS)
                                
                            if getattr(logic_mode, "is_random_map", False) and hasattr(logic_mode, "enemy_spawn_points"):
                                settings.set_enemy_spawn_points(logic_mode.enemy_spawn_points)
                            player.set_direction(NAME_TO_DIRECTION["up"])
                            player.update_position()
                            
                            game_state["enemy_manager"].clear_enemies()
                            for b in game_state["bullets"]:
                                if hasattr(b, "purge"):
                                    b.purge()  # лучи босса переживают обычный kill()
                                else:
                                    b.kill()
                            game_state["all_sprites"].add(player)
                            
                            # Восстановление босса, если игрок умер во время дуэли
                            if game_state.get("logic_mode"):
                                if game_state["logic_mode"].is_boss_phase:
                                    game_state["logic_mode"].start_boss_phase()
                                    # новое место возрождения не должно сразу попасть под остатки атаки
                                    player.invuln_ms = max(getattr(player, "invuln_ms", 0),
                                                           getattr(game_state["logic_mode"], "RESPAWN_INVULN_MS", 0))
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
                            menu.state = menu.prev_state  # Возврат в выбор режима
                            curtain_dir = -1
                            after_curtain = None
                            # Во время шторки танк красится в "бесцветный" вариант - возвращаем цвет
                            apply_custom_tank(g_save)
                            current_menu_stats = get_menu_stats(menu.selected_mode, menu.selected_slot)
                            
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
                    _lm_x = game_state["logic_mode"]
                    if _lm_x.instant_respawn():
                        # Босс-файт, жизни ещё есть: возвращаем игрока на поле сразу, без шторки
                        pygame.event.get(pygame.KEYDOWN)
                        pygame.event.get(pygame.KEYUP)
                        player = game_state["player"]
                        if hasattr(player, "moving_dirs"):
                            player.moving_dirs.clear()
                        if hasattr(player, "is_moving"):
                            player.is_moving = False
                        if hasattr(player, "velocity"):
                            player.velocity = [0, 0]
                        player.set_direction(NAME_TO_DIRECTION["up"])
                        for b in game_state["bullets"]:
                            if b.is_player:  # пули босса летят дальше: бой не сбрасывается
                                b.kill()
                        game_state["all_sprites"].add(player)
                        _lm_x.respawn_player()  # мигающий неуязвимый игрок в новом месте
                        app_state = "PLAYING"
                    else:
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

            current_board = get_board_model_for_state(game_state)
            player.board = current_board

            max_enemies, speed_multiplier, spawn_delay = get_difficulty_params(game_state)
            player_obstacles = pygame.sprite.Group(enemies.sprites() + game_state["blocks"].sprites())

            player_stuck = False
            for sprite in player_obstacles:
                if hitbox_collide(player, sprite):
                    player_stuck = True
                    break
            
            if player_stuck:
                tanks_list = [player] + list(enemies)
                _pb = get_board_model_for_state(game_state)
                nx, ny = find_nearest_empty_cell(player, max((len(r) for r in _pb), default=settings.BOARD_WIDTH),
                                                 len(_pb) or settings.BOARD_HEIGHT, game_state["blocks"], tanks_list)
                player.grid_x, player.grid_y = nx, ny
                player.update_position()

            # Страховка: если отпускание всё же пропало
            if player.key_held and player.current_move_dir in DIR_ACTIONS:
                if not controls.sync_action(DIR_ACTIONS[player.current_move_dir]):
                    player.handle_keyup(player.current_move_dir)

            if game_state["logic_mode"].player_locked():
                if player.key_held:
                    player.handle_keyup(player.current_move_dir)  # катсцена: игрок стоит
            else:
                player.update_movement(dt_ms, collision_group=player_obstacles)
            if getattr(player, "invuln_ms", 0) > 0:
                player.invuln_ms = max(0, player.invuln_ms - dt_ms)
            
            all_ai_obstacles = pygame.sprite.Group(enemies.sprites() + [player] + game_state["blocks"].sprites())
            for enemy in enemies:
                enemy.board = current_board 
                enemy.update_ai(dt_ms, player, all_ai_obstacles, bullets, all_sprites,
                                speed_multiplier, game_state["blocks"])

            current_board = get_board_model_for_state(game_state)
            bullets.update(dt_ms, board=current_board)

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

                if bullet.is_player and game_state["logic_mode"].on_player_bullet(bullet):
                    bullet.kill()  # попал в особый объект режима (цветной блок)
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
                            if getattr(e, "is_boss", False):
                                if getattr(e, "invulnerable", False):
                                    continue  # интро босса: выстрел просто гаснет
                                if e.hurt_hitbox.colliderect(bullet.rect):
                                    e.hp -= 1

                                    save_game(game_state["mode"], game_state["slot"], game_state["player"], game_state["enemy_manager"], game_state)
                                    
                                    if e.hp <= 0 and game_state["logic_mode"].boss_lethal_hook(e, not g_save.get("fullscreen", False)):
                                        e.hp = max(1, e.hp)  # финал D01: босс не умирает, последний выстрел - окном игрока
                                    elif e.hp <= 0:
                                        e.kill()
                                        assets.play_sound(assets.BOSS_EXPLOSION_SOUND, game_state["sounds_enabled"])
                            else:
                                e.kill()
                                assets.play_sound(assets.ENEMY_EXPLOSION_SOUND, game_state["sounds_enabled"])
                                game_state["kills_this_level"] += 1
                                game_state["global_kills"] += 1
                                game_state["score"] += 100
                                if game_state["score"] > game_state["hi_score"]:
                                    game_state["hi_score"] = game_state["score"]
                                    save_hi_score(game_state["mode"], game_state["hi_score"])
                else:
                    if getattr(player, "invuln_ms", 0) > 0:
                        continue  # возрождение: пули пролетают сквозь мигающего игрока
                    if hitbox_collide(bullet, player):
                        bullet.kill()
                        all_sprites.remove(player)
                        assets.play_sound(assets.EXPLOSION_SOUND, game_state["sounds_enabled"])
                        game_state["lives"] -= 1
                        game_state["lives_positions"] = generate_lives_positions(game_state["lives"])

                        app_state = "EXPLODING"
                        explosion_frame, explosion_timer = 0, 0
                        # Взрыв в цвет игрока (как закрашенный танк) и без наложения на настоящие
                        _painted = g_save.get("custom_tank", {}).get("enabled", False) and g_save.get("paint_tank", False)
                        if game_state["logic_mode"].plain_player(g_save):
                            _painted = False  # D01 (пока не пройден): взрыв без краски
                        explosion_imgs = assets.build_explosion_imgs(tuple(g_save.get("rgb", [129, 136, 111])) if _painted else None)
                        _eb = get_board_model_for_state(game_state)
                        _size = explosion_imgs[0].get_width() // CELL_SIZE if explosion_imgs else 4
                        explosion_rect = pygame.Rect(0, 0, _size * CELL_SIZE, _size * CELL_SIZE)
                        if _eb:
                            _tx, _ty = find_explosion_spot(_eb, player.grid_x, player.grid_y, _size)
                        else:
                            _tx, _ty = player.grid_x - _size // 2, player.grid_y - _size // 2
                        explosion_rect.topleft = (OFFSET_X + _tx * CELL_SIZE, OFFSET_Y + _ty * CELL_SIZE)
                        break

            if app_state == "PLAYING" and not game_state["logic_mode"].is_boss_phase:
                remaining_kills = game_state["target_enemies"] - game_state["kills_this_level"]
                actual_max = min(max_enemies, max(0, remaining_kills))
                enemy_manager.spawn_enemy_if_needed(dt_ms, actual_max, spawn_delay)

            if app_state == "PLAYING" and game_state.get("logic_mode"):
                game_state["logic_mode"].update_effects(dt_ms)
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

        current_game_state = game_state if 'game_state' in locals() else None
        layout = get_layout_for_state(current_game_state)
        target_w, target_h = get_logical_size(current_game_state)
        current_board = get_board_model_for_state(current_game_state)
        area = layout.map_area

        # КАМЕРА (считаем ДО отрисовки, рисуем только видимую часть)
        camera_x, camera_y = 0, 0

        if app_state in ("PLAYING", "FROZEN_GAME", "EXPLODING") and game_state:
            player = game_state["player"]
            # Камера следует за игроком внутри области карты (HUD в неё не входит)
            camera_x = max(0, min(player.rect.centerx - (area.w // 2), target_w - area.w))
            camera_y = max(0, min(player.rect.centery - (area.h // 2), target_h - area.h))

            # Отключаем скролл, если карта меньше области
            if target_w <= area.w: camera_x = 0
            if target_h <= area.h: camera_y = 0

            _co = game_state["logic_mode"].camera_origin() if hasattr(game_state.get("logic_mode"), "camera_origin") else None
            if _co is not None:  # D01-финал: окно показывает только поле босса
                camera_x, camera_y = _co

        view_w = min(area.w, target_w)
        view_h = min(area.h, target_h)

        # Поверхность размером ТОЛЬКО с видимую область
        if virtual_screen.get_size() != (view_w, view_h):
            virtual_screen = pygame.Surface((view_w, view_h))

        virtual_screen.fill(settings.BACKGROUND_COLOR)

        # Клетки поля - только те, что попадают в кадр
        models.draw_smart_board(
            virtual_screen, current_board,
            settings.OFFSET_X - camera_x, settings.OFFSET_Y - camera_y, assets.PIXEL_IMG_RAW
        )

        # Игровые объекты - со сдвигом на камеру и отсечением по видимой области
        if app_state in ("PLAYING", "FROZEN_GAME", "EXPLODING", "WIN_SHOW") and game_state:
            is_curtain_active = (curtain > 0)

            if g_save.get("custom_tank", {}).get("enabled", False):
                _plain = bool(game_state.get("logic_mode") and game_state["logic_mode"].plain_player(g_save))
                apply_custom_tank(g_save, force_colorless=is_curtain_active or _plain)
                player = game_state["player"]
                player.base_image = assets.PLAYER_BASE_IMG
                player.update_image()

            _lm_img = game_state.get("logic_mode")
            _timg = _lm_img.player_image(g_save) if (_lm_img is not None and not is_curtain_active) else None
            if _timg is not None:  # режим рисует закрашенный танк (D01: цветные клетки)
                game_state["player"].base_image = _timg
                game_state["player"].update_image()

            _pl = game_state["player"]
            if getattr(_pl, "invuln_ms", 0) > 0:  # мигание после возрождения
                _pl.image.set_alpha(70 if (int(_pl.invuln_ms) // 110) % 2 else 255)
            else:
                _pl.image.set_alpha(255)

            for bullet in game_state["bullets"]:
                if bullet.is_player and hasattr(bullet, "update_curtain_shading"):
                    bullet.update_curtain_shading(is_curtain_active)

            draw_group_culled(virtual_screen, game_state["all_sprites"], camera_x, camera_y)
            draw_group_culled(virtual_screen, game_state["blocks"], camera_x, camera_y)

            if app_state == "EXPLODING" and explosion_rect is not None:
                img_idx = 0 if explosion_frame % 2 == 0 else 1
                _frames = explosion_imgs or assets.EXPLOSION_IMGS
                if len(_frames) > img_idx:
                    virtual_screen.blit(_frames[img_idx], explosion_rect.move(-camera_x, -camera_y))

            _gmx = game_state.get("logic_mode")
            if _gmx is not None and hasattr(_gmx, "draw_final_boom"):
                _gmx.draw_final_boom(virtual_screen, camera_x, camera_y)  # D01: чёрный взрыв босса в финале

            if app_state == "WIN_SHOW" and assets.WIN_IMG:
                win_rect = assets.WIN_IMG.get_rect(topleft=get_cell_topleft(2, 0))
                virtual_screen.blit(assets.WIN_IMG, win_rect.move(-camera_x, -camera_y))
                game_state["logic_mode"].draw_win_overlay(virtual_screen, win_rect.move(-camera_x, -camera_y), win_timer)

        # Эффекты режима поверх кадра поля (D01: завесы и глитч)
        if game_state and app_state in ("PLAYING", "FROZEN_GAME", "EXPLODING") and game_state.get("logic_mode"):
            game_state["logic_mode"].draw_overlay(virtual_screen, camera_x, camera_y, game_state["paused"])

        # Готовый кадр карты -> окно (по центру своей области, если карта меньше неё)
        ui_surface.fill(settings.BACKGROUND_COLOR)

        offset_x = area.x + (area.w - view_w) // 2
        offset_y = area.y + (area.h - view_h) // 2
        # Карта показывается ровно в границах поля из меню (клетки + их обводка): всё
        ui_surface.set_clip(layout.field_rect)
        _zoom = 1.0
        _bm = game_state.get("logic_mode") if game_state else None
        if _bm is not None and app_state in ("PLAYING", "FROZEN_GAME", "EXPLODING"):
            _zoom = _bm.beat_zoom()  # пульс в такт музыке (режим D01, босс-файт)
        if _zoom > 1.002:
            _zw, _zh = int(view_w * _zoom), int(view_h * _zoom)
            ui_surface.blit(pygame.transform.scale(virtual_screen, (_zw, _zh)),
                            (offset_x - (_zw - view_w) // 2, offset_y - (_zh - view_h) // 2))
        else:
            ui_surface.blit(virtual_screen, (offset_x, offset_y))
        ui_surface.set_clip(None)

        # Окно ОС босса за краем поля
        _bwin, _bbul = None, []
        if _bm is not None and app_state in ("PLAYING", "FROZEN_GAME", "EXPLODING"):
            _bwin = _bm.boss_window_info()
            _bbul = _bm.boss_window_bullets()
        if _bm is None or app_state not in ("PLAYING", "FROZEN_GAME", "EXPLODING"):
            if boss_window.WINDOW.has_windows():
                boss_window.WINDOW.close()  # вышли из игры - окна босса не нужны
        elif _bwin is not None or _bbul or boss_window.WINDOW.has_windows():
            boss_window.WINDOW.frame(
                _bwin, _bbul, actual_w / base_w,
                lambda cx, cy: (offset_x + settings.OFFSET_X + cx * settings.CELL_SIZE - camera_x,
                                offset_y + settings.OFFSET_Y + cy * settings.CELL_SIZE - camera_y),
                (monitor_w, monitor_h), g_save.get("fullscreen", False))

        # Финал D01: игрок и его пули - окна ОС, босс заперт в поле 3x3
        if _bm is not None and _bm.final_active() and not _bm.final_booming() and app_state in ("PLAYING", "FROZEN_GAME", "EXPLODING"):
            _held = [ACTION_DIRS[a] for a in ACTION_DIRS if controls.sync_action(a)]
            _pimg = _bm.player_image(g_save) or assets.DEFAULT_PLAYER_BASE_IMG or assets.PLAYER_BASE_IMG
            if final_windows.FINAL.frame(
                    _held, _bm.final_field_cells(), actual_w / base_w,
                    lambda cx, cy: (offset_x + settings.OFFSET_X + cx * settings.CELL_SIZE - camera_x,
                                    offset_y + settings.OFFSET_Y + cy * settings.CELL_SIZE - camera_y),
                    (monitor_w, monitor_h), g_save.get("fullscreen", False), _pimg,
                    paused=bool(game_state.get("paused"))):
                _bm.final_bullet_hit()
        elif final_windows.FINAL.has_windows():
            final_windows.FINAL.close()

        # Реально отрисованное поле: клетки карты на экране
        _bcols = max((len(r) for r in current_board), default=0)
        _board_px = pygame.Rect(offset_x + settings.OFFSET_X - camera_x, offset_y + settings.OFFSET_Y - camera_y,
                                _bcols * CELL_SIZE, len(current_board) * CELL_SIZE)
        if _bm is not None and _bm.final_active():  # поле резко сжалось до 3x3: рамка тоже
            _fx, _fy, _fw, _fh = _bm.final_field_cells()
            _board_px = pygame.Rect(_board_px.x + _fx * CELL_SIZE, _board_px.y + _fy * CELL_SIZE, _fw * CELL_SIZE, _fh * CELL_SIZE)
        _drawn = hud.drawn_field_rect(layout, _board_px)

        if game_state and app_state in ("PLAYING", "FROZEN_GAME", "EXPLODING", "WIN_SHOW"):
            hud.draw_field_frame(ui_surface, _drawn)

        # Шторка: клеточная сетка поверх видимых клеток поля (внутри обводки)
        curtain_rc = _drawn.inflate(-2 * hud.FIELD_PAD, -2 * hud.FIELD_PAD)
        if curtain_rc.w <= 0 or curtain_rc.h <= 0:
            curtain_rc = layout.field_rect.inflate(-2 * hud.FIELD_PAD, -2 * hud.FIELD_PAD)

        # Какие клетки карты видны в кадре
        curtain_cells = visible_curtain_cells(current_board, _board_px, curtain_rc)
        _act_cols, _act_rows = curtain_cells["cols"], curtain_cells["rows"]
        curtain_cols = max(1, len(_act_cols))
        curtain_rows = max(1, len(_act_rows))

        # "Сломанная" шкала жизней (режим просит через hp_broken()): значение
        _hp_fx = None
        _hp_classic_cells = None
        _gm = game_state.get("logic_mode") if game_state else None
        if _gm is not None and app_state in ("PLAYING", "FROZEN_GAME", "EXPLODING") and _gm.hp_broken():
            _hp_fx = pygame.time.get_ticks()

        if layout.kind == "classic":
            _hud_model = models.HUD_MODEL
            if _hp_fx is not None:
                if hud.normalize(layout.board_mode, layout.hud_mode, layout.hp_model,
                                 getattr(_gm, "hp_fill", "gauge"))[3] == "gauge":
                    _lit = hud.gauge_cells(game_state, models.HUD_MODEL, "gauge")
                else:
                    _lit = game_state["lives_positions"]
                _hud_model, _hp_classic_cells = hp_break.break_bar(models.HUD_MODEL, _lit, _hp_fx)
            models.draw_smart_board(
                ui_surface, _hud_model,
                layout.hud_x, settings.HUD_BOARD_Y, assets.PIXEL_IMG_RAW
            )

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
            
            # Пока шторка идёт
            _menu_colorless = (curtain > 0) or (curtain_dir != 0)
            menu.colorless = _menu_colorless
            if g_save.get("custom_tank", {}).get("enabled", False):
                apply_custom_tank(g_save, force_colorless=_menu_colorless)
            menu.draw()
            current_goal = None
            if current_menu_stats.get("is_boss_phase"):
                current_goal = ("HP BOSS", f"{current_menu_stats.get('boss_hp', 0)}/{current_menu_stats.get('boss_max_hp', 0)}")
            elif menu.selected_mode == 5:
                current_goal = ("G O A L", str(current_menu_stats.get("global_kills", 0)))
                
            is_settings_mode = (menu.state == "SETTINGS")
            render_hud(ui_surface, font, current_menu_stats, current_sound_img, False, pause_rect, sound_rect, custom_goal=current_goal, is_settings=is_settings_mode, hud_start_x=current_hud_x)

            if menu.state == "SLOT" and curtain_dir == 0:
                box_width = 460
                box_height = 420
                ui_surf_box = pygame.Surface((box_width, box_height), pygame.SRCALPHA)
                pygame.draw.rect(ui_surf_box, (0, 0, 0, 220), ui_surf_box.get_rect(), border_radius=15)
                
                slot_str = f"< SLOT {menu.selected_slot:02d} >"
                slot_surf = font.render(slot_str, True, (255, 255, 0))
                ui_surf_box.blit(slot_surf, slot_surf.get_rect(center=(box_width//2, 30)))
                
                y_offset = 80
                line_spacing = 45
                
                def draw_stat(label, value, y):
                    lbl_s = font.render(label, True, (255, 255, 255))
                    val_s = font.render(str(value), True, (255, 255, 0))
                    ui_surf_box.blit(lbl_s, (40, y))
                    val_r = val_s.get_rect(topright=(box_width - 40, y))
                    ui_surf_box.blit(val_s, val_r)

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
                ui_surf_box.blit(hint_surf, hint_rect)

                ui_surface.blit(ui_surf_box, ((base_w - box_width) // 2, (base_h - box_height) // 2))

        elif app_state in ("PLAYING", "FROZEN_GAME", "EXPLODING", "WIN_SHOW"):
            if game_state:
                max_enemies, speed_multiplier, spawn_delay = get_difficulty_params(game_state)
                target_enemies = game_state["target_enemies"]
                
                if game_state.get("logic_mode"):
                    target_enemies = game_state["logic_mode"].target_kills
                    is_boss = game_state["logic_mode"].is_boss_phase
                    current_level = "BOSS" if is_boss else game_state["logic_mode"].get_level_text()
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
                if game_state.get("logic_mode"):
                    stats["hide_panels"] = game_state["logic_mode"].hidden_hud_panels()
                current_goal = game_state["logic_mode"].get_custom_hud_goal() if game_state.get("logic_mode") else None

                # Шкала HP: клетки жизней
                _mode = game_state.get("logic_mode")
                _fill = hud.normalize(layout.board_mode, layout.hud_mode, layout.hp_model,
                                      getattr(_mode, "hp_fill", "gauge"))[3]
                if layout.kind in ("windows", "os"):
                    stats["hp_cells"] = hud.gauge_cells(game_state, layout.hp_model, _fill)
                elif layout.kind == "classic" and _fill == "gauge":
                    stats["lives_positions"] = hud.gauge_cells(game_state, models.HUD_MODEL, "gauge")

                if _hp_fx is not None:
                    if layout.kind in ("windows", "os"):
                        stats["hp_model"], stats["hp_cells"] = hp_break.break_bar(layout.hp_model, stats["hp_cells"], _hp_fx)
                    elif layout.kind == "classic" and _hp_classic_cells is not None:
                        stats["lives_positions"] = _hp_classic_cells

                if layout.kind == "classic":
                    render_hud(ui_surface, font, stats, current_sound_img, game_state["paused"], pause_rect, sound_rect, custom_goal=current_goal, hud_start_x=current_hud_x)
                elif layout.kind == "windows":
                    hud.render_windows(
                        ui_surface, font, layout, stats,
                        current_sound_img or assets.SOUNDS_IMG_BLACK, game_state["paused"], current_goal,
                        assets.PIXEL_IMG_RAW, assets.PAUSE_IMG_BLACK, assets.PAUSE_IMG_INACTIVE
                    )
                elif layout.kind == "os":
                    # HUD в самостоятельных окнах ОС
                    if os_hud_mgr.sync(layout, actual_w / base_w, (monitor_w, monitor_h), g_save.get("fullscreen", False),
                                       getattr(_mode, "os_window_icons", None)):
                        os_hud_mgr.update(
                            font, stats, current_goal, game_state["paused"],
                            current_sound_img or assets.SOUNDS_IMG_BLACK, assets.PIXEL_IMG_RAW,
                            assets.PAUSE_IMG_BLACK, assets.PAUSE_IMG_INACTIVE
                        )
        
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
            ui_surface.blit(ui_surf, (15, 15))

        if curtain > 0:
            t_img = assets._PIXEL_IMG_RAW

            ui_surface.set_clip(curtain_rc)
            cc = curtain_cells
            ox0, oy0 = cc["origin"]
            has = cc.get("has")
            cols_l, rows_l = cc["cols"], cc["rows"]
            if has:
                if TRANSITION_STYLE in ("RIGHT_TO_LEFT", "LEFT_TO_RIGHT"):
                    for step in range(min(curtain, len(cols_l))):
                        col = cols_l[len(cols_l) - 1 - step] if TRANSITION_STYLE == "RIGHT_TO_LEFT" else cols_l[step]
                        for row in range(cc["r0"], cc["r1"]):
                            if has(row, col):
                                ui_surface.blit(t_img, (ox0 + col * CELL_SIZE, oy0 + row * CELL_SIZE))
                else:
                    for step in range(min(curtain, len(rows_l))):
                        row = rows_l[len(rows_l) - 1 - step] if TRANSITION_STYLE == "BOTTOM_TO_TOP" else rows_l[step]
                        for col in range(cc["c0"], cc["c1"]):
                            if has(row, col):
                                ui_surface.blit(t_img, (ox0 + col * CELL_SIZE, oy0 + row * CELL_SIZE))
            ui_surface.set_clip(None)
        
        if app_state == "SETTINGS":
            render_hud(ui_surface, font, None, current_sound_img, False, pause_rect, sound_rect, is_settings=True, hud_start_x=current_hud_x)
            
            box_width = min(WIDTH - 80, base_w - 20)
            box_height = min(HEIGHT - 160, base_h - 20)
            ui_surf = pygame.Surface((box_width, box_height), pygame.SRCALPHA)
            pygame.draw.rect(ui_surf, (0, 0, 0, 200), ui_surf.get_rect(), border_radius=15)
            
            YELLOW, WHITE, GREY = (255, 255, 0), (255, 255, 255), (170, 170, 170)

            def draw_settings_text(text_str, y_pos, is_selected, x_pos=40, color=None) -> None:
                color = color or (YELLOW if is_selected else WHITE)
                tsurf = font.render(text_str, True, color)
                ui_surf.blit(tsurf, (x_pos, y_pos))

            page_name = settings_pages(g_save)[settings_page]
            layout_ids = build_settings_layout(g_save, settings_page)
            settings_index = max(0, min(settings_index, len(layout_ids) - 1))
            active_id = layout_ids[settings_index]
            now_ms = pygame.time.get_ticks()

            def draw_center_text(text_str, center_y, color) -> None:
                tsurf = font.render(text_str, True, color)
                ui_surf.blit(tsurf, tsurf.get_rect(center=(box_width // 2, center_y)))

            # Заголовок по центру (как переключатель слота в меню)
            tab_row_active = (active_id == "PAGE")
            header = font.render(f"< {page_name} >", True, YELLOW if tab_row_active else WHITE)
            ui_surf.blit(header, header.get_rect(center=(box_width // 2, 30)))

            current_y = 80

            if page_name == "DISPLAY":
                draw_settings_text(f"SCALE: < {user_scale:.1f}x >", current_y, active_id == "SCALE")
                current_y += 40
                draw_settings_text(f"FONT: < {g_save.get('font', 'DS-DIGI')} >", current_y, active_id == "FONT")
                current_y += 40
                draw_settings_text(f"CURTAIN: < {g_save.get('curtain_style', 'RIGHT_TO_LEFT')} >", current_y, active_id == "CURTAIN")
                current_y += 40

            elif page_name == "TANK":
                draw_settings_text(f"CUSTOM TANK: {'[X]' if g_save.get('custom_tank', {}).get('enabled') else '[ ]'}", current_y, active_id == "CUSTOM_TANK")
                current_y += 40

                if g_save.get("custom_tank", {}).get("enabled", False):
                    preview_x = 80
                    preview_y = current_y + 10
                
                    pad = 3
                    t = 4
                    border_color = (70, 77, 51)
                    background_color = (137, 145, 113)
                    inactive_color = (129, 136, 111)

                    outer_rect_5x5 = pygame.Rect(preview_x - pad - t, preview_y - pad - t, 5 * CELL_SIZE + 2 * (pad + t), 5 * CELL_SIZE + 2 * (pad + t))
                    pygame.draw.rect(ui_surf, border_color, outer_rect_5x5)

                    inner_rect_5x5 = pygame.Rect(preview_x - pad, preview_y - pad, 5 * CELL_SIZE + 2 * pad, 5 * CELL_SIZE + 2 * pad)
                    pygame.draw.rect(ui_surf, background_color, inner_rect_5x5)

                    outer_rect_3x3 = pygame.Rect(preview_x + CELL_SIZE - pad - t, preview_y + CELL_SIZE - pad - t, 3 * CELL_SIZE + 2 * (pad + t), 3 * CELL_SIZE + 2 * (pad + t))
                    pygame.draw.rect(ui_surf, border_color, outer_rect_3x3, t) 

                    empty_surf = pygame.Surface((CELL_SIZE, CELL_SIZE), pygame.SRCALPHA)                    
                    if assets.PIXEL_IMG_RAW:
                        base_col = assets.colorize_icon(assets.PIXEL_IMG_RAW, (*inactive_color, 255))
                        empty_surf.blit(base_col, (0, 0))
                    else:
                        empty_surf.fill(inactive_color)

                    for cx in range(3):
                        for cy in range(3):
                            x = preview_x + (cx + 1) * CELL_SIZE
                            y = preview_y + (cy + 1) * CELL_SIZE
                        
                            if corruption is not None:
                                ui_surf.blit(empty_surf, (x, y))  # на месте превью - "живой" танк (ниже)
                            elif [cx, cy] in g_save["custom_tank"].get("pixels", []):
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
                            else:
                                ui_surf.blit(empty_surf, (x, y))

                    if corruption is not None:
                        corruption.draw_tank(ui_surf, (preview_x + CELL_SIZE, preview_y + CELL_SIZE))

                    current_y += 5 * CELL_SIZE + 20
            
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

            else:  # CONTROLS
                col_slot = (330, 520)
                for action in CONTROL_ACTIONS:
                    row_active = (active_id == f"BIND:{action}")
                    draw_settings_text(f"{ACTION_LABELS[action]}:", current_y, row_active)
                    tokens = controls.tokens(action)
                    sel_slot = min(bind_slot, len(tokens) - 1)
                    for slot_i, token in enumerate(tokens):
                        capturing = bind_capture is not None and bind_capture["action"] == action and bind_capture["slot"] == slot_i
                        if capturing:
                            txt = "PRESS..." if (now_ms // 300) % 2 == 0 else "        "
                            draw_settings_text(f"<{txt}>", current_y, True, col_slot[slot_i], (255, 120, 80))
                        elif row_active and slot_i == sel_slot:
                            draw_settings_text(f"<{bind_label(token)}>", current_y, True, col_slot[slot_i])
                        else:
                            draw_settings_text(f" {bind_label(token)} ", current_y, False, col_slot[slot_i], WHITE if row_active else GREY)
                    current_y += 40

            # Нижний текст - как в слотах меню
            if bind_message and now_ms < bind_message_until:
                draw_center_text(bind_message, box_height - 110, (140, 220, 140))
            if bind_capture is not None:
                draw_center_text("PRESS A KEY OR MOUSE BUTTON", box_height - 70, (255, 120, 80))
                draw_center_text("ESC: CANCEL   HOLD ESC: BIND ESC", box_height - 30, (150, 150, 150))
            else:
                if page_name == "CONTROLS":
                    draw_center_text("ENTER: REBIND   DEL: CLEAR", box_height - 70, (150, 150, 150))
                draw_center_text("PRESS [R] TO RESET", box_height - 30, (150, 150, 150))

            ui_surface.blit(ui_surf, ((base_w - box_width) // 2, (base_h - box_height) // 2))

        if corruption is not None:
            corruption.draw_overlay(ui_surface)

        if os_hud_mgr.items and not (layout.kind == "os" and app_state in ("PLAYING", "FROZEN_GAME", "EXPLODING", "WIN_SHOW")):
            os_hud_mgr.close_all()

        if game_state and app_state in ("PLAYING", "FROZEN_GAME", "EXPLODING") and game_state.get("logic_mode"):
            # эффекты режима на всём окне (не только на поле), клетки - по сетке поля
            game_state["logic_mode"].draw_window_overlay(
                ui_surface, (offset_x + settings.OFFSET_X - camera_x, offset_y + settings.OFFSET_Y - camera_y),
                layout.field_rect, game_state["paused"])

        scaled_game = pygame.transform.scale(ui_surface, (actual_w, actual_h))
        real_screen.blit(scaled_game, (0, 0))
        
        draw_procedural_outer_frame(real_screen, actual_w, actual_h, border_size = 4)

        pygame.display.flip()

        if corruption is not None and corruption.finished:
            # Экран залит, аудио закончилось: запоминаем событие
            g_save["tank_corrupted"] = True
            g_save["corrupted_menu_seen"] = False
            g_save["rgb"] = [0, 0, 0]
            controls.save_to(g_save)
            save_load.save_global_save(g_save)
            corruption_event.show_system_message()
            running = False

    os_hud_mgr.close_all()
    boss_window.WINDOW.close()
    final_windows.FINAL.close()
    discord_activity.close()
    pygame.quit()

if __name__ == "__main__":
    main()
