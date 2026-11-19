"""Light native UI with a live preview, freeze control, tray and settings."""

from __future__ import annotations

import queue
import threading
import time
import tkinter as tk
from tkinter import ttk

import cv2
from PIL import Image, ImageDraw, ImageTk

from facecam.ui.bridge import Bridge
from facecam.ui.preview import H, W

BG = "#F1EED6"
CARD = "#FFFDF4"
INK = "#0A3323"
MUTED = "#3B5446"
ACCENT = "#D3968C"
STRIP = "#CFE1E3"
FONT = "Segoe UI"


class NativeShell:
    """Tkinter window: same controls as the web UI, without WebView2."""

    def __init__(self, app, minimized: bool = False) -> None:
        self.app = app
        self.bridge = Bridge(app)
        self.frames: queue.Queue = queue.Queue(maxsize=2)
        self.photo = None
        self.tray = None

        self.root = tk.Tk()
        self.root.title("FaceCam")
        self.root.geometry("1040x800")
        self.root.configure(bg=BG)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        self.mode = tk.StringVar(value="output")
        self.status = tk.StringVar(value="Starting")
        self.camera_text = tk.StringVar(value="Webcam: …")
        self.vcam_text = tk.StringVar(value="Virtual camera: …")
        self.fps_text = tk.StringVar(value="Stages: measuring…")
        self.freeze_text = tk.StringVar(value="Freeze framing")
        self.message = tk.StringVar(value="")

        self.zoom = tk.DoubleVar(value=app.settings.zoom)
        self.brightness = tk.IntVar(value=app.settings.brightness)
        self.contrast = tk.IntVar(value=app.settings.contrast)
        self.camera_index = tk.IntVar(value=app.settings.camera)
        self.autostart = tk.BooleanVar(value=app.settings.autostart)

        self._build()
        self._make_tray()
        if minimized:
            self.root.withdraw()
        threading.Thread(target=self._preview_worker, daemon=True).start()
        self._poll()

    def _card(self, parent):
        frame = tk.Frame(parent, bg=CARD, highlightbackground=INK,
                         highlightthickness=1, padx=14, pady=10)
        frame.pack(fill="x", padx=18, pady=8)
        return frame

    def _build(self) -> None:
        header = self._card(self.root)
        tk.Label(header, text="FaceCam", font=(FONT, 24, "bold"),
                 bg=CARD, fg=INK).pack(side="left")
        tk.Label(header, text="  your own camera — no OBS needed",
                 font=(FONT, 11), bg=CARD, fg=MUTED).pack(side="left", pady=(8, 0))
        self.status_label = tk.Label(header, textvariable=self.status,
                                     font=(FONT, 11, "bold"), bg=ACCENT, fg=CARD,
                                     padx=12, pady=4)
        self.status_label.pack(side="right")

        preview_card = self._card(self.root)
        strip = tk.Frame(preview_card, bg=STRIP)
        strip.pack(fill="x", pady=(0, 8))
        tk.Label(strip, text="Live preview", font=(FONT, 11, "bold"),
                 bg=STRIP, fg=INK).pack(side="left", padx=8, pady=3)
        self.preview_label = tk.Label(preview_card, text="Starting preview…",
                                      bg=INK, fg=CARD, width=W, height=H)
        self.preview_label.pack()

        controls = self._card(self.root)
        row = tk.Frame(controls, bg=CARD)
        row.pack(fill="x")
        tk.Button(row, text="Output", font=(FONT, 10, "bold"), bg=STRIP, fg=INK,
                  relief="groove", command=lambda: self.mode.set("output")).pack(side="left")
        tk.Button(row, text="Camera", font=(FONT, 10, "bold"), bg=CARD, fg=INK,
                  relief="groove", command=lambda: self.mode.set("camera")).pack(side="left", padx=6)
        self.freeze_button = tk.Button(row, textvariable=self.freeze_text,
                                       font=(FONT, 10, "bold"), bg=ACCENT, fg=CARD,
                                       relief="groove", command=self.toggle_freeze)
        self.freeze_button.pack(side="left", padx=6)
        tk.Label(row, text="Zoom", font=(FONT, 10), bg=CARD, fg=INK).pack(side="left", padx=(20, 4))
        self.zoom_label = tk.Label(row, text="1.0×", font=(FONT, 10, "bold"),
                                   bg=CARD, fg=INK, width=5)
        self.zoom_label.pack(side="right")
        tk.Scale(row, from_=0.5, to=2.0, resolution=0.1, orient="horizontal",
                 variable=self.zoom, command=self._set_zoom, bg=CARD, fg=INK,
                 highlightbackground=CARD, length=260, showvalue=False).pack(side="left")
        tk.Label(controls, text="Ctrl+Alt+F freezes the framing from any app",
                 font=(FONT, 9), bg=CARD, fg=MUTED).pack(anchor="w", pady=(6, 0))

        status = self._card(self.root)
        tk.Label(status, text="Status", font=(FONT, 11, "bold"),
                 bg=CARD, fg=INK).pack(anchor="w")
        for variable in (self.camera_text, self.vcam_text, self.fps_text):
            tk.Label(status, textvariable=variable, font=(FONT, 10), bg=CARD,
                     fg=INK, anchor="w").pack(fill="x", pady=1)

        settings = self._card(self.root)
        tk.Label(settings, text="Settings", font=(FONT, 11, "bold"),
                 bg=CARD, fg=INK).pack(anchor="w")
        row = tk.Frame(settings, bg=CARD)
        row.pack(fill="x", pady=6)
        tk.Label(row, text="Webcam", font=(FONT, 10), bg=CARD, fg=INK).pack(side="left")
        tk.Spinbox(row, from_=0, to=8, textvariable=self.camera_index,
                   width=5, font=(FONT, 10)).pack(side="left", padx=6)
        tk.Label(row, text="Brightness", font=(FONT, 10), bg=CARD, fg=INK).pack(side="left", padx=(18, 4))
        tk.Scale(row, from_=0, to=100, orient="horizontal", variable=self.brightness,
                 bg=CARD, fg=INK, highlightbackground=CARD, length=130).pack(side="left")
        tk.Label(row, text="Contrast", font=(FONT, 10), bg=CARD, fg=INK).pack(side="left", padx=(18, 4))
        tk.Scale(row, from_=0, to=100, orient="horizontal", variable=self.contrast,
                 bg=CARD, fg=INK, highlightbackground=CARD, length=130).pack(side="left")
        row = tk.Frame(settings, bg=CARD)
        row.pack(fill="x")
        tk.Checkbutton(row, text="Start with Windows", variable=self.autostart,
                       font=(FONT, 10), bg=CARD, fg=INK,
                       activebackground=CARD).pack(side="left")
        tk.Button(row, text="Register McG Cam", font=(FONT, 10), bg=CARD, fg=INK,
                  relief="groove", command=self._register).pack(side="left", padx=12)
        tk.Button(row, text="Save settings", font=(FONT, 10, "bold"), bg=INK,
                  fg=CARD, relief="groove", command=self._save).pack(side="left")
        tk.Label(settings, textvariable=self.message, font=(FONT, 9),
                 bg=CARD, fg=MUTED).pack(anchor="w", pady=(6, 0))

    def _make_tray(self) -> None:
        try:
            import pystray

            image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
            draw = ImageDraw.Draw(image)
            draw.rounded_rectangle((2, 2, 62, 62), 14, fill=INK)
            draw.ellipse((18, 14, 46, 42), outline=ACCENT, width=5)
            draw.rectangle((14, 48, 50, 54), fill=ACCENT)

            def on_open(icon):
                self.root.after(0, self.show)

            def on_freeze(icon):
                self.root.after(0, self.toggle_freeze)

            menu = pystray.Menu(
                pystray.MenuItem("Open FaceCam", on_open, default=True),
                pystray.MenuItem("Freeze framing", on_freeze,
                                 checked=lambda item: self.app.freeze.is_set()),
                pystray.MenuItem("Quit", lambda icon: self.root.after(0, self.close)),
            )
            self.tray = pystray.Icon("FaceCam", image, "FaceCam", menu)
        except Exception:
            self.tray = None

    def show(self) -> None:
        self.root.deiconify()
        self.root.lift()

    def toggle_freeze(self) -> None:
        self.app.toggle_freeze()

    def _set_zoom(self, _value=None) -> None:
        self.bridge.set_zoom(float(self.zoom.get()))
        self.zoom_label.config(text=f"{float(self.zoom.get()):.1f}×")

    def _save(self) -> None:
        result = self.bridge.save_settings({
            "camera": int(self.camera_index.get()),
            "brightness": int(self.brightness.get()),
            "contrast": int(self.contrast.get()),
            "zoom": float(self.zoom.get()),
            "autostart": bool(self.autostart.get()),
        })
        self.message.set(result.get("error") or "Saved")

    def _register(self) -> None:
        result = self.bridge.register_vcam()
        self.message.set(result.get("error") or "Registered - restart FaceCam")

    def _preview_worker(self) -> None:
        cap = None
        current_mode = None
        while not self.app.stop.is_set():
            mode = self.mode.get()
            if cap is None or mode != current_mode:
                if cap is not None:
                    cap.release()
                cap = cv2.VideoCapture(self.bridge._preview.url(mode))
                current_mode = mode
            ok, frame = cap.read()
            if not ok:
                time.sleep(0.1)
                continue
            image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            if self.frames.full():
                self.frames.get_nowait()
            self.frames.put(image)
        if cap is not None:
            cap.release()

    def _poll(self) -> None:
        if self.app.stop.is_set():
            return
        while not self.frames.empty():
            image = self.frames.get_nowait()
            self.photo = ImageTk.PhotoImage(image)
            self.preview_label.configure(image=self.photo, text="")
        state = self.bridge.state()
        self.status.set(state["state"].capitalize())
        self.status_label.configure(bg=ACCENT if not state["frozen"] else STRIP)
        self.camera_text.set(f"● Webcam: {state['camera']}")
        vcam = state["vcam"]
        self.vcam_text.set(f"● Virtual camera: McG Cam · {vcam['status']}"
                           + (" · in use" if vcam["connected"] else ""))
        stages = ", ".join(f"{name} {value} fps" for name, value in self.app.fps.items())
        self.fps_text.set(f"● {stages or 'measuring…'}")
        self.freeze_text.set("Resume framing" if state["frozen"] else "Freeze framing")
        if self.tray is not None:
            try:
                self.tray.update_menu()
            except Exception:
                pass
        self.root.after(100, self._poll)

    def close(self) -> None:
        self.app.stop.set()
        if self.tray is not None:
            self.tray.stop()
        self.root.destroy()

    def run(self) -> None:
        if self.tray is not None:
            self.tray.run_detached()
        self.root.mainloop()
        self.bridge.close()
        self.app.shutdown()
