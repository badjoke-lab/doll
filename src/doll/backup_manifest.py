"""Authoritative inventory records for verified local backups."""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, cast
from uuid import UUID, uuid4

from doll.audit import _serialize_metadata as _serialize_audit_metadata
from doll.audit import _validate_token as _validate_audit_token
from doll.state import (
    ReadOnlyStateError,
    RecordEnvelope,
    StaleRevisionError,
    StateCorruptError,
    StateError,
    _utc_now,
)
from doll.state_repository import StateRepository, _validate_record_fields
from doll.state_repository import _serialize_metadata as _serialize_record_metadata

BackupKind = Literal["state", "workspace"]
VerificationStatus = Literal["verified"]

_ALLOWED_BACKUP_KINDS = frozenset({"state", "workspace"})
_ALLOWED_VERIFICATION_STATUSES = frozenset({"verified"})
_DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
_CATEGORY_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,79}$")
MAX_FILE_NAME_LENGTH = 255
MAX_CATEGORY_COUNT = 64
MAX_LIST_LIMIT = 200


class BackupManifestError(StateError):
    """Base class for authoritative backup inventory failures."""


class BackupManifestValidationError(BackupManifestError):
    """Raised when backup inventory metadata is invalid."""


class BackupManifestRegistrationError(BackupManifestError):
    """Raised when a verified backup cannot be registered atomically."""


class BackupManifestCorruptError(BackupManifestError):
    """Raised when a stored backup inventory record is malformed."""


@dataclass(frozen=True, slots=True)
class BackupManifestRecord:
    """Portable metadata for one successfully verified and registered backup."""

    backup_id: str
    backup_kind: BackupKind
    backup_format_version: int
    workspace_id: str
    schema_version: int
    source_state_revision: int
    created_at: str
    verified_at: str
    manifest_hash: str
    file_name: str
    file_size_bytes: int
    file_sha256: str
    verification_status: VerificationStatus
    included_categories: tuple[str, ...]
    excluded_categories: tuple[str, ...]


@dataclass(slots=True)
class BackupManifestService:
    """Register and inspect private verified-backup inventory records."""

    repository: StateRepository

    def register_verified(
        self,
        *,
        backup_kind: BackupKind,
        backup_format_version: int,
        workspace_id: str,
        schema_version: int,
        source_state_revision: int,
        created_at: str,
        verified_at: str,
        manifest_hash: str,
        file_name: str,
        file_size_bytes: int,
        file_sha256: str,
        included_categories: tuple[str, ...],
        excluded_categories: tuple[str, ...],
        operation_id: str | None = None,
        backup_id: str | None = None,
    ) -> BackupManifestRecord:
        """Register one verified backup with its audit event and revision atomically."""

        if self.repository.read_only:
            raise ReadOnlyStateError("state repository is open in read-only mode")

        safe_backup_id = _validate_uuid("backup ID", backup_id or str(uuid4()))
        safe_workspace_id = _validate_uuid("workspace ID", workspace_id)
        if safe_workspace_id != str(self.repository.workspace.record.workspace_id):
            raise BackupManifestValidationError(
                "backup workspace identity does not match repository"
            )
        safe_kind = _validate_backup_kind(backup_kind)
        safe_format = _validate_positive_int("backup format version", backup_format_version)
        safe_schema = _validate_positive_int("schema version", schema_version)
        safe_revision = _validate_nonnegative_int("source state revision", source_state_revision)
        safe_created_at = _validate_utc_timestamp(created_at, "backup creation time")
        safe_verified_at = _validate_utc_timestamp(verified_at, "backup verification time")
        if _parse_utc(safe_verified_at) < _parse_utc(safe_created_at):
            raise BackupManifestValidationError("backup verification precedes creation")
        safe_manifest_hash = _validate_digest("manifest hash", manifest_hash)
        safe_file_name = _validate_file_name(file_name)
        safe_file_size = _validate_nonnegative_int("backup file size", file_size_bytes)
        safe_file_hash = _validate_digest("backup file hash", file_sha256)
        safe_included = _validate_categories("included categories", included_categories)
        safe_excluded = _validate_categories("excluded categories", excluded_categories)
        if set(safe_included) & set(safe_excluded):
            raise BackupManifestValidationError("included and excluded categories overlap")
        safe_operation_id = _validate_audit_token("operation ID", operation_id or str(uuid4()), 200)

        _validate_record_fields(
            record_type="backup_manifest",
            schema_version=1,
            status="active",
            provenance="system-generated",
            sensitivity="internal",
        )

        metadata: dict[str, object] = {
            "backup_id": safe_backup_id,
            "backup_kind": safe_kind,
            "backup_format_version": safe_format,
            "workspace_id": safe_workspace_id,
            "schema_version": safe_schema,
            "source_state_revision": safe_revision,
            "created_at": safe_created_at,
            "verified_at": safe_verified_at,
            "manifest_hash": safe_manifest_hash,
            "file_name": safe_file_name,
            "file_size_bytes": safe_file_size,
            "file_sha256": safe_file_hash,
            "verification_status": "verified",
            "included_categories": list(safe_included),
            "excluded_categories": list(safe_excluded),
        }
        metadata_json = _serialize_record_metadata(metadata)
        audit_metadata_json = _serialize_audit_metadata(
            {
                "backup_kind": safe_kind,
                "backup_format_version": safe_format,
                "source_state_revision": safe_revision,
                "file_name": safe_file_name,
                "file_size_bytes": safe_file_size,
                "file_sha256": safe_file_hash,
                "manifest_hash": safe_manifest_hash,
            }
        )
        title = f"Verified {safe_kind} backup"
        event_id = str(uuid4())
        occurred_at = _utc_now()
        connection = self.repository.connection

        connection.execute("BEGIN IMMEDIATE")
        try:
            current = connection.execute(
                "SELECT schema_version, state_revision FROM schema_metadata WHERE singleton = 1"
            ).fetchone()
            if current is None:
                raise StateCorruptError("state metadata is missing during backup registration")
            if cast(int, current["schema_version"]) != safe_schema:
                raise StaleRevisionError("state schema changed before backup registration")
            if cast(int, current["state_revision"]) != safe_revision:
                raise StaleRevisionError("state revision changed before backup registration")
            connection.execute(
                """
                INSERT INTO records (
                    id,
                    record_type,
                    schema_version,
                    created_at,
                    updated_at,
                    revision,
                    status,
                    provenance,
                    sensitivity,
                    title,
                    metadata_json
                ) VALUES (?, 'backup_manifest', 1, ?, ?, 1, 'active',
                          'system-generated', 'internal', ?, ?)
                """,
                (
                    safe_backup_id,
                    safe_created_at,
                    safe_verified_at,
                    title,
                    metadata_json,
                ),
            )
            connection.execute(
                """
                INSERT INTO audit_events (
                    event_id,
                    operation_id,
                    occurred_at,
                    actor_type,
                    action,
                    target_type,
                    target_id,
                    result,
                    summary,
                    metadata_json
                ) VALUES (?, ?, ?, 'system', 'backup.create', 'backup_manifest', ?,
                          'success', 'Created verified local backup', ?)
                """,
                (
                    event_id,
                    safe_operation_id,
                    occurred_at,
                    safe_backup_id,
                    audit_metadata_json,
                ),
            )
            next_revision = self.repository._commit_state_revision()
            connection.execute("COMMIT")
        except (StaleRevisionError, StateCorruptError):
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
        except sqlite3.DatabaseError as exc:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise BackupManifestRegistrationError(
                "verified backup inventory could not be registered"
            ) from exc
        except BaseException:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise

        self.repository._sync_after_commit(next_revision)
        return self.get(safe_backup_id)

    def get(self, backup_id: str) -> BackupManifestRecord:
        """Return one backup inventory record."""

        safe_id = _validate_uuid("backup ID", backup_id)
        record = self.repository.get_record(safe_id)
        if record.record_type != "backup_manifest":
            raise KeyError(backup_id)
        return _backup_manifest_from_record(record)

    def list(self, *, limit: int = 50) -> tuple[BackupManifestRecord, ...]:
        """List newest active backup inventory records."""

        if limit < 1 or limit > MAX_LIST_LIMIT:
            raise BackupManifestValidationError(
                f"backup list limit must be between 1 and {MAX_LIST_LIMIT}"
            )
        try:
            rows = self.repository.connection.execute(
                """
                SELECT id
                FROM records
                WHERE record_type = 'backup_manifest' AND status = 'active'
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        except sqlite3.DatabaseError as exc:
            raise StateCorruptError("backup inventory is unreadable") from exc
        return tuple(self.get(cast(str, row[0])) for row in rows)


def _backup_manifest_from_record(record: RecordEnvelope) -> BackupManifestRecord:
    """Validate and convert one common-envelope backup manifest record."""

    try:
        if record.record_type != "backup_manifest":
            raise BackupManifestCorruptError("record is not a backup manifest")
        if record.schema_version != 1:
            raise BackupManifestCorruptError("backup manifest schema version is unsupported")
        if record.status not in {"active", "archived"}:
            raise BackupManifestCorruptError("backup manifest lifecycle is unsupported")
        if record.provenance not in {"system-generated", "imported", "restored"}:
            raise BackupManifestCorruptError("backup manifest provenance is unsupported")
        if record.sensitivity == "secret":
            raise BackupManifestCorruptError("backup manifest must not be secret")
        metadata = record.metadata
        backup_id = _required_string(metadata, "backup_id")
        if _validate_uuid("backup ID", backup_id) != record.id:
            raise BackupManifestCorruptError("backup manifest identity does not match envelope")
        backup_kind = _validate_backup_kind(_required_string(metadata, "backup_kind"))
        backup_format_version = _validate_positive_int(
            "backup format version", _required_int(metadata, "backup_format_version")
        )
        workspace_id = _validate_uuid("workspace ID", _required_string(metadata, "workspace_id"))
        schema_version = _validate_positive_int(
            "schema version", _required_int(metadata, "schema_version")
        )
        source_state_revision = _validate_nonnegative_int(
            "source state revision", _required_int(metadata, "source_state_revision")
        )
        created_at = _validate_utc_timestamp(
            _required_string(metadata, "created_at"), "backup creation time"
        )
        verified_at = _validate_utc_timestamp(
            _required_string(metadata, "verified_at"), "backup verification time"
        )
        if _parse_utc(verified_at) < _parse_utc(created_at):
            raise BackupManifestCorruptError("backup verification precedes creation")
        manifest_hash = _validate_digest(
            "manifest hash", _required_string(metadata, "manifest_hash")
        )
        file_name = _validate_file_name(_required_string(metadata, "file_name"))
        file_size_bytes = _validate_nonnegative_int(
            "backup file size", _required_int(metadata, "file_size_bytes")
        )
        file_sha256 = _validate_digest(
            "backup file hash", _required_string(metadata, "file_sha256")
        )
        verification_status_value = _required_string(metadata, "verification_status")
        if verification_status_value not in _ALLOWED_VERIFICATION_STATUSES:
            raise BackupManifestCorruptError("backup verification status is invalid")
        included_categories = _validate_categories(
            "included categories", _required_string_list(metadata, "included_categories")
        )
        excluded_categories = _validate_categories(
            "excluded categories", _required_string_list(metadata, "excluded_categories")
        )
        if set(included_categories) & set(excluded_categories):
            raise BackupManifestCorruptError("backup categories overlap")
        _validate_utc_timestamp(record.created_at, "record creation time")
        _validate_utc_timestamp(record.updated_at, "record update time")
    except BackupManifestCorruptError:
        raise
    except (BackupManifestValidationError, KeyError, TypeError, ValueError) as exc:
        raise BackupManifestCorruptError("backup manifest record is malformed") from exc

    return BackupManifestRecord(
        backup_id=backup_id,
        backup_kind=backup_kind,
        backup_format_version=backup_format_version,
        workspace_id=workspace_id,
        schema_version=schema_version,
        source_state_revision=source_state_revision,
        created_at=created_at,
        verified_at=verified_at,
        manifest_hash=manifest_hash,
        file_name=file_name,
        file_size_bytes=file_size_bytes,
        file_sha256=file_sha256,
        verification_status=cast(VerificationStatus, verification_status_value),
        included_categories=included_categories,
        excluded_categories=excluded_categories,
    )


def _validate_backup_kind(value: object) -> BackupKind:
    if not isinstance(value, str) or value not in _ALLOWED_BACKUP_KINDS:
        raise BackupManifestValidationError("backup kind is invalid")
    return cast(BackupKind, value)


def _validate_uuid(name: str, value: object) -> str:
    if not isinstance(value, str):
        raise BackupManifestValidationError(f"{name} must be text")
    try:
        return str(UUID(value))
    except ValueError as exc:
        raise BackupManifestValidationError(f"{name} is invalid") from exc


def _validate_positive_int(name: str, value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise BackupManifestValidationError(f"{name} must be positive")
    return value


def _validate_nonnegative_int(name: str, value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise BackupManifestValidationError(f"{name} must be non-negative")
    return value


def _validate_utc_timestamp(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise BackupManifestValidationError(f"{name} must be UTC")
    try:
        parsed = _parse_utc(value)
    except ValueError as exc:
        raise BackupManifestValidationError(f"{name} is invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        raise BackupManifestValidationError(f"{name} must be UTC")
    return value


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value[:-1] + "+00:00")


def _validate_digest(name: str, value: object) -> str:
    if not isinstance(value, str) or not _DIGEST_PATTERN.fullmatch(value):
        raise BackupManifestValidationError(f"{name} is invalid")
    return value


def _validate_file_name(value: object) -> str:
    if not isinstance(value, str):
        raise BackupManifestValidationError("backup file name must be text")
    if (
        not value
        or len(value) > MAX_FILE_NAME_LENGTH
        or value in {".", ".."}
        or "/" in value
        or "\\" in value
        or any(ord(character) < 32 for character in value)
    ):
        raise BackupManifestValidationError("backup file name is invalid")
    return value


def _validate_categories(name: str, value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise BackupManifestValidationError(f"{name} must be a list")
    if len(value) > MAX_CATEGORY_COUNT:
        raise BackupManifestValidationError(f"{name} has too many values")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str) or not _CATEGORY_PATTERN.fullmatch(item):
            raise BackupManifestValidationError(f"{name} contains an invalid value")
        if item in result:
            raise BackupManifestValidationError(f"{name} contains a duplicate value")
        result.append(item)
    return tuple(result)


def _required_string(metadata: dict[str, object], key: str) -> str:
    value = metadata.get(key)
    if not isinstance(value, str) or not value:
        raise BackupManifestCorruptError(f"backup manifest {key} is invalid")
    return value


def _required_int(metadata: dict[str, object], key: str) -> int:
    value = metadata.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise BackupManifestCorruptError(f"backup manifest {key} is invalid")
    return value


def _required_string_list(metadata: dict[str, object], key: str) -> tuple[str, ...]:
    value = metadata.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise BackupManifestCorruptError(f"backup manifest {key} is invalid")
    return tuple(cast(list[str], value))
