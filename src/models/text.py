# Цифры и буквы пиксельным шрифтом, анимированный текст


import pygame

from core.settings import CELL_SIZE
from models.tanks import generate_model_surface


NUMBER_MODELS = {
    '0': [
        "XXX",
        "X X",
        "X X",
        "X X",
        "XXX",
    ],
    '1': [
        " X ",
        "XX ",
        " X ",
        " X ",
        "XXX",
    ],
    '2': [
        'XXX',
        '  X',
        'XXX',
        'X  ',
        'XXX',
    ],
    '3': [
        'XXX',
        '  X',
        'XXX',
        '  X',
        'XXX',
    ],
    '4': [
        'X X',
        'X X',
        'XXX',
        '  X',
        '  X',
    ],
    '5': [
        'XXX',
        'X  ',
        'XXX',
        '  X',
        'XXX',
    ],
    '6': [
        'XXX',
        'X  ',
        'XXX',
        'X X',
        'XXX',
    ],
    '7': [
        'XXX',
        '  X',
        '  X',
        '  X',
        '  X',
    ],
    '8': [
        'XXX',
        'X X',
        'XXX',
        'X X',
        'XXX',
    ],
    '9': [
        'XXX',
        'X X',
        'XXX',
        '  X',
        'XXX',
    ]
}

LETTER_MODELS = {
    'A': [
        [
            " XXX ",
            "X   X",
            "XXXXX",
            "X   X",
            "X   X",
        ],
        [
            " XXX ",
            "X   X",
            "XXXXX",
            "X   X",
            "X   X",
        ],
        [
            '  X  ',
            ' X X ',
            ' XXX ',
            ' X X ',
            ' X X ',
        ],
        [
            '  X  ',
            '  X  ',
            '  X  ',
            '  X  ',
            '  X  ',
        ],
    ],
    'B': [
        [
            "XXXX ", 
            "X   X", 
            "XXXX ", 
            "X   X", 
            "XXXX ",
        ],
        [
            "XXXX ", 
            "X   X", 
            "XXXX ", 
            "X   X", 
            "XXXX ",
        ],
        [
            " XXX ", 
            " X X ", 
            " XXX ", 
            " X X ",
            " XXX ",
        ],
        [
            '  X  ',
            '  X  ',
            '  X  ',
            '  X  ',
            '  X  ',
        ],
        [
            " XXX ", 
            " X X ", 
            " XXX ", 
            " X X ",
            " XXX ",
        ],
        [
            " XXXX", 
            "X   X", 
            " XXXX", 
            "X   X", 
            " XXXX",
        ],
        [
            " XXXX", 
            "X   X", 
            " XXXX", 
            "X   X", 
            " XXXX",
        ],
    ],
    'C': [
        [
            ' XXXX',
            'X    ',
            'X    ',
            'X    ',
            ' XXXX',
        ],
        [
            ' XXXX',
            'X    ',
            'X    ',
            'X    ',
            ' XXXX',
        ],
        [
            ' XXX ',
            ' X   ',
            ' X   ',
            ' X   ',
            ' XXX ',
        ],
        [
            '  X  ',
            '  X  ',
            '  X  ',
            '  X  ',
            '  X  ',
        ],
        [
            ' XXX ',
            '   X ',
            '   X ',
            '   X ',
            ' XXX ',
        ],
        [
            'XXXX ',
            '    X',
            '    X',
            '    X',
            'XXXX '
        ],        [
            'XXXX ',
            '    X',
            '    X',
            '    X',
            'XXXX ',
        ],
    ],
    'D': [
        [
            'XXXX ',
            ' X  X',
            ' X  X',
            ' X  X',
            'XXXX ',
        ],
        [
            'XXXX ',
            ' X  X',
            ' X  X',
            ' X  X',
            'XXXX ',
        ],
        [
            ' XXX ',
            ' X X ',
            ' X X ',
            ' X X ',
            ' XXX ',
        ],
        [
            '  X  ',
            '  X  ',
            '  X  ',
            '  X  ',
            '  X  ',
        ],
        [
            ' XXX ',
            ' X X ',
            ' X X ',
            ' X X ',
            ' XXX ',
        ],
        [
            ' XXXX',
            'X  X ',
            'X  X ',
            'X  X ',
            ' XXXX',
        ],
        [
            ' XXXX',
            'X  X ',
            'X  X ',
            'X  X ',
            ' XXXX',
        ],
    ],
    'E': [
        [
            'XXXXX',
            'X    ',
            'XXXX ',
            'X    ',
            'XXXXX',      
        ],
        [
            'XXXXX',
            'X    ',
            'XXXX ',
            'X    ',
            'XXXXX',      
        ],
        [
            ' XXX ',
            ' X   ',
            ' XXX ',
            ' X   ',
            ' XXX ',
        ],
        [
            '  X  ',
            '  X  ',
            '  X  ',
            '  X  ',
            '  X  ',
        ],
        [
            ' XXX ',
            '   X ',
            ' XXX ',
            '   X ',
            ' XXX ',
        ],
        [
            'XXXXX',
            '    X',
            ' XXXX',
            '    X',
            'XXXXX',
        ],
        [
            'XXXXX',
            '    X',
            ' XXXX',
            '    X',
            'XXXXX',
        ],
    ],
    'F': [
        [
            'XXXXX',
            'X    ',
            'XXXX ',
            'X    ',
            'X    ',      
        ],
        [
            'XXXXX',
            'X    ',
            'XXXX ',
            'X    ',
            'X    ',      
        ],
        [
            ' XXX ',
            ' X   ',
            ' XXX ',
            ' X   ',
            ' X   ',
        ],
        [
            '  X  ',
            '  X  ',
            '  X  ',
            '  X  ',
            '  X  ',
        ],
        [
            ' XXX ',
            '   X ',
            ' XXX ',
            '   X ',
            '   X ',
        ],
        [
            'XXXXX',
            '    X',
            ' XXXX',
            '    X',
            '    X',
        ],
        [
            'XXXXX',
            '    X',
            ' XXXX',
            '    X',
            '    X',
        ],
    ]
}

def generate_animated_text(text: str, color_or_image, spacing_cells: int = 1) -> list[pygame.Surface]:
    char_sequences = []
    
    for char in text.upper():
        if char in NUMBER_MODELS:
            seq = [NUMBER_MODELS[char]]
        elif char in LETTER_MODELS:
            seq = LETTER_MODELS[char]
        else:
            seq = []
        char_sequences.append(seq)
        
    max_frames = max((len(seq) for seq in char_sequences if seq), default=1)
    
    animated_surfaces = []
    spacing_pixels = spacing_cells * CELL_SIZE
    
    for frame_idx in range(max_frames):
        char_surfaces = []
        
        for seq in char_sequences:
            if not seq:
                char_surfaces.append(pygame.Surface((3 * CELL_SIZE, 0), pygame.SRCALPHA))
                continue
            
            actual_frame_idx = min(frame_idx, len(seq) - 1)
            model_frame = seq[actual_frame_idx]
            
            char_surfaces.append(generate_model_surface(model_frame, color_or_image))
            
        total_width = sum(surf.get_width() for surf in char_surfaces) + spacing_pixels * max(0, len(char_surfaces) - 1)
        max_height = max((surf.get_height() for surf in char_surfaces), default=0)
        
        composite_surf = pygame.Surface((total_width, max_height), pygame.SRCALPHA)
        current_x = 0
        for surf in char_surfaces:
            composite_surf.blit(surf, (current_x, 0))
            current_x += surf.get_width() + spacing_pixels
            
        animated_surfaces.append(composite_surf)
        
    return animated_surfaces
