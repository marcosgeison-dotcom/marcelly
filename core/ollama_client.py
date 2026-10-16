"""
Wrapper do cliente Ollama.
Toda comunicação é local — nenhum dado sai da máquina.
"""
import json
from typing import Any, Optional
from ollama import Client, ResponseError

from config import CONFIG


class OllamaClient:
    def __init__(self):
        self.client = Client(host=CONFIG.ollama.host)

    def chat(
        self,
        prompt: str,
        system: str = "",
        model: Optional[str] = None,
        format_json: bool = False,
    ) -> str:
        """
        Envia uma mensagem ao modelo local.
        Se format_json=True, usa constrained decoding do Ollama
        para garantir JSON válido.
        """
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        try:
            response = self.client.chat(
                model=model or CONFIG.ollama.model,
                messages=messages,
                options={
                    "temperature": CONFIG.ollama.temperature,
                    "num_ctx": 4096,
                },
                format="json" if format_json else "",
            )
            return response.message.content
        except ResponseError as e:
            raise RuntimeError(f"Erro no Ollama: {e.error}") from e

    def chat_stream(self, prompt: str, system: str = "", model: Optional[str] = None):
        """Gera a resposta em pedaços (streaming local) — a primeira palavra
        aparece em ~1 segundo, em vez de esperar a resposta inteira."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        try:
            stream = self.client.chat(
                model=model or CONFIG.ollama.model,
                messages=messages,
                options={
                    "temperature": CONFIG.ollama.temperature,
                    "num_ctx": 4096,
                },
                stream=True,
            )
            for part in stream:
                piece = part.message.content
                if piece:
                    yield piece
        except ResponseError as e:
            raise RuntimeError(f"Erro no Ollama: {e.error}") from e

    def classify_intent(self, user_input: str) -> dict[str, Any]:
        """
        Classifica a intenção do usuário em uma das frentes.
        Usa constrained decoding para garantir JSON válido.
        """
        system = (
            "Você é um classificador de intenções. Dado o texto do usuário, "
            "retorne APENAS um JSON com os campos: "
            "'intent' (chat|email|decision|guidance|automation), "
            "'confidence' (0.0 a 1.0), "
            "'reasoning' (explicação curta em português). "
            "Use 'chat' para conversa casual, saudações, agradecimentos ou "
            "perguntas gerais que não caibam nas outras frentes. "
            "Não gere texto fora do JSON."
        )
        raw = self.chat(user_input, system=system, format_json=True)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"intent": "chat", "confidence": 0.5, "reasoning": "Fallback"}

    def embed(self, text: str) -> list[float]:
        """Gera embeddings locais para memória de longo prazo."""
        response = self.client.embed(
            model="nomic-embed-text",
            input=text,
        )
        return response["embeddings"][0]
