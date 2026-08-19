import pygame
from settings import CELL_SIZE

PLAYER_MODEL:list[str] = [
    " X ",
    "XXX",
    "XXX"
]

ENEMY_MODEL:list[str] = [
    " X ",
    "XXX",
    "X X"
]

DEFAULT_BOSS_MODELS:dict[str, list[str]] = {
    "idle": [
        "   X   ",
        "X XXX X",
        " X X X ",
        "  X X  ",
        "XXX XXX",
        "  XXX  ",
        "XX X XX"
    ],
    "left0": [
        "   X   ",
        "X XXX  ",
        " X X X ",
        "  X X  ",
        "XXX XX ",
        "  XXX  ",
        "XX X X "
    ],
    "left1": [
        "   X   ",
        "X XXX  ",
        " X X   ",
        "  X X  ",
        "XXX X  ",
        "  XXX  ",
        "XX X   "
    ],
    "right0": [
        "   X   ",
        "  XXX X",
        " X X X ",
        "  X X  ",
        " XX XXX",
        "  XXX  ",
        " X X XX"
    ],
    "right1": [
        "   X   ",
        "  XXX X",
        "   X X ",
        "  X X  ",
        "  X XXX",
        "  XXX  ",
        "   X XX"
    ]
}

def generate_model_surface(model_matrix, color_or_image = None) -> pygame.Surface:
    height_cells = len(model_matrix)
    width_cells = len(model_matrix[0]) if height_cells > 0 else 0
    
    surface_width = width_cells * CELL_SIZE
    surface_height = height_cells * CELL_SIZE
    surface = pygame.Surface((surface_width, surface_height), pygame.SRCALPHA)
    
    default_color = (0, 0, 0)
    for row_idx, row in enumerate(model_matrix):
        for col_idx, char in enumerate(row):
            # Если символ 'X' (или любой другой, кроме пробела/точки) — рисуем блок
            if char in (' ', '.', '\n'):
                continue
                
            x = col_idx * CELL_SIZE
            y = row_idx * CELL_SIZE
            
            if isinstance(color_or_image, pygame.Surface):
                surface.blit(color_or_image, (x, y))
            else:
                color = color_or_image if isinstance(color_or_image, tuple) else default_color
                rect = pygame.Rect(x, y, CELL_SIZE, CELL_SIZE)
                pygame.draw.rect(surface, color, rect)
                
    return surface

def generate_states_surfaces(models_dict, color_or_image = None) -> dict:
    # Принимает словарь текстовых матриц
    surfaces_dict = {}
    for state_name, matrix in models_dict.items():
        surface = generate_model_surface(matrix, color_or_image)
        surfaces_dict[state_name] = surface
    return surfaces_dict