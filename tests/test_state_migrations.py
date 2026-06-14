from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from doll import state, state_db, state_migrations, state_schema, workspace


def initialized_workspace(
    tmp_path: Path,
    name: str = "workspace",
) -> workspace.InitializedWorkspace:
    return workspace.initialize_workspace(tmp_path / name)


def test_failed_migration_rolls_back_and_records_failure(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    failing = (
        state.Migration(
            migration_id="0001-failing",
            from_version=0,
            to_version=1,
            statements=(
                "CREATE TABLE should_rollback (id INTEGER PRIMARY KEY)",
                "THIS IS NOT VALID SQL",
            ),
        ),
    )

    with pytest.raises(state.MigrationError):
        state.initialize_state_repository(initialized.root, migrations=failing)

    database_path = initialized.root / "state" / state.STATE_DATABASE_NAME
    connection = sqlite3.connect(database_path)
    try:
        version = connection.execute(
            "SELECT schema_version FROM schema_metadata WHERE singleton = 1"
        ).fetchone()
        table = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'should_rollback'"
        ).fetchone()
        failed = connection.execute("SELECT status, error_class FROM migration_history").fetchone()
    finally:
        connection.close()

    assert version == (0,)
    assert table is None
    assert failed is not None
    assert failed[0] == "failed"
    assert failed[1] == "OperationalError"

    with state.open_state_repository(initialized.root) as repository:
        assert repository.status().schema_version == state.CURRENT_SCHEMA_VERSION


def test_existing_schema_one_migrates_to_audit_schema(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    database_path = initialized.root / "state" / state.STATE_DATABASE_NAME
    connection = state_db._connect(database_path, read_only=False)
    try:
        state_db._bootstrap(connection, str(initialized.record.workspace_id))
        state_migrations._apply_migration(connection, state_db.MIGRATION_0001)
    finally:
        connection.close()

    with state.open_state_repository(initialized.root) as repository:
        assert repository.status().schema_version == state.CURRENT_SCHEMA_VERSION
        tables = {
            row[0]
            for row in repository.connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        triggers = {
            row[0]
            for row in repository.connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'trigger'"
            ).fetchall()
        }
        history = repository.connection.execute(
            "SELECT migration_id, status FROM migration_history ORDER BY completed_at"
        ).fetchall()

    assert "audit_events" in tables
    assert {"audit_events_no_update", "audit_events_no_delete"} <= triggers
    assert [tuple(row) for row in history] == [
        ("0001-initial-authoritative-state", "completed"),
        ("0002-append-oriented-audit-events", "completed"),
    ]


def test_failed_audit_migration_leaves_schema_one_usable(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    failing = (
        state_db.MIGRATION_0001,
        state.Migration(
            migration_id="0002-failing-audit",
            from_version=1,
            to_version=2,
            statements=(
                "CREATE TABLE should_rollback_audit (id INTEGER PRIMARY KEY)",
                "THIS IS NOT VALID SQL",
            ),
        ),
    )

    with pytest.raises(state.MigrationError):
        state.initialize_state_repository(initialized.root, migrations=failing)

    database_path = initialized.root / "state" / state.STATE_DATABASE_NAME
    connection = sqlite3.connect(database_path)
    try:
        version = connection.execute(
            "SELECT schema_version FROM schema_metadata WHERE singleton = 1"
        ).fetchone()
        rolled_back = connection.execute(
            "SELECT name FROM sqlite_master WHERE name = 'should_rollback_audit'"
        ).fetchone()
        records = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'records'"
        ).fetchone()
    finally:
        connection.close()

    assert version == (1,)
    assert rolled_back is None
    assert records == ("records",)

    with state.open_state_repository(initialized.root) as repository:
        assert repository.status().schema_version == state.CURRENT_SCHEMA_VERSION


def test_private_metadata_and_bootstrap_failure_paths() -> None:
    connection = sqlite3.connect(":memory:", isolation_level=None)
    connection.row_factory = sqlite3.Row
    try:
        with pytest.raises(state.StateCorruptError):
            state_db._metadata_row(connection)

        connection.execute("CREATE TABLE schema_metadata (singleton INTEGER)")
        with pytest.raises(sqlite3.DatabaseError):
            state_db._bootstrap(connection, "workspace")
    finally:
        connection.close()


def test_failed_migration_history_write_rolls_back() -> None:
    connection = sqlite3.connect(":memory:", isolation_level=None)
    try:
        migration = state.Migration("bad", 0, 1, ())
        with pytest.raises(sqlite3.DatabaseError):
            state_migrations._record_failed_migration(
                connection,
                migration,
                "run",
                "2026-01-01T00:00:00Z",
                RuntimeError("boom"),
            )
        assert connection.in_transaction is False
    finally:
        connection.close()


def test_migration_detects_changed_schema_version(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    migration = (
        state.Migration(
            migration_id="0001-race",
            from_version=0,
            to_version=1,
            statements=("UPDATE schema_metadata SET schema_version = 9 WHERE singleton = 1",),
        ),
    )
    with pytest.raises(state.MigrationError):
        state.initialize_state_repository(initialized.root, migrations=migration)


def test_apply_migrations_rejects_future_version(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.initialize_state_repository(initialized.root):
        pass
    database_path = initialized.root / "state" / state.STATE_DATABASE_NAME
    connection = sqlite3.connect(database_path, isolation_level=None)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute(
            "UPDATE schema_metadata SET schema_version = ? WHERE singleton = 1",
            (state.CURRENT_SCHEMA_VERSION + 1,),
        )
        with pytest.raises(state.FutureSchemaVersionError):
            state.apply_migrations(connection)
    finally:
        connection.close()


def test_migration_chain_rejects_leaps_and_duplicate_starts(tmp_path: Path) -> None:
    leap_workspace = initialized_workspace(tmp_path, "leap")
    leap = (
        state.Migration(
            migration_id="0001-leap",
            from_version=0,
            to_version=2,
            statements=(),
        ),
    )
    with pytest.raises(state.StateCorruptError, match="advance exactly one"):
        state.initialize_state_repository(leap_workspace.root, migrations=leap)

    duplicate_workspace = initialized_workspace(tmp_path, "duplicate")
    duplicate = (
        state.Migration("0001-first", 0, 1, ()),
        state.Migration("0001-second", 0, 1, ()),
    )
    with pytest.raises(state.StateCorruptError, match="multiple migrations"):
        state.initialize_state_repository(duplicate_workspace.root, migrations=duplicate)


def test_migration_chain_rejects_duplicate_ids(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    duplicate_ids = (
        state.Migration("duplicate", 0, 1, ()),
        state.Migration("duplicate", 1, 2, ()),
    )
    with pytest.raises(state.StateCorruptError, match="duplicate migration id"):
        state.initialize_state_repository(initialized.root, migrations=duplicate_ids)


def test_workspace_sync_error_is_wrapped(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    initialized = initialized_workspace(tmp_path)

    def fail_sync(root: Path, revision: int) -> workspace.WorkspaceRecord:
        raise workspace.WorkspaceRevisionError("boom")

    monkeypatch.setattr(state_schema, "update_workspace_state_revision", fail_sync)
    with pytest.raises(state.StateRevisionMismatchError):
        state_schema._sync_workspace_revision(initialized, 1)


def test_status_for_bootstrap_schema_zero(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    failing = (
        state.Migration(
            migration_id="0001-failing",
            from_version=0,
            to_version=1,
            statements=("INVALID SQL",),
        ),
    )
    with pytest.raises(state.MigrationError):
        state.initialize_state_repository(initialized.root, migrations=failing)
    database_path = initialized.root / "state" / state.STATE_DATABASE_NAME
    connection = sqlite3.connect(database_path, isolation_level=None)
    connection.row_factory = sqlite3.Row
    repository = state.StateRepository(
        workspace=initialized,
        database_path=database_path,
        connection=connection,
        read_only=False,
    )
    try:
        assert repository.status().schema_version == 0
        assert repository.status().record_count == 0
    finally:
        repository.close()
