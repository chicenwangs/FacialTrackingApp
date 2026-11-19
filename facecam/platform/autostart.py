"""Opt-in 'start with Windows' via the per-user Run key (no admin needed)."""

from __future__ import annotations

import sys
from pathlib import Path

APP_NAME = "FaceCam"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def launch_command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --minimized'
    script = Path(__file__).resolve().parents[2] / "main.py"
    return f'"{sys.executable}" "{script}" --minimized'


def is_enabled() -> bool:
    if sys.platform != "win32":
        return False
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, APP_NAME)
            return True
    except OSError:
        return False


def set_enabled(enabled: bool) -> None:
    if sys.platform != "win32":
        return
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_WRITE) as key:
            if enabled:
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, launch_command())
            else:
                winreg.DeleteValue(key, APP_NAME)
    except OSError:
        pass
