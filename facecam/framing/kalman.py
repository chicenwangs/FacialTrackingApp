"""Constant-velocity Kalman filter on (cx, cy, w), ported from the v1 tracker."""

from __future__ import annotations

import numpy as np


class Kalman2DScale:
    """State [cx, vx, cy, vy, w, vw]; measurements are (cx, cy, w)."""

    def __init__(self, dt=1 / 30, process_noise_pos=1.0, process_noise_scale=1.0,
                 meas_noise_pos=50.0, meas_noise_scale=200.0) -> None:
        self.dt = dt
        self.x = np.zeros((6, 1))
        self.F = np.eye(6)
        self._set_dt(dt)
        self.H = np.zeros((3, 6))
        self.H[0, 0] = self.H[1, 2] = self.H[2, 4] = 1.0
        q, qs = process_noise_pos, process_noise_scale
        self.Q = np.diag([q, q * 0.1, q, q * 0.1, qs, qs * 0.1])
        self.R = np.diag([meas_noise_pos, meas_noise_pos, meas_noise_scale])
        self.P = np.eye(6) * 1000.0
        self.inited = False

    def _set_dt(self, dt: float) -> None:
        self.dt = dt
        self.F[0, 1] = self.F[2, 3] = self.F[4, 5] = dt

    def predict(self, dt: float | None = None) -> np.ndarray:
        if dt is not None and abs(dt - self.dt) > 1e-6:
            self._set_dt(dt)
        self.x = self.F @ self.x
        self.P = self.F @ self.P @ self.F.T + self.Q
        return self.x.copy()

    def update(self, z) -> np.ndarray:
        zv = np.asarray(z, dtype=float).reshape(3, 1)
        if not self.inited:
            self.x[:] = 0.0
            self.x[0, 0], self.x[2, 0], self.x[4, 0] = zv[0, 0], zv[1, 0], zv[2, 0]
            self.inited = True
            return self.x
        s = self.H @ self.P @ self.H.T + self.R
        k = self.P @ self.H.T @ np.linalg.inv(s)
        self.x = self.x + k @ (zv - self.H @ self.x)
        self.P = (np.eye(6) - k @ self.H) @ self.P
        return self.x

    @property
    def state(self) -> tuple[float, float, float]:
        return float(self.x[0, 0]), float(self.x[2, 0]), float(self.x[4, 0])
