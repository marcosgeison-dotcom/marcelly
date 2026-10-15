# Marcelly

Assistente de IA **local e open source** que processa dados no seu computador — voz e texto, automação do sistema e decisões calibradas, sem nuvem e sem telemetria.

## Estrutura

```
marcelly/
├── marcelly_orchestrator.py   # Orquestrador principal
├── config.py                  # Configuração local (Ollama etc.)
├── modules/
│   ├── intent_router.py       # Roteador de intenções
│   ├── email_module.py        # E-mail local-first (IMAP + Ollama)
│   ├── decision_module.py     # Decisão calibrada (tydex/brier)
│   └── guidance_module.py     # Direcionamentos e escolhas
├── core/
│   └── ollama_client.py       # Wrapper do cliente Ollama
├── requirements.txt
└── docs/                      # Páginas, estilos e arquitetura
```

## Instalação

```bash
pip install -r requirements.txt
python marcelly_orchestrator.py
```

Requer [Ollama](https://ollama.com) rodando localmente (`OLLAMA_HOST`, padrão `http://localhost:11434`).

## Licença

MIT — veja o arquivo [LICENSE](LICENSE).
