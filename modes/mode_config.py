import importlib

def get_mode_class(mode_id:str):
    import modes.mode_a
    import modes.mode_b
    import modes.mode_c
    import modes.mode_d

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
        }
        module_name = letter_module_map.get(letter)
        if module_name is None:
            return None

        module = importlib.import_module(f'modes.{module_name}')
        class_name = f"Mode{mode_id.upper()}"
        return getattr(module, class_name, None)

    return getattr(importlib.import_module('modes.mode_a'), 'ModeA01', None)