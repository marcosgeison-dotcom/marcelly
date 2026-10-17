"""Proteções para fatos políticos e informações que exigem atualização em tempo real."""
import re


CURRENT_AFFAIRS = re.compile(
    r"\b(eleição|eleições|eleitoral|corrida presidencial|pesquisa eleitoral|\"
    r"intenção de voto|quem está (?:na )?frente|quem lidera|candidato)\b",
    re.IGNORECASE,
)
LULA_PARTY = re.compile(r"\b(lula|luiz inácio lula da silva)\b.*\b(pt|pp|partido)\b|\b(pt|pp|partido)\b.*\b(lula|luiz inácio lula da silva)\b", re.IGNORECASE)


def safe_current_affairs_reply(user_input: str) -> str | None:
    """Impede que o modelo local invente dados políticos atuais ou atribuições partidárias."""
    if LULA_PARTY.search(user_input):
        return (
            "O registro de referência local é: Luiz Inácio Lula da Silva é filiado ao "
            "Partido dos Trabalhadores (PT), não ao Partido Progressista (PP). Para "
            "informações eleitorais atuais, não vou inferir ou inventar dados sem uma fonte atualizada."
        )
    if CURRENT_AFFAIRS.search(user_input):
        return (
            "Como sou uma IA local, não tenho acesso à internet em tempo real para consultar pesquisas, candidaturas ou resultados eleitorais. "
            "Para não arriscar uma informação incorreta, não vou afirmar quem está à frente. "
            "Se você colar aqui o texto de uma pesquisa, eu analiso para você."
        )
    return None
