# Настраиваемое управление
import pygame

DEFAULT_CONTROLS = {
    "up": ["w", "up"],
    "down": ["s", "down"],
    "left": ["a", "left"],
    "right": ["d", "right"],
    "shoot": ["return", "space"],
    "pause": ["escape", "backspace"],
    "vol_up": ["="],
    "vol_down": ["-"],
    "mute": ["0"],
}
DUAL_ACTIONS = ("up", "down", "left", "right", "shoot", "pause")
SINGLE_ACTIONS = ("vol_up", "vol_down", "mute")
ALL_ACTIONS = DUAL_ACTIONS + SINGLE_ACTIONS
MOVE_ACTIONS = ("up", "down", "left", "right")

ACTION_LABELS = {
    "up": "MOVE UP", "down": "MOVE DOWN", "left": "MOVE LEFT", "right": "MOVE RIGHT",
    "shoot": "SHOOT", "pause": "PAUSE / EXIT",
    "vol_up": "VOLUME +", "vol_down": "VOLUME -", "mute": "MUTE",
}

# Кнопки мыши, которые можно назначить
MOUSE_BUTTONS = {1: "mouse1", 2: "mouse2", 3: "mouse3", 6: "mouse6", 7: "mouse7"}

# Клавиши, которые считаются одной
ALIAS_GROUPS = (
    frozenset({"=", "+", "[+]"}),
    frozenset({"-", "[-]"}),
    frozenset({"0", "[0]"}),
)

# действие игры -> действие интерфейса
MENU_FROM_GAME = {"up": "up", "down": "down", "left": "left", "right": "right", "shoot": "confirm", "pause": "back"}

TOKEN_LABELS = {
    "return": "ENTER", "escape": "ESC", "backspace": "BKSP", "space": "SPACE",
    "up": "UP", "down": "DOWN", "left": "LEFT", "right": "RIGHT",
    "left shift": "L SHIFT", "right shift": "R SHIFT", "left ctrl": "L CTRL", "right ctrl": "R CTRL",
    "left alt": "L ALT", "right alt": "R ALT", "caps lock": "CAPS",
    "mouse1": "MOUSE L", "mouse2": "MOUSE M", "mouse3": "MOUSE R", "mouse6": "MOUSE 4", "mouse7": "MOUSE 5",
}

_DOWN_TYPES = ("KEYDOWN", "MOUSEBUTTONDOWN")
_UP_TYPES = ("KEYUP", "MOUSEBUTTONUP")


def _group(token):
    for g in ALIAS_GROUPS:
        if token in g:
            return g
    return frozenset({token})


def label(token) -> str:
    # Короткое имя бинда для экрана ('' -> '---')
    if not token:
        return "---"
    return TOKEN_LABELS.get(token, str(token).upper())


def is_valid_token(token) -> bool:
    if not isinstance(token, str) or not token:
        return False
    if token.startswith("mouse"):
        return token in MOUSE_BUTTONS.values()
    try:
        pygame.key.key_code(token)
        return True
    except Exception:
        return False


def event_token(event):
    # Имя нажатой/отпущенной клавиши или кнопки мыши (или None)
    t = event.type
    if t in (pygame.KEYDOWN, pygame.KEYUP):
        try:
            name = pygame.key.name(event.key)
        except Exception:
            return None
        return name.lower() if name else None
    if t in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
        return MOUSE_BUTTONS.get(getattr(event, "button", 0))
    return None


def _is_down(event) -> bool:
    return event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN)


def _is_up(event) -> bool:
    return event.type in (pygame.KEYUP, pygame.MOUSEBUTTONUP)


class Controls:
    def __init__(self, g_save=None) -> None:
        self.binds = {}
        self._held = {a: set() for a in ALL_ACTIONS}
        self.load(g_save)

    # загрузка / сохранение
    def _default(self, action):
        slots = 2 if action in DUAL_ACTIONS else 1
        d = list(DEFAULT_CONTROLS[action])
        return (d + [""] * slots)[:slots]

    def load(self, g_save) -> None:
        # Читает бинды из g_save["controls"]
        raw = (g_save or {}).get("controls") if isinstance(g_save, dict) else None
        raw = raw if isinstance(raw, dict) else {}
        used = set()
        self.binds = {}
        for action in ALL_ACTIONS:
            slots = 2 if action in DUAL_ACTIONS else 1
            val = raw.get(action)
            tokens = []
            if isinstance(val, (list, tuple)):
                for t in list(val)[:slots]:
                    t = t.lower() if isinstance(t, str) else t
                    ok = is_valid_token(t) and not (_group(t) & used)
                    tokens.append(t if ok else "")
                    if ok:
                        used |= _group(t)
            tokens = (tokens + [""] * slots)[:slots]
            if not any(tokens):  # действие не должно остаться без бинда
                tokens = self._default(action)
                for t in tokens:
                    if t and (_group(t) & used):
                        tokens = [x if x and not (_group(x) & used) else "" for x in tokens]
                if not any(tokens):
                    tokens = [""] * slots
                for t in tokens:
                    if t:
                        used |= _group(t)
            self.binds[action] = tokens
        self.clear_held()

    def save_to(self, g_save) -> None:
        g_save["controls"] = {a: list(v) for a, v in self.binds.items()}

    def reset(self) -> None:
        self.binds = {a: self._default(a) for a in ALL_ACTIONS}
        self.clear_held()

    # поиск
    def _owner(self, token):
        grp = _group(token)
        for action in ALL_ACTIONS:
            for i, t in enumerate(self.binds[action]):
                if t and t in grp:
                    return action, i
        return None

    def action_of(self, token):
        o = self._owner(token) if token else None
        return o[0] if o else None

    def tokens(self, action):
        return list(self.binds[action])

    # события
    def action_down(self, event):
        # Действие игры, вызванное этим нажатием (клавиша или кнопка мыши), либо None
        if not _is_down(event):
            return None
        action = self.action_of(event_token(event))
        if action:
            self._held[action].add(event_token(event))
        return action

    def action_up(self, event):
        # (действие, полностью_отпущено)
        if not _is_up(event):
            return None, False
        token = event_token(event)
        action = self.action_of(token)
        if not action:
            return None, False
        for held in self._held[action]:
            if held in _group(token):
                self._held[action].discard(held)
                break
        return action, not self._held[action]

    def matches(self, event, action) -> bool:
        # Нажатие подходит действию
        return _is_down(event) and self.action_of(event_token(event)) == action

    def menu_action(self, event):
        # Для меню и настроек: 'up'/'down'/'left'/'right'/'confirm'/'back' или None
        if not _is_down(event):
            return None
        token = event_token(event)
        return MENU_FROM_GAME.get(self.action_of(token)) if token else None

    # опрос реального состояния устройств
    _MOUSE_POLL = {"mouse1": 0, "mouse2": 1, "mouse3": 2, "mouse6": 3, "mouse7": 4}

    def is_held(self, action) -> bool:
        # Зажат ли сейчас хоть один бинд действия
        try:
            keys = pygame.key.get_pressed()
            mouse = pygame.mouse.get_pressed(num_buttons=5)
            for token in self.binds[action]:
                if not token:
                    continue
                for t in _group(token):
                    if t in self._MOUSE_POLL:
                        if mouse[self._MOUSE_POLL[t]]:
                            return True
                    elif keys[pygame.key.key_code(t)]:
                        return True
            return False
        except Exception:
            return True  # опрос недоступен - считаем "зажато", ничего не обрываем

    def sync_action(self, action) -> bool:
        # is_held + забывает устаревшие "зажатые" записи
        held = self.is_held(action)
        if not held:
            self._held[action].clear()
        return held

    def clear_held(self) -> None:
        for a in self._held:
            self._held[a].clear()

    # изменение биндов
    def assign(self, action, slot: int, token) -> str:
        # Назначает token ячейке slot действия
        if action not in self.binds or not is_valid_token(token):
            return "BAD KEY"
        slots = self.binds[action]
        slot = max(0, min(slot, len(slots) - 1))
        previous = slots[slot]
        if previous and token in _group(previous):
            return ""
        owner = self._owner(token)
        message = ""
        if owner:
            o_action, o_slot = owner
            o_slots = self.binds[o_action]
            if o_action == action:  # та же клавиша в соседней ячейке - меняем местами
                o_slots[o_slot] = previous
            elif o_action in DUAL_ACTIONS and any(t for i, t in enumerate(o_slots) if i != o_slot):
                o_slots[o_slot] = ""  # у другого действия остаётся второй бинд
                message = f"TAKEN FROM {ACTION_LABELS[o_action]}"
            elif previous:
                o_slots[o_slot] = previous  # обмен: другое действие получает нашу прежнюю клавишу
                message = f"SWAPPED WITH {ACTION_LABELS[o_action]}"
            else:
                return f"USED BY {ACTION_LABELS[o_action]}"
        slots[slot] = token
        self.clear_held()
        return message

    def clear(self, action, slot: int) -> str:
        # Очищает ячейку
        slots = self.binds.get(action)
        if slots is None or slot >= len(slots):
            return ""
        if not slots[slot]:
            return "ALREADY EMPTY"
        if action in DUAL_ACTIONS and not any(t for i, t in enumerate(slots) if i != slot):
            return "KEEP ONE BIND"
        if action in SINGLE_ACTIONS:
            return "KEEP THE BIND"
        slots[slot] = ""
        self.clear_held()
        return ""
