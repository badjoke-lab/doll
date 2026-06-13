"""Platform-aware path helpers for doll."""

from __future__ import annotations

import os
import platform
from pathlib import Path

APP_NAME = "doll"


def default_workspace_root() -> Path:
    """Return doll's platformdirs-style user data directory."""

    return _user_data_path(APP_NAME)


def canonicalize_path(path: Path) -> Path:
    """Return a canonical absolute path without requiring the final path to exist."""

    return path.expanduser().resolve(strict=False)


def _user_data_path(app_name: str) -> Path:
    """Small platformdirs-compatible user data path helper.

    The IMP-002 design uses platformdirs semantics. This helper keeps those semantics local while
    avoiding import-time filesystem access or additional runtime side effects.
    """

    system = platform.system()
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support" / app_name
    if system == "Windows":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / app_name
        return Path.home() / "AppData" / "Local" / app_name
    xdg_data_home = os.environ.get("XDG_DATA_HOME")
    if xdg_data_home:
        return Path(xdg_data_home) / app_name
    return Path.home() / ".local" / "share" / app_name
