"""Run this while sitting in front of the webcam to check tracking and RAM.

    python test_with_face.py

It prints once a second for 60 seconds. Sit still for the first 20 seconds,
then move to each corner of the frame. A good run shows a face box every tick,
a still crop while you sit still, and RSS around 130 MB.
"""

import ctypes
import math
import os
import time
from ctypes import wintypes


class _PMC(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]


_psapi = ctypes.WinDLL("psapi")
_kernel32 = ctypes.WinDLL("kernel32")
_psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(_PMC), wintypes.DWORD]
_kernel32.GetCurrentProcess.restype = wintypes.HANDLE


def rss_mb():
    counters = _PMC()
    counters.cb = ctypes.sizeof(counters)
    _psapi.GetProcessMemoryInfo(_kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb)
    return counters.WorkingSetSize / 1e6


def main():
    from facecam.core import App

    app = App()
    app.start()
    print("Sit in front of the camera. First 20s: still. Then: move to each corner.", flush=True)
    previous = None
    movements = []
    ticks = 0
    seconds = int(os.environ.get("FACECAM_TEST_SECONDS", "60"))
    try:
        while ticks < seconds and not app.stop.is_set():
            time.sleep(1.0)
            ticks += 1
            face = app.vision.face_box
            crop = app.vision.crop
            centre = None if crop is None else (crop.x + crop.w / 2, crop.y + crop.h / 2)
            if centre and previous:
                movements.append(math.dist(centre, previous))
            previous = centre
            face_text = "none" if face is None else (
                f"({face.x:.0f},{face.y:.0f}) {face.w:.0f}px")
            crop_text = "none" if crop is None else f"{crop.w:.0f}x{crop.h:.0f}"
            stages = ", ".join(f"{k}={v}" for k, v in app.fps.items())
            print(f"{ticks:2d}s face={face_text:24s} crop={crop_text:10s} "
                  f"out={app.out.device:22s} fps[{stages}] rss={rss_mb():.0f}MB", flush=True)
    finally:
        app.stop.set()
        app.shutdown()
        if movements:
            print(f"mean crop movement: {sum(movements)/len(movements):.2f} px/s "
                  f"(still section should be near zero)", flush=True)


if __name__ == "__main__":
    main()
