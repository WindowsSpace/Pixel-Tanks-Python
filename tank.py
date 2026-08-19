import pygame
import random
from typing import Literal
from settings import DIR_TO_ANGLE, DIR_UP, DIR_DOWN, DIR_LEFT, DIR_RIGHT, PLAYER_MOVE_DELAY_MS, BOARD_WIDTH, BOARD_HEIGHT, CELL_SIZE
from grid import grid_to_pixel_center, in_bounds
from bullet import Bullet
import assets

class Tank(pygame.sprite.Sprite):
    def __init__(self, gx, gy, image_data, hp:int = 1, max_hp:int = 1) -> None:
        super().__init__()
        self.hp = hp
        self.max_hp = max_hp
        
        if isinstance(image_data, dict):
            if not image_data:
                self.frames_dict = {"default": assets.PIXEL_IMG_RAW}
            else:
                self.frames_dict = image_data
            
            self.current_state = "idle" if "idle" in self.frames_dict else list(self.frames_dict.keys())[0]
        elif isinstance(image_data, list):
            self.frames_dict = {"idle": image_data[0]}
            self.current_state = "idle"
        else:
            self.frames_dict = {"idle": image_data}
            self.current_state = "idle"
            
        self.base_image = self.frames_dict[self.current_state]
        self.image = self.base_image.copy()
        self.rect = self.image.get_rect()

        # Базовые хитбоксы
        self.hitbox = self.rect.copy()
        self.hurt_hitbox = self.hitbox.copy() # Копия обычного хитбокса, доступная для ручного редактирования
        
        self.grid_x = gx
        self.grid_y = gy
        self.direction = random.choice([DIR_UP, DIR_DOWN, DIR_LEFT, DIR_RIGHT])
        self.angle = DIR_TO_ANGLE[self.direction]
        self.anim_timer = 0
        
        self.update_image()
        self.update_position()
    
    def set_state(self, new_state:Literal['idle', ''] = 'idle') -> None:
        if new_state in self.frames_dict and self.current_state != new_state:
            self.current_state = new_state
            self.base_image = self.frames_dict[self.current_state]
            self.update_image()

    def update_image(self) -> None:
        self.image = pygame.transform.rotate(self.base_image, self.angle)
        self.rect = self.image.get_rect(center=self.rect.center)
        self.mask = pygame.mask.from_surface(self.image)

    def update_position(self) -> None:
        cx, cy = grid_to_pixel_center(self.grid_x, self.grid_y)
        self.rect.centerx, self.rect.centery = cx, cy
        self.hitbox.centerx, self.hitbox.centery = cx, cy
        self.hurt_hitbox.centerx, self.hurt_hitbox.centery = cx, cy

    def set_direction(self, direction, collision_group = None) -> None:
        self.direction = direction
        self.angle = DIR_TO_ANGLE[self.direction]
        self.update_image()
        if collision_group:
            self.resolve_rotation_overlap(collision_group)
    
    def update_movement_anim(self, is_moving:bool, speed_rate:int = 15) -> None:
        if not is_moving:
            self.set_state("idle")
            return

        self.anim_timer += 1
        if (self.anim_timer // speed_rate) % 2 == 0:
            self.set_state("move0")
        else:
            self.set_state("move1")

    def can_move_to(self, gx, gy, collision_group = None) -> bool:
        cell_width = self.rect.width // CELL_SIZE
        cell_radius = cell_width // 2
        
        if not (in_bounds(gx - cell_radius, gy - cell_radius) and 
                in_bounds(gx + cell_radius, gy + cell_radius)): 
            return False
        
        if collision_group:
            old_center = self.rect.center
            self.rect.center = grid_to_pixel_center(gx, gy)
            
            if not hasattr(self, 'mask'):
                self.mask = pygame.mask.from_surface(self.image)
                
            for sprite in collision_group:
                if sprite is not self:
                    if not hasattr(sprite, 'mask'):
                        sprite.mask = pygame.mask.from_surface(sprite.image)
                    if pygame.sprite.collide_mask(self, sprite):
                        self.rect.center = old_center
                        return False
            self.rect.center = old_center
        return True

    def move_step(self, collision_group = None) -> bool:
        new_x, new_y = self.grid_x + self.direction[0], self.grid_y + self.direction[1]
        if self.can_move_to(new_x, new_y, collision_group):
            self.grid_x, self.grid_y = new_x, new_y
            self.update_position()
            return True
        return False
    
    def resolve_rotation_overlap(self, collision_group) -> None:
        if not collision_group: return
        is_overlapping = any(sprite is not self and pygame.sprite.collide_mask(self, sprite) for sprite in collision_group)
        if not is_overlapping: return
            
        dx, dy = self.direction
        if self.can_move_to(self.grid_x + dx, self.grid_y + dy, collision_group):
            self.grid_x += dx
            self.grid_y += dy
            self.update_position()
            return
        if self.can_move_to(self.grid_x - dx, self.grid_y - dy, collision_group):
            self.grid_x -= dx
            self.grid_y -= dy
            self.update_position()
            return

class PlayerTank(Tank):
    def __init__(self, gx, gy, base_image = None, hp=1, max_hp=1) -> None:
        if base_image is None:
            base_image = assets.PLAYER_BASE_IMG
        super().__init__(gx, gy, base_image, hp=hp, max_hp=max_hp)
        self.current_move_dir = None
        self.key_held = False
        self.time_since_last_step = 0
        self.fixed_direction = None

    def handle_keydown(self, direction, collision_group = None) -> None:
        self.current_move_dir = direction
        self.key_held = True
        move_dir = self.fixed_direction if self.fixed_direction else direction
        if self.direction == move_dir:
            self.time_since_last_step = PLAYER_MOVE_DELAY_MS 
        else:
            self.set_direction(move_dir, collision_group)
            self.time_since_last_step = 0

    def handle_keyup(self, direction) -> None:
        if self.current_move_dir == direction:
            self.key_held = False
            self.current_move_dir = None
            self.time_since_last_step = 0

    def update_movement(self, dt_ms, collision_group = None) -> None:
        if not self.key_held or self.current_move_dir is None: return
        target_dir = self.fixed_direction if self.fixed_direction else self.current_move_dir
        if self.direction != target_dir:
            self.set_direction(target_dir, collision_group)
            self.time_since_last_step = 0
            return

        self.time_since_last_step += dt_ms
        if self.time_since_last_step >= PLAYER_MOVE_DELAY_MS:
            self.time_since_last_step = 0
            dx, dy = self.current_move_dir
            if self.can_move_to(self.grid_x + dx, self.grid_y + dy, collision_group):
                self.grid_x += dx
                self.grid_y += dy
                self.update_position()
            else:
                self.key_held, self.current_move_dir = False, None

class EnemyTank(Tank):
    def __init__(self, gx, gy, base_image = None, hp=1, max_hp=1,
                aggressiveness=0.6,
                move_time_min=400, move_time_max=800,
                shoot_time_min=1000, shoot_time_max=3500,
                destroy_blocks_priority=True) -> None:
        if base_image is None:
            base_image = assets.ENEMY_BASE_IMG
        super().__init__(gx, gy, base_image, hp=hp, max_hp=max_hp)
        
        # Настройки
        self.aggressiveness = aggressiveness
        self.move_time_min = move_time_min
        self.move_time_max = move_time_max
        self.shoot_time_min = shoot_time_min
        self.shoot_time_max = shoot_time_max
        self.destroy_blocks_priority = destroy_blocks_priority

        # Переменные для детектора застревания
        self.stuck_timer = 0
        self.stuck_threshold = 300
        
        self.is_recovering = False
        self.recovery_timer = 0
        self.recovery_duration = 500

        self.move_timer = random.randint(self.move_time_min, self.move_time_max)
        self.shoot_timer = random.randint(self.shoot_time_min, self.shoot_time_max)

    def update_ai(self, dt_ms, player, collision_group, bullets_group, all_sprites_group, speed_mult=1.0) -> None:
        self.shoot_timer -= dt_ms * speed_mult
        if self.shoot_timer <= 0:
            self.shoot(bullets_group, all_sprites_group)
            self.shoot_timer = random.randint(self.shoot_time_min, self.shoot_time_max)

        if self.is_recovering:
            self.recovery_timer -= dt_ms * speed_mult

            self.move_timer -= dt_ms * speed_mult
            if self.move_timer <= 0:
                self.move_step(collision_group)
                self.move_timer = random.randint(self.move_time_min, self.move_time_max)

            if self.recovery_timer <= 0:
                self.is_recovering = False
                self.choose_smart_random_direction(collision_group)
            return

        self.move_timer -= dt_ms * speed_mult
        if self.move_timer <= 0:
            if random.random() < self.aggressiveness: 
                dx, dy = player.grid_x - self.grid_x, player.grid_y - self.grid_y
                possible_dirs = [(DIR_RIGHT if dx > 0 else DIR_LEFT)] if abs(dx) > abs(dy) else [(DIR_DOWN if dy > 0 else DIR_UP)]
                chosen_dir = possible_dirs[0] if possible_dirs else random.choice([DIR_UP, DIR_DOWN, DIR_LEFT, DIR_RIGHT])
            else:
                chosen_dir = random.choice([DIR_UP, DIR_DOWN, DIR_LEFT, DIR_RIGHT])

            if self.direction != chosen_dir:
                self.set_direction(chosen_dir, collision_group)
            else:
                moved = self.move_step(collision_group)
                if not moved:
                    self.stuck_timer += 400 
                    if self.stuck_timer >= self.stuck_threshold:
                        self.start_recovery()
                    elif self.destroy_blocks_priority:
                        if random.random() < self.aggressiveness:
                            self.shoot(bullets_group, all_sprites_group)

                        if random.random() < 0.3:
                            avail = self.get_available_directions(collision_group)
                            backward = (-self.direction[0], -self.direction[1])
                            
                            sides = [d for d in avail if d != self.direction and d != backward]

                            if sides:
                                self.set_direction(random.choice(sides), collision_group)
                                self.stuck_timer = 0
                else:
                    self.stuck_timer = 0
            self.move_timer = random.randint(self.move_time_min, self.move_time_max)

    def shoot(self, bullets_group, all_sprites_group) -> None:
        b = Bullet(self, self.direction, assets.PIXEL_IMG_RAW, is_player=False)
        bullets_group.add(b)
        all_sprites_group.add(b)

    def start_recovery(self) -> None:
        self.is_recovering = True
        self.recovery_timer = self.recovery_duration
        self.stuck_timer = 0
        
        if self.direction == DIR_UP:
            self.set_direction(DIR_DOWN)
        elif self.direction == DIR_DOWN:
            self.set_direction(DIR_UP)
        elif self.direction == DIR_LEFT:
            self.set_direction(DIR_RIGHT)
        elif self.direction == DIR_RIGHT:
            self.set_direction(DIR_LEFT)

    def choose_smart_random_direction(self, collision_group) -> None:
        avail = self.get_available_directions(collision_group)
        
        if avail:
            backward = (-self.direction[0], -self.direction[1])
            sides = [d for d in avail if d != self.direction and d != backward]
            
            if sides:
                new_dir = random.choice(sides)
            else:
                new_dir = random.choice(avail)
                
            self.set_direction(new_dir, collision_group)
        else:
            self.set_direction(random.choice([DIR_UP, DIR_DOWN, DIR_LEFT, DIR_RIGHT]), collision_group)

    def get_available_directions(self, collision_group):
        available = []
        for d in [DIR_UP, DIR_DOWN, DIR_LEFT, DIR_RIGHT]:
            if self.can_move_to(self.grid_x + d[0], self.grid_y + d[1], collision_group):
                available.append(d)
        return available

class DefaultBoss(Tank):
    def __init__(self, gx, gy, frames_dict = None, hp:int = 2, max_hp:int = None) -> None:
        if frames_dict is None:
            frames_dict = assets.DEFAULT_BOSS_FRAMES
        max_hp_val = max_hp if max_hp is not None else hp
        super().__init__(gx, gy, frames_dict, hp=hp, max_hp=max_hp_val)
        
        self.set_direction(DIR_DOWN)
        
        self.move_timer = 500
        
        # Таймеры стрельбы
        self.shoot_timer = 2000
        self.burst_count = 0  # Количество пуль в текущей очереди
        self.burst_timer = 500  # Задержка между пулями в очереди
        
        self.current_move_dir = DIR_LEFT
        
        # Переопределяем хитбокс
        self.hurt_hitbox = pygame.Rect(0, 0, 6, self.rect.height)
        self.update_position()
    
    def update_position(self) -> None:
        super().update_position()
        self.set_state(
            "left1" if self.grid_x <= 1 else
            "left0" if self.grid_x <= 2 else
            "right1" if self.grid_x >= BOARD_WIDTH - 2 else
            "right0" if self.grid_x >= BOARD_WIDTH - 3 else
            "idle"
        )
    
    def can_move_to(self, gx, gy, collision_group = None) -> bool:
        if gx < 1 or gx > BOARD_WIDTH - 2:
            return False

        cell_radius = self.rect.width // CELL_SIZE // 2
        if gy - cell_radius < 0 or gy + cell_radius >= BOARD_HEIGHT:
            return False
            
        if collision_group:
            old_center = self.rect.center
            self.rect.center = grid_to_pixel_center(gx, gy)
            
            if not hasattr(self, 'mask'):
                self.mask = pygame.mask.from_surface(self.image)
                
            for sprite in collision_group:
                if sprite is not self:
                    if not hasattr(sprite, 'mask'):
                        sprite.mask = pygame.mask.from_surface(sprite.image)
                    if pygame.sprite.collide_mask(self, sprite):
                        self.rect.center = old_center
                        return False
            self.rect.center = old_center
        return True

    def update_ai(self, dt_ms, player, collision_group, bullets_group, all_sprites_group, speed_mult=1.0) -> None:
        self.move_timer -= dt_ms * (speed_mult / 2)
        if self.move_timer <= 0:
            if random.random() < 0.3:
                self.current_move_dir = random.choice([DIR_LEFT, DIR_RIGHT])
            
            dx, dy = self.current_move_dir
            if self.can_move_to(self.grid_x + dx, self.grid_y + dy, collision_group):
                self.grid_x += dx
                self.grid_y += dy
            else:
                self.current_move_dir = DIR_RIGHT if self.current_move_dir == DIR_LEFT else DIR_LEFT
                
            self.update_position()
            self.move_timer = 600

        # Логика стрельбы
        if self.burst_count > 0:
            self.burst_timer -= dt_ms * (speed_mult / 2)
            if self.burst_timer <= 0:
                orig_center = self.rect.center

                self.rect.center = (self.hurt_hitbox.centerx, self.hurt_hitbox.bottom)
                b = Bullet(self, DIR_DOWN, assets.PIXEL_IMG_RAW, is_player=False)
                
                self.rect.center = orig_center 
                
                bullets_group.add(b)
                all_sprites_group.add(b)
                
                self.burst_count -= 1
                if self.burst_count > 0:
                    self.burst_timer = 500  # Время в миллисекундах между пулями в очереди
                else:
                    self.shoot_timer = 2000 # Задержка до следующей атаки
        else:
            self.shoot_timer -= dt_ms * speed_mult
            if self.shoot_timer <= 0:
                self.burst_count = 2 # Выпускаем 2 пули по очереди
                self.burst_timer = 0
