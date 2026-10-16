"""
Marcelly — Controle de recursos do motor local.

O llama-server (motor do Ollama) pode tomar grande parte da CPU em
maquinas modestas e congelar o computador. Aqui mantemos o motor com
prioridade abaixo do normal: o Windows sempre responde primeiro a
interface e aos outros programas — o modelo continua gerando, so
com menos forca. As threads de inferencia sao limitadas em config.py.
"""
import os
import subprocess
import threading
import time

from config import CONFIG
from core.debug import DEBUG

_FLAGS = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_MOTOR_NAMES = ("llama-server", "ollama", "ollama_llama_server")

_SET_PRIORITY_SCRIPT = (
    "foreach ($p in Get-Process -Name "
    + ", ".join("'" + n + "'" for n in _MOTOR_NAMES)
    + " -ErrorAction SilentlyContinue) {"
    " try { $p.PriorityClass = [System.Diagnostics.ProcessPriorityClass]::BelowNormal"
    " } catch {} }"
)


def apply_low_priority() -> bool:
    """Marca o motor local (llama-server) com prioridade abaixo do normal."""
    if os.name != "nt":
        return False
    ok = False
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", _SET_PRIORITY_SCRIPT],
            capture_output=True, text=True, timeout=15, creationflags=_FLAGS,
        )
        ok = result.returncode == 0
    except Exception as e:
        DEBUG.log("error", onde="recursos", erro=str(e))
    DEBUG.log(
        "recursos",
        evento="prioridade_baixa",
        aplicada=ok,
        threads=CONFIG.ollama.num_thread,
    )
    return ok


def start_priority_guard(interval: int = 60):
    """Aplica a prioridade baixa agora e revisa periodicamente em segundo plano
    (o motor do Ollama pode reiniciar e voltar com prioridade normal)."""
    def _loop():
        while True:
            try:
                apply_low_priority()
            except Exception:
                pass
            time.sleep(interval)

    threading.Thread(target=_loop, daemon=True).start()
