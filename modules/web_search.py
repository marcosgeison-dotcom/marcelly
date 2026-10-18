"""Busca web leve para perguntas que dependem de dados recentes."""
import hashlib
import logging
import sqlite3
import time

from config import DATA_DIR
from duckduckgo_search import DDGS

log = logging.getLogger("marcelly.web_search")
WEB_CACHE_TTL_SECONDS = 3 * 60 * 60

def _cache_connection():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DATA_DIR / "marcelly.db"))
    conn.execute("CREATE TABLE IF NOT EXISTS web_cache (cache_key TEXT PRIMARY KEY, context TEXT NOT NULL, expires_at REAL NOT NULL)")
    return conn

def _cache_key(query: str) -> str:
    normalized = " ".join(query.lower().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def search_web(query: str, max_results: int = 3) -> str:
    """Busca resultados públicos e devolve somente o contexto essencial ao modelo."""
    log.info("Iniciando busca web: %s", query)
    key = _cache_key(query)
    with _cache_connection() as conn:
        row = conn.execute("SELECT context FROM web_cache WHERE cache_key = ? AND expires_at > ?", (key, time.time())).fetchone()
    if row:
        log.info("Busca web atendida pelo cache local")
        return row[0]
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
    if context:
        with _cache_connection() as conn:
            conn.execute("INSERT OR REPLACE INTO web_cache (cache_key, context, expires_at) VALUES (?, ?, ?)", (key, context, time.time() + WEB_CACHE_TTL_SECONDS))
    log.info("Busca web concluída com %d resultado(s)", len(formatted_results))
    return context
