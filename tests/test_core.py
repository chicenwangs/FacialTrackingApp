"""Checks for the logic that can silently break the picture or the pipeline."""

import tempfile
import threading
import time
import unittest
from pathlib import Path

import numpy as np

from facecam.capture import LatestFrame
from facecam.core.engine import VisionThread, render_output
from facecam.framing import (
    Framer, Kalman2DScale, clamp, crop_rect, rate_limit, slider_to_mult, zoom_for_face,
)
from facecam.metrics import Metrics
from facecam.protocols import FaceBox, Frame, Rect
from facecam.settings import Settings, load, save

AR = 16 / 9


def inside(rect, width, height):
    return (rect.x >= 0 and rect.y >= 0
            and rect.x + rect.w <= width and rect.y + rect.h <= height)


class CropTests(unittest.TestCase):
    def test_zoom_one_is_full_frame(self):
        self.assertEqual(crop_rect(640, 360, 1.0, 1280, 720, AR), Rect(0, 0, 1280, 720))

    def test_zoom_two_centred(self):
        self.assertEqual(crop_rect(640, 360, 2.0, 1280, 720, AR), Rect(320, 180, 640, 360))

    def test_crop_stays_inside_at_edges(self):
        for cx, cy in ((0, 0), (1280, 720), (-500, 360), (640, 9999)):
            rect = crop_rect(cx, cy, 2.0, 1280, 720, AR)
            self.assertTrue(inside(rect, 1280, 720))
            self.assertEqual((rect.w, rect.h), (640, 360))

    def test_four_three_input_keeps_output_aspect(self):
        rect = crop_rect(320, 240, 1.0, 640, 480, AR)
        self.assertAlmostEqual(rect.w / rect.h, AR, delta=0.01)
        self.assertTrue(inside(rect, 640, 480))

    def test_zoom_for_face_uses_face_width(self):
        self.assertAlmostEqual(zoom_for_face(0.28 * 640, 1280), 2.0)
        self.assertGreater(zoom_for_face(400, 1280, slider=2.0),
                           zoom_for_face(400, 1280, slider=1.0))
        self.assertEqual(zoom_for_face(5, 1280), 3.0)

    def test_slider_and_rate_limit(self):
        self.assertEqual(slider_to_mult(50), 0.5)
        self.assertEqual(slider_to_mult(250), 2.0)
        cx, cy, w = rate_limit((0, 0, 100), (1000, -1000, 500))
        self.assertAlmostEqual(w, 120)
        self.assertAlmostEqual(cx, 30)
        self.assertAlmostEqual(cy, -30)

    def test_framer_follows_then_holds_when_face_is_lost(self):
        framer = Framer(1280, 720)
        face = Rect(610, 300, 180, 180)
        t = 0.0
        for _ in range(90):
            t += 1 / 30
            crop = framer.step(t, face)
        self.assertAlmostEqual(crop.x + crop.w / 2, 700, delta=5)
        for _ in range(60):
            t += 1 / 30
            framer.step(t)
        held = framer.crop
        t += 1
        self.assertEqual(framer.step(t), held)

    def test_framer_with_no_face_ever_is_full_frame(self):
        self.assertEqual(Framer(1280, 720).step(0.0), Rect(0, 0, 1280, 720))


class KalmanTests(unittest.TestCase):
    def test_first_update_and_convergence(self):
        kf = Kalman2DScale()
        kf.update((100, 50, 80))
        self.assertEqual(kf.state, (100.0, 50.0, 80.0))
        rng = np.random.default_rng(0)
        for _ in range(200):
            kf.predict()
            noise = rng.normal(0, 5, 3)
            kf.update((640 + noise[0], 360 + noise[1], 200 + noise[2]))
        cx, cy, w = kf.state
        self.assertLess(abs(cx - 640), 5)
        self.assertLess(abs(cy - 360), 5)
        self.assertLess(abs(w - 200), 10)

    def test_dt_change_updates_transition(self):
        kf = Kalman2DScale(dt=1 / 30)
        kf.predict(dt=0.1)
        self.assertEqual(kf.F[0, 1], 0.1)


class SettingsTests(unittest.TestCase):
    def test_round_trip_and_bad_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "settings.json"
            save(path, Settings(brightness=73, first_run_done=True))
            loaded = load(path)
            self.assertEqual(loaded.brightness, 73)
            self.assertTrue(loaded.first_run_done)
            self.assertEqual(loaded.zoom, 1.0)

            path.write_text("{not json", encoding="utf-8")
            self.assertEqual(load(path).brightness, 50)
            self.assertTrue(path.with_suffix(".json.bad").exists())


class PipelineTests(unittest.TestCase):
    def test_latest_frame_keeps_newest(self):
        slot = LatestFrame()
        image = np.zeros((2, 2, 3), np.uint8)
        for seq in range(1, 4):
            slot.put(Frame(image, 0, seq))
        self.assertEqual(slot.get().seq, 3)
        self.assertIsNone(slot.wait_newer(3, timeout=0.01))
        self.assertEqual(slot.wait_newer(1, timeout=0.01).seq, 3)

    def test_render_output_crops_and_always_fills_output(self):
        src = np.full((720, 1280, 3), 100, np.uint8)
        image = render_output(src, Rect(320, 180, 640, 360), 1280, 720)
        self.assertEqual(image.shape, (720, 1280, 3))

    def test_yunet_worker_runs_without_a_face(self):
        from facecam.vision.yunet_face import YuNetWorker

        worker = YuNetWorker()
        try:
            worker.request(np.zeros((720, 1280, 3), np.uint8), 1)
            deadline = time.time() + 3
            while worker.latest() is None and time.time() < deadline:
                time.sleep(0.02)
            result = worker.latest()
            self.assertIsNotNone(result)
            self.assertIsNone(result[1])
        finally:
            worker.close()

    def test_hybrid_tracker_runs_without_a_face(self):
        from facecam.vision import HybridFaceTracker

        tracker = HybridFaceTracker()
        try:
            blank = np.zeros((720, 1280, 3), np.uint8)
            for seq in range(1, 4):
                self.assertIsNone(tracker.detect(Frame(blank, time.perf_counter_ns(), seq)))
        finally:
            tracker.close()

    def test_pause_stops_detection_then_resumes(self):
        class CountingFace:
            def __init__(self):
                self.calls = 0

            def detect(self, frame):
                self.calls += 1
                return FaceBox(Rect(600, 300, 180, 180), 0.9)

        stop, pause = threading.Event(), threading.Event()
        slot = LatestFrame()
        face = CountingFace()
        vision = VisionThread(slot, face, Metrics(), stop, None, pause)
        vision.start()
        try:
            image = np.zeros((720, 1280, 3), np.uint8)
            for seq in range(1, 31):
                slot.put(Frame(image, time.perf_counter_ns(), seq))
                time.sleep(1 / 30)
            pause.set()
            time.sleep(0.2)
            before = face.calls
            for seq in range(31, 51):
                slot.put(Frame(image, time.perf_counter_ns(), seq))
                time.sleep(1 / 30)
            self.assertLessEqual(face.calls - before, 1)   # one call may be in flight

            pause.clear()
            deadline = time.time() + 2
            for seq in range(51, 101):
                slot.put(Frame(image, time.perf_counter_ns(), seq))
                time.sleep(1 / 30)
                if face.calls > before:
                    break
            self.assertGreater(face.calls, before)
        finally:
            stop.set()
            pause.clear()
            vision.join(timeout=2)

    def test_freeze_holds_the_crop_then_resumes(self):
        class MovingFace:
            def __init__(self):
                self.box = Rect(600, 300, 180, 180)

            def detect(self, frame):
                return FaceBox(self.box, 0.9)

        stop, freeze = threading.Event(), threading.Event()
        slot = LatestFrame()
        face = MovingFace()
        vision = VisionThread(slot, face, Metrics(), stop, freeze)
        vision.start()
        try:
            image = np.zeros((720, 1280, 3), np.uint8)
            deadline = time.time() + 2
            for seq in range(1, 31):
                slot.put(Frame(image, time.perf_counter_ns(), seq))
                time.sleep(1 / 30)
            while vision.crop is None and time.time() < deadline:
                time.sleep(0.01)
            freeze.set()
            time.sleep(0.1)
            held = vision.crop
            self.assertIsNotNone(held)
            face.box = Rect(50, 50, 180, 180)
            for seq in range(31, 61):
                slot.put(Frame(image, time.perf_counter_ns(), seq))
                time.sleep(1 / 30)
            self.assertEqual(vision.crop, held)

            freeze.clear()
            deadline = time.time() + 3
            for seq in range(61, 121):
                slot.put(Frame(image, time.perf_counter_ns(), seq))
                time.sleep(1 / 30)
                if vision.crop != held:
                    break
            self.assertNotEqual(vision.crop, held)
        finally:
            stop.set()
            vision.join(timeout=2)

    def test_vision_publishes_crop(self):
        class FakeFace:
            def detect(self, frame):
                return FaceBox(Rect(600, 300, 180, 180), 0.9)

        stop = threading.Event()
        slot = LatestFrame()
        vision = VisionThread(slot, FakeFace(), Metrics(), stop)
        vision.start()
        try:
            image = np.zeros((720, 1280, 3), np.uint8)
            for seq in range(1, 11):
                slot.put(Frame(image, time.perf_counter_ns(), seq))
                time.sleep(1 / 30)
            deadline = time.time() + 2
            while vision.crop is None and time.time() < deadline:
                time.sleep(0.01)
            self.assertIsNotNone(vision.crop)
            self.assertLess(vision.crop.w, 1280)
        finally:
            stop.set()
            vision.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
