"""Workspace initialization primitives."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from doll import __version__
from doll.paths import canonical_path, default_workspace_root

WORKSPACE_RECORD_FILE: Final = "workspace.json"
WORKSPACE_SCHEMA_VERSION: Final = "0.1"


class WorkspaceInitError(ValueError):
    """Raised when a workspace cannot be initialized safely."""


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


def create_workspace(
    target: Path | None = None, *, instance_label: str = "default"
) -> WorkspaceRecord:
    """Create a new workspace with an atomic identity record.

    The target directory must either not exist or be an empty directory. Repository checkouts,
    duplicate workspaces, and non-empty targets are rejected before durable state is written.
    If writing the identity record fails, files created by this call are cleaned up.
    """

    workspace_path = canonical_path(target or default_workspace_root())
    _reject_repository_checkout(workspace_path)
    _reject_duplicate_workspace(workspace_path)
    _prepare_empty_target(workspace_path)

    record = _new_workspace_record(instance_label=instance_label)
    created_record = workspace_path / WORKSPACE_RECORD_FILE
    temp_path: Path | None = None
    try:
        fd, temp_name = tempfile.mkstemp(
            prefix=f".{WORKSPACE_RECORD_FILE}.", suffix=".tmp", dir=workspace_path
        )
        temp_path = Path(temp_name)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(asdict(record), handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, created_record)
        temp_path = None
    except OSError as exc:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
        _cleanup_created_workspace(workspace_path, created_record)
        raise WorkspaceInitError(f"failed to create workspace identity: {exc}") from exc
    return record


def _new_workspace_record(*, instance_label: str) -> WorkspaceRecord:
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    return WorkspaceRecord(
        workspace_id=str(uuid.uuid4()),
        created_at=now,
        updated_at=now,
        schema_version=WORKSPACE_SCHEMA_VERSION,
        product_version_created=__version__,
        product_version_last_opened=__version__,
        profile_preference="lite",
        state_revision=0,
        instance_label=instance_label,
    )


def _prepare_empty_target(path: Path) -> None:
    if path.exists():
        if not path.is_dir():
            raise WorkspaceInitError("workspace target exists and is not a directory")
        if any(path.iterdir()):
            raise WorkspaceInitError("workspace target must be empty")
        return
    path.mkdir(parents=True)


def _reject_duplicate_workspace(path: Path) -> None:
    if (path / WORKSPACE_RECORD_FILE).exists():
        raise WorkspaceInitError("workspace already exists at target")


def _reject_repository_checkout(path: Path) -> None:
    if (path / ".git").exists() or (path / "pyproject.toml").exists():
        raise WorkspaceInitError("workspace target appears to be a repository checkout")


def _cleanup_created_workspace(path: Path, record_path: Path) -> None:
    record_path.unlink(missing_ok=True)
    try:
        next(path.iterdir())
    except StopIteration:
        shutil.rmtree(path, ignore_errors=True)
    except FileNotFoundError:
        return
