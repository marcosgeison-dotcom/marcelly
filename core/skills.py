"""
11 skills locais da Marcelly.
Cada skill e uma habilidade instalada junto com o executavel -
tudo roda no seu computador, sem enviar nada para fora.

Uma delas, a Revisao de Solicitacoes, analisa seus pedidos passados
e aponta melhorias e falhas em como voce pede as coisas.
"""

import json
import re
import time
from datetime import datetime, timedelta

from core.debug import DEBUG
from core.ollama_client import OllamaClient


class Skill:
    def __init__(self, key, name, emoji, description, handler):
        self.key = key
        self.name = name
        self.emoji = emoji
        self.description = description
        self.handler = handler

    def run(self, request, registry):
        return self.handler(request, registry)


class SkillRegistry:
    """Catalogo das 11 skills instaladas junto com o executavel."""

    KEYWORDS = [
        (r"\bskills?\b|\bhabilidades?\b|\bo que voc[êe] sabe fazer\b", "lista"),
        (r"\b(retrospectiva|revis(ã|a)o dos? meus? pedidos?|melhorias? e falhas?|como posso melhorar)\b", "revisao"),
        (r"\b(busque|pesquise|procure no hist[óo]rico|busca no hist[óo]rico)\b", "busca"),
        (r"\b(hist[óo]rico das? (minhas )?conversas?|conversas? por dia)\b", "dias"),
        (r"\b(plano|planeje|planejar|passo a passo)\b", "plano"),
        (r"\b(lembrete|lembretes|me lembre)\b", "lembrete"),
        (r"\b(e-?mail|caixa de entrada|inbox)\b", "email"),
        (r"\b(decis[ãa]o|devo|vale a pena)\b", "decisao"),
        (r"\b(op[çc][õo]es|ideias|alternativas|sugest[õo]es)\b", "ideias"),
        (r"\b(o que voc[êe] sabe sobre mim|meus fatos|minha mem[óo]ria)\b", "memoria"),
        (r"\b(h[áa]bitos|padr[õo]es)\b", "habitos"),
    ]

    def __init__(self, orchestrator):
        self.orch = orchestrator
        self.llm = OllamaClient()
        self._reminder = None  # criado sob demanda (abre o banco local)
        self.skills = [
            Skill("resumo", "Resumo Inteligente", "\U0001f4dd",
                  "Resume conversas, e-mails e assuntos longos.", self._resumo),
            Skill("revisao", "Revisao de Solicitacoes", "\U0001f50e",
                  "Analisa seus pedidos passados e aponta melhorias e falhas.", self._revisao),
            Skill("busca", "Busca por Assunto", "\U0001f50d",
                  "Encontra qualquer assunto no historico do chat.", self._busca),
            Skill("dias", "Organizacao por Dia", "\U0001f5d3\ufe0f",
                  "Organiza e mostra as conversas separadas por dia.", self._dias),
            Skill("plano", "Planejamento", "\U0001f9ed",
                  "Transforma um objetivo em um plano pratico.", self._plano),
            Skill("lembrete", "Lembretes", "\u23f0",
                  "Cria, lista e conclui lembretes locais.", self._lembrete),
            Skill("email", "E-mail", "\U0001f4e7",
                  "Resume e classifica sua caixa de entrada.", self._email),
            Skill("decisao", "Analise de Decisoes", "\U0001f9e0",
                  "Compara opcoes e recomenda um caminho.", self._decisao),
            Skill("ideias", "Direcionamento e Ideias", "\U0001f4a1",
                  "Gera opcoes e alternativas para o seu pedido.", self._ideias),
            Skill("memoria", "Memoria de Fatos", "\U0001f4cc",
                  "Aprende e lembra fatos sobre voce.", self._memoria),
            Skill("habitos", "Padroes e Habitos", "\U0001f4c8",
                  "Detecta seus habitos recorrentes.", self._habitos),
        ]

    # ---------- Catalogo ----------
    def list_skills(self) -> str:
        lines = ["\u2728 **As 11 skills instaladas na Marcelly:**", ""]
        for i, s in enumerate(self.skills, 1):
            lines.append(str(i) + ". " + s.emoji + " **" + s.name + "** \u2014 " + s.description)
        lines += [
            "",
            "E so pedir: _\"faca uma retrospectiva dos meus pedidos\"_,",
            "_\"busque no historico sobre o projeto X\"_ ou _\"organize por dia\"_.",
        ]
        return "\n".join(lines)

    def dispatch(self, request: str) -> str:
        lower = request.lower()
        for pattern, target in self.KEYWORDS:
            if re.search(pattern, lower):
                if target == "lista":
                    return self.list_skills()
                skill = self._by_key(target)
                if skill:
                    DEBUG.log("skills", skill=skill.name)
                    return skill.emoji + " " + skill.run(request, self)
        return self.list_skills()

    def _by_key(self, key: str):
        for s in self.skills:
            if s.key == key:
                return s
        return None

    # ---------- Handlers ----------
    def _resumo(self, request, reg):
        lower = request.lower()
        if "e-mail" in lower or "email" in lower or "inbox" in lower:
            return reg.orch.email.daily_brief()
        rows = reg.orch.memory.recent_interactions(20)
        if not rows:
            return "Ainda nao temos conversas para resumir."
        convo = "\n".join(
            "Voce: " + r["user_message"] + "\nIntencao: " + (r["intent"] or "?")
            for r in rows
        )
        system = (
            "Resuma a conversa abaixo em ate 6 topicos curtos em portugues, "
            "destacando os principais assuntos. Sem introducoes."
        )
        return self.llm.chat(convo, system=system).strip()

    def _revisao(self, request, reg):
        rows = reg.orch.memory.recent_interactions(30)
        if not rows:
            return "Ainda nao ha solicitacoes suficientes para eu analisar. Converse comigo um pouco mais!"
        listing = "\n".join(
            str(i) + ". Pedido: " + r["user_message"] + " (intencao detectada: " + (r["intent"] or "?") + ")"
            for i, r in enumerate(rows, 1)
        )
        system = (
            "Voce e a skill de Revisao de Solicitacoes. Analise os pedidos do "
            "usuario abaixo e produza, em portugues, duas secoes:\n"
            "\u2705 **Melhorias sugeridas** - como o usuario pode pedir melhor "
            "(mais contexto, mais especifico, menos ambiguo).\n"
            "\u26a0\ufe0f **Falhas encontradas** - pedidos vagos, incompletos ou que "
            "provavelmente nao geraram a resposta esperada.\n"
            "Seja especifico citando os pedidos (use o numero). Sem introducoes."
        )
        return self.llm.chat(listing, system=system).strip()

    def _busca(self, request, reg):
        system = (
            "Extraia o termo de busca do pedido. Retorne APENAS JSON: "
            "{'query': 'assunto a procurar no historico'}."
        )
        try:
            raw = self.llm.chat(request, system=system, format_json=True)
            query = json.loads(raw).get("query", "").strip()
        except Exception:
            query = ""
        if not query:
            query = re.sub(
                r"\b(busque|pesquise|procure|no hist[óo]rico|hist[óo]rico|sobre)\b",
                " ", request, flags=re.IGNORECASE,
            ).strip()
        if not query:
            return "\U0001f50d Me diga qual assunto procurar: _\"busque no historico sobre reunioes\"_."
        items = reg.orch.memory.search_interactions(query)
        if not items:
            return "\U0001f50d Nada encontrado sobre **" + query + "** no historico."
        lines = ["\U0001f50d **" + str(len(items)) + " resultado(s) para \"" + query + "\":**", ""]
        for it in items[:10]:
            when = time.strftime("%d/%m %H:%M", time.localtime(it["ts"]))
            lines.append("\u2022 _" + when + "_ \u2014 " + it["user_message"][:120])
        if len(items) > 10:
            lines.append("")
            lines.append("(+" + str(len(items) - 10) + " no painel Historico, aba busca)")
        return "\n".join(lines)

    def _dias(self, request, reg):
        memory = reg.orch.memory
        days = memory.history_days()
        if not days:
            return "Ainda nao ha conversas salvas. Assim que conversarmos, organizo tudo por dia!"
        m = re.search(r"(\d{1,2})/(\d{1,2})", request)
        target = None
        if m:
            year = datetime.now().year
            try:
                target = datetime(year, int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
            except ValueError:
                target = None
        elif "ontem" in request.lower():
            target = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        elif "hoje" in request.lower():
            target = datetime.now().strftime("%Y-%m-%d")
        if target:
            items = memory.interactions_by_day(target)
            if not items:
                return "Nenhuma conversa registrada em " + target + "."
            lines = ["\U0001f5d3\ufe0f **Conversas de " + target + ":**", ""]
            for it in items:
                when = time.strftime("%H:%M", time.localtime(it["ts"]))
                lines.append("\u2022 _" + when + "_ \u2014 " + it["user_message"][:120])
            return "\n".join(lines)
        total = sum(d["n"] for d in days)
        lines = ["\U0001f5d3\ufe0f **" + str(total) + " conversas em " + str(len(days)) + " dias:**", ""]
        for d in days[:14]:
            lines.append("\u2022 " + d["day"] + ": " + str(d["n"]) + " conversa(s)")
        if len(days) > 14:
            lines.append("")
            lines.append("(veja todas no painel Historico)")
        return "\n".join(lines)

    def _plano(self, request, reg):
        system = (
            "Voce e um agente planejador. Divida o pedido do usuario em um plano "
            "curto e pratico: de 3 a 6 passos numerados, cada um com uma acao "
            "concreta. Responda em portugues, sem introducoes."
        )
        return self.llm.chat(request, system=system).strip()

    def _lembrete(self, request, reg):
        from core.agents import ReminderAgent
        if self._reminder is None:
            self._reminder = ReminderAgent()
        return self._reminder.run(request)

    def _email(self, request, reg):
        lower = request.lower()
        if "resumo" in lower or "brief" in lower:
            return reg.orch.email.daily_brief()
        summaries = reg.orch.email.fetch_and_classify(limit=10)
        lines = ["\U0001f4ec **" + str(len(summaries)) + " e-mails recentes:**", ""]
        for s in summaries:
            lines.append("\u2022 **[" + s.category + "]** " + s.sender + ": " + s.subject)
            lines.append("  " + s.summary)
        return "\n".join(lines)

    def _decisao(self, request, reg):
        orch = reg.orch
        options = orch._extract_options(request) or ["Sim", "Nao", "Esperar"]
        result = orch.decision.decide(request, options)
        lines = ["\U0001f9e0 **Decisao analisada:** " + request, "", "**Probabilidades:**"]
        for opt, prob in sorted(result.probabilities.items(), key=lambda x: -x[1]):
            bar = "\u2588" * int(prob * 20)
            lines.append("  - " + str(opt) + ": " + format(prob, ".1%") + " " + bar)
        lines += ["", "\u2705 **Recomendacao:** " + result.recommended,
                  "\U0001f4dd " + result.explanation]
        return "\n".join(lines)

    def _ideias(self, request, reg):
        system = (
            "Gere de 4 a 6 opcoes ou alternativas criativas e praticas para o pedido "
            "abaixo, em portugues, em lista numerada. Sem introducoes."
        )
        return self.llm.chat(request, system=system).strip()

    def _memoria(self, request, reg):
        facts = reg.orch.memory.get_facts()[:10]
        if not facts:
            return "Ainda nao aprendi fatos sobre voce. Converse comigo e vou anotando!"
        lines = ["\U0001f4cc **O que sei sobre voce:**", ""]
        for f in facts:
            lines.append("\u2022 " + f.key + ": " + f.value)
        return "\n".join(lines)

    def _habitos(self, request, reg):
        patterns = reg.orch.memory.get_patterns(6)
        if not patterns:
            return "Ainda nao detectei padroes. Converse comigo por alguns dias!"
        lines = ["\U0001f4c8 **Padroes que detectei:**", ""]
        for p in patterns:
            lines.append("\u2022 " + p)
        return "\n".join(lines)
