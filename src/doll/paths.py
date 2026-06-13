"""Platform-aware paths for doll workspaces."""

from __future__ import annotations

import os
import platform
from pathlib import Path


def default_workspace_root() -> Path:
    """Return the platform convention for doll's private workspace root."""

    system = platform.system()
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "doll"
    if system == "Windows":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / "doll"
        return Path.home() / "AppData" / "Local" / "doll"
    xdg_data_home = os.environ.get("XDG_DATA_HOME")
    if xdg_data_home:
        return Path(xdg_data_home) / "doll"
    return Path.home() / ".local" / "share" / "doll"


def canonical_path(path: Path) -> Path:
    """Resolve a path for containment and duplicate checks without requiring it to exist."""

    return path.expanduser().resolve(strict=False)
