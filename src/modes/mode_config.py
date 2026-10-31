import importlib
import pkgutil
import re

MODE_CLASS_NAME = re.compile(r"Mode([A-Z])(\d+)")


def all_mode_ids() -> list[str]:
    # берём режимы прямо из кода: класс ModeA01 -> "A01", новый режим появится сам
    import modes
    ids = set()
    for info in pkgutil.iter_modules(modes.__path__):
        if not re.fullmatch(r"mode_[a-z]", info.name):
            continue
        module = importlib.import_module(f"modes.{info.name}")
        for name in dir(module):
            m = MODE_CLASS_NAME.fullmatch(name)
            if m and isinstance(getattr(module, name), type):
                ids.add(name[4:])
    return sorted(ids, key=lambda i: (i[0], int(i[1:])))


def get_mode_class(mode_id:str):
    import modes.mode_a
    import modes.mode_b
    import modes.mode_c
    import modes.mode_e
    import modes.mode_d
    import modes.mode_f

    if not mode_id:
        return None

    if mode_id[0].isalpha():
        letter = mode_id[0].upper()
        letter_module_map = {
            'A': 'mode_a',
            'B': 'mode_b',
            'C': 'mode_c',
            'D': 'mode_d',
            'E': 'mode_e',
            'F': 'mode_f',
        }
        module_name = letter_module_map.get(letter)
        if module_name is None:
            return None

        module = importlib.import_module(f'modes.{module_name}')
        class_name = f"Mode{mode_id.upper()}"
        return getattr(module, class_name, None)

    return getattr(importlib.import_module('modes.mode_a'), 'ModeA01', None)