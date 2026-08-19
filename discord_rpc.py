import os
import sys
import time
import json
import struct

CLIENT_ID = "1539607326724718754"

class DiscordPresence:
    def __init__(self, client_id=CLIENT_ID) -> None:
        self.client_id = client_id
        self.connected = False
        self.start_time = int(time.time())
        self.ipc_file = None
        
        self.connect()

    def connect(self) -> None:
        print(f"[Discord RPC] An attempt to connect to Client ID {self.client_id}...")
        
        try:
            if sys.platform == 'win32':
                pipe_path = r'\\.\pipe\discord-ipc-0'
                self.ipc_file = open(pipe_path, 'w+b')
            else:
                import socket
                pipe_path = os.environ.get('XDG_RUNTIME_DIR', '/tmp') + '/discord-ipc-0'
                self.ipc_file = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                self.ipc_file.connect(pipe_path)

            self.send_payload(0, {'v': 1, 'client_id': self.client_id})
            
            self.connected = True
            print("[Discord RPC] Successfully connected to Discord through IPC!")
            
        except FileNotFoundError:
            print("[Discord RPC] Discord the communication channel is not running or unavailable.")
        except Exception as e:
            print(f"[Discord RPC] Connection error: {e}")

    def send_payload(self, opcode: int, payload: dict) -> None:
        if not self.ipc_file:
            return
            
        payload_json = json.dumps(payload).encode('utf-8')
        header = struct.pack('<II', opcode, len(payload_json))
        
        if sys.platform == 'win32':
            self.ipc_file.write(header + payload_json)
            self.ipc_file.flush()
        else:
            self.ipc_file.sendall(header + payload_json)

    def update(self, app_state: str, game_state: dict = None, current_mode: str = "A01") -> None:
        if not self.connected:
            return

        try:
            details = "In the menu"
            state = f"Mode: {current_mode}"
            large_image = "tt-icon"
            large_text = "Pixel Console"

            if app_state == "SETTINGS":
                details = "In the settings"
                state = "Modifies the parameters"

            elif app_state in ("PLAYING", "FROZEN_GAME", "EXPLODING", "WIN_SHOW") and game_state:
                mode_name = game_state.get("mode", current_mode)
                logic_mode = game_state.get("logic_mode")
                is_paused = game_state.get("paused", False)
                is_boss = (logic_mode and getattr(logic_mode, "is_boss_phase", False)) or str(game_state.get("level")) == "BOSS"
                
                if is_paused:
                    details = f"Pause | Mode {mode_name}"
                elif is_boss:
                    details = f"BATTLE WITH THE BOSS | Mode {mode_name}"
                else:
                    level_val = game_state.get("level", 1)
                    details = f"Playing | Mode {mode_name} | Level {level_val}"

                score = game_state.get("score", 0)
                lives = game_state.get("lives", 0)
                
                if is_boss and logic_mode and getattr(logic_mode, "boss", None):
                    boss = logic_mode.boss
                    boss_hp = max(0, getattr(boss, "hp", 0))
                    boss_max = getattr(boss, "max_hp", boss_hp)
                    state = f"Score: {score} | HP Boss: {boss_hp}/{boss_max} | Lives: {lives}"
                else:
                    kills = game_state.get("kills_this_level", 0)
                    target = game_state.get("target_enemies", 0)
                    state = f"Score: {score} | G O A L: {kills}/{target} | Lives: {lives}"

            activity = {
                "details": details,
                "state": state,
                "assets": {
                    "large_image": large_image,
                    "large_text": large_text
                },
                "timestamps": {
                    "start": self.start_time
                }
            }

            payload = {
                "cmd": "SET_ACTIVITY",
                "args": {
                    "pid": os.getpid(),
                    "activity": activity
                },
                "nonce": str(time.time())
            }

            self.send_payload(1, payload)

        except Exception as e:
            self.connected = False
            print(f"[Discord RPC] Error during the update: {e}")
            self.close()

    def close(self) -> None:
        if self.connected and self.ipc_file:
            try:
                self.send_payload(2, {})
                self.ipc_file.close()
            except Exception:
                pass
            self.ipc_file = None
        self.connected = False