"""
15 skills locais da Marcelly.
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
from core.resilience import chat_with_retry, local_ideas, local_review, local_summary, simple_plan, try_alternatives, with_email_alternatives


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
    """Catalogo das 15 skills instaladas junto com o executavel."""

    KEYWORDS = [
        (r"\bskills?\b|\bhabilidades?\b|\bo que voc[êe] sabe fazer\b", "lista"),
        (r"\b(resum[oa]s?|resumir)\b", "resumo"),
        (r"\b(organiz\w+|separe|agrupe)\b.*\bdia\b", "dias"),
        (r"\bmelhore\b", "revisao"),
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
        (r"\bsuperpowers?\b|\bmetodologia\b", "superpowers"),
        (r"\bkarpathy\b", "karpathy"),
        (r"\b(adhd|tdah)\b", "adhd"),
        (r"\b(octopus|polvo)\b", "octopus"),
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
            Skill("superpowers", "Superpowers", "\U0001f9e9",
                  "Metodologia de desenvolvimento em passos verificaveis.", self._superpowers),
            Skill("karpathy", "Karpathy", "\U0001f977",
                  "Guias de codigo simples, sem exageros de engenharia.", self._karpathy),
            Skill("adhd", "I have ADHD", "\U0001f4af",
                  "Respostas acionaveis: direto ao ponto, passo a passo.", self._adhd),
            Skill("octopus", "Claude Octopus", "\U0001f419",
                  "Analisa o pedido por tres perspectivas e resume a melhor.", self._octopus),
        ]

    # ---------- Catalogo ----------
    def list_skills(self) -> str:
        lines = ["\u2728 **As " + str(len(self.skills)) + " skills instaladas na Marcelly:**", ""]
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
            body, error = with_email_alternatives(reg.orch.email, reg.orch.email.daily_brief)
            return body if error is None else error
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
        return try_alternatives("Resumo Inteligente", [
            ("resumo pelo modelo local", lambda: self.llm.chat(convo, system=system).strip()),
            ("resumo local simplificado", lambda: local_summary(rows)),
        ])

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
        return try_alternatives("Revisao de Solicitacoes", [
            ("analise pelo modelo local", lambda: self.llm.chat(listing, system=system).strip()),
            ("analise local simplificada", lambda: local_review(rows)),
        ])

    def _busca(self, request, reg):
        system = (
            "Extraia o termo de busca do pedido. Retorne APENAS JSON: "
            "{'query': 'assunto a procurar no historico'}."
        )
        try:
            raw = chat_with_retry(self.llm, request, system=system, format_json=True)
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
        return try_alternatives("Planejamento", [
            ("plano pelo modelo local", lambda: self.llm.chat(request, system=system).strip()),
            ("plano local simplificado", lambda: simple_plan(request)),
        ])

    def _lembrete(self, request, reg):
        from core.agents import ReminderAgent
        if self._reminder is None:
            self._reminder = ReminderAgent()
        return self._reminder.run(request)

    def _email(self, request, reg):
        lower = request.lower()
        if "resumo" in lower or "brief" in lower:
            body, error = with_email_alternatives(reg.orch.email, reg.orch.email.daily_brief)
            return body if error is None else error

        def _list_emails():
            summaries = reg.orch.email.fetch_and_classify(limit=10)
            lines = ["\U0001f4ec **" + str(len(summaries)) + " e-mails recentes:**", ""]
            for s in summaries:
                lines.append("\u2022 **[" + s.category + "]** " + s.sender + ": " + s.subject)
                lines.append("  " + s.summary)
            return "\n".join(lines)

        body, error = with_email_alternatives(reg.orch.email, _list_emails)
        return body if error is None else error

    def _decisao(self, request, reg):
        orch = reg.orch
        options = orch._extract_options(request) or ["Sim", "Nao", "Esperar"]

        def _via_calibrado():
            result = orch.decision.decide(request, options)
            lines = ["\U0001f9e0 **Decisao analisada:** " + request, "", "**Probabilidades:**"]
            for opt, prob in sorted(result.probabilities.items(), key=lambda x: -x[1]):
                bar = "\u2588" * int(prob * 20)
                lines.append("  - " + str(opt) + ": " + format(prob, ".1%") + " " + bar)
            lines += ["", "\u2705 **Recomendacao:** " + result.recommended,
                      "\U0001f4dd " + result.explanation]
            return "\n".join(lines)

        def _via_chat():
            opts = ", ".join(str(o) for o in options)
            system = (
                "Voce e uma skill de analise de decisoes. Compare as opcoes, "
                "estime a chance de cada uma valer a pena e recomende um caminho, "
                "em portugues, de forma curta e objetiva."
            )
            texto = chat_with_retry(self.llm, request + "\nOpcoes: " + opts, system=system).strip()
            return "\U0001f9e0 **Decisao analisada (analise alternativa):** " + request + "\n\n" + texto

        return try_alternatives("Analise de Decisoes", [
            ("modelo calibrado", _via_calibrado),
            ("analise pelo modelo de chat", _via_chat),
        ])

    def _ideias(self, request, reg):
        system = (
            "Gere de 4 a 6 opcoes ou alternativas criativas e praticas para o pedido "
            "abaixo, em portugues, em lista numerada. Sem introducoes."
        )
        return try_alternatives("Direcionamento e Ideias", [
            ("ideias pelo modelo local", lambda: self.llm.chat(request, system=system).strip()),
            ("opcoes locais simplificadas", lambda: local_ideas(request)),
        ])

    def _memoria(self, request, reg):
        def _read():
            facts = reg.orch.memory.get_facts()[:10]
            if not facts:
                return "Ainda nao aprendi fatos sobre voce. Converse comigo e vou anotando!"
            lines = ["\U0001f4cc **O que sei sobre voce:**", ""]
            for f in facts:
                lines.append("\u2022 " + f.key + ": " + f.value)
            return "\n".join(lines)

        return try_alternatives("Memoria de Fatos", [("ler a memoria local", _read)])

    def _habitos(self, request, reg):
        def _read():
            patterns = reg.orch.memory.get_patterns(6)
            if not patterns:
                return "Ainda nao detectei padroes. Converse comigo por alguns dias!"
            lines = ["\U0001f4c8 **Padroes que detectei:**", ""]
            for p in patterns:
                lines.append("\u2022 " + p)
            return "\n".join(lines)

        return try_alternatives("Padroes e Habitos", [("ler a memoria local", _read)])

    # ---------- Skills instaladas (pacotes externos) ----------
    def _superpowers(self, request, reg):
        system = (
            "Voce e a skill Superpowers, uma metodologia de desenvolvimento em "
            "etapas verificaveis. Para o pedido do usuario, responda em portugues "
            "neste formato:\n"
            "\U0001f9e9 **Entendimento:** reformule o objetivo em uma frase.\n"
            "\U0001f4cb **Plano:** de 3 a 6 passos numerados e concretos, cada um com "
            "o criterio que prova que o passo funcionou.\n"
            "\U0001f41b **Riscos:** ate 3 pontos que podem dar errado e como detectar.\n"
            "\u2705 **Primeiro passo:** o que fazer agora e como verificar.\n"
            "Sem introducoes."
        )
        return try_alternatives("Superpowers", [
            ("plano metodologico pelo modelo local", lambda: self.llm.chat(request, system=system).strip()),
            ("plano local simplificado", lambda: simple_plan(request)),
        ])

    def _karpathy(self, request, reg):
        system = (
            "Voce e a skill Karpathy: guias de codigo derivados das observacoes de "
            "Andrej Karpathy sobre erros comuns de modelos de linguagem. Ao responder "
            "ao pedido do usuario, em portugues, siga:\n"
            "1. A solucao mais simples que funciona vence - cada linha de codigo custa.\n"
            "2. Nao invente abstracoes, camadas ou flexibilidade para o futuro.\n"
            "3. Prefira apagar codigo a adicionar; reuso antes de algo novo.\n"
            "4. Teste o comportamento real, nao detalhes internos.\n"
            "5. Ao apontar um problema, cite onde ele esta (arquivo, linha ou trecho).\n"
            "Se o pedido nao for sobre codigo, responda curto e direto. Sem introducoes."
        )
        def _fallback():
            return (
                "\U0001f977 **Checklist Karpathy (sem modelo disponivel):**\n"
                "1. Qual e a solucao mais simples que funciona?\n"
                "2. Da para apagar codigo em vez de adicionar?\n"
                "3. Nenhuma abstracao nova antes da segunda repeticao real.\n"
                "4. Teste o comportamento que o usuario ve, nao detalhes internos."
            )
        return try_alternatives("Karpathy", [
            ("resposta guiada pelo modelo local", lambda: self.llm.chat(request, system=system).strip()),
            ("checklist local simplificado", _fallback),
        ])

    def _adhd(self, request, reg):
        system = (
            "O leitor tem TDAH. Modele toda a resposta para ser acionavel, em portugues:\n"
            "1. Comece com a resposta ou proxima acao - nunca com preambulo.\n"
            "2. Numere o trabalho de varios passos; uma acao delimitada por passo.\n"
            "3. Termine com UMA proxima acao de menos de dois minutos.\n"
            "4. Listas com no maximo 5 itens.\n"
            "5. Estime tempos em unidades concretas, nunca 'um pouco'.\n"
            "Sem recapitulacoes nem despedidas."
        )
        return try_alternatives("I have ADHD", [
            ("resposta acionavel pelo modelo local", lambda: self.llm.chat(request, system=system).strip()),
            ("resposta local simplificada", lambda: simple_plan(request)),
        ])

    def _octopus(self, request, reg):
        system = (
            "Voce e a skill Claude Octopus: analise o pedido por tres perspectivas "
            "antes de responder, em portugues:\n"
            "\U0001f41b **Braco 1 - Construtor:** proponha a solucao mais direta.\n"
            "\U0001f9d0 **Braco 2 - Auditor:** aponte riscos e falhas dessa proposta.\n"
            "\u2699\ufe0f **Braco 3 - Executor:** transforme em passos curtos e acionaveis.\n"
            "\U0001f4dd **Veredito:** a melhor resposta final, unindo os tres bracos.\n"
            "Cada braco em ate 3 linhas. Sem introducoes."
        )
        return try_alternatives("Claude Octopus", [
            ("tres perspectivas pelo modelo local", lambda: self.llm.chat(request, system=system).strip()),
            ("ideias locais simplificadas", lambda: local_ideas(request)),
        ])

