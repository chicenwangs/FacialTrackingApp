"""Wires capture, vision and output together."""

from __future__ import annotations

import logging
import threading
from dataclasses import replace

from facecam.capture import CaptureThread, LatestFrame, find_camera, open_camera
from facecam.core.engine import OUT_FPS, OUT_H, OUT_W, OutputThread, VisionThread
from facecam.metrics import Metrics
from facecam.paths import app_dir
from facecam.settings import Settings, load, save
from facecam.vcam import make_output
from facecam.vision import HybridFaceTracker

log = logging.getLogger(__name__)


class App:
    def __init__(self, backend: str = "yunet") -> None:
        self.root = app_dir()
        self.settings_path = self.root / "settings.json"
        self.settings: Settings = load(self.settings_path)
        self._auto_pick_camera()

        self.stop = threading.Event()
        self.freeze = threading.Event()
        self.hotkey = None
        self.metrics = Metrics()
        self.fps: dict[str, float] = {}
        self.slot = LatestFrame()
        if backend == "facemesh":
            self.face = HybridFaceTracker()
        else:
            from facecam.vision.yunet_face import YuNetWorker

            self.face = HybridFaceTracker(worker_factory=YuNetWorker,
                                          detect_every=3, edge_every=2)
        self.vision = VisionThread(self.slot, self.face, self.metrics, self.stop, self.freeze)
        self.capture = CaptureThread(
            self.settings.camera, (self.settings.width, self.settings.height),
            self.slot, self.metrics, self.stop,
        )

        self.out, self.out_status = make_output()
        self.output = OutputThread(self.slot, self.vision, self, self.metrics, self.stop)

    def _auto_pick_camera(self) -> None:
        """Use the saved camera if it works, otherwise take the first that does."""
        cap = open_camera(self.settings.camera, self.settings.width, self.settings.height)
        ok = False
        if cap is not None:
            ok, _ = cap.read()
            cap.release()
        if ok:
            return
        found = find_camera(self.settings.width, self.settings.height)
        if found is not None:
            self.settings = replace(self.settings, camera=found)
            save(self.settings_path, self.settings)

    def start(self) -> None:
        for thread in (self.capture, self.vision, self.output):
            thread.start()
        try:
            from facecam.platform.hotkey import FreezeHotkey

            self.hotkey = FreezeHotkey(self.toggle_freeze)
            self.hotkey.start()
        except Exception as exc:
            log.warning("freeze hotkey unavailable: %s", exc)

    def toggle_freeze(self) -> bool:
        """Freeze or resume framing. Returns the new frozen state."""
        if self.freeze.is_set():
            self.freeze.clear()
        else:
            self.freeze.set()
        return self.freeze.is_set()

    def shutdown(self) -> None:
        self.stop.set()
        if self.hotkey is not None:
            self.hotkey.stop.set()
        for thread in (self.capture, self.vision, self.output):
            if thread.is_alive():
                thread.join(timeout=2)
        self.face.close()
        save(self.settings_path, self.settings)

    def apply_settings(self, settings: Settings) -> Settings:
        old = self.settings
        self.settings = settings
        if (settings.camera != old.camera
                or (settings.width, settings.height) != (old.width, old.height)):
            self.capture.reopen(settings.camera, (settings.width, settings.height))
        self.vision.cmds.put(f"zoom {settings.zoom}")
        if settings.autostart != old.autostart:
            from facecam.platform.autostart import set_enabled

            set_enabled(settings.autostart)
        save(self.settings_path, settings)
        return settings

    def tick(self) -> None:
        """Called once a second by the UI shell."""
        pass
