"""
Módulo de e-mail local-first.
Conecta via IMAP/SMTP, classifica e-mails e pré-redige respostas.
Nenhum dado sai da máquina — o modelo roda via Ollama.
"""
import email
from dataclasses import dataclass
from email.header import decode_header
from typing import Optional

from imapclient import IMAPClient

from config import CONFIG
from core.ollama_client import OllamaClient


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

    def _connect(self) -> IMAPClient:
        if not CONFIG.email.imap_host or not CONFIG.email.username:
            raise RuntimeError(
                "E-mail não configurado. Defina IMAP_HOST, EMAIL_USER e EMAIL_PASS."
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
            import json
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
            f"📬 Resumo do dia — {len(summaries)} e-mails analisados",
            f"🔴 Urgentes: {len(urgent)}",
            f"✉️ Precisam de resposta: {len(replies)}",
            f"📄 Informativos: {len(fyi)}",
            "",
        ]
        for s in urgent + replies:
            lines.append(f"• [{s.category}] {s.sender}: {s.subject}")
            lines.append(f"  {s.summary}")
        return "\n".join(lines)