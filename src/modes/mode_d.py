from modes.base_mode import BaseMode

import random
import pygame
from core import settings
from core.settings import DIR_UP, DIR_DOWN
from core.utils import generate_lives_positions
from core import assets
from core.grid import get_cell_topleft
from core.utils import is_cell_walkable
from entities.blocks import spawn_blocks, BlackBlock, PixelBlock, ColorBlock, color_cell_image
from core.collision import hitbox_collide
from models import PLAYER_MODEL, WIN_MODEL
from models.hp import get_hp_model
from entities.tank import BlackBoss
from entities.tank.black_boss import SPAWN_GRACE_MS


def boss_grace_ms() -> int:
    return SPAWN_GRACE_MS
from services import boss_music, audio_fx
from ui.glitch import Glitch
from ui import boss_window, final_windows, hud

class ModeD01(BaseMode):
    # НАСТРОЙКИ
    BOSS_LEVEL = 5  # на этом уровне - босс
    BOSS_HP = 16  # здоровье босса (16 - под шкалу 1x16)

    # Уровни 1-4: kills - сколько врагов убить; max_enemies/delay
    LEVELS = {
        1: dict(kills=6,  max_enemies=3, delay=(1300, 1800), clusters=2,
                ai=dict(aggressiveness=0.55, intelligence=0.4, patrol_chance=0.12,
                        shoot_time_min=1200, shoot_time_max=3500)),
        2: dict(kills=8,  max_enemies=3, delay=(1100, 1600), clusters=3,
                ai=dict(aggressiveness=0.70, intelligence=0.5, patrol_chance=0.08,
                        move_time_min=350, move_time_max=700,
                        shoot_time_min=1000, shoot_time_max=3000)),
        3: dict(kills=10, max_enemies=4, delay=(900, 1400), clusters=3,
                ai=dict(aggressiveness=0.80, intelligence=0.6, patrol_chance=0.05,
                        move_time_min=300, move_time_max=600,
                        shoot_time_min=800, shoot_time_max=2600)),
        4: dict(kills=12, max_enemies=4, delay=(800, 1200), clusters=4,
                ai=dict(aggressiveness=0.90, intelligence=0.7, patrol_chance=0.03,
                        move_time_min=260, move_time_max=520,
                        shoot_time_min=600, shoot_time_max=2000)),
    }

    # Раскладка босс-файта
    BOSS_LAYOUT = {
        "board_mode": "DYNAMIC",  # окно под размер поля
        "board_model_name": "ALT",
        "hud": "OS_WINDOWS",  # HUD отдельными окнами ОС
        "hp_style": "1x4",  # шкала жизней 1x4 вместо 4x4
        "hp_fill": "gauge",
    }

    # Заготовленные блоки арены босса: фигуры те же, а места СЛУЧАЙНЫЕ
    BOSS_ARENA_SHAPES = [
        [(0, 0), (1, 0), (0, 1), (1, 1)],
        [(0, 0), (1, 0), (0, 1), (1, 1)],
        [(0, 0), (1, 0)],
    ]
    ARENA_MARGIN_X = 0.22  # отступ от боковых краёв (доля ширины поля)
    ARENA_MARGIN_Y = 0.28  # то же сверху и снизу (доля высоты)
    # Запасная фиксированная раскладка
    BOSS_ARENA_BLOCKS = [
        {"shape": [(0, 0), (1, 0), (0, 1), (1, 1)], "x": 1, "y": 8},
        {"shape": [(0, 0), (1, 0), (0, 1), (1, 1)], "x": 7, "y": 8},
        {"shape": [(0, 0), (1, 0)], "x": 4, "y": 12},
    ]

    # Фоновый замедленный Redacted на уровнях 1-4
    AMBIENT_GAIN_START = 0.30
    AMBIENT_GAIN_STEP = 0.08

    # "Порча" (0..1): растёт по уровням и управляет завесами
    CORRUPTION = {1: 0.15, 2: 0.35, 3: 0.55, 4: 0.75}
    CORRUPTION_BOSS, CORRUPTION_BOSS_LOW = 0.90, 1.0

    # Завесы: чёрные клетки поверх поля (без коллизий)
    VEIL_INTERVAL_MS = (3000, 1200)  # пауза между завесами при порче 0 -> 1
    VEIL_LIFE_MS = (1200, 2800)  # сколько живёт завеса (последние 400 мс мигает)
    # Настоящие чёрные блоки (их можно расстрелять)
    BLOCK_INTERVAL_MS = (10000, 4500)  # пауза между появлениями при порче 0 -> 1
    # Глитч-"шейдер": сила = порча * (0.7 .. 1.3 на бите)
    GLITCH_ON = True

    # Окна ОС для босса за краем поля и его пуль (ui/boss_window.py)
    BOSS_OS_WINDOW = True

    # Цветные блоки (фаза 1)
    COLOR_PALETTE = [(230, 57, 70), (244, 140, 30), (245, 212, 40), (72, 200, 90),
                     (50, 200, 220), (66, 105, 235), (166, 86, 224)]
    PICKUP_EVERY_BEATS = 10  # новый цветной блок появляется раз в столько битов
    PICKUP_MAX = 2  # сколько цветных блоков на поле одновременно
    PICKUP_TTL_BEATS = 36  # сколько живёт (потом мигает и исчезает)
    # Блоки-укрытия (пункт 11): обычные блоки, в которых можно спрятаться от пуль
    COVER_EVERY_BEATS = 20
    COVER_MAX_EXTRA = 8  # сколько блоков-укрытий максимум добавляется за бой
    COVER_SHAPES = [[(0, 0)], [(0, 0), (1, 0)], [(0, 0), (0, 1)], [(0, 0), (1, 0), (0, 1), (1, 1)]]

    # Пульс поля в такт музыке босса: каждый 4-й бит на обычной песне
    BEAT_EVERY, BEAT_EVERY_LOW = 4, 2
    BEAT_ZOOM, BEAT_ZOOM_LOW = 0.030, 0.045  # на сколько увеличивается поле в пике пульса (3 % / 4.5 %)
    TARGET_KILLS: int = LEVELS[1]["kills"]  # цель первого уровня (её показывает меню)

    def __init__(self, game_state) -> None:
        super().__init__(game_state)
        self.mode_id = "D01"
        self.max_levels = self.BOSS_LEVEL
        self.target_kills = self.LEVELS[1]["kills"]
        self.enemy_params = dict(self.LEVELS[1]["ai"])
        self.enemy_skin = "BLACK"  # враги - чёрные
        # Уровни 1-4: классическое поле и HUD
        self.level_overrides = {self.BOSS_LEVEL: dict(self.BOSS_LAYOUT)}
        self.boss_max_player_bullets = 4  # на босс-файте игрок стреляет как обычно (до 4 пуль)
        self.lock_player_in_boss = False  # и ездит свободно, а не только влево-вправо
        self.restore_blocks_on_respawn = True
        self.victory = False  # босс побеждён, играет концовка
        self.victory_low = False
        self.enemy_bullet_color = (0, 0, 0)  # пули врагов и босса - чёрные
        self._veils = []  # завесы: {"cells": [(x, y), ...], "ttl": мс}
        self._veil_timer = 2000
        self._block_timer = 6000
        self._glitch = Glitch()
        self._beat_latch = False
        hud.HP_CELL_COLORS = {}  # цвета клеток шкалы HP не должны "переезжать" из прошлой игры
        self.pickups = pygame.sprite.Group()  # цветные блоки (проходимы, не стены)
        self.collected = []  # собранные игроком цвета (по порядку)
        self.painted = {}  # клетка модели танка (x, y) -> цвет
        self._pick_timer = 2500
        self._cover_timer = 9000
        self._cover_count = 0
        self._player_img = (None, None)  # (ключ, картинка) - кэш закрашенного танка
        self._wveils = []  # чёрные клетки по всему окну (вне поля): {"cells", "ttl"}
        self._wveil_timer = 0
        self._wglitch = Glitch()
        self._wlast = pygame.time.get_ticks()
        self.final = False  # финал: поле 3x3, босс заперт, игрок - окно ОС
        self._final_sound = None
        self._final_chan = None
        self._final_paused = False
        self.final_ms = 0  # сколько длится финал (для защиты от мгновенного убийства)
        self.final_warned = False  # окно-ошибка за слишком ранний выстрел уже показано
        self.boom_ms = None  # не None - идёт взрыв босса
        self._boom_imgs = []
        self._boss_starts = 0  # сколько раз создавался босс (первое создание - с интро)
        self._intro_flag = False  # идёт интро босса (BossIntro): ни атак, ни битов
        self._low_intro_done = False  # интро последней жизни для текущей жизни уже было
        self._arena = None  # случайная раскладка блоков арены

    # Уровни 1-4
    def _level_cfg(self):
        return self.LEVELS.get(min(self.level_number, max(self.LEVELS)))

    def setup_level(self, is_new_level=False) -> None:
        boss_music.MUSIC.preload()  # музыку грузим заранее, пока идёт шторка
        boss_music.MUSIC.ambient_gain = self.AMBIENT_GAIN_START + self.AMBIENT_GAIN_STEP * (self.level_number - 1)
        if self.level_number >= self.BOSS_LEVEL:
            if is_new_level:
                self.blocks_generated = False
            return  # арену и босса создаёт start_boss_phase()

        cfg = self._level_cfg()
        self.target_kills = self.state["target_enemies"] = cfg["kills"]
        self.enemy_params = dict(cfg["ai"])
        em = self.state.get("enemy_manager")
        if em is not None:
            em.enemy_params = dict(cfg["ai"])

        player = self.state["player"]
        player.grid_x, player.grid_y = random.choice(settings.PLAYER_SPAWN_POINTS)
        player.update_position()

        if is_new_level or not self.blocks_generated:
            for b in list(self.state["blocks"]):
                b.kill()
            spawn_blocks(self.state, self.bw, self.bh, self.scale_clusters(cfg["clusters"]))
            self.blocks_generated = True
            self.save_block_snapshot()
        elif self.restore_blocks_on_respawn:
            self.restore_block_snapshot()

    def modify_spawn_params(self, max_enemies, spawn_delay):
        if self.is_boss_phase:
            return 0, spawn_delay
        cfg = self._level_cfg()
        return cfg["max_enemies"], random.randint(*cfg["delay"])

    def after_level_reset(self) -> None:
        # Приложение только что убрало врагов и пули нового уровня
        if self.level_number >= self.BOSS_LEVEL and not self.is_boss_phase:
            self.start_boss_phase()

    def check_conditions(self):
        if not self.is_boss_phase:
            if self.state["kills_this_level"] >= self.target_kills:
                self.advance_level()
                self.state["kills_this_level"] = 0
                return "NEXT_LEVEL"
            return None

        # босс-файт
        boss = self.boss
        if boss is None and not self.victory:
            self.start_boss_phase()  # сохранение сделано в момент входа на босс-файт
            boss = self.boss
        if self.final and final_windows.FINAL.disabled:
            self.final_hit()  # окна не заработали - засчитываем победу, игра не зависает
            boss = self.boss
        if boss is not None and boss.alive():
            if self._intro_flag and not boss_music.MUSIC.in_intro() and boss_music.MUSIC.mode == "boss":
                self._intro_flag = False  # BossIntro закончился -> начинается бой
                boss.finish_intro()
            boss.os_windows = self._windows_on()  # окна ОС работают -> пули вылетают из-за края как окна
            boss.shielded = not self.all_colors()  # пока не собраны все цвета, выстрелы игрока боссу не вредят
            boss.set_enraged(self.all_colors())  # вторая фаза - когда собраны все цвета
            return None
        if boss is not None and boss.hp <= 0 and not self.victory:
            self.victory = True
            self.victory_low = self.is_low_hp()
            self.clear_bullets()
            return "WIN_SCREEN"  # концовка (BossEnd) доиграет поверх победного экрана
        return None

    # Босс
    def is_low_hp(self) -> bool:
        # Последняя жизнь игрока: LOWHP-музыка и вторая фаза босса
        return self.state.get("lives", 4) <= 1

    def make_boss(self, gx, gy, hp, max_hp):
        # форма босса - дефолтный танк (в D01 играет только дефолтный игрок)
        return BlackBoss(gx, gy, base_image=assets.make_black_copy(assets.DEFAULT_PLAYER_BASE_IMG or assets.PLAYER_BASE_IMG),
                         hp=hp, max_hp=max_hp)

    def start_boss_phase(self) -> None:
        # Создаёт арену и босса
        from services.save_load import save_game, load_game
        self.enhanced_bullet_collision = self.is_boss_phase = True
        self.clear_bullets()  # заранее выпущенные пули не должны задеть нового босса
        had_boss = self.boss is not None  # босс уже есть: возрождение или загрузка сохранения

        em = self.state.get("enemy_manager")
        if em is not None:
            em.clear_enemies()  # убирает и прежнего босса, и остатки обычных врагов
        self.boss = None

        player = self.state["player"]
        first_start = self._boss_starts == 0 and not had_boss  # повторный вход (сохранение) - без интро
        player.grid_x, player.grid_y = self.bw // 2, self.bh - 2  # временно: окончательное место - после арены и босса
        player.fixed_direction = None
        player.set_direction(DIR_UP)
        player.update_position()

        # Первый вход на босс-файт: жизни восстанавливаются до стартовых (4)
        if not self.boss_bonus_given:
            self.state["lives"] = self.start_lives
            self.state["lives_positions"] = generate_lives_positions(self.state["lives"])
            self.boss_bonus_given = True
            save_game(self.state.get("mode", "D01"), self.state.get("slot", 1), player,
                      self.state.get("enemy_manager"), self.state)

        # Арена: прежние блоки убираем, ставим сценарий босса
        for b in list(self.state["blocks"]):
            b.kill()
        if self._arena is None:
            self._arena = self.random_arena_blocks() or self.fit_shapes(self.BOSS_ARENA_BLOCKS)
        spawn_blocks(self.state, self.bw, self.bh, num_clusters=0, custom_shapes=self._arena)
        self.blocks_generated = True

        # Здоровье босса переживает смерть игрока
        hp = max_hp = self.BOSS_HP
        data = load_game(self.state.get("mode", "D01"), self.state.get("slot", 1))
        if data and data.get("boss"):
            hp = data["boss"].get("hp", hp)
            max_hp = data["boss"].get("max_hp", max_hp) or max_hp

        for p in list(self.pickups):
            p.kill()
        self._pick_timer = 2500
        self._cover_count = 0
        self.boss = self.make_boss(self.bw // 2, 3, hp, max_hp)
        self.boss.set_tempo(self.beat_ms())
        self.boss.shielded = not self.all_colors()
        self.boss.set_direction(DIR_DOWN)
        self.boss.os_windows = self._windows_on()
        self.boss.set_enraged(self.all_colors())
        self.state["enemies"].add(self.boss)
        self.state["all_sprites"].add(self.boss)
        self._boss_starts += 1

        # Игрок: первый раз - снизу по центру, дальше - случайное честное место
        if not first_start:
            player.grid_x, player.grid_y = self.fair_player_spot()
            player.update_position()

        # Интро: при первом появлении и каждый раз
        low = self.is_low_hp()
        if not low:
            self._low_intro_done = False
        variant = None
        if low and not self._low_intro_done:
            variant, self._low_intro_done = "last", True
        elif first_start:
            variant = "first"
        if variant is not None:
            self._begin_intro(variant)
        else:
            self._intro_flag = False
            self.boss.grace_ms = boss_grace_ms()  # возродились - босс первые секунды не стреляет
            boss_music.MUSIC.set_variant(low)  # музыка без интро: лупу нужной версии (обычной / LOWHP)

    def random_arena_blocks(self):
        # Случайные места для заготовленных фигур арены: в центральной части поля
        bw, bh = self.bw, self.bh
        mx = max(2, round(bw * self.ARENA_MARGIN_X))
        my = max(2, round(bh * self.ARENA_MARGIN_Y))
        boss_c, player_c = (bw // 2, 3), (bw // 2, bh - 2)

        def near(cells, c, r):
            return any(max(abs(x - c[0]), abs(y - c[1])) <= r for x, y in cells)

        taken, items = set(), []
        for shape in self.BOSS_ARENA_SHAPES:
            w = max(dx for dx, _ in shape) + 1
            h = max(dy for _, dy in shape) + 1
            x_lo, x_hi, y_lo, y_hi = mx, bw - mx - w, my, bh - my - h
            if x_hi < x_lo or y_hi < y_lo:
                continue
            found = None
            for gap in (1, 0):  # сначала с зазором, потом вплотную
                for _ in range(80):
                    x, y = random.randint(x_lo, x_hi), random.randint(y_lo, y_hi)
                    cells = [(x + dx, y + dy) for dx, dy in shape]
                    if near(cells, boss_c, 3) or near(cells, player_c, 3):
                        continue
                    if any(max(abs(cx - tx), abs(cy - ty)) <= gap for cx, cy in cells for tx, ty in taken):
                        continue
                    found = (x, y, cells)
                    break
                if found:
                    break
            if found:
                items.append({"shape": shape, "x": found[0], "y": found[1]})
                taken.update(found[2])
        return items

    # Победа: классическое поле и HUD, WIN в чёрных пикселях
    CLASSIC_LAYOUT = {"board_mode": "CLASSIC", "board_model_name": "NORMAL", "hud": "ON",
                      "hp_style": "4x4", "hp_fill": "gauge"}
    WIN_SMEAR_STATIC = 0.20  # доля клеток WIN, залитых чёрным навсегда
    WIN_SMEAR_FLICKER = 0.22  # и столько ещё мерцает

    def on_win_screen(self) -> None:
        hud.HP_CELL_COLORS = {}
        self._wveils.clear()
        for k, v in self.CLASSIC_LAYOUT.items():  # обычное поле и обычный HUD, как до босса
            self.apply_level_option(k, v)
        self.state["lives_positions"] = generate_lives_positions(self.state.get("lives", 1))

    def draw_win_overlay(self, surface, win_rect, t_ms) -> None:
        cell = assets.BLACK_CELL_IMG
        C = settings.CELL_SIZE
        if cell is not None:
            frame = int(t_ms) // 140
            for y, row in enumerate(WIN_MODEL):
                for x, ch in enumerate(row):
                    if ch in " .":
                        continue
                    h = ((x * 73856093) ^ (y * 19349663)) % 1000 / 1000.0
                    h2 = ((x * 83492791) ^ (y * 2654435761) ^ (frame * 40503)) % 1000 / 1000.0
                    if h < self.WIN_SMEAR_STATIC or h2 < self.WIN_SMEAR_FLICKER:
                        surface.blit(cell, (win_rect.x + x * C, win_rect.y + y * C))
        if self.GLITCH_ON:  # "шейдер": полосы и вспышки поверх всей сцены
            self._glitch.update(0.8)
            self._glitch.apply(surface, 0.8)

    def draw_window_overlay(self, surface, grid_origin, field_rect, paused=False) -> None:
        # Чёрные клетки и сдвиг полос по всему окну, не только на поле
        now = pygame.time.get_ticks()
        dt = min(100, now - self._wlast)
        self._wlast = now
        if self.victory or not self.GLITCH_ON:
            self._wveils.clear()
            return
        c = self.corruption
        C = settings.CELL_SIZE
        ox, oy = grid_origin
        w, h = surface.get_size()
        if not paused:
            self._wveil_timer -= dt
            if self._wveil_timer <= 0 and c > 0:
                self._wveil_timer = random.uniform(700, 1800) / (0.4 + 1.6 * c)
                gx0, gx1 = -(ox // C) - 1, (w - ox) // C + 1
                gy0, gy1 = -(oy // C) - 1, (h - oy) // C + 1
                cx, cy = random.randint(gx0, gx1), random.randint(gy0, gy1)
                shape = random.choice(self.COVER_SHAPES + [[(0, 0), (1, 0), (2, 0)], [(0, 0), (0, 1), (0, 2)]])
                self._wveils.append({"cells": [(cx + dx, cy + dy) for dx, dy in shape],
                                     "ttl": random.uniform(900, 2600)})
            for v in self._wveils:
                v["ttl"] -= dt
            self._wveils = [v for v in self._wveils if v["ttl"] > 0]
            self._wglitch.update(c * 0.5)
        cell = assets.BLACK_CELL_IMG
        if cell is not None:
            for v in self._wveils:
                if v["ttl"] < 400 and (int(v["ttl"]) // 100) % 2 == 0:
                    continue
                for gx, gy in v["cells"]:
                    r = pygame.Rect(ox + gx * C, oy + gy * C, C, C)
                    if r.colliderect(field_rect) or not r.colliderect(surface.get_rect()):
                        continue  # внутри поля - его собственные завесы; за окном - не видно
                    surface.blit(cell, r.topleft)
        self._wglitch.apply(surface, c * 0.5)

    # Финал: поле 3x3, заперт босс, Redacted x3
    FINAL_SPEED = 3.0  # скорость Redacted (300 %)
    FINAL_FIELD = 4  # сторона сжатого поля (клеток)
    FINAL_GRACE_MS = 6000  # первые секунды финала босса убить нельзя
    BOOM_STEP_MS = 150  # смена кадра взрыва (как у игрока)
    BOOM_HIDE_MS = 600  # через столько танк босса пропадает под взрывом
    BOOM_TOTAL_MS = 1500  # полная длина взрыва, после неё - победа

    def final_active(self) -> bool:
        return self.final and not self.victory

    def final_center(self):
        return self.bw // 2, self.bh // 2

    def final_field_cells(self):
        cx, cy = self.final_center()
        n = self.FINAL_FIELD
        return cx - n // 2, cy - n // 2, n, n

    def layout_cells(self):
        # Размер окна игры в клетках: в финале окно сжимается до поля босса (DYNAMIC)
        if self.final:
            return self.FINAL_FIELD, self.FINAL_FIELD
        return None

    def camera_origin(self):
        # Камера в финале стоит ровно на поле босса
        if self.final:
            x0, y0, _, _ = self.final_field_cells()
            return x0 * settings.CELL_SIZE, y0 * settings.CELL_SIZE
        return None

    def apply_final_audio(self, volume, paused) -> None:
        # Redacted x3 живёт вне assets, поэтому громкость и паузу ему задаём отдельно
        snd, chan = self._final_sound or getattr(assets, "REDACTED_SOUND", None), self._final_chan
        if snd is None or chan is None:
            return
        try:
            snd.set_volume(volume if self.state.get("sounds_enabled", True) else 0.0)
            if paused and not self._final_paused:
                chan.pause()
                self._final_paused = True
            elif not paused and self._final_paused:
                chan.unpause()
                self._final_paused = False
        except Exception:
            pass

    def get_board_model(self):
        board = super().get_board_model()
        if not self.final:
            return board
        x0, y0, w, h = self.final_field_cells()  # всё, кроме 3x3 в центре, - пустота
        rows = []
        for y, row in enumerate(board):
            rows.append("".join((ch if (x0 <= x < x0 + w and y0 <= y < y0 + h) else " ") for x, ch in enumerate(row)))
        return rows

    def boss_lethal_hook(self, boss, windows_ok=True) -> bool:
        if self.final or self.victory:
            return False
        if not windows_ok or not self._windows_on():
            return False  # без окон ОС финала не будет: сразу победа
        self._start_final(boss)
        return True

    def _start_final(self, boss) -> None:
        st = self.state
        self.final = True
        final_windows.FINAL.reset()
        boss.hp = 1  # последний выстрел добьёт; сейчас босс не умирает
        self.clear_bullets()
        for grp in (st["blocks"], self.pickups):
            for b in list(grp):
                b.kill()
        self._veils.clear()
        cx, cy = self.final_center()
        self.final_ms, self.final_warned, self.boom_ms = 0, False, None
        boss.vanish = False
        boss.lock_at(cx, cy, self.final_field_cells())
        player = st["player"]
        st["all_sprites"].remove(player)  # игрок теперь окно ОС
        player.grid_x, player.grid_y = 0, 0
        player.update_position()
        player.invuln_ms = 10 ** 9
        # Redacted x3 вместо музыки боя
        try:
            if self._final_sound is None:
                self._final_sound = audio_fx.sped_sound(getattr(assets, "REDACTED_SOUND", None), self.FINAL_SPEED)
            snd = self._final_sound or getattr(assets, "REDACTED_SOUND", None)
            if snd is not None and st.get("sounds_enabled", True):
                self._final_chan = snd.play(loops=-1)
                self._final_paused = False
        except Exception:
            self._final_chan = None

    def _stop_final_sound(self) -> None:
        try:
            if self._final_chan is not None:
                self._final_chan.stop()
        except Exception:
            pass
        self._final_chan = None
        self._final_paused = False

    def final_booming(self) -> bool:
        return self.final and self.boom_ms is not None

    def final_bullet_hit(self) -> None:
        # Пуля-окно игрока попала в поле босса
        if self.boom_ms is not None:
            return
        if self.final_ms < self.FINAL_GRACE_MS:
            final_windows.FINAL.pending.clear()
            if not self.final_warned:
                self.final_warned = True
                try:
                    from ui.corruption import show_system_message
                    show_system_message(
                        "Y0U.exe — ошибка",
                        "Не удаётся завершить процесс «Y0U.exe».\n\n"
                        "Код ошибки: 0x0000000D — процесс занят.\n"
                        "Он ещё не закончил свои дела. Подождите немного и повторите попытку.",
                        "error", "Повторить")
                except Exception:
                    pass
            return
        self.final_hit()

    def final_hit(self) -> None:
        # Последний выстрел игрока попал в босса: запускается взрыв
        if self.boom_ms is not None:
            return
        self._stop_final_sound()
        final_windows.FINAL.close()
        self.boom_ms = 0
        self._boom_imgs = assets.build_explosion_imgs((0, 0, 0))  # клетки взрыва - того же цвета, что и сам босс
        assets.play_sound(assets.BOSS_EXPLOSION_SOUND, self.state.get("sounds_enabled", True))

    def _tick_final(self, dt_ms) -> None:
        self.final_ms += dt_ms
        if self.boom_ms is None:
            return
        self.boom_ms += dt_ms
        boss = self.boss
        if boss is not None and self.boom_ms >= self.BOOM_HIDE_MS:
            boss.vanish = True
        if self.boom_ms >= self.BOOM_TOTAL_MS:
            self.final = False
            self.boom_ms = None
            if boss is not None:
                boss.hp = 0
                boss.kill()

    def draw_final_boom(self, surface, camera_x, camera_y) -> None:
        if not self.final_booming() or not self._boom_imgs:
            return
        idx = min((int(self.boom_ms) // self.BOOM_STEP_MS) % 2, len(self._boom_imgs) - 1)
        img = self._boom_imgs[idx]
        size = max(1, img.get_width() // settings.CELL_SIZE)
        cx, cy = self.final_center()
        tx, ty = get_cell_topleft(cx - size // 2, cy - size // 2)
        surface.blit(img, (tx - camera_x, ty - camera_y))

    # Цветные блоки
    def beat_ms(self) -> float:
        return 60000.0 / max(1.0, boss_music.MUSIC.bpm)

    def all_colors(self) -> bool:
        # Игрок собрал все цвета: босса можно ранить, начинается вторая фаза
        return len(self.collected) >= len(self.COLOR_PALETTE)

    def collect_color(self, color) -> None:
        self.collected.append(tuple(color))
        free = [(x, y) for y, row in enumerate(PLAYER_MODEL) for x, ch in enumerate(row)
                if ch not in " ." and (x, y) not in self.painted]
        if free:
            self.painted[random.choice(free)] = tuple(color)  # случайная часть танка
        if self.state.get("lives", 0) < self.start_lives:  # +1 жизнь, если есть куда
            self.state["lives"] += 1
            self.state["lives_positions"] = generate_lives_positions(self.state["lives"])
        self._sync_hp_colors()

    def _sync_hp_colors(self) -> None:
        # Шкала HP красится снизу вверх: i-й собранный цвет - i-я клетка снизу
        if not self.is_boss_phase or self.victory:
            hud.HP_CELL_COLORS = {}
            return
        rows = len(get_hp_model(self.BOSS_LAYOUT["hp_style"]))
        hud.HP_CELL_COLORS = {(0, rows - 1 - i): c for i, c in enumerate(self.collected[:rows])}

    # Шанс цветной пули игрока: растёт с числом цветов в корпусе
    PLAYER_COLOR_BULLET_PER_COLOR = 0.13
    PLAYER_COLOR_BULLET_MAX = 0.92

    def player_bullet_color(self, default):
        n = len(self.collected)
        if self.is_boss_phase and n and random.random() < min(self.PLAYER_COLOR_BULLET_MAX,
                                                              self.PLAYER_COLOR_BULLET_PER_COLOR * n):
            return random.choice(self.collected)  # пуля цвета одной из закрашенных частей корпуса
        return default

    def player_locked(self) -> bool:
        return self.intro_active() or self.final  # катсцена-интро: ни ходить, ни стрелять

    def player_image(self, g_save=None):
        # Дефолтный танк игрока (на боссе в D01 всегда дефолтная форма)
        if not self.is_boss_phase or self.victory:
            return None
        base = None
        if g_save is not None and not self.plain_player(g_save) and g_save.get("paint_tank", False):
            base = tuple(g_save.get("rgb", [129, 136, 111]))
        if not self.painted and base is None:
            return None
        key = (base, tuple(sorted(self.painted.items())))
        if self._player_img[0] == key:
            return self._player_img[1]
        size = settings.CELL_SIZE
        surf = pygame.Surface((len(PLAYER_MODEL[0]) * size, len(PLAYER_MODEL) * size), pygame.SRCALPHA)
        for y, row in enumerate(PLAYER_MODEL):
            for x, ch in enumerate(row):
                if ch in " .":
                    continue
                color = self.painted.get((x, y), base)
                surf.blit(color_cell_image(color) if color is not None else assets.PIXEL_IMG_RAW, (x * size, y * size))
        self._player_img = (key, surf)
        return surf

    def on_player_bullet(self, bullet) -> bool:
        hit = pygame.sprite.spritecollide(bullet, self.pickups, True, hitbox_collide)
        return bool(hit)  # расстрелянный цветной блок пропадает без бонуса

    def _spawn_pickup(self) -> None:
        left = [c for c in self.COLOR_PALETTE if c not in self.collected and c not in {p.color for p in self.pickups}]
        if not left:
            return
        board = self.get_board_model()
        st = self.state
        taken = {(b.grid_x, b.grid_y) for b in st["blocks"]} | {(p.grid_x, p.grid_y) for p in self.pickups}
        player = st["player"]
        boss = self.boss
        for _ in range(40):
            x = random.randint(1, max(1, self.bw - 2))
            y = random.randint(1, max(1, self.bh - 2))
            if (x, y) in taken or not is_cell_walkable(board, x, y):
                continue
            if max(abs(x - player.grid_x), abs(y - player.grid_y)) < 3:
                continue  # не прямо под игроком
            if boss is not None and boss.state == "FIELD" and max(abs(x - boss.grid_x), abs(y - boss.grid_y)) < 3:
                continue
            ttl = self.beat_ms() * self.PICKUP_TTL_BEATS
            block = ColorBlock(x, y, random.choice(left), ttl)
            self.pickups.add(block)
            st["all_sprites"].add(block)
            return

    def _update_pickups(self, dt_ms) -> None:
        for p in list(self.pickups):
            if not p.tick(dt_ms):
                p.kill()
        # подбор: любая клетка танка игрока на клетке блока
        player = self.state["player"]
        if player.alive() and self.pickups:
            try:
                cells = {(player.grid_x + dx, player.grid_y + dy) for dx, dy in player.get_footprint()}
            except Exception:
                cells = {(player.grid_x + dx, player.grid_y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)}
            for p in list(self.pickups):
                if (p.grid_x, p.grid_y) in cells:
                    p.kill()
                    self.collect_color(p.color)
        if self.all_colors():
            for p in list(self.pickups):
                p.kill()
            return
        self._pick_timer -= dt_ms
        if self._pick_timer <= 0:
            if len(self.pickups) < self.PICKUP_MAX:
                self._spawn_pickup()
            self._pick_timer = self.beat_ms() * self.PICKUP_EVERY_BEATS * random.uniform(0.8, 1.25)

    def _update_cover(self, dt_ms) -> None:
        # Время от времени появляются обычные блоки (их можно расстрелять)
        self._cover_timer -= dt_ms
        if self._cover_timer > 0:
            return
        self._cover_timer = self.beat_ms() * self.COVER_EVERY_BEATS * random.uniform(0.8, 1.3)
        if self._cover_count >= self.COVER_MAX_EXTRA:
            return
        st = self.state
        board = self.get_board_model()
        taken = {(b.grid_x, b.grid_y) for b in st["blocks"]} | {(p.grid_x, p.grid_y) for p in self.pickups}
        player = st["player"]
        tanks = [(e.grid_x, e.grid_y, 4 if getattr(e, "is_boss", False) else 3) for e in st["enemies"]]
        for _ in range(40):
            shape = random.choice(self.COVER_SHAPES)
            bx = random.randint(2, max(2, self.bw - 4))
            by = random.randint(2, max(2, self.bh - 4))
            cells = [(bx + dx, by + dy) for dx, dy in shape]
            if any((x, y) in taken or not is_cell_walkable(board, x, y) for x, y in cells):
                continue
            if any(max(abs(x - player.grid_x), abs(y - player.grid_y)) < 4 for x, y in cells):
                continue  # не на голову игроку
            if any(max(abs(x - ex), abs(y - ey)) < r for x, y in cells for ex, ey, r in tanks):
                continue
            for x, y in cells:
                block = PixelBlock(x, y)
                st["blocks"].add(block)
                st["all_sprites"].add(block)
            self._cover_count += len(cells)
            return

    # Интро и возрождение
    def _begin_intro(self, variant) -> None:
        low = variant == "last"
        if low:
            boss_music.MUSIC.restart_boss(low=True)  # BossIntroLOWHP играет заново
        boss_music.MUSIC.preload()
        length = boss_music.MUSIC.intro_length_ms(low)
        steps = (self.bw // 2 + 2) if low else (3 + 2 + 1)
        # босс дойдёт ровно к концу интро; без файла интро - быстро
        step_ms = (length * 0.9 / steps) if length > 0 else 450
        self._intro_flag = True
        self._veils.clear()
        self.clear_bullets()
        self.boss.begin_intro(variant, step_ms, self.bw, self.bh)

    def intro_active(self) -> bool:
        return self._intro_flag and self.is_boss_phase and not self.victory

    def fair_player_spot(self):
        # Случайное место для возрождения: свободное для танка
        board = self.get_board_model()
        player = self.state["player"]
        blocks = {(b.grid_x, b.grid_y) for b in self.state["blocks"]}
        bx, by = self.bw // 2, 3  # босс стоит (или встанет) здесь
        boss = self.boss
        if boss is not None and boss.alive() and boss.state == "FIELD":
            bx, by = boss.grid_x, boss.grid_y  # бой идёт: считаем от настоящего положения босса
        r = max(1, getattr(player, "width_cells", 3) // 2)

        def free(x, y):
            return all(is_cell_walkable(board, x + dx, y + dy) and (x + dx, y + dy) not in blocks
                       for dx in range(-r, r + 1) for dy in range(-r, r + 1))

        cells = [(x, y) for y in range(r, self.bh - r) for x in range(r, self.bw - r) if free(x, y)]
        for min_dist, lane in ((8, 3), (6, 2), (5, 0), (3, 0)):
            good = [(x, y) for x, y in cells
                    if max(abs(x - bx), abs(y - by)) >= min_dist and abs(x - bx) > lane]
            if good:
                return random.choice(good)
        return random.choice(cells) if cells else (self.bw // 2, self.bh - 2)

    RESPAWN_INVULN_MS = 2600  # столько игрок мигает и неуязвим после смерти на боссе

    def respawn_player(self) -> None:
        # Босс-файт продолжается без сброса (босс, цвета, HP босса остаются)
        player = self.state["player"]
        player.grid_x, player.grid_y = self.fair_player_spot()
        player.fixed_direction = None
        player.set_direction(DIR_UP)
        player.update_position()
        player.invuln_ms = self.RESPAWN_INVULN_MS

    def instant_respawn(self) -> bool:
        # Смерть на босс-файте, когда после неё у игрока больше одной жизни
        return self.is_boss_phase and not self.victory and self.state.get("lives", 0) >= 2

    def get_custom_hud_goal(self):
        if self.is_boss_phase and self.boss is not None:
            return ("BOSS", "|" * max(0, self.boss.hp) or "-")  # здоровье босса - чёрточки
        return None

    # Музыка
    def music_state(self):
        if self.final:
            return None, False  # в финале играет только Redacted x3
        if self.victory:
            return "end", self.victory_low
        if self.is_boss_phase:
            # Босс-уровень открыт заново (загрузка сохранения): BossIntro не играем
            boss_music.MUSIC.start_in_loop = self._boss_starts == 0 and self.boss is not None
            return "boss", self.is_low_hp()
        return "ambient", False  # уровни 1-4: тихий замедленный Redacted

    # Игрок без краски, пока режим не пройден
    def plain_player(self, g_save) -> bool:
        return not bool(g_save.get("completed", {}).get("D01", False))

    # Порча: завесы, чёрные блоки, глитч
    @property
    def corruption(self) -> float:
        if self.final:
            return 1.0  # финал: максимум помех
        if self.is_boss_phase:
            return self.CORRUPTION_BOSS_LOW if self.is_low_hp() else self.CORRUPTION_BOSS
        return self.CORRUPTION.get(min(self.level_number, max(self.CORRUPTION)), 0.15)

    @staticmethod
    def _lerp(pair, c) -> float:
        return pair[0] + (pair[1] - pair[0]) * c

    def update_effects(self, dt_ms) -> None:
        if self.final:
            self._tick_final(dt_ms)
        if self.victory or self.intro_active() or self.final:
            self._veils.clear()
            self._beat_latch = False
            if self.GLITCH_ON and not self.victory:
                self._glitch.update(self.corruption * (1.0 if self.final else 0.4))  # лёгкий фон без вспышек на бит
            return
        c = self.corruption

        if self.is_boss_phase:
            self._update_pickups(dt_ms)
            self._update_cover(dt_ms)
            self._sync_hp_colors()

        # завесы
        for v in self._veils:
            v["ttl"] -= dt_ms
        self._veils = [v for v in self._veils if v["ttl"] > 0]
        self._veil_timer -= dt_ms
        if self._veil_timer <= 0:
            if len(self._veils) < 1 + int(5 * c):
                self._spawn_veil(c)
            if self.is_boss_phase:  # на боссе завесы в такт: раз в 4 бита (на LOWHP - в 2)
                beat_ms = 60000.0 / max(1.0, boss_music.MUSIC.bpm)
                self._veil_timer = beat_ms * (2 if self.is_low_hp() else 4)
            else:
                self._veil_timer = self._lerp(self.VEIL_INTERVAL_MS, c) * random.uniform(0.7, 1.3)

        # настоящие чёрные блоки
        self._block_timer -= dt_ms
        if self._block_timer <= 0:
            alive = sum(1 for b in self.state["blocks"] if isinstance(b, BlackBlock))
            if alive < 1 + int(4 * c):
                self._spawn_black_block()
            self._block_timer = self._lerp(self.BLOCK_INTERVAL_MS, c) * random.uniform(0.8, 1.2)

        # глитч (на акцентном бите босса - принудительная вспышка)
        if self.GLITCH_ON:
            pulse = 0.0
            if self.is_boss_phase:
                pulse = boss_music.MUSIC.beat_pulse(self.BEAT_EVERY_LOW if self.is_low_hp() else self.BEAT_EVERY)
                if pulse > 0.95 and not self._beat_latch:
                    self._beat_latch = True
                    self._glitch.kick(c)
                elif pulse < 0.5:
                    self._beat_latch = False
            self._glitch.update(c * (0.7 + 0.6 * pulse))

    def _spawn_veil(self, c) -> None:
        w = random.randint(1, 2 + int(2 * c))
        h = random.randint(1, 2 + int(2 * c))
        x0 = random.randint(0, max(0, self.bw - w))
        y0 = random.randint(0, max(0, self.bh - h))
        board = self.get_board_model()
        cells = [(x, y) for x in range(x0, x0 + w) for y in range(y0, y0 + h) if is_cell_walkable(board, x, y)]
        if cells:
            self._veils.append({"cells": cells, "ttl": random.randint(*self.VEIL_LIFE_MS)})

    def _spawn_black_block(self) -> None:
        st = self.state
        board = self.get_board_model()
        taken = {(b.grid_x, b.grid_y) for b in st["blocks"]}
        player = st["player"]
        tanks = [(e.grid_x, e.grid_y, 4 if getattr(e, "is_boss", False) else 3) for e in st["enemies"]]
        spawns = list(settings.PLAYER_SPAWN_POINTS) + list(settings.ENEMY_SPAWN_POINTS)
        for _ in range(30):  # ищем место, где блок никому не встанет на голову
            x = random.randint(1, max(1, self.bw - 2))
            y = random.randint(1, max(1, self.bh - 2))
            if (x, y) in taken or not is_cell_walkable(board, x, y):
                continue
            if max(abs(x - player.grid_x), abs(y - player.grid_y)) < 4:
                continue
            if any(max(abs(x - ex), abs(y - ey)) < r for ex, ey, r in tanks):
                continue
            if any(max(abs(x - sx), abs(y - sy)) <= 1 for sx, sy in spawns):
                continue
            block = BlackBlock(x, y)
            st["blocks"].add(block)
            st["all_sprites"].add(block)
            return

    def draw_overlay(self, surface, camera_x, camera_y, paused=False) -> None:
        cell = assets.BLACK_CELL_IMG
        if cell is not None and self._veils:
            player = self.state["player"]
            shots = {(b.grid_x, b.grid_y) for b in self.state["bullets"] if b.is_player}
            for v in self._veils:
                if v["ttl"] < 400 and (int(v["ttl"]) // 100) % 2 == 0:
                    continue  # перед исчезновением завеса мигает
                for x, y in v["cells"]:
                    if abs(x - player.grid_x) <= 2 and abs(y - player.grid_y) <= 2:
                        continue  # игрока не закрываем
                    if (x, y) in shots:
                        continue  # и его пули тоже
                    tx, ty = get_cell_topleft(x, y)
                    surface.blit(cell, (tx - camera_x, ty - camera_y))
        boss = self.boss
        if cell is not None and boss is not None and boss.alive() and hasattr(boss, "lurk_cells"):
            for x, y in boss.lurk_cells():  # босс за краем поля: край его ряда горит / мигает перед
                tx, ty = get_cell_topleft(x, y)
                surface.blit(cell, (tx - camera_x, ty - camera_y))
        if self.GLITCH_ON and not self.victory:
            self._glitch.apply(surface, self.corruption)

    def _windows_on(self) -> bool:
        return bool(self.BOSS_OS_WINDOW) and hud.os_available() and not boss_window.WINDOW.disabled

    def boss_window_info(self):
        boss = self.boss
        if not self._windows_on() or self.victory or self.final or boss is None or not boss.alive():
            return None
        center = boss.ghost_center() if hasattr(boss, "ghost_center") else None
        if center is None:
            return None
        return boss.window_image(), center[0], center[1]

    def boss_window_bullets(self):
        # Клетки пуль босса, которые ещё летят снаружи поля
        if not self._windows_on() or self.victory or self.final:
            return []
        return [(b.grid_x, b.grid_y) for b in self.state["bullets"] if getattr(b, "outside", False)]

    def hidden_hud_panels(self):
        # На босс-файте очки, рекорд, уровень и скорость не важны - их не рисуем
        if self.is_boss_phase and not self.victory:
            return frozenset({"SCORE", "HI-SCORE", "LEVEL"})
        return frozenset()

    # Эффекты второй фазы
    def hp_broken(self) -> bool:
        # Последняя жизнь на босс-файте: шкала жизней "сломана"
        return self.is_boss_phase and not self.victory and self.is_low_hp()

    def beat_zoom(self) -> float:
        if not self.is_boss_phase or self.victory or self.intro_active() or self.final:
            return 1.0
        low = self.is_low_hp()
        pulse = boss_music.MUSIC.beat_pulse(self.BEAT_EVERY_LOW if low else self.BEAT_EVERY)
        return 1.0 + (self.BEAT_ZOOM_LOW if low else self.BEAT_ZOOM) * pulse

class ModeD02(BaseMode):
    TARGET_KILLS:int = 1
    def __init__(self, game_state) -> None:
        super().__init__(game_state)
        self.mode_id = "D02"

class ModeD03(BaseMode):
    TARGET_KILLS:int = 1
    def __init__(self, game_state) -> None:
        super().__init__(game_state)
        self.mode_id = "D03"
