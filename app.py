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