"""
Marcelly — Integração com o Windows.
Cria o atalho na Área de Trabalho e controla a inicialização
automática junto com o Windows (chave Run do usuário atual — HKCU,
sem afetar outras contas do computador).
"""
import os
import subprocess
import sys
from pathlib import Path

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "Marcelly"


def _app_script() -> str:
    return str(Path(__file__).parent.parent / "app.py")


def _pythonw() -> str:
    exe = Path(sys.executable)
    if exe.name.lower() == "python.exe":
        return str(exe.with_name("pythonw.exe"))
    return str(exe)


def _run_command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    return f'"{_pythonw()}" "{_app_script()}"'


def create_desktop_shortcut() -> bool:
    """Cria 'Marcelly.lnk' na Área de Trabalho (idempotente)."""
    if os.name != "nt":
        return False
    desktop = Path(os.path.expanduser("~")) / "Desktop"
    if not desktop.exists():  # OneDrive pode redirecionar a Área de Trabalho
        desktop = Path(os.path.expandvars(r"%USERPROFILE%\OneDrive\Desktop"))
    if not desktop.exists():
        return False
    lnk = desktop / "Marcelly.lnk"
    if lnk.exists():
        return True

    if getattr(sys, "frozen", False):
        target, args, workdir, icon = sys.executable, "", str(Path(sys.executable).parent), sys.executable
    else:
        target, args, workdir, icon = _pythonw(), f'"{_app_script()}"', str(Path(__file__).parent.parent), _pythonw()

    script = (
        '$s = (New-Object -ComObject WScript.Shell).CreateShortcut("' + str(lnk) + '");'
        '$s.TargetPath = "' + target + '";'
        '$s.Arguments = "' + args + '";'
        '$s.IconLocation = "' + icon + ',0";'
        '$s.WorkingDirectory = "' + workdir + '";'
        '$s.Description = "Marcelly - Assistente IA local";'
        '$s.Save()'
    )
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True, text=True, timeout=30,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return lnk.exists()
    except Exception:
        return False


def get_autostart() -> bool:
    if os.name != "nt":
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, VALUE_NAME)
            return True
    except FileNotFoundError:
        return False
    except Exception:
        return False


def set_autostart(enabled: bool) -> bool:
    if os.name != "nt":
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if enabled:
                winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, _run_command())
            else:
                try:
                    winreg.DeleteValue(key, VALUE_NAME)
                except FileNotFoundError:
                    pass
        return True
    except Exception:
        return False
