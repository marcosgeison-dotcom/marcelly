"""
Agentes locais da Marcelly.
Instalados junto com o executável: cada agente executa uma tarefa
concreta usando os módulos e a memória locais — nada sai da máquina.
"""
import json
import re
import sqlite3
import time
from pathlib import Path

from config import DATA_DIR
from core.debug import DEBUG
from core.ollama_client import OllamaClient
from core.resilience import chat_with_retry, simple_plan, try_alternatives, with_email_alternatives

DB_PATH = DATA_DIR / "marcelly.db"


class BaseAgent:
    name = ""
    emoji = ""
    description = ""

    def run(self, request: str) -> str:
        raise NotImplementedError


class EmailAgent(BaseAgent):
    name = "Agente de E-mail"
    emoji = "📧"
    description = "Resume a caixa de entrada, classifica e-mails e pré-redige respostas."

    def __init__(self, email_module):
        self.email = email_module

    def run(self, request: str) -> str:
        if "resumo" in request.lower() or "brief" in request.lower():
            body, error = with_email_alternatives(self.email, self.email.daily_brief)
            return body if error is None else error

        def _list_emails() -> str:
            summaries = self.email.fetch_and_classify(limit=10)
            lines = [f"\U0001f4e7 **{len(summaries)} e-mails recentes:**", ""]
            for s in summaries:
                lines.append(f"\u2022 **[{s.category}]** {s.sender}: {s.subject}")
                lines.append(f"  {s.summary}")
                if s.draft_reply:
                    lines.append(f"  \U0001f4ac _Rascunho:_ {s.draft_reply[:140]}...")
            return "\n".join(lines)

        body, error = with_email_alternatives(self.email, _list_emails)
        return body if error is None else error

class PlannerAgent(BaseAgent):
    name = "Agente Planejador"
    emoji = "🗂️"
    description = "Transforma um objetivo em um plano curto com passos práticos."

    def __init__(self):
        self.llm = OllamaClient()

    def run(self, request: str) -> str:
        system = (
            "Voc\u00ea \u00e9 um agente planejador. Divida o pedido do usu\u00e1rio em um plano "
            "curto e pr\u00e1tico: de 3 a 6 passos numerados, cada um com uma a\u00e7\u00e3o "
            "concreta. Responda em portugu\u00eas, sem introdu\u00e7\u00f5es."
        )
        return try_alternatives("Agente Planejador", [
            ("plano pelo modelo local", lambda: self.llm.chat(request, system=system).strip()),
            ("plano local simplificado", lambda: simple_plan(request)),
        ])

class ReminderAgent(BaseAgent):
    name = "Agente de Lembretes"
    emoji = "⏰"
    description = "Cria, lista e conclui lembretes salvos localmente no SQLite."

    def __init__(self):
        self.llm = OllamaClient()
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                due TEXT,
                done INTEGER DEFAULT 0,
                created_at REAL
            )
        """)
        self.conn.commit()

    def run(self, request: str) -> str:
        lower = request.lower()
        if any(w in lower for w in ("liste", "quais lembretes", "meus lembretes", "ver lembretes")):
            return self._list()
        if any(w in lower for w in ("conclu", "marque como feito", "lembrete pronto")):
            return self._complete(request)
        return self._create(request)

    def _create(self, request: str) -> str:
        system = (
            "Extraia um lembrete do pedido. Retorne APENAS JSON: "
            "{'text': 'o que lembrar', 'due': 'data/hora em texto livre ou null'}."
        )
        try:
            raw = chat_with_retry(self.llm, request, system=system, format_json=True)
            data = json.loads(raw)
        except Exception:
            data = {"text": request, "due": None}
        text = (data.get("text") or request).strip()
        due = data.get("due") or None
        self.conn.execute(
            "INSERT INTO reminders (text, due, created_at) VALUES (?, ?, ?)",
            (text, due, time.time()),
        )
        self.conn.commit()
        extra = f" para {due}" if due else ""
        return f"⏰ Lembrete criado{extra}: **{text}**\n\nDiga _\"meus lembretes\"_ para ver a lista."

    def _list(self) -> str:
        rows = self.conn.execute(
            "SELECT id, text, due FROM reminders WHERE done = 0 ORDER BY created_at DESC LIMIT 20"
        ).fetchall()
        if not rows:
            return "Nenhum lembrete ativo no momento. Diga _\"me lembre de...\"_ para criar um."
        lines = ["⏰ **Seus lembretes:**", ""]
        for r in rows:
            due = f" — {r['due']}" if r["due"] else ""
            lines.append(f"• {r['text']}{due}")
        return "\n".join(lines)

    def _complete(self, request: str) -> str:
        system = (
            "O usuário quer concluir um lembrete. Retorne APENAS JSON: "
            "{'text': 'texto do lembrete a concluir'}."
        )
        try:
            raw = chat_with_retry(self.llm, request, system=system, format_json=True)
            text = json.loads(raw).get("text", "")
        except Exception:
            text = ""
        pattern = f"%{text}%" if text else "%"
        cur = self.conn.execute(
            "UPDATE reminders SET done = 1 WHERE done = 0 AND text LIKE ?",
            (pattern,),
        )
        self.conn.commit()
        if cur.rowcount:
            return f"✅ {cur.rowcount} lembrete(s) concluído(s)."
        return "Não encontrei esse lembrete. Diga _\"meus lembretes\"_ para ver a lista."


class PatternsAgent(BaseAgent):
    name = "Agente de Padrões"
    emoji = "📈"
    description = "Analisa seus hábitos e fatos aprendidos e mostra o que já sabe."

    def __init__(self, memory):
        self.memory = memory

    def run(self, request: str) -> str:
        def _collect() -> str:
            patterns = self.memory.get_patterns(5)
            facts = self.memory.get_facts()[:5]
            if not patterns and not facts:
                return (
                    "Ainda n\u00e3o tenho padr\u00f5es suficientes sobre voc\u00ea. "
                    "Converse comigo por alguns dias e analiso seus h\u00e1bitos."
                )
            lines = ["\U0001f4ca **O que aprendi sobre voc\u00ea:**", ""]
            for p in patterns:
                lines.append(f"\u2022 {p}")
            for f in facts:
                lines.append(f"\u2022 {f.key}: {f.value}")
            return "\n".join(lines)

        return try_alternatives("Agente de Padr\u00f5es", [("ler a mem\u00f3ria local", _collect)])

class AgentRegistry:
    """Catálogo dos agentes instalados junto com o executável."""

    KEYWORDS = [
        (r"\b(agente|agentes|quais agentes)\b", "lista"),
        (r"\b(lembrete|lembretes|me lembre|lembra-?me|me avise)\b", "Agente de Lembretes"),
        (r"\b(plano|planeje|planejar|rotina|passo a passo|organizar)\b", "Agente Planejador"),
        (r"\b(e-?mail|inbox|caixa de entrada|correio)\b", "Agente de E-mail"),
        (r"\b(h[áa]bitos|padr[õo]es)\b", "Agente de Padrões"),
    ]

    def __init__(self, memory, email_module):
        self.llm = OllamaClient()
        self.agents = [
            EmailAgent(email_module),
            PlannerAgent(),
            ReminderAgent(),
            PatternsAgent(memory),
        ]

    def list_agents(self) -> str:
        lines = ["🤖 **Agentes instalados na Marcelly:**", ""]
        for a in self.agents:
            lines.append(f"• {a.emoji} **{a.name}** — {a.description}")
        lines += [
            "",
            "É só pedir: _\"monte um plano para...\"_, _\"me lembre de...\"_,",
            "_\"resuma meus e-mails\"_ ou _\"analise meus hábitos\"_.",
        ]
        return "\n".join(lines)

    def _by_name(self, name: str):
        for a in self.agents:
            if a.name == name:
                return a
        return None

    def pick(self, request: str):
        lower = request.lower()
        for pattern, target in self.KEYWORDS:
            if re.search(pattern, lower):
                if target == "lista":
                    return None  # cai no catálogo
                return self._by_name(target)
        return None

    def dispatch(self, request: str) -> str:
        agent = self.pick(request)
        DEBUG.log("agents", agent=agent.name if agent else "catálogo")
        if agent is None:
            return self.list_agents()
        return f"{agent.emoji} {agent.run(request)}"