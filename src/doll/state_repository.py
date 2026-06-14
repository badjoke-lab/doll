"""Common record envelope repository operations."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import cast
from uuid import uuid4

from doll.state import (
    _ALLOWED_PROVENANCE,
    _ALLOWED_SENSITIVITY,
    _ALLOWED_STATUSES,
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
        record_id = str(uuid4())
        now = _utc_now()
        metadata_json = _serialize_metadata(metadata or {})

        self.connection.execute("BEGIN IMMEDIATE")
        try:
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
                    record_id,
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
        return self.get_record(record_id)

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
