"""
Módulo de direcionamentos e escolhas.
Apresenta alternativas estruturadas com prós, contras e evidências.
"""
from dataclasses import dataclass, field

from core.ollama_client import OllamaClient


@dataclass
class Option:
    title: str
    pros: list[str]
    cons: list[str]
    evidence: str
    best_for: str


@dataclass
class GuidanceResult:
    question: str
    options: list[Option]
    recommendation: str
    reasoning: str


class GuidanceModule:
    def __init__(self):
        self.llm = OllamaClient()

    def explore(self, question: str, context: str = "") -> GuidanceResult:
        """
        Gera 3 a 5 alternativas estruturadas com trade-offs.
        """
        system = (
            "Você é um conselheiro. Dado o pedido do usuário, retorne APENAS JSON com "
            "a estrutura: {'options': [{'title': str, 'pros': [str], 'cons': [str], "
            "'evidence': str, 'best_for': str}], 'recommendation': str, 'reasoning': str}. "
            "Gere entre 3 e 5 opções. Seja honesto sobre incertezas."
        )
        prompt = f"Pergunta: {question}\nContexto: {context}"
        raw = self.llm.chat(prompt, system=system, format_json=True)

        import json
        try:
            data = json.loads(raw)
        except Exception:
            data = {"options": [], "recommendation": "", "reasoning": ""}

        options = [
            Option(
                title=o.get("title", ""),
                pros=o.get("pros", []),
                cons=o.get("cons", []),
                evidence=o.get("evidence", ""),
                best_for=o.get("best_for", ""),
            )
            for o in data.get("options", [])
        ]

        return GuidanceResult(
            question=question,
            options=options,
            recommendation=data.get("recommendation", ""),
            reasoning=data.get("reasoning", ""),
        )