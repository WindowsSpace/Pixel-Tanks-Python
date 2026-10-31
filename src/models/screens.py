# Модели экранов: взрыв, победа, настройки


EXPLOSION_MODELS = [
    [
        'X  X',
        ' XX ',
        ' XX ',
        'X  X',
    ],
    [
        ' XX ',
        'X  X',
        'X  X',
        ' XX ',
    ]
]

WIN_MODEL = [
    "X   X",
    "X   X",
    "X X X",
    "XX XX",
    "X   X",
    '     ',
    ' XXX ',
    '  X  ',
    '  X  ',
    '  X  ',
    ' XXX ',
    '     ',
    'X   X',
    'XX  X',
    'X X X',
    'X  XX',
    'X   X',
]

ALT_WIN_MODEL = [
    "X   X XXX X   X",
    "X   X  X  XX  X",
    "X X X  X  X X X",
    "XX XX  X  X  XX",
    "X   X XXX X   X"
]

WIN_MODELS = {
    "NORMAL": WIN_MODEL,
    "ALT": ALT_WIN_MODEL,
}

def get_win_model(model_input) -> list[str]:
    if isinstance(model_input, list):
        return model_input
    return WIN_MODELS.get(model_input, WIN_MODEL)

SETTINGS_MODEL = [
    '    XX    ',
    ' XX XX XX ',
    ' XXX  XXX ',
    '  X    X  ',
    'XX  XX  XX',
    'XX  XX  XX',
    '  X    X  ',
    ' XXX  XXX ',
    ' XX XX XX ',
    '    XX    '
]
