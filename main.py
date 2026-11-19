"""FaceCam - face framing into its own virtual camera (no OBS needed)."""

from __future__ import annotations

import argparse
import ctypes
import sys
import traceback


def show_error(message: str) -> None:
    try:
        ctypes.windll.user32.MessageBoxW(None, message, "FaceCam", 0x10)
    except Exception:
        print("FaceCam error:", message, file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(prog="FaceCam")
    parser.add_argument("--web", action="store_true",
                        help="use the Svelte UI (looks nicer, uses ~150MB more RAM)")
    parser.add_argument("--facemesh", action="store_true",
                        help="use MediaPipe FaceMesh instead of the lighter YuNet detector")
    parser.add_argument("--minimized", action="store_true",
                        help="start in the tray (used by Start with Windows)")
    args = parser.parse_args()
    try:
        from facecam.core import App

        app = App(backend="facemesh" if args.facemesh else "yunet")
        if args.minimized:
            app.pause.set()      # autostart sits in the tray, webcam closed
        app.start()
        if args.web:
            from facecam.ui.shell import Shell

            Shell(app).run()
        else:
            from facecam.ui.native_shell import NativeShell

            NativeShell(app, minimized=args.minimized).run()
    except ImportError as exc:
        show_error(f"Missing package: {exc}\nRun: pip install -r requirements.txt")
    except Exception as exc:
        traceback.print_exc()
        show_error(f"{type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()
