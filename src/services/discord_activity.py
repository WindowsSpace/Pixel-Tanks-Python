# Discord Rich Presence для игры (класс DiscordActivity)
import json
import os
import struct
import sys
import threading
import time

from core import settings

OP_HANDSHAKE, OP_FRAME, OP_CLOSE, OP_PING, OP_PONG = 0, 1, 2, 3, 4

DEFAULT_CLIENT_ID = "1539607326724718754"
DEFAULT_ASSETS = {
    "large": "tt-icon",
    "large_text": "Pixel Console",
    # Ключи маленькой иконки по состояниям
    "small": {},
}
GAME_STATES = ("PLAYING", "FROZEN_GAME", "EXPLODING", "WIN_SHOW")


def _clip(text: str, limit: int = 128) -> str:
    # Discord принимает строки 2...128 символов
    text = " ".join(str(text).split())
    if len(text) < 2:
        text = (text + "  ")[:2] if text else "--"
    return text[:limit]


# канал IPC
class _Ipc:
    # Один канал связи с Discord (именованный канал Windows или unix-сокет)

    def __init__(self) -> None:
        self.sock = None
        self.file = None

    @staticmethod
    def candidates():
        if sys.platform == "win32":
            return [rf"\\.\pipe\discord-ipc-{i}" for i in range(10)]
        bases = [os.environ.get(k) for k in ("XDG_RUNTIME_DIR", "TMPDIR", "TMP", "TEMP")] + ["/tmp"]
        subdirs = ("", "app/com.discordapp.Discord/", "app/com.discordapp.DiscordCanary/",
                   "snap.discord/", "snap.discord-canary/")
        out = []
        for base in dict.fromkeys(b for b in bases if b):
            for sub in subdirs:
                for i in range(10):
                    out.append(os.path.join(base, sub, f"discord-ipc-{i}"))
        return out

    def open(self, timeout: float = 3.0) -> bool:
        for path in self.candidates():
            try:
                if sys.platform == "win32":
                    if not os.path.exists(path):
                        continue
                    self.file = open(path, "r+b", buffering=0)
                else:
                    import socket
                    if not os.path.exists(path):
                        continue
                    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    s.settimeout(timeout)
                    s.connect(path)
                    self.sock = s
                return True
            except OSError:
                self.close()
        return False

    def _read_exact(self, n: int) -> bytes:
        buf = b""
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf)) if self.sock else self.file.read(n - len(buf))
            if not chunk:
                raise ConnectionError("channel closed")
            buf += chunk
        return buf

    def send(self, op: int, payload: dict) -> None:
        data = json.dumps(payload).encode("utf-8")
        frame = struct.pack("<II", op, len(data)) + data
        if self.sock:
            self.sock.sendall(frame)
        else:
            self.file.write(frame)

    def recv(self):
        op, length = struct.unpack("<II", self._read_exact(8))
        body = self._read_exact(length) if length else b""
        return op, (json.loads(body.decode("utf-8")) if body else {})

    def close(self) -> None:
        for obj in (self.sock, self.file):
            try:
                if obj:
                    obj.close()
            except Exception:
                pass
        self.sock = self.file = None


# класс активности
class DiscordActivity:
    def __init__(self, client_id=None, enabled=None, assets=None, min_interval=None, autostart: bool = True) -> None:
        self.client_id = str(client_id or getattr(settings, "DISCORD_CLIENT_ID", DEFAULT_CLIENT_ID))
        self.enabled = bool(getattr(settings, "DISCORD_ENABLED", True) if enabled is None else enabled)
        self.assets = dict(DEFAULT_ASSETS)
        self.assets.update(getattr(settings, "DISCORD_ASSETS", {}) or {})
        if assets:
            self.assets.update(assets)
        self.min_interval = float(getattr(settings, "DISCORD_MIN_INTERVAL", 4.0) if min_interval is None else min_interval)

        self.session_start = int(time.time())
        self._game_ref = None  # какая игра идёт сейчас (для отсчёта времени игры)
        self._game_start = self.session_start

        self.connected = False
        self._cond = threading.Condition()
        self._pending = None  # последнее состояние, ожидающее отправки
        self._last_built = None  # последнее переданное в поток (чтобы не слать одно и то же)
        self._stop = False
        self._thread = None
        if self.enabled and autostart:
            self.start()

    # жизненный цикл
    def start(self) -> None:
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, name="discord-activity", daemon=True)
            self._thread.start()

    def close(self) -> None:
        with self._cond:
            self._stop = True
            self._cond.notify_all()
        t = self._thread
        if t is not None and t.is_alive():
            t.join(timeout=2.0)
        self._thread = None

    # что показывать (чистая функция состояния)
    def build(self, app_state: str, game_state=None, current_mode: str = "A01", now=None) -> dict:
        details = "In the menu"
        state = f"Mode: {current_mode}"
        small_key = "menu"
        start = self.session_start

        if app_state == "SETTINGS":
            details, state, small_key = "In the settings", "Modifies the parameters", "settings"

        elif app_state in GAME_STATES and game_state:
            mode_name = game_state.get("mode", current_mode)
            logic = game_state.get("logic_mode")
            paused = bool(game_state.get("paused", False))
            is_boss = bool(logic and getattr(logic, "is_boss_phase", False)) or str(game_state.get("level")) == "BOSS"
            score = game_state.get("score", 0)
            lives = game_state.get("lives", 0)

            if game_state is not self._game_ref:  # началась новая игра - время считаем заново
                self._game_ref = game_state
                self._game_start = int(now if now is not None else time.time())
            start = self._game_start

            if app_state == "WIN_SHOW":
                details, state, small_key = f"Victory! | Mode {mode_name}", f"Score: {score}", "win"
            elif paused:
                details, small_key = f"Pause | Mode {mode_name}", "paused"
            elif is_boss:
                details, small_key = f"BATTLE WITH THE BOSS | Mode {mode_name}", "boss"
            else:
                level = logic.get_level_text() if logic and hasattr(logic, "get_level_text") else game_state.get("level", 1)
                label = f"Level {level}" if str(level).isdigit() else str(level)
                details, small_key = f"Playing | Mode {mode_name} | {label}", "playing"

            if app_state != "WIN_SHOW":
                boss = getattr(logic, "boss", None) if logic else None
                if is_boss and boss is not None:
                    hp = max(0, getattr(boss, "hp", 0))
                    state = f"Score: {score} | HP Boss: {hp}/{getattr(boss, 'max_hp', hp)} | Lives: {lives}"
                else:
                    kills, target = game_state.get("kills_this_level", 0), game_state.get("target_enemies", 0)
                    state = f"Score: {score} | G O A L: {kills}/{target} | Lives: {lives}"
        else:
            self._game_ref = None

        images = {"large_image": self.assets["large"], "large_text": self.assets["large_text"]}
        small = (self.assets.get("small") or {}).get(small_key)
        if small:
            images["small_image"] = small
            images["small_text"] = _clip(small_key.capitalize())
        return {
            "details": _clip(details),
            "state": _clip(state),
            "assets": images,
            "timestamps": {"start": int(start)},
        }

    # вызывается из игрового цикла (быстро, без ввода-вывода)
    def update(self, app_state: str, game_state=None, current_mode: str = "A01") -> None:
        if not self.enabled or self._stop:
            return
        activity = self.build(app_state, game_state, current_mode)
        if activity == self._last_built:
            return
        self._last_built = activity
        with self._cond:
            self._pending = activity
            self._cond.notify_all()

    # фоновый поток
    def _run(self) -> None:
        ipc = None
        retry_delay, next_try = 3.0, 0.0
        last_sent = 0.0
        shown = None  # что сейчас видит Discord
        while True:
            with self._cond:
                if self._stop:
                    break
                if self._pending is None or self._pending == shown:
                    self._cond.wait(timeout=1.0)
                    continue
                activity = self._pending

            if ipc is None:  # (пере)подключаемся с нарастающей паузой
                pause = next_try - time.monotonic()
                if pause > 0:
                    with self._cond:
                        if not self._stop:
                            self._cond.wait(timeout=min(1.0, pause))
                    continue
                ipc = self._connect()
                if ipc is None:
                    next_try = time.monotonic() + retry_delay
                    retry_delay = min(60.0, retry_delay * 1.7)
                    continue
                retry_delay, shown = 3.0, None

            wait = self.min_interval - (time.monotonic() - last_sent)
            if wait > 0:  # лимит частоты; за это время могло появиться более свежее
                with self._cond:
                    if not self._stop:
                        self._cond.wait(timeout=wait)
                continue

            try:
                self._send_activity(ipc, activity)
            except Exception:
                ipc = self._drop(ipc)
                shown = None
                next_try = time.monotonic() + retry_delay
                continue
            shown, last_sent = activity, time.monotonic()
            with self._cond:
                if self._pending == activity:
                    self._pending = None

        # завершение: очистить статус и закрыть канал
        if ipc is not None:
            try:
                self._send_activity(ipc, None)
            except Exception:
                pass
            try:
                ipc.send(OP_CLOSE, {})
            except Exception:
                pass
            ipc.close()
        self.connected = False

    def _connect(self):
        ipc = _Ipc()
        try:
            if not ipc.open():
                return None
            ipc.send(OP_HANDSHAKE, {"v": 1, "client_id": self.client_id})
            for _ in range(5):  # ждём READY
                op, data = ipc.recv()
                if op == OP_CLOSE:
                    raise ConnectionError(data)
                if op == OP_FRAME and data.get("evt") == "READY":
                    self.connected = True
                    return ipc
                if op == OP_FRAME and data.get("evt") == "ERROR":
                    raise ConnectionError(data)
                if op == OP_PING:
                    ipc.send(OP_PONG, data)
            raise ConnectionError("no READY")
        except Exception:
            ipc.close()
            self.connected = False
            return None

    def _send_activity(self, ipc, activity) -> None:
        ipc.send(OP_FRAME, {
            "cmd": "SET_ACTIVITY",
            "args": {"pid": os.getpid(), "activity": activity},
            "nonce": f"{time.time():.6f}",
        })
        for _ in range(5):  # читаем ответ, чтобы канал не копил данные
            op, data = ipc.recv()
            if op == OP_PING:
                ipc.send(OP_PONG, data)
                continue
            if op == OP_CLOSE:
                raise ConnectionError(data)
            if op == OP_FRAME and data.get("cmd") == "SET_ACTIVITY":
                if data.get("evt") == "ERROR":
                    raise ConnectionError(data)
                return
        raise ConnectionError("no reply")

    def _drop(self, ipc):
        try:
            ipc.close()
        finally:
            self.connected = False
        return None
