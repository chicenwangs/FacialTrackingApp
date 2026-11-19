"""Our own virtual camera only: no OBS, no output picker."""

from __future__ import annotations

import time

import cv2
import numpy as np

from facecam.platform.vcam_reg import is_registered
from facecam.vcam.softcam import CLSID, NAME, SoftcamOutput, dll_path

__all__ = ["NullOutput", "SoftcamOutput", "make_output", "placeholder", "vcam_status"]


class NullOutput:
    """Keeps the app running until McG Cam is registered; shows a clear status."""

    device = "None (McG Cam not ready)"

    def open(self, width, height, fps) -> None:
        self.fps = fps

    def send(self, rgb) -> None:
        pass

    def sleep_until_next_frame(self) -> None:
        time.sleep(1.0 / max(1.0, getattr(self, "fps", 30)))

    def close(self) -> None:
        pass


def vcam_status() -> str:
    if not dll_path().exists():
        return "not installed"
    return "registered" if is_registered(CLSID) else "not registered"


def make_output():
    """Return (output, status). The only output is our own DirectShow camera."""
    status = vcam_status()
    if status == "registered":
        return SoftcamOutput(), status
    return NullOutput(), status


def placeholder(width: int, height: int, text: str) -> np.ndarray:
    image = np.full((height, width, 3), 24, np.uint8)
    cv2.putText(image, text, (40, height // 2), cv2.FONT_HERSHEY_SIMPLEX,
                1.2, (230, 230, 230), 2)
    return image
