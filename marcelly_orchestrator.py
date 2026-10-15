"""
Marcelly — Orquestrador principal.
Recebe entrada do usuário, classifica a intenção e roteia para o módulo correto.
"""
import logging
import sys
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from config import CONFIG
from modules.intent_router import IntentRouter
from modules.email_module import EmailModule
from modules.decision_module import DecisionModule
from modules.guidance_module import GuidanceModule

logging.basicConfig(level=CONFIG.log_level)
console = Console()


class MarcellyOrchestrator:
    def __init__(self):
        self.router = IntentRouter()
        self.email = EmailModule()
        self.decision = DecisionModule()
        self.guidance = GuidanceModule()
        self.memory: list[dict[str, Any]] = []

    def _ensure_ollama(self) -> bool:
        """Configuração inicial: garante Ollama instalado, rodando e com os modelos."""
        import shutil
        import subprocess
        import time
        from rich.prompt import Confirm
        from ollama import Client

        def _ok() -> bool:
            try:
                Client(host=CONFIG.ollama.host).list()
                return True
            except Exception:
                return False

        if _ok():
            return True

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
        if not _ok():
            subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            for _ in range(10):
                time.sleep(2)
                if _ok():
                    break
        if not _ok():
            console.print(
                "[red]Não consegui iniciar o Ollama.[/red] "
                "Abra o aplicativo Ollama e rode o Marcelly novamente."
            )
            return False

        for model in (CONFIG.ollama.model, CONFIG.ollama.decision_model, "nomic-embed-text"):
            console.print(f"[cyan]Baixando modelo: {model}[/cyan]")
            subprocess.run(["ollama", "pull", model], check=False)
        return _ok()

    def handle(self, user_input: str) -> str:
        """Processa uma entrada e devolve a resposta formatada."""
        routing = self.router.route(user_input)
        console.print(
            f"[dim]→ Intenção: {routing.intent} "
            f"(confiança: {routing.confidence:.0%}) — {routing.reasoning}[/dim]"
        )

        if routing.intent == "email":
            return self._handle_email(user_input)
        if routing.intent == "decision":
            return self._handle_decision(user_input)
        if routing.intent == "guidance":
            return self._handle_guidance(user_input)

        return "Não entendi. Tente algo como: 'resuma meus e-mails', " \
               "'devo aceitar a proposta?' ou 'me dê opções para o jantar'."

    def _handle_email(self, user_input: str) -> str:
        if "resumo" in user_input.lower() or "brief" in user_input.lower():
            return self.email.daily_brief()
        summaries = self.email.fetch_and_classify(limit=10)
        lines = [f"📬 {len(summaries)} e-mails recentes:"]
        for s in summaries:
            lines.append(f"• [{s.category}] {s.sender}: {s.subject}")
            lines.append(f"  {s.summary}")
            if s.draft_reply:
                lines.append(f"  💬 Rascunho: {s.draft_reply[:120]}...")
        return "\n".join(lines)

    def _handle_decision(self, user_input: str) -> str:
        # Extrai opções do texto (simples: separadas por " ou " ou vírgulas)
        options = self._extract_options(user_input)
        if not options:
            options = ["Sim", "Não", "Esperar mais informações"]

        result = self.decision.decide(user_input, options)
        lines = [
            f"🧠 Decisão analisada: {user_input}",
            "",
            "📊 Probabilidades:",
        ]
        for opt, prob in sorted(result.probabilities.items(), key=lambda x: -x[1]):
            bar = "█" * int(prob * 20)
            lines.append(f"  {opt:20s} {prob:5.1%} {bar}")
        lines += [
            "",
            f"✅ Recomendação: {result.recommended}",
            f"📝 {result.explanation}",
        ]
        return "\n".join(lines)

    def _handle_guidance(self, user_input: str) -> str:
        result = self.guidance.explore(user_input)
        lines = [f"🧭 Alternativas para: {user_input}", ""]
        for i, opt in enumerate(result.options, 1):
            lines.append(f"  {i}. {opt.title}")
            for p in opt.pros:
                lines.append(f"     ✅ {p}")
            for c in opt.cons:
                lines.append(f"     ⚠️ {c}")
            lines.append(f"     💡 Melhor para: {opt.best_for}")
            lines.append("")
        if result.recommendation:
            lines.append(f"🎯 Recomendação: {result.recommendation}")
        if result.reasoning:
            lines.append(f"📝 {result.reasoning}")
        return "\n".join(lines)

    def _extract_options(self, text: str) -> list[str]:
        """Extração simples de opções separadas por ' ou ', ' vs ' ou vírgulas."""
        import re
        if " ou " in text:
            parts = re.split(r"\s+ou\s+", text, flags=re.IGNORECASE)
            return [p.strip().rstrip("?") for p in parts if p.strip()]
        if " vs " in text.lower():
            parts = re.split(r"\s+vs\.?\s+", text, flags=re.IGNORECASE)
            return [p.strip().rstrip("?") for p in parts if p.strip()]
        return []

    def run_cli(self):
        """Modo interativo de linha de comando."""
        if not self._ensure_ollama():
            return
        console.print(Panel.fit(
            "[bold cyan]Marcelly[/bold cyan] — Assistente local\n"
            "[dim]E-mails · Decisões · Direcionamentos[/dim]\n"
            "Digite [bold]sair[/bold] para encerrar.",
            border_style="cyan",
        ))
        while True:
            try:
                user_input = Prompt.ask("\n[bold cyan]Você[/bold cyan]")
            except (KeyboardInterrupt, EOFError):
                break
            if user_input.strip().lower() in {"sair", "exit", "quit"}:
                break
            if not user_input.strip():
                continue
            try:
                response = self.handle(user_input)
            except ConnectionError:
                console.print(Panel(
                    "[bold red]Não consegui falar com o Ollama.[/bold red]\n"
                    "Verifique se ele está instalado e rodando:\n"
                    "[cyan]ollama serve[/cyan]  (em outro terminal)\n"
                    "E baixe o modelo:\n"
                    "[cyan]ollama pull llama3.2:8b[/cyan]",
                    border_style="red", title="Erro de conexão",
                ))
                continue
            except Exception as e:
                console.print(Panel(f"[red]Algo deu errado:[/red] {e}", border_style="red", title="Erro"))
                continue
            console.print(Panel(response, border_style="green", title="Marcelly"))

        console.print("[dim]Até logo.[/dim]")


if __name__ == "__main__":
    orchestrator = MarcellyOrchestrator()
    if len(sys.argv) > 1:
        # Modo one-shot: python marcelly_orchestrator.py "resuma meus e-mails"
        if orchestrator._ensure_ollama():
            print(orchestrator.handle(" ".join(sys.argv[1:])))
    else:
        orchestrator.run_cli()