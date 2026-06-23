"""Common record envelope repository operations."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import cast
from uuid import UUID, uuid4

from doll.secret_policy import SecretPolicyError, validate_ordinary_state_record
from doll.state import (
    _ALLOWED_PROVENANCE,
    _ALLOWED_SENSITIVITY,
    _ALLOWED_STATUSES,
    ConversationActorType,
    ConversationEventKind,
    ConversationEventRecord,
    ConversationOriginClass,
    ConversationRecord,
    ConversationValidationError,
    ReadOnlyStateError,
    RecordEnvelope,
    RecordProvenance,
    RecordSensitivity,
    RecordStatus,
    RecordValidationError,
    StaleRevisionError,
    StateCorruptError,
    StateStatus,
    _utc_now,
)
from doll.state_db import _metadata_row
from doll.workspace import InitializedWorkspace, load_workspace, update_workspace_state_revision

_CONVERSATION_RECORD_TYPE = "conversation"
_CONVERSATION_EVENT_RECORD_TYPE = "conversation_event"
_CONVERSATION_SCHEMA_VERSION = 1
_MAX_CONVERSATION_LIST_LIMIT = 500
_CONVERSATION_METADATA_KEYS = frozenset({"source_environment_id", "source_conversation_id"})
_CONVERSATION_EVENT_METADATA_KEYS = frozenset(
    {
        "conversation_id",
        "event_kind",
        "actor_type",
        "origin_class",
        "parent_event_ids",
        "sequence_hint",
        "content_reference",
        "occurred_at",
        "source_event_kind",
        "source_environment_id",
        "source_object_id",
        "provider_id",
        "application_id",
        "interface_id",
        "model_manifest_id",
        "runtime_adapter_id",
        "operation_id",
        "extensions",
    }
)


@dataclass(slots=True)
class StateRepository:
    """Open SQLite state repository bound to one workspace."""

    workspace: InitializedWorkspace
    database_path: Path
    connection: sqlite3.Connection
    read_only: bool

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> StateRepository:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def status(self) -> StateStatus:
        row = _metadata_row(self.connection)
        schema_version = cast(int, row["schema_version"])
        if schema_version == 0:
            record_count = 0
        else:
            record_count_row = self.connection.execute("SELECT COUNT(*) FROM records").fetchone()
            if record_count_row is None:  # pragma: no cover - SQLite always returns one row.
                raise StateCorruptError("record count could not be read")
            record_count = cast(int, record_count_row[0])
        return StateStatus(
            workspace_id=cast(str, row["workspace_id"]),
            schema_version=schema_version,
            state_revision=cast(int, row["state_revision"]),
            record_count=record_count,
            read_only=self.read_only,
            database_path=self.database_path,
        )

    def _require_write(self) -> None:
        if self.read_only:
            raise ReadOnlyStateError("state repository is open in read-only mode")

    def _commit_state_revision(self) -> int:
        self.connection.execute(
            """
            UPDATE schema_metadata
            SET state_revision = state_revision + 1, updated_at = ?
            WHERE singleton = 1
            """,
            (_utc_now(),),
        )
        row = self.connection.execute(
            "SELECT state_revision FROM schema_metadata WHERE singleton = 1"
        ).fetchone()
        if row is None:
            raise StateCorruptError("state revision metadata is missing")
        return cast(int, row[0])

    def _sync_after_commit(self, revision: int) -> None:
        update_workspace_state_revision(self.workspace.root, revision)
        self.workspace = load_workspace(self.workspace.root)

    def create_record(
        self,
        *,
        record_type: str,
        schema_version: int = 1,
        status: RecordStatus = "active",
        provenance: RecordProvenance = "user-created",
        sensitivity: RecordSensitivity = "personal",
        title: str | None = None,
        metadata: dict[str, object] | None = None,
        record_id: str | None = None,
    ) -> RecordEnvelope:
        """Create one authoritative record and advance the workspace state revision."""

        self._require_write()
        _validate_record_fields(
            record_type=record_type,
            schema_version=schema_version,
            status=status,
            provenance=provenance,
            sensitivity=sensitivity,
        )
        metadata_value = metadata or {}
        _validate_secret_boundary(
            record_type=record_type,
            sensitivity=sensitivity,
            metadata=metadata_value,
        )
        canonical_record_id = _validate_record_id(record_id) if record_id else str(uuid4())
        now = _utc_now()
        metadata_json = _serialize_metadata(metadata_value)

        self.connection.execute("BEGIN IMMEDIATE")
        try:
            duplicate = self.connection.execute(
                "SELECT 1 FROM records WHERE id = ?",
                (canonical_record_id,),
            ).fetchone()
            if duplicate is not None:
                raise RecordValidationError("record identifier already exists")
            self.connection.execute(
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
                ) VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?)
                """,
                (
                    canonical_record_id,
                    record_type,
                    schema_version,
                    now,
                    now,
                    status,
                    provenance,
                    sensitivity,
                    title,
                    metadata_json,
                ),
            )
            state_revision = self._commit_state_revision()
            self.connection.execute("COMMIT")
        except BaseException:
            self.connection.execute("ROLLBACK")
            raise

        self._sync_after_commit(state_revision)
        return self.get_record(canonical_record_id)

    def get_record(self, record_id: str) -> RecordEnvelope:
        """Return one common-envelope record."""

        row = self.connection.execute(
            """
            SELECT
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
            FROM records
            WHERE id = ?
            """,
            (record_id,),
        ).fetchone()
        if row is None:
            raise KeyError(record_id)
        return _record_from_row(cast(sqlite3.Row, row))

    def update_record(
        self,
        record_id: str,
        *,
        expected_revision: int,
        status: RecordStatus | None = None,
        title: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> RecordEnvelope:
        """Update mutable envelope fields with optimistic revision checking."""

        self._require_write()
        current = self.get_record(record_id)
        if current.revision != expected_revision:
            raise StaleRevisionError(
                f"record revision is {current.revision}, expected {expected_revision}"
            )
        next_status = status or current.status
        if next_status not in _ALLOWED_STATUSES:
            raise RecordValidationError(f"invalid record status: {next_status}")
        next_title = current.title if title is None else title
        next_metadata = current.metadata if metadata is None else metadata
        if current.record_type == "instruction_origin" and (
            next_title != current.title or next_metadata != current.metadata
        ):
            raise RecordValidationError("instruction-origin title and metadata are immutable")
        _validate_secret_boundary(
            record_type=current.record_type,
            sensitivity=current.sensitivity,
            metadata=next_metadata,
        )
        metadata_json = _serialize_metadata(next_metadata)
        now = _utc_now()

        self.connection.execute("BEGIN IMMEDIATE")
        try:
            self.connection.execute(
                """
                UPDATE records
                SET
                    updated_at = ?,
                    revision = revision + 1,
                    status = ?,
                    title = ?,
                    metadata_json = ?
                WHERE id = ? AND revision = ?
                """,
                (
                    now,
                    next_status,
                    next_title,
                    metadata_json,
                    record_id,
                    expected_revision,
                ),
            )
            changes_row = self.connection.execute("SELECT changes()").fetchone()
            if changes_row is None or cast(int, changes_row[0]) != 1:
                raise StaleRevisionError("record revision changed during update")
            state_revision = self._commit_state_revision()
            self.connection.execute("COMMIT")
        except BaseException:
            self.connection.execute("ROLLBACK")
            raise

        self._sync_after_commit(state_revision)
        return self.get_record(record_id)

    def save_conversation(
        self,
        record: ConversationRecord,
        *,
        provenance: RecordProvenance = "user-created",
        sensitivity: RecordSensitivity = "personal",
    ) -> ConversationRecord:
        """Persist one canonical conversation with its stable identifier."""

        self.create_record(
            record_id=record.conversation_id,
            record_type=_CONVERSATION_RECORD_TYPE,
            schema_version=_CONVERSATION_SCHEMA_VERSION,
            provenance=provenance,
            sensitivity=sensitivity,
            title=record.title,
            metadata=record.canonical_metadata(),
        )
        return self.get_conversation(record.conversation_id)

    def get_conversation(self, conversation_id: str) -> ConversationRecord:
        """Restore one validated canonical conversation."""

        return _conversation_from_envelope(self.get_record(conversation_id))

    def list_conversations(self, *, limit: int = 100) -> tuple[ConversationRecord, ...]:
        """List canonical conversations in deterministic creation order."""

        _validate_conversation_limit(limit)
        rows = self.connection.execute(
            """
            SELECT id
            FROM records
            WHERE record_type = ?
            ORDER BY created_at ASC, id ASC
            LIMIT ?
            """,
            (_CONVERSATION_RECORD_TYPE, limit),
        ).fetchall()
        return tuple(self.get_conversation(cast(str, row[0])) for row in rows)

    def save_conversation_event(
        self,
        record: ConversationEventRecord,
        *,
        provenance: RecordProvenance = "user-created",
        sensitivity: RecordSensitivity = "personal",
    ) -> ConversationEventRecord:
        """Persist one event after validating its conversation graph."""

        self.get_conversation(record.conversation_id)
        self._validate_event_parent_ownership(record)
        self.create_record(
            record_id=record.event_id,
            record_type=_CONVERSATION_EVENT_RECORD_TYPE,
            schema_version=_CONVERSATION_SCHEMA_VERSION,
            provenance=provenance,
            sensitivity=sensitivity,
            metadata=record.canonical_metadata(),
        )
        return self.get_conversation_event(record.event_id)

    def get_conversation_event(self, event_id: str) -> ConversationEventRecord:
        """Restore one event and verify its persisted relationships."""

        event = self._get_conversation_event_without_relationship_check(event_id)
        try:
            self.get_conversation(event.conversation_id)
        except KeyError as exc:
            raise StateCorruptError("persisted event conversation is missing") from exc
        self._validate_persisted_event_parent_ownership(event)
        return event

    def list_conversation_events(
        self,
        conversation_id: str,
        *,
        limit: int = 500,
    ) -> tuple[ConversationEventRecord, ...]:
        """List one conversation's events using a deterministic presentation order."""

        self.get_conversation(conversation_id)
        _validate_conversation_limit(limit)
        rows = self.connection.execute(
            """
            SELECT id
            FROM records
            WHERE record_type = ?
            ORDER BY created_at ASC, id ASC
            """,
            (_CONVERSATION_EVENT_RECORD_TYPE,),
        ).fetchall()
        events = tuple(
            event
            for event in (self.get_conversation_event(cast(str, row[0])) for row in rows)
            if event.conversation_id == conversation_id
        )
        return tuple(sorted(events, key=_conversation_event_order_key)[:limit])

    def _get_conversation_event_without_relationship_check(
        self,
        event_id: str,
    ) -> ConversationEventRecord:
        return _conversation_event_from_envelope(self.get_record(event_id))

    def _validate_event_parent_ownership(
        self,
        record: ConversationEventRecord,
    ) -> None:
        for parent_id in record.parent_event_ids:
            try:
                parent = self.get_conversation_event(parent_id)
            except KeyError as exc:
                raise ConversationValidationError("parent event does not exist") from exc
            if parent.conversation_id != record.conversation_id:
                raise ConversationValidationError(
                    "parent event belongs to a different conversation"
                )

    def _validate_persisted_event_parent_ownership(
        self,
        record: ConversationEventRecord,
    ) -> None:
        for parent_id in record.parent_event_ids:
            try:
                parent = self._get_conversation_event_without_relationship_check(parent_id)
            except KeyError as exc:
                raise StateCorruptError("persisted parent event is missing") from exc
            if parent.conversation_id != record.conversation_id:
                raise StateCorruptError("persisted parent event belongs to another conversation")


def _validate_record_fields(
    *,
    record_type: str,
    schema_version: int,
    status: str,
    provenance: str,
    sensitivity: str,
) -> None:
    if not record_type.strip():
        raise RecordValidationError("record type must not be blank")
    if schema_version < 1:
        raise RecordValidationError("record schema version must be at least 1")
    if status not in _ALLOWED_STATUSES:
        raise RecordValidationError(f"invalid record status: {status}")
    if provenance not in _ALLOWED_PROVENANCE:
        raise RecordValidationError(f"invalid record provenance: {provenance}")
    if sensitivity not in _ALLOWED_SENSITIVITY:
        raise RecordValidationError(f"invalid record sensitivity: {sensitivity}")


def _validate_record_id(value: str) -> str:
    try:
        canonical = str(UUID(value))
    except (ValueError, AttributeError) as exc:
        raise RecordValidationError("record identifier is invalid") from exc
    if canonical != value:
        raise RecordValidationError("record identifier must use canonical UUID text")
    return canonical


def _validate_secret_boundary(
    *,
    record_type: str,
    sensitivity: str,
    metadata: dict[str, object],
) -> None:
    try:
        validate_ordinary_state_record(
            record_type=record_type,
            sensitivity=sensitivity,
            metadata=metadata,
        )
    except SecretPolicyError as exc:
        raise RecordValidationError(str(exc)) from exc


def _serialize_metadata(metadata: dict[str, object]) -> str:
    try:
        return json.dumps(
            metadata,
            ensure_ascii=False,
            sort_keys=True,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise RecordValidationError("record metadata must be JSON-compatible") from exc


def _reject_nonstandard_json(value: str) -> object:
    raise ValueError(f"non-standard JSON constant: {value}")


def _record_from_row(row: sqlite3.Row) -> RecordEnvelope:
    try:
        metadata_value = json.loads(
            cast(str, row["metadata_json"]),
            parse_constant=_reject_nonstandard_json,
        )
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise StateCorruptError("record metadata is not valid JSON") from exc
    if not isinstance(metadata_value, dict):
        raise StateCorruptError("record metadata is not a JSON object")
    metadata = cast(dict[str, object], metadata_value)
    return RecordEnvelope(
        id=cast(str, row["id"]),
        record_type=cast(str, row["record_type"]),
        schema_version=cast(int, row["schema_version"]),
        created_at=cast(str, row["created_at"]),
        updated_at=cast(str, row["updated_at"]),
        revision=cast(int, row["revision"]),
        status=cast(RecordStatus, row["status"]),
        provenance=cast(RecordProvenance, row["provenance"]),
        sensitivity=cast(RecordSensitivity, row["sensitivity"]),
        title=cast(str | None, row["title"]),
        metadata=metadata,
    )


def _conversation_from_envelope(envelope: RecordEnvelope) -> ConversationRecord:
    if (
        envelope.record_type != _CONVERSATION_RECORD_TYPE
        or envelope.schema_version != _CONVERSATION_SCHEMA_VERSION
    ):
        raise StateCorruptError("record is not a supported canonical conversation")
    if frozenset(envelope.metadata) != _CONVERSATION_METADATA_KEYS:
        raise StateCorruptError("canonical conversation metadata shape is invalid")
    try:
        return ConversationRecord(
            conversation_id=envelope.id,
            title=envelope.title,
            source_environment_id=cast(
                str | None,
                envelope.metadata["source_environment_id"],
            ),
            source_conversation_id=cast(
                str | None,
                envelope.metadata["source_conversation_id"],
            ),
        )
    except ConversationValidationError as exc:
        raise StateCorruptError("canonical conversation metadata is invalid") from exc


def _conversation_event_from_envelope(
    envelope: RecordEnvelope,
) -> ConversationEventRecord:
    if (
        envelope.record_type != _CONVERSATION_EVENT_RECORD_TYPE
        or envelope.schema_version != _CONVERSATION_SCHEMA_VERSION
    ):
        raise StateCorruptError("record is not a supported canonical conversation event")
    if frozenset(envelope.metadata) != _CONVERSATION_EVENT_METADATA_KEYS:
        raise StateCorruptError("canonical conversation event metadata shape is invalid")
    parent_value = envelope.metadata["parent_event_ids"]
    if not isinstance(parent_value, list) or not all(
        isinstance(value, str) for value in parent_value
    ):
        raise StateCorruptError("canonical conversation parent metadata is invalid")
    extensions_value = envelope.metadata["extensions"]
    if not isinstance(extensions_value, dict) or not all(
        isinstance(key, str) for key in extensions_value
    ):
        raise StateCorruptError("canonical conversation extensions are invalid")
    try:
        return ConversationEventRecord(
            event_id=envelope.id,
            conversation_id=cast(str, envelope.metadata["conversation_id"]),
            event_kind=cast(
                ConversationEventKind,
                envelope.metadata["event_kind"],
            ),
            actor_type=cast(
                ConversationActorType,
                envelope.metadata["actor_type"],
            ),
            origin_class=cast(
                ConversationOriginClass,
                envelope.metadata["origin_class"],
            ),
            parent_event_ids=tuple(parent_value),
            sequence_hint=cast(int | None, envelope.metadata["sequence_hint"]),
            content_reference=cast(
                str | None,
                envelope.metadata["content_reference"],
            ),
            occurred_at=cast(str | None, envelope.metadata["occurred_at"]),
            source_event_kind=cast(
                str | None,
                envelope.metadata["source_event_kind"],
            ),
            source_environment_id=cast(
                str | None,
                envelope.metadata["source_environment_id"],
            ),
            source_object_id=cast(
                str | None,
                envelope.metadata["source_object_id"],
            ),
            provider_id=cast(str | None, envelope.metadata["provider_id"]),
            application_id=cast(
                str | None,
                envelope.metadata["application_id"],
            ),
            interface_id=cast(str | None, envelope.metadata["interface_id"]),
            model_manifest_id=cast(
                str | None,
                envelope.metadata["model_manifest_id"],
            ),
            runtime_adapter_id=cast(
                str | None,
                envelope.metadata["runtime_adapter_id"],
            ),
            operation_id=cast(str | None, envelope.metadata["operation_id"]),
            extensions=cast(dict[str, object], extensions_value),
        )
    except ConversationValidationError as exc:
        raise StateCorruptError("canonical conversation event metadata is invalid") from exc


def _conversation_event_order_key(
    record: ConversationEventRecord,
) -> tuple[bool, int, str, str]:
    return (
        record.sequence_hint is None,
        record.sequence_hint if record.sequence_hint is not None else 0,
        record.occurred_at or "",
        record.event_id,
    )


def _validate_conversation_limit(value: object) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not 1 <= value <= _MAX_CONVERSATION_LIST_LIMIT
    ):
        raise ConversationValidationError("list limit is invalid")
