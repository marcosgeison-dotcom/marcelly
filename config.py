"""
Configuração local do Marcelly.
Nenhum dado é enviado para servidores externos por padrão.
"""
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


def _persistent_data_dir() -> Path:
    """Pasta de dados persistente. No executavel (PyInstaller onefile),
    Path(__file__) vive numa pasta temporaria apagada ao fechar o app —
    por isso memoria, lembretes, e-mail e debug ficam em LOCALAPPDATA."""
    if getattr(sys, "frozen", False):
        base = os.getenv("LOCALAPPDATA") or os.path.expanduser("~")
        return Path(base) / "Marcelly" / "data"
    return Path(__file__).parent / "data"


DATA_DIR = _persistent_data_dir()


@dataclass
class OllamaConfig:
    host: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    model: str = os.getenv("MARCELY_MODEL", "llama3.2:3b")
    decision_model: str = os.getenv("MARCELY_DECISION_MODEL", "qwen2.5:3b")
    temperature: float = 0.3
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
class MarcellyConfig:
    ollama: OllamaConfig = field(default_factory=OllamaConfig)
    email: EmailConfig = field(default_factory=EmailConfig)
    log_level: str = os.getenv("MARCELY_LOG", "INFO")
    confirm_sensitive_actions: bool = True
    local_only: bool = True  # garante que nenhuma chamada externa seja feita


CONFIG = MarcellyConfig()