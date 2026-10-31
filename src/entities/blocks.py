import pygame
import random
from core import assets
from core import settings
from core.grid import get_cell_topleft

# Фигуры блоков
BLOCK_SHAPES:list[list[tuple[int, int]]] = [
    [(0, 0), (1, 0), (0, 1), (1, 1)],  # Квадрат 2x2
    [(0, 0), (1, 0), (2, 0)],  # Горизонтальная линия 1x3
    [(0, 0), (0, 1), (0, 2)],  # Вертикальная линия 3x1
    [(0, 0), (1, 0), (2, 0), (1, 1)],  # Т-образная
    [(0, 0), (0, 1), (0, 2), (1, 2)],  # L-образная
    [(0, 0), (1, 0), (1, 1), (2, 1)],  # Z-образная
    [(1, 0), (0, 1), (1, 1), (2, 1), (1, 2)],  # Плюс
    [(0, 0), (2, 0), (0, 1), (1, 1), (2, 1)],  # U-образная арка
    [(0, 0), (1, 1), (2, 2)]  # Диагональ
]

class PixelBlock(pygame.sprite.Sprite):
    def __init__(self, gx, gy) -> None:
        super().__init__()
        self.image = assets.PIXEL_IMG_RAW
        self.rect = self.image.get_rect()
        self.hitbox = self.rect.copy()
        self.grid_x = gx
        self.grid_y = gy
        self.update_position()

    def update_position(self) -> None:
        tx, ty = get_cell_topleft(self.grid_x, self.grid_y)
        
        self.rect.x = tx + (settings.CELL_SIZE - self.rect.width) // 2
        self.rect.y = ty + (settings.CELL_SIZE - self.rect.height) // 2
        
        self.hitbox.center = self.rect.center

class BlackBlock(PixelBlock):
    # Настоящий блок (его можно расстрелять), перекрашенный в чёрный
    def __init__(self, gx, gy) -> None:
        super().__init__(gx, gy)
        if assets.BLACK_CELL_IMG is not None:
            self.image = assets.BLACK_CELL_IMG


_color_cell_cache: dict = {}


def color_cell_image(color):
    # Клетка заданного цвета: цветная подложка и тёмный пиксель сверху
    key = tuple(color)
    img = _color_cell_cache.get(key)
    if img is None:
        img = pygame.Surface(assets.PIXEL_IMG_RAW.get_size(), pygame.SRCALPHA)
        if assets.PIXEL_COLOR_IMG_RAW is not None:
            img.blit(assets.colorize_icon(assets.PIXEL_COLOR_IMG_RAW, (*key, 255)), (0, 0))
        img.blit(assets.PIXEL_IMG_RAW, (0, 0))
        _color_cell_cache[key] = img
    return img


class ColorBlock(PixelBlock):
    # Цветной блок-"бонус" (D01): безопасен для игрока, проходим для танков

    BLINK_MS = 2500

    def __init__(self, gx, gy, color, ttl_ms=14000) -> None:
        super().__init__(gx, gy)
        self.color = tuple(color)
        self.ttl = ttl_ms
        self._img = color_cell_image(self.color)
        self.image = self._img
        self._blank = pygame.Surface(self._img.get_size(), pygame.SRCALPHA)

    def tick(self, dt_ms) -> bool:
        # Возвращает False, когда блок истёк
        self.ttl -= dt_ms
        if self.ttl <= 0:
            return False
        blinking = self.ttl < self.BLINK_MS and (int(self.ttl) // 120) % 2 == 0
        self.image = self._blank if blinking else self._img
        return True


def _spawn_random_clusters(state, board_width, board_height, num_clusters) -> None:
    # Случайные кластеры по ВСЕМУ полю
    scale = float(getattr(settings, "RANDOM_CLUSTERS_SCALE", 1.0))
    count = int(round(num_clusters * scale))
    if count <= 0 or board_width < 6 or board_height < 6:
        return
    enemy_r = int(getattr(settings, "RANDOM_CLUSTERS_SAFE_RADIUS", 2))
    player_r = int(getattr(settings, "RANDOM_CLUSTERS_PLAYER_SAFE_RADIUS", 0))
    enemy_pts = set(map(tuple, getattr(settings, "ENEMY_SPAWN_POINTS", [])))
    player_pts = set(map(tuple, getattr(settings, "PLAYER_SPAWN_POINTS", []))) - enemy_pts
    occupied = {(b.grid_x, b.grid_y) for b in state["blocks"]}

    cur = state.get("player") if hasattr(state, "get") else None
    cur_pos = (cur.grid_x, cur.grid_y) if cur is not None and hasattr(cur, "grid_x") else None

    def forbidden_cells(er, pr):
        bad = set()
        if cur_pos is not None:  # там, где игрок стоит прямо сейчас, блоков нет (радиус 2)
            for dy in range(-er, er + 1):
                for dx in range(-er, er + 1):
                    bad.add((cur_pos[0] + dx, cur_pos[1] + dy))
        for pts, r in ((enemy_pts, er), (player_pts, pr)):
            for sx, sy in pts:
                for dy in range(-r, r + 1):
                    for dx in range(-r, r + 1):
                        bad.add((sx + dx, sy + dy))
        return bad

    # от строгих настроек к мягким: если места почти нет, всё равно ставим
    levels = [(enemy_r, player_r)]
    for er, pr in ((max(enemy_r - 1, 1), max(player_r - 1, 0)), (1, 0), (0, 0)):
        if (er, pr) not in levels:
            levels.append((er, pr))

    for _ in range(count):
        placed = False
        for er, pr in levels:
            bad = forbidden_cells(er, pr)
            candidates = []
            for shape in random.sample(BLOCK_SHAPES, len(BLOCK_SHAPES)):
                for _try in range(25):
                    base_x = random.randint(2, board_width - 3)
                    base_y = random.randint(2, board_height - 3)
                    cells = [(base_x + dx, base_y + dy) for dx, dy in shape]
                    if any(not (0 < x < board_width - 1 and 0 < y < board_height - 1) for x, y in cells):
                        continue
                    if any(c in occupied or c in bad for c in cells):
                        continue
                    candidates.append(cells)
                    break
                if len(candidates) >= 6:
                    break
            if not candidates:
                continue
            for x, y in random.choice(candidates):
                block = PixelBlock(x, y)
                state["blocks"].add(block)
                state["all_sprites"].add(block)
                occupied.add((x, y))
            placed = True
            break
        if not placed:
            break


def spawn_blocks(state, board_width, board_height, num_clusters = 0, fixed_coords = None, custom_shapes = None) -> None:
    if custom_shapes:
        for item in custom_shapes:
            shape = item["shape"]
            base_x = item["x"]
            base_y = item["y"]
            
            for dx, dy in shape:
                b_x = base_x + dx
                b_y = base_y + dy
                
                # Базовая проверка, чтобы блок не нарисовался за пределами экрана
                if 0 <= b_x < board_width and 0 <= b_y < board_height:
                    block = PixelBlock(b_x, b_y)
                    state["blocks"].add(block)
                    state["all_sprites"].add(block)

    # 2. Случайные кластеры блоков
    if num_clusters > 0 and BLOCK_SHAPES and getattr(settings, "RANDOM_CLUSTERS_ENABLED", True):
        _spawn_random_clusters(state, board_width, board_height, num_clusters)

    tanks = []
    if "player" in state and state["player"].alive():
        tanks.append(state["player"])
    if "enemies" in state:
        tanks.extend(list(state["enemies"]))

    for b in state["blocks"]:
        if not hasattr(b, 'mask') or b.mask is None:
            b.mask = pygame.mask.from_surface(b.image)

    for tank in tanks:
        tank.update_position()
        if not hasattr(tank, 'mask') or tank.mask is None:
            tank.mask = pygame.mask.from_surface(tank.image)

        has_collision = False
        for b in state["blocks"]:
            if pygame.sprite.collide_mask(tank, b):
                has_collision = True
                break

        if has_collision:
            new_x, new_y = find_nearest_empty_cell(tank, board_width, board_height, state["blocks"], tanks)
            tank.grid_x, tank.grid_y = new_x, new_y
            tank.update_position()

def spawn_cells(state, cells, board_width, board_height) -> None:
    # Создаёт блоки на заданных клетках [(x, y), ...] через общий spawn_blocks
    if not cells:
        return
    spawn_blocks(
        state, board_width, board_height,
        custom_shapes=[{"shape": [(0, 0)], "x": x, "y": y} for x, y in cells],
    )

def find_nearest_empty_cell(tank, width, height, blocks_group, tanks):
    queue = [(tank.grid_x, tank.grid_y)]
    visited = set([(tank.grid_x, tank.grid_y)])
    directions = [(0, 1), (1, 0), (0, -1), (-1, 0), (1, 1), (-1, -1), (1, -1), (-1, 1)]

    # Создаем временную группу препятствий (все блоки + все другие живые танки)
    obstacles = pygame.sprite.Group()
    obstacles.add(*blocks_group)
    for t in tanks:
        if t is not tank and t.alive():
            obstacles.add(t)

    # Гарантируем наличие масок у всех препятствий для корректного рассчета
    for sprite in obstacles:
        if not hasattr(sprite, 'mask') or sprite.mask is None:
            sprite.mask = pygame.mask.from_surface(sprite.image)

    while queue:
        cx, cy = queue.pop(0)
        
        if tank.can_move_to(cx, cy, obstacles):
            return cx, cy

        for dx, dy in directions:
            nx, ny = cx + dx, cy + dy
            # в пределах игрового поля
            if 1 <= nx < width - 1 and 1 <= ny < height - 1 and (nx, ny) not in visited:
                visited.add((nx, ny))
                queue.append((nx, ny))
                
    return tank.grid_x, tank.grid_y  # Возвращаем исходную точку в крайнем случае