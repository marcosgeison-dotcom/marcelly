"""
Roteador de intenções — inclui conversa casual (chat) e agentes.
Combina regras determinísticas (rápidas) com classificação via LLM (precisa).
"""
import re
from dataclasses import dataclass

from core.ollama_client import OllamaClient


@dataclass
class RoutingResult:
    intent: str          # "chat" | "email" | "decision" | "guidance" | "agents" | "automation"
    confidence: float
    reasoning: str
    module: str          # nome do módulo a acionar


KEYWORDS = {
    "chat": [
        r"^\s*(ol[áa]|oi|e a[íi]|bom dia|boa tarde|boa noite|tudo bem|como vai)",
        r"\b(obrigad[oa]|valeu|brigad[oa])\b",
    ],
    "email": [
        r"\b(e-?mail|inbox|caixa de entrada|gmail|outlook|imap|responder|rascunho)\b",
        r"\b(mensagem|correio|enviar|receber)\b",
    ],
    "decision": [
        r"\b(decidir|decisão|escolher|opção|devo|vale a pena|melhor caminho)\b",
        r"\b(probabilidade|chance|risco|comparar)\b",
    ],
    "guidance": [
        r"\b(opções|alternativas|caminhos|direcionamento|sugestões|ideias)\b",
        r"\b(como fazer|o que fazer|me ajude a pensar)\b",
    ],
    "agents": [
        r"\b(agente|agentes|quais agentes)\b",
        r"\b(lembrete|lembretes|me lembre|lembra-?me|me avise)\b",
        r"\b(plano|planeje|planejar|monte uma rotina|passo a passo)\b",
    ],
}


class IntentRouter:
    def __init__(self):
        self.llm = OllamaClient()

    def route(self, user_input: str) -> RoutingResult:
        for intent, patterns in KEYWORDS.items():
            for pattern in patterns:
                if re.search(pattern, user_input, re.IGNORECASE):
                    return RoutingResult(
                        intent=intent,
                        confidence=0.85,
                        reasoning=f"Correspondência de palavra-chave: {pattern}",
                        module=f"{intent}_module",
                    )

        result = self.llm.classify_intent(user_input)
        intent = result.get("intent", "chat")
        return RoutingResult(
            intent=intent,
            confidence=result.get("confidence", 0.5),
            reasoning=result.get("reasoning", ""),
            module=f"{intent}_module",
        )