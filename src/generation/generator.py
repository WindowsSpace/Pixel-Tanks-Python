# MapGenerator - генерация карты и расстановка блоков


from typing import Optional
import random

from generation.grid_ops import _bfs_dist, _carve, _center_mask, _largest_component, _rebuild
from generation.params import BlockParams, MapParams, _DIRS4, _NEAR_OFFSETS
from generation.simulation import _open_lanes, _stuck_blocks


# ГЕНЕРАТОР
class MapGenerator:
    # Генератор карт и блоков

    def __init__(self, params: Optional[MapParams] = None, block_params: Optional[BlockParams] = None,
                 shape_library=None) -> None:
        self.p = params or MapParams()
        self.bp = block_params or BlockParams()
        self.shape_library = [list(s) for s in shape_library] if shape_library else []

    @property
    def rng(self):
        # Seed задан - детерминированный генератор, иначе общий random
        if self.p.seed is None:
            return random
        if getattr(self, "_seeded", None) is None or self._seeded[0] != self.p.seed:
            self._seeded = (self.p.seed, random.Random(self.p.seed))
        return self._seeded[1]

    # стили карты
    def _styles(self):
        return {"grid": self._style_grid, "rooms": self._style_rooms, "caves": self._style_caves,
                "open": self._style_open, "scatter": self._style_scatter}

    # фигуры блоков
    def _shape_external(self):
        return list(self.rng.choice(self.shape_library))

    def _block_styles(self):
        # Стили расстановки: {фабрика фигуры: вес}
        s = {
            "singles":   {self._shape_single: 8, self._shape_dotted: 1, self._shape_line: 1},
            "mixed":     {self._shape_single: 5, self._shape_line: 3, self._shape_dotted: 3, self._shape_blob: 3,
                          self._shape_walk: 2, self._shape_solid: 2, self._shape_diag: 1, self._shape_checker: 1,
                          self._shape_ring: 1},
            "airy":      {self._shape_dotted: 4, self._shape_checker: 3, self._shape_blob: 3, self._shape_walk: 3,
                          self._shape_diag: 2, self._shape_single: 3},
            "structure": {self._shape_line: 4, self._shape_solid: 4, self._shape_ring: 3, self._shape_blob: 1,
                          self._shape_single: 1},
        }
        if self.shape_library and self.bp.external_weight > 0:
            for name in ("mixed", "structure"):
                s[name][self._shape_external] = self.bp.external_weight
        return s

    # перенесённые функции
    _SOLID_SHAPES = (
        [(0, 0), (1, 0), (0, 1), (1, 1)],  # 2x2
        [(0, 0), (1, 0), (2, 0), (0, 1)],  # Г
        [(0, 0), (1, 0), (2, 0), (1, 1)],  # Т
        [(1, 0), (0, 1), (1, 1), (2, 1), (1, 2)],  # плюс
        [(0, 0), (1, 0), (1, 1), (2, 1)],  # Z
        [(0, 0), (2, 0), (0, 1), (1, 1), (2, 1)],  # арка
    )

    def _max_corridor(self, w, h):
        return max(self.p.min_corridor, min(self.p.max_corridor, min(w, h) // 3))

    def _corridor_width(self, max_w):
        # Ширина коридора >= 3. Тройка самая частая, широкие - реже
        choices = list(range(self.p.min_corridor, max_w + 1))
        weights = [1.0 / ((k - 2) ** self.p.corridor_bias) for k in choices]
        return self.rng.choices(choices, weights=weights)[0]

    def _strips(self, length, max_w, gap_max):
        # Полосы вдоль одной оси: [(start, end)], ширина каждой >= 3
        res = []
        pos = self.rng.randint(1, 3)
        while True:
            sw = self._corridor_width(max_w)
            if pos + sw > length - 1:
                break
            res.append((pos, pos + sw - 1))
            gap = 0 if self.rng.random() < 0.05 else self.rng.randint(1, gap_max)
            pos += sw + gap
        return res

    def _style_grid(self, g, w, h):
        max_w = self._max_corridor(w, h)
        gap_max = self.rng.randint(*self.p.grid_gap_max)
        vs = self._strips(w, max_w, gap_max)
        hs = self._strips(h, max_w, gap_max)
        partial = self.rng.uniform(*self.p.grid_partial)  # шанс, что полоса короче карты (тупики)

        for (a, b) in vs:
            y0, y1 = 1, h - 2
            if self.rng.random() < partial:
                y0, y1 = self.rng.randint(1, h // 2), self.rng.randint(h // 2, h - 2)
            _carve(g, w, h, a, y0, b, y1)
        for (a, b) in hs:
            x0, x1 = 1, w - 2
            if self.rng.random() < partial:
                x0, x1 = self.rng.randint(1, w // 2), self.rng.randint(w // 2, w - 2)
            _carve(g, w, h, x0, a, x1, b)

        # Случайно перекрываем участки между перекрёстками - получается лабиринт
        p_cut = self.rng.uniform(*self.p.grid_cut)
        for (xa, xb) in vs:
            for i in range(len(hs) - 1):
                y0, y1 = hs[i][1] + 1, hs[i + 1][0] - 1
                if y0 <= y1 and self.rng.random() < p_cut:
                    _carve(g, w, h, xa, y0, xb, y1, False)
        for (ya, yb) in hs:
            for i in range(len(vs) - 1):
                x0, x1 = vs[i][1] + 1, vs[i + 1][0] - 1
                if x0 <= x1 and self.rng.random() < p_cut:
                    _carve(g, w, h, x0, ya, x1, yb, False)

    def _l_corridor(self, g, w, h, p1, p2, cw):
        # Г-образный коридор шириной cw между двумя точками
        (x1, y1), (x2, y2) = p1, p2
        lo = cw // 2
        hi = cw - lo - 1
        if self.rng.random() < 0.5:
            _carve(g, w, h, min(x1, x2), y1 - lo, max(x1, x2), y1 + hi)
            _carve(g, w, h, x2 - lo, min(y1, y2), x2 + hi, max(y1, y2))
        else:
            _carve(g, w, h, x1 - lo, min(y1, y2), x1 + hi, max(y1, y2))
            _carve(g, w, h, min(x1, x2), y2 - lo, max(x1, x2), y2 + hi)

    def _style_rooms(self, g, w, h):
        max_w = self._max_corridor(w, h)
        max_room_w = max(4, min(w // 2, self.p.room_max))
        max_room_h = max(4, min(h // 2, self.p.room_max))
        n = max(3, (w * h) // self.rng.randint(*self.p.rooms_area_div))
        centers = []
        for _ in range(n * 3):
            if len(centers) >= n:
                break
            rw = self.rng.randint(3, max_room_w)
            rh = self.rng.randint(3, max_room_h)
            if w - 1 - rw < 1 or h - 1 - rh < 1:
                continue
            x = self.rng.randint(1, w - 1 - rw)
            y = self.rng.randint(1, h - 1 - rh)
            _carve(g, w, h, x, y, x + rw - 1, y + rh - 1)
            centers.append((x + rw // 2, y + rh // 2))

        if len(centers) < 2:
            return
        self.rng.shuffle(centers)
        for i in range(len(centers) - 1):
            self._l_corridor(g, w, h, centers[i], centers[i + 1], self._corridor_width(max_w))
        for _ in range(self.rng.randint(0, len(centers) // 2)):  # лишние связи -> петли
            a, b = self.rng.sample(centers, 2)
            self._l_corridor(g, w, h, a, b, self._corridor_width(max_w))

    def _style_caves(self, g, w, h):
        s = self.rng.choices([1, 2, 3], weights=list(self.p.cave_scale_weights))[0]  # масштаб "зерна"
        cw, ch = max(4, w // s), max(4, h // s)
        fill = self.rng.uniform(*self.p.cave_fill)
        c = [[self.rng.random() < fill for _ in range(cw)] for _ in range(ch)]
        for _ in range(self.rng.randint(*self.p.cave_iterations)):
            n = [[False] * cw for _ in range(ch)]
            for y in range(1, ch - 1):
                for x in range(1, cw - 1):
                    cnt = sum(c[y + dy][x + dx] for dy in (-1, 0, 1) for dx in (-1, 0, 1))
                    n[y][x] = cnt >= 5
            c = n
        for y in range(ch):
            for x in range(cw):
                if c[y][x]:
                    _carve(g, w, h, x * s, y * s, x * s + s - 1, y * s + s - 1)

    def _style_open(self, g, w, h):
        m = self.rng.randint(*self.p.open_margin)
        _carve(g, w, h, m, m, w - 1 - m, h - 1 - m)
        n = max(2, (w * h) // self.rng.randint(*self.p.open_area_div))
        for _ in range(n):
            rw = self.rng.randint(1, self.rng.choice([2, 4, 8]))
            rh = self.rng.randint(1, self.rng.choice([2, 4, 8]))
            x = self.rng.randint(2, max(2, w - 3 - rw))
            y = self.rng.randint(2, max(2, h - 3 - rh))
            _carve(g, w, h, x, y, x + rw - 1, y + rh - 1, False)

    def _style_scatter(self, g, w, h):
        n = max(4, (w * h) // self.rng.randint(*self.p.scatter_area_div))
        for _ in range(n):
            rw = self.rng.randint(3, max(3, min(self.p.scatter_max_size, w - 3)))
            rh = self.rng.randint(3, max(3, min(self.p.scatter_max_size, h - 3)))
            x = self.rng.randint(1, max(1, w - 1 - rw))
            y = self.rng.randint(1, max(1, h - 1 - rh))
            _carve(g, w, h, x, y, x + rw - 1, y + rh - 1)

    def _build_layout(self, w, h):
        g = [[False] * w for _ in range(h)]
        names = [n for n, wt in self.p.style_weights.items() if wt > 0 and (n == "mixed" or n in self._styles())] or ["grid"]
        style = self.rng.choices(names, weights=[self.p.style_weights.get(n, 1) for n in names])[0]
        if style == "mixed":
            parts = self.rng.sample(["grid", "rooms", "caves", "scatter"], self.rng.choice([2, 2, 3]))
        else:
            parts = [style]
        for p in parts:
            self._styles()[p](g, w, h)
        return g, "+".join(parts)

    def _pick_spawns(self, comp, center, w, h, enemies_count):
        player = self.rng.choice(comp)
        dist = _bfs_dist(center, player, w, h)
        maxd = max(dist.values())
        min_d = min(self.p.spawn_min_distance_cap, max(6, maxd // 2))
        far = [c for c, d in dist.items() if d >= min_d]
        if not far:
            far = [c for c, d in dist.items() if c != player] or [player]

        def man(a, b):
            return abs(a % w - b % w) + abs(a // w - b // w)

        spawns = []
        for _ in range(enemies_count):
            pool = self.rng.sample(far, min(30, len(far)))
            # берём точку, максимально удалённую от уже выбранных
            best = max(pool, key=lambda c: min([man(c, s) for s in spawns] + [man(c, player)]))
            spawns.append(best)
        return player, spawns

    def generate_level(self, width: int, height: int, enemies_count: int = 3, debug: bool = False):
        # Возвращает
        width, height = max(width, 9), max(height, 9)
        need = max(enemies_count + 1, 12)
        min_cells = max(need * 2, int((width - 2) * (height - 2) * self.p.min_floor_fraction))

        best = None
        style_used = "?"
        for _ in range(self.p.max_attempts):
            g, style = self._build_layout(width, height)
            center = _center_mask(g, width, height)
            comp = _largest_component(center, width, height)
            if best is None or len(comp) > len(best[0]):
                best, style_used = (comp, style), style
            if len(comp) >= min_cells:
                break
        comp = best[0] if best else []

        if len(comp) < need:  # запасной вариант - пустая арена
            g = [[False] * width for _ in range(height)]
            _carve(g, width, height, 1, 1, width - 2, height - 2)
            center = _center_mask(g, width, height)
            comp = _largest_component(center, width, height)
            style_used = "arena(fallback)"

        floor, center = _rebuild(comp, width, height)
        player, spawns = self._pick_spawns(comp, center, width, height, enemies_count)

        board = [''.join('X' if floor[y * width + x] else ' ' for x in range(width))
                 for y in range(height)]
        player_spawn = (player % width, player // width)
        enemy_spawns = [(s % width, s // width) for s in spawns]

        if debug:
            print(f"\n-- карта {width}x{height}, стиль: {style_used} --")
            for row in board:
                print(row)
            print(f"Игрок: {player_spawn} | Враги: {enemy_spawns}\n")
        return board, player_spawn, enemy_spawns

    def _shape_single(self):
        return [(0, 0)]

    def _shape_line(self):
        n = self.rng.randint(2, 7)
        step = self.rng.choice([1, 1, 1, 2, 2, 3])  # 2 -> блок через клетку, 3 -> через две
        return [(i * step, 0) for i in range(n)]

    def _shape_dotted(self):
        x, cells = 0, []
        for _ in range(self.rng.randint(3, 8)):
            cells.append((x, 0))
            x += 1 + self.rng.choice([0, 0, 1, 1, 2])  # случайные промежутки 0-2 клетки
        return cells

    def _shape_blob(self):
        w, h = self.rng.randint(2, 5), self.rng.randint(2, 5)
        p = self.rng.uniform(0.4, 0.85)
        cells = [(x, y) for y in range(h) for x in range(w) if self.rng.random() < p]
        return cells or [(0, 0)]

    def _shape_checker(self):
        w, h = self.rng.randint(2, 5), self.rng.randint(2, 5)
        return [(x, y) for y in range(h) for x in range(w) if (x + y) % 2 == 0]

    def _shape_diag(self):
        n = self.rng.randint(2, 6)
        step = self.rng.choice([1, 1, 2])
        return [(i * step, i * step) for i in range(n)]

    def _shape_walk(self):
        x = y = 0
        cells = [(0, 0)]
        for _ in range(self.rng.randint(3, 9)):
            dx, dy = self.rng.choice(_DIRS4)
            k = self.rng.choice([1, 1, 2])  # прыжок на 2 -> пустая клетка между блоками
            x, y = x + dx * k, y + dy * k
            cells.append((x, y))
        return cells

    def _shape_ring(self):
        n = self.rng.randint(3, 5)
        cells = [(x, y) for y in range(n) for x in range(n) if x in (0, n - 1) or y in (0, n - 1)]
        for _ in range(self.rng.randint(0, 3)):  # выбиваем пару клеток -> "дырявая" рамка
            if len(cells) > 3:
                cells.remove(self.rng.choice(cells))
        return cells

    def _shape_solid(self):
        return list(self.rng.choice(self._SOLID_SHAPES))

    def _random_density(self):
        # Число блоков заметно варьируется: от почти пусто до плотно
        if self.bp.fixed_density is not None:
            return self.bp.fixed_density * self.bp.density_scale
        ranges = self.bp.density_ranges  # [(вес, (мин, макс)), ...]
        weights = [wt for wt, _ in ranges]
        _, (lo, hi) = self.rng.choices(ranges, weights=weights)[0]
        return self.rng.uniform(lo, hi) * self.bp.density_scale

    def _transform(self, shape):
        if self.rng.random() < 0.5:
            shape = [(y, x) for x, y in shape]  # поворот/отражение по диагонали
        if self.rng.random() < 0.5:
            shape = [(-x, y) for x, y in shape]
        if self.rng.random() < 0.5:
            shape = [(x, -y) for x, y in shape]
        return shape

    def generate_blocks(self, board, player_spawn, enemy_spawns, density=None):
        # Возвращает список клеток [(x, y), ...] для разрушаемых блоков F02
        h = len(board)
        w = len(board[0])
        N = w * h
        floor = bytearray(N)
        for y, row in enumerate(board):
            for x, ch in enumerate(row):
                if ch == 'X':
                    floor[y * w + x] = 1
        center = _center_mask([[bool(floor[y * w + x]) for x in range(w)] for y in range(h)], w, h)

        spawns = [player_spawn] + list(enemy_spawns)
        start = player_spawn[1] * w + player_spawn[0]
        forbid = set()
        for sx, sy in spawns:
            for dy in range(-self.bp.spawn_clear_radius, self.bp.spawn_clear_radius + 1):
                for dx in range(-self.bp.spawn_clear_radius, self.bp.spawn_clear_radius + 1):
                    x, y = sx + dx, sy + dy
                    if 0 <= x < w and 0 <= y < h:
                        forbid.add(y * w + x)

        floor_idx = [i for i in range(N) if floor[i]]
        center_idx = [i for i in floor_idx if center[i] and i not in forbid]
        any_idx = [i for i in floor_idx if i not in forbid]
        if not any_idx:
            return []

        if density is None:
            density = self._random_density()
        target = max(int(len(floor_idx) * density), min(self.bp.min_blocks, len(floor_idx) // 8))
        target = min(self.bp.max_blocks, max(1, target))

        styles = self._block_styles()
        names = [n for n in styles if self.bp.style_weights.get(n, 0) > 0] or ["mixed"]
        style = self.rng.choices(names, weights=[self.bp.style_weights.get(n, 1) for n in names])[0]
        makers = list(styles[style])
        maker_w = [styles[style][m] for m in makers]

        taken = set()
        taken_list = []  # тот же набор, но со случайным доступом

        def try_place():
            shape = self._transform(self.rng.choices(makers, weights=maker_w)[0]())
            # Якорь: рядом с уже стоящим блоком (через клетку) или в случайном месте
            if taken and self.rng.random() < self.bp.near_chance:
                b0 = self.rng.choice(taken_list)
                ox, oy = self.rng.choice(_NEAR_OFFSETS)
                ax, ay = b0 % w + ox, b0 // w + oy
            else:
                pool = center_idx if (center_idx and self.rng.random() < self.bp.center_chance) else any_idx
                a = self.rng.choice(pool)
                ax, ay = a % w, a // w
            cells = []
            for dx, dy in shape:
                x, y = ax + dx, ay + dy
                if not (0 <= x < w and 0 <= y < h):
                    continue  # часть фигуры за краем - просто обрезаем
                i = y * w + x
                if floor[i] and i not in forbid and i not in taken:
                    cells.append(i)
            return cells

        for _ in range(self.bp.rounds):
            tries = 0
            while len(taken) < target and tries < target * 4 + 20:
                tries += 1
                cells = try_place()
                if cells:
                    taken.update(cells)
                    taken_list.extend(cells)
                    if len(taken) > target:  # не перебираем цель сильнее чем на одну фигуру
                        break

            blk = bytearray(N)
            for i in taken:
                blk[i] = 1
            stuck = _stuck_blocks(w, h, floor, center, blk, start)
            if not stuck:
                if len(taken) >= target:
                    break
                continue
            taken.difference_update(stuck)  # убираем только неразрушимые клетки
            taken_list[:] = list(taken)

        blk = bytearray(N)
        for i in taken:
            blk[i] = 1
        targets = [e[1] * w + e[0] for e in enemy_spawns]
        _open_lanes(w, h, center, blk, start, targets)

        return [(i % w, i // w) for i in range(N) if blk[i]]


# СОВМЕСТИМОСТЬ: функции с настройками по умолчанию
def generate_random_level(width: int, height: int, enemies_count: int = 3, debug: bool = False):
    return MapGenerator().generate_level(width, height, enemies_count, debug)


def generate_random_blocks(board, player_spawn, enemy_spawns, density=None, max_blocks=None, rounds=None):
    gen = MapGenerator()
    if max_blocks is not None:
        gen.bp.max_blocks = max_blocks
    if rounds is not None:
        gen.bp.rounds = rounds
    return gen.generate_blocks(board, player_spawn, enemy_spawns, density)


# САМОПРОВЕРКА
if __name__ == "__main__":
    import time
    gen = MapGenerator()
    for _ in range(6):
        w, h = random.randint(15, 100), random.randint(15, 64)
        t0 = time.time()
        board, ps, es = gen.generate_level(w, h, 5)
        t1 = time.time()
        blocks = gen.generate_blocks(board, ps, es)
        t2 = time.time()
        print(f"{w}x{h}: map {t1 - t0:.2f}s, blocks {len(blocks)} in {t2 - t1:.2f}s")
