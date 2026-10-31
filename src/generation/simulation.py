# Симуляция "игрок расчищает блоки": какие блоки можно прострелить, проезды


from collections import deque
import random

from generation.grid_ops import _NEIGH9, _center_mask


# СИМУЛЯЦИЯ ДЛЯ БЛОКОВ
def _stuck_blocks(w, h, floor, center, blk, start):
    # Симуляция: возвращает множество индексов блоков
    blk = bytearray(blk)
    N = w * h
    dirs = (1, -1, w, -w)
    neigh = _NEIGH9(w)
    remaining = [i for i in range(N) if blk[i]]

    while remaining:
        cnt = [0] * N  # сколько блоков попадает в квадрат 3x3 вокруг клетки
        for b in remaining:
            for off in neigh:
                cnt[b + off] += 1

        reach = bytearray(N)
        if center[start] and not cnt[start]:
            reach[start] = 1
            q = deque([start])
            while q:
                cur = q.popleft()
                for d in dirs:
                    n = cur + d
                    if center[n] and not reach[n] and not cnt[n]:
                        reach[n] = 1
                        q.append(n)

        shootable, rest = [], []
        for b in remaining:
            ok = False
            for d in dirs:
                p, k = b + d, 1
                while floor[p] and not blk[p]:
                    if k >= 2 and reach[p]:  # танк стоит в p, ствол смотрит на блок
                        ok = True
                        break
                    p += d
                    k += 1
                if ok:
                    break
            (shootable if ok else rest).append(b)

        if not shootable:
            return set(rest)
        for b in shootable:
            blk[b] = 0
        remaining = rest
    return set()


def _reach_with_blocks(w, h, center, blk, start):
    N = w * h
    neigh = _NEIGH9(w)
    cnt = [0] * N
    for b in range(N):
        if blk[b]:
            for off in neigh:
                cnt[b + off] += 1
    reach = bytearray(N)
    if center[start] and not cnt[start]:
        reach[start] = 1
        q = deque([start])
        while q:
            cur = q.popleft()
            for d in (1, -1, w, -w):
                n = cur + d
                if center[n] and not reach[n] and not cnt[n]:
                    reach[n] = 1
                    q.append(n)
    return reach


def _open_lanes(w, h, center, blk, start, targets):
    # Гарантирует, что от игрока к каждому спавну врага есть проезд без стрельбы
    neigh = _NEIGH9(w)
    for t in targets:
        reach = _reach_with_blocks(w, h, center, blk, start)
        if reach[t]:
            continue
        parent = {t: None}
        q = deque([t])
        found = None
        while q:
            cur = q.popleft()
            if reach[cur]:
                found = cur
                break
            for d in (1, -1, w, -w):
                n = cur + d
                if center[n] and n not in parent:
                    parent[n] = cur
                    q.append(n)
        c = found
        while c is not None:
            for off in neigh:
                blk[c + off] = 0
            c = parent[c]

def pick_respawn_point(board, block_cells, origin, avoid_points=(), min_dist=10):
    # Случайное безопасное место для возрождения игрока: свободный центр 3x3
    h = len(board)
    w = len(board[0])
    N = w * h
    grid = [[board[y][x] == 'X' for x in range(w)] for y in range(h)]
    center = _center_mask(grid, w, h)

    blk = bytearray(N)
    for (x, y) in block_cells:
        if 0 <= x < w and 0 <= y < h:
            blk[y * w + x] = 1

    start = origin[1] * w + origin[0]
    reach = _reach_with_blocks(w, h, center, blk, start)
    cells = [i for i in range(N) if reach[i]]
    if not cells:
        return origin

    def man_min(i):
        x, y = i % w, i // w
        return min((abs(x - ax) + abs(y - ay) for ax, ay in avoid_points), default=10 ** 9)

    d = min_dist
    while d >= 0:
        good = [i for i in cells if man_min(i) >= d]
        if good:
            c = random.choice(good)
            return (c % w, c // w)
        d = d // 2 if d > 1 else -1
    return origin
