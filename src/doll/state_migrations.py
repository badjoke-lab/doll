"""Deterministic SQLite schema migration operations."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from typing import cast
from uuid import uuid4

from doll.state import (
    CURRENT_SCHEMA_VERSION,
    FutureSchemaVersionError,
    Migration,
    MigrationError,
    StateCorruptError,
    _utc_now,
)
from doll.state_db import MIGRATION_0001, MIGRATION_0002, _metadata_row

MIGRATIONS: tuple[Migration, ...] = (MIGRATION_0001, MIGRATION_0002)


def _record_failed_migration(
    connection: sqlite3.Connection,
    migration: Migration,
    migration_run_id: str,
    started_at: str,
    error: BaseException,
) -> None:
    connection.execute("BEGIN IMMEDIATE")
    try:
        connection.execute(
            """
            INSERT INTO migration_history (
                migration_run_id,
                migration_id,
                from_schema_version,
                to_schema_version,
                started_at,
                completed_at,
                status,
                error_class
            ) VALUES (?, ?, ?, ?, ?, ?, 'failed', ?)
            """,
            (
                migration_run_id,
                migration.migration_id,
                migration.from_version,
                migration.to_version,
                started_at,
                _utc_now(),
                type(error).__name__,
            ),
        )
        connection.execute("COMMIT")
    except BaseException:
        connection.execute("ROLLBACK")
        raise


def _apply_migration(connection: sqlite3.Connection, migration: Migration) -> None:
    migration_run_id = str(uuid4())
    started_at = _utc_now()
    connection.execute("BEGIN IMMEDIATE")
    try:
        connection.execute(
            """
            INSERT INTO migration_history (
                migration_run_id,
                migration_id,
                from_schema_version,
                to_schema_version,
                started_at,
                status
            ) VALUES (?, ?, ?, ?, ?, 'running')
            """,
            (
                migration_run_id,
                migration.migration_id,
                migration.from_version,
                migration.to_version,
                started_at,
            ),
        )
        for statement in migration.statements:
            connection.execute(statement)
        completed_at = _utc_now()
        connection.execute(
            """
            UPDATE schema_metadata
            SET schema_version = ?, updated_at = ?
            WHERE singleton = 1 AND schema_version = ?
            """,
            (migration.to_version, completed_at, migration.from_version),
        )
        changes_row = connection.execute("SELECT changes()").fetchone()
        if changes_row is None or cast(int, changes_row[0]) != 1:
            raise StateCorruptError("schema version changed during migration")
        connection.execute(
            """
            UPDATE migration_history
            SET completed_at = ?, status = 'completed'
            WHERE migration_run_id = ?
            """,
            (completed_at, migration_run_id),
        )
        connection.execute("COMMIT")
    except BaseException as exc:
        connection.execute("ROLLBACK")
        _record_failed_migration(
            connection,
            migration,
            migration_run_id,
            started_at,
            exc,
        )
        raise MigrationError(
            f"migration {migration.migration_id} failed and was rolled back"
        ) from exc


def _index_migrations(migrations: Iterable[Migration]) -> dict[int, Migration]:
    by_from_version: dict[int, Migration] = {}
    migration_ids: set[str] = set()
    for migration in migrations:
        if migration.from_version in by_from_version:
            raise StateCorruptError(
                f"multiple migrations start at schema version {migration.from_version}"
            )
        if migration.migration_id in migration_ids:
            raise StateCorruptError(f"duplicate migration id: {migration.migration_id}")
        by_from_version[migration.from_version] = migration
        migration_ids.add(migration.migration_id)
    return by_from_version


def apply_migrations(
    connection: sqlite3.Connection,
    migrations: Iterable[Migration] = MIGRATIONS,
) -> int:
    """Apply ordered pending migrations and return the resulting schema version."""

    by_from_version = _index_migrations(migrations)
    current_version = cast(int, _metadata_row(connection)["schema_version"])
    if current_version > CURRENT_SCHEMA_VERSION:
        raise FutureSchemaVersionError(
            f"state schema version {current_version} is newer than supported "
            f"version {CURRENT_SCHEMA_VERSION}"
        )

    while current_version < CURRENT_SCHEMA_VERSION:
        migration = by_from_version.get(current_version)
        if migration is None:
            raise StateCorruptError(f"no valid migration from schema version {current_version}")
        if migration.to_version != current_version + 1:
            raise StateCorruptError(
                f"migration {migration.migration_id} must advance exactly one schema version"
            )
        if migration.to_version > CURRENT_SCHEMA_VERSION:
            raise StateCorruptError(
                f"migration {migration.migration_id} exceeds supported schema version "
                f"{CURRENT_SCHEMA_VERSION}"
            )
        _apply_migration(connection, migration)
        current_version = migration.to_version

    return current_version
