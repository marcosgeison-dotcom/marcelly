"""
Detecta o humor do usuário a partir da mensagem e do contexto temporal.
Combina regras rápidas (keywords) com análise via LLM quando ambíguo.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from core.ollama_client import OllamaClient

Mood = Literal["happy", "tired", "stressed", "excited", "neutral", "sad"]


@dataclass
class MoodContext:
    mood: Mood
    confidence: float
    time_of_day: str      # "morning" | "afternoon" | "evening" | "night"
    day_of_week: str      # "monday" ... "sunday"
    is_weekend: bool
    reason: str


MOOD_KEYWORDS = {
    "stressed": ["cansado", "estressado", "corrido", "sem tempo", "urgente", "prazo", "pressão", "ansioso"],
    "tired": ["exausto", "sono", "dormir", "cansado", "acabado", "sem energia"],
    "happy": ["feliz", "ótimo", "alegre", "bom dia", "tudo bem", "maravilhoso", "adorei"],
    "excited": ["animado", "empolgado", "não vejo a hora", "ansioso", "uhul", "eba"],
    "sad": ["triste", "desanimado", "chateado", "desapontado", "ruim"],
}


class MoodDetector:
    def __init__(self):
        self.llm = OllamaClient()

    def detect(self, message: str) -> MoodContext:
        now = datetime.now()
        time_of_day = self._time_of_day(now.hour)
        day_of_week = now.strftime("%A").lower()
        is_weekend = now.weekday() >= 5

        msg_lower = message.lower()
        for mood, kws in MOOD_KEYWORDS.items():
            for kw in kws:
                if kw in msg_lower:
                    return MoodContext(
                        mood=mood,
                        confidence=0.75,
                        time_of_day=time_of_day,
                        day_of_week=day_of_week,
                        is_weekend=is_weekend,
                        reason=f"Palavra-chave: {kw}",
                    )

        mood = self._llm_mood(message)
        return MoodContext(
            mood=mood,
            confidence=0.6,
            time_of_day=time_of_day,
            day_of_week=day_of_week,
            is_weekend=is_weekend,
            reason="Análise via LLM local",
        )

    def _time_of_day(self, hour: int) -> str:
        if 5 <= hour < 12: return "morning"
        if 12 <= hour < 18: return "afternoon"
        if 18 <= hour < 23: return "evening"
        return "night"

    def _llm_mood(self, message: str) -> Mood:
        system = (
            "Classifique o humor do usuário. Retorne APENAS uma palavra entre: "
            "happy, tired, stressed, excited, neutral, sad."
        )
        raw = self.llm.chat(message, system=system).strip().lower()
        for m in ["happy", "tired", "stressed", "excited", "sad"]:
            if m in raw:
                return m
        return "neutral"
