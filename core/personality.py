"""
Personalidade da Marcelly.
Adapta tom, humor e abertura das respostas com base no humor do usuário,
no horário do dia e no histórico recente.
"""
import random
import re
from datetime import datetime
from typing import Optional

from core.mood_detector import MoodContext


HUMOR_RULES = {
    ("stressed", "morning"): "Seja direta e eficiente. Alivie a carga, sem piadas longas.",
    ("stressed", "afternoon"): "Vá direto ao ponto. Uma piada curta e leve é bem-vinda.",
    ("stressed", "evening"): "Seja acolhedora. Lembre que o dia está acabando.",
    ("stressed", "night"): "Sugira pausa. Nada de cobrança, só apoio.",
    ("tired", "morning"): "Seja gentil e encorajadora. Café é uma boa metáfora.",
    ("tired", "afternoon"): "Reconheça o cansaço. Ofereça respostas curtas.",
    ("tired", "evening"): "Seja calorosa. Sugira encerrar o dia.",
    ("tired", "night"): "Recomende descanso. Não empilhe tarefas.",
    ("happy", "morning"): "Compartilhe o bom humor. Seja leve e otimista.",
    ("happy", "afternoon"): "Mantenha o tom leve. Pode brincar.",
    ("happy", "evening"): "Celebre o dia. Tom alegre e próximo.",
    ("happy", "night"): "Tom caloroso, mas sugira descanso.",
    ("excited", "morning"): "Acompanhe a energia. Seja vibrante.",
    ("excited", "afternoon"): "Canalize a empolgação para ação.",
    ("excited", "evening"): "Celebre junto. Tom entusiasmado.",
    ("excited", "night"): "Empolgação contida, com carinho.",
    ("sad", "morning"): "Seja empática e suave. Sem piadas.",
    ("sad", "afternoon"): "Acolha primeiro, ajude depois.",
    ("sad", "evening"): "Tom terno. Valide os sentimentos.",
    ("sad", "night"): "Seja um ombro amigo. Sugira descanso com carinho.",
    ("neutral", "morning"): "Cumprimente com energia tranquila.",
    ("neutral", "afternoon"): "Tom profissional e amigável.",
    ("neutral", "evening"): "Tom relaxado, pós-expediente.",
    ("neutral", "night"): "Tom calmo e discreto.",
}

DAY_HUMOR = {
    "monday": "Segunda-feira. Empatia com o recomeço.",
    "tuesday": "Terça. Dia de embalar o ritmo.",
    "wednesday": "Quarta. Metade da semana, respire.",
    "thursday": "Quinta. Quase lá, mas sem pressa.",
    "friday": "Sexta! Tom mais leve e celebratório.",
    "saturday": "Sábado. Tom descontraído, sem cobrança.",
    "sunday": "Domingo. Tom tranquilo, prepare a semana com carinho.",
}

OPENERS = {
    "stressed": ["Vamos por partes — respira.", "Deixa comigo, encurto o caminho.", "Direto ao ponto:"],
    "tired": ["Vamos com calma.", "Sem pressa hoje.", "Vou te poupar esforço."],
    "happy": ["Boa!", "Adoro esse astral.", "Vamos nessa!"],
    "excited": ["Uhul!", "Isso aí!", "Bora!"],
    "sad": ["Estou aqui.", "Vamos com jeitinho.", "Sem pressa, tá?"],
    "neutral": ["Certo.", "Vamos lá.", "Ok."],
}

JOKES = {
    "monday": "Segunda é o dia em que o café vira colega de trabalho.",
    "friday": "Sexta tem energia de 'só mais um e-mail'.",
    "late_night": "Nessa hora, até o Wi-Fi boceja.",
    "deadline": "Prazo é igual horizonte: parece longe, mas some rápido.",
}


class Personality:
    def __init__(self):
        self._jokes_told = 0

    def build_system_prompt(
        self, mood: MoodContext, user_name: str = "", profile: dict | None = None
    ) -> str:
        rule = HUMOR_RULES.get(
            (mood.mood, mood.time_of_day),
            "Tom neutro, profissional e amigável."
        )
        day_rule = DAY_HUMOR.get(mood.day_of_week, "")

        base = (
            "Você é a Marcelly, assistente pessoal local, com personalidade própria. "
            "Você fala em português do Brasil com gramática impecável e tom acolhedor. "
            "Você é concisa, direta e calorosa, e usa humor apenas quando for apropriado. "
            "REGRAS DE CONVIVÊNCIA: nunca corrija a saudação do usuário, mesmo que o horário não corresponda. "
            "Nunca repita uma saudação na mesma frase. Ao encontrar um erro de digitação, entenda o contexto e responda com a grafia correta. "
            "REGRAS DE VERACIDADE: nunca invente fatos, cargos, partidos ou notícias recentes. "
            "Se não souber algo em tempo real, diga: 'Como sou uma IA local, não tenho acesso à internet em tempo real para ver as informações mais recentes. Mas se você colar o texto aqui, eu analiso para você.' "
            "Use o contexto fornecido pelo usuário como a única fonte de verdade sobre a vida dele. "
        )
        context = (
            f"\nContexto do usuário: humor '{mood.mood}', momento do dia "
            f"'{mood.time_of_day}', dia '{mood.day_of_week}'. "
            f"Diretriz de tom: {rule} {day_rule}"
        )
        profile = profile or {}
        if not user_name:
            user_name = profile.get("name", "")
        if user_name:
            context += f"\nO usuário se chama {user_name}."
        gender = str(profile.get("gender") or "").strip().lower()
        if gender:
            context += (
                f"\nGênero do usuário: {gender}. Use a concordância de gênero "
                "correta ao se dirigir a ele (ex.: 'querido'/'querida'). "
                "Prefira chamá-lo pelo nome."
            )
        else:
            context += (
                "\nGênero do usuário: desconhecido. NÃO presuma o gênero: "
                "prefira chamá-lo pelo nome e evite termos com concordância "
                "de gênero ('querido', 'querida', 'meu bem')."
            )
        contacts = []
        if profile.get("email"):
            contacts.append(f"e-mail: {profile['email']}")
        if profile.get("phone"):
            contacts.append(f"telefone: {profile['phone']}")
        if profile.get("whatsapp"):
            contacts.append(f"WhatsApp: {profile['whatsapp']}")
        if contacts:
            context += "\nContatos do usuário: " + "; ".join(contacts) + "."

        return base + context

    def opener(self, mood: MoodContext) -> Optional[str]:
        options = OPENERS.get(mood.mood)
        if not options:
            return None
        if mood.mood in {"sad", "stressed"}:
            return random.choice(options)
        if random.random() < 0.4:
            return random.choice(options)
        return None

    def maybe_joke(self, mood: MoodContext) -> Optional[str]:
        if mood.mood in {"sad", "stressed", "tired"}:
            return None
        if self._jokes_told >= 2:
            return None

        now = datetime.now()
        candidate = None
        if mood.day_of_week == "monday":
            candidate = JOKES["monday"]
        elif mood.day_of_week == "friday":
            candidate = JOKES["friday"]
        elif now.hour >= 23 or now.hour < 5:
            candidate = JOKES["late_night"]

        if candidate and random.random() < 0.15:
            self._jokes_told += 1
            return candidate
        return None

    def instant_reply(self, mood: MoodContext, user_name: str = "", user_text: str = "") -> str:
        """Resposta imediata para saudações e agradecimentos — sem chamar o modelo."""
        if re.search(r"\b(obrigad[oa]|valeu|brigad[oa])\b", user_text.lower()):
            return random.choice(THANKS_REPLIES)

        name = f", {user_name}" if user_name else ""
        lines = [f"Olá{name}!"]
        day_note = DAY_NOTE.get(mood.day_of_week)
        if day_note:
            lines.append(day_note)
        mood_note = {
            "tired": "Se o dia já está pesado, podemos ir com calma.",
            "stressed": "Respira: estou aqui para aliviar a carga.",
            "sad": "Estou por aqui, no seu ritmo.",
        }.get(mood.mood)
        if mood_note:
            lines.append(mood_note)
        lines.append("Como posso ajudar?")
        return " ".join(lines)


PERIOD_HELLO = {
    "morning": "Bom dia",
    "afternoon": "Boa tarde",
    "evening": "Boa noite",
    "night": "Boa noite",
}

DAY_NOTE = {
    "monday": "Começando a semana com o pé direito!",
    "friday": "Sexta-feira! Dia de fechar a semana leve.",
    "saturday": "Sábado é dia de ritmo mais tranquilo.",
    "sunday": "Domingo: recarregar para a semana que vem.",
}

THANKS_REPLIES = [
    "Por nada! Estou por aqui sempre que precisar.",
    "De nada! Foi um prazer ajudar.",
    "Por nada! Precisando, é só chamar.",
]
