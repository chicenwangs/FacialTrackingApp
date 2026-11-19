"""Windows helpers that need no extra dependency."""

from __future__ import annotations

import ctypes


def run_elevated(exe: str, params: str) -> bool:
    """Show a UAC prompt and launch exe. True if it was launched."""
    shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    shell32.ShellExecuteW.restype = ctypes.c_void_p
    result = shell32.ShellExecuteW(None, "runas", exe, params, None, 0)
    return int(result or 0) > 32
