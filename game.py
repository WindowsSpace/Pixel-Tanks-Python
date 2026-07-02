import pygame
import random

from settings import WIDTH, HEIGHT, \
    BACKGROUND_COLOR, PLAYER_SPAWN_POINTS, \
    HUD_START_X, HUD_BOARD_Y, \
    CELL_SIZE, OFFSET_X, OFFSET_Y, \
    BOARD_WIDTH, BOARD_HEIGHT, \
    PLAYER_MOVE_KEYS, PLAYER_SHOOT_KEYS
import assets 
from tank import PlayerTank, EnemyTank
from bullet import Bullet
from enemy_manager import EnemyManager
from menu import MainMenu
from save_load import save_game, load_game, NAME_TO_DIRECTION, load_hi_score, save_hi_score, delete_save

LONG_ESC_MS = 800

def generate_lives_positions(lives_count) -> list[tuple[int, int]]:
    positions = [(x, y) for x in range(4) for y in range(4)]
    return random.sample(positions, min(lives_count, 16))

def get_difficulty_params(game_state) -> tuple[int, int, int]:
    level = game_state["level"]
    global_kills = game_state["global_kills"]
    max_enemies = min(4, 1 + (level // 2))
    speed_multiplier = min(3, 1.0 + (global_kills // 10) * 0.1)
    spawn_delay = max(500, 2000 - (level * 200))
    return max_enemies, speed_multiplier, spawn_delay

def create_new_game(slot, previous_data=None):
    all_sprites = pygame.sprite.Group()
    bullets = pygame.sprite.Group()
    enemies = pygame.sprite.Group()
    px, py = random.choice(PLAYER_SPAWN_POINTS)
    player = PlayerTank(px, py, assets.PLAYER_BASE_IMG)
    all_sprites.add(player)
    enemy_manager = EnemyManager(assets.ENEMY_BASE_IMG, enemies, all_sprites, player)

    state = {
        "slot": slot,
        "player": player,
        "enemy_manager": enemy_manager,
        "all_sprites": all_sprites,
        "bullets": bullets,
        "enemies": enemies,
        "paused": False,
        "sounds_enabled": True,
        "lives": 4,
        "score": 0,
        "level": 1,
        "target_enemies": 10,
        "kills_this_level": 0,
        "global_kills": 0,
        "hi_score": load_hi_score(),
        "lives_positions": generate_lives_positions(4)
    }

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

def load_game_into_slot(slot):
    data = load_game(slot)
    state = create_new_game(slot, data)
    if data is None: return state

    player = state["player"]
    enemies = state["enemies"]
    all_sprites = state["all_sprites"]

    player.grid_x = data["player"]["grid_x"]
    player.grid_y = data["player"]["grid_y"]
    player.set_direction(NAME_TO_DIRECTION.get(data["player"].get("direction", "up"), NAME_TO_DIRECTION["up"]))
    player.update_position()

    for e_data in data.get("enemies", []):
        enemy = EnemyTank(e_data["grid_x"], e_data["grid_y"], assets.ENEMY_BASE_IMG)
        enemy.set_direction(NAME_TO_DIRECTION.get(e_data.get("direction", "up"), NAME_TO_DIRECTION["up"]))
        enemy.update_position()
        enemies.add(enemy)
        all_sprites.add(enemy)
    return state

def get_menu_stats(slot):
    data = load_game(slot)
    hi_score = load_hi_score()
    if data:
        s = data.get("stats", {})
        speed_multiplier = min(3, 1.0 + (s.get("global_kills", 0) // 10) * 0.1)
        lives = s.get("lives", 4)
        return {
            "score": s.get("score", 0), 
            "hi_score": hi_score,
            "kills_this_level": s.get("kills_this_level", 0), 
            "target_enemies": s.get("target", 10),
            "level": s.get("level", 1), 
            "speed_multiplier": speed_multiplier,
            "lives": lives,
            "lives_positions": generate_lives_positions(lives)
        }
    return {
        "score": 0, 
        "hi_score": hi_score, 
        "kills_this_level": 0,
        "target_enemies": 10, 
        "level": 1, 
        "speed_multiplier": 1.0,
        "lives": 4,
        "lives_positions": generate_lives_positions(4)
    }

def hitbox_collide(sprite1, sprite2):
    return pygame.sprite.collide_mask(sprite1, sprite2) is not None

def render_text(screen, font, text, y_offset) -> None:
    surf = font.render(text, True, (0, 0, 0))
    rect = surf.get_rect(center=(HUD_START_X + (4 * CELL_SIZE) // 2, y_offset))
    screen.blit(surf, rect)

def render_hud(screen, font, stats, sound_img, paused, pause_rect, sound_rect) -> None:
    y_base = 40
    render_text(screen, font, "SCORE", y_base)
    render_text(screen, font, str(stats["score"]), y_base + 35)
    render_text(screen, font, "HI-SCORE", y_base + 80)
    render_text(screen, font, str(stats["hi_score"]), y_base + 115)
    render_text(screen, font, "G O A L", y_base + 160)
    render_text(screen, font, f'{stats["kills_this_level"]}/{stats["target_enemies"]}', y_base + 195)

    for lx, ly in stats["lives_positions"]:
        screen.blit(assets.BULLET_IMG_RAW, (HUD_START_X + lx * CELL_SIZE, HUD_BOARD_Y + ly * CELL_SIZE))

    y_stats = HUD_BOARD_Y + (4 * CELL_SIZE) + 30
    render_text(screen, font, f'LEVEL {stats["level"]}', y_stats)
    render_text(screen, font, f'SPEED x{stats["speed_multiplier"]:.1f}', y_stats + 40)

    screen.blit(assets.PAUSE_IMG_BLACK if paused else assets.PAUSE_IMG_INACTIVE, pause_rect)
    screen.blit(sound_img, sound_rect)

def main() -> None:
    global dt_ms

    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_icon(pygame.image.load("assets/sprites/tank-icon.png"))
    pygame.display.set_caption("Pixel Tanks")
    pygame.mouse.set_visible(False)
    assets.convert_assets()

    clock = pygame.time.Clock()
    dt_ms = 0
    font = assets.CUSTOM_FONT
    menu = MainMenu(screen, font)

    pause_rect = assets.PAUSE_IMG_BLACK.get_rect()
    sound_rect = assets.SOUNDS_IMG_BLACK.get_rect()
    
    # Система состояний
    app_state = "MENU" # Возможные состояния: MENU, PLAYING, FROZEN_GAME, EXPLODING
    game_state = None
    sounds_enabled = True
    esc_down_time = None

    # Переменные Transition ("Занавес")
    curtain = 0       # от 0 до 10 (0 - полностью открыто, 10 - полностью закрыто)
    curtain_dir = 0   # 1 (закрывается), -1 (открывается), 0 (бездействует)
    after_curtain = None 
    transition_timer = 0
    TRANSITION_SPEED_MS = 50

    # Переменные Explosion (Взрыв)
    explosion_frame = 0 
    explosion_timer = 0
    EXPLOSION_SPEED_MS = 150
    explosion_rect = None

    board_rect = pygame.Rect(OFFSET_X, OFFSET_Y, BOARD_WIDTH * CELL_SIZE, BOARD_HEIGHT * CELL_SIZE)
    # board_center_x = OFFSET_X + (BOARD_WIDTH * CELL_SIZE) // 2
    # board_center_y = OFFSET_Y + (BOARD_HEIGHT * CELL_SIZE) // 2

    last_menu_slot = None
    current_menu_stats = None
    menu_lives_timer = 0
    MENU_LIVES_DELAY = 1000  # Раз в секунду

    esc_held = False
    esc_hold_timer = 0
    secret_buffer = ""

    current_volume = 1.0  # Текущая громкость (от 0.0 до 1.0)
    saved_volume = 1.0    # Память для восстановления громкости после мута
    is_muted = False      # Булева о состоянии мута
    VOLUME_STEP = 0.1

    last_drawn_volume = -1.0 
    current_sound_img = None

    running = True
    while running:
        dt_ms = clock.tick(60)

        # События
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                if app_state in ("PLAYING", "FROZEN_GAME", "EXPLODING") and game_state:
                    save_game(game_state["slot"], game_state["player"], game_state["enemy_manager"], game_state)
                running = False

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_0:
                    if is_muted:
                        is_muted = False
                        current_volume = saved_volume  # Возвращаем громкость из памяти
                    else:
                        saved_volume = current_volume  # Запоминаем текущую перед мутом
                        current_volume = 0.0
                        is_muted = True

                # Прибавление громкости
                elif event.key in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS):
                    if is_muted:
                        is_muted = False
                        # Если был мут, плавно прибавляем от того значения, которое запомнили
                        current_volume = min(1.0, saved_volume + VOLUME_STEP)
                    else:
                        current_volume = min(1.0, current_volume + VOLUME_STEP)

                # Убавление громкости
                elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                    if is_muted:
                        is_muted = False
                        # Если был мут, плавно убавляем от того значения, которое запомнили
                        current_volume = max(0.0, saved_volume - VOLUME_STEP)
                    else:
                        # Если мута не было, просто уменьшаем текущую громкость, упираясь в 0.0
                        current_volume = max(0.0, current_volume - VOLUME_STEP)

            # Управление в меню (работает только если "занавес" не двигается)
            if app_state == "MENU" and curtain_dir == 0:
                if event.type == pygame.KEYDOWN:
                    if event.unicode.isalpha():
                        secret_buffer += event.unicode.lower()

                        # Храним только последние 5 символов
                        if len(secret_buffer) > 5:
                            secret_buffer = secret_buffer[-5:]
                        
                        # Проверяем слово и не играет ли уже звук
                        if secret_buffer == "event" or secret_buffer == 'умуте':
                            if assets.EVENT_SOUND and assets.EVENT_SOUND.get_num_channels() == 0:
                                assets.play_sound(assets.EVENT_SOUND, sounds_enabled)
                            secret_buffer = ""

                result = menu.handle_event(event)
                if result:
                    action, slot = result
                    if action == "start_slot":
                        curtain_dir = 1
                        after_curtain = "INIT_GAME"

            # Управление в игре (если не заморожена и "занавес" открыт)
            elif app_state == "PLAYING" and curtain_dir == 0:
                if event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                        esc_held = True

                if event.type == pygame.KEYUP:
                    if event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                        # Пауза срабатывает только если кнопку отпустили быстро (короткое нажатие)
                        if esc_held and esc_hold_timer < LONG_ESC_MS:
                            game_state["paused"] = not game_state["paused"]
                        esc_held = False
                        esc_hold_timer = 0

                if not game_state["paused"]:
                    player = game_state["player"]
                    if event.type == pygame.KEYDOWN:
                        if event.key in PLAYER_MOVE_KEYS:
                            player.handle_keydown(PLAYER_MOVE_KEYS[event.key], game_state["enemies"])
                        if event.key in PLAYER_SHOOT_KEYS:
                            # Считаем, сколько пуль игрока сейчас летит по полю и если их меньше 4, то производим выстрел
                            active_player_bullets = sum(1 for b in game_state["bullets"] if b.is_player)
                            if active_player_bullets < 4:
                                bullet = Bullet(player, player.direction, assets.BULLET_IMG_RAW, is_player=True)
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

            r = int(129 * (1.0 - target_vol))
            g = int(136 * (1.0 - target_vol))
            b = int(111 * (1.0 - target_vol))

            current_sound_img = assets.colorize_icon(assets.SOUNDS_IMG_BASE, (r, g, b, 255))

        # if assets.EVENT_SOUND:
        #     assets.EVENT_SOUND.set_volume(1.0 if sounds_enabled else 0.0)
                
        if esc_held and app_state == "PLAYING" and curtain_dir == 0:
            esc_hold_timer += dt_ms
            if esc_hold_timer >= LONG_ESC_MS:
                esc_held = False
                esc_hold_timer = 0
                save_game(game_state["slot"], game_state["player"], game_state["enemy_manager"], game_state)
                # Автоматически запускаем "занавес"
                app_state = "FROZEN_GAME"
                curtain_dir = 1
                after_curtain = "MENU_FROM_ESC"

        # Переходы
        if curtain_dir != 0:
            transition_timer += dt_ms
            if transition_timer >= TRANSITION_SPEED_MS:
                transition_timer = 0
                curtain += curtain_dir
                
                # "Занавес" полностью закрылся
                if curtain >= 10:
                    curtain = 10
                    if after_curtain == "INIT_GAME":
                        game_state = load_game_into_slot(menu.selected_slot)
                        game_state["sounds_enabled"] = sounds_enabled
                        app_state = "FROZEN_GAME"
                        curtain_dir = -1
                        after_curtain = "START_PLAYING"

                    elif after_curtain == "MENU_FROM_ESC":
                        game_state = None
                        app_state = "MENU"
                        curtain_dir = -1
                        after_curtain = None
                        
                    elif after_curtain == "RESPAWN_OR_GAMEOVER":
                        if game_state["lives"] > 0:
                            # Возрождаем игрока в случайной точке
                            player = game_state["player"]
                            player.grid_x, player.grid_y = random.choice(PLAYER_SPAWN_POINTS)
                            player.set_direction(NAME_TO_DIRECTION["up"])
                            player.update_position()

                            pygame.event.clear()
                            
                            game_state["enemy_manager"].clear_enemies()
                            for b in game_state["bullets"]: b.kill()
                            game_state["all_sprites"].add(player) # Возвращаем игрока на экран
                            
                            app_state = "FROZEN_GAME"
                            curtain_dir = -1
                            after_curtain = "START_PLAYING"
                        else:
                            # Игра окончена
                            delete_save(game_state["slot"])
                            game_state = None
                            app_state = "MENU"
                            curtain_dir = -1
                            after_curtain = None
                            
                # "Занавес" полностью открылся
                elif curtain <= 0:
                    curtain = 0
                    curtain_dir = 0
                    if after_curtain == "START_PLAYING":
                        app_state = "PLAYING"
                        after_curtain = None

        # Логика взрыва
        if app_state == "EXPLODING":
            explosion_timer += dt_ms
            if explosion_timer >= EXPLOSION_SPEED_MS:
                explosion_timer = 0
                explosion_frame += 1
                if explosion_frame >= 4:
                    # Взрыв закончился, запускаем "занавес"
                    curtain_dir = 1
                    after_curtain = "RESPAWN_OR_GAMEOVER"
                    app_state = "FROZEN_GAME"

        # Вторая логика игры (обычная)
        if app_state == "PLAYING" and not game_state["paused"] and curtain_dir == 0:
            player = game_state["player"]
            bullets = game_state["bullets"]
            enemies = game_state["enemies"]
            enemy_manager = game_state["enemy_manager"]
            all_sprites = game_state["all_sprites"]

            max_enemies, speed_multiplier, spawn_delay = get_difficulty_params(game_state)

            player.update_movement(dt_ms, collision_group=enemies)
            all_tanks = pygame.sprite.Group(enemies.sprites() + [player])
            
            for enemy in enemies:
                enemy.update_ai(dt_ms, player, all_tanks, bullets, all_sprites, speed_mult=speed_multiplier)

            bullets.update(dt_ms)

            # Столкновения снарядов
            player_bullets = [b for b in bullets if b.is_player]
            enemy_bullets = [b for b in bullets if not b.is_player]
            for pb in player_bullets:
                collided = pygame.sprite.spritecollide(pb, enemy_bullets, dokill=False, collided=hitbox_collide)
                if collided:
                    pb.kill()
                    for eb in collided: eb.kill()

            for bullet in bullets.sprites():
                if not bullet.alive(): continue
                if bullet.is_player:
                    hit_list = pygame.sprite.spritecollide(bullet, enemies, dokill=False, collided=hitbox_collide)
                    if hit_list:
                        bullet.kill()
                        assets.play_sound(assets.EXPLOSION_SOUND, game_state["sounds_enabled"])
                        for e in hit_list: e.kill()
                        
                        game_state["kills_this_level"] += 1
                        game_state["global_kills"] += 1
                        game_state["score"] += 100
                        if game_state["score"] > game_state["hi_score"]:
                            game_state["hi_score"] = game_state["score"]
                            save_hi_score(game_state["hi_score"])

                        if game_state["kills_this_level"] >= game_state["target_enemies"]:
                            game_state["level"] += 1
                            game_state["target_enemies"] += random.randint(1, 5)
                            game_state["kills_this_level"] = 0
                else:
                    if hitbox_collide(bullet, player):
                        bullet.kill()
                        all_sprites.remove(player)
                        assets.play_sound(assets.EXPLOSION_SOUND, game_state["sounds_enabled"])
                        
                        # Инициализация смерти игрока
                        game_state["lives"] -= 1
                        game_state["lives_positions"] = generate_lives_positions(game_state["lives"])

                        app_state = "EXPLODING"
                        explosion_frame = 0
                        explosion_timer = 0
                        explosion_rect = pygame.Rect(0, 0, 172, 172)
                        pixel_x = OFFSET_X + ((player.grid_x + random.choice([-2, -1])) * CELL_SIZE)
                        pixel_y = OFFSET_Y + ((player.grid_y + random.choice([-2, -1])) * CELL_SIZE)
                        explosion_rect.topleft = (pixel_x, pixel_y)
                        explosion_rect.clamp_ip(board_rect)
                        break

            if app_state == "PLAYING":
                enemy_manager.spawn_enemy_if_needed(dt_ms, max_enemies, spawn_delay)

        # Отрисовка БГшника
        screen.fill(BACKGROUND_COLOR)
        screen.blit(assets.BACKGROUND_IMG, (0, 0))

        # Отрисовка активного "слоя" снизу
        if app_state == "MENU":
            menu.draw()
            
            # Загружаем данные из файла ТОЛЬКО если игрок переключил слот в меню
            if menu.selected_slot != last_menu_slot:
                last_menu_slot = menu.selected_slot
                current_menu_stats = get_menu_stats(last_menu_slot)
                lives_count = current_menu_stats.get("lives", 4)
                current_menu_stats["lives_positions"] = generate_lives_positions(lives_count)
                menu_lives_timer = 0
            
            # Ради забавы обновляем "анимацию" жизней (изначально это был баг но я решил оставить)
            menu_lives_timer += dt_ms
            if menu_lives_timer >= MENU_LIVES_DELAY:
                menu_lives_timer = 0
                lives_count = current_menu_stats.get("lives", 4)
                current_menu_stats["lives_positions"] = generate_lives_positions(lives_count)
            
            # Отрисовываем HUD, используя сохраненные в памяти стейты
            render_hud(screen, font, current_menu_stats, current_sound_img, False, pause_rect, sound_rect)
        elif app_state in ("PLAYING", "FROZEN_GAME", "EXPLODING"):
            if game_state:
                game_state["all_sprites"].draw(screen)

                # Отрисовка взрыва
                if app_state == "EXPLODING" and explosion_rect is not None:
                    # Логика кадров: 0 -> exp1, 1 -> exp2, 2 -> exp1, 3 -> exp2
                    img_idx = 0 if explosion_frame % 2 == 0 else 1
                    if len(assets.EXPLOSION_IMGS) > img_idx:
                        screen.blit(assets.EXPLOSION_IMGS[img_idx], explosion_rect)

                # Отрисовка HUD игры
                _, speed_multiplier, _ = get_difficulty_params(game_state)
                stats = {
                    "score": game_state["score"], 
                    "hi_score": game_state["hi_score"],
                    "kills_this_level": game_state["kills_this_level"], 
                    "target_enemies": game_state["target_enemies"],
                    "level": game_state["level"], 
                    "speed_multiplier": speed_multiplier,
                    "lives_positions": game_state["lives_positions"]
                }
                render_hud(screen, font, stats, current_sound_img, game_state["paused"], pause_rect, sound_rect)
        
        if esc_hold_timer > 100 and app_state in ("PLAYING", "FROZEN_GAME"):
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

        # Отрисовка "занавеса" поверх всего
        if curtain > 0:
            t_idx = curtain - 1
            if len(assets.TRANSITION_IMGS) > t_idx:
                t_img = assets.TRANSITION_IMGS[t_idx]
                t_rect = t_img.get_rect()
                screen.blit(t_img, t_rect)

        pygame.display.flip()
        
    pygame.quit()

# Да.
if __name__ == "__main__":
    main()
