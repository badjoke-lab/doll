"""Authoritative managed artifact creation and inspection."""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast
from uuid import uuid4

from doll.audit import _serialize_metadata as _serialize_audit_metadata
from doll.audit import _validate_token as _validate_audit_token
from doll.state import (
    ReadOnlyStateError,
    RecordEnvelope,
    RecordProvenance,
    RecordSensitivity,
    StateCorruptError,
    StateError,
    _utc_now,
)
from doll.state_repository import (
    StateRepository,
    _validate_record_fields,
)
from doll.state_repository import (
    _serialize_metadata as _serialize_record_metadata,
)
from doll.workspace_files import (
    DEFAULT_MAX_ARTIFACT_BYTES,
    PublishedFileCleanupError,
    PublishedWorkspaceFile,
    WorkspaceFileError,
    publish_new_workspace_file,
    validate_managed_path,
    verify_workspace_file,
)

ArtifactCreator = Literal["user", "system", "model", "runtime", "capability"]
_ALLOWED_CREATORS = frozenset({"user", "system", "model", "runtime", "capability"})
_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
_MEDIA_TYPE_PATTERN = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9!#$&^_.+-]*/[A-Za-z0-9][A-Za-z0-9!#$&^_.+-]*$"
)
MAX_TITLE_LENGTH = 240
MAX_ARTIFACT_TYPE_LENGTH = 120
MAX_FORMAT_LENGTH = 80
MAX_LIST_LIMIT = 200


class ArtifactError(RuntimeError):
    """Base class for managed artifact failures."""


class ArtifactValidationError(ArtifactError):
    """Raised when artifact metadata or content arguments are invalid."""


class ArtifactRegistrationError(ArtifactError):
    """Raised when a published file cannot be registered authoritatively."""


class ArtifactRollbackError(ArtifactError):
    """Raised when failed registration cannot remove its newly published file."""


class ArtifactIntegrityError(ArtifactError):
    """Raised when a managed file does not match its authoritative record."""


class ArtifactCorruptError(ArtifactError):
    """Raised when an artifact record is malformed or inconsistent."""


@dataclass(frozen=True, slots=True)
class ArtifactInfo:
    """Portable authoritative metadata for one managed artifact."""

    artifact_id: str
    title: str
    artifact_type: str
    managed_path: str
    content_hash: str
    size_bytes: int
    created_by: ArtifactCreator
    operation_id: str
    created_at: str
    sensitivity: RecordSensitivity
    format: str | None
    media_type: str | None


@dataclass(frozen=True, slots=True)
class ArtifactVerification:
    """Successful verification result for one managed artifact."""

    artifact: ArtifactInfo
    actual_hash: str
    actual_size_bytes: int


@dataclass(slots=True)
class WorkspaceFileService:
    """Create and inspect authoritative files inside workspace artifacts/."""

    repository: StateRepository
    maximum_bytes: int = DEFAULT_MAX_ARTIFACT_BYTES

    def __post_init__(self) -> None:
        if self.maximum_bytes < 1 or self.maximum_bytes > DEFAULT_MAX_ARTIFACT_BYTES:
            raise ArtifactValidationError("workspace file service size limit is unsupported")

    @property
    def artifacts_root(self) -> Path:
        return self.repository.workspace.root / "artifacts"

    def create_bytes(
        self,
        *,
        managed_path: str,
        content: bytes,
        title: str,
        artifact_type: str,
        operation_id: str | None = None,
        created_by: ArtifactCreator = "user",
        sensitivity: RecordSensitivity = "personal",
        format: str | None = None,
        media_type: str | None = None,
        max_bytes: int | None = None,
    ) -> ArtifactInfo:
        """Atomically create, hash, index, and audit one new artifact."""

        if self.repository.read_only:
            raise ReadOnlyStateError("state repository is open in read-only mode")
        if not isinstance(content, bytes):
            raise ArtifactValidationError("artifact content must be bytes")

        safe_path = validate_managed_path(managed_path).as_posix()
        safe_title = _validate_title(title)
        safe_type = _validate_identifier("artifact type", artifact_type, MAX_ARTIFACT_TYPE_LENGTH)
        safe_operation_id = _validate_audit_token(
            "operation ID",
            operation_id or str(uuid4()),
            200,
        )
        if created_by not in _ALLOWED_CREATORS:
            raise ArtifactValidationError(f"invalid artifact creator: {created_by}")
        safe_format = (
            _validate_identifier("artifact format", format, MAX_FORMAT_LENGTH)
            if format is not None
            else None
        )
        safe_media_type = _validate_media_type(media_type)
        accepted_limit = self.maximum_bytes if max_bytes is None else max_bytes
        if accepted_limit < 1 or accepted_limit > self.maximum_bytes:
            raise ArtifactValidationError("artifact size limit exceeds the service boundary")

        provenance = _provenance_for_creator(created_by)
        _validate_record_fields(
            record_type="artifact",
            schema_version=1,
            status="active",
            provenance=provenance,
            sensitivity=sensitivity,
        )

        published = publish_new_workspace_file(
            self.artifacts_root,
            safe_path,
            content,
            max_bytes=accepted_limit,
        )
        artifact_id = str(uuid4())
        try:
            state_revision = self._register(
                artifact_id=artifact_id,
                title=safe_title,
                artifact_type=safe_type,
                published=published,
                operation_id=safe_operation_id,
                created_by=created_by,
                provenance=provenance,
                sensitivity=sensitivity,
                format=safe_format,
                media_type=safe_media_type,
            )
        except BaseException as exc:
            try:
                published.cleanup()
            except PublishedFileCleanupError as cleanup_exc:
                raise ArtifactRollbackError(
                    "artifact registration failed and published-file cleanup also failed"
                ) from cleanup_exc
            if isinstance(exc, (ArtifactError, WorkspaceFileError, ReadOnlyStateError)):
                raise
            raise ArtifactRegistrationError(
                "artifact could not be registered authoritatively"
            ) from exc

        published.close()
        self.repository._sync_after_commit(state_revision)
        return self.get(artifact_id)

    def create_text(
        self,
        *,
        managed_path: str,
        text: str,
        title: str,
        artifact_type: str = "text",
        operation_id: str | None = None,
        created_by: ArtifactCreator = "user",
        sensitivity: RecordSensitivity = "personal",
        format: str | None = "txt",
        media_type: str | None = "text/plain",
        max_bytes: int | None = None,
    ) -> ArtifactInfo:
        """Create one UTF-8 artifact without platform-dependent encoding."""

        if not isinstance(text, str):
            raise ArtifactValidationError("artifact text must be Unicode text")
        return self.create_bytes(
            managed_path=managed_path,
            content=text.encode("utf-8"),
            title=title,
            artifact_type=artifact_type,
            operation_id=operation_id,
            created_by=created_by,
            sensitivity=sensitivity,
            format=format,
            media_type=media_type,
            max_bytes=max_bytes,
        )

    def get(self, artifact_id: str) -> ArtifactInfo:
        """Inspect one artifact record without reading its file contents."""

        record = self.repository.get_record(artifact_id)
        if record.record_type != "artifact":
            raise KeyError(artifact_id)
        return _artifact_from_record(record)

    def list(self, *, limit: int = 50) -> tuple[ArtifactInfo, ...]:
        """List newest active artifact records."""

        if limit < 1 or limit > MAX_LIST_LIMIT:
            raise ArtifactValidationError(
                f"artifact list limit must be between 1 and {MAX_LIST_LIMIT}"
            )
        try:
            rows = self.repository.connection.execute(
                """
                SELECT id
                FROM records
                WHERE record_type = 'artifact' AND status = 'active'
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        except sqlite3.DatabaseError as exc:
            raise StateCorruptError("artifact index is unreadable") from exc
        return tuple(self.get(cast(str, row[0])) for row in rows)

    def verify(self, artifact_id: str) -> ArtifactVerification:
        """Verify the managed file against authoritative size and SHA-256 metadata."""

        artifact = self.get(artifact_id)
        try:
            digest = verify_workspace_file(
                self.artifacts_root,
                artifact.managed_path,
                max_bytes=self.maximum_bytes,
            )
        except WorkspaceFileError as exc:
            raise ArtifactIntegrityError("managed artifact could not be verified") from exc
        if digest.content_hash != artifact.content_hash or digest.size_bytes != artifact.size_bytes:
            raise ArtifactIntegrityError("managed artifact does not match its record")
        return ArtifactVerification(
            artifact=artifact,
            actual_hash=digest.content_hash,
            actual_size_bytes=digest.size_bytes,
        )

    def _register(
        self,
        *,
        artifact_id: str,
        title: str,
        artifact_type: str,
        published: PublishedWorkspaceFile,
        operation_id: str,
        created_by: ArtifactCreator,
        provenance: RecordProvenance,
        sensitivity: RecordSensitivity,
        format: str | None,
        media_type: str | None,
    ) -> int:
        metadata: dict[str, object] = {
            "artifact_type": artifact_type,
            "managed_path": published.managed_path,
            "content_hash": published.content_hash,
            "size_bytes": published.size_bytes,
            "created_by": created_by,
            "operation_id": operation_id,
        }
        if format is not None:
            metadata["format"] = format
        if media_type is not None:
            metadata["media_type"] = media_type
        metadata_json = _serialize_record_metadata(metadata)
        audit_metadata_json = _serialize_audit_metadata(
            {
                "content_hash": published.content_hash,
                "size_bytes": published.size_bytes,
            }
        )
        now = _utc_now()
        event_id = str(uuid4())
        connection = self.repository.connection

        connection.execute("BEGIN IMMEDIATE")
        try:
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
                ) VALUES (?, 'artifact', 1, ?, ?, 1, 'active', ?, ?, ?, ?)
                """,
                (
                    artifact_id,
                    now,
                    now,
                    provenance,
                    sensitivity,
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
                ) VALUES (?, ?, ?, ?, 'artifact.create', 'artifact', ?, 'success', ?, ?)
                """,
                (
                    event_id,
                    operation_id,
                    now,
                    created_by,
                    artifact_id,
                    "Created managed artifact",
                    audit_metadata_json,
                ),
            )
            state_revision = self.repository._commit_state_revision()
            connection.execute("COMMIT")
        except BaseException:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise

        return state_revision


def _validate_title(value: str) -> str:
    if not isinstance(value, str):
        raise ArtifactValidationError("artifact title must be text")
    normalized = " ".join(value.split())
    if not normalized or len(normalized) > MAX_TITLE_LENGTH:
        raise ArtifactValidationError("artifact title is empty or too long")
    if any(ord(character) < 32 for character in normalized):
        raise ArtifactValidationError("artifact title contains control characters")
    return normalized


def _validate_identifier(name: str, value: str, maximum: int) -> str:
    if not isinstance(value, str):
        raise ArtifactValidationError(f"{name} must be text")
    normalized = value.strip()
    if not normalized or len(normalized) > maximum:
        raise ArtifactValidationError(f"{name} is empty or too long")
    if not _IDENTIFIER_PATTERN.fullmatch(normalized):
        raise ArtifactValidationError(f"{name} contains unsupported characters")
    return normalized


def _validate_media_type(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if len(normalized) > 120 or not _MEDIA_TYPE_PATTERN.fullmatch(normalized):
        raise ArtifactValidationError("artifact media type is invalid")
    return normalized


def _provenance_for_creator(creator: ArtifactCreator) -> RecordProvenance:
    if creator == "user":
        return "user-created"
    if creator == "model":
        return "model-proposed"
    return "system-generated"


def _artifact_from_record(record: RecordEnvelope) -> ArtifactInfo:
    try:
        metadata = record.metadata
        artifact_type = _validate_identifier(
            "artifact type",
            _required_string(metadata, "artifact_type"),
            MAX_ARTIFACT_TYPE_LENGTH,
        )
        managed_path = validate_managed_path(_required_string(metadata, "managed_path")).as_posix()
        content_hash = _required_string(metadata, "content_hash")
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", content_hash):
            raise ArtifactCorruptError("artifact content hash is invalid")
        size_bytes = metadata["size_bytes"]
        if not isinstance(size_bytes, int) or isinstance(size_bytes, bool) or size_bytes < 0:
            raise ArtifactCorruptError("artifact size is invalid")
        created_by_value = _required_string(metadata, "created_by")
        if created_by_value not in _ALLOWED_CREATORS:
            raise ArtifactCorruptError("artifact creator is invalid")
        operation_id = _required_string(metadata, "operation_id")
        _validate_audit_token("operation ID", operation_id, 200)
        format_raw = _optional_string(metadata, "format")
        format_value = (
            _validate_identifier("artifact format", format_raw, MAX_FORMAT_LENGTH)
            if format_raw is not None
            else None
        )
        media_type = _validate_media_type(_optional_string(metadata, "media_type"))
        if record.title is None:
            raise ArtifactCorruptError("artifact title is missing")
        title = _validate_title(record.title)
    except ArtifactCorruptError:
        raise
    except (
        ArtifactValidationError,
        WorkspaceFileError,
        StateError,
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        raise ArtifactCorruptError("artifact record contains invalid metadata") from exc

    return ArtifactInfo(
        artifact_id=record.id,
        title=title,
        artifact_type=artifact_type,
        managed_path=managed_path,
        content_hash=content_hash,
        size_bytes=size_bytes,
        created_by=cast(ArtifactCreator, created_by_value),
        operation_id=operation_id,
        created_at=record.created_at,
        sensitivity=record.sensitivity,
        format=format_value,
        media_type=media_type,
    )


def _required_string(metadata: dict[str, object], key: str) -> str:
    value = metadata.get(key)
    if not isinstance(value, str) or not value:
        raise ArtifactCorruptError(f"artifact {key} is invalid")
    return value


def _optional_string(metadata: dict[str, object], key: str) -> str | None:
    value = metadata.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ArtifactCorruptError(f"artifact {key} is invalid")
    return value
