# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['facecam_mediapipe.py'],
    pathex=[],
    binaries=[],
    datas=[('facecam_config.json', '.'), ('C:\\Users\\jeremy josh\\AppData\\Local\\Programs\\Python\\Python310\\lib\\site-packages\\mediapipe\\modules', 'mediapipe\\modules'), ('C:\\Users\\jeremy josh\\AppData\\Local\\Programs\\Python\\Python310\\lib\\site-packages\\cv2\\data\\haarcascades\\haarcascade_frontalface_default.xml', 'haarcascades')],
    hiddenimports=['mediapipe', 'pyvirtualcam', 'cv2', 'numpy'],
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
    [],
    exclude_binaries=True,
    name='FaceCamApp',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='FaceCamApp',
)
