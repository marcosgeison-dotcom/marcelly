"""
Modo de depuração da Marcelly.
Grava eventos localmente em data/debug.log e mantém os últimos
eventos em memória para o painel de depuração da interface.
"""
import json
import threading
import time
from collections import deque
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
LOG_PATH = DATA_DIR / "debug.log"
STATE_PATH = DATA_DIR / "debug_state.json"


class DebugLog:
    def __init__(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self.events = deque(maxlen=200)
        self.enabled = False
        try:
            if STATE_PATH.exists():
                self.enabled = bool(
                    json.loads(STATE_PATH.read_text(encoding="utf-8")).get("enabled")
                )
        except Exception:
            pass

    def set_enabled(self, value: bool) -> bool:
        self.enabled = bool(value)
        try:
            STATE_PATH.write_text(json.dumps({"enabled": self.enabled}), encoding="utf-8")
        except Exception:
            pass
        self.log("debug_mode", value=self.enabled)
        return self.enabled

    def log(self, kind: str, **data) -> dict:
        event = {"ts": time.time(), "kind": kind, **data}
        with self._lock:
            self.events.append(event)
            if self.enabled:
                try:
                    with LOG_PATH.open("a", encoding="utf-8") as f:
                        f.write(json.dumps(event, ensure_ascii=False) + "\n")
                except Exception:
                    pass
        return event

    def recent(self, limit: int = 100) -> list:
        with self._lock:
            return list(self.events)[-limit:]

    def clear(self):
        with self._lock:
            self.events.clear()


DEBUG = DebugLog()