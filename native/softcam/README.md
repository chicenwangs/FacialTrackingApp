# softcam (McG Cam)

Upstream: github.com/tshino/softcam `v1.8.1`, MIT. No prebuilt DLL upstream → build here.
`build.ps1` clones, renames filter to **McG Cam**, new CLSID `{41411E10-0F51-4062-97E7-8D2914F8CE52}`, builds x64 Release.
Python talks to it via ctypes (`src/mcg/vcam/softcam.py`). Why: ADR-009.

## Steps
1. Need: git, VS 2022 (or Build Tools) with "Desktop development with C++" + Windows SDK.
2. Build (normal shell): `powershell -ExecutionPolicy Bypass -File native\softcam\build.ps1`
3. Register (**admin** shell, once): `regsvr32 "<repo>\native\softcam\bin\softcam.dll"`
4. Unregister: `regsvr32 /u "<repo>\native\softcam\bin\softcam.dll"`

Registry stores the DLL path. Move repo → re-register.
x64 only. 32-bit apps won't see McG Cam (fine: Zoom/Discord/Chrome/OBS are 64-bit).
