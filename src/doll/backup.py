"""Verified local backup creation, inspection, and integrity checking."""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import sqlite3
import stat
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import cast
from uuid import UUID

from pydantic import ValidationError

from doll.artifact import ArtifactCorruptError, WorkspaceFileService, _artifact_from_record
from doll.backup_manifest import BackupKind, BackupManifestRecord, BackupManifestService
from doll.paths import canonicalize_path, find_doll_repository_ancestor
from doll.state import (
    CURRENT_SCHEMA_VERSION,
    STATE_DATABASE_NAME,
    StateError,
    _utc_now,
    open_state_repository,
)
from doll.state_package import (
    StatePackageError,
    export_state_package,
    verify_state_package,
)
from doll.state_repository import StateRepository, _record_from_row
from doll.workspace import (
    WORKSPACE_DIRECTORIES,
    WORKSPACE_RECORD_NAME,
    WORKSPACE_SCHEMA_VERSION,
    WorkspaceRecord,
    load_workspace,
)
from doll.workspace_files import DEFAULT_MAX_ARTIFACT_BYTES, validate_managed_path

BACKUP_FORMAT_VERSION = 1
BACKUP_ROOT = "doll-backup"
CHECKSUM_ALGORITHM = "sha256"
ENCRYPTION_STATE = "none"

MAX_BACKUP_MEMBERS = 4096
MAX_BACKUP_MEMBER_BYTES = 768 * 1024 * 1024
MAX_BACKUP_TOTAL_BYTES = 1024 * 1024 * 1024
MAX_COMPRESSION_RATIO = 1000
MAX_JSON_BYTES = 4 * 1024 * 1024
MAX_WORKSPACE_SNAPSHOT_BYTES = 512 * 1024 * 1024

_DRIVE_PATH = re.compile(r"^[A-Za-z]:")
_DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_STATE_PAYLOAD_PATH = "payload/state-package.zip"
_WORKSPACE_RECORD_PATH = "payload/workspace.json"
_WORKSPACE_DATABASE_PATH = f"payload/state/{STATE_DATABASE_NAME}"
_ARTIFACT_PREFIX = "payload/artifacts/"
_REQUIRED_BASE_PATHS = ("manifest.json", "checksums.json", "README.txt")
_STATE_INCLUDED = ("doll_state_package",)
_STATE_EXCLUDED = (
    "backup_history",
    "caches",
    "model_assets",
    "reproducible_indexes",
    "runtime_assets",
    "secrets",
    "temporary_files",
)
_WORKSPACE_INCLUDED = (
    "authoritative_artifacts",
    "sqlite_state_snapshot",
    "workspace_identity",
)
_WORKSPACE_EXCLUDED = (
    "audit_directory_files",
    "backup_history",
    "caches",
    "configuration_files",
    "model_assets",
    "reproducible_indexes",
    "runtime_assets",
    "secrets",
    "temporary_files",
)


class BackupError(StateError):
    """Base class for local backup failures."""


class BackupValidationError(BackupError):
    """Raised when a backup source, request, or payload is invalid."""


class BackupIntegrityError(BackupError):
    """Raised when backup bytes, members, checksums, or snapshots disagree."""


class BackupUnsafePathError(BackupError):
    """Raised when a backup or workspace path is unsafe."""


class BackupLimitError(BackupError):
    """Raised when a backup exceeds a fixed resource boundary."""


class BackupCreationError(BackupError):
    """Raised when a backup cannot be created and published safely."""


class BackupRegistrationError(BackupError):
    """Raised when a published backup cannot be registered and is rolled back."""


@dataclass(frozen=True, slots=True)
class BackupInspection:
    """Fully verified portable metadata for one backup archive."""

    backup_format_version: int
    backup_kind: BackupKind
    workspace_id: str
    schema_version: int
    source_state_revision: int
    created_at: str
    included_categories: tuple[str, ...]
    excluded_categories: tuple[str, ...]
    member_count: int
    payload_file_count: int
    total_payload_size_bytes: int
    manifest_hash: str
    file_size_bytes: int
    file_sha256: str


@dataclass(frozen=True, slots=True)
class BackupCreationResult:
    """Result of verified publication and authoritative inventory registration."""

    inspection: BackupInspection
    inventory: BackupManifestRecord


def create_state_backup(
    workspace_path: Path | None,
    output_path: Path,
    *,
    created_at: str | None = None,
    operation_id: str | None = None,
) -> BackupCreationResult:
    """Create a verified backup that contains one verified Doll State package."""

    output = _prepare_output(workspace_path, output_path)
    timestamp = _validate_utc_timestamp(created_at or _utc_now(), "backup creation time")
    state_package_path = _temporary_sibling(output, suffix=".state-package.tmp")
    try:
        with open_state_repository(workspace_path, read_only=True) as repository:
            source = _source_identity(repository)
            export_state_package(repository, state_package_path, exported_at=timestamp)
            state_inspection = verify_state_package(state_package_path)
            if (
                state_inspection.workspace_id != source.workspace_id
                or state_inspection.schema_version != source.schema_version
                or state_inspection.state_revision != source.state_revision
            ):
                raise BackupIntegrityError("nested state package identity does not match source")
            _ensure_source_unchanged(repository, source)
        state_package_bytes = _read_regular_file(
            state_package_path,
            maximum=MAX_BACKUP_MEMBER_BYTES,
            label="state package",
        )
        members, manifest = _build_state_members(
            source=source,
            created_at=timestamp,
            state_package_bytes=state_package_bytes,
            state_package_record_count=sum(state_inspection.record_counts.values()),
            state_package_file_count=state_inspection.authoritative_file_count,
            omitted_secret_count=sum(state_inspection.omitted_secret_counts.values()),
        )
        inspection = _publish_verified_backup(output, members)
        _assert_manifest_matches_inspection(manifest, inspection)
        return _register_published_backup(
            workspace_path=workspace_path,
            output=output,
            inspection=inspection,
            operation_id=operation_id,
        )
    except BackupError:
        raise
    except StatePackageError as exc:
        raise BackupCreationError("state backup could not create a verified state package") from exc
    except BaseException as exc:
        raise BackupCreationError("state backup creation failed") from exc
    finally:
        state_package_path.unlink(missing_ok=True)


def create_workspace_backup(
    workspace_path: Path | None,
    output_path: Path,
    *,
    created_at: str | None = None,
    operation_id: str | None = None,
) -> BackupCreationResult:
    """Create a verified full durable-workspace backup without secret records."""

    output = _prepare_output(workspace_path, output_path)
    timestamp = _validate_utc_timestamp(created_at or _utc_now(), "backup creation time")
    snapshot_path = _temporary_sibling(output, suffix=".sqlite-snapshot.tmp")
    try:
        with open_state_repository(workspace_path, read_only=True) as repository:
            source = _source_identity(repository)
            _reject_secret_records(repository.connection)
            _validate_workspace_layout(repository.workspace.root)
            _create_sqlite_snapshot(repository.connection, snapshot_path)
            snapshot_metadata = _verify_sqlite_snapshot(snapshot_path, source)
            workspace_bytes = _read_workspace_identity(repository.workspace.root, source)
            artifacts = _collect_authoritative_artifacts(repository)
            _ensure_source_unchanged(repository, source)
        snapshot_bytes = _read_regular_file(
            snapshot_path,
            maximum=MAX_WORKSPACE_SNAPSHOT_BYTES,
            label="SQLite snapshot",
        )
        members, manifest = _build_workspace_members(
            source=source,
            created_at=timestamp,
            workspace_bytes=workspace_bytes,
            snapshot_bytes=snapshot_bytes,
            artifacts=artifacts,
            record_count=snapshot_metadata.record_count,
            audit_event_count=snapshot_metadata.audit_event_count,
        )
        inspection = _publish_verified_backup(output, members)
        _assert_manifest_matches_inspection(manifest, inspection)
        return _register_published_backup(
            workspace_path=workspace_path,
            output=output,
            inspection=inspection,
            operation_id=operation_id,
        )
    except BackupError:
        raise
    except BaseException as exc:
        raise BackupCreationError("workspace backup creation failed") from exc
    finally:
        snapshot_path.unlink(missing_ok=True)


def inspect_backup(backup_path: Path) -> BackupInspection:
    """Inspect a backup by performing complete verification."""

    return _load_backup(backup_path)


def verify_backup(backup_path: Path) -> BackupInspection:
    """Verify backup archive safety, checksums, manifest, and nested payloads."""

    return _load_backup(backup_path)


@dataclass(frozen=True, slots=True)
class _SourceIdentity:
    workspace_id: str
    workspace_schema_version: int
    schema_version: int
    state_revision: int


@dataclass(frozen=True, slots=True)
class _SnapshotMetadata:
    record_count: int
    audit_event_count: int


def _prepare_output(workspace_path: Path | None, output_path: Path) -> Path:
    output = canonicalize_path(output_path)
    if os.path.lexists(output):
        raise BackupCreationError("backup output already exists")
    if find_doll_repository_ancestor(output.parent) is not None:
        raise BackupUnsafePathError("backup output must be outside the source repository")
    output.parent.mkdir(parents=True, exist_ok=True)

    workspace = load_workspace(workspace_path)
    try:
        relative = output.relative_to(workspace.root)
    except ValueError:
        return output
    if not relative.parts or relative.parts[0] != "backups":
        raise BackupUnsafePathError("backup output inside a workspace must be under backups")
    return output


def _temporary_sibling(output: Path, *, suffix: str) -> Path:
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output.name}.",
        suffix=suffix,
        dir=output.parent,
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    temporary.unlink()
    return temporary


def _source_identity(repository: StateRepository) -> _SourceIdentity:
    status = repository.status()
    if repository.workspace.record.state_revision != status.state_revision:
        raise BackupValidationError("workspace and state revisions are inconsistent")
    return _SourceIdentity(
        workspace_id=str(repository.workspace.record.workspace_id),
        workspace_schema_version=repository.workspace.record.schema_version,
        schema_version=status.schema_version,
        state_revision=status.state_revision,
    )


def _ensure_source_unchanged(repository: StateRepository, source: _SourceIdentity) -> None:
    status = repository.status()
    fresh_workspace = load_workspace(repository.workspace.root)
    if (
        status.workspace_id != source.workspace_id
        or status.schema_version != source.schema_version
        or status.state_revision != source.state_revision
        or fresh_workspace.record.state_revision != source.state_revision
        or str(fresh_workspace.record.workspace_id) != source.workspace_id
    ):
        raise BackupIntegrityError("backup source changed during creation")


def _reject_secret_records(connection: sqlite3.Connection) -> None:
    try:
        row = connection.execute(
            "SELECT COUNT(*) FROM records WHERE sensitivity = 'secret'"
        ).fetchone()
    except sqlite3.DatabaseError as exc:
        raise BackupValidationError("secret-record inventory is unreadable") from exc
    if row is None:
        raise BackupValidationError("secret-record inventory is missing")
    if cast(int, row[0]) != 0:
        raise BackupValidationError(
            "unencrypted full workspace backup is refused while secret records exist"
        )


def _validate_workspace_layout(root: Path) -> None:
    expected_root = {WORKSPACE_RECORD_NAME, *WORKSPACE_DIRECTORIES}
    try:
        root_entries = {entry.name: entry for entry in root.iterdir()}
    except OSError as exc:
        raise BackupValidationError("workspace layout is unreadable") from exc
    if set(root_entries) != expected_root:
        raise BackupValidationError("workspace contains unknown or missing top-level content")
    for name, entry in root_entries.items():
        if entry.is_symlink():
            raise BackupUnsafePathError("workspace contains a symbolic link")
        if name == WORKSPACE_RECORD_NAME:
            if not entry.is_file():
                raise BackupValidationError("workspace identity is not a regular file")
        elif not entry.is_dir():
            raise BackupValidationError("workspace managed directory is not a directory")

    state_root = root / "state"
    allowed_state = {
        STATE_DATABASE_NAME,
        f"{STATE_DATABASE_NAME}-wal",
        f"{STATE_DATABASE_NAME}-shm",
    }
    state_entries = {entry.name: entry for entry in state_root.iterdir()}
    if STATE_DATABASE_NAME not in state_entries:
        raise BackupValidationError("workspace state database is missing")
    if set(state_entries) - allowed_state:
        raise BackupValidationError("workspace state directory contains unknown content")
    database = state_entries[STATE_DATABASE_NAME]
    if database.is_symlink() or not database.is_file():
        raise BackupUnsafePathError("workspace state database is not a regular file")
    for sidecar_name in allowed_state - {STATE_DATABASE_NAME}:
        sidecar = state_entries.get(sidecar_name)
        if sidecar is not None and (sidecar.is_symlink() or not sidecar.is_file()):
            raise BackupUnsafePathError("workspace SQLite sidecar is unsafe")

    for empty_directory in ("audit", "config"):
        directory = root / empty_directory
        if any(directory.iterdir()):
            raise BackupValidationError(
                f"workspace {empty_directory} content is not accepted by this backup format"
            )
    _validate_excluded_tree(root / "backups")
    _validate_excluded_tree(root / "temporary")


def _validate_excluded_tree(root: Path) -> None:
    for current, directories, files in os.walk(root, followlinks=False):
        current_path = Path(current)
        for name in [*directories, *files]:
            path = current_path / name
            if path.is_symlink():
                raise BackupUnsafePathError("excluded workspace content contains a symbolic link")


def _create_sqlite_snapshot(source: sqlite3.Connection, target: Path) -> None:
    if target.exists():
        raise BackupCreationError("temporary snapshot path already exists")
    try:
        destination = sqlite3.connect(target, isolation_level=None)
        try:
            source.backup(destination)
            result = destination.execute("PRAGMA integrity_check").fetchone()
            if result is None or result[0] != "ok":
                raise BackupIntegrityError("SQLite snapshot integrity check failed")
        finally:
            destination.close()
        _fsync_file(target)
    except BackupError:
        target.unlink(missing_ok=True)
        raise
    except sqlite3.DatabaseError as exc:
        target.unlink(missing_ok=True)
        raise BackupCreationError("SQLite snapshot could not be created") from exc


def _verify_sqlite_snapshot(path: Path, source: _SourceIdentity) -> _SnapshotMetadata:
    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(
            f"{path.resolve().as_uri()}?mode=ro",
            uri=True,
            isolation_level=None,
        )
        connection.row_factory = sqlite3.Row
        integrity = connection.execute("PRAGMA integrity_check").fetchone()
        if integrity is None or integrity[0] != "ok":
            raise BackupIntegrityError("SQLite snapshot integrity check failed")
        metadata = connection.execute(
            """
            SELECT workspace_id, schema_version, state_revision
            FROM schema_metadata WHERE singleton = 1
            """
        ).fetchone()
        if metadata is None:
            raise BackupIntegrityError("SQLite snapshot metadata is missing")
        if (
            cast(str, metadata["workspace_id"]) != source.workspace_id
            or cast(int, metadata["schema_version"]) != source.schema_version
            or cast(int, metadata["state_revision"]) != source.state_revision
        ):
            raise BackupIntegrityError("SQLite snapshot identity does not match source")
        secret_row = connection.execute(
            "SELECT COUNT(*) FROM records WHERE sensitivity = 'secret'"
        ).fetchone()
        if secret_row is None or cast(int, secret_row[0]) != 0:
            raise BackupIntegrityError("SQLite snapshot contains secret records")
        record_row = connection.execute("SELECT COUNT(*) FROM records").fetchone()
        audit_row = connection.execute("SELECT COUNT(*) FROM audit_events").fetchone()
        if record_row is None or audit_row is None:
            raise BackupIntegrityError("SQLite snapshot counts are unreadable")
        return _SnapshotMetadata(
            record_count=cast(int, record_row[0]),
            audit_event_count=cast(int, audit_row[0]),
        )
    except BackupError:
        raise
    except sqlite3.DatabaseError as exc:
        raise BackupIntegrityError("SQLite snapshot is unreadable") from exc
    finally:
        if connection is not None:
            connection.close()


def _read_workspace_identity(root: Path, source: _SourceIdentity) -> bytes:
    path = root / WORKSPACE_RECORD_NAME
    content = _read_regular_file(path, maximum=MAX_JSON_BYTES, label="workspace identity")
    try:
        record = WorkspaceRecord.model_validate_json(content)
    except ValidationError as exc:
        raise BackupValidationError("workspace identity is invalid") from exc
    if (
        str(record.workspace_id) != source.workspace_id
        or record.schema_version != source.workspace_schema_version
        or record.state_revision != source.state_revision
    ):
        raise BackupIntegrityError("workspace identity does not match backup source")
    return content


def _collect_authoritative_artifacts(repository: StateRepository) -> dict[str, bytes]:
    expected: dict[str, tuple[int, str, str]] = {}
    try:
        rows = repository.connection.execute(
            "SELECT id FROM records "
            "WHERE record_type = 'artifact' AND status IN ('active', 'archived') "
            "ORDER BY id"
        ).fetchall()
    except sqlite3.DatabaseError as exc:
        raise BackupValidationError("artifact inventory is unreadable") from exc
    for row in rows:
        record = repository.get_record(cast(str, row[0]))
        try:
            artifact = _artifact_from_record(record)
        except ArtifactCorruptError as exc:
            raise BackupValidationError("artifact inventory is invalid") from exc
        path = validate_managed_path(artifact.managed_path).as_posix()
        if path in expected:
            raise BackupValidationError("duplicate authoritative artifact path")
        expected[path] = (artifact.size_bytes, artifact.content_hash, artifact.artifact_id)

    actual = _artifact_file_paths(repository.workspace.root / "artifacts")
    if set(actual) != set(expected):
        raise BackupIntegrityError("workspace artifact files do not match authoritative records")

    result: dict[str, bytes] = {}
    service = WorkspaceFileService(repository)
    for managed_path, (size_bytes, content_hash, artifact_id) in expected.items():
        service.verify(artifact_id)
        content = _read_regular_file(
            actual[managed_path],
            maximum=DEFAULT_MAX_ARTIFACT_BYTES,
            label="managed artifact",
        )
        if len(content) != size_bytes:
            raise BackupIntegrityError("managed artifact size changed during backup")
        if f"sha256:{hashlib.sha256(content).hexdigest()}" != content_hash:
            raise BackupIntegrityError("managed artifact hash changed during backup")
        result[f"{_ARTIFACT_PREFIX}{managed_path}"] = content
    return result


def _artifact_file_paths(root: Path) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for current, directories, files in os.walk(root, followlinks=False):
        current_path = Path(current)
        for directory_name in directories:
            directory = current_path / directory_name
            if directory.is_symlink():
                raise BackupUnsafePathError("artifact tree contains a symbolic link")
        for file_name in files:
            path = current_path / file_name
            if path.is_symlink() or not path.is_file():
                raise BackupUnsafePathError("artifact tree contains a non-regular file")
            relative = path.relative_to(root).as_posix()
            validate_managed_path(relative)
            folded = relative.casefold()
            if any(existing.casefold() == folded for existing in result):
                raise BackupUnsafePathError("artifact tree has a case-folding path collision")
            result[relative] = path
    return result


def _build_state_members(
    *,
    source: _SourceIdentity,
    created_at: str,
    state_package_bytes: bytes,
    state_package_record_count: int,
    state_package_file_count: int,
    omitted_secret_count: int,
) -> tuple[dict[str, bytes], dict[str, object]]:
    members: dict[str, bytes] = {
        _STATE_PAYLOAD_PATH: state_package_bytes,
        "README.txt": _readme_bytes("state"),
    }
    manifest: dict[str, object] = {
        "backup_format_version": BACKUP_FORMAT_VERSION,
        "backup_kind": "state",
        "workspace_id": source.workspace_id,
        "source_workspace_schema_version": source.workspace_schema_version,
        "source_state_schema_version": source.schema_version,
        "source_state_revision": source.state_revision,
        "created_at": created_at,
        "checksum_algorithm": CHECKSUM_ALGORITHM,
        "encryption_state": ENCRYPTION_STATE,
        "included_categories": list(_STATE_INCLUDED),
        "excluded_categories": list(_STATE_EXCLUDED),
        "payload_file_count": 1,
        "total_payload_size_bytes": len(state_package_bytes),
        "state_package": {
            "path": f"{BACKUP_ROOT}/{_STATE_PAYLOAD_PATH}",
            "record_count": state_package_record_count,
            "authoritative_file_count": state_package_file_count,
            "omitted_secret_record_count": omitted_secret_count,
        },
    }
    return _finish_members(members, manifest), manifest


def _build_workspace_members(
    *,
    source: _SourceIdentity,
    created_at: str,
    workspace_bytes: bytes,
    snapshot_bytes: bytes,
    artifacts: dict[str, bytes],
    record_count: int,
    audit_event_count: int,
) -> tuple[dict[str, bytes], dict[str, object]]:
    members: dict[str, bytes] = {
        _WORKSPACE_RECORD_PATH: workspace_bytes,
        _WORKSPACE_DATABASE_PATH: snapshot_bytes,
        "README.txt": _readme_bytes("workspace"),
        **artifacts,
    }
    payload_size = (
        len(workspace_bytes) + len(snapshot_bytes) + sum(len(value) for value in artifacts.values())
    )
    manifest: dict[str, object] = {
        "backup_format_version": BACKUP_FORMAT_VERSION,
        "backup_kind": "workspace",
        "workspace_id": source.workspace_id,
        "source_workspace_schema_version": source.workspace_schema_version,
        "source_state_schema_version": source.schema_version,
        "source_state_revision": source.state_revision,
        "created_at": created_at,
        "checksum_algorithm": CHECKSUM_ALGORITHM,
        "encryption_state": ENCRYPTION_STATE,
        "included_categories": list(_WORKSPACE_INCLUDED),
        "excluded_categories": list(_WORKSPACE_EXCLUDED),
        "payload_file_count": 2 + len(artifacts),
        "total_payload_size_bytes": payload_size,
        "workspace_snapshot": {
            "workspace_path": f"{BACKUP_ROOT}/{_WORKSPACE_RECORD_PATH}",
            "database_path": f"{BACKUP_ROOT}/{_WORKSPACE_DATABASE_PATH}",
            "record_count": record_count,
            "audit_event_count": audit_event_count,
            "artifact_file_count": len(artifacts),
        },
    }
    return _finish_members(members, manifest), manifest


def _finish_members(members: dict[str, bytes], manifest: dict[str, object]) -> dict[str, bytes]:
    members["manifest.json"] = _json_bytes(manifest)
    checksums = {
        "algorithm": CHECKSUM_ALGORITHM,
        "entries": [
            {
                "path": f"{BACKUP_ROOT}/{path}",
                "sha256": hashlib.sha256(content).hexdigest(),
                "size_bytes": len(content),
            }
            for path, content in sorted(members.items())
        ],
    }
    members["checksums.json"] = _json_bytes(checksums)
    return {f"{BACKUP_ROOT}/{path}": content for path, content in members.items()}


def _publish_verified_backup(output: Path, members: dict[str, bytes]) -> BackupInspection:
    temporary = _temporary_sibling(output, suffix=".backup.tmp")
    published = False
    try:
        _write_deterministic_zip(temporary, members)
        inspection = verify_backup(temporary)
        _fsync_file(temporary)
        os.replace(temporary, output)
        published = True
        _fsync_directory(output.parent)
        published_inspection = verify_backup(output)
        if published_inspection != inspection:
            raise BackupIntegrityError("published backup differs from verified temporary archive")
        return published_inspection
    except BackupError:
        if published:
            _rollback_publication(output)
        temporary.unlink(missing_ok=True)
        raise
    except BaseException as exc:
        if published:
            _rollback_publication(output)
        temporary.unlink(missing_ok=True)
        raise BackupCreationError("backup publication failed") from exc


def _register_published_backup(
    *,
    workspace_path: Path | None,
    output: Path,
    inspection: BackupInspection,
    operation_id: str | None,
) -> BackupCreationResult:
    try:
        with open_state_repository(workspace_path) as repository:
            inventory = BackupManifestService(repository).register_verified(
                backup_kind=inspection.backup_kind,
                backup_format_version=inspection.backup_format_version,
                workspace_id=inspection.workspace_id,
                schema_version=inspection.schema_version,
                source_state_revision=inspection.source_state_revision,
                created_at=inspection.created_at,
                verified_at=_utc_now(),
                manifest_hash=inspection.manifest_hash,
                file_name=output.name,
                file_size_bytes=inspection.file_size_bytes,
                file_sha256=inspection.file_sha256,
                included_categories=inspection.included_categories,
                excluded_categories=inspection.excluded_categories,
                operation_id=operation_id,
            )
    except BaseException as exc:
        try:
            output.unlink(missing_ok=False)
            _fsync_directory(output.parent)
        except BaseException as rollback_exc:
            raise BackupRegistrationError(
                "backup inventory registration failed and publication rollback also failed"
            ) from rollback_exc
        raise BackupRegistrationError(
            "backup inventory registration failed; published backup was removed"
        ) from exc
    return BackupCreationResult(inspection=inspection, inventory=inventory)


def _load_backup(backup_path: Path) -> BackupInspection:
    expanded = backup_path.expanduser()
    if expanded.is_symlink():
        raise BackupValidationError("backup is not a regular file")
    backup = canonicalize_path(expanded)
    if not backup.is_file():
        raise BackupValidationError("backup is not a regular file")
    file_bytes = _read_regular_file(
        backup,
        maximum=MAX_BACKUP_TOTAL_BYTES,
        label="backup archive",
    )
    _validate_zip_end_record(file_bytes)
    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes), "r") as archive:
            infos = archive.infolist()
            _validate_archive_inventory(infos)
            members = {info.filename: archive.read(info) for info in infos}
    except BackupError:
        raise
    except (
        OSError,
        RuntimeError,
        ValueError,
        zipfile.BadZipFile,
        zipfile.LargeZipFile,
    ) as exc:
        raise BackupValidationError("backup ZIP is unreadable") from exc

    checksums_path = f"{BACKUP_ROOT}/checksums.json"
    checksums = _load_json_bytes(_required_member(members, checksums_path), "checksums")
    checksum_entries = _validate_checksums(checksums)
    expected_members = {checksums_path, *checksum_entries}
    if set(members) != expected_members:
        raise BackupIntegrityError("backup member inventory does not match checksums")
    for name, expected in checksum_entries.items():
        content = members[name]
        if len(content) != expected["size_bytes"]:
            raise BackupIntegrityError("backup member size does not match inventory")
        if hashlib.sha256(content).hexdigest() != expected["sha256"]:
            raise BackupIntegrityError("backup member checksum mismatch")

    manifest_path = f"{BACKUP_ROOT}/manifest.json"
    manifest_bytes = _required_member(members, manifest_path)
    manifest_value = _load_json_bytes(manifest_bytes, "manifest")
    inspection_base = _validate_manifest(manifest_value)
    _validate_member_paths_for_kind(set(members), inspection_base.backup_kind)
    if inspection_base.backup_kind == "state":
        _validate_state_payload(members, cast(dict[str, object], manifest_value), inspection_base)
    else:
        _validate_workspace_payload(
            members,
            cast(dict[str, object], manifest_value),
            inspection_base,
        )

    payload_size = _payload_size(members)
    if payload_size != inspection_base.total_payload_size_bytes:
        raise BackupIntegrityError("backup payload size does not match manifest")
    return BackupInspection(
        backup_format_version=inspection_base.backup_format_version,
        backup_kind=inspection_base.backup_kind,
        workspace_id=inspection_base.workspace_id,
        schema_version=inspection_base.schema_version,
        source_state_revision=inspection_base.source_state_revision,
        created_at=inspection_base.created_at,
        included_categories=inspection_base.included_categories,
        excluded_categories=inspection_base.excluded_categories,
        member_count=len(members),
        payload_file_count=inspection_base.payload_file_count,
        total_payload_size_bytes=inspection_base.total_payload_size_bytes,
        manifest_hash=f"sha256:{hashlib.sha256(manifest_bytes).hexdigest()}",
        file_size_bytes=len(file_bytes),
        file_sha256=f"sha256:{hashlib.sha256(file_bytes).hexdigest()}",
    )


@dataclass(frozen=True, slots=True)
class _ManifestInspection:
    backup_format_version: int
    backup_kind: BackupKind
    workspace_id: str
    workspace_schema_version: int
    schema_version: int
    source_state_revision: int
    created_at: str
    included_categories: tuple[str, ...]
    excluded_categories: tuple[str, ...]
    payload_file_count: int
    total_payload_size_bytes: int


def _validate_manifest(value: object) -> _ManifestInspection:
    if not isinstance(value, dict):
        raise BackupValidationError("backup manifest must be an object")
    manifest = cast(dict[str, object], value)
    if _required_positive_int(manifest, "backup_format_version") != BACKUP_FORMAT_VERSION:
        raise BackupValidationError("backup format version is unsupported")
    kind_value = _required_string(manifest, "backup_kind")
    if kind_value not in {"state", "workspace"}:
        raise BackupValidationError("backup kind is unsupported")
    kind = cast(BackupKind, kind_value)
    workspace_id = _required_uuid(manifest, "workspace_id")
    workspace_schema = _required_positive_int(manifest, "source_workspace_schema_version")
    if workspace_schema > WORKSPACE_SCHEMA_VERSION:
        raise BackupValidationError("workspace schema is newer than supported")
    schema_version = _required_positive_int(manifest, "source_state_schema_version")
    if schema_version != CURRENT_SCHEMA_VERSION:
        raise BackupValidationError("state schema is not current or supported")
    revision = _required_nonnegative_int(manifest, "source_state_revision")
    created_at = _validate_utc_timestamp(
        _required_string(manifest, "created_at"), "manifest creation time"
    )
    if manifest.get("checksum_algorithm") != CHECKSUM_ALGORITHM:
        raise BackupValidationError("backup checksum algorithm is unsupported")
    if manifest.get("encryption_state") != ENCRYPTION_STATE:
        raise BackupValidationError("encrypted backups are unsupported")
    included = _required_categories(manifest, "included_categories")
    excluded = _required_categories(manifest, "excluded_categories")
    expected_included = _STATE_INCLUDED if kind == "state" else _WORKSPACE_INCLUDED
    expected_excluded = _STATE_EXCLUDED if kind == "state" else _WORKSPACE_EXCLUDED
    if included != expected_included or excluded != expected_excluded:
        raise BackupValidationError("backup categories do not match format contract")
    payload_count = _required_positive_int(manifest, "payload_file_count")
    payload_size = _required_nonnegative_int(manifest, "total_payload_size_bytes")
    return _ManifestInspection(
        backup_format_version=BACKUP_FORMAT_VERSION,
        backup_kind=kind,
        workspace_id=workspace_id,
        workspace_schema_version=workspace_schema,
        schema_version=schema_version,
        source_state_revision=revision,
        created_at=created_at,
        included_categories=included,
        excluded_categories=excluded,
        payload_file_count=payload_count,
        total_payload_size_bytes=payload_size,
    )


def _validate_state_payload(
    members: dict[str, bytes],
    manifest: dict[str, object],
    inspection: _ManifestInspection,
) -> None:
    state_member = f"{BACKUP_ROOT}/{_STATE_PAYLOAD_PATH}"
    content = _required_member(members, state_member)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".doll-state-verify-", suffix=".zip")
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        nested = verify_state_package(temporary)
    except StatePackageError as exc:
        raise BackupIntegrityError("nested Doll State package is invalid") from exc
    finally:
        temporary.unlink(missing_ok=True)
    if (
        nested.workspace_id != inspection.workspace_id
        or nested.schema_version != inspection.schema_version
        or nested.state_revision != inspection.source_state_revision
    ):
        raise BackupIntegrityError("nested Doll State package identity does not match manifest")
    metadata = manifest.get("state_package")
    if not isinstance(metadata, dict):
        raise BackupValidationError("state package metadata is invalid")
    state_metadata = cast(dict[str, object], metadata)
    if state_metadata.get("path") != state_member:
        raise BackupIntegrityError("state package path does not match manifest")
    if _required_nonnegative_int(state_metadata, "record_count") != sum(
        nested.record_counts.values()
    ):
        raise BackupIntegrityError("state package record count does not match manifest")
    if (
        _required_nonnegative_int(state_metadata, "authoritative_file_count")
        != nested.authoritative_file_count
    ):
        raise BackupIntegrityError("state package file count does not match manifest")
    if _required_nonnegative_int(state_metadata, "omitted_secret_record_count") != sum(
        nested.omitted_secret_counts.values()
    ):
        raise BackupIntegrityError("state package secret omission count does not match manifest")
    if inspection.payload_file_count != 1:
        raise BackupIntegrityError("state backup payload file count is invalid")


def _validate_workspace_payload(
    members: dict[str, bytes],
    manifest: dict[str, object],
    inspection: _ManifestInspection,
) -> None:
    workspace_member = f"{BACKUP_ROOT}/{_WORKSPACE_RECORD_PATH}"
    database_member = f"{BACKUP_ROOT}/{_WORKSPACE_DATABASE_PATH}"
    workspace_bytes = _required_member(members, workspace_member)
    database_bytes = _required_member(members, database_member)
    try:
        workspace_record = WorkspaceRecord.model_validate_json(workspace_bytes)
    except ValidationError as exc:
        raise BackupValidationError("backup workspace identity is invalid") from exc
    if (
        str(workspace_record.workspace_id) != inspection.workspace_id
        or workspace_record.schema_version != inspection.workspace_schema_version
        or workspace_record.state_revision != inspection.source_state_revision
    ):
        raise BackupIntegrityError("backup workspace identity does not match manifest")

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".doll-workspace-verify-", suffix=".sqlite3"
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(database_bytes)
            handle.flush()
            os.fsync(handle.fileno())
        source = _SourceIdentity(
            workspace_id=inspection.workspace_id,
            workspace_schema_version=inspection.workspace_schema_version,
            schema_version=inspection.schema_version,
            state_revision=inspection.source_state_revision,
        )
        snapshot = _verify_sqlite_snapshot(temporary, source)
        artifacts = _snapshot_artifact_inventory(temporary)
    finally:
        temporary.unlink(missing_ok=True)

    actual_artifact_members = {
        name.removeprefix(f"{BACKUP_ROOT}/{_ARTIFACT_PREFIX}"): content
        for name, content in members.items()
        if name.startswith(f"{BACKUP_ROOT}/{_ARTIFACT_PREFIX}")
    }
    if set(actual_artifact_members) != set(artifacts):
        raise BackupIntegrityError("backup artifact members do not match snapshot records")
    for path, (size_bytes, content_hash) in artifacts.items():
        content = actual_artifact_members[path]
        if len(content) != size_bytes:
            raise BackupIntegrityError("backup artifact size does not match snapshot record")
        if f"sha256:{hashlib.sha256(content).hexdigest()}" != content_hash:
            raise BackupIntegrityError("backup artifact hash does not match snapshot record")

    metadata = manifest.get("workspace_snapshot")
    if not isinstance(metadata, dict):
        raise BackupValidationError("workspace snapshot metadata is invalid")
    snapshot_metadata = cast(dict[str, object], metadata)
    if snapshot_metadata.get("workspace_path") != workspace_member:
        raise BackupIntegrityError("workspace identity path does not match manifest")
    if snapshot_metadata.get("database_path") != database_member:
        raise BackupIntegrityError("workspace database path does not match manifest")
    if _required_nonnegative_int(snapshot_metadata, "record_count") != snapshot.record_count:
        raise BackupIntegrityError("workspace record count does not match manifest")
    if (
        _required_nonnegative_int(snapshot_metadata, "audit_event_count")
        != snapshot.audit_event_count
    ):
        raise BackupIntegrityError("workspace audit count does not match manifest")
    if _required_nonnegative_int(snapshot_metadata, "artifact_file_count") != len(artifacts):
        raise BackupIntegrityError("workspace artifact count does not match manifest")
    if inspection.payload_file_count != 2 + len(artifacts):
        raise BackupIntegrityError("workspace payload file count is invalid")


def _snapshot_artifact_inventory(path: Path) -> dict[str, tuple[int, str]]:
    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(
            f"{path.resolve().as_uri()}?mode=ro",
            uri=True,
            isolation_level=None,
        )
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT id, record_type, schema_version, created_at, updated_at, revision,
                   status, provenance, sensitivity, title, metadata_json
            FROM records
            WHERE record_type = 'artifact' AND status IN ('active', 'archived')
            ORDER BY id
            """
        ).fetchall()
        result: dict[str, tuple[int, str]] = {}
        for row in rows:
            record = _record_from_row(cast(sqlite3.Row, row))
            artifact = _artifact_from_record(record)
            managed_path = validate_managed_path(artifact.managed_path).as_posix()
            if managed_path in result:
                raise BackupIntegrityError("snapshot contains duplicate artifact paths")
            result[managed_path] = (artifact.size_bytes, artifact.content_hash)
        return result
    except BackupError:
        raise
    except (sqlite3.DatabaseError, ArtifactCorruptError) as exc:
        raise BackupIntegrityError("snapshot artifact inventory is invalid") from exc
    finally:
        if connection is not None:
            connection.close()


def _validate_zip_end_record(content: bytes) -> None:
    """Reject ZIP comments, trailing bytes, split archives, and inconsistent directories."""

    minimum_size = 22
    if len(content) < minimum_size:
        raise BackupIntegrityError("backup ZIP end record is missing")
    offset = len(content) - minimum_size
    record = content[offset:]
    if record[:4] != b"PK\x05\x06":
        raise BackupIntegrityError("backup ZIP must end with one canonical end record")
    disk_number = int.from_bytes(record[4:6], "little")
    directory_disk = int.from_bytes(record[6:8], "little")
    disk_entries = int.from_bytes(record[8:10], "little")
    total_entries = int.from_bytes(record[10:12], "little")
    directory_size = int.from_bytes(record[12:16], "little")
    directory_offset = int.from_bytes(record[16:20], "little")
    comment_length = int.from_bytes(record[20:22], "little")
    if (
        disk_number != 0
        or directory_disk != 0
        or disk_entries != total_entries
        or comment_length != 0
    ):
        raise BackupIntegrityError("backup ZIP end record is unsupported")
    if total_entries == 0xFFFF or directory_size == 0xFFFFFFFF or directory_offset == 0xFFFFFFFF:
        raise BackupIntegrityError("ZIP64 backups are unsupported")
    if directory_offset + directory_size != offset:
        raise BackupIntegrityError("backup ZIP central directory boundary is invalid")


def _validate_archive_inventory(infos: list[zipfile.ZipInfo]) -> None:
    if not infos or len(infos) > MAX_BACKUP_MEMBERS:
        raise BackupLimitError("backup member count is unsupported")
    seen: set[str] = set()
    folded: set[str] = set()
    total = 0
    for info in infos:
        name = _validate_member_name(info.filename)
        if name in seen:
            raise BackupUnsafePathError("duplicate backup member")
        folded_name = name.casefold()
        if folded_name in folded:
            raise BackupUnsafePathError("case-folding backup member collision")
        seen.add(name)
        folded.add(folded_name)
        mode = info.external_attr >> 16
        file_type = stat.S_IFMT(mode)
        if info.is_dir() or file_type == stat.S_IFLNK:
            raise BackupUnsafePathError("non-regular backup member")
        if file_type not in {0, stat.S_IFREG}:
            raise BackupUnsafePathError("unsupported backup entry type")
        if info.file_size < 0 or info.file_size > MAX_BACKUP_MEMBER_BYTES:
            raise BackupLimitError("backup member is too large")
        total += info.file_size
        if total > MAX_BACKUP_TOTAL_BYTES:
            raise BackupLimitError("backup total size is too large")
        if info.file_size > 0:
            if info.compress_size == 0:
                raise BackupLimitError("backup compression ratio is unsafe")
            if info.file_size / info.compress_size > MAX_COMPRESSION_RATIO:
                raise BackupLimitError("backup compression ratio is unsafe")


def _validate_member_name(value: str) -> str:
    if not value or "\\" in value or "\x00" in value:
        raise BackupUnsafePathError("backup member path is unsafe")
    if any(ord(character) < 32 for character in value):
        raise BackupUnsafePathError("backup member path has control characters")
    if value.startswith("/") or value.startswith("//") or _DRIVE_PATH.match(value):
        raise BackupUnsafePathError("backup member path is absolute")
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise BackupUnsafePathError("backup member path is unsafe")
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or path.parts[0] != BACKUP_ROOT:
        raise BackupUnsafePathError("backup root is invalid")
    return path.as_posix()


def _validate_checksums(value: object) -> dict[str, dict[str, object]]:
    if not isinstance(value, dict):
        raise BackupValidationError("checksums must be an object")
    checksums = cast(dict[str, object], value)
    if checksums.get("algorithm") != CHECKSUM_ALGORITHM:
        raise BackupValidationError("checksum algorithm is unsupported")
    entries = checksums.get("entries")
    if not isinstance(entries, list):
        raise BackupValidationError("checksum entries must be a list")
    result: dict[str, dict[str, object]] = {}
    for raw in entries:
        if not isinstance(raw, dict):
            raise BackupValidationError("checksum entry must be an object")
        entry = cast(dict[str, object], raw)
        path_value = entry.get("path")
        digest = entry.get("sha256")
        size = entry.get("size_bytes")
        if not isinstance(path_value, str):
            raise BackupValidationError("checksum path is invalid")
        safe_path = _validate_member_name(path_value)
        if safe_path.endswith("/checksums.json"):
            raise BackupValidationError("checksums must not self-reference")
        if safe_path in result:
            raise BackupValidationError("duplicate checksum entry")
        if not isinstance(digest, str) or not _DIGEST_PATTERN.fullmatch(digest):
            raise BackupValidationError("checksum digest is invalid")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise BackupValidationError("checksum size is invalid")
        result[safe_path] = {"sha256": digest, "size_bytes": size}
    return result


def _validate_member_paths_for_kind(paths: set[str], kind: BackupKind) -> None:
    fixed = {f"{BACKUP_ROOT}/{path}" for path in _REQUIRED_BASE_PATHS}
    if not fixed.issubset(paths):
        raise BackupIntegrityError("required backup member is missing")
    if kind == "state":
        expected = {f"{BACKUP_ROOT}/{_STATE_PAYLOAD_PATH}", *fixed}
        if paths != expected:
            raise BackupIntegrityError("state backup contains unsupported members")
        return
    required_workspace = {
        f"{BACKUP_ROOT}/{_WORKSPACE_RECORD_PATH}",
        f"{BACKUP_ROOT}/{_WORKSPACE_DATABASE_PATH}",
        *fixed,
    }
    if not required_workspace.issubset(paths):
        raise BackupIntegrityError("workspace backup member is missing")
    for path in paths - required_workspace:
        if not path.startswith(f"{BACKUP_ROOT}/{_ARTIFACT_PREFIX}"):
            raise BackupIntegrityError("workspace backup contains unsupported members")


def _write_deterministic_zip(path: Path, members: dict[str, bytes]) -> None:
    try:
        with zipfile.ZipFile(
            path,
            mode="x",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
            allowZip64=False,
        ) as archive:
            for name, content in sorted(members.items()):
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.create_system = 3
                info.external_attr = (stat.S_IFREG | 0o600) << 16
                info.flag_bits |= 0x800
                archive.writestr(info, content, compress_type=zipfile.ZIP_DEFLATED)
    except (OSError, ValueError, zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        raise BackupCreationError("backup ZIP could not be written") from exc


def _read_regular_file(path: Path, *, maximum: int, label: str) -> bytes:
    try:
        before = path.stat(follow_symlinks=False)
    except OSError as exc:
        raise BackupValidationError(f"{label} is unreadable") from exc
    if stat.S_IFMT(before.st_mode) != stat.S_IFREG:
        raise BackupUnsafePathError(f"{label} is not a regular file")
    if before.st_size < 0 or before.st_size > maximum:
        raise BackupLimitError(f"{label} exceeds the size limit")
    try:
        content = path.read_bytes()
        after = path.stat(follow_symlinks=False)
    except OSError as exc:
        raise BackupValidationError(f"{label} is unreadable") from exc
    if (
        before.st_dev != after.st_dev
        or before.st_ino != after.st_ino
        or before.st_size != after.st_size
        or before.st_mtime_ns != after.st_mtime_ns
        or len(content) != before.st_size
    ):
        raise BackupIntegrityError(f"{label} changed while being read")
    return content


def _rollback_publication(output: Path) -> None:
    try:
        output.unlink(missing_ok=True)
        _fsync_directory(output.parent)
    except BaseException as exc:
        raise BackupCreationError("backup publication rollback failed") from exc


def _fsync_file(path: Path) -> None:
    try:
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except OSError as exc:
        raise BackupCreationError("backup file durability check failed") from exc


def _fsync_directory(path: Path) -> None:
    if os.name == "nt":  # pragma: no cover - directory fsync is unavailable on Windows.
        return
    descriptor: int | None = None
    try:
        descriptor = os.open(path, os.O_RDONLY)
        os.fsync(descriptor)
    except OSError as exc:
        raise BackupCreationError("backup directory durability check failed") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _json_bytes(value: object) -> bytes:
    try:
        return (
            json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                allow_nan=False,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise BackupValidationError("backup value is not strict JSON") from exc


def _load_json_bytes(value: bytes, name: str) -> object:
    if len(value) > MAX_JSON_BYTES:
        raise BackupLimitError(f"{name} is too large")
    try:
        text = value.decode("utf-8")
        return json.loads(text, parse_constant=_reject_nonstandard_json)
    except UnicodeDecodeError as exc:
        raise BackupValidationError(f"{name} is not UTF-8") from exc
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise BackupValidationError(f"{name} is not valid strict JSON") from exc


def _reject_nonstandard_json(value: str) -> object:
    raise ValueError(f"non-standard JSON constant: {value}")


def _required_member(members: dict[str, bytes], name: str) -> bytes:
    try:
        return members[name]
    except KeyError as exc:
        raise BackupIntegrityError("required backup member is missing") from exc


def _required_string(mapping: dict[str, object], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise BackupValidationError(f"{key} is missing or invalid")
    return value


def _required_uuid(mapping: dict[str, object], key: str) -> str:
    value = _required_string(mapping, key)
    try:
        return str(UUID(value))
    except ValueError as exc:
        raise BackupValidationError(f"{key} is not a valid UUID") from exc


def _required_nonnegative_int(mapping: dict[str, object], key: str) -> int:
    value = mapping.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise BackupValidationError(f"{key} is not a non-negative integer")
    return value


def _required_positive_int(mapping: dict[str, object], key: str) -> int:
    value = _required_nonnegative_int(mapping, key)
    if value < 1:
        raise BackupValidationError(f"{key} is not positive")
    return value


def _required_categories(mapping: dict[str, object], key: str) -> tuple[str, ...]:
    value = mapping.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise BackupValidationError(f"{key} must be a string list")
    result = tuple(cast(list[str], value))
    if len(result) != len(set(result)):
        raise BackupValidationError(f"{key} contains duplicate values")
    return result


def _validate_utc_timestamp(value: str, name: str) -> str:
    if not value.endswith("Z"):
        raise BackupValidationError(f"{name} must be UTC")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise BackupValidationError(f"{name} is invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        raise BackupValidationError(f"{name} must be UTC")
    return value


def _payload_size(members: dict[str, bytes]) -> int:
    return sum(
        len(content)
        for name, content in members.items()
        if name.startswith(f"{BACKUP_ROOT}/payload/")
    )


def _readme_bytes(kind: BackupKind) -> bytes:
    return (
        "Doll Local Backup\n"
        f"Format version: {BACKUP_FORMAT_VERSION}\n"
        f"Backup kind: {kind}\n"
        "This archive contains data only. Do not execute backup content.\n"
        "Verify checksums.json and nested payloads before restore.\n"
        "Restore is not implemented by IMP-010.\n"
    ).encode()


def _assert_manifest_matches_inspection(
    manifest: dict[str, object], inspection: BackupInspection
) -> None:
    if (
        manifest.get("backup_kind") != inspection.backup_kind
        or manifest.get("workspace_id") != inspection.workspace_id
        or manifest.get("source_state_revision") != inspection.source_state_revision
    ):
        raise BackupIntegrityError("verified backup does not match creation manifest")
