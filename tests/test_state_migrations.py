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
        assert repository.status().schema_version == 1


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
