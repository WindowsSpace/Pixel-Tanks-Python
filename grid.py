from settings import CELL_SIZE, OFFSET_X, OFFSET_Y, BOARD_WIDTH, BOARD_HEIGHT

def grid_to_pixel_center(gx, gy):
    # Перевод координат клетки (gx, gy) в пиксели (центр)
    px = OFFSET_X + gx * CELL_SIZE + CELL_SIZE // 2
    py = OFFSET_Y + gy * CELL_SIZE + CELL_SIZE // 2
    return px, py

def in_bounds(gx, gy):
    return 0 <= gx < BOARD_WIDTH and 0 <= gy < BOARD_HEIGHT
