"""Registry read to see whether our DirectShow filter is registered."""

from __future__ import annotations

import sys


def is_registered(clsid: str) -> bool:
    if sys.platform != "win32":
        return False
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, rf"CLSID\{clsid}\InprocServer32"):
            return True
    except OSError:
        return False
