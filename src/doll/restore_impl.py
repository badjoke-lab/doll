"""Implementation for verified backup restore and post-restore validation."""

from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from doll.artifact import WorkspaceFileService
from doll.backup import (
    BACKUP_ROOT,
    MAX_BACKUP_TOTAL_BYTES,
    BackupError,
    BackupInspection,
    BackupIntegrityError,
    BackupUnsafePathError,
    BackupValidationError,
    _read_regular_file,
    verify_backup,
)
from doll.paths import canonicalize_path, find_doll_repository_ancestor
from doll.state import STATE_DATABASE_NAME, open_state_repository
from doll.state_package import (
    StatePackageError,
    export_state_package,
    import_state_package,
    verify_state_package,
)
from doll.workspace import WORKSPACE_DIRECTORIES, WORKSPACE_RECORD_NAME, load_workspace
from doll.workspace_files import validate_managed_path

_STATE_MEMBER = f"{BACKUP_ROOT}/payload/state-package.zip"
_WORKSPACE_MEMBER = f"{BACKUP_ROOT}/payload/workspace.json"
_DATABASE_MEMBER = f"{BACKUP_ROOT}/payload/state/{STATE_DATABASE_NAME}"
_ARTIFACT_PREFIX = f"{BACKUP_ROOT}/payload/artifacts/"


class RestoreError(BackupError):
    """Base class for restore failures."""


class RestoreConflictError(RestoreError):
    """Raised when the restore target is not absent or empty."""


class RestoreValidationError(RestoreError):
    """Raised when staged or published state fails validation."""


class RestorePublicationError(RestoreError):
    """Raised when atomic publication or rollback fails."""


@dataclass(frozen=True, slots=True)
class RestoreValidation:
    """Portable post-restore validation result."""

    workspace_id: str
    schema_version: int
    state_revision: int
    record_count: int
    artifact_count: int
    backup_inventory_count: int
    audit_event_count: int


@dataclass(frozen=True, slots=True)
class RestoreResult:
    """Result returned after publication and fresh-process validation."""

    backup_kind: str
    workspace_id: str
    source_state_revision: int
    restored_state_revision: int
    record_count: int
    artifact_count: int
    backup_inventory_count: int
    audit_event_count: int
    fresh_process_validated: bool


def restore_state_backup(backup_path: Path, target: Path) -> RestoreResult:
    return _restore_backup(backup_path, target, expected_kind="state")


def restore_workspace_backup(backup_path: Path, target: Path) -> RestoreResult:
    return _restore_backup(backup_path, target, expected_kind="workspace")


def validate_restored_workspace(
    target: Path,
    *,
    expected_workspace_id: str,
    expected_schema_version: int,
    expected_state_revision: int,
) -> RestoreValidation:
    workspace = load_workspace(target)
    if str(workspace.record.workspace_id) != expected_workspace_id:
        raise RestoreValidationError("restored workspace identity does not match backup")
    if workspace.record.state_revision != expected_state_revision:
        raise RestoreValidationError("restored workspace revision does not match expected state")

    descriptor, name = tempfile.mkstemp(prefix=".doll-restore-check-", suffix=".zip")
    os.close(descriptor)
    package_path = Path(name)
    package_path.unlink()
    try:
        with open_state_repository(target, read_only=True) as repository:
            status = repository.status()
            if status.workspace_id != expected_workspace_id:
                raise RestoreValidationError("restored database identity does not match backup")
            if status.schema_version != expected_schema_version:
                raise RestoreValidationError("restored schema version does not match backup")
            if status.state_revision != expected_state_revision:
                raise RestoreValidationError("restored database revision does not match expected state")
            integrity = repository.connection.execute("PRAGMA integrity_check").fetchone()
            if integrity is None or integrity[0] != "ok":
                raise RestoreValidationError("restored SQLite integrity check failed")
            if repository.connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
                raise RestoreValidationError("restored SQLite foreign-key check failed")
            package = export_state_package(repository, package_path)
            audit_count = _count(repository.connection, "SELECT COUNT(*) FROM audit_events")
            backup_count = _count(
                repository.connection,
                "SELECT COUNT(*) FROM records WHERE record_type = 'backup_manifest'",
            )
            artifact_rows = repository.connection.execute(
                "SELECT id FROM records WHERE record_type = 'artifact' "
                "AND status IN ('active', 'archived') ORDER BY id"
            ).fetchall()
            for row in artifact_rows:
                WorkspaceFileService(repository).verify(str(row[0]))

        verified = verify_state_package(package_path)
        if verified != package:
            raise RestoreValidationError("fresh portable validation result changed")
        if (
            verified.workspace_id != expected_workspace_id
            or verified.schema_version != expected_schema_version
            or verified.state_revision != expected_state_revision
        ):
            raise RestoreValidationError("portable validation identity changed")
        record_count = sum(verified.record_counts.values())
        if record_count != status.record_count:
            raise RestoreValidationError("restored record inventory is inconsistent")
        return RestoreValidation(
            workspace_id=verified.workspace_id,
            schema_version=verified.schema_version,
            state_revision=verified.state_revision,
            record_count=record_count,
            artifact_count=verified.record_counts.get("artifact", 0),
            backup_inventory_count=backup_count,
            audit_event_count=audit_count,
        )
    except RestoreError:
        raise
    except BaseException as exc:
        raise RestoreValidationError("restored workspace validation failed") from exc
    finally:
        package_path.unlink(missing_ok=True)


def _count(connection: object, query: str) -> int:
    row = connection.execute(query).fetchone()  # type: ignore[attr-defined]
    if row is None:
        raise RestoreValidationError("restored inventory is unreadable")
    return int(row[0])


def _restore_backup(backup_path: Path, target: Path, *, expected_kind: str) -> RestoreResult:
    inspection = verify_backup(backup_path)
    if inspection.backup_kind != expected_kind:
        raise RestoreValidationError("backup kind does not match restore operation")
    target_path, target_existed = _prepare_target(target)
    members = _read_verified_members(backup_path, inspection)
    staging = target_path.parent / f".doll-restore-{uuid4().hex}"
    empty_backup: Path | None = None
    published = False
    try:
        if expected_kind == "state":
            restored_revision = _stage_state_restore(members, staging)
        else:
            _stage_workspace_restore(members, staging)
            restored_revision = inspection.source_state_revision
        staged = validate_restored_workspace(
            staging,
            expected_workspace_id=inspection.workspace_id,
            expected_schema_version=inspection.schema_version,
            expected_state_revision=restored_revision,
        )
        empty_backup = _publish_target(staging, target_path, target_existed=target_existed)
        published = True
        fresh = _validate_in_fresh_process(
            target_path,
            inspection,
            expected_state_revision=restored_revision,
        )
        if fresh != staged:
            raise RestoreValidationError("fresh-process validation differs from staged validation")
        if empty_backup is not None:
            empty_backup.rmdir()
            empty_backup = None
        _fsync_directory(target_path.parent)
        return RestoreResult(
            backup_kind=expected_kind,
            workspace_id=fresh.workspace_id,
            source_state_revision=inspection.source_state_revision,
            restored_state_revision=fresh.state_revision,
            record_count=fresh.record_count,
            artifact_count=fresh.artifact_count,
            backup_inventory_count=fresh.backup_inventory_count,
            audit_event_count=fresh.audit_event_count,
            fresh_process_validated=True,
        )
    except RestoreError:
        _rollback_restore(staging, target_path, empty_backup, published, target_existed)
        raise
    except BaseException as exc:
        _rollback_restore(staging, target_path, empty_backup, published, target_existed)
        raise RestoreError("backup restore failed") from exc


def _prepare_target(target: Path) -> tuple[Path, bool]:
    expanded = target.expanduser()
    if os.path.lexists(expanded) and expanded.is_symlink():
        raise BackupUnsafePathError("restore target must not be a symbolic link")
    target_path = canonicalize_path(expanded)
    if find_doll_repository_ancestor(target_path) is not None:
        raise BackupUnsafePathError("restore target must be outside the repository")
    existed = target_path.exists()
    if existed:
        if not target_path.is_dir():
            raise RestoreConflictError("restore target is not a directory")
        if any(target_path.iterdir()):
            raise RestoreConflictError("restore target is not empty")
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if not target_path.parent.is_dir():
        raise RestoreConflictError("restore target parent is not a directory")
    return target_path, existed


def _read_verified_members(
    backup_path: Path, inspection: BackupInspection
) -> dict[str, bytes]:
    content = _read_regular_file(
        canonicalize_path(backup_path),
        maximum=MAX_BACKUP_TOTAL_BYTES,
        label="backup archive",
    )
    digest = f"sha256:{hashlib.sha256(content).hexdigest()}"
    if len(content) != inspection.file_size_bytes or digest != inspection.file_sha256:
        raise BackupIntegrityError("backup changed after verification")
    try:
        with zipfile.ZipFile(io.BytesIO(content), "r") as archive:
            return {info.filename: archive.read(info) for info in archive.infolist()}
    except (OSError, RuntimeError, ValueError, zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        raise BackupValidationError("verified backup could not be reopened") from exc


def _stage_state_restore(members: dict[str, bytes], staging: Path) -> int:
    try:
        nested = members[_STATE_MEMBER]
    except KeyError as exc:
        raise BackupIntegrityError("state backup payload is missing") from exc
    descriptor, name = tempfile.mkstemp(
        prefix=".doll-restore-state-", suffix=".zip", dir=staging.parent
    )
    path = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(nested)
            handle.flush()
            os.fsync(handle.fileno())
        return import_state_package(path, staging).imported_state_revision
    except StatePackageError as exc:
        raise RestoreValidationError("state backup payload could not be restored") from exc
    finally:
        path.unlink(missing_ok=True)


def _stage_workspace_restore(members: dict[str, bytes], staging: Path) -> None:
    try:
        workspace_bytes = members[_WORKSPACE_MEMBER]
        database_bytes = members[_DATABASE_MEMBER]
    except KeyError as exc:
        raise BackupIntegrityError("workspace backup payload is missing") from exc
    staging.mkdir(mode=0o700)
    try:
        for directory in WORKSPACE_DIRECTORIES:
            (staging / directory).mkdir(mode=0o700)
        _write_new_file(staging / WORKSPACE_RECORD_NAME, workspace_bytes)
        _write_new_file(staging / "state" / STATE_DATABASE_NAME, database_bytes)
        for name, content in members.items():
            if name.startswith(_ARTIFACT_PREFIX):
                relative = validate_managed_path(name.removeprefix(_ARTIFACT_PREFIX))
                destination = staging / "artifacts" / relative
                destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                _write_new_file(destination, content)
        for directory in (staging / "state", staging / "artifacts", staging):
            _fsync_directory(directory)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def _write_new_file(path: Path, content: bytes) -> None:
    try:
        with path.open("xb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            path.chmod(0o600)
        except OSError:
            pass
    except OSError as exc:
        raise RestorePublicationError("restore staging file could not be written") from exc


def _publish_target(staging: Path, target: Path, *, target_existed: bool) -> Path | None:
    empty_backup: Path | None = None
    published = False
    try:
        if target_existed:
            if not target.is_dir() or any(target.iterdir()):
                raise RestoreConflictError("restore target changed before publication")
            empty_backup = target.with_name(f".{target.name}.empty-{uuid4().hex}")
            os.replace(target, empty_backup)
        elif os.path.lexists(target):
            raise RestoreConflictError("restore target appeared before publication")
        os.replace(staging, target)
        published = True
        _fsync_directory(target.parent)
        return empty_backup
    except BaseException as exc:
        try:
            if published and target.exists():
                shutil.rmtree(target)
            if empty_backup is not None and empty_backup.exists():
                os.replace(empty_backup, target)
        except BaseException as rollback_exc:
            raise RestorePublicationError("restore publication rollback failed") from rollback_exc
        if isinstance(exc, RestoreError):
            raise
        raise RestorePublicationError("restore target could not be published") from exc


def _validate_in_fresh_process(
    target: Path,
    inspection: BackupInspection,
    *,
    expected_state_revision: int,
) -> RestoreValidation:
    command = [
        sys.executable,
        "-m",
        "doll.restore_validation",
        "--workspace",
        str(target),
        "--workspace-id",
        inspection.workspace_id,
        "--schema-version",
        str(inspection.schema_version),
        "--state-revision",
        str(expected_state_revision),
    ]
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RestoreValidationError("fresh-process validation could not run") from exc
    if completed.returncode != 0:
        raise RestoreValidationError("fresh-process validation failed")
    try:
        value = json.loads(completed.stdout)
        return RestoreValidation(
            workspace_id=str(value["workspace_id"]),
            schema_version=int(value["schema_version"]),
            state_revision=int(value["state_revision"]),
            record_count=int(value["record_count"]),
            artifact_count=int(value["artifact_count"]),
            backup_inventory_count=int(value["backup_inventory_count"]),
            audit_event_count=int(value["audit_event_count"]),
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise RestoreValidationError("fresh-process validation output is invalid") from exc


def _rollback_restore(
    staging: Path,
    target: Path,
    empty_backup: Path | None,
    published: bool,
    target_existed: bool,
) -> None:
    try:
        if staging.exists():
            shutil.rmtree(staging)
        if published and target.exists():
            shutil.rmtree(target)
        if empty_backup is not None and empty_backup.exists():
            os.replace(empty_backup, target)
        elif published and target_existed and not target.exists():
            target.mkdir(mode=0o700)
        _fsync_directory(target.parent)
    except BaseException as exc:
        raise RestorePublicationError("restore rollback failed") from exc


def _fsync_directory(path: Path) -> None:
    if os.name == "nt":
        return
    try:
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except OSError as exc:
        raise RestorePublicationError("restore directory durability check failed") from exc
