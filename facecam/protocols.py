"""Small shared data types. Immutable so threads can pass them by assignment."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np


@dataclass(frozen=True, slots=True)
class Frame:
    image: np.ndarray          # HxWx3 uint8, RGB
    t_ns: int                  # time.perf_counter_ns() at capture
    seq: int


@dataclass(frozen=True, slots=True)
class Rect:
    x: float
    y: float
    w: float
    h: float


@dataclass(frozen=True, slots=True)
class FaceBox:
    box: Rect
    score: float


class FaceSource(Protocol):
    def detect(self, frame: Frame) -> FaceBox | None: ...


class VirtualCamera(Protocol):
    device: str

    def open(self, width: int, height: int, fps: int) -> None: ...

    def send(self, rgb: np.ndarray) -> None: ...

    def close(self) -> None: ...
