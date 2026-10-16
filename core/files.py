"""
Marcelly — Leitura de arquivos anexados no chat (100% local).

Extrai texto de arquivos enviados pelo usuário para que o orquestrador
consiga analisá-los. Nada é enviado para a internet.
"""
from __future__ import annotations

import io

# Tamanho máximo de texto enviado ao modelo (evita estourar o contexto)
MAX_TEXT_CHARS = 12000

TEXT_SUFFIXES = {
    "txt", "md", "markdown", "log", "csv", "tsv", "json", "yaml", "yml", "ini",
    "py", "js", "ts", "jsx", "tsx", "html", "css", "xml", "sql", "sh", "bat",
    "ps1", "java", "c", "cpp", "cs", "go", "rb", "php", "rs", "toml", "cfg",
}


def extract_text(filename: str, data: bytes) -> str:
    """Extrai texto de um anexo. Devolve "" quando o formato não é suportado."""
    suffix = ""
    if filename and "." in filename:
        suffix = filename.rsplit(".", 1)[-1].lower()

    if suffix == "pdf":
        return _pdf_text(data)
    if suffix == "docx":
        return _docx_text(data)
    if suffix in TEXT_SUFFIXES or not suffix:
        return _plain_text(data)
    return ""


def _pdf_text(data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except Exception:
        return ""
    try:
        reader = PdfReader(io.BytesIO(data))
        pages = [(page.extract_text() or "") for page in reader.pages]
        return _limit("\n".join(p for p in pages if p))
    except Exception:
        return ""


def _docx_text(data: bytes) -> str:
    try:
        from docx import Document
    except Exception:
        return ""
    try:
        document = Document(io.BytesIO(data))
        parts = [p.text for p in document.paragraphs if p.text]
        return _limit("\n".join(parts))
    except Exception:
        return ""


def _plain_text(data: bytes) -> str:
    # Binário (imagem, executável etc.): não é texto legível
    if b"\x00" in data[:2048]:
        return ""
    for encoding in ("utf-8", "latin-1"):
        try:
            return _limit(data.decode(encoding))
        except Exception:
            continue
    return ""


def _limit(text: str) -> str:
    text = text.strip()
    if not text:
        return ""
    if len(text) > MAX_TEXT_CHARS:
        return text[:MAX_TEXT_CHARS] + "\n… (conteúdo truncado para a análise)"
    return text
