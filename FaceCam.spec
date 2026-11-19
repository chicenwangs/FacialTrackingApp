# -*- mode: python ; coding: utf-8 -*-
# PyInstaller one-folder build. Run: pyinstaller FaceCam.spec --noconfirm
import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

root = Path(SPECPATH).parent
datas = [(str(root / "ui" / "build"), "ui/build"), (str(root / "models"), "models")]
dll = root / "native" / "softcam" / "bin" / "softcam.dll"
if dll.exists():
    datas.append((str(dll), "native/softcam/bin"))
else:
    print("WARNING: softcam.dll missing; build will ship without its own camera")

binaries, hidden = [], []
for package in ("mediapipe", "webview", "clr_loader", "pythonnet"):
    data, bins, imports = collect_all(package)
    datas += data
    binaries += bins
    hidden += imports

a = Analysis(
    ["main.py"],
    pathex=[str(root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden + ["cv2", "numpy", "pystray._win32"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["IPython", "pytest"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True, name="FaceCam",
    debug=False, console=os.environ.get("FACECAM_CONSOLE") == "1",
    upx=True, runtime_tmpdir=None,
)
coll = COLLECT(exe, a.binaries, a.datas, name="FaceCam")
