from modes.base_mode import BaseMode

import random
from core import settings
from entities.blocks import spawn_cells, BLOCK_SHAPES
from generation import MapGenerator, MapParams, BlockParams, pick_respawn_point


class ModeF01(BaseMode):
    # Случайная карта БЕЗ разрушаемых блоков (только стены-пустоты)
    TARGET_KILLS: int = 5

    # Лимиты генерации
    MIN_SIZE: int = 15
    MAX_SIZE: int = 100
    MAX_AREA: int = 100 * 100
    MAX_LEVELS: int = 1

    # к общим настройкам, которые можно менять по уровням
    LEVEL_OPTIONS = BaseMode.LEVEL_OPTIONS + ("map_params", "block_params")

    def __init__(self, game_state) -> None:
        super().__init__(game_state)
        self.mode_id = "F01"
        self.target_kills = self.TARGET_KILLS

        # Настройки этого режима (общий список - в BaseMode.__init__)
        self.board_mode = "DYNAMIC"  # "CLASSIC" | "CENTER" | "TRIMMED" | "DYNAMIC"
        self.hud = "ON"  # "ON" | "OFF" | "WINDOWS" | "OS_WINDOWS"
        self.hp_style = "4x4"  # "4x4" | "1x16" | "2x8" | "3x6" (динамически) | своя модель
        self.hp_fill = "scatter"  # "gauge" (шкала) | "scatter"
        self.os_borderless = True  # True - окна HUD без рамки ОС (для hud = "OS_WINDOWS")
        self.os_window_icons = {}  # например {"HP": "assets/hp.png", "*": "assets/icon.png"}
        self.skip_win_screen = True  # True - после победы сразу занавес и меню, без экрана WIN
        self.level_label = "MAZE"  # текст вместо номера уровня (None - показывать номер)
        self.start_lives = 4  # жизней со старта (например 8 или 10)
        self.save_map = True  # True - карта (и блоки) сохраняется вместе с игрой

        # Параметры генерации карты и блоков
        self.map_params = MapParams()
        self.block_params = BlockParams()  # сколько блоков: density_scale / density_ranges / min_blocks

        # Смена по уровням (нужно MAX_LEVELS > 1). Пример:
        # self.level_overrides = {
        #     1: {"board_mode": "TRIMMED", "hud": "OFF"},
        #     2: {"board_mode": "DYNAMIC", "hud": "WINDOWS", "hp_style": "1x16", "board_size": "random"},
        #     3: {"board_mode": "CENTER", "hud": "OS_WINDOWS", "board_size": (40, 40), "level_label": None,
        #         "map_params": {"style_weights": {"caves": 1}, "max_corridor": 5},     # только указанные поля
        #         "block_params": {"density_scale": 0.8}},
        # }

        self.max_levels = self.MAX_LEVELS
        self.extra_speed = 0.0

        self.is_random_map = True
        self.player_spawn_point = None
        self.enemy_spawn_points = []
        self.board = []
        self.enemies_count = 5

        self.board_width, self.board_height = self._roll_board_size()

    @classmethod
    def _roll_board_size(cls) -> tuple[int, int]:
        # Случайный размер поля: стороны MIN..MAX, но площадь не больше MAX_AREA
        w = random.randint(cls.MIN_SIZE, cls.MAX_SIZE)
        h = random.randint(cls.MIN_SIZE, min(cls.MAX_SIZE, cls.MAX_AREA // w))
        if random.random() < 0.5:  # чтобы карта не была чаще "горизонтальной"
            w, h = h, w
        return w, h

    def setup_level(self, is_new_level: bool = False) -> None:
        # Случайная карта не хранится в сохранении: если её ещё нет
        if not self.board:
            is_new_level = True

        if is_new_level:
            if getattr(self, "is_random_map", False):
                new_map, p_spawn, e_spawns = self.make_generator().generate_level(
                    self.board_width, self.board_height, self.enemies_count
                )
                self.board              = new_map
                self.player_spawn_point = p_spawn
                self.enemy_spawn_points = e_spawns

                # Обновляем settings, пока enemy_manager не сделал следующий тик
                settings.set_enemy_spawn_points(self.enemy_spawn_points)

            # Убираем старые блоки
            for b in list(self.state["blocks"]):
                b.kill()

        super().setup_level(is_new_level)

        player = self.state.get("player")
        if player:
            player.board = self.board
            if is_new_level and getattr(self, "is_random_map", False):
                player.grid_x, player.grid_y = self.player_spawn_point
                player.update_position()

        # Блоки - уже после расстановки игрока (в F01 хук ничего не делает)
        if is_new_level:
            self._populate_blocks()
            self.blocks_generated = True  # карта и блоки созданы: загрузка сохранения их не пересоздаёт

    # Сохранение карты
    def export_map(self):
        # Карта для сохранения игры (если self.save_map включён)
        if not self.board or self.player_spawn_point is None:
            return None
        return {
            "board": list(self.board),
            "player_spawn": list(self.player_spawn_point),
            "enemy_spawns": [list(p) for p in self.enemy_spawn_points],
        }

    def import_map(self, data) -> bool:
        # Возвращает сохранённую карту вместо новой
        try:
            board = [str(r) for r in data["board"]]
            w = len(board[0])
            if not board or w == 0 or any(len(r) != w for r in board):
                return False
            px, py = (int(v) for v in data["player_spawn"])
            enemies = [(int(x), int(y)) for x, y in data["enemy_spawns"]]
            inside = lambda x, y: 0 <= x < w and 0 <= y < len(board) and board[y][x] != " "
            if not inside(px, py) or not all(inside(x, y) for x, y in enemies):
                return False
        except (KeyError, IndexError, TypeError, ValueError):
            return False

        self.board = board
        self.board_width, self.board_height = w, len(board)
        self.player_spawn_point = (px, py)
        self.enemy_spawn_points = enemies
        settings.set_enemy_spawn_points(self.enemy_spawn_points)
        self.blocks_generated = True  # карта и блоки уже есть - setup_level их не создаёт
        return True

    def make_generator(self) -> MapGenerator:
        # Генератор с параметрами ТЕКУЩЕГО уровня режима
        return MapGenerator(self.map_params, self.block_params, shape_library=BLOCK_SHAPES)

    def _populate_blocks(self) -> None:
        # Хук: F01 блоков не создаёт. Переопределяется в F02
        return None

    def get_respawn_point(self) -> tuple[int, int]:
        # Случайное безопасное место возрождения игрока после смерти
        if not self.board or self.player_spawn_point is None:
            return self.player_spawn_point
        blocks = [(b.grid_x, b.grid_y) for b in self.state["blocks"]]
        avoid = list(self.enemy_spawn_points) + [(e.grid_x, e.grid_y) for e in self.state["enemies"]]
        min_dist = max(8, min(len(self.board[0]), len(self.board)) // 4)
        return pick_respawn_point(self.board, blocks, self.player_spawn_point, avoid, min_dist)

    def get_board_model(self):
        return self.board

    def save_block_snapshot(self) -> None:
        pass

    def restore_block_snapshot(self) -> None:
        pass

    def modify_spawn_params(self, max_enemies, spawn_delay):
        return 5, random.randint(1000, 1500)

    def apply_level_option(self, name, value) -> None:
        if name == "board_size":
            if value == "random":
                self.board_width, self.board_height = self._roll_board_size()
            elif isinstance(value, (tuple, list)) and len(value) == 2:
                self.board_width = max(self.MIN_SIZE, min(self.MAX_SIZE, int(value[0])))
                self.board_height = max(self.MIN_SIZE, min(self.MAX_SIZE, int(value[1])))
        else:
            super().apply_level_option(name, value)

    def check_conditions(self):
        if self.state["kills_this_level"] >= self.target_kills:
            self.advance_level()
            self.state["kills_this_level"] = 0
            if self.level_number > self.max_levels:
                return "WIN_SCREEN"
            return "NEXT_LEVEL"
        return None


class ModeF02(ModeF01):
    # Та же случайная карта, но с разрушаемыми блоками

    def __init__(self, game_state) -> None:
        super().__init__(game_state)
        self.mode_id = "F02"

    def _populate_blocks(self) -> None:
        if not self.board:
            return
        cells = self.make_generator().generate_blocks(
            self.board, self.player_spawn_point, self.enemy_spawn_points
        )
        spawn_cells(self.state, cells, self.board_width, self.board_height)
