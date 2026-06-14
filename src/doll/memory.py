"""Confirmed long-term memory records for authoritative Doll State."""

from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from math import isfinite
from typing import Literal, cast
from uuid import UUID, uuid4

from doll.audit import _serialize_metadata as _serialize_audit_metadata
from doll.audit import _validate_token as _validate_audit_token
from doll.state import (
    ReadOnlyStateError,
    RecordEnvelope,
    RecordProvenance,
    RecordSensitivity,
    RecordStatus,
    StaleRevisionError,
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

MemorySourceType = Literal[
    "user_statement",
    "accepted_suggestion",
    "approved_import",
    "migrated",
    "restored",
]
MemoryMutationActor = Literal["user", "model", "runtime", "capability", "system"]

_ALLOWED_SOURCE_TYPES = frozenset(
    {
        "user_statement",
        "accepted_suggestion",
        "approved_import",
        "migrated",
        "restored",
    }
)
_ALLOWED_MUTATION_ACTORS = frozenset({"user"})
_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
_POSIX_PATH_PATTERN = re.compile(r"(?<![:/\w])/(?:[^/\s]+/)*[^/\s]+")
_WINDOWS_PATH_PATTERN = re.compile(r"(?i)\b[A-Z]:[\\/]")
_SECRET_ASSIGNMENT_PATTERN = re.compile(
    r"(?i)\b(?:password|passwd|secret|api[_ -]?key|access[_ -]?token|"
    r"refresh[_ -]?token|authorization|cookie|private[_ -]?key|"
    r"recovery[_ -]?phrase|seed[_ -]?phrase|mnemonic)\b\s*[:=]\s*\S+"
)

MAX_SUBJECT_LENGTH = 240
MAX_CONTENT_LENGTH = 6000
MAX_IDENTIFIER_LENGTH = 200
MAX_REFERENCE_COUNT = 100
MAX_MEMORY_LIMIT = 200


class ConfirmedMemoryError(StateError):
    """Base class for confirmed-memory failures."""


class MemoryValidationError(ConfirmedMemoryError):
    """Raised when a confirmed memory is invalid."""


class ForbiddenMemoryMutationError(ConfirmedMemoryError):
    """Raised when a non-user path attempts an authoritative memory mutation."""


class MemoryExportError(ConfirmedMemoryError):
    """Raised when a confirmed memory cannot be exported safely."""


class MemoryCorruptError(ConfirmedMemoryError):
    """Raised when a stored confirmed memory is malformed."""


@dataclass(frozen=True, slots=True)
class ConfirmedMemoryInfo:
    record_id: str
    subject: str
    content: str
    source_type: MemorySourceType
    confirmation_state: Literal["confirmed"]
    valid_from: str | None
    valid_until: str | None
    confidence: float
    related_memory_ids: tuple[str, ...]
    contradicts_memory_ids: tuple[str, ...]
    source_reference: str | None
    model_manifest_id: str | None
    runtime_adapter_id: str | None
    session_id: str | None
    origin_operation_id: str | None
    revision: int
    status: RecordStatus
    provenance: RecordProvenance
    sensitivity: RecordSensitivity
    created_at: str
    updated_at: str


@dataclass(slots=True)
class ConfirmedMemoryService:
    repository: StateRepository

    def create(
        self,
        *,
        subject: str,
        content: str,
        source_type: MemorySourceType = "user_statement",
        valid_from: str | None = None,
        valid_until: str | None = None,
        confidence: float = 1.0,
        related_memory_ids: Sequence[str] = (),
        contradicts_memory_ids: Sequence[str] = (),
        source_reference: str | None = None,
        model_manifest_id: str | None = None,
        runtime_adapter_id: str | None = None,
        session_id: str | None = None,
        origin_operation_id: str | None = None,
        operation_id: str | None = None,
        sensitivity: RecordSensitivity = "personal",
        actor_type: MemoryMutationActor = "user",
    ) -> ConfirmedMemoryInfo:
        _require_user_actor(actor_type)
        validated = _validated_memory_values(
            self.repository,
            subject=subject,
            content=content,
            source_type=source_type,
            valid_from=valid_from,
            valid_until=valid_until,
            confidence=confidence,
            related_memory_ids=related_memory_ids,
            contradicts_memory_ids=contradicts_memory_ids,
            source_reference=source_reference,
            model_manifest_id=model_manifest_id,
            runtime_adapter_id=runtime_adapter_id,
            session_id=session_id,
            origin_operation_id=origin_operation_id,
            self_id=None,
        )
        provenance = _provenance_for_source(cast(MemorySourceType, validated["source_type"]))
        record_id = _create_memory_record(
            self.repository,
            title=cast(str, validated["subject"]),
            metadata=validated,
            provenance=provenance,
            sensitivity=sensitivity,
            operation_id=operation_id,
        )
        return self.get(record_id)

    def update(
        self,
        record_id: str,
        *,
        expected_revision: int,
        subject: str,
        content: str,
        source_type: MemorySourceType,
        valid_from: str | None = None,
        valid_until: str | None = None,
        confidence: float = 1.0,
        related_memory_ids: Sequence[str] = (),
        contradicts_memory_ids: Sequence[str] = (),
        source_reference: str | None = None,
        model_manifest_id: str | None = None,
        runtime_adapter_id: str | None = None,
        session_id: str | None = None,
        origin_operation_id: str | None = None,
        operation_id: str | None = None,
        actor_type: MemoryMutationActor = "user",
    ) -> ConfirmedMemoryInfo:
        _require_user_actor(actor_type)
        current_record = _require_memory_record(self.repository, record_id)
        current = _memory_from_record(current_record)
        _require_active(current.status)
        validated = _validated_memory_values(
            self.repository,
            subject=subject,
            content=content,
            source_type=source_type,
            valid_from=valid_from,
            valid_until=valid_until,
            confidence=confidence,
            related_memory_ids=related_memory_ids,
            contradicts_memory_ids=contradicts_memory_ids,
            source_reference=source_reference,
            model_manifest_id=model_manifest_id,
            runtime_adapter_id=runtime_adapter_id,
            session_id=session_id,
            origin_operation_id=origin_operation_id,
            self_id=record_id,
        )
        provenance = _provenance_for_source(cast(MemorySourceType, validated["source_type"]))
        _update_memory_record(
            self.repository,
            current_record=current_record,
            expected_revision=expected_revision,
            title=cast(str, validated["subject"]),
            metadata=validated,
            status="active",
            provenance=provenance,
            operation_id=operation_id,
            action="memory.update",
        )
        return self.get(record_id)

    def archive(
        self,
        record_id: str,
        *,
        expected_revision: int,
        operation_id: str | None = None,
        actor_type: MemoryMutationActor = "user",
    ) -> ConfirmedMemoryInfo:
        _require_user_actor(actor_type)
        current_record = _require_memory_record(self.repository, record_id)
        current = _memory_from_record(current_record)
        _require_active(current.status)
        _update_memory_record(
            self.repository,
            current_record=current_record,
            expected_revision=expected_revision,
            title=current.subject,
            metadata=current_record.metadata,
            status="archived",
            provenance=current.provenance,
            operation_id=operation_id,
            action="memory.archive",
        )
        return self.get(record_id)

    def get(self, record_id: str) -> ConfirmedMemoryInfo:
        return _memory_from_record(_require_memory_record(self.repository, record_id))

    def list(
        self,
        *,
        include_archived: bool = False,
        limit: int = 50,
    ) -> tuple[ConfirmedMemoryInfo, ...]:
        if limit < 1 or limit > MAX_MEMORY_LIMIT:
            raise MemoryValidationError(
                f"memory list limit must be between 1 and {MAX_MEMORY_LIMIT}"
            )
        status_clause = (
            "AND status IN ('active', 'archived')" if include_archived else "AND status = 'active'"
        )
        try:
            rows = self.repository.connection.execute(
                f"""
                SELECT id
                FROM records
                WHERE record_type = 'memory' {status_clause}
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        except sqlite3.DatabaseError as exc:
            raise StateCorruptError("confirmed memories are unreadable") from exc
        return tuple(self.get(cast(str, row[0])) for row in rows)

    def export_json(self, record_id: str) -> str:
        memory = self.get(record_id)
        if memory.sensitivity == "secret":
            raise MemoryExportError("secret confirmed memories are excluded from normal export")
        payload = {
            "export_schema": "doll.confirmed-memory.v1",
            "record": {
                "id": memory.record_id,
                "record_type": "memory",
                "schema_version": 1,
                "created_at": memory.created_at,
                "updated_at": memory.updated_at,
                "revision": memory.revision,
                "status": memory.status,
                "provenance": memory.provenance,
                "sensitivity": memory.sensitivity,
                "title": memory.subject,
                "memory": {
                    "memory_class": "confirmed",
                    "content": memory.content,
                    "subject": memory.subject,
                    "source_type": memory.source_type,
                    "confirmation_state": "confirmed",
                    "valid_from": memory.valid_from,
                    "valid_until": memory.valid_until,
                    "confidence": memory.confidence,
                    "related_memory_ids": list(memory.related_memory_ids),
                    "contradicts_memory_ids": list(memory.contradicts_memory_ids),
                    "source_reference": memory.source_reference,
                    "model_manifest_id": memory.model_manifest_id,
                    "runtime_adapter_id": memory.runtime_adapter_id,
                    "session_id": memory.session_id,
                    "origin_operation_id": memory.origin_operation_id,
                },
            },
        }
        return (
            json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                allow_nan=False,
                separators=(",", ":"),
            )
            + "\n"
        )


def _validated_memory_values(
    repository: StateRepository,
    *,
    subject: str,
    content: str,
    source_type: MemorySourceType,
    valid_from: str | None,
    valid_until: str | None,
    confidence: float,
    related_memory_ids: Sequence[str],
    contradicts_memory_ids: Sequence[str],
    source_reference: str | None,
    model_manifest_id: str | None,
    runtime_adapter_id: str | None,
    session_id: str | None,
    origin_operation_id: str | None,
    self_id: str | None,
) -> dict[str, object]:
    safe_subject = _validate_text("memory subject", subject, MAX_SUBJECT_LENGTH)
    safe_content = _validate_text("memory content", content, MAX_CONTENT_LENGTH)
    safe_source_type = _validate_source_type(source_type)
    safe_valid_from = _validate_optional_utc("memory valid-from", valid_from)
    safe_valid_until = _validate_optional_utc("memory valid-until", valid_until)
    _validate_validity_window(safe_valid_from, safe_valid_until)
    safe_confidence = _validate_confidence(confidence)

    related = _validate_reference_ids("related memory IDs", related_memory_ids)
    contradicts = _validate_reference_ids(
        "contradicting memory IDs",
        contradicts_memory_ids,
    )
    if set(related) & set(contradicts):
        raise MemoryValidationError("one memory ID cannot be both related and contradicting")
    _validate_memory_references(
        repository,
        related + contradicts,
        self_id=self_id,
    )

    safe_source_reference = _validate_optional_identifier(
        "source reference",
        source_reference,
    )
    safe_model_manifest_id = _validate_optional_identifier(
        "model manifest ID",
        model_manifest_id,
    )
    safe_runtime_adapter_id = _validate_optional_identifier(
        "runtime adapter ID",
        runtime_adapter_id,
    )
    safe_session_id = _validate_optional_identifier("session ID", session_id)
    safe_origin_operation_id = _validate_optional_identifier(
        "origin operation ID",
        origin_operation_id,
    )
    if safe_source_type == "accepted_suggestion":
        required = (
            safe_model_manifest_id,
            safe_runtime_adapter_id,
            safe_session_id,
            safe_origin_operation_id,
        )
        if any(value is None for value in required):
            raise MemoryValidationError(
                "accepted suggestions require model, runtime, session, and operation provenance"
            )

    return {
        "memory_class": "confirmed",
        "content": safe_content,
        "subject": safe_subject,
        "source_type": safe_source_type,
        "confirmation_state": "confirmed",
        "valid_from": safe_valid_from,
        "valid_until": safe_valid_until,
        "confidence": safe_confidence,
        "related_memory_ids": list(related),
        "contradicts_memory_ids": list(contradicts),
        "source_reference": safe_source_reference,
        "model_manifest_id": safe_model_manifest_id,
        "runtime_adapter_id": safe_runtime_adapter_id,
        "session_id": safe_session_id,
        "origin_operation_id": safe_origin_operation_id,
    }


def _create_memory_record(
    repository: StateRepository,
    *,
    title: str,
    metadata: dict[str, object],
    provenance: RecordProvenance,
    sensitivity: RecordSensitivity,
    operation_id: str | None,
) -> str:
    if repository.read_only:
        raise ReadOnlyStateError("state repository is open in read-only mode")
    _validate_record_fields(
        record_type="memory",
        schema_version=1,
        status="active",
        provenance=provenance,
        sensitivity=sensitivity,
    )
    safe_operation_id = _validate_operation_id(operation_id)
    record_id = str(uuid4())
    now = _utc_now()
    metadata_json = _serialize_record_metadata(metadata)
    connection = repository.connection

    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            """
            INSERT INTO records (
                id, record_type, schema_version, created_at, updated_at, revision,
                status, provenance, sensitivity, title, metadata_json
            ) VALUES (?, 'memory', 1, ?, ?, 1, 'active', ?, ?, ?, ?)
            """,
            (
                record_id,
                now,
                now,
                provenance,
                sensitivity,
                title,
                metadata_json,
            ),
        )
        _insert_memory_audit(
            repository,
            operation_id=safe_operation_id,
            action="memory.create",
            target_id=record_id,
            metadata=metadata,
            sensitivity=sensitivity,
        )
        state_revision = repository._commit_state_revision()
        connection.execute("COMMIT")
    except sqlite3.DatabaseError as exc:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise StateCorruptError("confirmed memory could not be created") from exc
    except BaseException:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise

    repository._sync_after_commit(state_revision)
    return record_id


def _update_memory_record(
    repository: StateRepository,
    *,
    current_record: RecordEnvelope,
    expected_revision: int,
    title: str,
    metadata: dict[str, object],
    status: RecordStatus,
    provenance: RecordProvenance,
    operation_id: str | None,
    action: str,
) -> None:
    if repository.read_only:
        raise ReadOnlyStateError("state repository is open in read-only mode")
    safe_operation_id = _validate_operation_id(operation_id)
    metadata_json = _serialize_record_metadata(metadata)
    now = _utc_now()
    connection = repository.connection

    try:
        connection.execute("BEGIN IMMEDIATE")
        refreshed = repository.get_record(current_record.id)
        if refreshed.revision != expected_revision:
            raise StaleRevisionError(
                f"record revision is {refreshed.revision}, expected {expected_revision}"
            )
        if refreshed.status != "active":
            raise MemoryValidationError("archived confirmed memory cannot be changed")
        connection.execute(
            """
            UPDATE records
            SET updated_at = ?, revision = revision + 1, status = ?,
                provenance = ?, title = ?, metadata_json = ?
            WHERE id = ? AND revision = ? AND status = 'active'
            """,
            (
                now,
                status,
                provenance,
                title,
                metadata_json,
                current_record.id,
                expected_revision,
            ),
        )
        changed = connection.execute("SELECT changes()").fetchone()
        if changed is None or cast(int, changed[0]) != 1:
            raise StaleRevisionError("record revision changed during update")
        _insert_memory_audit(
            repository,
            operation_id=safe_operation_id,
            action=action,
            target_id=current_record.id,
            metadata=metadata,
            sensitivity=current_record.sensitivity,
        )
        state_revision = repository._commit_state_revision()
        connection.execute("COMMIT")
    except sqlite3.DatabaseError as exc:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise StateCorruptError("confirmed memory could not be updated") from exc
    except BaseException:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise

    repository._sync_after_commit(state_revision)


def _insert_memory_audit(
    repository: StateRepository,
    *,
    operation_id: str,
    action: str,
    target_id: str,
    metadata: dict[str, object],
    sensitivity: RecordSensitivity,
) -> None:
    source_type = metadata.get("source_type")
    if not isinstance(source_type, str):
        raise MemoryValidationError("memory source type is unavailable for audit")
    audit_metadata = {
        "memory_class": "confirmed",
        "source_type": source_type,
        "sensitivity": sensitivity,
        "related_count": len(_metadata_list(metadata, "related_memory_ids")),
        "contradiction_count": len(_metadata_list(metadata, "contradicts_memory_ids")),
        "has_validity_window": (
            metadata.get("valid_from") is not None or metadata.get("valid_until") is not None
        ),
    }
    repository.connection.execute(
        """
        INSERT INTO audit_events (
            event_id, operation_id, occurred_at, actor_type, action,
            target_type, target_id, result, summary, metadata_json
        ) VALUES (?, ?, ?, 'user', ?, 'memory', ?, 'success', ?, ?)
        """,
        (
            str(uuid4()),
            operation_id,
            _utc_now(),
            _validate_audit_token("action", action, 120),
            target_id,
            "Changed confirmed memory record",
            _serialize_audit_metadata(audit_metadata),
        ),
    )


def _require_memory_record(
    repository: StateRepository,
    record_id: str,
) -> RecordEnvelope:
    record = repository.get_record(record_id)
    if record.record_type != "memory":
        raise KeyError(record_id)
    return record


def _memory_from_record(record: RecordEnvelope) -> ConfirmedMemoryInfo:
    try:
        _validate_memory_envelope(record)
        memory_class = _required_string(record.metadata, "memory_class")
        if memory_class != "confirmed":
            raise MemoryValidationError("memory class is not confirmed")
        confirmation_state = _required_string(
            record.metadata,
            "confirmation_state",
        )
        if confirmation_state != "confirmed":
            raise MemoryValidationError("memory confirmation state is invalid")
        subject = _validate_text(
            "memory subject",
            _required_string(record.metadata, "subject"),
            MAX_SUBJECT_LENGTH,
        )
        content = _validate_text(
            "memory content",
            _required_string(record.metadata, "content"),
            MAX_CONTENT_LENGTH,
        )
        if record.title != subject:
            raise MemoryValidationError("memory title and subject are inconsistent")
        source_type = _validate_source_type(_required_string(record.metadata, "source_type"))
        if record.provenance != _provenance_for_source(source_type):
            raise MemoryValidationError("memory provenance is inconsistent")
        valid_from = _validate_optional_utc(
            "memory valid-from",
            _optional_string(record.metadata, "valid_from"),
        )
        valid_until = _validate_optional_utc(
            "memory valid-until",
            _optional_string(record.metadata, "valid_until"),
        )
        _validate_validity_window(valid_from, valid_until)
        confidence = _validate_confidence(record.metadata.get("confidence"))

        related = _metadata_reference_ids(record.metadata, "related_memory_ids")
        contradicts = _metadata_reference_ids(
            record.metadata,
            "contradicts_memory_ids",
        )
        if set(related) & set(contradicts):
            raise MemoryValidationError(
                "memory references overlap between related and contradicting"
            )

        source_reference = _validate_optional_identifier(
            "source reference",
            _optional_string(record.metadata, "source_reference"),
        )
        model_manifest_id = _validate_optional_identifier(
            "model manifest ID",
            _optional_string(record.metadata, "model_manifest_id"),
        )
        runtime_adapter_id = _validate_optional_identifier(
            "runtime adapter ID",
            _optional_string(record.metadata, "runtime_adapter_id"),
        )
        session_id = _validate_optional_identifier(
            "session ID",
            _optional_string(record.metadata, "session_id"),
        )
        origin_operation_id = _validate_optional_identifier(
            "origin operation ID",
            _optional_string(record.metadata, "origin_operation_id"),
        )
        if source_type == "accepted_suggestion":
            if any(
                value is None
                for value in (
                    model_manifest_id,
                    runtime_adapter_id,
                    session_id,
                    origin_operation_id,
                )
            ):
                raise MemoryValidationError("accepted suggestion provenance is incomplete")
    except (
        KeyError,
        MemoryValidationError,
        TypeError,
        ValueError,
    ) as exc:
        raise MemoryCorruptError("confirmed memory record is malformed") from exc

    return ConfirmedMemoryInfo(
        record_id=record.id,
        subject=subject,
        content=content,
        source_type=source_type,
        confirmation_state="confirmed",
        valid_from=valid_from,
        valid_until=valid_until,
        confidence=confidence,
        related_memory_ids=related,
        contradicts_memory_ids=contradicts,
        source_reference=source_reference,
        model_manifest_id=model_manifest_id,
        runtime_adapter_id=runtime_adapter_id,
        session_id=session_id,
        origin_operation_id=origin_operation_id,
        revision=record.revision,
        status=record.status,
        provenance=record.provenance,
        sensitivity=record.sensitivity,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _validate_memory_envelope(record: RecordEnvelope) -> None:
    if record.schema_version != 1:
        raise MemoryValidationError("confirmed memory schema version is unsupported")
    if record.revision < 1:
        raise MemoryValidationError("confirmed memory revision must be positive")
    if record.status not in {"active", "archived"}:
        raise MemoryValidationError("confirmed memory status is unsupported")
    if record.provenance not in {
        "user-confirmed",
        "imported",
        "migrated",
        "restored",
    }:
        raise MemoryValidationError("confirmed memory provenance is unsupported")
    if record.sensitivity not in {
        "public",
        "internal",
        "personal",
        "sensitive",
        "secret",
    }:
        raise MemoryValidationError("confirmed memory sensitivity is unsupported")

    created_at = _validate_optional_utc(
        "memory created-at",
        record.created_at,
    )
    updated_at = _validate_optional_utc(
        "memory updated-at",
        record.updated_at,
    )
    if created_at is None or updated_at is None:
        raise MemoryValidationError("confirmed memory timestamps are missing")
    created = datetime.fromisoformat(created_at[:-1] + "+00:00")
    updated = datetime.fromisoformat(updated_at[:-1] + "+00:00")
    if updated < created:
        raise MemoryValidationError("confirmed memory updated-at precedes created-at")


def _validate_text(name: str, value: str, maximum: int) -> str:
    if not isinstance(value, str):
        raise MemoryValidationError(f"{name} must be text")
    normalized = "\n".join(line.rstrip() for line in value.strip().splitlines())
    if not normalized or len(normalized) > maximum:
        raise MemoryValidationError(f"{name} is empty or too long")
    if any(ord(character) < 32 and character not in {"\n", "\t"} for character in normalized):
        raise MemoryValidationError(f"{name} contains control characters")
    _reject_absolute_path(normalized)
    return normalized


def _validate_source_type(value: str) -> MemorySourceType:
    if value not in _ALLOWED_SOURCE_TYPES:
        raise MemoryValidationError(f"invalid memory source type: {value}")
    return cast(MemorySourceType, value)


def _provenance_for_source(
    source_type: MemorySourceType,
) -> RecordProvenance:
    mapping: dict[MemorySourceType, RecordProvenance] = {
        "user_statement": "user-confirmed",
        "accepted_suggestion": "user-confirmed",
        "approved_import": "imported",
        "migrated": "migrated",
        "restored": "restored",
    }
    return mapping[source_type]


def _validate_optional_utc(
    name: str,
    value: str | None,
) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.endswith("Z"):
        raise MemoryValidationError(f"{name} must be UTC and end in Z")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise MemoryValidationError(f"{name} is not a valid timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        raise MemoryValidationError(f"{name} must be UTC")
    return value


def _validate_validity_window(
    valid_from: str | None,
    valid_until: str | None,
) -> None:
    if valid_from is None or valid_until is None:
        return
    start = datetime.fromisoformat(valid_from[:-1] + "+00:00")
    end = datetime.fromisoformat(valid_until[:-1] + "+00:00")
    if end <= start:
        raise MemoryValidationError("memory valid-until must be later than valid-from")


def _validate_confidence(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MemoryValidationError("memory confidence must be a number")
    normalized = float(value)
    if not isfinite(normalized) or normalized < 0.0 or normalized > 1.0:
        raise MemoryValidationError("memory confidence must be between 0 and 1")
    return normalized


def _validate_reference_ids(
    name: str,
    values: Sequence[str],
) -> tuple[str, ...]:
    if isinstance(values, str):
        raise MemoryValidationError(f"{name} must be a sequence")
    if len(values) > MAX_REFERENCE_COUNT:
        raise MemoryValidationError(f"{name} exceeds {MAX_REFERENCE_COUNT} entries")
    normalized: list[str] = []
    for value in values:
        if not isinstance(value, str):
            raise MemoryValidationError(f"{name} must contain text IDs")
        try:
            canonical = str(UUID(value))
        except ValueError as exc:
            raise MemoryValidationError(f"{name} contains an invalid record ID") from exc
        if canonical in normalized:
            raise MemoryValidationError(f"{name} contains duplicate IDs")
        normalized.append(canonical)
    return tuple(normalized)


def _validate_memory_references(
    repository: StateRepository,
    references: Sequence[str],
    *,
    self_id: str | None,
) -> None:
    for reference in references:
        if self_id is not None and reference == self_id:
            raise MemoryValidationError("confirmed memory cannot reference itself")
        try:
            record = repository.get_record(reference)
        except KeyError as exc:
            raise MemoryValidationError("memory reference does not exist") from exc
        if record.record_type != "memory":
            raise MemoryValidationError("memory reference points to another record type")
        _memory_from_record(record)


def _validate_optional_identifier(
    name: str,
    value: str | None,
) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise MemoryValidationError(f"{name} must be text")
    normalized = value.strip()
    if not normalized or len(normalized) > MAX_IDENTIFIER_LENGTH:
        raise MemoryValidationError(f"{name} is empty or too long")
    if not _TOKEN_PATTERN.fullmatch(normalized):
        raise MemoryValidationError(f"{name} contains unsupported characters")
    return normalized


def _validate_operation_id(value: str | None) -> str:
    return _validate_audit_token(
        "operation ID",
        value or str(uuid4()),
        MAX_IDENTIFIER_LENGTH,
    )


def _require_user_actor(actor_type: MemoryMutationActor) -> None:
    if actor_type not in _ALLOWED_MUTATION_ACTORS:
        raise ForbiddenMemoryMutationError(
            "confirmed memory mutation requires an explicit user-controlled actor"
        )


def _require_active(status: RecordStatus) -> None:
    if status != "active":
        raise MemoryValidationError("archived confirmed memory cannot be changed")


def _reject_absolute_path(value: str) -> None:
    if "file://" in value or _POSIX_PATH_PATTERN.search(value):
        raise MemoryValidationError("confirmed memory must not contain an absolute local path")
    if _WINDOWS_PATH_PATTERN.search(value):
        raise MemoryValidationError("confirmed memory must not contain an absolute local path")


def _required_string(
    metadata: dict[str, object],
    key: str,
) -> str:
    value = metadata.get(key)
    if not isinstance(value, str) or not value:
        raise MemoryValidationError(f"{key} is missing or invalid")
    return value


def _optional_string(
    metadata: dict[str, object],
    key: str,
) -> str | None:
    value = metadata.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise MemoryValidationError(f"{key} is invalid")
    return value


def _metadata_reference_ids(
    metadata: dict[str, object],
    key: str,
) -> tuple[str, ...]:
    value = metadata.get(key)
    if not isinstance(value, list):
        raise MemoryValidationError(f"{key} must be a list")
    return _validate_reference_ids(key, cast(list[str], value))


def _metadata_list(
    metadata: dict[str, object],
    key: str,
) -> list[object]:
    value = metadata.get(key)
    if not isinstance(value, list):
        raise MemoryValidationError(f"{key} must be a list")
    return value
