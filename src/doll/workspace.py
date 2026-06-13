"""Workspace initialization primitives."""

from __future__ import annotations

import json
import os
import shutil
import stat
import tempfile
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Final

from doll import __version__
from doll.paths import canonicalize_path, default_workspace_root

WORKSPACE_RECORD_FILE: Final = "workspace.json"
WORKSPACE_SCHEMA_VERSION: Final = "0.1"
MINIMAL_WORKSPACE_DIRECTORIES: Final = ("state", "files", "cache")
_PRIVATE_DIRECTORY_MODE: Final = 0o700
_PRIVATE_FILE_MODE: Final = 0o600


class WorkspaceInitError(ValueError):
    """Raised when a workspace cannot be initialized safely."""


class ProfilePreference(StrEnum):
    """Allowed workspace profile preferences."""

    LITE = "lite"
    HEAVY = "heavy"
    AUTO = "auto"


@dataclass(frozen=True)
class WorkspaceRecord:
    """Stable identity record for a doll workspace."""

    workspace_id: str
    created_at: str
    updated_at: str
    schema_version: str
    product_version_created: str
    product_version_last_opened: str
    profile_preference: str
    state_revision: int
    instance_label: str


@dataclass(frozen=True)
class WorkspaceInitResult:
    """Result of initializing a workspace."""

    path: Path
    record: WorkspaceRecord
    created_root: bool


def create_workspace(
    target: Path | None = None,
    *,
    instance_label: str = "default",
    profile: ProfilePreference = ProfilePreference.LITE,
) -> WorkspaceInitResult:
    """Create a new workspace and identity record safely."""

    workspace_path = canonicalize_path(target or default_workspace_root())
    _reject_repository_ancestor(workspace_path)
    _reject_duplicate_workspace(workspace_path)
    created_root = _prepare_empty_root(workspace_path)
    created_directories: list[Path] = []
    record_path = workspace_path / WORKSPACE_RECORD_FILE
    temp_path: Path | None = None

    try:
        for directory_name in MINIMAL_WORKSPACE_DIRECTORIES:
            directory = workspace_path / directory_name
            directory.mkdir(mode=_PRIVATE_DIRECTORY_MODE)
            _apply_private_directory_permissions(directory)
            created_directories.append(directory)

        record = _new_workspace_record(instance_label=instance_label, profile=profile)
        fd, temp_name = tempfile.mkstemp(
            prefix=f".{WORKSPACE_RECORD_FILE}.", suffix=".tmp", dir=workspace_path
        )
        temp_path = Path(temp_name)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(asdict(record), handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp_path, _PRIVATE_FILE_MODE)
        os.replace(temp_path, record_path)
        temp_path = None
    except OSError as exc:
        _cleanup_failed_init(
            workspace_path,
            record_path=record_path,
            temp_path=temp_path,
            created_directories=created_directories,
            created_root=created_root,
        )
        raise WorkspaceInitError(f"failed to create workspace: {exc}") from exc

    return WorkspaceInitResult(path=workspace_path, record=record, created_root=created_root)


def _new_workspace_record(*, instance_label: str, profile: ProfilePreference) -> WorkspaceRecord:
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    return WorkspaceRecord(
        workspace_id=str(uuid.uuid4()),
        created_at=now,
        updated_at=now,
        schema_version=WORKSPACE_SCHEMA_VERSION,
        product_version_created=__version__,
        product_version_last_opened=__version__,
        profile_preference=profile.value,
        state_revision=0,
        instance_label=instance_label,
    )


def _prepare_empty_root(path: Path) -> bool:
    if path.exists():
        if not path.is_dir():
            raise WorkspaceInitError("workspace target exists and is not a directory")
        if any(path.iterdir()):
            raise WorkspaceInitError("workspace target must be empty")
        _apply_private_directory_permissions(path)
        return False
    path.mkdir(mode=_PRIVATE_DIRECTORY_MODE, parents=True)
    _apply_private_directory_permissions(path)
    return True


def _reject_duplicate_workspace(path: Path) -> None:
    if (path / WORKSPACE_RECORD_FILE).exists():
        raise WorkspaceInitError("workspace already exists at target")


def _reject_repository_ancestor(path: Path) -> None:
    for candidate in (path, *path.parents):
        if _looks_like_repository(candidate):
            raise WorkspaceInitError("workspace target must not be inside a repository checkout")


def _looks_like_repository(path: Path) -> bool:
    if (path / ".git").exists():
        return True
    pyproject = path / "pyproject.toml"
    try:
        return pyproject.is_file()
    except OSError:
        return False


def _apply_private_directory_permissions(path: Path) -> None:
    if os.name == "posix":
        path.chmod(_PRIVATE_DIRECTORY_MODE)


def _cleanup_failed_init(
    workspace_path: Path,
    *,
    record_path: Path,
    temp_path: Path | None,
    created_directories: list[Path],
    created_root: bool,
) -> None:
    if temp_path is not None:
        temp_path.unlink(missing_ok=True)
    record_path.unlink(missing_ok=True)
    for directory in reversed(created_directories):
        shutil.rmtree(directory, ignore_errors=True)
    if created_root:
        shutil.rmtree(workspace_path, ignore_errors=True)
    elif workspace_path.exists() and os.name == "posix":
        current_mode = stat.S_IMODE(workspace_path.stat().st_mode)
        if current_mode != _PRIVATE_DIRECTORY_MODE:
            workspace_path.chmod(_PRIVATE_DIRECTORY_MODE)
