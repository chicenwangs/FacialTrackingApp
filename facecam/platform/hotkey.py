"""Global hotkeys: Ctrl+Alt+F freezes framing, Ctrl+Alt+P toggles low-power pause."""

from __future__ import annotations

import ctypes
import threading
from ctypes import wintypes

MOD_CONTROL, MOD_ALT = 0x0002, 0x0001
VK_F, VK_P = 0x46, 0x50
WM_HOTKEY = 0x0312
PM_REMOVE = 0x0001


class GlobalHotkeys(threading.Thread):
    def __init__(self, freeze_callback, pause_callback) -> None:
        super().__init__(name="hotkey", daemon=True)
        self.callbacks = {1: freeze_callback, 2: pause_callback}
        self.stop = threading.Event()

    def run(self) -> None:
        user32 = ctypes.windll.user32
        mods = MOD_CONTROL | MOD_ALT
        registered = [
            hotkey_id for hotkey_id, vk in ((1, VK_F), (2, VK_P))
            if self._register(user32, hotkey_id, mods, vk)
        ]
        if not registered:
            return
        try:
            message = wintypes.MSG()
            while not self.stop.is_set():
                if user32.PeekMessageW(ctypes.byref(message), None, 0, 0, PM_REMOVE):
                    if message.message == WM_HOTKEY:
                        callback = self.callbacks.get(message.wParam)
                        if callback:
                            callback()
                    user32.TranslateMessage(ctypes.byref(message))
                    user32.DispatchMessageW(ctypes.byref(message))
                else:
                    self.stop.wait(0.05)
        finally:
            for hotkey_id in registered:
                user32.UnregisterHotKey(None, hotkey_id)

    @staticmethod
    def _register(user32, hotkey_id: int, mods: int, vk: int) -> bool:
        try:
            return bool(user32.RegisterHotKey(None, hotkey_id, mods, vk))
        except Exception:
            return False
