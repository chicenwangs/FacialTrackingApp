"""Loopback MJPEG preview: 127.0.0.1, random port and token, 30 fps 640x360."""

from __future__ import annotations

import secrets
import threading
import time
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import cv2
import numpy as np

W, H, FPS = 640, 360, 30
BOUNDARY = b"facecamframe"


class PreviewServer:
    """`render(mode)` returns an RGB frame or None; frames are made only on request."""

    def __init__(self, render: Callable[[str], np.ndarray | None]) -> None:
        self.render = render
        self.token = secrets.token_urlsafe(16)
        server = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args) -> None:
                pass

            def do_GET(self) -> None:
                url = urlparse(self.path)
                query = parse_qs(url.query)
                if url.path != "/preview" or query.get("token", [""])[0] != server.token:
                    self.send_error(403)
                    return
                mode = query.get("mode", ["output"])[0]
                self.send_response(200)
                self.send_header("Content-Type", f"multipart/x-mixed-replace; boundary={BOUNDARY.decode()}")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                try:
                    while True:
                        t0 = time.perf_counter()
                        rgb = server.render(mode)
                        if rgb is not None:
                            ok, jpg = cv2.imencode(
                                ".jpg", cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR),
                                [cv2.IMWRITE_JPEG_QUALITY, 75],
                            )
                            if ok:
                                self.wfile.write(b"--" + BOUNDARY + b"\r\nContent-Type: image/jpeg\r\n")
                                self.wfile.write(f"Content-Length: {len(jpg)}\r\n\r\n".encode())
                                self.wfile.write(jpg.tobytes() + b"\r\n")
                        time.sleep(max(0.0, 1 / FPS - (time.perf_counter() - t0)))
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                    return

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.httpd.daemon_threads = True
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, name="preview", daemon=True).start()

    def url(self, mode: str) -> str:
        return f"http://127.0.0.1:{self.port}/preview?token={self.token}&mode={mode}"

    def close(self) -> None:
        self.httpd.shutdown()
