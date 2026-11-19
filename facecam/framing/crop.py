"""Pure crop / zoom math (from McG, ported from the original main loop)."""

from __future__ import annotations

import math

from facecam.protocols import Rect

ZOOM_SLIDER_MIN = 0.5
ZOOM_SLIDER_MAX = 2.0


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def slider_to_mult(value: int) -> float:
    """UI slider 50..200 -> 0.5..2.0."""
    return clamp(value / 100.0, ZOOM_SLIDER_MIN, ZOOM_SLIDER_MAX)


def zoom_for_face(face_w, in_w, slider=1.0, target_frac=0.28,
                  zoom_min=1.0, zoom_max=3.0) -> float:
    """Zoom so the face fills target_frac * slider of the crop width.

    The v1 app ignored face_w here; zooming to the actual face is what keeps
    framing consistent when the user moves toward or away from the camera.
    """
    slider = clamp(slider, ZOOM_SLIDER_MIN, ZOOM_SLIDER_MAX)
    crop_w = max(1.0, face_w) / (target_frac * slider)
    return clamp(in_w / crop_w, zoom_min, zoom_max)


def crop_rect(cx, cy, zoom, in_w, in_h, aspect) -> Rect:
    """Crop of `aspect` centred on (cx, cy), shifted to stay inside the frame."""
    w = in_w / max(zoom, 1e-6)
    h = w / aspect
    if h > in_h:
        h = in_h
        w = h * aspect
    if w > in_w:
        w = in_w
        h = w / aspect
    cw, ch = max(2, int(w)), max(2, int(h))
    x = int(clamp(math.floor(cx - cw / 2), 0, in_w - cw))
    y = int(clamp(math.floor(cy - ch / 2), 0, in_h - ch))
    return Rect(x, y, cw, ch)


def rate_limit(prev, new, max_scale_step=0.20, max_move_frac=0.25):
    """Cap per-step size change and centre move (move cap = fraction of width)."""
    pcx, pcy, pw = prev
    cx, cy, w = new
    w = clamp(w, pw * (1 - max_scale_step), pw * (1 + max_scale_step))
    move = max_move_frac * w
    return pcx + clamp(cx - pcx, -move, move), pcy + clamp(cy - pcy, -move, move), w
