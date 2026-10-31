# Операции над сеткой: проходимые для танка 3x3 области, связность


from collections import deque


# ХОЛСТ И ОЧИСТКА ПОД ТАНК 3x3 (не зависят от параметров)
def _carve(g, w, h, x0, y0, x1, y1, value=True):
    # Заполняет прямоугольник [x0..x1]x[y0..y1] (включительно)
    x0, x1 = max(1, min(x0, x1)), min(w - 2, max(x0, x1))
    y0, y1 = max(1, min(y0, y1)), min(h - 2, max(y0, y1))
    for y in range(y0, y1 + 1):
        row = g[y]
        for x in range(x0, x1 + 1):
            row[x] = value


def _center_mask(g, w, h):
    # Плоский массив: 1, если вокруг клетки полностью свободный квадрат 3x3
    hz = [[0] * w for _ in range(h)]
    for y in range(h):
        row, out = g[y], hz[y]
        for x in range(1, w - 1):
            out[x] = 1 if (row[x - 1] and row[x] and row[x + 1]) else 0
    c = bytearray(w * h)
    for y in range(1, h - 1):
        up, mid, dn = hz[y - 1], hz[y], hz[y + 1]
        base = y * w
        for x in range(1, w - 1):
            if up[x] and mid[x] and dn[x]:
                c[base + x] = 1
    return c


def _largest_component(center, w, h):
    N = w * h
    seen = bytearray(N)
    best = []
    steps = (1, -1, w, -w)
    for i in range(N):
        if center[i] and not seen[i]:
            comp = [i]
            seen[i] = 1
            q = deque([i])
            while q:
                cur = q.popleft()
                for d in steps:
                    n = cur + d
                    if center[n] and not seen[n]:
                        seen[n] = 1
                        comp.append(n)
                        q.append(n)
            if len(comp) > len(best):
                best = comp
    return best


def _NEIGH9(w):
    return [dy * w + dx for dy in (-1, 0, 1) for dx in (-1, 0, 1)]


def _rebuild(comp, w, h):
    # Пол = объединение квадратов 3x3 вокруг достижимых центров. Недостижимые "огрызки" исчезают.
    floor = bytearray(w * h)
    for c in comp:
        for off in _NEIGH9(w):
            floor[c + off] = 1
    center = bytearray(w * h)
    for c in comp:
        center[c] = 1
    return floor, center


def _bfs_dist(center, start, w, h):
    dist = {start: 0}
    q = deque([start])
    steps = (1, -1, w, -w)
    while q:
        cur = q.popleft()
        for d in steps:
            n = cur + d
            if center[n] and n not in dist:
                dist[n] = dist[cur] + 1
                q.append(n)
    return dist
