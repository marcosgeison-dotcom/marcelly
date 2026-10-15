"""
Configuração local do Marcelly.
Nenhum dado é enviado para servidores externos por padrão.
"""
import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class OllamaConfig:
    host: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    model: str = os.getenv("MARCELY_MODEL", "llama3.2:8b")
    decision_model: str = os.getenv("MARCELY_DECISION_MODEL", "qwen2.5:3b")
    temperature: float = 0.3


@dataclass
class EmailConfig:
    """Configuração de e-mail. Senhas nunca são gravadas em disco."""
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