"""
Marcelly — Orquestrador com personalidade e memória.
Recebe entrada, detecta humor, roteia, gera resposta e aprende.
"""
import logging
import re
from typing import Any

from rich.console import Console
from rich.panel import Panel

from config import CONFIG
from core.agents import AgentRegistry
from core.debug import DEBUG
from core.intent_router import IntentRouter
from core.memory import Memory
from core.mood_detector import MoodDetector
from core.ollama_client import OllamaClient
from core.personality import Personality
from modules.chat_module import ChatModule
from modules.decision_module import DecisionModule
from modules.email_module import EmailModule
from modules.guidance_module import GuidanceModule

logging.basicConfig(level=CONFIG.log_level)
log = logging.getLogger("marcelly")
console = Console()


class MarcellyOrchestrator:
    def __init__(self):
        self.router = IntentRouter()
        self.mood = MoodDetector()
        self.personality = Personality()
        self.memory = Memory()
        self.llm = OllamaClient()

        self.email = EmailModule()
        self.decision = DecisionModule()
        self.guidance = GuidanceModule()
        self.chat = ChatModule()

        # Agentes locais — instalados junto com o executável
        self.agents = AgentRegistry(memory=self.memory, email_module=self.email)

    def _ensure_ollama(self) -> bool:
        """Configuração inicial: garante Ollama instalado, rodando e com os modelos."""
        import shutil
        import subprocess
        import time
        from rich.prompt import Confirm
        from ollama import Client

        wanted = [CONFIG.ollama.model, CONFIG.ollama.decision_model, "nomic-embed-text"]

        def _server_ok() -> bool:
            try:
                Client(host=CONFIG.ollama.host).list()
                return True
            except Exception:
                return False

        def _installed() -> set:
            try:
                return {m.model for m in Client(host=CONFIG.ollama.host).list().models}
            except Exception:
                return set()

        def _missing() -> list:
            have = _installed()
            return [m for m in wanted if not any(h == m or h.startswith(m) for h in have)]

        missing = _missing()
        if _server_ok() and not missing:
            return True

        if _server_ok():
            console.print(f"[yellow]Faltam modelos: {', '.join(missing)}[/yellow]")
        else:
            console.print(Panel(
                "[yellow]Ollama não encontrado.[/yellow]\n"
                "Ele é o cérebro local do Marcelly (nada sai da sua máquina).\n"
                "Agora vou instalar, iniciar e baixar os modelos pela primeira vez.",
                border_style="yellow", title="Configuração inicial",
            ))
            if not Confirm.ask("Continuar com a configuração agora?", default=True):
                console.print("[dim]Sem problema — instale depois em https://ollama.com/download[/dim]")
                return False
            if not shutil.which("ollama"):
                subprocess.run(
                    ["winget", "install", "--id", "Ollama.Ollama", "-e",
                     "--accept-source-agreements", "--accept-package-agreements"],
                    check=False,
                )
            if not _server_ok():
                subprocess.Popen(
                    ["ollama", "serve"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                for _ in range(10):
                    time.sleep(2)
                    if _server_ok():
                        break
            if not _server_ok():
                console.print(
                    "[red]Não consegui iniciar o Ollama.[/red] "
                    "Abra o aplicativo Ollama e rode o Marcelly novamente."
                )
                return False
            missing = _missing()

        failed = []
        for model in missing:
            console.print(f"[cyan]Baixando modelo: {model}[/cyan]")
            try:
                result = subprocess.run(["ollama", "pull", model], check=False)
                if result.returncode != 0 or model in _missing():
                    failed.append(model)
            except FileNotFoundError:
                failed.append(model)
        if failed:
            console.print(Panel(
                "[yellow]Não consegui baixar:[/yellow] " + ", ".join(failed) + "\n"
                "Verifique sua internet e rode o Marcelly novamente.\n"
                "Ou baixe manualmente no PowerShell:\n"
                "[cyan]ollama pull llama3.2:3b[/cyan]",
                border_style="yellow", title="Download de modelos",
            ))
        return _server_ok() and not failed

    def handle(self, user_input: str) -> dict[str, Any]:
        """
        Processa uma entrada e devolve:
        { "text": str, "meta": { "intent", "mood", ... } }
        """
        mood_ctx = self.mood.detect(user_input)
        DEBUG.log("mood", mood=mood_ctx.mood, time_of_day=mood_ctx.time_of_day)
        routing = self.router.route(user_input)
        DEBUG.log(
            "routing",
            intent=routing.intent,
            confidence=routing.confidence,
            reasoning=routing.reasoning,
        )

        try:
            self.memory.learn_facts(user_input)
        except Exception as e:
            log.warning(f"Falha ao aprender fatos: {e}")
            DEBUG.log("error", where="memoria.fatos", error=str(e))

        if routing.intent == "email":
            text = self._handle_email(user_input, mood_ctx)
        elif routing.intent == "decision":
            text = self._handle_decision(user_input, mood_ctx)
        elif routing.intent == "guidance":
            text = self._handle_guidance(user_input, mood_ctx)
        elif routing.intent == "agents":
            text = self._handle_agents(user_input, mood_ctx)
        else:
            text = self._handle_chat(user_input, mood_ctx)

        try:
            self.memory.log_interaction(
                user_message=user_input,
                intent=routing.intent,
                mood=mood_ctx.mood,
                response=text,
            )
            self.memory.detect_patterns()
        except Exception as e:
            log.warning(f"Falha ao registrar interação: {e}")
            DEBUG.log("error", where="memoria.interacao", error=str(e))

        return {
            "text": text,
            "meta": {
                "intent": routing.intent,
                "confidence": routing.confidence,
                "mood": mood_ctx.mood,
                "time_of_day": mood_ctx.time_of_day,
                "day_of_week": mood_ctx.day_of_week,
            },
        }

    def _is_casual(self, text: str) -> bool:
        casuals = [
            "olá", "oi", "bom dia", "boa tarde", "boa noite",
            "tudo bem", "como vai", "como você está", "e aí",
        ]
        t = text.lower().strip()
        return len(t) < 30 and any(c in t for c in casuals)

    def _handle_chat(self, user_input: str, mood_ctx) -> str:
        system = self.personality.build_system_prompt(
            mood_ctx, user_name=self.memory.profile.get("name", "")
        )
        context = self.memory.build_context()
        if context:
            system += "\n\n" + context

        reply = self.chat.reply(user_input, system).strip()
        opener = self.personality.opener(mood_ctx)

        parts = [f"{opener} {reply}" if opener else reply]
        joke = self.personality.maybe_joke(mood_ctx)
        if joke:
            parts.append(f"\n\n_Ps: {joke}_")
        return "\n".join(parts)

    def _handle_agents(self, user_input: str, mood_ctx) -> str:
        body = self.agents.dispatch(user_input)
        return self._wrap_with_personality(body, mood_ctx, topic="agents")

    def _handle_email(self, user_input: str, mood_ctx) -> str:
        if "resumo" in user_input.lower() or "brief" in user_input.lower():
            body = self.email.daily_brief()
        else:
            summaries = self.email.fetch_and_classify(limit=10)
            lines = [f"📬 **{len(summaries)} e-mails recentes:**", ""]
            for s in summaries:
                lines.append(f"• **[{s.category}]** {s.sender}: {s.subject}")
                lines.append(f"  {s.summary}")
                if s.draft_reply:
                    lines.append(f"  💬 _Rascunho:_ {s.draft_reply[:140]}...")
            body = "\n".join(lines)
        return self._wrap_with_personality(body, mood_ctx, topic="email")

    def _handle_decision(self, user_input: str, mood_ctx) -> str:
        options = self._extract_options(user_input) or ["Sim", "Não", "Esperar"]
        result = self.decision.decide(user_input, options)

        lines = [f"🧠 **Decisão analisada:** {user_input}", "", "**Probabilidades:**"]
        for opt, prob in sorted(result.probabilities.items(), key=lambda x: -x[1]):
            bar = "█" * int(prob * 20)
            lines.append(f"  `{opt:<20}` {prob:5.1%} {bar}")
        lines += ["", f"✅ **Recomendação:** {result.recommended}", f"📝 {result.explanation}"]
        return self._wrap_with_personality("\n".join(lines), mood_ctx, topic="decision")

    def _handle_guidance(self, user_input: str, mood_ctx) -> str:
        result = self.guidance.explore(user_input)
        lines = [f"🧭 **Alternativas para:** {user_input}", ""]
        for i, opt in enumerate(result.options, 1):
            lines.append(f"**{i}. {opt.title}**")
            for p in opt.pros:
                lines.append(f"   ✅ {p}")
            for c in opt.cons:
                lines.append(f"   ⚠️ {c}")
            lines.append(f"   💡 _Melhor para:_ {opt.best_for}")
            lines.append("")
        if result.recommendation:
            lines.append(f"🎯 **Recomendação:** {result.recommendation}")
        if result.reasoning:
            lines.append(f"📝 {result.reasoning}")
        return self._wrap_with_personality("\n".join(lines), mood_ctx, topic="guidance")

    def _wrap_with_personality(self, body: str, mood_ctx, topic: str) -> str:
        parts = []
        opener = self.personality.opener(mood_ctx)
        if opener and topic != "decision":
            parts.append(opener)
        parts.append(body)

        if mood_ctx.mood == "stressed":
            parts.append("\n_Respira. Estou aqui se precisar de mais._")
        elif mood_ctx.mood == "tired":
            parts.append("\n_Se quiser, deixo o resto pra amanhã._")
        elif mood_ctx.mood == "sad":
            parts.append("\n_Estou por aqui, sem pressa._")
        return "\n".join(parts)

    def _extract_options(self, text: str) -> list[str]:
        lower = text.lower()
        for sep in (" ou ", " vs "):
            if sep in lower:
                return [
                    p.strip().rstrip("?")
                    for p in re.split(re.escape(sep), text, flags=re.IGNORECASE)
                    if p.strip()
                ]
        return []