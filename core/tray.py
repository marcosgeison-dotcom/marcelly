"""
Marcelly — Ícone na bandeja do sistema.
Mantém o Marcelly ativo na área de notificação com as opções
Abrir (reabre a janela do chat) e Sair (encerra de verdade).
A imagem é o mesmo favicon do site (ui/icon.png).
"""
import threading
from pathlib import Path

import pystray
from PIL import Image

ICON_PATH = Path(__file__).parent.parent / "ui" / "icon.png"

_icon = None


def start(on_open, on_quit):
    global _icon
    if _icon is not None:
        return
    image = Image.open(ICON_PATH)
    menu = pystray.Menu(
        pystray.MenuItem("Abrir Marcelly", lambda *_: on_open(), default=True),
        pystray.MenuItem("Sair", lambda *_: on_quit()),
    )
    _icon = pystray.Icon("Marcelly", image, "Marcelly — Assistente IA local", menu)
    threading.Thread(target=_icon.run, daemon=True).start()


def stop():
    global _icon
    if _icon is not None:
        _icon.stop()
        _icon = None
