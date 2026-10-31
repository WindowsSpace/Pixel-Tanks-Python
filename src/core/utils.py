import random
def level_to_int(value, default=None):
    # Номер уровня из любого значения: 3 -> 3, "3" -> 3
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        v = value.strip().lstrip('+')
        if v.isdigit():
            return int(v)
    return default
def generate_lives_positions(lives_count):
    positions = [(x, y) for x in range(4) for y in range(4)]
    return random.sample(positions, min(lives_count, 16))
def is_cell_walkable(board: list, x: int, y: int) -> bool:
    # Можно ли занять клетку (x, y) карты. Выход за карту = стена
    if y < 0 or y >= len(board):
        return False
    row_data = board[y]
    if x < 0 or x >= len(row_data):
        return False
    cell_val = row_data[x]
    # Непроходимой клеткой считаем 1, '1', ' ' или '#'
    if cell_val in (1, '1', ' ', '#') or (isinstance(cell_val, int) and cell_val != 0):
        return False
    return True
def is_area_walkable(gx: int, gy: int, width_cells: int, height_cells: int, board: list) -> bool:
    # Прямоугольная область целиком проходима
    for cy in range(height_cells):
        for cx in range(width_cells):
            if not is_cell_walkable(board, gx + cx, gy + cy):
                return False
    return True
def are_cells_walkable(board: list, gx: int, gy: int, cells) -> bool:
    # Проходимы ли клетки (dx, dy) относительно центра (gx, gy)
    for dx, dy in cells:
        if not is_cell_walkable(board, gx + dx, gy + dy):
            return False
    return True

def get_random_spawn_points(board_model: list[str], count: int) -> list[tuple[int, int]]:
    empty_cells = []
    for y, row in enumerate(board_model):
        for x, char in enumerate(row):
            if char == " ":
                empty_cells.append((x, y))
                
    # Выбираем случайные уникальные клетки из пустых
    if len(empty_cells) < count:
        return empty_cells
    return random.sample(empty_cells, count)

def find_explosion_spot(board: list, gx: int, gy: int, size: int = 4):
    # Куда поставить анимацию взрыва игрока
    base_x, base_y = gx - size // 2, gy - size // 2
    cx, cy = gx + 0.5, gy + 0.5
    best, best_key = [], None
    radius = size + 4
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            tx, ty = base_x + dx, base_y + dy
            walls = sum(1 for yy in range(ty, ty + size) for xx in range(tx, tx + size)
                        if not is_cell_walkable(board, xx, yy))
            dist = (tx + size / 2 - cx) ** 2 + (ty + size / 2 - cy) ** 2
            key = (walls, round(dist, 3))
            if best_key is None or key < best_key:
                best_key, best = key, [(tx, ty)]
            elif key == best_key:
                best.append((tx, ty))
    return random.choice(best)
