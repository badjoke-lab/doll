"""SQLite connection and bootstrap metadata operations."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import cast

from doll.state import (
    CURRENT_SCHEMA_VERSION,
    STATE_DATABASE_NAME,
    FutureSchemaVersionError,
    Migration,
    StateCorruptError,
    _utc_now,
)
from doll.workspace import InitializedWorkspace


def _database_path(workspace: InitializedWorkspace) -> Path:
    return workspace.root / "state" / STATE_DATABASE_NAME


def _configure_connection(connection: sqlite3.Connection, *, read_only: bool) -> None:
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 5000")
    if read_only:
        connection.execute("PRAGMA query_only = ON")


def _configure_write_journal(connection: sqlite3.Connection) -> None:
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA synchronous = FULL")


def _connect(path: Path, *, read_only: bool) -> sqlite3.Connection:
    if read_only:
        connection = sqlite3.connect(
            f"{path.resolve().as_uri()}?mode=ro",
            uri=True,
            isolation_level=None,
        )
    else:
        connection = sqlite3.connect(path, isolation_level=None)
    _configure_connection(connection, read_only=read_only)
    return connection


def _bootstrap(connection: sqlite3.Connection, workspace_id: str) -> None:
    now = _utc_now()
    connection.execute("BEGIN IMMEDIATE")
    try:
        connection.execute(
            """
            CREATE TABLE schema_metadata (
                singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                workspace_id TEXT NOT NULL,
                schema_version INTEGER NOT NULL CHECK (schema_version >= 0),
                state_revision INTEGER NOT NULL CHECK (state_revision >= 0),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE migration_history (
                migration_run_id TEXT PRIMARY KEY,
                migration_id TEXT NOT NULL,
                from_schema_version INTEGER NOT NULL,
                to_schema_version INTEGER NOT NULL,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                status TEXT NOT NULL CHECK (status IN ('running', 'completed', 'failed')),
                error_class TEXT
            )
            """
        )
        connection.execute(
            """
            INSERT INTO schema_metadata (
                singleton,
                workspace_id,
                schema_version,
                state_revision,
                created_at,
                updated_at
            ) VALUES (1, ?, 0, 0, ?, ?)
            """,
            (workspace_id, now, now),
        )
        connection.execute("COMMIT")
    except BaseException:
        connection.execute("ROLLBACK")
        raise


def _metadata_row(connection: sqlite3.Connection) -> sqlite3.Row:
    try:
        row = connection.execute(
            """
            SELECT workspace_id, schema_version, state_revision
            FROM schema_metadata
            WHERE singleton = 1
            """
        ).fetchone()
    except sqlite3.DatabaseError as exc:
        raise StateCorruptError("state database metadata is unreadable") from exc
    if row is None:
        raise StateCorruptError("state database metadata is missing")
    return cast(sqlite3.Row, row)


def _validate_database_identity(
    connection: sqlite3.Connection,
    workspace: InitializedWorkspace,
) -> tuple[int, int]:
    row = _metadata_row(connection)
    workspace_id = cast(str, row["workspace_id"])
    schema_version = cast(int, row["schema_version"])
    state_revision = cast(int, row["state_revision"])

    if workspace_id != str(workspace.record.workspace_id):
        raise StateCorruptError("state database belongs to a different workspace")
    if schema_version > CURRENT_SCHEMA_VERSION:
        raise FutureSchemaVersionError(
            f"state schema version {schema_version} is newer than supported "
            f"version {CURRENT_SCHEMA_VERSION}"
        )
    return schema_version, state_revision


MIGRATION_0001: Migration = Migration(
    migration_id="0001-initial-authoritative-state",
    from_version=0,
    to_version=1,
    statements=(
        """
        CREATE TABLE records (
            id TEXT PRIMARY KEY,
            record_type TEXT NOT NULL,
            schema_version INTEGER NOT NULL CHECK (schema_version >= 1),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            revision INTEGER NOT NULL CHECK (revision >= 1),
            status TEXT NOT NULL CHECK (
                status IN ('active', 'archived', 'superseded', 'deleted', 'invalid')
            ),
            provenance TEXT NOT NULL CHECK (
                provenance IN (
                    'user-created',
                    'user-confirmed',
                    'imported',
                    'model-proposed',
                    'system-generated',
                    'migrated',
                    'restored'
                )
            ),
            sensitivity TEXT NOT NULL CHECK (
                sensitivity IN ('public', 'internal', 'personal', 'sensitive', 'secret')
            ),
            title TEXT,
            metadata_json TEXT NOT NULL DEFAULT '{}'
        )
        """,
        "CREATE INDEX records_type_status_idx ON records(record_type, status)",
        "CREATE INDEX records_updated_at_idx ON records(updated_at)",
    ),
)

MIGRATION_0002: Migration = Migration(
    migration_id="0002-append-oriented-audit-events",
    from_version=1,
    to_version=2,
    statements=(
        """
        CREATE TABLE audit_events (
            sequence INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT NOT NULL UNIQUE,
            operation_id TEXT NOT NULL,
            occurred_at TEXT NOT NULL,
            actor_type TEXT NOT NULL CHECK (
                actor_type IN ('user', 'system', 'model', 'runtime', 'capability', 'migration')
            ),
            actor_id TEXT,
            action TEXT NOT NULL,
            target_type TEXT,
            target_id TEXT,
            result TEXT NOT NULL CHECK (
                result IN ('success', 'denied', 'failed', 'cancelled', 'partial')
            ),
            summary TEXT,
            error_class TEXT,
            metadata_json TEXT NOT NULL DEFAULT '{}'
        )
        """,
        "CREATE INDEX audit_events_operation_idx ON audit_events(operation_id, sequence)",
        "CREATE INDEX audit_events_action_idx ON audit_events(action, sequence)",
        "CREATE INDEX audit_events_actor_idx ON audit_events(actor_type, sequence)",
        "CREATE INDEX audit_events_result_idx ON audit_events(result, sequence)",
        """
        CREATE TRIGGER audit_events_no_update
        BEFORE UPDATE ON audit_events
        BEGIN
            SELECT RAISE(ABORT, 'audit events are append-only');
        END
        """,
        """
        CREATE TRIGGER audit_events_no_delete
        BEFORE DELETE ON audit_events
        BEGIN
            SELECT RAISE(ABORT, 'audit events are append-only');
        END
        """,
    ),
)
