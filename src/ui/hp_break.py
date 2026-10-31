# "Сломанная" шкала жизней: в шкале появляется трещина

# НАСТРОЙКИ
DROP_PERIOD_MS = 400  # новая капля раз в столько мс (один бит Y0U при 150 BPM)
DROP_STEP_MS = 110  # капля опускается на клетку за столько мс

def _cell_exists(model, x, y) -> bool:
    return 0 <= y < len(model) and 0 <= x < len(model[y]) and model[y][x] not in " ."


def crack_cells(model, lit=()):
    # Клетки шкалы, "выломанные" трещиной (горящие клетки жизни не трогаем)
    rows = len(model)
    cols = max((len(r) for r in model), default=0)
    lit = {tuple(c) for c in lit}
    out = set()
    if rows >= 3:
        mid = max(1, rows // 2 - 1)  # трещина выше "дна", где горят последние жизни
        for x in range(cols):
            off = (x * 5 + 2) % 3 - 1 if rows >= 8 else 0  # неровный край трещины: -1, 0 или +1
            ys = {mid + off}
            if x % 2 == 0:
                ys.add(mid + off + 1)
            for y in ys:
                if _cell_exists(model, x, y) and (x, y) not in lit:
                    out.add((x, y))
    elif cols >= 3:  # горизонтальная шкала: трещина - по столбцам
        mid = cols // 2
        for x in (mid, mid + 1):
            for y in range(rows):
                if _cell_exists(model, x, y) and (x, y) not in lit:
                    out.add((x, y))
    return out


def _hash(i: int) -> int:
    return ((i * 2654435761) >> 7) & 0xFFFF


def drops(model, crack, lit, t_ms):
    # Капли, стекающие из трещины вниз: [(x, y), ...]
    rows = len(model)
    if rows < 3 or not crack:
        return []
    lit = {tuple(c) for c in lit}
    top = {}
    for x, y in crack:
        top[x] = min(top.get(x, rows), y)  # капля появляется в верхней клетке трещины
    xs = sorted(top)
    t_ms = int(t_ms)
    i_now = t_ms // DROP_PERIOD_MS
    life_periods = (DROP_STEP_MS * rows) // DROP_PERIOD_MS + 1
    out = []
    for i in range(max(0, i_now - life_periods), i_now + 1):
        x = xs[_hash(i) % len(xs)]
        age = t_ms - i * DROP_PERIOD_MS
        y = top[x] + age // DROP_STEP_MS
        if 0 <= y < rows and (x, y) not in lit:
            out.append((x, int(y)))
    return out


def break_bar(model, lit, t_ms):
    lit = [tuple(c) for c in lit]
    crack = crack_cells(model, lit)
    rows = []
    for y, row in enumerate(model):
        rows.append("".join(" " if (x, y) in crack else ch for x, ch in enumerate(row)))
    cells = lit + [d for d in drops(model, crack, lit, t_ms) if d not in lit]
    return tuple(rows), cells
