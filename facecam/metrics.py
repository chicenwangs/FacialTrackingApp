"""Per-stage timings. Threads add, main thread reads once a second."""

from __future__ import annotations

import threading
from collections import defaultdict


class Metrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sum: dict[str, float] = defaultdict(float)
        self._n: dict[str, int] = defaultdict(int)

    def add(self, stage: str, ms: float) -> None:
        with self._lock:
            self._sum[stage] += ms
            self._n[stage] += 1

    def take(self) -> dict[str, tuple[int, float]]:
        """Return {stage: (count, mean_ms)} and reset."""
        with self._lock:
            out = {k: (n, self._sum[k] / n) for k, n in self._n.items() if n}
            self._sum.clear()
            self._n.clear()
        return out
