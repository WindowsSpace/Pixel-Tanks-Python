import pygame
import time

from settings import WIDTH, HEIGHT, BACKGROUND_COLOR, PLAYER_MOVE_KEYS, PLAYER_SHOOT_KEYS, PLAYER_START_GRID
import assets 
from tank import PlayerTank, EnemyTank
from bullet import Bullet
from enemy_manager import EnemyManager
from menu import MainMenu
from save_load import save_game, load_game, NAME_TO_DIRECTION

LONG_ESC_MS = 800  # сколько держать ESC для выхода с сохранением

def create_new_game(slot):
    all_sprites = pygame.sprite.Group()
    bullets = pygame.sprite.Group()
    enemies = pygame.sprite.Group()

    player = PlayerTank(PLAYER_START_GRID[0], PLAYER_START_GRID[1], assets.PLAYER_BASE_IMG)
    all_sprites.add(player)

    enemy_manager = EnemyManager(
        enemy_image=assets.ENEMY_BASE_IMG,
        enemies_group=enemies,
        all_sprites_group=all_sprites,
        player=player,
    )

    return {
        "slot": slot,
        "player": player,
        "enemy_manager": enemy_manager,
        "all_sprites": all_sprites,
        "bullets": bullets,
        "enemies": enemies,
        "paused": False,
    }


def load_game_into_slot(slot):
    # загрузить сохранённые данные, если есть
    state = create_new_game(slot)
    data = load_game(slot)
    if data is None:
        return state  # новый прогресс

    player = state["player"]
    enemy_manager = state["enemy_manager"]
    enemies = state["enemies"]
    all_sprites = state["all_sprites"]

    # Восстановление игрока
    player.grid_x = data["player"]["grid_x"]
    player.grid_y = data["player"]["grid_y"]
    
    direction_name = data["player"].get("direction", "up")
    player.set_direction(NAME_TO_DIRECTION.get(direction_name, NAME_TO_DIRECTION["up"]))
    player.update_position()

    # Враги
    
    for e_data in data.get("enemies", []):
        ex = e_data["grid_x"]
        ey = e_data["grid_y"]
        dname = e_data.get("direction", "up")
        enemy = EnemyTank(ex, ey, assets.ENEMY_BASE_IMG)
        enemy.set_direction(NAME_TO_DIRECTION.get(dname, NAME_TO_DIRECTION["up"]))
        enemy.update_position()
        enemies.add(enemy)
        all_sprites.add(enemy)

    enemy_manager.total_spawned = data.get("total_spawned", 0)
    enemy_manager.total_destroyed = data.get("total_destroyed", 0)

    return state

def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Tank Game")

    assets.convert_assets()

    clock = pygame.time.Clock()
    font = pygame.font.SysFont("arial", 28)

    # Состояние
    app_state = "menu"  # "menu" или "playing"

    game_state = None  # словарь из create_new_game/load_game_into_slot
    esc_down_time = None

    menu = MainMenu(screen, font)

    # Подготовим rect для спрайта паузы
    pause_rect = assets.PAUSE_IMG.get_rect(center=(WIDTH // 2, HEIGHT // 2))

    running = True
    while running:
        dt_ms = clock.tick(60)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                # Если идёт игра — автосейв и выход
                if app_state == "playing" and game_state is not None:
                    save_game(game_state["slot"], game_state["player"], game_state["enemy_manager"])
                running = False

            if app_state == "menu":
                result = menu.handle_event(event)
                if result:
                    action, slot = result
                    if action == "start_slot":
                        # Загружаем игру/создаём новую
                        game_state = load_game_into_slot(slot)
                        app_state = "playing"

            elif app_state == "playing":
                # ESC: пауза/длинное удержание — выход с сохранением
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    esc_down_time = pygame.time.get_ticks()
                    # короткое нажатие — просто пауза
                    game_state["paused"] = not game_state["paused"]

                if event.type == pygame.KEYUP and event.key == pygame.K_ESCAPE:
                    if esc_down_time is not None:
                        held = pygame.time.get_ticks() - esc_down_time
                        esc_down_time = None
                        if held >= LONG_ESC_MS:
                            # долгий ESC: сохранить и вернуться в меню
                            save_game(game_state["slot"], game_state["player"], game_state["enemy_manager"])
                            app_state = "menu"
                            game_state = None
                            continue  # сразу рисуем меню

                if not game_state["paused"]:
                    # Управление и стрельба
                    player = game_state["player"]
                    bullets = game_state["bullets"]
                    enemies = game_state["enemies"]
                    enemy_manager = game_state["enemy_manager"]
                    all_sprites = game_state["all_sprites"]

                    if event.type == pygame.KEYDOWN:
                        from settings import PLAYER_MOVE_KEYS, PLAYER_SHOOT_KEYS
                        if event.key in PLAYER_MOVE_KEYS:
                            direction = PLAYER_MOVE_KEYS[event.key]
                            player.handle_keydown(direction)

                        if event.key in PLAYER_SHOOT_KEYS:
                            bullet = Bullet(player, player.direction)
                            bullets.add(bullet)
                            all_sprites.add(bullet)

                    if event.type == pygame.KEYUP:
                        from settings import PLAYER_MOVE_KEYS
                        if event.key in PLAYER_MOVE_KEYS:
                            direction = PLAYER_MOVE_KEYS[event.key]
                            player.handle_keyup(direction)

        # Обновление и рендер
        if app_state == "menu":
            menu.draw()
            pygame.display.flip()
            continue

        # app_state == "playing"
        player = game_state["player"]
        bullets = game_state["bullets"]
        enemies = game_state["enemies"]
        enemy_manager = game_state["enemy_manager"]
        all_sprites = game_state["all_sprites"]

        if not game_state["paused"]:
            player.update_movement(dt_ms, collision_group=enemies)
            bullets.update()

            for bullet in bullets.copy():
                hit_list = pygame.sprite.spritecollide(bullet, enemies, dokill=False)
                if hit_list:
                    bullet.kill()
                    for e in hit_list:
                        enemy_manager.enemy_destroyed(e)

            enemy_manager.spawn_enemy_if_needed()

            if enemy_manager.is_level_completed():
                # можно сохранить и вернуться в меню
                save_game(game_state["slot"], player, enemy_manager)
                app_state = "menu"
                game_state = None

        # Рендер игры
        screen.fill(BACKGROUND_COLOR)
        screen.blit(assets.BACKGROUND_IMG, (0, 0))
        all_sprites.draw(screen)

        if game_state["paused"]:
            screen.blit(assets.PAUSE_IMG, pause_rect)

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
