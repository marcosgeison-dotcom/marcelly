"""
Marcelly — Servidor local.
Sobe a interface de chat e conecta ao orquestrador via WebSocket.
Tudo roda em 127.0.0.1 — nada sai da máquina.
"""
import asyncio
import base64
import json
import sys
import threading
import os
import time
import webbrowser
from pathlib import Path

import uvicorn
from fastapi import Body, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from core.debug import DEBUG
from core.orchestrator import MarcellyOrchestrator
from core.startup import create_desktop_shortcut, get_autostart, set_autostart
from core.voice import VoiceEngine

BASE_DIR = Path(__file__).parent
UI_DIR = BASE_DIR / "ui"

app = FastAPI(title="Marcelly", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=str(UI_DIR)), name="static")

orchestrator = MarcellyOrchestrator()
voice = VoiceEngine()


@app.get("/")
async def index():
    return FileResponse(UI_DIR / "index.html")


@app.get("/api/autostart")
async def autostart_state():
    return {"enabled": get_autostart()}


@app.post("/api/autostart")
async def update_autostart(enabled: bool = Body(..., embed=True)):
    ok = set_autostart(enabled)
    return {"enabled": get_autostart() if ok else enabled, "ok": ok}


@app.get("/api/debug")
async def debug_state():
    return {"enabled": DEBUG.enabled, "events": DEBUG.recent(100)}


@app.post("/api/debug")
async def update_debug(enabled: bool = Body(..., embed=True)):
    DEBUG.set_enabled(enabled)
    return {"enabled": DEBUG.enabled, "events": DEBUG.recent(100)}

@app.get("/api/history")
async def history(day: str = None):
    """Histórico separado por dia (sem 'day': lista de dias; com 'day': o dia escolhido)."""
    memory = orchestrator.memory
    if day:
        return {"day": day, "items": memory.interactions_by_day(day)}
    return {"days": memory.history_days()}


@app.get("/api/search")
async def search(q: str = ""):
    """Busca por assunto no histórico local."""
    q = q.strip()
    if not q:
        return {"q": "", "items": []}
    return {"q": q, "items": memory_search(q)}


def memory_search(q: str):
    return orchestrator.memory.search_interactions(q)


@app.get("/api/storage")
async def storage_check():
    """A cada 120 dias, sinaliza que há registros antigos que podem ser arquivados."""
    memory = orchestrator.memory
    days = memory.days_since_cleanup_check()
    if days is None:
        memory.mark_cleanup_check()
        return {"due": False, "old_records": 0, "days_since": 0}
    old = memory.count_interactions_older_than()
    return {"due": days >= 120, "old_records": old, "days_since": int(days)}


@app.post("/api/storage/archive")
async def storage_archive():
    """Salva cópia dos registros antigos em JSON local e libera espaço no banco."""
    result = orchestrator.memory.archive_old_interactions()
    orchestrator.memory.mark_cleanup_check()
    return result


@app.post("/api/storage/postpone")
async def storage_postpone():
    """Adia o aviso por mais 120 dias."""
    orchestrator.memory.mark_cleanup_check()
    return {"due": False}


async def _log_and_send_debug(ws: WebSocket, started: float, response: dict):
    event = DEBUG.log(
        "response",
        duration_ms=int((time.time() - started) * 1000),
        intent=(response.get("meta") or {}).get("intent"),
        chars=len(response.get("text", "")),
    )
    if DEBUG.enabled:
        await ws.send_json({"type": "debug", "event": event})


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            raw = await ws.receive_text()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                payload = {"message": raw}

            # ---------- Comando de voz ----------
            if payload.get("type") == "voice":
                audio_b64 = payload.get("audio", "")
                if not audio_b64:
                    continue
                await ws.send_json({"type": "transcribing", "value": True})
                try:
                    audio = base64.b64decode(audio_b64)
                    text = await asyncio.to_thread(voice.transcribe, audio)
                except Exception as e:
                    DEBUG.log("error", where="voz", error=str(e))
                    await ws.send_json({"type": "transcribing", "value": False})
                    await ws.send_json({
                        "type": "message",
                        "text": f"⚠️ Não consegui ouvir: {e}",
                        "meta": {"intent": "voice_error"},
                    })
                    continue
                await ws.send_json({"type": "transcribing", "value": False})
                if not text:
                    await ws.send_json({
                        "type": "message",
                        "text": "🎙️ Não entendi o que você disse. Tente falar de novo.",
                        "meta": {"intent": "voice_error"},
                    })
                    continue
                await ws.send_json({"type": "transcript", "text": text})
                await ws.send_json({"type": "typing", "value": True})
                DEBUG.log("request", source="voz", message=text)
                started = time.time()
                try:
                    response = await asyncio.to_thread(orchestrator.handle, text)
                except Exception as e:
                    response = {"text": f"⚠️ Algo deu errado: {e}", "meta": {"intent": "error"}}
                    DEBUG.log("error", where="voz", error=str(e))
                await _log_and_send_debug(ws, started, response)
                await ws.send_json({"type": "typing", "value": False})
                await ws.send_json({"type": "message", **response})
                if payload.get("speak", True) and response.get("text"):
                    voice.speak(response["text"])
                continue

            # ---------- Mensagem de texto ----------
            user_message = payload.get("message", "").strip()
            if not user_message:
                continue

            await ws.send_json({"type": "typing", "value": True})
            DEBUG.log("request", source="texto", message=user_message)
            started = time.time()
            try:
                response = await asyncio.to_thread(orchestrator.handle, user_message)
            except Exception as e:
                response = {"text": f"⚠️ Algo deu errado: {e}", "meta": {"intent": "error"}}
                DEBUG.log("error", where="texto", error=str(e))
            await _log_and_send_debug(ws, started, response)
            await ws.send_json({"type": "typing", "value": False})
            await ws.send_json({"type": "message", **response})
    except WebSocketDisconnect:
        return


if __name__ == "__main__":
    import webview

    from core import tray

    if not orchestrator._ensure_ollama():
        sys.exit(1)
    # Atalho na Área de Trabalho + início junto com o Windows (1ª execução)
    create_desktop_shortcut()
    if not get_autostart():
        set_autostart(True)

    port = 8765
    url = f"http://127.0.0.1:{port}"

    # Servidor em segundo plano — a janela nativa é a interface principal
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    threading.Thread(target=server.run, daemon=True).start()
    deadline = time.time() + 30
    while not server.started and time.time() < deadline:
        time.sleep(0.2)
    if not server.started:
        sys.exit(1)

    holder = {"window": None}

    def _esconde():
        # Ao minimizar, a janela some da barra e continua só no ícone da bandeja
        try:
            holder["window"].hide()
        except Exception:
            pass

    def abrir():
        janela = holder["window"]
        if janela is not None:
            try:
                janela.show()
                return
            except Exception:
                holder["window"] = None
        webbrowser.open(url)

    def sair():
        server.should_exit = True
        tray.stop()
        os._exit(0)

    tray.start(on_open=abrir, on_quit=sair)

    janela = webview.create_window("Marcelly", url, width=1000, height=720, min_size=(420, 520))
    holder["window"] = janela
    try:
        janela.events.minimized += _esconde
    except AttributeError:
        pass

    webview.start()
    # Janela fechada (X): o servidor continua ativo e o ícone fica na bandeja
    while not server.should_exit:
        time.sleep(0.5)