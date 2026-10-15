"""
Roteador de intenções.
Combina regras determinísticas (rápidas) com classificação via LLM (precisa).
"""
import re
from dataclasses import dataclass
from typing import Optional

from core.ollama_client import OllamaClient


@dataclass
class RoutingResult:
    intent: str          # "email" | "decision" | "guidance" | "automation"
    confidence: float
    reasoning: str
    module: str          # nome do módulo a acionar


# Palavras-chave para roteamento determinístico (rápido, sem LLM)
KEYWORDS = {
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
}


class IntentRouter:
    def __init__(self):
        self.llm = OllamaClient()

    def route(self, user_input: str) -> RoutingResult:
        # 1. Tenta roteamento determinístico primeiro (latência baixa)
        for intent, patterns in KEYWORDS.items():
            for pattern in patterns:
                if re.search(pattern, user_input, re.IGNORECASE):
                    return RoutingResult(
                        intent=intent,
                        confidence=0.85,
                        reasoning=f"Correspondência de palavra-chave: {pattern}",
                        module=f"{intent}_module",
                    )

        # 2. Fallback: classificação via LLM local
        result = self.llm.classify_intent(user_input)
        intent = result.get("intent", "guidance")
        return RoutingResult(
            intent=intent,
            confidence=result.get("confidence", 0.5),
            reasoning=result.get("reasoning", ""),
            module=f"{intent}_module" if intent != "automation" else "automation_module",
        )