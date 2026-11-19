# softcam (FaceCam Camera)

Upstream: github.com/tshino/softcam `v1.8.1`, MIT. No prebuilt DLL upstream, so this repo ships the source and a build script.

`build.ps1` patches the filter name to **FaceCam Camera** and the CLSID to `{B7E2A4C1-9D3F-4E6A-8B25-0C1D2E3F4A5B}`, then builds x64 Release. Python talks to it via ctypes in `facecam/vcam/softcam.py`.

## Steps

1. Need: git (only if `src/` is missing), VS 2022 or Build Tools with "Desktop development with C++" + Windows SDK.
2. Build (normal shell): `powershell -ExecutionPolicy Bypass -File native\softcam\build.ps1`
3. Register (**admin** shell, once): `regsvr32 "<repo>\native\softcam\bin\softcam-facecam.dll"`
4. Unregister: `regsvr32 /u "<repo>\native\softcam\bin\softcam-facecam.dll"`

The Setup page and Settings button in FaceCam can do step 3 for you with a UAC prompt. The registry stores the DLL path, so move the folder → re-register. x64 only; 32-bit apps will not see the camera (Zoom, Discord, Chrome and OBS are 64-bit).
