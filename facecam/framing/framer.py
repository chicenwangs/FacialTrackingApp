"""Face box -> smooth crop. The vision thread owns it; output only reads `.crop`."""

from __future__ import annotations

from dataclasses import dataclass

from facecam.framing.crop import (
    ZOOM_SLIDER_MAX, ZOOM_SLIDER_MIN, clamp, crop_rect, rate_limit, zoom_for_face,
)
from facecam.framing.kalman import Kalman2DScale
from facecam.protocols import Rect


@dataclass(frozen=True, slots=True)
class FramerConfig:
    target_face_frac: float = 0.28
    zoom_min: float = 1.0
    zoom_max: float = 3.0
    max_scale_step: float = 0.20
    max_move_frac: float = 0.25
    lost_hold_s: float = 0.5      # predict this long after the last face, then hold


class Framer:
    def __init__(self, in_w, in_h, aspect=16 / 9, cfg=None) -> None:
        self.in_w, self.in_h, self.aspect = in_w, in_h, aspect
        self.cfg = cfg or FramerConfig()
        self.slider = 1.0
        self.crop = crop_rect(in_w / 2, in_h / 2, 1.0, in_w, in_h, aspect)
        self._reset()

    def _reset(self) -> None:
        self.kf = Kalman2DScale()
        self._prev = None
        self._last_t = None
        self._last_face_t = float("-inf")

    def set_zoom(self, mult: float) -> None:
        self.slider = clamp(mult, ZOOM_SLIDER_MIN, ZOOM_SLIDER_MAX)

    def reset_tracking(self) -> None:
        """Forget filter state after a freeze; keep the held crop and zoom."""
        self._reset()

    def step(self, t: float, face: Rect | None = None) -> Rect:
        """Advance to t (seconds). No face -> brief prediction, then hold still."""
        dt = 1 / 30 if self._last_t is None else clamp(t - self._last_t, 1 / 240, 0.25)
        self._last_t = t
        if face is not None:
            self.kf.predict(dt)
            self.kf.update((face.x + face.w / 2, face.y + face.h / 2, face.w))
            self._last_face_t = t
        elif self.kf.inited and t - self._last_face_t < self.cfg.lost_hold_s:
            self.kf.predict(dt)
        else:
            return self.crop

        cfg = self.cfg
        state = self.kf.state
        if self._prev is not None:
            state = rate_limit(self._prev, state, cfg.max_scale_step, cfg.max_move_frac)
        self._prev = state
        cx, cy, w = state
        zoom = zoom_for_face(w, self.in_w, self.slider, cfg.target_face_frac,
                             cfg.zoom_min, cfg.zoom_max)
        self.crop = crop_rect(cx, cy, zoom, self.in_w, self.in_h, self.aspect)
        return self.crop
