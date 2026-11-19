"""Global Ctrl+Alt+F hotkey for freezing the framing (Windows only)."""

from __future__ import annotations

import ctypes
import threading
from ctypes import wintypes

MOD_CONTROL, MOD_ALT = 0x0002, 0x0001
VK_F, WM_HOTKEY = 0x46, 0x0312
PM_REMOVE = 0x0001


class FreezeHotkey(threading.Thread):
    def __init__(self, callback) -> None:
        super().__init__(name="hotkey", daemon=True)
        self.callback = callback
        self.stop = threading.Event()

    def run(self) -> None:
        if not self._register():
            return
        try:
            user32 = ctypes.windll.user32
            message = wintypes.MSG()
            while not self.stop.is_set():
                if user32.PeekMessageW(ctypes.byref(message), None, 0, 0, PM_REMOVE):
                    if message.message == WM_HOTKEY:
                        self.callback()
                    user32.TranslateMessage(ctypes.byref(message))
                    user32.DispatchMessageW(ctypes.byref(message))
                else:
                    self.stop.wait(0.05)
        finally:
            ctypes.windll.user32.UnregisterHotKey(None, 1)

    def _register(self) -> bool:
        try:
            return bool(ctypes.windll.user32.RegisterHotKey(
                None, 1, MOD_CONTROL | MOD_ALT, VK_F))
        except Exception:
            return False
