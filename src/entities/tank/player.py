# Танк игрока


from core import assets
from core.settings import PLAYER_MOVE_DELAY_MS
from entities.tank.base import Tank


class PlayerTank(Tank):
    def __init__(self, gx, gy, base_image = None, hp=1, max_hp=1) -> None:
        if base_image is None:
            base_image = assets.PLAYER_BASE_IMG
        super().__init__(gx, gy, base_image, hp=hp, max_hp=max_hp)
        self.current_move_dir = None
        self.key_held = False
        self.time_since_last_step = 0
        self.fixed_direction = None
        self.invuln_ms = 0  # > 0 - игрок мигает и не получает урон

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
