from modes.base_mode import BaseMode

import random
import settings
import json
from settings import BOARD_WIDTH, BOARD_HEIGHT, DIR_UP, DIR_LEFT, DIR_RIGHT
from blocks import spawn_blocks
from save_load import save_game, load_game
from tank import DefaultBoss

class ModeD01(BaseMode):
    TARGET_KILLS:int = 1
    def __init__(self, game_state) -> None:
        super().__init__(game_state)
        self.mode_id = "D01"


# ==========================================
# РЕЖИМ D - 02 (Плейсхолдер 2)
# ==========================================
class ModeD02(BaseMode):
    TARGET_KILLS:int = 1
    def __init__(self, game_state) -> None:
        super().__init__(game_state)
        self.mode_id = "D02"