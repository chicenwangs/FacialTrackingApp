"""Blind tracking test: a synthetic face moves through the corners.

No webcam or person needed. A fake landmark worker supplies noisy ground-truth
landmarks, but the two OpenCV trackers, fusion, EMA, Kalman and crop math are
the real code paths.
"""

import math
import time
import unittest
from unittest.mock import patch

import cv2
import numpy as np

from facecam.core.engine import render_output
from facecam.framing import Framer
from facecam.protocols import Frame
from facecam.vision import hybrid_face

WIDTH, HEIGHT, FACE_W = 1280, 720, 200
LANDMARK_NOISE = 5.0
POINTS = [
    (0.0, -0.4), (-1 / 5.2, -0.1), (1 / 5.2, -0.1),
    (0.0, 0.1), (0.0, 0.3), (0.0, 0.5),
]


def truth(frame_no):
    """Smooth path through centre, top-right corner and bottom-left corner."""
    stops = [0, 50, 100, 150, 200]
    centres = [(640, 360), (1100, 150), (180, 600), (640, 360), (640, 360)]
    for index in range(len(stops) - 1):
        if frame_no <= stops[index + 1]:
            start, end = stops[index], stops[index + 1]
            ratio = (frame_no - start) / (end - start)
            ratio = ratio * ratio * (3 - 2 * ratio)   # ease, no jumps
            x0, y0 = centres[index]
            x1, y1 = centres[index + 1]
            return (x0 + (x1 - x0) * ratio, y0 + (y1 - y0) * ratio, FACE_W)
    return centres[-1][0], centres[-1][1], FACE_W


def make_frame(cx, cy, width, frame_no):
    image = np.full((HEIGHT, WIDTH, 3), 235, np.uint8)
    # Static texture gives the trackers something to lock on to.
    for i in range(0, WIDTH, 120):
        cv2.rectangle(image, (i, 0), (i + 40, HEIGHT), (210, 210, 220), -1)
    cv2.ellipse(image, (int(cx), int(cy)), (int(width / 2), int(width / 2)),
                0, 0, 360, (170, 130, 110), -1)
    for offset in (-0.22, 0.22):
        cv2.ellipse(image, (int(cx + offset * width), int(cy - 0.12 * width)),
                    (12, 8), 0, 0, 360, (30, 30, 30), -1)
    return image


class FakeWorker:
    """Dated landmarks with noise, derived from the supplied ground truth."""

    def __init__(self, truth_fn=truth):
        self._truth = truth_fn
        self._result = None

    def request(self, image, frame_no):
        cx, cy, width = self._truth(frame_no)
        rng = np.random.default_rng(frame_no)
        points = [(cx + dx * width + rng.normal(0, LANDMARK_NOISE),
                   cy + dy * width + rng.normal(0, LANDMARK_NOISE)) for dx, dy in POINTS]
        self._result = (frame_no, points)

    def latest(self):
        return self._result

    def close(self):
        pass


class TrackingSimulation(unittest.TestCase):
    def test_two_box_tracking_through_corners(self):
        with patch.object(hybrid_face, "_LandmarkWorker", FakeWorker):
            tracker = hybrid_face.HybridFaceTracker()
            framer = Framer(WIDTH, HEIGHT)
            boxes = []
            errors = []
            jitter = []
            started = time.perf_counter()
            try:
                previous = None
                for frame_no in range(1, 201):
                    cx, cy, _ = truth(frame_no)
                    image = make_frame(cx, cy, FACE_W, frame_no)
                    box = tracker.detect(Frame(image, time.perf_counter_ns(), frame_no))
                    boxes.append(box)
                    if box is None:
                        continue
                    errors.append(math.hypot(box.box.x + box.box.w / 2 - cx,
                                             box.box.y + box.box.h / 2 - cy))
                    if previous is not None:
                        px, py, _ = truth(frame_no - 1)
                        expected_move = math.hypot(cx - px, cy - py)
                        actual_move = math.hypot(
                            (box.box.x + box.box.w / 2) - previous[0],
                            (box.box.y + box.box.h / 2) - previous[1])
                        jitter.append(abs(actual_move - expected_move))
                    previous = (box.box.x + box.box.w / 2, box.box.y + box.box.h / 2)

                    crop = framer.step(frame_no / 30, box.box)
                    self.assertGreaterEqual(crop.x, 0)
                    self.assertGreaterEqual(crop.y, 0)
                    self.assertLessEqual(crop.x + crop.w, WIDTH)
                    self.assertLessEqual(crop.y + crop.h, HEIGHT)
                    self.assertTrue(crop.x <= cx <= crop.x + crop.w)
                    self.assertTrue(crop.y <= cy <= crop.y + crop.h)
                    output = render_output(image, crop, 1280, 720)
                    self.assertEqual(output.shape, (720, 1280, 3))
            finally:
                tracker.close()

        elapsed = time.perf_counter() - started
        lost = sum(box is None for box in boxes)
        mean_error = sum(errors) / len(errors) if errors else 999
        mean_jitter = sum(jitter) / len(jitter) if jitter else 999
        print(f"\nSIM: {elapsed:.2f}s for 200 frames ({200 / elapsed:.1f} fps), "
              f"lost={lost}, mean error={mean_error:.1f}px, "
              f"mean jitter={mean_jitter:.2f}px/frame")

        self.assertLess(lost, 5, "face was lost for too many frames")
        self.assertLess(mean_error, 30, "tracking drifted too far")
        self.assertLess(mean_jitter, 5, "output was too jittery")
        self.assertLess(elapsed / 200, 0.025, "tracking is too slow for 40 fps")


    def test_still_face_produces_a_still_crop(self):
        still = lambda frame_no: (700, 350, FACE_W)
        with patch.object(hybrid_face, "_LandmarkWorker", lambda: FakeWorker(still)):
            tracker = hybrid_face.HybridFaceTracker()
            framer = Framer(WIDTH, HEIGHT)
            centres = []
            widths = []
            try:
                for frame_no in range(1, 121):
                    cx, cy = 700, 350
                    image = make_frame(cx, cy, FACE_W, frame_no)
                    box = tracker.detect(Frame(image, time.perf_counter_ns(), frame_no))
                    if box is None:
                        continue
                    crop = framer.step(frame_no / 30, box.box)
                    centres.append((crop.x + crop.w / 2, crop.y + crop.h / 2))
                    widths.append(crop.w)
            finally:
                tracker.close()

        steps = [math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(centres, centres[1:])]
        width_steps = [abs(b - a) for a, b in zip(widths, widths[1:])]
        mean_step = sum(steps) / len(steps)
        mean_width_step = sum(width_steps) / len(width_steps)
        print(f"\nSTILL: crop moves {mean_step:.2f}px/frame, "
              f"width changes {mean_width_step:.2f}px/frame")
        self.assertLess(mean_step, 1.0, "crop jitters while the face is still")
        self.assertLess(mean_width_step, 1.0, "zoom breathes while the face is still")


if __name__ == "__main__":
    unittest.main()
