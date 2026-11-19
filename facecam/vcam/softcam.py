"""SoftcamOutput: ctypes wrapper over softcam.dll (from an earlier prototype, ADR-009)."""

from __future__ import annotations

import ctypes
import os
from pathlib import Path

import cv2
import numpy as np

from facecam.paths import resource_dir
from facecam.platform.vcam_reg import is_registered

DEFAULT_DLL = resource_dir() / "native" / "softcam" / "bin" / "softcam-facecam.dll"
CLSID = "{B7E2A4C1-9D3F-4E6A-8B25-0C1D2E3F4A5B}"
NAME = "FaceCam Camera"     # name baked into the DLL at build time


def dll_path() -> Path:
    return Path(os.environ.get("FACECAM_SOFTCAM_DLL", DEFAULT_DLL))


def available() -> bool:
    return dll_path().exists() and is_registered(CLSID)


class SoftcamOutput:
    """send() takes RGB; softcam wants BGR."""

    device = NAME

    def __init__(self, path: Path | None = None) -> None:
        dll = ctypes.CDLL(str(path or dll_path()))
        dll.scCreateCamera.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_float]
        dll.scCreateCamera.restype = ctypes.c_void_p
        dll.scDeleteCamera.argtypes = [ctypes.c_void_p]
        dll.scSendFrame.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        dll.scIsConnected.argtypes = [ctypes.c_void_p]
        dll.scIsConnected.restype = ctypes.c_bool
        self._dll = dll
        self._cam = None
        self._size = (0, 0)

    def open(self, width: int, height: int, fps: int) -> None:
        if width % 4 or height % 4:
            raise ValueError("softcam needs width/height divisible by 4")
        cam = self._dll.scCreateCamera(width, height, 0.0)   # output thread owns the clock
        if not cam:
            raise RuntimeError("scCreateCamera failed (another sender running?)")
        self._cam, self._size = cam, (width, height)

    def send(self, rgb: np.ndarray) -> None:
        if self._cam is None:
            return
        height, width = rgb.shape[:2]
        if (width, height) != self._size:
            raise ValueError(f"frame {width}x{height} != camera {self._size}")
        bgr = np.ascontiguousarray(cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
        self._dll.scSendFrame(self._cam, bgr.ctypes.data)

    @property
    def connected(self) -> bool:
        return bool(self._cam) and bool(self._dll.scIsConnected(self._cam))

    def close(self) -> None:
        if self._cam is not None:
            self._dll.scDeleteCamera(self._cam)
            self._cam = None
