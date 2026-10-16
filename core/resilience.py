"""
Recuperacao automatica compartilhada.

Todos os agentes e skills da Marcelly usam estes helpers: quando uma
tentativa falha (modelo indisponivel, servidor fora do ar, banco ocupado),
as alternativas sao testadas automaticamente antes de reportar falha —
e a mensagem final lista o que foi tentado, nunca um erro cru.
"""
import time
from collections import Counter

from core.debug import DEBUG
from core.performance import PERF


def try_alternatives(label: str, steps, retries: int = 1, delay: float = 0.8) -> str:
    """
    Executa as alternativas em ordem ate uma funcionar.
    'steps' e uma lista de (nome, funcao) — cada uma e tentada
    'retries' + 1 vezes com 'delay' entre tentativas.
    Retorna o resultado da primeira que funcionar; se nenhuma funcionar,
    devolve uma mensagem amigavel listando o que foi tentado.
    """
    errors = []
    for name, fn in steps:
        for attempt in range(retries + 1):
            try:
                result = fn()
                if attempt:
                    DEBUG.log("resilience", event="alternativa_recuperou", label=label, step=name)
                return result
            except Exception as exc:
                errors.append(name + ": " + str(exc))
                DEBUG.log("resilience", event="falha", label=label, step=name, error=str(exc))
                if attempt < retries:
                    time.sleep(delay)
    return friendly_failure(label, errors)


def friendly_failure(label: str, errors) -> str:
    tried = "\n".join("- " + e for e in errors)
    return (
        "\u26a0\ufe0f **" + label + "** nao conseguiu concluir agora. Ja testei as alternativas:\n\n"
        + tried + "\n\n"
        "O que pode ajudar:\n"
        "- Diga _\"status\"_ para verificar se o modelo local esta rodando.\n"
        "- Tente de novo em alguns segundos (o modelo pode estar ocupado).\n"
        "- Se persistir, ative o botao **Depuracao** e veja os detalhes no painel."
    )


def chat_with_retry(llm, prompt: str, system: str = "", format_json: bool = False,
                    retries: int = 1, delay: float = 0.8) -> str:
    """Chamada ao modelo local com nova tentativa automatica antes de desistir."""
    last = None
    # No modo rapido, sem repeticao: entrega a resposta na primeira tentativa
    attempts = 0 if PERF.is_accelerated() else retries
    for attempt in range(attempts + 1):
        try:
            return llm.chat(prompt, system=system, format_json=format_json)
        except Exception as exc:
            last = exc
            DEBUG.log("resilience", event="llm_nova_tentativa", attempt=attempt, error=str(exc))
            if attempt < retries:
                time.sleep(delay)
    raise last


def with_email_alternatives(email_module, fn):
    """
    Executa uma operacao de e-mail (fn) tentando servidores alternativos
    antes de reportar falha. Retorna (resultado, None) ou (None, mensagem).
    """
    if not email_module.is_configured():
        return None, email_module.setup_guide()
    try:
        return fn(), None
    except Exception as exc:
        last_error = str(exc)
        DEBUG.log("resilience", event="email_falha", error=last_error)
    fixed, error, _host, tried = email_module.try_alternative_hosts()
    if fixed:
        try:
            return fn(), None
        except Exception as exc:
            last_error = str(exc)
    tried_txt = ", ".join("**" + host + "**" for host in tried) or "nenhum"
    return None, (
        "\u26a0\ufe0f Nao consegui conectar agora:\n" + last_error + "\n\n"
        "\U0001f50d Ja testei automaticamente estes servidores: " + tried_txt + " — nenhum aceitou.\n\n"
        "Alternativas que costumam resolver:\n"
        "- **Locaweb** e hospedagens brasileiras similares usam o servidor compartilhado **email-ssl.com.br** (porta 993).\n"
        "- **HostGator**: **mail.seudominio.com.br**.\n"
        "- Me envie o servidor IMAP exato do seu provedor que eu atualizo e testo."
    )


# ---------- Alternativas locais (sem depender do modelo) ----------

def simple_plan(request: str) -> str:
    goal = request.strip().rstrip(".") or "seu objetivo"
    return (
        "\U0001f5ed\ufe0f **Plano local (modo simplificado — o modelo nao respondeu):**\n\n"
        "1. Defina em uma frase o resultado desejado: _" + goal + "_.\n"
        "2. Separe o que depende de outra pessoa do que depende so de voce.\n"
        "3. Escolha o primeiro passo mais rapido (algo abaixo de 15 minutos).\n"
        "4. Reserve um horario para os proximos dois passos.\n"
        "5. No fim do dia, revise o que ficou pendente e ajuste.\n\n"
        "_Quando o modelo voltar, peca de novo que eu refino o plano._"
    )


def local_summary(rows) -> str:
    counts = Counter(r["intent"] or "conversa" for r in rows)
    lines = ["\U0001f4dd **Resumo local (modo simplificado — o modelo nao respondeu):**", ""]
    for intent, n in counts.most_common(6):
        lines.append("\u2022 " + str(n) + " pedido(s) de **" + intent + "**")
    lines += ["", "_Quando o modelo voltar, peca de novo para um resumo detalhado._"]
    return "\n".join(lines)


def local_review(rows) -> str:
    vague = [r for r in rows if len(r["user_message"].split()) < 4]
    counts = Counter(r["intent"] or "?" for r in rows)
    lines = ["\U0001f50d **Revisao local (modo simplificado — o modelo nao respondeu):**", ""]
    lines.append("\u2705 **Melhorias sugeridas:**")
    if vague:
        for r in vague[:5]:
            lines.append("\u2022 _\"" + r["user_message"] + "\"_ e curto demais — de mais contexto ao pedir.")
    else:
        lines.append("\u2022 Seus pedidos estao com bom nivel de detalhe.")
    lines += ["", "\u26a0\ufe0f **Falhas encontradas:**"]
    top = counts.most_common(3)
    if top:
        for intent, n in top:
            lines.append("\u2022 " + str(n) + " pedido(s) roteados para **" + intent + "** — se algo nao respondeu como esperava, reformule com a palavra-chave do assunto.")
    else:
        lines.append("\u2022 Nada anormal nos ultimos pedidos.")
    lines += ["", "_Quando o modelo voltar, peca de novo para uma analise completa._"]
    return "\n".join(lines)


def local_ideas(request: str) -> str:
    goal = request.strip().rstrip(".") or "seu pedido"
    return (
        "\U0001f4a1 **Opcoes locais (modo simplificado — o modelo nao respondeu):**\n\n"
        "1. Fazer voce mesmo(a), agora — o caminho mais rapido.\n"
        "2. Pedir ajuda a alguem com experiencia no assunto.\n"
        "3. Usar uma ferramenta ou servico pronto para isso.\n"
        "4. Fazer uma versao minima e ajustar depois.\n"
        "5. Adiar e voltar com mais informacao sobre " + goal + ".\n\n"
        "_Quando o modelo voltar, peca de novo para eu gerar opcoes sob medida._"
    )
