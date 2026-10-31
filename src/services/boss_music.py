# Музыка режима D01 (папка assets/sounds/Boss/Y0U + фоновый Redacted)

import os
import pygame

from core import assets
from services import audio_fx

FOLDER = "assets/sounds/Boss/Y0U"
FILES = {
    "intro": "BossIntro.ogg", "intro_low": "BossIntroLOWHP.ogg",
    "loop": "BossLoop.ogg", "loop_low": "BossLoopLOWHP.ogg",
    "end": "BossEnd.ogg", "end_low": "BossEndLOWHP.ogg",
}

# НАСТРОЙКИ
AMBIENT_RATE = 0.55  # во сколько раз Redacted замедляется
AMBIENT_FALLBACK_FILE = "assets/sounds/Boss/RedactedSlow.ogg"  # если замедлить "на лету" не вышло и такой файл есть
AMBIENT_FADE_IN_MS = 1500
AMBIENT_FADE_OUT_MS = 700

PAUSE_SLOW_MS = 500  # за сколько музыка "останавливается" на паузе
RESUME_SLOW_MS = 450  # и за сколько разгоняется обратно
XFADE_MS = 50  # стык основного звука и хвоста плёнки (убирает щелчок)
SOFT_FADE_MS = 180  # запасная плавная пауза, если хвосты сделать нельзя

# Бит
BEAT_OFFSET_MS = 0  # сдвиг бита: если пульс экрана опережает/запаздывает
PULSE_DECAY_BEATS = 1.6  # за сколько битов пульс затухает после акцентного бита

def read_bpm(default=150.0) -> float:
    # Темп из Y0U/BPM.txt (для бита экрана)
    real = assets._find_file(os.path.join(FOLDER, "BPM.txt"))
    try:
        with open(real, "r", encoding="utf-8") as f:
            return float(f.read().strip())
    except Exception:
        return default


class BossMusic:
    def __init__(self) -> None:
        self.snd = {}
        self.loaded = False
        self.ch_a = None  # обычная версия
        self.ch_b = None  # LOWHP-версия
        self.ch_c = None  # фоновый Redacted
        self.ch_t = None  # хвосты "плёнки" на паузе
        self.ambient_gain = 0.4  # громкость фона (0..1 от общей); режим меняет её по уровням
        self.mode = None  # None | "ambient" | "boss" | "end"
        self.bpm = 150.0
        self.end_done = False  # концовка уже сыграла
        self.seg_t0 = None  # когда началась текущая часть (интро / очередной повтор лупа)
        self.seg_count = 0
        self.seg_kind = "intro"
        self.use_low = False  # какая версия играет сейчас: False - обычная, True - LOWHP
        self.start_in_loop = False  # режим просит: при запуске боевой музыки пропустить интро
        self.amb_t0 = 0
        # пауза
        self.pstate = "run"  # run | xfade_out | paused | resuming | xfade_in | soft_out
        self.paused = False  # музыка сейчас не играет "как обычно"
        self.fx = 1.0  # множитель громкости основных каналов
        self.p_t0 = 0
        self.pause_at = 0
        self.resume_at = 0
        self.vol_now = 1.0
        self._soft_from = 1.0  # с какого уровня громкости идёт плавная пауза / возврат

    # загрузка
    def preload(self) -> bool:
        # Загружает файлы (один раз)
        if self.loaded:
            return True
        if not pygame.mixer.get_init():
            return False
        for key, name in FILES.items():
            self.snd[key] = assets._load_sound(os.path.join(FOLDER, name))
        # Фон: замедленный Redacted "на лету"; запасной вариант - готовый файл
        self.snd["ambient"] = audio_fx.slowed_sound(getattr(assets, "REDACTED_SOUND", None), AMBIENT_RATE) \
            or assets._load_sound(AMBIENT_FALLBACK_FILE)
        self.bpm = read_bpm(self.bpm)
        if pygame.mixer.get_num_channels() < 10:
            pygame.mixer.set_num_channels(10)
        pygame.mixer.set_reserved(4)  # каналы 0-3 - только для музыки режима D01
        self.ch_a = pygame.mixer.Channel(0)
        self.ch_b = pygame.mixer.Channel(1)
        self.ch_c = pygame.mixer.Channel(2)
        self.ch_t = pygame.mixer.Channel(3)
        self.loaded = True
        return True

    # запуск / остановка
    def _stop_channel(self, ch) -> None:
        # stop() дважды: если в очереди канала что-то есть, первый stop запустит его
        ch.stop()
        ch.stop()

    def _stop_main(self) -> None:
        if self.loaded:
            self._stop_channel(self.ch_a)
            self._stop_channel(self.ch_b)

    def _reset_pause(self) -> None:
        self.pstate = "run"
        self.paused = False
        self.fx = 1.0

    def stop_all(self) -> None:
        self._stop_main()
        if self.loaded:
            self._stop_channel(self.ch_c)
            self.ch_t.stop()
        self.mode = None
        self.seg_t0 = None
        self._reset_pause()

    def _start_ambient(self) -> None:
        self.stop_all()
        self.end_done = False
        if self.snd.get("ambient") is not None:
            self.ch_c.play(self.snd["ambient"], loops=-1, fade_ms=AMBIENT_FADE_IN_MS)
        self.amb_t0 = pygame.time.get_ticks()
        self.mode = "ambient"

    def _variant(self, low) -> bool:
        # Какую версию играть: True - LOWHP
        s = self.snd
        have_low = s.get("loop_low") is not None or s.get("intro_low") is not None
        have_norm = s.get("loop") is not None or s.get("intro") is not None
        return (bool(low) and have_low) or not have_norm

    def _play_variant(self, skip_intro=False) -> None:
        # Запускает на канале ТЕКУЩЕЙ версии (use_low) интро -> луп
        s = self.snd
        sfx = "_low" if self.use_low else ""
        intro, loop = s.get("intro" + sfx), s.get("loop" + sfx)
        ch = self.ch_b if self.use_low else self.ch_a
        if skip_intro and loop is not None:
            first = loop
            self.seg_count = 1  # первый "сегмент" (луп) уже идёт
        else:
            first = intro or loop
            self.seg_count = 0
        self.seg_t0 = None  # поставится в _upkeep_boss в кадре старта
        if first is not None:
            ch.play(first)

    def _start_boss(self, low=False, skip_intro=False) -> None:
        self.end_done = False
        was_ambient = self.mode == "ambient"
        self._stop_main()
        self.ch_t.stop()
        self._reset_pause()
        if was_ambient:
            self.ch_c.fadeout(AMBIENT_FADE_OUT_MS)  # фон плавно уходит, а интро босса уже стартует
        else:
            self._stop_channel(self.ch_c)
        self.use_low = self._variant(low)
        self._play_variant(skip_intro)
        self.mode = "boss"

    def restart_boss(self, low=False) -> None:
        # Заново запускает BossIntro -> BossLoop нужной версии
        if self.loaded:
            self._start_boss(low)

    def set_variant(self, low) -> None:
        # Переключает версию боевой музыки БЕЗ интро: сразу луп нужной версии
        if not self.loaded or self.mode != "boss":
            return
        target = self._variant(low)
        if target == self.use_low:
            return
        self._stop_main()
        self.ch_t.stop()
        self._reset_pause()
        self.use_low = target
        self._play_variant(skip_intro=True)

    def intro_length_ms(self, low=False) -> float:
        # Длина интро-музыки (мс); 0 - файла нет
        snd = (self.snd.get("intro_low") if low else None) or self.snd.get("intro") or self.snd.get("intro_low")
        try:
            return snd.get_length() * 1000.0 if snd is not None else 0.0
        except Exception:
            return 0.0

    def in_intro(self) -> bool:
        # Идёт ли сейчас BossIntro (до начала лупа)
        return self.mode == "boss" and (self.seg_t0 is None or self.seg_kind == "intro")

    def _start_end(self, low: bool) -> None:
        self.stop_all()
        self.end_done = True
        s = self.snd
        sound = (s["end_low"] if low else s["end"]) or s["end"] or s["end_low"]
        if sound is not None:
            self.ch_a.play(sound)
        self.mode = "end"

    # раз в кадр
    def update(self, want, low, volume, paused=False) -> None:
        # want: "ambient" | "boss" | "end" | None; low - у игрока мало жизней; volume
        if not self.loaded:
            return

        if want == "boss":
            if self.mode != "boss":
                self._start_boss(low, skip_intro=self.start_in_loop)
        elif want == "end":
            if self.mode != "end" and not self.end_done:
                self._start_end(low)
        elif want == "ambient":
            if self.mode != "ambient":
                self._start_ambient()
        elif self.mode in ("boss", "ambient"):
            self.stop_all()

        self.vol_now = volume * (self.ambient_gain if self.mode == "ambient" else 1.0)
        self._pause_logic(pygame.time.get_ticks(), paused)
        g = self.fx

        if self.mode == "ambient":
            if self.snd.get("ambient") is not None:
                self.snd["ambient"].set_volume(volume * self.ambient_gain * g)
        elif self.mode == "boss":
            self._upkeep_boss(low, volume * g)
        elif self.mode == "end":
            self._set_end_volume(volume)
            if not self.ch_a.get_busy() and self.pstate == "run":
                self.mode = None  # концовка дозвучала

    # пауза: музыка замедляется и разгоняется
    def _main_channels(self):
        return (self.ch_a, self.ch_b, self.ch_c)

    def _position(self, at):
        # (Sound, позиция в нём мс, зациклен ли) для звука
        try:
            if self.mode == "ambient":
                snd = self.snd.get("ambient")
                if snd is None:
                    return None
                length = snd.get_length() * 1000.0
                return snd, (at - self.amb_t0) % length, True
            if self.mode == "boss" and self.seg_t0 is not None:
                base = "intro" if self.seg_kind == "intro" else "loop"
                snd = (self.snd.get(base + "_low") if self.use_low else None) or self.snd.get(base) or self.snd.get(base + "_low")
                if snd is None:
                    return None
                length = snd.get_length() * 1000.0
                pos = at - self.seg_t0
                return (snd, pos % length, True) if self.seg_kind == "loop" else (snd, min(max(pos, 0), length), False)
        except Exception:
            pass
        return None

    def _play_tail(self, kind, at, length_ms) -> bool:
        info = self._position(at)
        if info is None:
            return False
        snd, pos, wrap = info
        tail = audio_fx.tape_tail(snd, pos, length_ms, kind, wrap)
        if tail is None:
            return False
        tail.set_volume(self.vol_now)
        self.ch_t.play(tail)
        return True

    def _set_paused_channels(self, paused: bool) -> None:
        for ch in self._main_channels():
            (ch.pause if paused else ch.unpause)()

    def _shift_clocks(self, delta) -> None:
        if self.seg_t0 is not None:
            self.seg_t0 += delta
        self.amb_t0 += delta

    def _pause_logic(self, now, want_pause) -> None:
        if self.mode is None or self.mode == "end":
            if self.mode == "end" and want_pause != (self.pstate != "run"):
                # концовку просто ставим на паузу / снимаем, без эффектов
                self._set_paused_channels(want_pause)
                self.pstate = "paused" if want_pause else "run"
                self.paused = want_pause
            return

        tapes = audio_fx.available()

        # запросы
        if want_pause and self.pstate in ("run", "xfade_in", "soft_in", "resuming"):
            if self.pstate == "resuming":  # снова пауза, пока разгонялись: основные каналы ещё стоят
                self.ch_t.stop()
                self.pstate = "paused"
            else:
                self.p_t0 = now
                self._soft_from = self.fx
                if tapes and self._play_tail("stop", now, PAUSE_SLOW_MS):
                    self.pstate = "xfade_out"
                else:
                    self.pstate = "soft_out"  # хвост сделать нельзя - плавное затухание
        elif not want_pause and self.pstate in ("paused", "xfade_out", "soft_out"):
            if self.pstate == "paused":
                self.p_t0 = now
                if tapes and self._play_tail("start", self.pause_at, RESUME_SLOW_MS):
                    self.pstate = "resuming"
                    self.resume_at = now + RESUME_SLOW_MS
                else:
                    self._set_paused_channels(False)
                    self._shift_clocks(now - self.pause_at)
                    self.pstate = "soft_in"
                    self._soft_from = 0.0
            else:  # не успели замолчать - просто возвращаем громкость
                self.ch_t.stop()
                self.pstate = "xfade_in" if self.pstate == "xfade_out" else "soft_in"
                self._soft_from = self.fx
                self.p_t0 = now

        # ход времени
        st = self.pstate
        if st == "xfade_out":
            k = (now - self.p_t0) / XFADE_MS
            self.fx = max(0.0, self._soft_from * (1.0 - k))
            if k >= 1:
                self._set_paused_channels(True)
                self.pause_at = now
                self.pstate = "paused"
        elif st == "soft_out":
            k = (now - self.p_t0) / SOFT_FADE_MS
            self.fx = max(0.0, self._soft_from * (1.0 - k))
            if k >= 1:
                self._set_paused_channels(True)
                self.pause_at = now
                self.pstate = "paused"
        elif st == "resuming":
            self.fx = 0.0
            if now >= self.resume_at:
                self._set_paused_channels(False)
                self._shift_clocks(now - self.pause_at)
                self.pstate = "xfade_in"
                self.p_t0 = now
                self._soft_from = 0.0
        elif st == "xfade_in":
            k = (now - self.p_t0) / XFADE_MS
            self.fx = min(1.0, self._soft_from + k * (1.0 - self._soft_from))
            if k >= 1:
                self.pstate = "run"
                self.fx = 1.0
        elif st == "soft_in":
            k = (now - self.p_t0) / SOFT_FADE_MS
            self.fx = min(1.0, self._soft_from + k * (1.0 - self._soft_from))
            if k >= 1:
                self.pstate = "run"
                self.fx = 1.0
        elif st == "paused":
            self.fx = 0.0

        self.paused = self.pstate in ("paused", "resuming", "xfade_out", "soft_out")

    # основной цикл босса
    def _upkeep_boss(self, low, volume) -> None:
        s = self.snd
        # Жизней снова больше одной -> возвращаемся на обычный луп
        if self.use_low and not low:
            self.set_variant(False)
        for key in ("intro", "loop", "intro_low", "loop_low"):
            if s[key] is not None:
                s[key].set_volume(volume if key.endswith("_low") == self.use_low else 0.0)

        # бесшовный луп: следующий повтор всегда стоит в очереди
        ch = self.ch_b if self.use_low else self.ch_a
        sfx = "_low" if self.use_low else ""
        loop, intro = s["loop" + sfx], s["intro" + sfx]
        if loop is None:
            return
        if ch.get_busy():
            if ch.get_queue() is None:
                ch.queue(loop)
                # Очередь опустела ровно тогда, когда началась новая часть
                self.seg_t0 = pygame.time.get_ticks()
                self.seg_count += 1
                self.seg_kind = "intro" if (self.seg_count == 1 and intro is not None) else "loop"
        elif not self.paused:
            ch.play(loop)  # канал замолчал (сбой устройства) - запускаем луп заново

    def beat_pulse(self, every: int) -> float:
        # Сила пульса 0..1: на каждом every-м бите музыки
        if self.mode != "boss" or self.paused or self.seg_t0 is None:
            return 0.0
        beat_ms = 60000.0 / max(1.0, self.bpm)
        el = pygame.time.get_ticks() - self.seg_t0 - BEAT_OFFSET_MS
        if el < 0:
            return 0.0
        idx = int(el // beat_ms)
        since = el - (idx // every * every) * beat_ms  # мс с последнего акцентного бита
        p = 1.0 - since / (beat_ms * PULSE_DECAY_BEATS)
        return p * p if p > 0 else 0.0

    def _set_end_volume(self, volume) -> None:
        for key in ("end", "end_low"):
            if self.snd.get(key) is not None:
                self.snd[key].set_volume(volume)


MUSIC = BossMusic()
