# FaceCam 2.0.0

First packaged release.

## Install

Download `FaceCam-Setup-2.0.0.exe`, run it, and approve the UAC prompt. It installs the app and registers **FaceCam Camera**, so OBS Virtual Camera is not needed. Pick FaceCam Camera in Zoom, Discord, Teams, OBS or a browser. Uninstalling removes the camera registration.

Optional: desktop shortcut and "Start FaceCam with Windows" (starts dormant in the tray).

## Highlights

- Own DirectShow virtual camera named FaceCam Camera.
- Two-box face tracking with Kalman smoothing and rate limits; corner re-acquisition; auto-zoom; brightness/contrast.
- Separate capture, vision and fixed 30 fps output threads; placeholder frames if the webcam stalls.
- `Ctrl+Alt+F` freezes framing; `Ctrl+Alt+P` enters low-power mode (webcam closed, detection stopped, ~111 MB → ~83 MB).
- Tray with Open / Freeze / Pause / Quit; optional autostart; closing X quits.
- Native UI by default; `--web` gives the Svelte UI when running from source.
- YuNet detector by default; `--facemesh` is available only from source.

## Notes

- 64-bit only. Restart apps that were open before installation so they see the new camera.
- The release build excludes MediaPipe to keep the installer small (~58 MB).
- If registration fails, use **Register FaceCam Camera** in Settings, or run `regsvr32` on `native\softcam\bin\softcam-facecam.dll` from an admin shell.
