"""
Configuração local do Marcelly.
Nenhum dado é enviado para servidores externos por padrão.
"""
import os
import sys
from dotenv import load_dotenv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

load_dotenv()


def _persistent_data_dir() -> Path:
    """Pasta de dados persistente. No executavel (PyInstaller onefile),
    Path(__file__) vive numa pasta temporaria apagada ao fechar o app —
    por isso memoria, lembretes, e-mail e debug ficam em LOCALAPPDATA."""
    if getattr(sys, "frozen", False):
        base = os.getenv("LOCALAPPDATA") or os.path.expanduser("~")
        return Path(base) / "Marcelly" / "data"
    return Path(__file__).parent / "data"


DATA_DIR = _persistent_data_dir()


def _total_ram_gb() -> float:
    """RAM total instalada; usada para escolher um modelo que caiba na memoria."""
    try:
        if os.name == "nt":
            import ctypes

            class _MemStatus(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            st = _MemStatus()
            st.dwLength = ctypes.sizeof(_MemStatus)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st))
            return st.ullTotalPhys / (1024 ** 3)
        return (os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")) / (1024 ** 3)
    except Exception:
        return 16.0


_TOTAL_RAM_GB = _total_ram_gb()
# Maquinas com pouca RAM: modelo de 1 bilhao de parametros (~1 GB na memoria)
# em vez do de 3 bi (~2 GB). Dois modelos grandes + pouca RAM fazem o Windows
# "abafar" no disco e o computador travar — o modelo leve evita isso.
_AUTO_MODEL = "llama3.2:1b" if _TOTAL_RAM_GB <= 8 else "llama3.2:3b"


@dataclass


@dataclass
class OllamaConfig:
    host: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    model: str = os.getenv("MARCELY_MODEL", "qwen2.5:1.5b")
    decision_model: str = os.getenv("MARCELY_DECISION_MODEL", "qwen2.5:1.5b")
    temperature: float = 0.2
    # Limite de threads por resposta: em maquinas modestas o llama-server
    # toma quase metade da CPU e congela tudo. Padrao: 2 a 4 threads.
    num_thread: int = int(os.getenv("MARCELY_NUM_THREADS", "0")) or max(2, min(4, (os.cpu_count() or 4) // 2))


@dataclass
class EmailConfig:
    """Configuração de e-mail: por variáveis de ambiente ou pelo chat
    (salva apenas neste computador, em data/email_config.json)."""
    imap_host: Optional[str] = os.getenv("IMAP_HOST")
    imap_port: int = int(os.getenv("IMAP_PORT", "993"))
    smtp_host: Optional[str] = os.getenv("SMTP_HOST")
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    username: Optional[str] = os.getenv("EMAIL_USER")
    # Senha lida apenas de variável de ambiente em memória
    password: Optional[str] = os.getenv("EMAIL_PASS")
    max_emails: int = 50


@dataclass
class CloudConfig:
    """Fallback opcional para perguntas complexas."""
    api_key: Optional[str] = os.getenv("DEEPSEEK_API_KEY")
    base_url: str = os.getenv("MARCELY_CLOUD_BASE_URL", "https://api.deepseek.com")
    model: str = os.getenv("MARCELY_CLOUD_MODEL", "deepseek-chat")
    ram_threshold: float = float(os.getenv("MARCELY_CLOUD_RAM_THRESHOLD", "85"))


@dataclass
class MarcellyConfig:
    ollama: OllamaConfig = field(default_factory=OllamaConfig)
    email: EmailConfig = field(default_factory=EmailConfig)
    cloud: CloudConfig = field(default_factory=CloudConfig)
    log_level: str = os.getenv("MARCELY_LOG", "INFO")
    confirm_sensitive_actions: bool = True
    local_only: bool = False  # perguntas complexas podem usar a DeepSeek se a chave estiver configurada


CONFIG = MarcellyConfig()