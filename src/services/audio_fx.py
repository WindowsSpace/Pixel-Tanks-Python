# Звуковые эффекты "на лету" для музыки режима D01

import pygame

try:
    import numpy as np
except Exception:  # numpy не установлен
    np = None
try:
    import audioop  # есть в Python < 3.13
except Exception:
    audioop = None

# НАСТРОЙКИ
SLOW_ECHO_MS = 70  # эхо замедленного звука: задержка
SLOW_ECHO_GAIN = 0.35  # ...и громкость повтора (0 - без эха)
SLOW_SMOOTH = 4  # сглаживание (простой фильтр высоких частот), число отсчётов
SLOW_FADE_IN_MS = 2000  # плавное начало и конец, чтобы повтор по кругу не "щёлкал"
SLOW_FADE_OUT_MS = 2500
_cache = {}  # id(Sound) -> (Sound, массив отсчётов)


def mixer_format():
    # (частота, каналы) микшера или None, если формат нам не подходит
    try:
        freq, fmt, ch = pygame.mixer.get_init()
    except Exception:
        return None
    if fmt != -16 or ch not in (1, 2):
        return None
    return freq, ch


def available() -> bool:
    return np is not None and mixer_format() is not None


def _samples(sound):
    # Отсчёты звука как массив int16 формы (n, каналы). Кэшируется
    key = id(sound)
    if key not in _cache:
        freq, ch = mixer_format()
        arr = np.frombuffer(sound.get_raw(), dtype=np.int16)
        _cache[key] = (sound, arr[: len(arr) // ch * ch].reshape(-1, ch))  # сам Sound держим, чтобы id не переиспользовался
    return _cache[key][1]


def _to_sound(data):
    return pygame.mixer.Sound(buffer=bytes(np.clip(data, -32768, 32767).astype(np.int16).tobytes()))


def slowed_sound(sound, rate: float = 0.55):
    # Замедленная в 1/rate раз копия звука (тон падает вместе с темпом)
    try:
        fmt = mixer_format()
        if sound is None or fmt is None:
            return None
        freq, ch = fmt
        if np is not None:
            src = _samples(sound).astype(np.float32)
            n = len(src)
            m = int(n / rate)
            pos = np.arange(m, dtype=np.float64) * rate
            i0 = np.minimum(pos.astype(np.int64), n - 1)
            i1 = np.minimum(i0 + 1, n - 1)
            fr = (pos - i0).astype(np.float32)[:, None]
            out = src[i0] * (1 - fr) + src[i1] * fr
            if SLOW_SMOOTH > 1:  # скользящее среднее = мягкий "глухой" тон
                k = SLOW_SMOOTH
                pad = np.cumsum(np.pad(out, ((k, 0), (0, 0))), axis=0)
                out = (pad[k:] - pad[:-k]) / k
            d = int(freq * SLOW_ECHO_MS / 1000)
            if SLOW_ECHO_GAIN > 0 and 0 < d < m:
                tmp = out.copy()
                out[d:] += SLOW_ECHO_GAIN * tmp[:-d]
                out /= (1 + SLOW_ECHO_GAIN)  # чтобы эхо не добавляло громкости
            env = np.ones(m, dtype=np.float32)
            fi, fo = int(freq * SLOW_FADE_IN_MS / 1000), int(freq * SLOW_FADE_OUT_MS / 1000)
            if 0 < fi < m:
                env[:fi] = np.linspace(0, 1, fi, dtype=np.float32)
            if 0 < fo < m:
                env[-fo:] = np.minimum(env[-fo:], np.linspace(1, 0, fo, dtype=np.float32))
            return _to_sound(out * env[:, None])
        if audioop is not None:  # запасной путь: просто растянуть, без эха
            out, _ = audioop.ratecv(sound.get_raw(), 2, ch, freq, int(round(freq / rate)), None)
            return pygame.mixer.Sound(buffer=out)
    except Exception:
        pass
    return None


def tape_tail(sound, pos_ms: float, length_ms: int, kind: str, wrap: bool):
    # Хвост "плёнки" из звука sound в позиции pos_ms
    try:
        if np is None or sound is None or mixer_format() is None:
            return None
        freq, ch = mixer_format()
        src = _samples(sound)
        n = len(src)
        if n < 2:
            return None
        count = int(freq * length_ms / 1000)
        t = np.arange(count, dtype=np.float64) / count  # 0..1
        if kind == "stop":
            src_ms = pos_ms + (t - t * t / 2) * length_ms  # скорость 1 -> 0
            gain = (1 - t) ** 0.8
        else:
            src_ms = pos_ms - length_ms / 2 + (t * t / 2) * length_ms  # скорость 0 -> 1, финиш ровно в pos_ms
            gain = t ** 0.8
        idx = src_ms / 1000.0 * freq
        i0 = np.floor(idx).astype(np.int64)
        fr = (idx - i0).astype(np.float32)[:, None]
        if wrap:
            i0 %= n
            i1 = (i0 + 1) % n
        else:
            i0 = np.clip(i0, 0, n - 1)
            i1 = np.clip(i0 + 1, 0, n - 1)
        out = src[i0].astype(np.float32) * (1 - fr) + src[i1].astype(np.float32) * fr
        out *= gain.astype(np.float32)[:, None]
        return _to_sound(out)
    except Exception:
        return None


def sped_sound(sound, rate: float = 3.0):
    # Ускоренная в rate раз копия звука (тон растёт вместе с темпом)
    try:
        fmt = mixer_format()
        if sound is None or fmt is None or np is None:
            return None
        src = _samples(sound)
        n = len(src)
        pos = (np.arange(int(n / rate), dtype=np.float64) * rate).astype(np.int64)
        return _to_sound(src[np.minimum(pos, n - 1)])
    except Exception:
        return None
