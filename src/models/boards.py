# Модели игровых полей (NORMAL/ALT/OKAK), модель HUD


def generate_blocks_from_model(model: list[str], block_class, start_gx: int, start_gy: int) -> list:
    blocks = []
    for row_idx, row in enumerate(model):
        for col_idx, char in enumerate(row):
            if char in (' ', '.', '\n'):
                continue

            blocks.append(block_class(start_gx + col_idx, start_gy + row_idx))
    return blocks

NORMAL_BOARD_MODEL = [
    "XXXXXXXXXX",
    "XXXXXXXXXX",
    "XXXXXXXXXX",
    "XXXXXXXXXX",
    "XXXXXXXXXX",
    "XXXXXXXXXX",
    "XXXXXXXXXX",
    "XXXXXXXXXX",
    "XXXXXXXXXX",
    "XXXXXXXXXX",
    "XXXXXXXXXX",
    "XXXXXXXXXX",
    "XXXXXXXXXX",
    "XXXXXXXXXX",
    "XXXXXXXXXX",
    "XXXXXXXXXX",
    "XXXXXXXXXX",
    "XXXXXXXXXX",
    "XXXXXXXXXX",
    "XXXXXXXXXX"
]

ALT_BOARD_MODEL = ["X" * 20 for _ in range(20)]

DOZA_BOARD_MODEL = [
    "XXXXXXXXXXXXXXXXXXXX",
    "XXXXXXXXXXXXXXXXXXXX",
    "XXXXXXXXXXXXXXXXXXXX",
    "                 XXX",
    "    XXXXXXXXX    XXX",
    "    XXXXXXXXX    XXX",
    "    XXXXXXXXX    XXX",
    "          XXX    XXX",
    "          XXX    XXX",
    "          XXXXXXXXXX",
    "          XXXXXXXXXX",
    "          XXXXXXXXXX",
]

BOARD_MODELS = {
    "NORMAL": NORMAL_BOARD_MODEL,
    "ALT": ALT_BOARD_MODEL,
    "OKAK": DOZA_BOARD_MODEL,
}

HUD_MODEL = [
    "XXXX",
    "XXXX",
    "XXXX",
    "XXXX"
]

def get_board_model(model_input) -> list[str]:
    if isinstance(model_input, list):
        return model_input
    return BOARD_MODELS.get(model_input, NORMAL_BOARD_MODEL)
