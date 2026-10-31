# Чёрный босс режима D01: полностью чёрная копия танка игрока

import random

import pygame

from core import assets
from core.settings import DIR_DOWN, DIR_LEFT, DIR_RIGHT, DIR_TO_ANGLE, DIR_UP
from entities.bullet import Bullet, BeamCell
from entities.tank.enemy import EnemyTank

# НАСТРОЙКИ
CALM = dict(aggressiveness=0.55, intelligence=0.5, patrol_chance=0.15,
            move_time_min=480, move_time_max=850,
            shoot_time_min=1700, shoot_time_max=3200)
CALM_VOLLEY_CHANCE = 0.18  # шанс, что очередной выстрел окажется залпом

# Поведение, когда у игрока последняя жизнь (вторая фаза)
ENRAGED = dict(aggressiveness=0.70, intelligence=0.6, patrol_chance=0.08,
               move_time_min=360, move_time_max=650,
               shoot_time_min=1100, shoot_time_max=2300)
ENRAGED_VOLLEY_CHANCE = 0.35
RICOCHET_ENRAGED = True  # пули второй фазы один раз отскакивают от края поля

VOLLEY_SIZE = 4  # пуль в залпе (как у игрока)
VOLLEY_GAP_MS = 110  # пауза между пулями залпа по умолчанию
VOLLEY_GAP_BEAT = 0.5  # доля бита между пулями залпа (при 150 BPM ~ 200 мс)

# Уход за край
HIDE_ENABLED = True  # False - босс всегда на поле
FIELD_TIME_MS = (9000, 14000)  # сколько босс ездит по полю (уязвим) между уходами
FIELD_TIME_ENRAGED_MS = (6000, 9000)
HIDDEN_DISTANCE = 3  # центр босса за краем поля, в клетках от края (без окон ОС)
HIDDEN_DISTANCE_WINDOWS = 7  # то же с окнами ОС: дальше
HIDDEN_TIME_MS = (5000, 7000)  # сколько сидит за краем и стреляет оттуда (неуязвим)
HIDDEN_TIME_ENRAGED_MS = (6000, 8500)
BLINK_MS = 700  # мигание при уходе и возвращении
TELEGRAPH_MS = 650  # предупреждение (мигает край) перед выстрелом из-за края
SHOT_GAP_MS = (800, 1400)  # пауза между выстрелами из-за края
SHOT_GAP_ENRAGED_MS = (500, 900)

# Две механики "за краем"
HIDDEN_WINDOW_CHANCE = 0.5  # шанс выбрать window, когда окна ОС доступны
WALL_COUNT_WEIGHTS = {1: 0.35, 2: 0.30, 3: 0.25, 4: 0.10}  # соло / дуо / трио / квартет
WALL_COUNT_WEIGHTS_ENRAGED = {1: 0.20, 2: 0.30, 3: 0.30, 4: 0.20}
WALL_SIMULTANEOUS_CHANCE = 0.45  # иначе - по очереди
WALL_STAGGER_MS = 450  # пауза между очередными стрелками
WALL_LANE_JITTER = 2  # у всех, кроме первого, ряд сдвигается на +-N
WINDOW_STEP_MS = 65  # скорость окна-босса: клетка за шаг
WINDOW_AIM_PAUSE_MS = (90, 220)  # пауза "прицелиться" (без предупреждения для игрока)

# Вторая фаза: атака ЛИНИЯМИ - через всё поле, мгновенно, ломают блоки
BEAM_ENABLED = True
BEAM_COOLDOWN_MS = (6500, 10500)  # пауза между атаками линиями
BEAM_COUNT_WEIGHTS = {1: 0.5, 2: 0.35, 3: 0.15}
BEAM_TELEGRAPH_MS = 1300
BEAM_TTL_MS = 260  # сколько луч держится

# Интро (пока играет BossIntro): босс медленно выходит из-за края поля
INTRO_TARGET_Y = 3  # клетка, до которой босс доходит
INTRO_START_OUT = 2  # на сколько клеток за краем стартует
INTRO_MIN_STEP_MS = 350  # быстрее шагать не будет, даже если интро-музыка короткая
SPAWN_GRACE_MS = 1500  # после возрождения игрока босс столько времени не стреляет
_SIDES = {  # сторона: (направление пуль внутрь поля)
    "L": DIR_RIGHT, "R": DIR_LEFT, "T": DIR_DOWN, "B": DIR_UP,
}


class BlackBoss(EnemyTank):
    is_boss = True

    def __init__(self, gx, gy, base_image=None, hp=16, max_hp=None) -> None:
        if base_image is None:
            # форма - как у танка игрока сейчас (в том числе кастомного), клетки - чёрные
            base_image = assets.make_black_copy(assets.PLAYER_BASE_IMG)
        super().__init__(gx, gy, base_image, hp=hp, max_hp=max_hp if max_hp else hp, **CALM)

        self.bullet_color = (0, 0, 0)  # пули босса - чёрные
        self.reload_ms = 0  # у босса свои залпы, обычная перезарядка врагов не нужна
        self.bullet_bounces = 0
        self.volley_chance = CALM_VOLLEY_CHANCE
        self.burst_left = 0
        self.burst_timer = 0
        self.burst_dir = self.direction
        self.burst_origin = None
        self.burst_outside = False
        self.enraged = False

        # уход за край
        self.state = "FIELD"  # FIELD | LEAVE | HIDDEN | RETURN
        self.state_timer = random.randint(*FIELD_TIME_MS)
        self.side = "L"
        self.lane = 1
        self.telegraphing = False
        self.tele_timer = 0
        self.shot_timer = 0
        self._blank = None
        self.os_windows = False  # режим включает: босс и пули показываются окнами ОС
        self.hidden_dist = HIDDEN_DISTANCE

        # за краем: тип механики и состояние
        self.hidden_kind = "wall"  # wall | window
        self.shots = []  # wall: активные "стрелки"
        self.ring = []  # window: клетки кольца вокруг поля
        self.ring_idx = 0
        self.ring_target = 0
        self.ring_timer = 0
        self.ring_wait = 0
        self.win_face = DIR_DOWN

        # интро
        self.intro = None  # None | "first" (сверху) | "last"
        self.intro_timer = 0
        self.intro_step_ms = 700
        self.intro_target = (gx, gy)
        self.grace_ms = 0  # пока > 0, босс не стреляет
        self.shielded = True  # пока игрок не собрал все цвета, босса нельзя ранить
        self.volley_gap = VOLLEY_GAP_MS
        self.locked = False  # финал: босс заперт в поле 4x4, только ездит/крутится
        self.lock_field = None
        self.lock_timer = 0
        self.vanish = False  # финальный взрыв: танк больше не рисуется
        self.beams = []  # план линий: {"axis": "row"|"col", "idx": int, "tele": ms}
        self.beam_cd = 4000

    @property
    def invulnerable(self) -> bool:
        return self.intro is not None or self.shielded or self.locked

    def lock_at(self, gx, gy, field=None) -> None:
        # Финал: босс заперт в маленьком поле (4x4), дрожит
        self.locked = True
        self.intro = None
        self.state = "FIELD"
        self.burst_left, self.beams, self.shots = 0, [], []
        self.lock_field = field
        self.lock_timer = random.randint(500, 900)
        self.grid_x, self.grid_y = gx, gy
        self._face(DIR_DOWN)
        self.update_position()

    def _locked_wander(self, dt_ms) -> None:
        # Запертый босс изредка поворачивается или делает шаг внутри поля
        self.lock_timer -= dt_ms
        if self.lock_timer > 0:
            return
        self.lock_timer = random.randint(450, 1000)
        d = random.choice((DIR_UP, DIR_DOWN, DIR_LEFT, DIR_RIGHT))
        if random.random() < 0.5 or self.lock_field is None:
            self._face(d)  # просто повернулся
            return
        x0, y0, w, h = self.lock_field  # танк 3x3: центр не ближе 1 клетки к краю поля
        nx, ny = self.grid_x + d[0], self.grid_y + d[1]
        self._face(d)
        if x0 + 1 <= nx <= x0 + w - 2 and y0 + 1 <= ny <= y0 + h - 2:
            self.grid_x, self.grid_y = nx, ny
            self.update_position()

    def set_tempo(self, beat_ms) -> None:
        # Темп музыки: пули залпа летят не в упор, а с паузой в долю бита
        self.volley_gap = max(160, int(beat_ms * VOLLEY_GAP_BEAT))

    def _bullet_color(self):
        return self.bullet_color

    # фазы
    def set_enraged(self, enraged: bool) -> None:
        # Включает/выключает вторую фазу
        if enraged == self.enraged:
            return
        self.enraged = enraged
        params = ENRAGED if enraged else CALM
        self.aggressiveness = params["aggressiveness"]
        self.intelligence = params["intelligence"]
        self.move_time_min, self.move_time_max = params["move_time_min"], params["move_time_max"]
        self.shoot_time_min, self.shoot_time_max = params["shoot_time_min"], params["shoot_time_max"]
        self.volley_chance = ENRAGED_VOLLEY_CHANCE if enraged else CALM_VOLLEY_CHANCE
        self.bullet_bounces = 1 if (enraged and RICOCHET_ENRAGED) else 0

    # интро
    def _face(self, direction) -> None:
        # Поворот без проверки стен
        self.direction = direction
        self.angle = DIR_TO_ANGLE[direction]
        self.update_image()

    def begin_intro(self, variant, step_ms, bw, bh) -> None:
        # Босс стартует за краем поля и по клетке выходит к своей позиции
        tx, ty = bw // 2, INTRO_TARGET_Y
        self.intro, self.intro_timer = variant, 0
        self.intro_step_ms = max(INTRO_MIN_STEP_MS, int(step_ms))
        self.intro_target = (tx, ty)
        self.burst_left = 0
        self.telegraphing = False
        self.state, self.state_timer = "FIELD", self._field_time()
        if variant == "last":  # другая сценка: выезжает сбоку, мигая
            self.grid_x, self.grid_y = -INTRO_START_OUT, ty
            self._face(DIR_RIGHT)
        else:  # обычная: медленно сверху
            self.grid_x, self.grid_y = tx, -INTRO_START_OUT
            self._face(DIR_DOWN)
        self.update_position()

    def finish_intro(self) -> None:
        # Конец интро: босс встаёт на место
        if self.intro is None:
            return
        self.intro = None
        self.grid_x, self.grid_y = self.intro_target
        self._face(DIR_DOWN)
        self.update_position()
        self.state, self.state_timer = "FIELD", self._field_time()

    def _intro_ai(self, dt_ms) -> None:
        self.intro_timer += dt_ms
        tx, ty = self.intro_target
        while self.intro_timer >= self.intro_step_ms and (self.grid_x, self.grid_y) != (tx, ty):
            self.intro_timer -= self.intro_step_ms
            if self.grid_x != tx:
                self.grid_x += 1 if tx > self.grid_x else -1
            elif self.grid_y != ty:
                self.grid_y += 1 if ty > self.grid_y else -1
            self.update_position()
        if (self.grid_x, self.grid_y) == (tx, ty):
            self.finish_intro()
        elif self.intro == "last":
            self._blink((int(self.intro_timer) // 90) % 4 != 0)  # мерцание

    # стрельба
    def _fire(self, direction, bullets_group, all_sprites_group, origin=None, outside=False) -> None:
        b = Bullet(self, direction, assets.PIXEL_IMG_RAW, is_player=False, custom_color=self._bullet_color())
        b.bounces_left = self.bullet_bounces
        if origin is not None:  # выстрел из-за края: пуля стартует в клетке на краю поля
            b.grid_x, b.grid_y = origin
            b.update_position()
        b.outside = bool(outside)  # летит снаружи поля (окно ОС) - пока не влетит внутрь
        bullets_group.add(b)
        all_sprites_group.add(b)

    def shoot(self, bullets_group, all_sprites_group) -> None:
        if self.intro is not None or self.grace_ms > 0:
            return
        self._fire(self.direction, bullets_group, all_sprites_group)
        if self.burst_left == 0 and random.random() < self.volley_chance:
            self.burst_left = VOLLEY_SIZE - 1  # остальные пули залпа вылетят в update_ai
            self.burst_timer = self.volley_gap
            self.burst_dir = self.direction  # залп летит туда, куда смотрел танк при первом выстреле
            self.burst_origin = None
            self.burst_outside = False

    # уход за край
    def _dims(self):
        b = self.board
        return (len(b[0]), len(b)) if b else None

    def _field_time(self):
        return random.randint(*(FIELD_TIME_ENRAGED_MS if self.enraged else FIELD_TIME_MS))

    def _blink(self, on: bool) -> None:
        # Мигание: в "выключенные" моменты танк невидим (картинка прозрачная)
        self.update_image()
        if not on:
            if self._blank is None or self._blank.get_size() != self.image.get_size():
                self._blank = pygame.Surface(self.image.get_size(), pygame.SRCALPHA)
            self.image = self._blank

    def _begin_leave(self) -> None:
        dims = self._dims()
        if dims is None:
            self.state_timer = 2000
            return
        bw, bh = dims
        dist = {"L": self.grid_x, "R": bw - 1 - self.grid_x, "T": self.grid_y, "B": bh - 1 - self.grid_y}
        self.side = min(dist, key=dist.get)  # уходим к ближайшему краю
        self.state, self.state_timer = "LEAVE", BLINK_MS
        self.burst_left = 0
        self.shots = []
        self.beams = []

    def _go_hidden(self) -> None:
        bw, bh = self._dims()
        self.lane = max(1, min((bh if self.side in ("L", "R") else bw) - 2,
                               self.grid_y if self.side in ("L", "R") else self.grid_x))  # ряд, из которого ушли
        self.hidden_kind = "window" if (self.os_windows and random.random() < HIDDEN_WINDOW_CHANCE) else "wall"
        dist = HIDDEN_DISTANCE_WINDOWS if self.hidden_kind == "window" else HIDDEN_DISTANCE
        self.hidden_dist = dist
        outside = {"L": (-dist, self.grid_y), "R": (bw - 1 + dist, self.grid_y),
                   "T": (self.grid_x, -dist), "B": (self.grid_x, bh - 1 + dist)}
        self.grid_x, self.grid_y = outside[self.side]
        self.update_image()
        self.update_position()
        self.state = "HIDDEN"
        self.state_timer = random.randint(*(HIDDEN_TIME_ENRAGED_MS if self.enraged else HIDDEN_TIME_MS))
        self.shot_timer = 700
        self.telegraphing = False
        self.burst_left = 0
        self.shots = []
        if self.hidden_kind == "window":
            self._build_ring(bw, bh, dist)
            self.ring_idx = self.ring_target = self._ring_index(self.side, self.lane)
            self.ring_wait = random.randint(*WINDOW_AIM_PAUSE_MS)
            self._ring_place()

    def _edge_cell(self, lane, side=None):
        bw, bh = self._dims()
        return {"L": (0, lane), "R": (bw - 1, lane), "T": (lane, 0), "B": (lane, bh - 1)}[side or self.side]

    def _aim_lane(self, player, side=None) -> int:
        bw, bh = self._dims()
        if (side or self.side) in ("L", "R"):
            return max(1, min(bh - 2, player.grid_y))
        return max(1, min(bw - 2, player.grid_x))

    # wall: пули вылетают из стен
    def _plan_wall_attack(self, player) -> None:
        weights = WALL_COUNT_WEIGHTS_ENRAGED if self.enraged else WALL_COUNT_WEIGHTS
        n = random.choices(list(weights), weights=list(weights.values()))[0]
        sides = random.sample(["L", "R", "T", "B"], n)
        together = random.random() < WALL_SIMULTANEOUS_CHANCE
        bw, bh = self._dims()
        for i, side in enumerate(sides):
            lane = self._aim_lane(player, side)
            if i > 0:
                span = bh if side in ("L", "R") else bw
                lane = max(1, min(span - 2, lane + random.randint(-WALL_LANE_JITTER, WALL_LANE_JITTER)))
            self.shots.append({"side": side, "lane": lane, "wait": 0 if together else i * WALL_STAGGER_MS,
                               "tele": TELEGRAPH_MS, "burst": 0, "burst_t": 0, "fired": False})

    def _update_wall(self, dt_ms, player, bullets_group, all_sprites_group) -> None:
        for sh in list(self.shots):
            if sh["fired"]:  # залп: остальные пули из той же стены
                if sh["burst"] > 0:
                    sh["burst_t"] -= dt_ms
                    if sh["burst_t"] <= 0:
                        self._fire(_SIDES[sh["side"]], bullets_group, all_sprites_group, self._edge_cell(sh["lane"], sh["side"]), False)
                        sh["burst"] -= 1
                        sh["burst_t"] = self.volley_gap
                else:
                    self.shots.remove(sh)
                continue
            if sh["wait"] > 0:
                sh["wait"] -= dt_ms
                continue
            sh["tele"] -= dt_ms
            if sh["tele"] <= 0:
                self._fire(_SIDES[sh["side"]], bullets_group, all_sprites_group, self._edge_cell(sh["lane"], sh["side"]), False)
                sh["fired"] = True
                if random.random() < self.volley_chance:
                    sh["burst"], sh["burst_t"] = VOLLEY_SIZE - 1, self.volley_gap
        self.telegraphing = any(not sh["fired"] and sh["wait"] <= 0 for sh in self.shots)

    # window: босс-окно ездит вокруг поля
    def _build_ring(self, bw, bh, d) -> None:
        x0, x1, y0, y1 = -d, bw - 1 + d, -d, bh - 1 + d
        ring = [(x, y0) for x in range(x0, x1 + 1)]
        ring += [(x1, y) for y in range(y0 + 1, y1 + 1)]
        ring += [(x, y1) for x in range(x1 - 1, x0 - 1, -1)]
        ring += [(x0, y) for y in range(y1 - 1, y0, -1)]
        self.ring = ring

    def _ring_index(self, side, lane) -> int:
        bw, bh = self._dims()
        d = self.hidden_dist
        cell = {"L": (-d, lane), "R": (bw - 1 + d, lane), "T": (lane, -d), "B": (lane, bh - 1 + d)}[side]
        return self.ring.index(cell)

    def _ring_face(self, cell):
        # Куда смотрит босс в клетке кольца: у сторон - внутрь поля, на углах
        bw, bh = self._dims()
        x, y = cell
        if 0 <= x < bw and y < 0:
            return DIR_DOWN
        if 0 <= x < bw and y >= bh:
            return DIR_UP
        if 0 <= y < bh and x < 0:
            return DIR_RIGHT
        if 0 <= y < bh and x >= bw:
            return DIR_LEFT
        dx, dy = (bw - 1) / 2 - x, (bh - 1) / 2 - y
        if abs(dx) >= abs(dy):
            return DIR_RIGHT if dx > 0 else DIR_LEFT
        return DIR_DOWN if dy > 0 else DIR_UP

    def _ring_place(self) -> None:
        cell = self.ring[self.ring_idx]
        self.win_face = self._ring_face(cell)
        self._face(self.win_face)
        self.grid_x, self.grid_y = cell
        self.update_position()

    def _pick_ring_target(self, player) -> None:
        sides = ["L", "R", "T", "B"]
        cur = self._ring_side(self.ring[self.ring_idx])
        if cur in sides and random.random() < 0.75:
            sides.remove(cur)  # чаще всего - на другую сторону (с разъездом по углу)
        side = random.choice(sides)
        lane = self._aim_lane(player, side)
        bw, bh = self._dims()
        span = bh if side in ("L", "R") else bw
        lane = max(1, min(span - 2, lane + random.choice((0, 0, 0, -1, 1))))
        self.ring_target = self._ring_index(side, lane)
        self.side, self.lane = side, lane

    def _ring_side(self, cell):
        bw, bh = self._dims()
        x, y = cell
        if 0 <= x < bw and y < 0:
            return "T"
        if 0 <= x < bw and y >= bh:
            return "B"
        if 0 <= y < bh and x < 0:
            return "L"
        if 0 <= y < bh and x >= bw:
            return "R"
        return None

    def _update_window(self, dt_ms, player, bullets_group, all_sprites_group) -> None:
        n = len(self.ring)
        if self.ring_idx != self.ring_target:
            self.ring_timer += dt_ms
            while self.ring_timer >= WINDOW_STEP_MS and self.ring_idx != self.ring_target:
                self.ring_timer -= WINDOW_STEP_MS
                fwd = (self.ring_target - self.ring_idx) % n
                self.ring_idx = (self.ring_idx + (1 if fwd <= n - fwd else -1)) % n
                self._ring_place()
            return
        self.ring_timer = 0
        self.ring_wait -= dt_ms
        if self.ring_wait > 0 or self.burst_left > 0:
            return
        if self.state_timer <= 0:
            return
        # на месте: стреляем (без предупреждения), затем едем к новой точке
        cell = self.ring[self.ring_idx]
        direction = self.win_face
        vec = {DIR_UP: (0, -1), DIR_DOWN: (0, 1), DIR_LEFT: (-1, 0), DIR_RIGHT: (1, 0)}[direction]
        origin = (cell[0] + 2 * vec[0], cell[1] + 2 * vec[1])
        self._fire(direction, bullets_group, all_sprites_group, origin, True)
        if random.random() < self.volley_chance:
            self.burst_left, self.burst_timer = VOLLEY_SIZE - 1, self.volley_gap
            self.burst_dir, self.burst_origin, self.burst_outside = direction, origin, True
        gap = SHOT_GAP_ENRAGED_MS if self.enraged else SHOT_GAP_MS
        self.ring_wait = random.randint(*gap) * 0.5
        self._pick_ring_target(player)

    def _hidden_ai(self, dt_ms, player, bullets_group, all_sprites_group) -> None:
        self.state_timer -= dt_ms
        if self.hidden_kind == "window":
            self._update_window(dt_ms, player, bullets_group, all_sprites_group)
            busy = self.burst_left > 0 or self.ring_idx != self.ring_target
        else:
            self._update_wall(dt_ms, player, bullets_group, all_sprites_group)
            if not self.shots:
                self.shot_timer -= dt_ms
                if self.shot_timer <= 0 and self.state_timer > TELEGRAPH_MS + 2 * WALL_STAGGER_MS:
                    self._plan_wall_attack(player)
                    gap = SHOT_GAP_ENRAGED_MS if self.enraged else SHOT_GAP_MS
                    self.shot_timer = random.randint(*gap)
            busy = bool(self.shots)
        if self.state_timer <= 0 and not busy:
            if self.hidden_kind == "window":
                side = self._ring_side(self.ring[self.ring_idx])
                if side is None:  # стоим на углу - доезжаем до ближайшей стороны
                    self.ring_idx = (self.ring_idx + 1) % len(self.ring)
                    self._ring_place()
                    return
                self.side = side
                bw, bh = self._dims()
                cx, cy = self.ring[self.ring_idx]
                self.lane = max(1, min((bh if side in ("L", "R") else bw) - 2, cy if side in ("L", "R") else cx))
            self._begin_return(player)

    def _begin_return(self, player, collision_group=None) -> None:
        # Выезд обратно на поле: ищем свободное место у того же края
        bw, bh = self._dims()
        lane0 = self._aim_lane(player)
        entry = {"L": lambda l: (1, l), "R": lambda l: (bw - 2, l), "T": lambda l: (l, 1), "B": lambda l: (l, bh - 2)}[self.side]
        span = (bh if self.side in ("L", "R") else bw)
        old = (self.grid_x, self.grid_y)
        for off in sorted(range(-(span // 2), span // 2 + 1), key=abs):
            gx, gy = entry(max(1, min(span - 2, lane0 + off)))
            self.grid_x, self.grid_y = gx, gy
            self.update_position()
            self.set_direction(_SIDES[self.side])  # лицом внутрь поля (поворот сам подвинет, если не влезает)
            if self.can_move_to(self.grid_x, self.grid_y, self._obstacles):
                self.state, self.state_timer = "RETURN", BLINK_MS
                return
        self.grid_x, self.grid_y = old  # места нет - ещё немного посидим за краем и попробуем снова
        self.update_position()
        self.state_timer = 400

    def ghost_center(self):
        # Центр клетки, где босс стоит за краем и виден окном ОС
        if self.state != "HIDDEN" or self.hidden_kind != "window" or not self.ring:
            return None
        return self.ring[self.ring_idx]

    def window_image(self):
        # Картинка босса для окна ОС: лицом туда, куда он сейчас смотрит
        cached = getattr(self, "_win_img", None)
        if cached is None or cached[0] != self.win_face:
            cached = (self.win_face, pygame.transform.rotate(self.base_image, DIR_TO_ANGLE[self.win_face]))
            self._win_img = cached
        return cached[1]

    def lurk_cells(self):
        # Клетки с предупреждением (мигают): край поля перед выстрелом из стены
        cells = []
        dims = self._dims()
        if dims is not None:
            bw, bh = dims
            for bm in self.beams:
                if (int(bm["tele"]) // 110) % 2 == 0:
                    continue
                if bm["axis"] == "row":
                    cells += [(x, bm["idx"]) for x in range(bw)]
                else:
                    cells += [(bm["idx"], y) for y in range(bh)]
        if self.state != "HIDDEN" or self.hidden_kind != "wall":
            return cells
        for sh in self.shots:
            if sh["fired"] or sh["wait"] > 0:
                continue
            if (int(sh["tele"]) // 100) % 2 == 0:
                continue
            cells += [self._edge_cell(l, sh["side"]) for l in (sh["lane"] - 1, sh["lane"], sh["lane"] + 1)]
        return cells

    # Атака линиями (вторая фаза)
    def _plan_beams(self, player) -> None:
        bw, bh = self._dims()
        n = random.choices(list(BEAM_COUNT_WEIGHTS), weights=list(BEAM_COUNT_WEIGHTS.values()))[0]
        used = set()
        for i in range(n):
            axis = random.choice(("row", "col"))
            span = bh if axis == "row" else bw
            if i == 0:  # первая линия бьёт в игрока
                idx = player.grid_y if axis == "row" else player.grid_x
            else:
                idx = random.randint(1, span - 2)
            idx = max(1, min(span - 2, idx))
            if any(a == axis and abs(idx - j) < 3 for a, j in used):
                continue  # линии не слипаются в сплошную стену
            used.add((axis, idx))
            self.beams.append({"axis": axis, "idx": idx, "tele": BEAM_TELEGRAPH_MS})

    def _update_beams(self, dt_ms, player, bullets_group, all_sprites_group) -> None:
        if not self.beams:
            self.beam_cd -= dt_ms
            if self.beam_cd <= 0 and self.enraged and BEAM_ENABLED and self.grace_ms <= 0:
                self._plan_beams(player)
            return
        bw, bh = self._dims()
        for bm in list(self.beams):
            bm["tele"] -= dt_ms
            if bm["tele"] > 0:
                continue
            cells = [(x, bm["idx"]) for x in range(bw)] if bm["axis"] == "row" else [(bm["idx"], y) for y in range(bh)]
            for x, y in cells:
                beam = BeamCell(x, y, BEAM_TTL_MS)
                bullets_group.add(beam)
                all_sprites_group.add(beam)
            self.beams.remove(bm)
        if not self.beams:
            self.beam_cd = random.randint(*BEAM_COOLDOWN_MS)

    # ИИ
    def update_ai(self, dt_ms, player, collision_group, bullets_group, all_sprites_group,
                  speed_mult=1.0, blocks_group=None) -> None:
        self._obstacles = collision_group

        if self.locked:  # финал: заперт в поле, "сбоит" мерцанием, ездит и крутится
            if self.vanish:  # взрыв: босс исчез под анимацией
                self.update_image()
                if self._blank is None or self._blank.get_size() != self.image.get_size():
                    self._blank = pygame.Surface(self.image.get_size(), pygame.SRCALPHA)
                self.image = self._blank
                return
            self._locked_wander(dt_ms)
            self._blink(not (random.random() < 0.12))
            return
        if self.intro is not None:  # интро: только выход из-за края, без атак
            self._intro_ai(dt_ms)
            return
        if self.grace_ms > 0:
            self.grace_ms = max(0, self.grace_ms - dt_ms)

        if self.burst_left > 0:  # залп: остальные пули
            self.burst_timer -= dt_ms
            if self.burst_timer <= 0:
                self._fire(self.burst_dir, bullets_group, all_sprites_group, self.burst_origin, self.burst_outside)
                self.burst_left -= 1
                self.burst_timer = self.volley_gap

        if not HIDE_ENABLED or not self.board:
            super().update_ai(dt_ms, player, collision_group, bullets_group, all_sprites_group, speed_mult, blocks_group)
            return

        if self.state == "FIELD":
            self.state_timer -= dt_ms
            self._update_beams(dt_ms, player, bullets_group, all_sprites_group)
            super().update_ai(dt_ms, player, collision_group, bullets_group, all_sprites_group, speed_mult, blocks_group)
            if self.state_timer <= 0:
                self._begin_leave()
        elif self.state == "LEAVE":
            self.state_timer -= dt_ms
            self._blink((int(self.state_timer) // 100) % 2 == 1)
            if self.state_timer <= 0:
                self._go_hidden()
        elif self.state == "HIDDEN":
            self._hidden_ai(dt_ms, player, bullets_group, all_sprites_group)
        elif self.state == "RETURN":
            self.state_timer -= dt_ms
            self._blink((int(self.state_timer) // 100) % 2 == 1)
            if self.state_timer <= 0:
                self.update_image()
                self.state, self.state_timer = "FIELD", self._field_time()
