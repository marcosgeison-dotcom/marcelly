"""
Módulo de conversa casual.
Usado quando a intenção não é e-mail, decisão ou direcionamento.
"""
from core.ollama_client import OllamaClient


class ChatModule:
    def __init__(self):
        self.llm = OllamaClient()

    def reply(self, user_input: str, system_prompt: str) -> str:
        return self.llm.chat(user_input, system=system_prompt).strip()

    def reply_stream(self, user_input: str, system_prompt: str):
        """Gera a resposta em pedaços (streaming local)."""
        for piece in self.llm.chat_stream(user_input, system=system_prompt):
            yield piece
