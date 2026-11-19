"""User settings directory and bundled resources (source tree or PyInstaller)."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def app_dir() -> Path:
    """FACECAM_HOME overrides this for tests and portable installs."""
    if home := os.environ.get("FACECAM_HOME"):
        return Path(home)
    return Path(os.environ.get("APPDATA", Path.home())) / "FaceCam"


def resource_dir() -> Path:
    """Root holding ui/build and native/; _MEIPASS when frozen."""
    frozen = getattr(sys, "_MEIPASS", None)
    return Path(frozen) if frozen else Path(__file__).resolve().parents[1]
