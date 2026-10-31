from core.settings import CELL_SIZE, OFFSET_X, OFFSET_Y

# Добавляем глобальное смещение камеры
camera_offset_x = 0
camera_offset_y = 0

def update_camera(player_pixel_x, player_pixel_y, screen_w, screen_h) -> None:
    global camera_offset_x, camera_offset_y
    # Центрируем камеру на игроке
    camera_offset_x = player_pixel_x - (screen_w // 2)
    camera_offset_y = player_pixel_y - (screen_h // 2)

def get_cell_topleft(gx, gy):
    # Вычитаем позицию камеры из финальных координат
    px = OFFSET_X + gx * CELL_SIZE - camera_offset_x
    py = OFFSET_Y + gy * CELL_SIZE - camera_offset_y
    return px, py

def grid_to_pixel_center(gx, gy):
    px = OFFSET_X + gx * CELL_SIZE + CELL_SIZE // 2
    py = OFFSET_Y + gy * CELL_SIZE + CELL_SIZE // 2
    return px, py

def in_bounds(gx: int, gy: int, board: list[str] = None) -> bool:
    if board is None:
        from core.settings import BOARD_WIDTH, BOARD_HEIGHT
        return 0 <= gx < BOARD_WIDTH and 0 <= gy < BOARD_HEIGHT
    
    rows = len(board)
    cols = len(board[0]) if rows > 0 else 0
    return 0 <= gx < cols and 0 <= gy < rows
