"""YuNet landmark provider: OpenCV-only, no MediaPipe/TFLite runtime in memory."""

from __future__ import annotations

import threading

import cv2
import numpy as np

from facecam.paths import resource_dir

MODEL = resource_dir() / "models" / "face_detection_yunet_2023mar.onnx"
DETECT_W = 320


class YuNetWorker:
    """Dated six-point landmarks derived from YuNet's face box.

    The synthetic points make the existing `landmark_box()` heuristic return
    the detector's centre and width, so the two-box fusion is unchanged.
    """

    def __init__(self) -> None:
        if not MODEL.exists():
            raise FileNotFoundError(MODEL)
        self._detector = cv2.FaceDetectorYN.create(str(MODEL), "", (DETECT_W, DETECT_W),
                                                   0.6, 0.3, 5000)
        self._lock = threading.Lock()
        self._request = threading.Event()
        self._stop = threading.Event()
        self._frame = None
        self._frame_no = -1
        self._result = None
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def request(self, image, frame_no: int) -> None:
        with self._lock:
            self._frame = image
            self._frame_no = frame_no
        self._request.set()

    def latest(self):
        with self._lock:
            return self._result

    def close(self) -> None:
        self._stop.set()
        self._request.set()
        self._thread.join(timeout=1.0)

    def _run(self) -> None:
        while not self._stop.is_set():
            self._request.wait(0.2)
            if self._stop.is_set():
                return
            self._request.clear()
            with self._lock:
                image, frame_no = self._frame, self._frame_no
            if image is None:
                continue

            height, width = image.shape[:2]
            scale = min(1.0, DETECT_W / float(width))
            small = cv2.resize(image, (max(1, int(width * scale)), max(1, int(height * scale))))
            try:
                self._detector.setInputSize((small.shape[1], small.shape[0]))
                _, faces = self._detector.detect(cv2.cvtColor(small, cv2.COLOR_RGB2BGR))
            except Exception:
                faces = None

            points = None
            if faces is not None and len(faces) and float(faces[0][14]) >= 0.6:
                x, y, face_w, face_h = (float(v) for v in faces[0][:4])
                cx, cy = (x + face_w / 2) / scale, (y + face_h / 2) / scale
                face_w = max(20.0, face_w / scale)
                points = [
                    (cx, cy - 0.4 * face_w),
                    (cx - face_w / 5.2, cy - 0.1 * face_w),
                    (cx + face_w / 5.2, cy - 0.1 * face_w),
                    (cx, cy + 0.1 * face_w),
                    (cx, cy + 0.3 * face_w),
                    (cx, cy + 0.5 * face_w),
                ]
            with self._lock:
                self._result = (frame_no, points)
