# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['facecam_mediapipe.py'],
    pathex=[],
    binaries=[('C:\\Users\\jeremy josh\\AppData\\Local\\Programs\\Python\\Python310\\Lib\\site-packages\\cv2\\cv2.pyd', '.'), ('C:\\Users\\jeremy josh\\AppData\\Local\\Programs\\Python\\Python310\\Lib\\site-packages\\cv2\\*.dll', '.')],
    datas=[('C:\\Users\\jeremy josh\\AppData\\Local\\Programs\\Python\\Python310\\Lib\\site-packages\\cv2\\data', 'cv2\\data'), ('C:\\Users\\jeremy josh\\AppData\\Local\\Programs\\Python\\Python310\\Lib\\site-packages\\cv2', 'cv2'), ('C:\\Users\\jeremy josh\\AppData\\Local\\Programs\\Python\\Python310\\Lib\\site-packages\\mediapipe', 'mediapipe')],
    hiddenimports=['pyvirtualcam', 'mediapipe', 'cv2', 'numpy'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='facecam_mediapipe',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
