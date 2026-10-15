"""
Módulo de decisão calibrada.
Usa tydex (open source, clone comportamental do Jev) para retornar
probabilidades reais para cada opção.
"""
from dataclasses import dataclass, field

from tydex import Tydex
from tydex.backends.ollama import OllamaBackend  # backend local

from config import CONFIG


@dataclass
class DecisionResult:
    options: list[str]
    probabilities: dict[str, float]
    recommended: str
    confidence: float
    explanation: str


class DecisionModule:
    def __init__(self):
        backend = OllamaBackend(
            host=CONFIG.ollama.host,
            model=CONFIG.ollama.decision_model,
        )
        self.decider = Tydex(backend, model=CONFIG.ollama.decision_model)

    def decide(self, question: str, options: list[str], context: str = "") -> DecisionResult:
        """
        Retorna uma distribuição de probabilidade calibrada sobre as opções.
        """
        state = {"question": question, "context": context}
        result = self.decider.choice(
            state,
            options,
            question=question,
        )

        probs = result.probabilities
        recommended = result.choice
        confidence = result.confidence

        explanation = (
            f"Com base no contexto fornecido, a opção mais provável é "
            f"'{recommended}' com {confidence:.0%} de confiança. "
            f"Distribuição: " + ", ".join(f"{k}: {v:.0%}" for k, v in probs.items())
        )

        return DecisionResult(
            options=options,
            probabilities=probs,
            recommended=recommended,
            confidence=confidence,
            explanation=explanation,
        )

    def decide_yes_no(self, question: str, context: str = "") -> dict:
        """Decisão binária com probabilidade calibrada."""
        result = self.decider.noul({"question": question, "context": context}, question)
        return {
            "probability": result.probability,
            "boolean": result.bool_value,
            "explanation": f"Probabilidade de sim: {result.probability:.0%}",
        }