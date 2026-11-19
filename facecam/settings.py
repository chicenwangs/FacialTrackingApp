"""settings.json: validated, schema-tagged, atomic writes with a backup."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, replace
from pathlib import Path

log = logging.getLogger(__name__)


@dataclass
class Settings:
    schema: int = 1
    camera: int = 0
    width: int = 1280
    height: int = 720
    zoom: float = 1.0
    brightness: int = 50
    contrast: int = 50
    autostart: bool = False
    first_run_done: bool = False


def _number(raw, key, default, low, high, integer=False):
    value = raw.get(key, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    if integer:
        value = int(value)
    return min(high, max(low, value))


def from_dict(raw, base: Settings | None = None) -> Settings:
    """Validate a dict of settings; unknown keys are ignored."""
    if not isinstance(raw, dict):
        raise ValueError("not an object")
    s = replace(base or Settings())
    s.camera = _number(raw, "camera", s.camera, 0, 16, True)
    s.width = _number(raw, "width", s.width, 320, 3840, True)
    s.height = _number(raw, "height", s.height, 240, 2160, True)
    s.zoom = _number(raw, "zoom", s.zoom, 0.5, 2.0)
    s.brightness = _number(raw, "brightness", s.brightness, 0, 100, True)
    s.contrast = _number(raw, "contrast", s.contrast, 0, 100, True)
    s.autostart = bool(raw.get("autostart", s.autostart))
    s.first_run_done = bool(raw.get("first_run_done", s.first_run_done))
    return s


def load(path: Path) -> Settings:
    if not path.exists():
        return Settings()
    try:
        return from_dict(json.loads(path.read_text("utf-8")))
    except (OSError, ValueError) as exc:
        log.error("settings.json bad (%s); using defaults, old file kept as .bad", exc)
        try:
            path.replace(path.with_suffix(".json.bad"))
        except OSError:
            pass
        return Settings()


def save(path: Path, settings: Settings) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            path.with_suffix(".json.bak").write_text(path.read_text("utf-8"), "utf-8")
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(asdict(replace(settings, schema=1)), indent=2), "utf-8")
        tmp.replace(path)
    except OSError as exc:
        log.error("cannot save settings: %s", exc)
