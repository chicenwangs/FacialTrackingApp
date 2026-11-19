"""API exposed to the Svelte UI as window.pywebview.api.*."""

from __future__ import annotations

import logging
from dataclasses import asdict, replace
from typing import Any

from facecam.core.engine import OUT_H, OUT_W, render_output
from facecam.paths import resource_dir
from facecam.settings import from_dict
from facecam.ui.preview import H, W, PreviewServer
from facecam.vcam import vcam_status
from facecam.vcam.softcam import NAME, SoftcamOutput, dll_path

log = logging.getLogger(__name__)


class Bridge:
    def __init__(self, app) -> None:
        self._app = app
        self._preview = PreviewServer(self._render)

    def _render(self, mode: str):
        frame = self._app.slot.get()
        if frame is None:
            return None
        if mode == "camera":
            import cv2

            image = frame.image.copy()
            box = self._app.vision.face_box
            if box is not None:
                cv2.rectangle(image, (int(box.x), int(box.y)),
                              (int(box.x + box.w), int(box.y + box.h)), (0, 255, 0), 2)
            return image
        return render_output(frame.image, self._app.vision.crop, W, H,
                             self._app.settings.brightness, self._app.settings.contrast)

    def state(self) -> dict[str, Any]:
        app = self._app
        out = app.out
        connected = isinstance(out, SoftcamOutput) and out.connected
        return {
            "state": "frozen" if app.freeze.is_set() else (
                "tracking" if app.capture.status == "ok" else "camera issue"),
            "frozen": app.freeze.is_set(),
            "fps": app.fps,
            "camera": app.capture.status,
            "vcam": {
                "status": vcam_status(),
                "live": isinstance(out, SoftcamOutput),
                "connected": bool(connected),
            },
            "zoom": app.settings.zoom,
            "brightness": app.settings.brightness,
            "contrast": app.settings.contrast,
        }

    # --- api (called from JS) ---
    def get_state(self) -> dict[str, Any]:
        return self.state() | {
            "preview": {
                "camera": self._preview.url("camera"),
                "output": self._preview.url("output"),
            },
            "settings": asdict(self._app.settings),
            "out_size": [OUT_W, OUT_H],
        }

    def get_settings(self) -> dict[str, Any]:
        return asdict(self._app.settings)

    def save_settings(self, data: dict[str, Any]) -> dict[str, Any]:
        try:
            merged = from_dict({**asdict(self._app.settings), **data}, self._app.settings)
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        try:
            settings = self._app.apply_settings(merged)
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
        return {"ok": True, "settings": asdict(settings)}

    def list_cameras(self) -> list[int]:
        import cv2

        found = []
        for index in range(5):
            if index == self._app.capture.index:
                found.append(index)
                continue
            cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
            if cap.isOpened():
                found.append(index)
            cap.release()
        return found

    def set_camera(self, index: int) -> dict[str, Any]:
        return self.save_settings({"camera": int(index)})

    def set_zoom(self, zoom: float) -> dict[str, Any]:
        return self.save_settings({"zoom": float(zoom)})

    def toggle_freeze(self) -> bool:
        return self._app.toggle_freeze()

    def _regsvr(self, unregister: bool) -> dict[str, Any]:
        import sys

        if sys.platform != "win32":
            return {"ok": False, "error": "Windows only"}
        dll = dll_path()
        if not dll.exists():
            return {"ok": False, "error": f"{dll} missing - see native/softcam/README.md"}
        from facecam.platform.win32 import run_elevated

        flag = "/u /s" if unregister else "/s"
        if not run_elevated("regsvr32", f'{flag} "{dll}"'):
            return {"ok": False, "error": "cancelled"}
        return {"ok": True, "restart": True}

    def register_vcam(self) -> dict[str, Any]:
        return self._regsvr(False)

    def unregister_vcam(self) -> dict[str, Any]:
        return self._regsvr(True)

    def finish_setup(self) -> dict[str, Any]:
        settings = replace(self._app.settings, first_run_done=True)
        self._app.apply_settings(settings)
        return {"ok": True}

    def quit(self) -> None:
        self._app.stop.set()

    def close(self) -> None:
        self._preview.close()
