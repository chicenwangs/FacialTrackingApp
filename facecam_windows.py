# facecam_windows.py
import cv2
import numpy as np
import pyvirtualcam
import time
import json
import os
import math

# ====== CONFIG ======
CONFIG_FILE = "facecam_config.json"

VCAM_WIDTH = 1280
VCAM_HEIGHT = 720
VCAM_ASPECT = VCAM_WIDTH / VCAM_HEIGHT

TRACK_FACE = True
SMOOTHING = 0.18

# Zoom/follow tuning
TARGET_FACE_FRAC = 0.18   # fraction of output width the face should occupy (baseline)
ZOOM_MIN = 1.0
ZOOM_MAX = 3.0

# benchmark parameters (ONLY used when you press D / click benchmark)
TARGET_FPS = 15.0
BENCH_SECONDS = 0.8

# UI
SLIDER_HEIGHT = 20
SLIDER_PADDING = 10
SLIDER_NAMES = ["Brightness", "Contrast", "Zoom"]
# zoom slider range maps 50..200 -> 0.5 .. 2.0 multiplier baseline
SLIDER_RANGES = [(0, 100), (0, 100), (50, 200)]

# Candidate 16:9 resolutions (high->low)
RESOLUTIONS_16_9 = [
    (1920, 1080),
    (1600, 900),
    (1280, 720),
    (1024, 576),
    (854, 480),
    (640, 360)
]

# ===== State =====
show_overlay = True
slider_values = [50, 50, 100]  # brightness, contrast, zoom*100 baseline
active_slider = None
res_index = None
cap = None
dropdown_open = False

# UI geometry (top groups)
res_box = (10, 10, 220, 36)          # resolution box (x,y,w,h)
controls_box = (res_box[0] + res_box[2] + 12, 10, 385, 36)  # larger black rectangle to the right
# slider geometry (on VCAM canvas)
slider_width = (VCAM_WIDTH - SLIDER_PADDING * 4) // len(SLIDER_NAMES)
slider_y = VCAM_HEIGHT - SLIDER_HEIGHT - SLIDER_PADDING
fps_text_y = slider_y - 36
dropdown_item_height = 30
dropdown_x, dropdown_y = res_box[0], res_box[1] + res_box[3] + 6

# face detector
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

# ===== Helpers =====
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

def measure_fps_for_res(res, seconds=BENCH_SECONDS):
    c = open_camera(res)
    if not c.isOpened():
        c.release()
        return 0.0
    t0 = time.time()
    frames = 0
    while time.time() - t0 < seconds:
        ret, _ = c.read()
        if ret:
            frames += 1
        else:
            time.sleep(0.005)
    elapsed = max(1e-6, time.time() - t0)
    avg_fps = frames / elapsed
    c.release()
    return avg_fps

def select_best_resolution_with_stats_impl():
    """Run on-demand benchmark, robustly filter out low-FPS outliers, choose highest res among candidates."""
    print("Running on-demand benchmark...")
    fps_list = []
    for (w,h) in RESOLUTIONS_16_9:
        avg = measure_fps_for_res((w,h), seconds=BENCH_SECONDS)
        fps_list.append(avg)
        print(f"  {w}x{h}: {avg:.1f} FPS")
    arr = np.array(fps_list)
    q1 = np.percentile(arr, 25)
    q3 = np.percentile(arr, 75)
    iqr = q3 - q1
    lower_thresh = max(TARGET_FPS, q1 - 1.5 * iqr)
    candidates = [i for i, val in enumerate(fps_list) if val >= lower_thresh]
    if candidates:
        best_idx = min(candidates)
        print("Candidates pass filter:", candidates, "-> choosing", best_idx, RESOLUTIONS_16_9[best_idx])
        save_config(best_idx)
        return best_idx
    # fallback score = fps * log(area)
    scores = []
    for idx, val in enumerate(fps_list):
        w,h = RESOLUTIONS_16_9[idx]
        area = w*h
        scores.append(val * math.log(area+1))
    best_idx = int(np.argmax(scores))
    print("No filtered candidates; selecting by score:", best_idx, RESOLUTIONS_16_9[best_idx])
    save_config(best_idx)
    return best_idx

# ===== Initialize camera quickly using saved config or default ====
saved_idx = load_config()
if saved_idx is not None:
    print("Using saved resolution index from config:", saved_idx, RESOLUTIONS_16_9[saved_idx])
    res_index = saved_idx
    tmp = open_camera(RESOLUTIONS_16_9[res_index])
    ok = tmp.isOpened()
    tmp.release()
    if not ok:
        print("Saved resolution could not be opened; will use camera default instead.")
        res_index = None

if res_index is None:
    print("Opening camera with system default resolution (fast startup).")
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        raise RuntimeError("Cannot open webcam")
    input_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    input_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps_camera = cap.get(cv2.CAP_PROP_FPS) or 30.0
    print(f"Default camera resolution: {input_width}x{input_height} @ {fps_camera:.1f} FPS")
else:
    input_width, input_height = RESOLUTIONS_16_9[res_index]
    cap = open_camera((input_width, input_height))
    if not cap.isOpened():
        raise RuntimeError("Cannot open webcam at saved resolution")
    aw = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    ah = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps_camera = cap.get(cv2.CAP_PROP_FPS) or 30.0
    input_width, input_height = aw, ah
    print(f"Camera opened (actual): {input_width}x{input_height} @ {fps_camera:.1f} FPS")

# recompute slider geometry if needed
slider_width = (VCAM_WIDTH - SLIDER_PADDING * 4) // len(SLIDER_NAMES)

cv2.namedWindow("FaceCam Preview", cv2.WINDOW_NORMAL)

# ===== Mouse callback & helpers =====
def update_slider_value(index, mouse_x):
    global slider_values
    x_start = SLIDER_PADDING + index * (slider_width + SLIDER_PADDING)
    vmin, vmax = SLIDER_RANGES[index]
    rel = (mouse_x - x_start) / slider_width
    new_val = int(vmin + rel * (vmax - vmin))
    new_val = max(min(new_val, vmax), vmin)
    slider_values[index] = new_val

def mouse_callback(event, x, y, flags, param):
    global active_slider, dropdown_open, res_index, input_width, input_height, cap, show_overlay
    if event == cv2.EVENT_LBUTTONDOWN:
        if show_overlay:
            # sliders
            for i in range(len(SLIDER_NAMES)):
                x_start = SLIDER_PADDING + i * (slider_width + SLIDER_PADDING)
                x_end = x_start + slider_width
                if slider_y <= y <= slider_y + SLIDER_HEIGHT and x_start <= x <= x_end:
                    active_slider = i
                    update_slider_value(i, x)
                    return
            # resolution box -> toggle dropdown
            rx, ry, rw, rh = res_box
            if rx <= x <= rx + rw and ry <= y <= ry + rh:
                dropdown_open = not dropdown_open
                return
            # dropdown items
            if dropdown_open:
                for idx_item, (rw_val, rh_val) in enumerate(RESOLUTIONS_16_9):
                    item_x = dropdown_x
                    item_y = dropdown_y + idx_item * dropdown_item_height
                    if item_x <= x <= item_x + rw and item_y <= y <= item_y + dropdown_item_height:
                        # choose resolution
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

            # controls group clickable using text bounding boxes
            hx, hy, hw, hh = controls_box
            if hx <= x <= hx + hw and hy <= y <= hy + hh:
                # compute text positions (must match drawing code)
                pad = 12
                cx = hx + pad
                cy = hy + hh // 2 + 6
                # text strings
                s_txt = "[S] Settings"
                d_txt = "[D]Benchmark"
                q_txt = "[Q]Quit"
                # measure widths
                s_size = cv2.getTextSize(s_txt, cv2.FONT_HERSHEY_SIMPLEX, 0.58, 1)[0]
                d_size = cv2.getTextSize(d_txt, cv2.FONT_HERSHEY_SIMPLEX, 0.58, 1)[0]
                q_size = cv2.getTextSize(q_txt, cv2.FONT_HERSHEY_SIMPLEX, 0.58, 1)[0]
                # positions
                s_pos = (cx, cy)
                d_pos = (cx + s_size[0] + 24, cy)
                q_pos = (cx + s_size[0] + d_size[0] + 48, cy)
                # make bounding boxes
                def point_in_text(px, py, pos, text_sz):
                    tx, ty = pos
                    tw, th = text_sz
                    # text baseline aligns bottom at ty, so top = ty - th
                    left = tx
                    right = tx + tw
                    top = ty - th
                    bottom = ty
                    return left <= px <= right and top <= py <= bottom
                # check which text clicked
                if point_in_text(x, y, s_pos, s_size):
                    show_overlay = not show_overlay
                    return
                if point_in_text(x, y, d_pos, d_size):
                    # run benchmark
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
                if point_in_text(x, y, q_pos, q_size):
                    # Quit visual clicked - actual quit via 'q' key; we set a flag by returning (main loop checks key)
                    # Here we simply break by raising KeyboardInterrupt handled by main loop keystroke,
                    # but we'll just set show_overlay False to give user feedback and rely on keyboard 'q' to quit.
                    # For safety, do nothing and let 'q' key perform quit.
                    return

        else:
            # overlay hidden: clicking controls area brings it back
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

# alias to deferred implementation
def select_best_resolution_with_stats_impl_alias():
    return select_best_resolution_with_stats_impl()

# ===== Main loop =====
with pyvirtualcam.Camera(width=VCAM_WIDTH, height=VCAM_HEIGHT, fps=(cap.get(cv2.CAP_PROP_FPS) or 30.0)) as cam:
    print("Virtual camera started:", cam.device)
    center_x, center_y = input_width // 2, input_height // 2
    last_time = time.time()
    display_fps = 0.0
    zoom_smoothed = slider_values[2] / 100.0  # baseline multiplier 0.5..2.0

    while True:
        ret, frame = cap.read()
        if not ret or frame is None:
            time.sleep(0.01)
            continue

        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
        face_detected = len(faces) > 0
        if TRACK_FACE and face_detected:
            x,y,w,h = faces[0]
            tx = x + w//2
            ty = y + h//2
            center_x += (tx - center_x) * SMOOTHING
            center_y += (ty - center_y) * SMOOTHING
            if show_overlay:
                cv2.rectangle(frame_rgb, (x,y), (x+w, y+h), (0,255,0), 2)

            # compute dynamic zoom so face occupies roughly TARGET_FACE_FRAC * VCAM_WIDTH
            user_zoom_mult = slider_values[2] / 100.0  # 0.5..2.0
            if w > 0:
                target_zoom = (TARGET_FACE_FRAC * input_width) / float(w)
                target_zoom *= user_zoom_mult
                target_zoom = max(min(target_zoom, ZOOM_MAX), ZOOM_MIN)
                zoom_smoothed += (target_zoom - zoom_smoothed) * 0.18
        else:
            user_zoom_mult = slider_values[2] / 100.0
            zoom_smoothed += (user_zoom_mult - zoom_smoothed) * 0.05

        zoom_scale = zoom_smoothed

        # apply brightness/contrast
        br = slider_values[0] / 50.0
        ct = slider_values[1] / 50.0
        frame_rgb = cv2.convertScaleAbs(frame_rgb, alpha=ct, beta=(br - 1.0) * 128)

        # ===== Compute crop rectangle that preserves VCAM aspect ratio to avoid stretching =====
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

        # draw overlay UI if shown
        if show_overlay:
            overlay = frame_out.copy()
            sx, sy, sw, sh = res_box
            cx, cy, cw_box, ch_box = controls_box

            # resolution dropdown shadow + panel
            cv2.rectangle(overlay, (sx+2, sy+2), (sx+sw+2, sy+sh+2), (0,0,0), -1)
            cv2.rectangle(overlay, (sx, sy), (sx+sw, sy+sh), (0,0,0), -1)

            # controls panel (translucent black box) with shadow (one big rectangle)
            cv2.rectangle(overlay, (cx+2, cy+2), (cx+cw_box+2, cy+ch_box+2), (0,0,0), -1)
            cv2.rectangle(overlay, (cx, cy), (cx+cw_box, cy+ch_box), (0,0,0), -1)

            # fps panel above sliders
            cv2.rectangle(overlay, (10, fps_text_y-22), (220, fps_text_y+8), (0,0,0), -1)

            alpha = 0.42
            frame_out = cv2.addWeighted(overlay, alpha, frame_out, 1-alpha, 0)

            # draw texts: resolution (on panel)
            cv2.putText(frame_out, f"{input_width}x{input_height}", (sx+8, sy+24), cv2.FONT_HERSHEY_SIMPLEX, 0.68, (255,255,255), 2)

            # controls text positions using measured widths
            pad = 12
            cx_text = cx + pad
            cy_text = cy + ch_box//2 + 6
            s_txt = "[S] Settings"
            d_txt = "[D]Benchmark"
            q_txt = "[Q]Quit"
            s_size = cv2.getTextSize(s_txt, cv2.FONT_HERSHEY_SIMPLEX, 0.58, 1)[0]
            d_size = cv2.getTextSize(d_txt, cv2.FONT_HERSHEY_SIMPLEX, 0.58, 1)[0]
            q_size = cv2.getTextSize(q_txt, cv2.FONT_HERSHEY_SIMPLEX, 0.58, 1)[0]
            s_pos = (cx_text, cy_text)
            d_pos = (cx_text + s_size[0] + 28, cy_text)
            q_pos = (cx_text + s_size[0] + d_size[0] + 56, cy_text)

            cv2.putText(frame_out, s_txt, s_pos, cv2.FONT_HERSHEY_SIMPLEX, 0.58, (255,255,255), 1)
            cv2.putText(frame_out, d_txt, d_pos, cv2.FONT_HERSHEY_SIMPLEX, 0.58, (255,255,255), 1)
            cv2.putText(frame_out, q_txt, q_pos, cv2.FONT_HERSHEY_SIMPLEX, 0.58, (255,255,255), 1)

            # FPS (white)
            cv2.putText(frame_out, f"{int(display_fps)} FPS", (12, fps_text_y), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255,255,255), 2)

            # draw sliders (shadow + background + white fill)
            for i, name in enumerate(SLIDER_NAMES):
                x_start = SLIDER_PADDING + i * (slider_width + SLIDER_PADDING)
                vmin, vmax = SLIDER_RANGES[i]
                val_norm = (slider_values[i] - vmin) / float(vmax - vmin)
                fill_width = int(val_norm * slider_width)
                cv2.rectangle(frame_out, (x_start+2, slider_y+2), (x_start+slider_width+2, slider_y+SLIDER_HEIGHT+2), (0,0,0), -1)
                cv2.rectangle(frame_out, (x_start, slider_y), (x_start+slider_width, slider_y+SLIDER_HEIGHT), (50,50,50), -1)
                cv2.rectangle(frame_out, (x_start, slider_y), (x_start+fill_width, slider_y+SLIDER_HEIGHT), (255,255,255), -1)
                cv2.putText(frame_out, name, (x_start, slider_y - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,255), 1)

            # dropdown items if open
            if dropdown_open:
                for idx_item, (rw, rh) in enumerate(RESOLUTIONS_16_9):
                    item_x = dropdown_x
                    item_y = dropdown_y + idx_item * dropdown_item_height
                    cv2.rectangle(frame_out, (item_x+2, item_y+2), (item_x+sw+2, item_y+dropdown_item_height+2), (0,0,0), -1)
                    cv2.rectangle(frame_out, (item_x, item_y), (item_x+sw, item_y+dropdown_item_height), (0,0,0), -1)
                    cv2.putText(frame_out, f"{rw}x{rh}", (item_x+8, item_y+20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 1)

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
            # run on-demand benchmark and switch resolution if better
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

cap.release()
cv2.destroyAllWindows()
