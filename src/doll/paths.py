"""Platform-aware path helpers for private doll data."""

from __future__ import annotations

from pathlib import Path

from platformdirs import user_data_path


def canonicalize_path(path: Path) -> Path:
    """Return an absolute, expanded, normalized path without requiring it to exist."""

    return path.expanduser().resolve(strict=False)


def default_workspace_path() -> Path:
    """Return the platform-appropriate default private workspace root."""

    return canonicalize_path(Path(user_data_path("doll", appauthor=False, roaming=False)))


def find_doll_repository_ancestor(path: Path) -> Path | None:
    """Return the containing doll repository checkout, if one can be identified."""

    canonical = canonicalize_path(path)
    for candidate in (canonical, *canonical.parents):
        pyproject = candidate / "pyproject.toml"
        if not (candidate / ".git").exists() or not pyproject.is_file():
            continue
        try:
            content = pyproject.read_text(encoding="utf-8")
        except OSError:
            continue
        if 'name = "doll-ai"' in content:
            return candidate
    return None
