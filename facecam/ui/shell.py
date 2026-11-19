"""Main window (pywebview) with a 10 Hz state push. Closing X quits the app."""

from __future__ import annotations

import json
import logging
import time

import webview

from facecam.paths import app_dir, resource_dir
from facecam.ui.bridge import Bridge

log = logging.getLogger(__name__)


def ui_index() -> str:
    return str(resource_dir() / "ui" / "build" / "index.html")


class Shell:
    def __init__(self, app) -> None:
        self.app = app
        self.bridge = Bridge(app)
        self.main = webview.create_window(
            "FaceCam",
            url=ui_index(),
            js_api=self.bridge,
            width=1280,
            height=800,
            min_size=(960, 640),
            background_color="#F1EED6",
        )
        self.main.events.closing += self._on_closing

    def _on_closing(self) -> bool:
        # The user asked for X to quit, not hide to a tray.
        self.app.stop.set()
        return True

    def _loop(self) -> None:
        last = time.perf_counter()
        while not self.app.stop.is_set():
            payload = json.dumps(self.bridge.state())
            try:
                self.main.evaluate_js(f"window.__sc && window.__sc.emit({payload})")
            except Exception as exc:
                log.debug("UI push failed: %s", exc)
            now = time.perf_counter()
            if now - last >= 1.0:
                self.app.fps = {
                    name: round(count / (now - last), 1)
                    for name, (count, _) in self.app.metrics.take().items()
                }
                last = now
            time.sleep(0.1)
        self.bridge.close()
        self.app.shutdown()
        self.main.destroy()

    def run(self) -> None:
        webview.start(
            self._loop,
            http_server=True,
            private_mode=False,
            storage_path=str(app_dir() / "webview"),
        )
