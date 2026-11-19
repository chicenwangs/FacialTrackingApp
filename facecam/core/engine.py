"""Vision and output threads. Vision writes crop; output only reads it."""

from __future__ import annotations

import logging
import queue
import threading
import time

import cv2
import numpy as np

from facecam.capture import LatestFrame
from facecam.framing import Framer, clamp
from facecam.metrics import Metrics
from facecam.protocols import Rect
from facecam.vcam import placeholder

log = logging.getLogger(__name__)

OUT_W, OUT_H, OUT_FPS = 1280, 720, 30
STALE_NS = 1_000_000_000          # frame older than 1s -> placeholder


def render_output(src: np.ndarray, crop: Rect | None, width: int, height: int,
                  brightness: int = 50, contrast: int = 50) -> np.ndarray:
    """Crop, adjust levels, resize. Used by output thread, preview and tests."""
    if crop is not None and crop.x + crop.w <= src.shape[1] and crop.y + crop.h <= src.shape[0]:
        src = src[int(crop.y):int(crop.y + crop.h), int(crop.x):int(crop.x + crop.w)]
    alpha = contrast / 50.0
    beta = (brightness / 50.0 - 1.0) * 128
    if alpha != 1.0 or beta != 0.0:
        src = cv2.convertScaleAbs(src, alpha=alpha, beta=beta)
    return cv2.resize(src, (width, height), interpolation=cv2.INTER_LINEAR)


class VisionThread(threading.Thread):
    """Track the face every frame; Kalman and crop math do the smoothing."""

    def __init__(self, slot: LatestFrame, face, metrics: Metrics,
                 stop: threading.Event, freeze: threading.Event | None = None,
                 pause: threading.Event | None = None) -> None:
        super().__init__(name="vision", daemon=True)
        self.slot, self.face, self.metrics, self.stop = slot, face, metrics, stop
        self.freeze = freeze if freeze is not None else threading.Event()
        self.pause = pause if pause is not None else threading.Event()
        self.cmds: queue.Queue[str] = queue.Queue()
        self.framer: Framer | None = None
        self.crop: Rect | None = None
        self.face_box: Rect | None = None
        self.zoom = 1.0

    def handle(self, command: str) -> None:
        name, _, arg = command.strip().partition(" ")
        if name == "zoom":
            try:
                self.zoom = clamp(float(arg), 0.5, 2.0)
            except ValueError:
                log.warning("zoom needs a number 0.5..2.0")
        elif name in ("zoom+", "zoom-"):
            self.zoom = clamp(self.zoom + (0.1 if name == "zoom+" else -0.1), 0.5, 2.0)
        elif name:
            log.warning("unknown command %r", name)

    def run(self) -> None:
        seq = 0
        was_frozen = False
        was_paused = False
        while not self.stop.is_set():
            if self.pause.is_set():
                was_paused = True
                self.pause.wait(0.1)      # no detection, no CPU work while dormant
                continue
            if was_paused:
                was_paused = False
                if self.framer is not None:
                    self.framer.reset_tracking()   # re-acquire cleanly on resume
            frame = self.slot.wait_newer(seq, timeout=0.5)
            if frame is None:
                continue
            seq = frame.seq
            while True:
                try:
                    self.handle(self.cmds.get_nowait())
                except queue.Empty:
                    break

            height, width = frame.image.shape[:2]
            if self.framer is None or (self.framer.in_w, self.framer.in_h) != (width, height):
                self.framer = Framer(width, height, OUT_W / OUT_H)
            self.framer.set_zoom(self.zoom)

            t0 = time.perf_counter_ns()
            if self.freeze.is_set():
                if not was_frozen:
                    self.framer.reset_tracking()
                was_frozen = True
                self.crop = self.framer.crop      # hold exactly where it was
            else:
                was_frozen = False
                found = self.face.detect(frame)  # tracker runs every frame
                self.face_box = found.box if found else None
                self.framer.step(frame.t_ns / 1e9, self.face_box)
                self.crop = self.framer.crop
            self.metrics.add("vision", (time.perf_counter_ns() - t0) / 1e6)


class OutputThread(threading.Thread):
    """Fixed-rate output clock. Never waits on vision; uses the newest crop."""

    def __init__(self, slot: LatestFrame, vision: VisionThread, app,
                 metrics: Metrics, stop: threading.Event) -> None:
        super().__init__(name="output", daemon=True)
        self.slot, self.vision, self.app = slot, vision, app
        self.metrics, self.stop = metrics, stop

    def run(self) -> None:
        app = self.app
        app.out.open(OUT_W, OUT_H, OUT_FPS)
        period = 1 / OUT_FPS
        dormant_frame = placeholder(OUT_W, OUT_H,
                                    "FaceCam paused - Ctrl+Alt+P to resume")
        was_paused = False
        next_t = time.perf_counter()
        try:
            while not self.stop.is_set():
                if app.pause.is_set():
                    if not was_paused:
                        was_paused = True
                        next_t = time.perf_counter()
                    app.out.send(dormant_frame)   # keep the camera alive at 1 fps
                    next_t += 1.0
                    delay = next_t - time.perf_counter()
                    if delay > 0:
                        time.sleep(delay)
                    else:
                        next_t = time.perf_counter()
                    continue
                if was_paused:
                    was_paused = False
                    next_t = time.perf_counter()

                t0 = time.perf_counter_ns()
                frame = self.slot.get()
                if frame is None or t0 - frame.t_ns > STALE_NS:
                    image = placeholder(OUT_W, OUT_H, "FaceCam: camera not ready")
                else:
                    image = render_output(frame.image, self.vision.crop, OUT_W, OUT_H,
                                          app.settings.brightness, app.settings.contrast)
                app.out.send(image)
                self.metrics.add("output", (time.perf_counter_ns() - t0) / 1e6)

                next_t += period
                delay = next_t - time.perf_counter()
                if delay > 0:
                    time.sleep(delay)
                elif delay < -period:
                    next_t = time.perf_counter()
        finally:
            app.out.close()
