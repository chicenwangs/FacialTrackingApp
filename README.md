# FaceCam v2

A Windows app that follows your face with the webcam and sends the framed video to **its own** virtual camera. Zoom, Discord, Teams, OBS and browsers pick that camera directly — you do not need OBS Virtual Camera or any other app that already provides one.

The app was built from the original `FacialTrackingApp` (v1) plus the useful parts of the McG v2 attempt. The hand-sign macro system is not included.

## What you asked for

- **Its own camera output.** The only output is the bundled DirectShow filter (`native/softcam`), named **McG Cam** after the build it came from. There is no output picker and no OBS/Unity option.
- **The webcam is picked automatically.** Startup probes camera indices and uses the saved one if it works, otherwise the first working camera. Setup no longer asks you to choose.
- **v1 two-box tracking, much cheaper.** `facecam/vision/hybrid_face.py` fuses face landmarks (0.6) + a tight box (0.3) + an enlarged box (0.1), with speed-adaptive smoothing, Kalman, rate limiting and a deadband so a still face stays still. The default landmark source is OpenCV YuNet (233 KB ONNX, `models/`), which avoids loading MediaPipe/TFLite at all: **~106 MB engine, ~132 MB with the native UI**. Use `python main.py --facemesh` for the old MediaPipe FaceMesh landmarks (better fine detail, ~170 MB engine). KCF was dropped: it allocated ~126 MB of FFT buffers on first update; two cheap MOSSE boxes replace it.
- **Light UI by default.** Native Tkinter window with preview, status, zoom, brightness/contrast, webcam and registration. `python main.py --web` gives McG's Svelte UI at ~150 MB extra. Closing **X really quits** in both.
- **30 fps preview and output.** `facecam/ui/preview.py` serves 640×360 MJPEG at 30 fps; the virtual camera stays 1280×720 at 30 fps. Separate capture / vision / output threads use a newest-frame buffer and placeholder frames when the webcam stalls.

## Install and run

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

The webcam is picked automatically at startup. Registration (once, admin) runs `regsvr32` on `native\softcam\bin\softcam.dll`; you can also do it from an admin shell or from the Settings buttons. After registering, restart FaceCam.

## UI

- **Native UI (default)** — live preview (Output / Camera toggle), status, zoom, webcam index, brightness, contrast, register button, Quit button and working X.
- **`--web` UI** — McG's Svelte Home / Settings / Setup pages with the same controls; Setup appears only if the camera is not registered.
- Both UIs use the same Python bridge and local MJPEG preview.

Settings are stored in `%APPDATA%\FaceCam\settings.json` (override with `FACECAM_HOME`).

## Layout

| Folder | Job |
| --- | --- |
| `facecam/capture` | Webcam thread, newest-frame slot, MSMF→DSHOW retry |
| `facecam/vision` | Restored v1 landmark + MOSSE tracking |
| `facecam/framing` | Kalman, zoom-to-face, crop, rate limiting (from McG) |
| `facecam/vcam` | softcam output, registration check, placeholder frames |
| `facecam/core` | Thread wiring and fixed-rate output |
| `facecam/ui` | Native Tkinter shell (default), optional pywebview shell, shared bridge and MJPEG preview |
| `ui/` | Svelte source and built static site |
| `native/softcam` | Built DLL and rebuild instructions |

## Tests and build

```powershell
python -m unittest discover -s tests
pyinstaller FaceCam.spec
```

18 tests cover crop math, framer, Kalman, settings, the frame buffer, YuNet startup, a still-face jitter test and a blind corner-tracking simulation. No webcam is needed. Latest sim: 0 lost frames, 16.9 px mean error, 2.66 px/frame jitter; still face moves the crop 0.33 px/frame. To rebuild the optional Svelte UI: `cd ui; npm ci; npm run build`.

## Rust feasibility spike

`rust-spike/` contains two small Rust programs that run the same YuNet ONNX model on a test face and print RSS and inference time. Measured here:

| Runtime | RSS after inference | Inference |
| --- | --- | --- |
| Python + OpenCV YuNet | ~46 MB | 7.6 ms at 320 px |
| Rust + tract (pure Rust kernels) | ~19 MB | 197 ms at 640 px |
| Rust + ONNX Runtime (optimised) | ~63 MB | 6.1 ms at 640 px |

Conclusion: Rust does not automatically save memory. A fast inference backend costs about as much as OpenCV's; the real savings would come from replacing the Python interpreter, NumPy and OpenCV's camera buffers, which is a full rewrite. Build the spike with `ORT_STRATEGY=system` and `ORT_LIB_LOCATION` pointing at a folder with `include/` and `lib/` from ONNX Runtime (the `download` strategy's old 1.8.1 URL is dead).

## Not included

The McG gesture pipeline, sign trainer, macro engine, Win32 hotkeys, tray, overlay HUD, autostart and installer. The OpenCV preview window and the output picker from the earlier v2 were also removed.
