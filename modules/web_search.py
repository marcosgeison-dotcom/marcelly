"""Busca web leve para perguntas que dependem de dados recentes."""
import logging

from duckduckgo_search import DDGS

log = logging.getLogger("marcelly.web_search")


def search_web(query: str, max_results: int = 3) -> str:
    """Busca resultados públicos e devolve somente o contexto essencial ao modelo."""
    log.info("Iniciando busca web: %s", query)
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results, region="br-pt"))
    except Exception as exc:
        log.warning("Busca web indisponível: %s", exc, exc_info=True)
        return ""

    formatted_results = []
    for index, result in enumerate(results, 1):
        title = str(result.get("title") or "Sem título").strip()
        body = str(result.get("body") or "Sem descrição").strip()
        href = str(result.get("href") or "").strip()
        if title or body:
            formatted_results.append(
                f"[{index}] Título: {title}\nResumo: {body[:700]}"
                + (f"\nFonte: {href}" if href else "")
            )
    context = "\n\n".join(formatted_results)
    log.info("Busca web concluída com %d resultado(s)", len(formatted_results))
    return context
