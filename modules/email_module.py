"""
Módulo de e-mail local-first.
Conecta via IMAP/SMTP, classifica e-mails e pré-redige respostas.
Nenhum dado sai da máquina — o modelo roda via Ollama.
"""
import email
import json
import re
from dataclasses import dataclass
from email.header import decode_header
from pathlib import Path
from typing import Optional

from imapclient import IMAPClient

from config import CONFIG, DATA_DIR
from core.ollama_client import OllamaClient

# Dados de acesso informados pelo usuário no chat são salvos APENAS neste
# computador (arquivo local em data/) — nunca vão para a nuvem.
CONFIG_FILE = DATA_DIR / "email_config.json"

# Servidores IMAP conhecidos — deduz o host quando o usuário só diz o provedor
KNOWN_IMAP_HOSTS = {
    "gmail.com": "imap.gmail.com",
    "googlemail.com": "imap.gmail.com",
    "outlook.com": "outlook.office365.com",
    "outlook.com.br": "outlook.office365.com",
    "hotmail.com": "outlook.office365.com",
    "hotmail.com.br": "outlook.office365.com",
    "live.com": "outlook.office365.com",
    "msn.com": "outlook.office365.com",
    "yahoo.com": "imap.mail.yahoo.com",
    "yahoo.com.br": "imap.mail.yahoo.com",
    "icloud.com": "imap.mail.me.com",
    "me.com": "imap.mail.me.com",
    "uol.com.br": "imap.uol.com.br",
    "terra.com.br": "imap.terra.com.br",
    "bol.com.br": "imap.bol.com.br",
    "ig.com.br": "imap.ig.com.br",
}

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PASSWORD_RE = re.compile(r"(?:senhas?|password|passwd)\s*(?:[:=]|é)\s*([^\s,;]+)", re.IGNORECASE)
HOST_RE = re.compile(r"\b((?:imap|mail|smtp)[\w.-]*\.[\w.-]+)", re.IGNORECASE)
PORT_RE = re.compile(r"\bporta\s*[:=]?\s*(\d{2,5})", re.IGNORECASE)

SETUP_GUIDE = (
    "📭 Ainda não configurei seu e-mail — é só me passar os dados que eu mesmo configuro.\n\n"
    "Me envie assim:\n"
    "\`imap.seuprovedor.com.br usuário: voce@provedor.com.br senha: SUA_SENHA\`\n\n"
    "- Não sabe o servidor IMAP? Me diga só o provedor (Gmail, Outlook...) e eu descubro o resto.\n"
    "- Gmail e Outlook pedem uma **senha de app** (não a senha normal do e-mail):\n"
    "  [senha de app no Gmail](https://myaccount.google.com/apppasswords) · "
    "[no Outlook](https://account.live.com/proofs/AppPassword).\n"
    "- A senha fica salva **apenas neste computador** — nada sai da sua máquina."
)


@dataclass
class EmailSummary:
    subject: str
    sender: str
    category: str      # "urgent" | "needs_reply" | "fyi"
    summary: str
    draft_reply: Optional[str] = None


class EmailModule:
    def __init__(self):
        self.llm = OllamaClient()
        self._load_persisted_config()

    # ---- Configuração pelo chat ------------------------------------------
    def _load_persisted_config(self) -> None:
        """Carrega a configuração salva localmente (data/email_config.json)."""
        if not CONFIG_FILE.exists():
            return
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            return
        for field in ("imap_host", "imap_port", "smtp_host", "smtp_port", "username", "password"):
            value = data.get(field)
            if value:
                setattr(CONFIG.email, field, value)

    def is_configured(self) -> bool:
        return bool(CONFIG.email.imap_host and CONFIG.email.username and CONFIG.email.password)

    def missing_fields(self) -> list:
        missing = []
        if not CONFIG.email.imap_host:
            missing.append("servidor IMAP")
        if not CONFIG.email.username:
            missing.append("seu e-mail (usuário)")
        if not CONFIG.email.password:
            missing.append("senha")
        return missing

    def save_config(self, imap_host=None, imap_port=None, username=None,
                    password=None, smtp_host=None, smtp_port=None) -> None:
        """Aplica a configuração e salva apenas neste computador."""
        if imap_host:
            CONFIG.email.imap_host = imap_host
        if imap_port:
            CONFIG.email.imap_port = int(imap_port)
        if username:
            CONFIG.email.username = username
        if password:
            CONFIG.email.password = password
        if smtp_host:
            CONFIG.email.smtp_host = smtp_host
        if smtp_port:
            CONFIG.email.smtp_port = int(smtp_port)
        try:
            CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "imap_host": CONFIG.email.imap_host,
                "imap_port": CONFIG.email.imap_port,
                "smtp_host": CONFIG.email.smtp_host,
                "smtp_port": CONFIG.email.smtp_port,
                "username": CONFIG.email.username,
                "password": CONFIG.email.password,
            }
            CONFIG_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception:
            pass  # sem persistência, a configuração vale apenas nesta sessão

    @staticmethod
    def extract_config(text: str) -> dict:
        """Extrai dados de acesso (host, usuário, senha) de uma mensagem."""
        out = {}
        match = EMAIL_RE.search(text)
        if match:
            out["username"] = match.group(0)
        match = PASSWORD_RE.search(text)
        if match:
            out["password"] = match.group(1).strip('"')
        match = HOST_RE.search(text)
        if match:
            out["imap_host"] = match.group(1).lower()
        match = PORT_RE.search(text)
        if match:
            out["imap_port"] = int(match.group(1))
        # Sem host explícito: deduz do domínio (Gmail, Outlook... ou imap.dominio)
        if "imap_host" not in out and "username" in out:
            domain = out["username"].split("@")[-1].lower()
            out["imap_host"] = KNOWN_IMAP_HOSTS.get(domain, "imap." + domain)
        return out

    def setup_guide(self) -> str:
        if self.is_configured():
            return (
                "✅ Seu e-mail já está configurado (" + str(CONFIG.email.username) + ").\n\n"
                "Quer atualizar algo? Me envie os novos dados — "
                "por exemplo: \`senha: NOVA_SENHA\`."
            )
        return SETUP_GUIDE

    def test_connection(self):
        """Testa a conexão IMAP. Retorna (ok, mensagem de erro)."""
        try:
            with self._connect() as client:
                client.select_folder("INBOX", readonly=True)
            return True, ""
        except Exception as e:
            return False, str(e)

    def candidate_hosts(self) -> list:
        """Servidores alternativos plausíveis para testar quando o informado falha."""
        candidates = []
        if CONFIG.email.username:
            domain = CONFIG.email.username.split("@")[-1].lower()
            known = KNOWN_IMAP_HOSTS.get(domain)
            if known:
                candidates.append(known)
            for prefix in ("mail.", "imap.", ""):
                host = prefix + domain
                if host not in candidates:
                    candidates.append(host)
            # Hospedagens brasileiras (Locaweb e similares) usam servidor compartilhado
            if domain.endswith(".com.br") and "email-ssl.com.br" not in candidates:
                candidates.append("email-ssl.com.br")
        return candidates

    def try_alternative_hosts(self):
        """
        Quando o servidor informado falha, testa candidatos alternativos.
        Retorna (ok, erro, servidor_que_funcionou, servidores_testados).
        Em caso de sucesso, já salva a configuração com o servidor que funcionou.
        """
        original = CONFIG.email.imap_host
        tried = []
        last_error = ""
        for host in self.candidate_hosts():
            if host == original:
                continue
            tried.append(host)
            CONFIG.email.imap_host = host
            ok, err = self.test_connection()
            if ok:
                self.save_config(imap_host=host)
                return True, "", host, tried
            last_error = err
        CONFIG.email.imap_host = original
        return False, last_error, None, tried

    # ---- Conexão e leitura -------------------------------------------------
    def _connect(self) -> IMAPClient:
        if not CONFIG.email.imap_host or not CONFIG.email.username or not CONFIG.email.password:
            raise RuntimeError(
                "E-mail não configurado ainda. Me passe os dados que eu configuro: "
                "servidor IMAP, seu e-mail e a senha."
            )
        client = IMAPClient(CONFIG.email.imap_host, port=CONFIG.email.imap_port, ssl=True)
        client.login(CONFIG.email.username, CONFIG.email.password)
        return client

    def _decode(self, value: str) -> str:
        if not value:
            return ""
        parts = decode_header(value)
        decoded = []
        for part, encoding in parts:
            if isinstance(part, bytes):
                decoded.append(part.decode(encoding or "utf-8", errors="replace"))
            else:
                decoded.append(part)
        return "".join(decoded)

    def fetch_and_classify(self, limit: int = 20) -> list[EmailSummary]:
        """Busca e-mails recentes, classifica e gera resumos + rascunhos."""
        summaries: list[EmailSummary] = []
        with self._connect() as client:
            client.select_folder("INBOX", readonly=True)
            uids = client.search(["UNSEEN"])[-limit:]
            if not uids:
                return summaries

            messages = client.fetch(uids, ["RFC822"])
            for uid, data in messages.items():
                msg = email.message_from_bytes(data[b"RFC822"])
                subject = self._decode(msg.get("Subject", ""))
                sender = self._decode(msg.get("From", ""))
                body = self._extract_body(msg)

                classified = self._classify(subject, body)
                summaries.append(
                    EmailSummary(
                        subject=subject,
                        sender=sender,
                        category=classified["category"],
                        summary=classified["summary"],
                        draft_reply=classified.get("draft_reply"),
                    )
                )
        return summaries

    def _extract_body(self, msg) -> str:
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    payload = part.get_payload(decode=True)
                    if payload:
                        return payload.decode(errors="replace")[:3000]
            return ""
        payload = msg.get_payload(decode=True)
        return payload.decode(errors="replace")[:3000] if payload else ""

    def _classify(self, subject: str, body: str) -> dict:
        system = (
            "Você é um assistente de e-mail. Classifique a mensagem e retorne APENAS JSON: "
            "{'category': 'urgent'|'needs_reply'|'fyi', "
            "'summary': 'resumo em 2 frases', "
            "'draft_reply': 'rascunho de resposta curto ou null'}. "
            "Se não precisar de resposta, draft_reply deve ser null."
        )
        prompt = f"Assunto: {subject}\n\nCorpo:\n{body}"
        raw = self.llm.chat(prompt, system=system, format_json=True)
        try:
            return json.loads(raw)
        except Exception:
            return {"category": "fyi", "summary": subject, "draft_reply": None}

    def daily_brief(self) -> str:
        """Gera um resumo diário da caixa de entrada."""
        summaries = self.fetch_and_classify(limit=30)
        urgent = [s for s in summaries if s.category == "urgent"]
        replies = [s for s in summaries if s.category == "needs_reply"]
        fyi = [s for s in summaries if s.category == "fyi"]

        lines = [
            f"📭 Resumo do dia — {len(summaries)} e-mails analisados",
            f"🔴 Urgentes: {len(urgent)}",
            f"✉️ Precisam de resposta: {len(replies)}",
            f"📄 Informativos: {len(fyi)}",
            "",
        ]
        for s in urgent + replies:
            lines.append(f"• [{s.category}] {s.sender}: {s.subject}")
            lines.append(f"  {s.summary}")
        return "\n".join(lines)
