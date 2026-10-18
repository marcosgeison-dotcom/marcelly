"""Cliente opcional para a cascata de processamento em nuvem."""
import json
import urllib.error
import urllib.request

import psutil

from config import CONFIG


class CloudClient:
    def available(self) -> bool:
        return bool(CONFIG.cloud.api_key) and not CONFIG.local_only

    def should_use(self, prompt: str) -> bool:
        if not self.available():
            return False
        if psutil.virtual_memory().percent >= CONFIG.cloud.ram_threshold:
            return True
        text = prompt.lower()
        complex_terms = (
            "analise", "análise", "planeje", "planejar", "estratégia", "estrategia",
            "compare", "comparar", "documento", "arquitetura", "debug", "depure",
            "código", "codigo", "passo a passo",
        )
        return len(prompt) >= 600 or any(term in text for term in complex_terms)

    def chat(self, prompt: str, system: str) -> str:
        if not self.available():
            raise RuntimeError("Nuvem indisponível")
        payload = json.dumps({
            "model": CONFIG.cloud.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "temperature": CONFIG.ollama.temperature,
            "stream": False,
        }).encode("utf-8")
        request = urllib.request.Request(
            CONFIG.cloud.base_url.rstrip("/") + "/chat/completions",
            data=payload,
            headers={
                "Authorization": f"Bearer {CONFIG.cloud.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=75) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as error:
            raise RuntimeError(f"Erro ao consultar a nuvem: {error.reason}") from error
        try:
            return data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError) as error:
            raise RuntimeError("Resposta inválida da nuvem") from error
