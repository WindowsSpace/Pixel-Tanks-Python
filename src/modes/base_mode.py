import copy
import dataclasses

from core import settings
import models
from core.settings import BOARD_WIDTH, BOARD_HEIGHT
from entities.blocks import spawn_blocks
from core.utils import level_to_int
from entities.tank import DefaultBoss

class BaseMode:
    # Какие настройки можно менять по уровням через self.level_overrides
    LEVEL_OPTIONS = ("board_model_name", "board_mode", "hud", "hp_style", "hp_fill", "os_borderless",
                     "os_window_icons", "skip_win_screen", "level_label", "start_lives", "cluster_scale", "save_map")

    def __init__(self, game_state) -> None:
        self.state = game_state
        self.mode_id = "Q99"

        # НАСТРОЙКИ РЕЖИМА
        self.board_mode = "CLASSIC"
        self.hud = "ON"
        # Модель карты из models ("NORMAL", "ALT", "OKAK" или свой список строк)
        self.board_model_name = "NORMAL"
        # Вид шкалы HP: имя из models.HP_MODELS ("4x4", "1x16", ...)
        self.hp_style = "4x4"
        # Как исчезают жизни: "gauge" - шкала (пропадает верхняя клетка, из равных - случайная),
        # "scatter" - клетки жизней разбросаны случайно.
        self.hp_fill = "scatter"
        # Окна HUD (hud = "OS_WINDOWS") без рамки ОС: без заголовка и кнопок
        self.os_borderless = True
        # Свои иконки окон HUD
        self.os_window_icons = {}
        # Сколько жизней у игрока со старта (по умолчанию 4)
        self.start_lives = 4
        # Победный экран: True - после победы сразу занавесом выходим в меню
        self.skip_win_screen = False
        # Текст вместо номера уровня в HUD (например "MAZE" или "ENDLESS"); None
        self.level_label = None
        # Сохранять ли текущую карту вместе с сохранением игры
        self.save_map = True
        # Множитель числа случайных кластеров блоков у этого режима
        self.cluster_scale = 1.0
        # Смена настроек по уровням: {номер_уровня: {опция: значение}}
        self.level_overrides = {}
        self._applied_level = 0
        # Параметры ИИ для вражеских танков этого режима
        self.enemy_params = {}
        # Картинка врагов: None - обычная, "BLACK" - полностью чёрная (режим D01)
        self.enemy_skin = None
        # Цвет пуль врагов (RGB) или None - обычные. D01: (0, 0, 0) - чёрные
        self.enemy_bullet_color = None
        # Сколько пуль игрок может держать в полёте на БОСС-файте
        self.boss_max_player_bullets = 1
        # Фиксировать ли направление игрока на босс-файте "вверх" (дуэль A02/B02...)
        self.lock_player_in_boss = True
        self.is_random_map = False

        self.enhanced_bullet_collision = False
        self.blocks_generated = False
        self.target_kills = 50
        self.extra_speed = 0.0

        self.restore_blocks_on_respawn = True
        self.saved_block_snapshot = []

        self.is_boss_phase = False
        self.boss_bonus_given = False
        self.boss = None

        self.level_number = level_to_int(self.state.get("level"), 1)

        self._reset_spawns()  # не тащим спавны предыдущего режима (например F)

    # Хуки для режимов с особым босс-файтом
    def make_boss(self, gx, gy, hp, max_hp):
        # Создаёт босса при загрузке сохранения. Режим со своим боссом переопределяет
        return DefaultBoss(gx, gy, hp=hp, max_hp=max_hp)

    def after_level_reset(self) -> None:
        # Вызывается приложением после смены уровня
        return None

    def try_revive(self) -> bool:
        # Игрок потерял последнюю жизнь
        return False

    def on_player_bullet(self, bullet) -> bool:
        # Пуля игрока попала в "особый" объект режима (например, цветной блок D01)
        return False

    def on_win_screen(self) -> None:
        # Занавес закрыт, сейчас покажут победный экран
        return None

    def draw_win_overlay(self, surface, win_rect, t_ms) -> None:
        # Поверх надписи WIN
        return None

    def draw_window_overlay(self, surface, grid_origin, field_rect, paused=False) -> None:
        # Эффекты поверх ВСЕГО окна игры перед выводом на экран
        return None

    def final_active(self) -> bool:
        # Идёт финальная сцена режима (игрок - окно ОС и т. п.)
        return False

    def boss_lethal_hook(self, boss, windows_ok=True) -> bool:
        # HP босса дошло до 0. True - режим не даёт ему умереть (начинается финал)
        return False

    def player_bullet_color(self, default):
        # Цвет пули игрока (None - обычная)
        return default

    def player_locked(self) -> bool:
        # True - игрок не может двигаться и стрелять (катсцена)
        return False

    def player_image(self, g_save=None):
        # Картинка танка игрока, если режим её переопределяет
        return None

    def instant_respawn(self) -> bool:
        # True - после смерти игрока вернуть на поле сразу, без шторки
        return False

    def music_state(self):
        # (что_играть, мало_жизней): "ambient" | "boss" | "end" | None
        return None, False

    def plain_player(self, g_save) -> bool:
        # True - в этом режиме танк и пули игрока рисуются без краски
        return False

    def update_effects(self, dt_ms) -> None:
        # Раз в кадр, пока идёт игра (не пауза): таймеры эффектов режима
        return None

    def draw_overlay(self, surface, camera_x, camera_y, paused=False) -> None:
        # Рисует эффекты режима поверх готового кадра поля (завесы, глитч)
        return None

    def boss_window_info(self):
        # (картинка, центр клетки gx, gy) для окна ОС босса или None (окно не нужно)
        return None

    def boss_window_bullets(self):
        # Клетки (gx, gy) пуль, летящих снаружи поля (каждая - окно ОС)
        return []

    def hidden_hud_panels(self):
        # Имена панелей HUD, которые сейчас не рисуем (экономия): "SCORE", "HI-SCORE"
        return frozenset()

    def hp_broken(self) -> bool:
        # True - шкала жизней рисуется "сломанной"
        return False

    def beat_zoom(self) -> float:
        # Масштаб поля в этот кадр (1.0 - без пульса)
        return 1.0

    def export_map(self):
        # Карта для записи в сохранение (dict) или None
        return None

    def import_map(self, data) -> bool:
        # Восстанавливает карту из сохранения; True, если получилось
        return False

    def save_block_snapshot(self) -> None:
        self.saved_block_snapshot = [
            {"shape": [(0, 0)], "x": b.grid_x, "y": b.grid_y}
            for b in self.state["blocks"]
        ]

    def restore_block_snapshot(self) -> None:
        if not self.saved_block_snapshot:
            self.save_block_snapshot()
            return

        for b in list(self.state["blocks"]):
            b.kill()

        spawn_blocks(
            self.state,
            self.bw,
            self.bh,
            num_clusters=0,
            custom_shapes=self.saved_block_snapshot
        )

    # Размер поля режима (по board_model_name)
    REF_W, REF_H = BOARD_WIDTH, BOARD_HEIGHT

    def _board_dims(self):
        m = models.get_board_model(self.board_model_name)
        return max((len(r) for r in m), default=self.REF_W), len(m) or self.REF_H

    @property
    def bw(self) -> int:
        return self._board_dims()[0]

    @property
    def bh(self) -> int:
        return self._board_dims()[1]

    def fit_x(self, x: int) -> int:
        # Координата X, заданная для поля 10x20, -> на текущем поле (пропорционально)
        w = self.bw
        return x if w == self.REF_W else round(x * (w - 1) / (self.REF_W - 1))

    def fit_y(self, y: int) -> int:
        h = self.bh
        return y if h == self.REF_H else round(y * (h - 1) / (self.REF_H - 1))

    def fit_shapes(self, shapes):
        # Сценарий блоков
        if not shapes or (self.bw, self.bh) == (self.REF_W, self.REF_H):
            return shapes
        return [dict(item, x=self.fit_x(item["x"]), y=self.fit_y(item["y"])) for item in shapes]

    def scale_clusters(self, n: int) -> int:
        # Число случайных кластеров блоков пропорционально площади поля
        k = (self.bw * self.bh) / (self.REF_W * self.REF_H) * self.cluster_scale
        if n <= 0 or abs(k - 1) < 1e-9:
            return n
        return max(0, round(n * k))

    def _reset_spawns(self) -> None:
        # Точки спавна по умолчанию под размер поля + спавны
        w, h = self._board_dims()
        settings.reset_spawn_points()
        settings.PLAYER_SPAWN_POINTS[:] = [(w // 2, h // 2 + 1)]
        settings.ENEMY_SPAWN_POINTS[:] = [(1, 1), (w - 2, 1), (1, h - 2), (w - 2, h - 2)]
        self.apply_spawns()
        self._spawn_dims = (w, h)

    def get_hud_params(self):
        # (board_mode, hud, hp_style, hp_fill) для раскладки окна
        return self.board_mode, self.hud, self.hp_style, self.hp_fill

    # Уровни
    def advance_level(self) -> int:
        # Переход на следующий уровень
        self.level_number += 1
        if level_to_int(self.state.get("level")) is not None:
            self.state["level"] = self.level_number
        self.state["level_number"] = self.level_number
        return self.level_number

    def restore_level(self) -> None:
        # Восстанавливает номер уровня после загрузки сохранения
        n = self.state.get("level_number")
        if not isinstance(n, int):
            n = level_to_int(self.state.get("level"), 1)
        self.level_number = max(1, n)
        self.state["level_number"] = self.level_number
        if level_to_int(self.state.get("level")) is None:
            self.state["level"] = self.level_number  # старые сохранения хранили тут текст ("ENDLESS")

    def get_level_text(self):
        # Что показывать в HUD вместо номера уровня
        if self.level_label is not None:
            return str(self.level_label)
        return self.state.get("level", 1)

    @staticmethod
    def _clone(value):
        if dataclasses.is_dataclass(value) and not isinstance(value, type):
            return copy.deepcopy(value)  # наборы параметров (например, map_params у F)
        return dict(value) if isinstance(value, dict) else list(value) if isinstance(value, list) else value

    def clear_bullets(self) -> None:
        # Убирает с поля ВСЕ летящие пули (свои и вражеские)
        for b in list(self.state.get("bullets", ())):
            if hasattr(b, "purge"):
                b.purge()  # лучи босса не гаснут от обычного kill()
            else:
                b.kill()

    def configure_level(self) -> None:
        # Применяет level_overrides, наступившие к текущему уровню: каждая запись
        due = []
        for k, opts in (self.level_overrides or {}).items():
            n = level_to_int(k)
            if n is not None and self._applied_level < n <= self.level_number:
                due.append((n, opts))
        for _, opts in sorted(due, key=lambda t: t[0]):
            for name, value in opts.items():
                self.apply_level_option(name, value)
        self._applied_level = max(self._applied_level, self.level_number)
        # Модель карты сменилась (board_model_name)
        if getattr(self, "_spawn_dims", None) != self._board_dims():
            self._reset_spawns()

    def apply_level_option(self, name, value) -> None:
        if name in self.LEVEL_OPTIONS or name in ("board_width", "board_height"):
            current = getattr(self, name, None)
            if dataclasses.is_dataclass(current) and isinstance(value, dict):
                # набор параметров + словарь правок: меняются только указанные поля
                setattr(self, name, dataclasses.replace(self._clone(current), **value))
            else:
                setattr(self, name, self._clone(value))
        elif name == "board_size" and isinstance(value, (tuple, list)) and len(value) == 2:
            self.board_width, self.board_height = int(value[0]), int(value[1])

    def get_board_model(self) -> list[str]:
        import models
        return models.get_board_model(self.board_model_name)
    
    def apply_spawns(self) -> None:
        return None

    def setup_level(self, is_new_level = False) -> None:
        if is_new_level:
            self.blocks_generated = False
            self.boss_bonus_given = False

    def check_conditions(self) -> str:
        return None

    def restrict_player_keys(self, event_key) -> bool:
        return True

    def get_custom_hud_goal(self) -> None:
        return None

    def modify_spawn_params(self, max_enemies, spawn_delay):
        return max_enemies, spawn_delay