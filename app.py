"""
Marcelly — Servidor local.
Sobe a interface de chat e conecta ao orquestrador via WebSocket.
Tudo roda em 127.0.0.1 — nada sai da máquina.
"""
import asyncio
import json
import sys
import threading
import webbrowser
from pathlib import Path

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from core.orchestrator import MarcellyOrchestrator

BASE_DIR = Path(__file__).parent
UI_DIR = BASE_DIR / "ui"

app = FastAPI(title="Marcelly", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=str(UI_DIR)), name="static")

orchestrator = MarcellyOrchestrator()


@app.get("/")
async def index():
    return FileResponse(UI_DIR / "index.html")


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
    port = 8765
    print("🔒 Marcelly rodando em http://127.0.0.1:8765")
    threading.Timer(1.5, lambda: webbrowser.open("http://127.0.0.1:8765")).start()
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
