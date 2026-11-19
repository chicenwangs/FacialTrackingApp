"""Capture thread with a one-slot 'newest frame wins' buffer and camera retry."""

from __future__ import annotations

import logging
import threading
import time

import cv2

from facecam.metrics import Metrics
from facecam.protocols import Frame

log = logging.getLogger(__name__)
RETRY_S = 2.0


class LatestFrame:
    """put() replaces the slot; readers never block the writer for long."""

    def __init__(self) -> None:
        self._cond = threading.Condition()
        self._frame: Frame | None = None

    def put(self, frame: Frame) -> None:
        with self._cond:
            self._frame = frame
            self._cond.notify_all()

    def get(self) -> Frame | None:
        with self._cond:
            return self._frame

    def wait_newer(self, seq: int, timeout: float) -> Frame | None:
        with self._cond:
            self._cond.wait_for(lambda: self._frame is not None and self._frame.seq > seq, timeout)
            frame = self._frame
            return frame if frame is not None and frame.seq > seq else None


def find_camera(width: int = 1280, height: int = 720, limit: int = 5) -> int | None:
    """First camera index that opens and delivers a frame. No user choice needed."""
    for index in range(limit):
        cap = open_camera(index, width, height)
        if cap is None:
            continue
        ok, _ = cap.read()
        cap.release()
        if ok:
            log.info("auto-selected camera %d", index)
            return index
    return None


def open_camera(index: int, width: int = 1280, height: int = 720, fps: int = 30):
    """MSMF first (fast), DSHOW fallback. MJPG keeps 720p30 cheap."""
    for api in (cv2.CAP_MSMF, cv2.CAP_DSHOW):
        cap = cv2.VideoCapture(index, api)
        if not cap.isOpened():
            cap.release()
            continue
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        cap.set(cv2.CAP_PROP_FPS, fps)
        ok, _ = cap.read()
        if ok:
            log.info("camera %d via %s: %dx%d", index, cap.getBackendName(),
                     int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                     int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
            return cap
        cap.release()
    return None


class CaptureThread(threading.Thread):
    def __init__(self, index: int, size: tuple[int, int], slot: LatestFrame,
                 metrics: Metrics, stop: threading.Event) -> None:
        super().__init__(name="capture", daemon=True)
        self.index, self.size, self.slot = index, size, slot
        self.metrics, self.stop = metrics, stop
        self._reopen = threading.Event()
        self.status = "opening"

    def reopen(self, index: int | None = None, size: tuple[int, int] | None = None) -> None:
        if index is not None:
            self.index = index
        if size is not None:
            self.size = size
        self._reopen.set()

    def run(self) -> None:
        seq = 0
        while not self.stop.is_set():
            self._reopen.clear()
            cap = open_camera(self.index, *self.size)
            if cap is None:
                self.status = f"camera {self.index} busy or missing, retrying"
                log.warning("camera %d busy/missing, retry in %.0fs", self.index, RETRY_S)
                self.stop.wait(RETRY_S)
                continue
            self.status = "ok"
            try:
                while not self.stop.is_set() and not self._reopen.is_set():
                    if not cap.grab():
                        log.warning("camera read failed, reopening")
                        break
                    t0 = time.perf_counter_ns()
                    ok, bgr = cap.retrieve()
                    if not ok:
                        continue
                    self.slot.put(Frame(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB), t0, seq))
                    seq += 1
                    self.metrics.add("capture", (time.perf_counter_ns() - t0) / 1e6)
            finally:
                cap.release()
