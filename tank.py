import pygame
import random
from settings import DIR_TO_ANGLE, DIR_UP, DIR_DOWN, DIR_LEFT, DIR_RIGHT, PLAYER_MOVE_DELAY_MS
from grid import grid_to_pixel_center, in_bounds
from bullet import Bullet
import assets

TankHitbox = 129

class Tank(pygame.sprite.Sprite):
    def __init__(self, gx, gy, base_image) -> None:
        super().__init__()
        self.base_image = base_image
        self.image = self.base_image.copy()
        self.rect = self.image.get_rect()
        self.hitbox = pygame.Rect(0, 0, TankHitbox, TankHitbox)
        self.grid_x = gx
        self.grid_y = gy
        self.direction = random.choice([DIR_UP, DIR_DOWN, DIR_LEFT, DIR_RIGHT])
        self.angle = DIR_TO_ANGLE[self.direction]
        self.update_image()
        self.update_position()

    def update_image(self) -> None:
        self.image = pygame.transform.rotate(self.base_image, self.angle)
        self.rect = self.image.get_rect(center=self.rect.center)
        self.mask = pygame.mask.from_surface(self.image)

    def update_position(self) -> None:
        cx, cy = grid_to_pixel_center(self.grid_x, self.grid_y)
        self.rect.centerx, self.rect.centery = cx, cy
        self.hitbox.centerx, self.hitbox.centery = cx, cy

    def set_direction(self, direction, collision_group = None) -> None:
        self.direction = direction
        self.angle = DIR_TO_ANGLE[self.direction]
        self.update_image()
        if collision_group:
            self.resolve_rotation_overlap(collision_group)

    def can_move_to(self, gx, gy, collision_group = None) -> bool:
        if not (in_bounds(gx - 1, gy - 1) and in_bounds(gx + 1, gy + 1)): return False
        
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
        if not collision_group:
            return
            
        is_overlapping = False
        for sprite in collision_group:
            if sprite is not self and pygame.sprite.collide_mask(self, sprite):
                is_overlapping = True
                break
                
        if not is_overlapping:
            return
            
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
    def __init__(self, gx, gy, base_image) -> None:
        super().__init__(gx, gy, base_image)
        self.current_move_dir = None
        self.key_held = False
        self.time_since_last_step = 0

    def handle_keydown(self, direction, collision_group = None) -> None:
        self.current_move_dir = direction
        self.key_held = True
        if self.direction == direction:
            self.time_since_last_step = PLAYER_MOVE_DELAY_MS 
        else:
            self.set_direction(direction, collision_group)
            self.time_since_last_step = 0

    def handle_keyup(self, direction) -> None:
        if self.current_move_dir == direction:
            self.key_held = False
            self.current_move_dir = None
            self.time_since_last_step = 0

    def update_movement(self, dt_ms, collision_group = None) -> None:
        if not self.key_held or self.current_move_dir is None: return
        if self.direction != self.current_move_dir:
            self.set_direction(self.current_move_dir, collision_group)
            self.time_since_last_step = 0
            return

        self.time_since_last_step += dt_ms
        if self.time_since_last_step >= PLAYER_MOVE_DELAY_MS:
            self.time_since_last_step = 0
            if not self.move_step(collision_group):
                self.key_held, self.current_move_dir = False, None

class EnemyTank(Tank):
    def __init__(self, gx, gy, base_image) -> None:
        super().__init__(gx, gy, base_image)
        self.move_timer = random.randint(500, 1000)
        self.shoot_timer = random.randint(500, 4500)

    def update_ai(self, dt_ms, player, collision_group, bullets_group, all_sprites_group, speed_mult=1.0) -> None:
        self.shoot_timer -= dt_ms * speed_mult
        if self.shoot_timer <= 0:
            b = Bullet(self, self.direction, assets.BULLET_IMG_RAW, is_player=False)
            bullets_group.add(b)
            all_sprites_group.add(b)
            self.shoot_timer = random.randint(500, 3500)

        self.move_timer -= dt_ms * speed_mult
        if self.move_timer <= 0:
            if random.random() < 0.6: 
                dx, dy = player.grid_x - self.grid_x, player.grid_y - self.grid_y
                possible_dirs = [(DIR_RIGHT if dx > 0 else DIR_LEFT)] if abs(dx) > abs(dy) else [(DIR_DOWN if dy > 0 else DIR_UP)]
                chosen_dir = possible_dirs[0] if possible_dirs else random.choice([DIR_UP, DIR_DOWN, DIR_LEFT, DIR_RIGHT])
            else:
                chosen_dir = random.choice([DIR_UP, DIR_DOWN, DIR_LEFT, DIR_RIGHT])

            if self.direction != chosen_dir:
                self.set_direction(chosen_dir, collision_group)
            else:
                self.move_step(collision_group)

            self.move_timer = random.randint(400, 800)
