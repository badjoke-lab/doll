"""Private workspace initialization and identity records."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from doll import __version__
from doll.paths import canonicalize_path, default_workspace_path, find_doll_repository_ancestor

WORKSPACE_SCHEMA_VERSION = 1
WORKSPACE_RECORD_NAME = "workspace.json"
WORKSPACE_DIRECTORIES = (
    "state",
    "artifacts",
    "audit",
    "backups",
    "config",
    "temporary",
)
ProfilePreference = Literal["lite", "heavy", "auto"]


class WorkspaceError(RuntimeError):
    """Base class for workspace initialization and loading failures."""


class WorkspaceExistsError(WorkspaceError):
    """Raised when a workspace identity already exists at the target."""


class WorkspacePathError(WorkspaceError):
    """Raised when a target path is unsafe or unusable."""


class WorkspaceNotEmptyError(WorkspaceError):
    """Raised when initialization would modify an unrelated non-empty directory."""


class WorkspaceRecordError(WorkspaceError):
    """Raised when a workspace identity record is missing or invalid."""


class WorkspaceRevisionError(WorkspaceError):
    """Raised when a state revision would move backwards."""


class WorkspaceRecord(BaseModel):
    """Stable identity and schema metadata for one doll workspace."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    workspace_id: UUID
    created_at: datetime
    updated_at: datetime
    schema_version: int = WORKSPACE_SCHEMA_VERSION
    product_version_created: str
    product_version_last_opened: str
    profile_preference: ProfilePreference = "lite"
    state_revision: int = Field(default=0, ge=0)
    instance_label: str = Field(min_length=1, max_length=120)

    @classmethod
    def create(
        cls,
        *,
        instance_label: str,
        profile_preference: ProfilePreference,
    ) -> WorkspaceRecord:
        """Create a new immutable workspace identity record."""

        now = datetime.now(UTC)
        return cls(
            workspace_id=uuid4(),
            created_at=now,
            updated_at=now,
            product_version_created=__version__,
            product_version_last_opened=__version__,
            profile_preference=profile_preference,
            instance_label=instance_label.strip(),
        )


@dataclass(frozen=True, slots=True)
class InitializedWorkspace:
    """Loaded or newly initialized doll workspace."""

    root: Path
    record: WorkspaceRecord


def _validate_target(root: Path) -> None:
    repository = find_doll_repository_ancestor(root)
    if repository is not None:
        raise WorkspacePathError(
            f"workspace must not be created inside the doll repository: {repository}"
        )

    if root.exists() and not root.is_dir():
        raise WorkspacePathError(f"workspace target is not a directory: {root}")

    record_path = root / WORKSPACE_RECORD_NAME
    if record_path.exists():
        raise WorkspaceExistsError(f"workspace already initialized: {root}")

    if root.exists() and any(root.iterdir()):
        raise WorkspaceNotEmptyError(f"workspace target is not empty: {root}")


def _write_record_atomic(path: Path, record: WorkspaceRecord) -> None:
    payload = json.dumps(record.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n"
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".workspace.",
        suffix=".tmp",
        dir=path.parent,
        text=True,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
        if os.name != "nt":
            path.chmod(0o600)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def _cleanup_failed_initialization(root: Path, *, created_root: bool) -> None:
    if created_root:
        shutil.rmtree(root, ignore_errors=True)
        return

    for directory_name in reversed(WORKSPACE_DIRECTORIES):
        directory = root / directory_name
        try:
            directory.rmdir()
        except OSError:
            pass
    (root / WORKSPACE_RECORD_NAME).unlink(missing_ok=True)


def initialize_workspace(
    path: Path | None = None,
    *,
    instance_label: str = "primary",
    profile_preference: ProfilePreference = "lite",
) -> InitializedWorkspace:
    """Initialize a new private workspace and return its stable identity."""

    root = canonicalize_path(path) if path is not None else default_workspace_path()
    _validate_target(root)

    label = instance_label.strip()
    if not label:
        raise WorkspacePathError("instance label must not be empty")

    created_root = False
    try:
        if not root.exists():
            root.mkdir(parents=True, exist_ok=False)
            created_root = True
        if os.name != "nt":
            root.chmod(0o700)

        for directory_name in WORKSPACE_DIRECTORIES:
            (root / directory_name).mkdir(exist_ok=False)

        record = WorkspaceRecord.create(
            instance_label=label,
            profile_preference=profile_preference,
        )
        _write_record_atomic(root / WORKSPACE_RECORD_NAME, record)
    except BaseException:
        _cleanup_failed_initialization(root, created_root=created_root)
        raise

    return InitializedWorkspace(root=root, record=record)


def load_workspace(path: Path | None = None) -> InitializedWorkspace:
    """Load and validate an initialized workspace without mutating it."""

    root = canonicalize_path(path) if path is not None else default_workspace_path()
    if not root.is_dir():
        raise WorkspaceRecordError(f"workspace directory does not exist: {root}")

    record_path = root / WORKSPACE_RECORD_NAME
    try:
        payload = record_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise WorkspaceRecordError(f"workspace identity is not readable: {record_path}") from exc

    try:
        record = WorkspaceRecord.model_validate_json(payload)
    except ValidationError as exc:
        raise WorkspaceRecordError(f"workspace identity is invalid: {record_path}") from exc

    if record.schema_version > WORKSPACE_SCHEMA_VERSION:
        raise WorkspaceRecordError(
            f"workspace schema version {record.schema_version} is newer than supported "
            f"version {WORKSPACE_SCHEMA_VERSION}"
        )

    state_directory = root / "state"
    if not state_directory.is_dir():
        raise WorkspaceRecordError(f"workspace state directory is missing: {state_directory}")

    return InitializedWorkspace(root=root, record=record)


def update_workspace_state_revision(root: Path, revision: int) -> WorkspaceRecord:
    """Persist a non-decreasing workspace state revision atomically."""

    workspace = load_workspace(root)
    if revision < workspace.record.state_revision:
        raise WorkspaceRevisionError(
            f"workspace state revision cannot decrease from "
            f"{workspace.record.state_revision} to {revision}"
        )
    if revision == workspace.record.state_revision:
        return workspace.record

    updated = workspace.record.model_copy(
        update={
            "state_revision": revision,
            "updated_at": datetime.now(UTC),
            "product_version_last_opened": __version__,
        }
    )
    _write_record_atomic(workspace.root / WORKSPACE_RECORD_NAME, updated)
    return updated
