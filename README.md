# FaceCam 2.0

FaceCam keeps your face framed in a webcam feed and sends the result to **its own virtual camera**. Zoom, Discord, Teams, OBS and browsers select **FaceCam Camera** directly — OBS Virtual Camera is not needed.

Built from the original `FacialTrackingApp` plus the good parts of an earlier prototype; the hand-sign macro system was left out.

## Install

1. Download `FaceCam-Setup-2.0.0.exe` from the [latest release](https://github.com/chicenwangs/FacialTrackingApp/releases/latest).
2. Run it and approve the UAC prompt. The installer copies the app and registers **FaceCam Camera** with Windows.
3. Start FaceCam from the Start menu or desktop shortcut.
4. In Zoom/Discord/Teams/OBS, pick **FaceCam Camera** as the webcam. Restart any app that was already open before the install.

Optional installer choices: desktop shortcut, and "Start FaceCam with Windows" (starts in the tray in low-power mode). Uninstalling removes both the app and the camera registration.

## Features

- **Own camera output** — a bundled DirectShow filter, no OBS or other virtual-camera app.
- **Auto camera selection** — the first working webcam is used; no setup prompt.
- **Face framing** — two-box fusion (face landmarks + tight and enlarged trackers), Kalman smoothing, rate limiting and a deadband so a still face stays still.
- **Corner tracking** — detection rate increases near the edges of the frame.
- **Auto-zoom** — the face fills a target share of the frame; adjustable from 0.5× to 2×.
- **Brightness and contrast** controls.
- **Freeze framing** — hold the current crop; `Ctrl+Alt+F` or the button/tray item.
- **Low-power pause** — `Ctrl+Alt+P` closes the webcam, stops detection and sends one placeholder frame per second instead of 30 live frames. Working set drops from ~111 MB to ~83 MB.
- **Tray and autostart** — Open, Freeze, Pause and Quit in the tray; optional Run-key entry.
- **30 fps preview and virtual camera** — preview is 640×360 MJPEG; output is 1280×720.
- **30 fps output with placeholder frames** if the webcam stalls or is unplugged.

## Controls

| Key | Action |
| --- | --- |
| `Ctrl+Alt+F` | Freeze / resume framing |
| `Ctrl+Alt+P` | Pause / resume low-power mode |
| `Q` / `Esc` | Quit (closing the window X also quits) |

The window has Output/Camera preview toggle, Zoom slider, Freeze and Pause buttons, status chips, webcam index, brightness, contrast, "Register FaceCam Camera" and "Start with Windows".

Settings live in `%APPDATA%\FaceCam\settings.json`. For a portable copy set `FACECAM_HOME`.

## Troubleshooting

- **FaceCam Camera is not in the list.** Run the installer as admin, or click **Register FaceCam Camera** in Settings (UAC prompt). Then restart the video app.
- **Camera busy or black.** Close other apps using the webcam; capture retries every 2 seconds and the virtual camera keeps sending a placeholder meanwhile.
- **Jitter or drift.** Adjust Zoom, or raise `STILL_DEADBAND` / `WIDTH_DEADBAND` in `facecam/vision/hybrid_face.py` when running from source.
- **Dirty picture after moving the folder.** The registry stores the DLL path; re-register with `regsvr32 "<folder>\native\softcam\bin\softcam-facecam.dll"` from an admin shell.
- **32-bit apps cannot see the camera.** The filter is x64 only.

## Build from source

Python 3.10+ on Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

Optional flags: `--web` uses the Svelte/pywebview UI (~150 MB extra, available in the installed app too), `--facemesh` uses MediaPipe landmarks instead of the lighter OpenCV YuNet detector (source only, ~170 MB), `--minimized` starts in the tray dormant.

Build the release:

```powershell
pip install pyinstaller
python -m PyInstaller FaceCam.spec --noconfirm
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" packaging\FaceCam.iss
```

The installer is written to `installer/FaceCam-Setup-2.0.0.exe`. The release build excludes MediaPipe to keep the download at ~58 MB; `--facemesh` therefore only works from source.

## Layout

| Folder | Job |
| --- | --- |
| `facecam/capture` | Webcam thread, newest-frame slot, MSMF→DSHOW retry |
| `facecam/vision` | YuNet landmarks + two-box MOSSE fusion |
| `facecam/framing` | Kalman, zoom-to-face, crop, rate limiting |
| `facecam/vcam` | softcam output, registration check, placeholder frames |
| `facecam/core` | Thread wiring, freeze/pause state, fixed-rate output |
| `facecam/platform` | Hotkeys, autostart, vcam registration |
| `facecam/ui` | Native Tkinter shell, optional pywebview shell, bridge, MJPEG preview |
| `ui/` | Svelte source and built static site |
| `native/softcam` | Camera DLL, source and rebuild script |
| `packaging/` | Inno Setup installer script |
| `rust-spike/` | Rust feasibility measurements (not part of the app) |
| `tests/` | 20 unit and blind-simulation tests |

## Tests

```powershell
python -m unittest discover -s tests
```

No webcam needed. The suite covers crop math, Kalman, framer, settings, freeze/pause, and a synthetic face moving through the corners (0 lost frames, ~17 px error, 2.66 px/frame jitter, still face moves 0.33 px/frame).

`test_with_face.py` runs a 60-second live check with you in front of the camera: face box, crop, output device, FPS and RSS once a second.

## Credits

OpenCV YuNet model from OpenCV Zoo; DirectShow softcam by tshino (MIT) patched for FaceCam; UI styling derived from an earlier prototype.
