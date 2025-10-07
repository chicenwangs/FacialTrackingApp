# facecam_mediapipe.py
# MediaPipe hybrid facecam with two trackers, Kalman smoothing, preview overlays,
# zoom slider functionality, and a toggle to fall back to the old Haar tracker ([O]OldTracker).
# Requires: opencv-python, numpy, pyvirtualcam, mediapipe
# Run in the venv you installed mediapipe into (your venv310).

import cv2
import numpy as np
import pyvirtualcam
import time
import json
import os
import math
import threading

import mediapipe as mp

# ===== Settings =====
TRACK_FACE = True
ZOOM_MIN = 1.0
ZOOM_MAX = 3.0

CONFIG_FILE = "facecam_config.json"

# UI / slider defaults
BRIGHTNESS_DEFAULT = 50
CONTRAST_DEFAULT = 50
ZOOM_DEFAULT = 100  # 50..200 -> 0.5..2.0 multiplier
SLIDER_HEIGHT = 20
SLIDER_PADDING = 10

# Candidate 16:9 input resolutions high->low
RESOLUTIONS_16_9 = [
    (1920, 1080),
    (1600, 900),
    (1280, 720),
    (800, 600),
    (640, 360)
]

# Virtual camera resolution (fixed)
VCAM_WIDTH = 1280
VCAM_HEIGHT = 720
VCAM_ASPECT = VCAM_WIDTH / VCAM_HEIGHT

# Detection / threading parameters
DETECTION_INTERVAL_FRAMES = 6
DETECT_DOWNSCALE_W = 640

# Kalman parameters
KALMAN_PROCESS_NOISE_POS = 1.0
KALMAN_PROCESS_NOISE_SCALE = 1.0
KALMAN_MEAS_NOISE_POS = 50.0
KALMAN_MEAS_NOISE_SCALE = 200.0

# Benchmark parameters
TARGET_FPS = 15.0
BENCH_SECONDS = 0.8

# ===== State & UI variables =====
show_overlay = True
slider_values = [BRIGHTNESS_DEFAULT, CONTRAST_DEFAULT, ZOOM_DEFAULT]
slider_names = ["Brightness", "Contrast", "Zoom"]
slider_ranges = [(0, 100), (0, 100), (50, 200)]

# UI geometry
SLIDER_COUNT = len(slider_names)
slider_width = (VCAM_WIDTH - SLIDER_PADDING * 4) // SLIDER_COUNT
slider_y = VCAM_HEIGHT - SLIDER_HEIGHT - SLIDER_PADDING

res_box = (10, 10, 220, 36)
controls_box = (res_box[0] + res_box[2] + 12, 10, 560, 36)  # widened a bit to fit extra label
fps_text_y = slider_y - 36
dropdown_item_height = 30
dropdown_x, dropdown_y = res_box[0], res_box[1] + res_box[3] + 6

# ===== Haar fallback (old tracker) =====
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
use_old_tracker = False  # toggled by [O]OldTracker

# ===== Helpers: config & benchmark =====
def save_config(chosen_index):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump({"best_res_index": chosen_index}, f)
    except Exception:
        pass

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                cfg = json.load(f)
            idx = cfg.get("best_res_index")
            if isinstance(idx, int) and 0 <= idx < len(RESOLUTIONS_16_9):
                return idx
        except Exception:
            pass
    return None

def open_camera(res):
    c = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    c.set(cv2.CAP_PROP_FRAME_WIDTH, int(res[0]))
    c.set(cv2.CAP_PROP_FRAME_HEIGHT, int(res[1]))
    return c

def measure_fps_for_res(res, base_frame, seconds=BENCH_SECONDS, results_so_far=None):
    """
    Measure FPS for a given resolution while showing a transparent overlay
    on the existing preview frame with ongoing results.
    - base_frame: current frame to overlay the benchmarking text on
    - results_so_far: dict {resolution: fps} of results already measured
    Returns measured FPS.
    """
    c = open_camera(res)
    if not c.isOpened():
        return 0.0

    t0 = time.time()
    frames = 0
    fps = 0.0
    results = {} if results_so_far is None else dict(results_so_far)

    while time.time() - t0 < seconds:
        ret, frame = c.read()
        if not ret:
            time.sleep(0.005)
            continue

        frames += 1
        elapsed = max(1e-6, time.time() - t0)
        fps = frames / elapsed
        results[res] = fps

        # draw overlay on the passed frame
        display = base_frame.copy()
        h, w = display.shape[:2]
        box_w, box_h = 480, 220
        box_x, box_y = (w - box_w)//2, (h - box_h)//2

        overlay = display.copy()
        alpha = 0.42
        cv2.rectangle(overlay, (box_x, box_y), (box_x + box_w, box_y + box_h), (0, 0, 0), -1)
        display = cv2.addWeighted(overlay, alpha, display, 1 - alpha, 0)

        # write title
        cv2.putText(display, "Testing resolution with best performance:",
                    (box_x + 10, box_y + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 1)

        # write each resolution and its FPS
        line_y = box_y + 60
        for (rw, rh) in RESOLUTIONS_16_9:
            fps_val = results.get((rw, rh), 0.0)
            cv2.putText(display, f"  {rw}x{rh}: {fps_val:.1f} FPS",
                        (box_x + 15, line_y), cv2.FONT_HERSHEY_SIMPLEX, 0.60, (255, 255, 255), 1)
            line_y += 30

        cv2.imshow("FaceCam Preview", display)
        cv2.waitKey(1)

    c.release()
    return fps

def select_best_resolution_with_stats_impl(current_frame):
    fps_list = []
    for (w,h) in RESOLUTIONS_16_9:
        avg = measure_fps_for_res((w,h), current_frame, seconds=BENCH_SECONDS)
        fps_list.append(avg)
        print(f"  {w}x{h}: {avg:.1f} FPS")  # optional console log

    arr = np.array(fps_list)
    q1 = np.percentile(arr, 25)
    q3 = np.percentile(arr, 75)
    iqr = q3 - q1
    lower_thresh = max(TARGET_FPS, q1 - 1.5 * iqr)
    candidates = [i for i, val in enumerate(fps_list) if val >= lower_thresh]
    if candidates:
        best_idx = max(candidates)
        save_config(best_idx)
        return best_idx
    scores = []
    for idx, val in enumerate(fps_list):
        w,h = RESOLUTIONS_16_9[idx]
        area = w*h
        scores.append(val * math.log(area+1))
    best_idx = int(np.argmax(scores))
    save_config(best_idx)
    return best_idx

# ===== Kalman & tracker helpers =====
import numpy as np

class SimpleKalman2DScale:
    def __init__(self, dt=1/30.0, process_noise_pos=1.0, process_noise_scale=1.0,
                 meas_noise_pos=50.0, meas_noise_scale=200.0):
        self.dt = dt
        self.x = np.zeros((6,1))  # [cx, vx, cy, vy, w, vw]
        F = np.eye(6)
        F[0,1] = dt
        F[2,3] = dt
        F[4,5] = dt
        self.F = F
        H = np.zeros((3,6))
        H[0,0] = 1.0
        H[1,2] = 1.0
        H[2,4] = 1.0
        self.H = H
        q = process_noise_pos
        qs = process_noise_scale
        Q = np.diag([q, q*0.1, q, q*0.1, qs, qs*0.1])
        self.Q = Q
        R = np.diag([meas_noise_pos, meas_noise_pos, meas_noise_scale])
        self.R = R
        self.P = np.eye(6) * 1000.0
        self.inited = False

    def predict(self, dt=None):
        if dt is not None and abs(dt - self.dt) > 1e-6:
            self.dt = dt
            self.F[0,1] = dt
            self.F[2,3] = dt
            self.F[4,5] = dt
        self.x = self.F @ self.x
        self.P = self.F @ self.P @ self.F.T + self.Q
        return self.x.copy()

    def update(self, z):
        z = np.array(z, dtype=float).reshape((3,1))
        if not self.inited:
            self.x[0,0] = z[0,0]
            self.x[2,0] = z[1,0]
            self.x[4,0] = z[2,0]
            self.x[1,0] = 0.0
            self.x[3,0] = 0.0
            self.x[5,0] = 0.0
            self.inited = True
            return self.x
        S = self.H @ self.P @ self.H.T + self.R
        K = self.P @ self.H.T @ np.linalg.inv(S)
        y = z - (self.H @ self.x)
        self.x = self.x + K @ y
        I = np.eye(6)
        self.P = (I - K @ self.H) @ self.P
        return self.x

def make_tracker(preferred='KCF'):
    try:
        if preferred == 'KCF':
            return cv2.TrackerKCF_create()
    except Exception:
        pass
    try:
        if preferred == 'KCF':
            return cv2.legacy.TrackerKCF_create()
    except Exception:
        pass
    try:
        return cv2.TrackerMOSSE_create()
    except Exception:
        try:
            return cv2.legacy.TrackerMOSSE_create()
        except Exception:
            return None

def enlarge_box(box, factor=1.25, frame_w=None, frame_h=None):
    x,y,w,h = box
    cx = x + w/2.0
    cy = y + h/2.0
    nw = w * factor
    nh = h * factor
    nx = int(cx - nw/2.0)
    ny = int(cy - nh/2.0)
    if frame_w and frame_h:
        nx = max(0, min(nx, frame_w-1))
        ny = max(0, min(ny, frame_h-1))
    return (nx, ny, int(nw), int(nh))

# ===== MediaPipe initialization & detection thread =====
mp_face_mesh = mp.solutions.face_mesh.FaceMesh(
    max_num_faces=1,
    refine_landmarks=False,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)

detection_lock = threading.Lock()
detection_frame = None
latest_landmarks = None
detection_request = threading.Event()

def detection_worker():
    global latest_landmarks, detection_frame
    while True:
        detection_request.wait()
        detection_request.clear()
        with detection_lock:
            frame_copy = None if detection_frame is None else detection_frame.copy()
        if frame_copy is None:
            continue
        h0, w0 = frame_copy.shape[:2]
        scale = min(1.0, DETECT_DOWNSCALE_W / float(w0))
        small = cv2.resize(frame_copy, (int(w0*scale), int(h0*scale)))
        rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
        res = mp_face_mesh.process(rgb)
        if res and res.multi_face_landmarks:
            lm = res.multi_face_landmarks[0]
            indices = [1, 33, 263, 61, 291, 152]
            pts = []
            for idx in indices:
                l = lm.landmark[idx]
                x_small = l.x * small.shape[1]
                y_small = l.y * small.shape[0]
                x_full = x_small / scale
                y_full = y_small / scale
                pts.append((x_full, y_full))
            with detection_lock:
                latest_landmarks = pts
        else:
            with detection_lock:
                latest_landmarks = None

_detection_thread = threading.Thread(target=detection_worker, daemon=True)
_detection_thread.start()

# ===== Run benchmark / init camera =====
res_index = None
saved_idx = load_config()
if saved_idx is not None:
    tmp = open_camera(RESOLUTIONS_16_9[saved_idx])
    ok = tmp.isOpened()
    tmp.release()
    if ok:
        res_index = saved_idx

if res_index is None:
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        raise RuntimeError("Cannot open webcam")
    input_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    input_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cam_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    print(f"Camera default: {input_width}x{input_height} @ {cam_fps:.1f} FPS")
else:
    input_width, input_height = RESOLUTIONS_16_9[res_index]
    cap = open_camera((input_width, input_height))
    if not cap.isOpened():
        raise RuntimeError("Cannot open webcam at saved resolution")
    aw = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    ah = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cam_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    input_width, input_height = aw, ah
    print(f"Camera opened: {input_width}x{input_height} @ {cam_fps:.1f} FPS")

slider_width = (VCAM_WIDTH - SLIDER_PADDING * 4) // SLIDER_COUNT

cv2.namedWindow("FaceCam Preview", cv2.WINDOW_NORMAL)

# ===== Tracker & Kalman state =====
tracker_main = None
tracker_big = None
tracker_ok_main = False
tracker_ok_big = False

kf = None
prev_cx = None
prev_cy = None
prev_w = None

frame_counter = 0
active_slider = None
dropdown_open = False

# mouse callback & helpers
def update_slider_value(index, mouse_x):
    global slider_values
    x_start = SLIDER_PADDING + index * (slider_width + SLIDER_PADDING)
    vmin, vmax = slider_ranges[index]
    rel = (mouse_x - x_start) / slider_width
    new_val = int(vmin + rel * (vmax - vmin))
    new_val = max(min(new_val, vmax), vmin)
    slider_values[index] = new_val

def mouse_callback(event, x, y, flags, param):
    global active_slider, dropdown_open, res_index, input_width, input_height, cap, show_overlay, use_old_tracker
    if event == cv2.EVENT_LBUTTONDOWN:
        if show_overlay:
            for i in range(len(slider_names)):
                x_start = SLIDER_PADDING + i * (slider_width + SLIDER_PADDING)
                x_end = x_start + slider_width
                if slider_y <= y <= slider_y + SLIDER_HEIGHT and x_start <= x <= x_end:
                    active_slider = i
                    update_slider_value(i, x)
                    return
            rx, ry, rw, rh = res_box
            if rx <= x <= rx + rw and ry <= y <= ry + rh:
                dropdown_open = not dropdown_open
                return
            if dropdown_open:
                for idx_item, (rw_val, rh_val) in enumerate(RESOLUTIONS_16_9):
                    item_x = dropdown_x
                    item_y = dropdown_y + idx_item * dropdown_item_height
                    if item_x <= x <= item_x + rw and item_y <= y <= item_y + dropdown_item_height:
                        res_index = idx_item
                        input_width, input_height = RESOLUTIONS_16_9[res_index]
                        try:
                            cap.release()
                            cap = open_camera((input_width, input_height))
                            aw = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                            ah = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                            input_width, input_height = aw, ah
                            print("Switched resolution to", input_width, input_height)
                        except Exception as ex:
                            print("Failed switching resolution:", ex)
                        dropdown_open = False
                        return

            hx, hy, hw, hh = controls_box
            if hx <= x <= hx + hw and hy <= y <= hy + hh:
                pad = 12
                cx = hx + pad
                cy = hy + hh // 2 + 6
                # New ordering: [S] [D] [O]OldTracker [Q]Quit
                s_txt = "[S] Settings"
                d_txt = "[D]Benchmark"
                o_txt = "[O]OldTracker"
                q_txt = "[Q]Quit"
                s_size = cv2.getTextSize(s_txt, cv2.FONT_HERSHEY_SIMPLEX, 0.58, 1)[0]
                d_size = cv2.getTextSize(d_txt, cv2.FONT_HERSHEY_SIMPLEX, 0.58, 1)[0]
                o_size = cv2.getTextSize(o_txt, cv2.FONT_HERSHEY_SIMPLEX, 0.58, 1)[0]
                q_size = cv2.getTextSize(q_txt, cv2.FONT_HERSHEY_SIMPLEX, 0.58, 1)[0]
                s_pos = (cx, cy)
                d_pos = (cx + s_size[0] + 28, cy)
                o_pos = (d_pos[0] + d_size[0] + 28, cy)
                q_pos = (o_pos[0] + o_size[0] + 28, cy)
                def point_in_text(px, py, pos, text_sz):
                    tx, ty = pos
                    tw, th = text_sz
                    left = tx
                    right = tx + tw
                    top = ty - th
                    bottom = ty
                    return left <= px <= right and top <= py <= bottom
                if point_in_text(x, y, s_pos, s_size):
                    show_overlay = not show_overlay
                    return
                if point_in_text(x, y, d_pos, d_size):
                    new_idx = select_best_resolution_with_stats_impl()
                    res_index = new_idx
                    input_width, input_height = RESOLUTIONS_16_9[res_index]
                    try:
                        cap.release()
                        cap = open_camera((input_width, input_height))
                        aw = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                        ah = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                        input_width, input_height = aw, ah
                        print("Benchmark switched resolution to", input_width, input_height)
                    except Exception as ex:
                        print("Failed switching resolution after benchmark:", ex)
                    return
                if point_in_text(x, y, o_pos, o_size):
                    use_old_tracker = not use_old_tracker
                    return
                if point_in_text(x, y, q_pos, q_size):
                    return
        else:
            hx, hy, hw, hh = controls_box
            if hx <= x <= hx + hw and hy <= y <= hy + hh:
                show_overlay = not show_overlay
                return

    elif event == cv2.EVENT_MOUSEMOVE:
        if active_slider is not None:
            update_slider_value(active_slider, x)
    elif event == cv2.EVENT_LBUTTONUP:
        active_slider = None

cv2.setMouseCallback("FaceCam Preview", mouse_callback)

# ===== Main Loop =====
res_index = res_index  # keep scope
with pyvirtualcam.Camera(
    width=VCAM_WIDTH,
    height=VCAM_HEIGHT,
    fps=(cap.get(cv2.CAP_PROP_FPS) or 30.0),
    backend='obs',
    device='OBS Virtual Camera'
) as cam:
    print(f"Virtual camera started: {cam.device}")
    center_x, center_y = input_width // 2, input_height // 2

    last_time = time.time()
    display_fps = 0.0

    while True:

        ret, frame = cap.read()
        if not ret or frame is None:
            time.sleep(0.01)
            continue

        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        frame_counter += 1

        # If user requested old tracker mode, run Haar detection every frame (simple fallback)
        if use_old_tracker:
            faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5)
            if len(faces) > 0:
                x, y, w, h = faces[0]
                # center and zoom based on detected face size
                center_x = x + w // 2
                center_y = y + h // 2

                # user zoom multiplier from slider (50..200 -> 0.5..2.0)
                user_zoom_mult = slider_values[2] / 100.0

                # TARGET: fraction of input width that face should occupy (default 0.32 = 32%)
                DEFAULT_FACE_FRACTION = 0.75
                # desired_face_width = fraction_of_frame * input_width / user_zoom_mult
                desired_face_width = max(20.0, DEFAULT_FACE_FRACTION * input_width / user_zoom_mult)

                zoom_scale = max(ZOOM_MIN, min(ZOOM_MAX, (input_width / desired_face_width)))

                # expose this rect for drawing on preview (so the green tracker box appears)
                tracker_rect_main = (int(x), int(y), int(w), int(h))
                tracker_rect_big = None
                landmark_to_draw = None
            else:
                # fallback: keep the previous center & zoom; no rect to draw
                zoom_scale = 1.0
                tracker_rect_main = None
                tracker_rect_big = None
                landmark_to_draw = None
        else:
            # ===== Hybrid mediapipe + trackers pipeline =====
            need_detection = (frame_counter % DETECTION_INTERVAL_FRAMES == 0) or (tracker_main is None) or (not tracker_ok_main) or (not tracker_ok_big)
            if need_detection:
                with detection_lock:
                    detection_frame = frame.copy()
                detection_request.set()

            # update trackers
            if tracker_main is not None:
                try:
                    tracker_ok_main, box_main = tracker_main.update(frame)
                except Exception:
                    tracker_ok_main = False
                    box_main = None
            else:
                tracker_ok_main = False
                box_main = None

            if tracker_big is not None:
                try:
                    tracker_ok_big, box_big = tracker_big.update(frame)
                except Exception:
                    tracker_ok_big = False
                    box_big = None
            else:
                tracker_ok_big = False
                box_big = None

            # read landmarks
            with detection_lock:
                lm_pts_local = None if latest_landmarks is None else list(latest_landmarks)

            landmark_box = None
            if lm_pts_local:
                xs = [p[0] for p in lm_pts_local]
                ys = [p[1] for p in lm_pts_local]
                land_cx = float(np.median(xs))
                land_cy = float(np.median(ys))
                try:
                    eye_w = float(np.linalg.norm(np.array(lm_pts_local[1]) - np.array(lm_pts_local[2])))
                    land_w = max(20.0, eye_w * 2.6)
                except Exception:
                    land_w = float(max(input_width*0.2, input_width/6.0))
                landmark_box = (land_cx, land_cy, land_w)
                # keep landmarks for drawing (in input coords)
                landmark_to_draw = lm_pts_local
            else:
                landmark_to_draw = None

            # init trackers when landmarks are available
            if landmark_box is not None and (tracker_main is None or (frame_counter % DETECTION_INTERVAL_FRAMES == 0)):
                lc, lyc, lw = landmark_box
                lh = lw
                lx = int(lc - lw/2.0)
                ly = int(lyc - lh/2.0)
                det_box_for_tracker = (max(0, lx), max(0, ly), int(lw), int(lh))
                t_main = make_tracker('KCF')
                if t_main is not None:
                    try:
                        t_main.init(frame, det_box_for_tracker)
                        tracker_main = t_main
                        tracker_ok_main = True
                    except Exception:
                        tracker_main = None
                        tracker_ok_main = False
                big_box_for_tracker = enlarge_box(det_box_for_tracker, factor=1.25, frame_w=input_width, frame_h=input_height)
                t_big = make_tracker('MOSSE')
                if t_big is not None:
                    try:
                        t_big.init(frame, big_box_for_tracker)
                        tracker_big = t_big
                        tracker_ok_big = True
                    except Exception:
                        tracker_big = None
                        tracker_ok_big = False

            # convert trackers to cx,cy,w
            track_cx = track_cy = track_w = None
            big_cx = big_cy = big_w = None
            tracker_rect_main = None
            tracker_rect_big = None
            if tracker_ok_main and box_main is not None:
                bx,by,bw,bh = box_main
                track_cx = bx + bw/2.0
                track_cy = by + bh/2.0
                track_w = bw
                tracker_rect_main = box_main
            if tracker_ok_big and box_big is not None:
                bx,by,bw,bh = box_big
                big_cx = bx + bw/2.0
                big_cy = by + bh/2.0
                big_w = bw
                tracker_rect_big = box_big

            # fuse
            w_land = 0.6 if landmark_box is not None else 0.0
            w_track = 0.3 if track_w is not None else 0.0
            w_big = 0.1 if big_w is not None else 0.0
            den = w_land + w_track + w_big

            if den < 1e-6:
                fused_cx = input_width / 2.0
                fused_cy = input_height / 2.0
                fused_w = min(input_width, input_height) * 0.6
            else:
                fused_cx = ((w_land * (landmark_box[0] if landmark_box else 0.0)) +
                            (w_track * (track_cx if track_cx is not None else 0.0)) +
                            (w_big  * (big_cx if big_cx is not None else 0.0))) / den
                fused_cy = ((w_land * (landmark_box[1] if landmark_box else 0.0)) +
                            (w_track * (track_cy if track_cy is not None else 0.0)) +
                            (w_big  * (big_cy if big_cy is not None else 0.0))) / den
                fused_w = ((w_land * (landmark_box[2] if landmark_box else 0.0)) +
                           (w_track * (track_w if track_w is not None else 0.0)) +
                           (w_big  * (big_w if big_w is not None else 0.0))) / den

            # init kalman
            if kf is None:
                camera_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
                kf = SimpleKalman2DScale(dt=1.0 / max(1.0, camera_fps),
                                         process_noise_pos=KALMAN_PROCESS_NOISE_POS,
                                         process_noise_scale=KALMAN_PROCESS_NOISE_SCALE,
                                         meas_noise_pos=KALMAN_MEAS_NOISE_POS,
                                         meas_noise_scale=KALMAN_MEAS_NOISE_SCALE)
                prev_cx, prev_cy, prev_w = fused_cx, fused_cy, fused_w

            dt = 1.0 / max(1.0, (cap.get(cv2.CAP_PROP_FPS) or 30.0))
            kf.predict(dt=dt)
            kf.update([fused_cx, fused_cy, fused_w])
            state = kf.x
            pred_cx = float(state[0,0])
            pred_cy = float(state[2,0])
            pred_w  = float(state[4,0])

            # rate limit
            if prev_w is None:
                prev_w = pred_w
            if prev_cx is None:
                prev_cx = pred_cx
            if prev_cy is None:
                prev_cy = pred_cy

            max_scale_change = 0.20
            scale_ratio = pred_w / (prev_w + 1e-9)
            if scale_ratio > 1 + max_scale_change:
                pred_w = prev_w * (1 + max_scale_change)
            elif scale_ratio < 1 - max_scale_change:
                pred_w = prev_w * (1 - max_scale_change)

            max_center_move = 0.25 * pred_w
            dx = pred_cx - prev_cx
            dy = pred_cy - prev_cy
            if abs(dx) > max_center_move:
                pred_cx = prev_cx + math.copysign(max_center_move, dx)
            if abs(dy) > max_center_move:
                pred_cy = prev_cy + math.copysign(max_center_move, dy)

            prev_cx, prev_cy, prev_w = pred_cx, pred_cy, pred_w

            center_x = pred_cx
            center_y = pred_cy

            # apply user zoom slider (slider_values[2] is 50..200 -> 0.5..2.0)
            user_zoom_mult = slider_values[2] / 100.0

            # Use a target fraction of the FRAME width (how much of the frame the face should fill).
            # Smaller fraction => more zoomed out. Default 0.32 means face ~32% of input width.
            DEFAULT_FACE_FRACTION = 0.75

            # Compute desired face width in input pixels: desired fraction of frame divided by user multiplier
            desired_face_width = max(20.0, DEFAULT_FACE_FRACTION * input_width / user_zoom_mult)

            zoom_scale = max(ZOOM_MIN, min(ZOOM_MAX, (input_width / desired_face_width)))

        # Apply brightness/contrast
        brightness = slider_values[0] / 50.0
        contrast = slider_values[1] / 50.0
        frame_rgb = cv2.convertScaleAbs(frame_rgb, alpha=contrast, beta=(brightness - 1.0) * 128)

        # Compute crop preserving aspect
        desired_crop_w = int((input_width / zoom_scale))
        desired_crop_h = int(desired_crop_w / VCAM_ASPECT)
        if desired_crop_h > input_height:
            desired_crop_h = input_height
            desired_crop_w = int(desired_crop_h * VCAM_ASPECT)
        desired_crop_w = max(2, int(desired_crop_w))
        desired_crop_h = max(2, int(desired_crop_h))

        half_w = desired_crop_w // 2
        half_h = desired_crop_h // 2

        x1 = int(center_x) - half_w
        y1 = int(center_y) - half_h
        x2 = x1 + desired_crop_w
        y2 = y1 + desired_crop_h

        if x1 < 0:
            x2 -= x1
            x1 = 0
        if x2 > input_width:
            diff = x2 - input_width
            x1 -= diff
            x2 -= diff
            if x1 < 0:
                x1 = 0
        if y1 < 0:
            y2 -= y1
            y1 = 0
        if y2 > input_height:
            diff = y2 - input_height
            y1 -= diff
            y2 -= diff
            if y1 < 0:
                y1 = 0

        x1 = max(0, x1); y1 = max(0, y1)
        x2 = min(input_width, x2); y2 = min(input_height, y2)

        cropped = frame_rgb[y1:y2, x1:x2]

        ch, cw = cropped.shape[:2]
        if (cw != desired_crop_w) or (ch != desired_crop_h):
            canvas = np.zeros((desired_crop_h, desired_crop_w, 3), dtype=cropped.dtype)
            paste_x = max(0, (desired_crop_w - cw)//2)
            paste_y = max(0, (desired_crop_h - ch)//2)
            canvas[paste_y:paste_y+ch, paste_x:paste_x+cw] = cropped
            cropped = canvas

        frame_out = cv2.resize(cropped, (VCAM_WIDTH, VCAM_HEIGHT), interpolation=cv2.INTER_LINEAR)

        # FPS smoothing
        now = time.time()
        fps_sample = 1.0 / max(1e-6, now - last_time)
        last_time = now
        display_fps = (display_fps * 0.9) + (fps_sample * 0.1)

        if show_overlay:
            overlay = frame_out.copy()
            sx, sy, sw, sh = res_box
            cx, cy, cw_box, ch_box = controls_box

            # main panels (shadow + panel)
            cv2.rectangle(overlay, (sx + 2, sy + 2), (sx + sw + 2, sy + sh + 2), (0, 0, 0), -1)
            cv2.rectangle(overlay, (sx, sy), (sx + sw, sy + sh), (0, 0, 0), -1)

            cv2.rectangle(overlay, (cx + 2, cy + 2), (cx + cw_box + 2, cy + ch_box + 2), (0, 0, 0), -1)
            cv2.rectangle(overlay, (cx, cy), (cx + cw_box, cy + ch_box), (0, 0, 0), -1)

            # fps box
            cv2.rectangle(overlay, (10, fps_text_y - 22), (220, fps_text_y + 8), (0, 0, 0), -1)

            alpha = 0.42
            frame_out = cv2.addWeighted(overlay, alpha, frame_out, 1 - alpha, 0)

            # resolution text
            cv2.putText(frame_out, f"{input_width}x{input_height}", (sx + 8, sy + 24),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.68, (255, 255, 255), 2)

            # controls: [S] [D] [O]OldTracker [Q]
            pad = 12
            cx_text = cx + pad
            cy_text = cy + ch_box // 2 + 6
            s_txt = "[S] Settings"
            d_txt = "[D]Benchmark"
            o_txt = "[O]OldTracker"
            q_txt = "[Q]Quit"
            s_size = cv2.getTextSize(s_txt, cv2.FONT_HERSHEY_SIMPLEX, 0.58, 1)[0]
            d_size = cv2.getTextSize(d_txt, cv2.FONT_HERSHEY_SIMPLEX, 0.58, 1)[0]
            o_size = cv2.getTextSize(o_txt, cv2.FONT_HERSHEY_SIMPLEX, 0.58, 1)[0]
            q_size = cv2.getTextSize(q_txt, cv2.FONT_HERSHEY_SIMPLEX, 0.58, 1)[0]
            s_pos = (cx_text, cy_text)
            d_pos = (cx_text + s_size[0] + 28, cy_text)
            o_pos = (d_pos[0] + d_size[0] + 28, cy_text)
            q_pos = (o_pos[0] + o_size[0] + 28, cy_text)

            cv2.putText(frame_out, s_txt, s_pos, cv2.FONT_HERSHEY_SIMPLEX, 0.58, (255, 255, 255), 1)
            cv2.putText(frame_out, d_txt, d_pos, cv2.FONT_HERSHEY_SIMPLEX, 0.58, (255, 255, 255), 1)
            if use_old_tracker:
                cv2.putText(frame_out, o_txt, o_pos, cv2.FONT_HERSHEY_SIMPLEX, 0.58, (0, 200, 255), 1)
            else:
                cv2.putText(frame_out, o_txt, o_pos, cv2.FONT_HERSHEY_SIMPLEX, 0.58, (255, 255, 255), 1)
            cv2.putText(frame_out, q_txt, q_pos, cv2.FONT_HERSHEY_SIMPLEX, 0.58, (255, 255, 255), 1)

            # FPS (white)
            cv2.putText(frame_out, f"{int(display_fps)} FPS", (12, fps_text_y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 255, 255), 2)

            # draw sliders (white fill)
            for i, name in enumerate(slider_names):
                x_start = SLIDER_PADDING + i * (slider_width + SLIDER_PADDING)
                vmin, vmax = slider_ranges[i]
                val_norm = (slider_values[i] - vmin) / float(vmax - vmin)
                fill_width = int(val_norm * slider_width)
                cv2.rectangle(frame_out, (x_start + 2, slider_y + 2),
                              (x_start + slider_width + 2, slider_y + SLIDER_HEIGHT + 2), (0, 0, 0), -1)
                cv2.rectangle(frame_out, (x_start, slider_y), (x_start + slider_width, slider_y + SLIDER_HEIGHT),
                              (50, 50, 50), -1)
                cv2.rectangle(frame_out, (x_start, slider_y), (x_start + fill_width, slider_y + SLIDER_HEIGHT),
                              (255, 255, 255), -1)
                cv2.putText(frame_out, name, (x_start, slider_y - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)


            # ------- draw trackers & landmarks (only when overlay visible) -------
            # helper to map input-space coordinates to output preview coords
            def input_to_output(px, py, crop_x1, crop_y1, crop_x2, crop_y2):
                rx = (px - crop_x1) / max(1, (crop_x2 - crop_x1)) * VCAM_WIDTH
                ry = (py - crop_y1) / max(1, (crop_y2 - crop_y1)) * VCAM_HEIGHT
                return int(rx), int(ry)


            try:
                # tracker main (green)
                if 'tracker_rect_main' in locals() and tracker_rect_main is not None:
                    bx, by, bw, bh = tracker_rect_main
                    p1 = input_to_output(bx, by, x1, y1, x2, y2)
                    p2 = input_to_output(bx + bw, by + bh, x1, y1, x2, y2)
                    cv2.rectangle(frame_out, p1, p2, (0, 255, 0), 2)

                # tracker big (blue/orange)
                if 'tracker_rect_big' in locals() and tracker_rect_big is not None:
                    bx, by, bw, bh = tracker_rect_big
                    p1 = input_to_output(bx, by, x1, y1, x2, y2)
                    p2 = input_to_output(bx + bw, by + bh, x1, y1, x2, y2)
                    cv2.rectangle(frame_out, p1, p2, (0, 130, 255), 2)

                # landmarks (white dots)
                if 'landmark_to_draw' in locals() and landmark_to_draw:
                    for (lx, ly) in landmark_to_draw:
                        ox, oy = input_to_output(lx, ly, x1, y1, x2, y2)
                        cv2.circle(frame_out, (ox, oy), 3, (0, 255, 0), -1)
            except Exception:
                # if crop coords (x1,y1,x2,y2) aren't available yet, skip drawing gracefully
                pass

            # dropdown items if open
            if dropdown_open:
                for idx_item, (rw, rh) in enumerate(RESOLUTIONS_16_9):
                    item_x = dropdown_x
                    item_y = dropdown_y + idx_item * dropdown_item_height
                    cv2.rectangle(frame_out, (item_x + 2, item_y + 2),
                                  (item_x + sw + 2, item_y + dropdown_item_height + 2), (0, 0, 0), -1)
                    cv2.rectangle(frame_out, (item_x, item_y), (item_x + sw, item_y + dropdown_item_height), (0, 0, 0),
                                  -1)
                    cv2.putText(frame_out, f"{rw}x{rh}", (item_x + 8, item_y + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                                (255, 255, 255), 1)

        # send & show
        cam.send(frame_out)
        disp = cv2.cvtColor(frame_out, cv2.COLOR_RGB2BGR)
        cv2.imshow("FaceCam Preview", disp)
        cam.sleep_until_next_frame()

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q') or key == 27:
            break
        if key == ord('s'):
            show_overlay = not show_overlay
        if key == ord('d'):
            results_so_far = {}
            for (w, h) in RESOLUTIONS_16_9:
                fps = measure_fps_for_res((w, h), frame_out, seconds=BENCH_SECONDS, results_so_far=results_so_far)
                results_so_far[(w, h)] = fps

            # select best resolution
            arr = np.array(list(results_so_far.values()))
            q1 = np.percentile(arr, 25)
            q3 = np.percentile(arr, 75)
            iqr = q3 - q1
            lower_thresh = max(TARGET_FPS, q1 - 1.5 * iqr)
            candidates = [i for i, val in enumerate(results_so_far.values()) if val >= lower_thresh]
            if candidates:
                best_idx = max(candidates)
            else:
                scores = [val * math.log(w * h + 1) for (w, h), val in results_so_far.items()]
                best_idx = int(np.argmax(scores))

            res_index = best_idx
            input_width, input_height = RESOLUTIONS_16_9[res_index]

            try:
                cap.release()
                cap = open_camera((input_width, input_height))
                aw = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                ah = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                input_width, input_height = aw, ah
                print(f"Benchmark switched resolution to {input_width} {input_height}")
            except Exception as ex:
                print("Failed switching resolution after benchmark:", ex)
        if key == ord('o'):
            use_old_tracker = not use_old_tracker


cap.release()
cv2.destroyAllWindows()
