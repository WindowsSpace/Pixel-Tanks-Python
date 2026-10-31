# Танк противника с настраиваемым ИИ

import random

from core import assets
from core.settings import DIR_DOWN, DIR_LEFT, DIR_RIGHT, DIR_UP
from entities.bullet import Bullet
from entities.tank.base import Tank

_ALL_DIRS = [DIR_UP, DIR_DOWN, DIR_LEFT, DIR_RIGHT]
_REVERSE  = {DIR_UP: DIR_DOWN, DIR_DOWN: DIR_UP,
             DIR_LEFT: DIR_RIGHT, DIR_RIGHT: DIR_LEFT}


class EnemyTank(Tank):

    def __init__(
        self,
        gx, gy,
        base_image=None,
        hp=1, max_hp=1,
        # поведение
        aggressiveness=0.6,
        intelligence=0.4,
        patrol_chance=0.12,
        patrol_min=3000,
        patrol_max=7000,
        # таймеры движения
        move_time_min=400, move_time_max=800,
        # таймеры стрельбы
        shoot_time_min=1000, shoot_time_max=3500,
        # перезарядка (минимальный интервал между ЛЮБЫМИ выстрелами)
        reload_ms=900,
    ) -> None:
        if base_image is None:
            base_image = assets.ENEMY_BASE_IMG
        super().__init__(gx, gy, base_image, hp=hp, max_hp=max_hp)
        self.bullet_color = None  # цвет подложки пуль (None - обычные)

        self.aggressiveness       = max(0.0, min(1.0, aggressiveness))
        self.intelligence         = max(0.0, min(1.0, intelligence))
        self.patrol_chance        = max(0.0, min(1.0, patrol_chance))
        self.patrol_min           = patrol_min
        self.patrol_max           = patrol_max
        self.move_time_min        = move_time_min
        self.move_time_max        = move_time_max
        self.shoot_time_min       = shoot_time_min
        self.shoot_time_max       = shoot_time_max
        self.reload_ms            = reload_ms  # 0 - без перезарядки (например, у босса)
        self.reload_timer         = 0  # сколько мс осталось до следующего выстрела
        self.side_fail_count      = 0  # подряд неудачных попыток "расчистить" боковой блок

        # Таймеры
        self.move_timer  = random.randint(self.move_time_min,  self.move_time_max)
        self.shoot_timer = random.randint(self.shoot_time_min, self.shoot_time_max)

        # Детектор застревания
        self.stuck_timer     = 0
        self.stuck_threshold = 300

        # Recovery (отъезд назад при полном застревании)
        self.is_recovering     = False
        self.recovery_timer    = 0
        self.recovery_duration = 500

        # Патрулирование
        self.is_patrolling = False
        self.patrol_timer  = 0

        # Боковая расчистка (intelligence >= 0.6)
        self.is_side_clearing     = False
        self.side_clear_timer     = 0
        self.side_clear_duration  = 700  # мс
        self.side_clear_saved_dir = None  # запомненное направление к игроку

    @staticmethod
    def _is_block_at(gx, gy, blocks_group) -> bool:
        # Есть ли разрушаемый блок в клетке (gx, gy)?
        if blocks_group is None:
            return False
        for b in blocks_group:
            if b.grid_x == gx and b.grid_y == gy:
                return True
        return False

    def _find_side_blocks(self, blocks_group) -> list:
        # Ищет блоки, стоящие СБОКУ от пути движения и мешающие проехать из-за
        if blocks_group is None:
            return []
        dx, dy   = self.direction
        perp1    = (-dy,  dx)  # одна боковая сторона
        perp2    = ( dy, -dx)  # другая боковая сторона
        fw_x, fw_y = self.grid_x + dx, self.grid_y + dy
        result = []
        for pd in (perp1, perp2):
            # Клетка сбоку от следующей по курсу
            cx, cy = fw_x + pd[0], fw_y + pd[1]
            if self._is_block_at(cx, cy, blocks_group):
                result.append((cx, cy, pd))
            # Та же боковая позиция, но ещё одну клетку вперёд (длинные коридоры)
            cx2, cy2 = cx + dx, cy + dy
            if self._is_block_at(cx2, cy2, blocks_group):
                result.append((cx2, cy2, pd))
        return result

    def _toward_player_dir(self, player) -> tuple:
        # Направление к игроку (ось с большей разницей координат)
        dx = player.grid_x - self.grid_x
        dy = player.grid_y - self.grid_y
        if abs(dx) >= abs(dy):
            return DIR_RIGHT if dx > 0 else DIR_LEFT
        return DIR_DOWN if dy > 0 else DIR_UP

    def _run_recovery(self, dt_ms, collision_group, speed_mult) -> None:
        # Отъезд назад - выход из полного застревания
        self.recovery_timer -= dt_ms * speed_mult
        self.move_timer -= dt_ms * speed_mult
        if self.move_timer <= 0:
            self.move_step(collision_group)
            self.move_timer = random.randint(self.move_time_min, self.move_time_max)
        if self.recovery_timer <= 0:
            self.is_recovering = False
            self.choose_smart_random_direction(collision_group)

    def _run_patrol(self, dt_ms, collision_group,
                    bullets_group, all_sprites_group, speed_mult) -> None:
        # Режим патруля: враг бродит случайно и стреляет вразброс
        self.patrol_timer -= dt_ms * speed_mult

        # Стрельба - более редкая и случайная (50 % тиков вообще не стреляем)
        self.shoot_timer -= dt_ms * speed_mult
        if self.shoot_timer <= 0:
            if random.random() < 0.5:
                self._try_shoot(bullets_group, all_sprites_group)
            self.shoot_timer = random.randint(
                int(self.shoot_time_min * 1.5),
                int(self.shoot_time_max * 2.0),
            )

        # Движение - предпочитаем прямо или бок, не назад
        self.move_timer -= dt_ms * speed_mult
        if self.move_timer <= 0:
            avail = self.get_available_directions(collision_group)
            if avail:
                backward  = _REVERSE.get(self.direction)
                fwd_sides = [d for d in avail if d != backward] or avail
                chosen    = random.choice(fwd_sides)
                if self.direction != chosen:
                    self.set_direction(chosen, collision_group)
                else:
                    self.move_step(collision_group)
            self.move_timer = random.randint(self.move_time_min, self.move_time_max)

        if self.patrol_timer <= 0:
            self.is_patrolling = False

    def _run_side_clearing(self, dt_ms, collision_group,
                            bullets_group, all_sprites_group, speed_mult) -> None:
        # Режим боковой расчистки: враг уже сдвинулся боком и теперь стреляет в своём
        self.side_clear_timer -= dt_ms * speed_mult

        self.shoot_timer -= dt_ms * speed_mult
        if self.shoot_timer <= 0:
            self._try_shoot(bullets_group, all_sprites_group)
            # Частая стрельба, чтобы быстрее разнести блок
            self.shoot_timer = random.randint(
                max(100, self.shoot_time_min // 2),
                max(300, self.shoot_time_max // 3),
            )

        if self.side_clear_timer <= 0:
            self.is_side_clearing = False
            if self.side_clear_saved_dir is not None:
                self.set_direction(self.side_clear_saved_dir, collision_group)
                self.side_clear_saved_dir = None

    def update_ai(
        self,
        dt_ms, player,
        collision_group, bullets_group, all_sprites_group,
        speed_mult=1.0,
        blocks_group=None,
    ) -> None:

        # 0. Перезарядка тикает всегда (в любом суб-режиме ИИ)
        if self.reload_timer > 0:
            self.reload_timer -= dt_ms * speed_mult

        # 1. Recovery
        if self.is_recovering:
            self._run_recovery(dt_ms, collision_group, speed_mult)
            return

        # 2. Боковая расчистка (высокий интеллект)
        if self.is_side_clearing:
            self._run_side_clearing(dt_ms, collision_group,
                                    bullets_group, all_sprites_group, speed_mult)
            return

        # 3. Патрулирование
        if self.is_patrolling:
            self._run_patrol(dt_ms, collision_group,
                             bullets_group, all_sprites_group, speed_mult)
            return

        # 4. Обычный таймер стрельбы
        self.shoot_timer -= dt_ms * speed_mult
        if self.shoot_timer <= 0:
            self._try_shoot(bullets_group, all_sprites_group)
            self.shoot_timer = random.randint(self.shoot_time_min, self.shoot_time_max)

        # 5. Таймер движения
        self.move_timer -= dt_ms * speed_mult
        if self.move_timer > 0:
            return

        # 6. Случайный переход в патруль Умный враг реже уходит в патруль
        eff_patrol = self.patrol_chance * (1.0 - self.intelligence * 0.5)
        if random.random() < eff_patrol:
            self.is_patrolling = True
            self.patrol_timer  = random.randint(self.patrol_min, self.patrol_max)
            self.move_timer    = random.randint(self.move_time_min, self.move_time_max)
            return

        # 7. Выбор направления: к игроку или случайное
        if random.random() < self.aggressiveness:
            chosen_dir = self._toward_player_dir(player)
        else:
            chosen_dir = random.choice(_ALL_DIRS)

        # 8. Попытка движения
        if self.direction != chosen_dir:
            self.set_direction(chosen_dir, collision_group)

        else:
            moved = self.move_step(collision_group)

            if not moved:
                self.stuck_timer += 400

                # Стрельба вперёд (пытаемся разнести центральный блок)
                if random.random() < self.aggressiveness:
                    self._try_shoot(bullets_group, all_sprites_group)

                # Интеллектуальная расчистка боковых блоков
                if self.intelligence >= 0.4 and blocks_group is not None:
                    side_blocks = self._find_side_blocks(blocks_group)

                    if side_blocks and self.side_fail_count >= 2:
                        # Боковой блок пулей не достать (он не на линии ствола)
                        self.side_fail_count = 0
                        self.start_recovery()
                        return

                    if side_blocks:
                        self.side_fail_count += 1
                        _bx, _by, side_dir = random.choice(side_blocks)

                        if self.intelligence >= 0.6:
                            # Высокий интеллект
                            saved = self.direction
                            self.set_direction(side_dir, collision_group)
                            did_move = self.move_step(collision_group)

                            if did_move:
                                # Успешно сдвинулись - теперь стреляем в исходном
                                self.set_direction(saved, collision_group)
                                self.is_side_clearing     = True
                                self.side_clear_timer     = self.side_clear_duration
                                self.side_clear_saved_dir = saved
                                self._try_shoot(bullets_group, all_sprites_group)
                            else:
                                # Боком не пробраться (стена / другой танк)
                                self._try_shoot(bullets_group, all_sprites_group)
                                self.set_direction(saved, collision_group)
                        else:
                            # Средний интеллект
                            self.set_direction(side_dir, collision_group)
                            self._try_shoot(bullets_group, all_sprites_group)

                        self.stuck_timer = 0
                        self.move_timer  = random.randint(self.move_time_min,
                                                           self.move_time_max)
                        return

                # Базовый уход в сторону
                side_chance = 0.3 + self.intelligence * 0.4
                if random.random() < side_chance:
                    avail    = self.get_available_directions(collision_group)
                    backward = _REVERSE.get(self.direction)
                    sides    = [d for d in avail
                                if d != self.direction and d != backward]
                    if sides:
                        self.set_direction(random.choice(sides), collision_group)
                        self.stuck_timer = 0

                # Полное застревание -> разворот и recovery
                if self.stuck_timer >= self.stuck_threshold:
                    self.start_recovery()

            else:
                self.stuck_timer = 0
                self.side_fail_count = 0

        self.move_timer = random.randint(self.move_time_min, self.move_time_max)

    def _try_shoot(self, bullets_group, all_sprites_group) -> bool:
        # Выстрел с обычной перезарядкой: пока она не прошла - выстрела нет
        if self.reload_ms > 0 and self.reload_timer > 0:
            return False
        self.shoot(bullets_group, all_sprites_group)
        self.reload_timer = self.reload_ms
        return True

    def shoot(self, bullets_group, all_sprites_group) -> None:
        b = Bullet(self, self.direction, assets.PIXEL_IMG_RAW, is_player=False, custom_color=self.bullet_color)
        bullets_group.add(b)
        all_sprites_group.add(b)

    def start_recovery(self) -> None:
        self.is_recovering     = True
        self.recovery_timer    = self.recovery_duration
        self.stuck_timer       = 0
        self.set_direction(_REVERSE.get(self.direction, DIR_DOWN))

    def choose_smart_random_direction(self, collision_group) -> None:
        avail = self.get_available_directions(collision_group)
        if avail:
            backward = _REVERSE.get(self.direction)
            sides    = [d for d in avail if d != self.direction and d != backward]
            self.set_direction(
                random.choice(sides) if sides else random.choice(avail),
                collision_group,
            )
        else:
            self.set_direction(random.choice(_ALL_DIRS), collision_group)

    def get_available_directions(self, collision_group) -> list:
        return [
            d for d in _ALL_DIRS
            if self.can_move_to(
                self.grid_x + d[0], self.grid_y + d[1], collision_group
            )
        ]
