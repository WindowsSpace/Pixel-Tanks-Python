# Виды шкалы HP (HP_MODELS) и их динамическое создание


# Виды шкалы HP ('X' - клетка жизни)
HP_MODELS: dict[str, list[str]] = {
    "4x4":  ["XXXX"] * 4,
    "1x16": ["X"] * 16,
    "2x8":  ["XX"] * 8,
    "8x2":  ["XXXXXXXX"] * 2,
    "16x1": ["X" * 16],
    "plus": [" X ", "XXX", " X "],  # пример "фигурной" шкалы
}
HP_DEFAULT = "4x4"
HP_MAX_CELLS = 64

def make_hp_model(cols: int, rows: int) -> list[str]:
    # Прямоугольная шкала HP "на лету": cols столбцов x rows строк
    cols, rows = max(1, min(int(cols), 32)), max(1, min(int(rows), 32))
    while cols * rows > HP_MAX_CELLS:
        rows = max(1, rows - 1)
    return ["X" * cols for _ in range(rows)]

def get_hp_model(style) -> list[str]:
    # Модель шкалы HP по описанию style: - имя из HP_MODELS ("4x4", "1x16", ...)
    if isinstance(style, (list, tuple)) and style and all(isinstance(r, str) for r in style):
        rows = [str(r) for r in style]
    elif isinstance(style, str):
        key = style.strip()
        if key in HP_MODELS:
            rows = HP_MODELS[key]
        elif key.lower() in HP_MODELS:
            rows = HP_MODELS[key.lower()]
        else:
            import re
            m = re.fullmatch(r"(\d+)\s*[xх×]\s*(\d+)", key.lower())
            rows = make_hp_model(int(m.group(1)), int(m.group(2))) if m else HP_MODELS[HP_DEFAULT]
    else:
        rows = HP_MODELS[HP_DEFAULT]
    if not any(ch not in " ." for r in rows for ch in r):
        rows = HP_MODELS[HP_DEFAULT]
    # ограничиваем число клеток
    cells = 0
    out = []
    for r in rows:
        keep = ''.join(ch for ch in r)
        cells += sum(1 for ch in keep if ch not in " .")
        out.append(keep)
        if cells >= HP_MAX_CELLS:
            break
    return out
