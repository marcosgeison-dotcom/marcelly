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
import webbrowser
from pathlib import Path

import uvicorn
from fastapi import Body, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

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
                        "text": "U0001f399 Não entendi o que você disse. Tente falar de novo.",
                        "meta": {"intent": "voice_error"},
                    })
                    continue
                await ws.send_json({"type": "transcript", "text": text})
                await ws.send_json({"type": "typing", "value": True})
                try:
                    response = await asyncio.to_thread(orchestrator.handle, text)
                except Exception as e:
                    response = {"text": f"⚠️ Algo deu errado: {e}", "meta": {"intent": "error"}}
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
            try:
                response = await asyncio.to_thread(orchestrator.handle, user_message)
            except Exception as e:
                response = {"text": f"⚠️ Algo deu errado: {e}", "meta": {"intent": "error"}}
            await ws.send_json({"type": "typing", "value": False})
            await ws.send_json({"type": "message", **response})
    except WebSocketDisconnect:
        return


if __name__ == "__main__":
    if not orchestrator._ensure_ollama():
        sys.exit(1)
    # Atalho na Área de Trabalho + início junto com o Windows (1ª execução)
    create_desktop_shortcut()
    if not get_autostart():
        set_autostart(True)
    port = 8765
    print("U0001f512 Marcelly rodando em http://127.0.0.1:8765")
    threading.Timer(1.5, lambda: webbrowser.open("http://127.0.0.1:8765")).start()
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
