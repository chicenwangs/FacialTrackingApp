"""v1-style two-box face tracking, made cheap enough to run in real time.

Landmarks from a FaceMesh worker are fused with a tight box and an enlarged
box (0.6 / 0.3 / 0.1), keeping the original app's two-box idea. Both boxes use
MOSSE: KCF allocated ~126MB of FFT buffers on first update. FaceMesh runs off
the video thread on a 640px copy, and a deadband keeps a still face still.
"""

from __future__ import annotations

import math
import threading

import cv2
import numpy as np

from facecam.protocols import FaceBox, Frame, Rect

DETECT_EVERY = 1
DETECT_EDGE_EVERY = 1
DETECT_WIDTH = 640
TRACK_W_MAIN = 640
TRACK_W_BIG = 480
LANDMARK_INDICES = (1, 33, 263, 61, 291, 152)  # forehead, eye corners, mouth, chin
W_LANDMARK, W_MAIN, W_BIG = 0.6, 0.3, 0.1
STILL_DEADBAND = 20.0        # noise below this barely moves the crop
WIDTH_DEADBAND = 18.0        # stops the zoom "breathing" on a still face
WIDTH_FOLLOW_ALPHA = 0.12
EDGE_FRACTION = 0.12


def landmark_box(points):
    """Centre and face width from the six landmarks (v1 heuristic)."""
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    eye_width = math.dist(points[1], points[2])
    return float(np.median(xs)), float(np.median(ys)), max(20.0, eye_width * 2.6)


def enlarge_box(box, factor=1.25, frame_w=None, frame_h=None):
    x, y, width, height = box
    cx, cy = x + width / 2.0, y + height / 2.0
    new_w, new_h = width * factor, height * factor
    nx, ny = cx - new_w / 2.0, cy - new_h / 2.0
    if frame_w and frame_h:
        nx = max(0, min(nx, frame_w - new_w))
        ny = max(0, min(ny, frame_h - new_h))
    return nx, ny, new_w, new_h


def _box_center(box):
    x, y, width, height = box
    return x + width / 2.0, y + height / 2.0, width


def _tracker_frame(image, target_width):
    """Reduced copy for a cheap tracker; returns (image, scale)."""
    height, width = image.shape[:2]
    scale = min(1.0, target_width / float(width))
    if scale == 1.0:
        return image, scale
    small = cv2.resize(image, (max(1, int(width * scale)), max(1, int(height * scale))),
                       interpolation=cv2.INTER_AREA)
    return small, scale


class _LandmarkWorker:
    """Runs FaceMesh off the video thread; keeps the newest dated result."""

    def __init__(self) -> None:
        import mediapipe as mp

        self._mesh = mp.solutions.face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=False,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self._lock = threading.Lock()
        self._request = threading.Event()
        self._stop = threading.Event()
        self._frame = None
        self._frame_no = -1
        self._result = None
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def request(self, image, frame_no: int) -> None:
        # Frames from the capture slot are never mutated, so a reference is safe.
        # Copying a full 720p frame here was ~2.7MB of churn per detection.
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
        close = getattr(self._mesh, "close", None)
        if close:
            close()

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
            scale = min(1.0, DETECT_WIDTH / float(width))
            small = cv2.resize(image, (max(1, int(width * scale)), max(1, int(height * scale))))
            try:
                found = self._mesh.process(np.ascontiguousarray(small))
            except Exception:
                found = None

            points = None
            if found and found.multi_face_landmarks:
                landmarks = found.multi_face_landmarks[0].landmark
                points = [
                    (landmarks[i].x * small.shape[1] / scale,
                     landmarks[i].y * small.shape[0] / scale)
                    for i in LANDMARK_INDICES
                ]
            with self._lock:
                self._result = (frame_no, points)


def _make_main_tracker():
    # KCF grows working set by ~125MB over 100 updates here; MOSSE costs ~3MB.
    # Two MOSSE boxes (tight + enlarged) keep the v1 fusion without that cost.
    for create in (lambda: cv2.legacy.TrackerMOSSE_create(),
                   lambda: cv2.TrackerMOSSE_create()):
        try:
            return create()
        except Exception:
            continue
    return None


def _make_big_tracker():
    for create in (lambda: cv2.legacy.TrackerMOSSE_create(),
                   lambda: cv2.TrackerMOSSE_create()):
        try:
            return create()
        except Exception:
            continue
    return None


class HybridFaceTracker:
    """Fuses fresh landmarks with two OpenCV trackers; returns a face box."""

    def __init__(self, worker_factory=None, detect_every=None, edge_every=None) -> None:
        self.detect_every = detect_every or DETECT_EVERY
        self.edge_every = edge_every or DETECT_EDGE_EVERY
        self._worker = (worker_factory or _LandmarkWorker)()
        self._main = None
        self._big = None
        self._frame_no = 0
        self._last_center = None
        self._ema = None
        self._anchor = None
        self.debug_points = None

    def close(self) -> None:
        self._worker.close()

    def _near_edge(self, width: int, height: int) -> bool:
        if self._last_center is None:
            return False
        cx, cy = self._last_center
        margin_x, margin_y = EDGE_FRACTION * width, EDGE_FRACTION * height
        return (cx < margin_x or cx > width - margin_x
                or cy < margin_y or cy > height - margin_y)

    def detect(self, frame: Frame) -> FaceBox | None:
        self._frame_no += 1
        image = frame.image
        height, width = image.shape[:2]

        interval = self.edge_every if self._near_edge(width, height) else self.detect_every
        if self._frame_no % interval == 0 or self._main is None:
            self._worker.request(image, self._frame_no)

        result = self._worker.latest()
        fresh = bool(result and result[1]
                     and 0 <= self._frame_no - result[0] <= interval + 2)

        main_image, main_scale = _tracker_frame(image, TRACK_W_MAIN)
        big_image, big_scale = _tracker_frame(image, TRACK_W_BIG)

        landmark = None
        box_main = box_big = None
        if fresh:
            landmark = landmark_box(result[1])
            self.debug_points = result[1]
            box_main = self._init_tracker(_make_main_tracker, main_image,
                                          landmark, main_scale, width, height, 1.0)
            box_big = self._init_tracker(_make_big_tracker, big_image,
                                         landmark, big_scale, width, height, 1.25)
        else:
            self.debug_points = None
            box_main = self._update_tracker(self._main, main_image, main_scale, width, height)
            box_big = self._update_tracker(self._big, big_image, big_scale, width, height)

        measurements = []
        if landmark:
            measurements.append((landmark, W_LANDMARK))
        if box_main:
            measurements.append((_box_center(box_main), W_MAIN))
        if box_big:
            measurements.append((_box_center(box_big), W_BIG))
        if not measurements:
            return None

        total = sum(weight for _, weight in measurements)
        cx, cy, face_w = (
            sum(value[index] * weight for value, weight in measurements) / total
            for index in range(3)
        )

        if self._ema is None:
            self._ema = (cx, cy, face_w)
            self._anchor = (cx, cy, face_w)
        else:
            ex, ey, ew = self._ema
            # Small gaps are treated as noise and barely move the crop; real
            # movement raises the gain so the follow is continuous, not stepwise.
            gap = math.hypot(cx - ex, cy - ey)
            alpha = min(0.6, max(0.05, (gap - STILL_DEADBAND) / 40.0))
            ex += alpha * (cx - ex)
            ey += alpha * (cy - ey)
            if abs(face_w - self._anchor[2]) > WIDTH_DEADBAND:
                ew += WIDTH_FOLLOW_ALPHA * (face_w - ew)
                self._anchor = (self._anchor[0], self._anchor[1], face_w)
            self._ema = (ex, ey, ew)
        cx, cy, face_w = self._ema
        self._last_center = (cx, cy)

        face_w = max(20.0, min(face_w, width))
        x = min(max(0.0, cx - face_w / 2.0), max(0.0, width - face_w))
        y = min(max(0.0, cy - face_w / 2.0), max(0.0, height - face_w))
        return FaceBox(Rect(x, y, face_w, face_w), 1.0)

    def _init_tracker(self, maker, image, landmark, scale, frame_w, frame_h, grow):
        # Re-use the tracker object; init() resets it in place. Allocating a new
        # KCF/MOSSE tracker several times a second caused memory churn.
        tracker = self._main if grow == 1.0 else self._big
        if tracker is None:
            tracker = maker()
        if tracker is None:
            return None
        cx, cy, face_w = landmark
        face_w *= grow
        box = (max(0.0, (cx - face_w / 2.0) * scale),
               max(0.0, (cy - face_w / 2.0) * scale),
               max(2.0, face_w * scale), max(2.0, face_w * scale))
        try:
            tracker.init(image, box)
        except Exception:
            return None
        if grow == 1.0:
            self._main = tracker
        else:
            self._big = tracker
        full = (box[0] / scale, box[1] / scale, box[2] / scale, box[3] / scale)
        return self._valid(full, frame_w, frame_h)

    def _update_tracker(self, tracker, image, scale, frame_w, frame_h):
        if tracker is None:
            return None
        try:
            ok, box = tracker.update(image)
        except Exception:
            return None
        if not ok:
            return None
        full = (box[0] / scale, box[1] / scale, box[2] / scale, box[3] / scale)
        return self._valid(full, frame_w, frame_h)

    @staticmethod
    def _valid(box, frame_w, frame_h):
        x, y, width, height = box
        if not all(math.isfinite(v) for v in box):
            return None
        if width < 8 or height < 8 or width > frame_w or height > frame_h:
            return None
        if x + width < 0 or y + height < 0 or x > frame_w or y > frame_h:
            return None
        return box
