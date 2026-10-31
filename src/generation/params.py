# Наборы параметров генерации: MapParams (карта) и BlockParams (блоки)


from dataclasses import dataclass
from dataclasses import field
from typing import Optional


_DIRS4 = ((1, 0), (-1, 0), (0, 1), (0, -1))
_NEAR_OFFSETS = ((2, 0), (-2, 0), (0, 2), (0, -2), (2, 2), (-2, 2), (2, -2), (-2, -2),
                 (3, 0), (-3, 0), (0, 3), (0, -3), (2, 1), (-2, 1), (1, 2), (-1, -2))


# ПАРАМЕТРЫ
@dataclass
class MapParams:
    # Параметры генерации КАРТЫ. Диапазоны - пары (мин, макс)
    seed: Optional[int] = None  # не None - одинаковая карта при одинаковых размерах
    min_corridor: int = 3  # меньше 3 танк (3x3) не проедет
    max_corridor: int = 9  # верхний предел ширины коридора
    corridor_bias: float = 1.0  # >1 - почти всегда узкие коридоры, <1 - шире
    # Вероятности "стилей" карты
    style_weights: dict = field(default_factory=lambda: {
        "grid": 22,  # сетка коридоров разной ширины
        "rooms": 20,  # комнаты + соединяющие проходы
        "caves": 16,  # пещеры (клеточный автомат)
        "open": 14,  # открытое поле с препятствиями-пустотами
        "scatter": 10,  # россыпь прямоугольников
        "mixed": 18,  # смесь 2-3 стилей
    })
    max_attempts: int = 40  # попыток сгенерировать "годную" карту
    min_floor_fraction: float = 0.04  # какую долю карты должна занимать проходимая область
    spawn_min_distance_cap: int = 20  # враги спавнятся не ближе (в шагах) к игроку
    # сетка
    grid_gap_max: tuple = (2, 7)  # макс. толщина стены между коридорами
    grid_partial: tuple = (0.0, 0.6)  # доля коротких коридоров (тупики)
    grid_cut: tuple = (0.05, 0.40)  # доля перекрытых участков (лабиринт)
    # комнаты
    room_max: int = 20  # макс. размер комнаты
    rooms_area_div: tuple = (120, 350)  # одна комната на столько клеток площади
    # пещеры
    cave_fill: tuple = (0.44, 0.56)
    cave_iterations: tuple = (3, 5)
    cave_scale_weights: tuple = (1, 2, 3)  # веса "зерна" 1x1, 2x2, 3x3
    # открытое поле и россыпь
    open_margin: tuple = (1, 3)
    open_area_div: tuple = (60, 220)
    scatter_area_div: tuple = (40, 120)
    scatter_max_size: int = 12

    def __post_init__(self) -> None:
        self.min_corridor = max(3, int(self.min_corridor))
        self.max_corridor = max(self.min_corridor, int(self.max_corridor))
        self.style_weights = dict(self.style_weights)


@dataclass
class BlockParams:
    # Параметры расстановки БЛОКОВ (F02)
    max_blocks: int = 900  # потолок числа блоков (для производительности игры)
    spawn_clear_radius: int = 4  # вокруг спавнов блоков нет (радиус 4 -> зона 9x9)
    rounds: int = 4  # раундов "поставить -> убрать недоступные"
    # сколько блоков
    density_ranges: tuple = (
        (0.05, (0.02, 0.04)),  # редко
        (0.40, (0.04, 0.08)),  # умеренно
        (0.40, (0.08, 0.13)),  # заметно
        (0.15, (0.13, 0.20)),  # плотно
    )
    density_scale: float = 1.0
    fixed_density: Optional[float] = None  # не None - всегда эта доля пола под блоками
    min_blocks: int = 10
    # стили расстановки (выбирается один на карту)
    style_weights: dict = field(default_factory=lambda: {"singles": 2, "mixed": 5, "airy": 3, "structure": 2})
    near_chance: float = 0.25  # шанс поставить кластер ровно через клетку от уже стоящего
    center_chance: float = 0.75  # шанс якоря на оси движения танка (центр 3x3)
    external_weight: float = 3.0  # вес фигур из внешней библиотеки (blocks.BLOCK_SHAPES)

    def __post_init__(self) -> None:
        self.style_weights = dict(self.style_weights)
        self.density_ranges = tuple(self.density_ranges)
