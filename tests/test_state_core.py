from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from doll import state, workspace


def initialized_workspace(
    tmp_path: Path,
    name: str = "workspace",
) -> workspace.InitializedWorkspace:
    return workspace.initialize_workspace(tmp_path / name)


def test_initialize_and_reopen_state_repository(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    database_path = initialized.root / "state" / state.STATE_DATABASE_NAME

    with state.initialize_state_repository(initialized.root) as repository:
        status = repository.status()
        assert status.schema_version == state.CURRENT_SCHEMA_VERSION
        assert status.state_revision == 0
        assert status.record_count == 0
        assert status.read_only is False
        assert status.workspace_id == str(initialized.record.workspace_id)

    assert database_path.is_file()

    with state.open_state_repository(initialized.root) as repository:
        assert repository.status().schema_version == state.CURRENT_SCHEMA_VERSION

    with pytest.raises(state.StateExistsError):
        state.initialize_state_repository(initialized.root)


def test_state_repository_requires_initialized_workspace_and_database(tmp_path: Path) -> None:
    with pytest.raises(workspace.WorkspaceRecordError):
        state.initialize_state_repository(tmp_path / "missing")

    initialized = initialized_workspace(tmp_path)
    with pytest.raises(state.StateNotInitializedError):
        state.open_state_repository(initialized.root)


def test_read_only_open_does_not_change_workspace_or_database(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.initialize_state_repository(initialized.root):
        pass
    database_path = initialized.root / "state" / state.STATE_DATABASE_NAME
    workspace_path = initialized.root / workspace.WORKSPACE_RECORD_NAME
    before_database = database_path.stat().st_mtime_ns
    before_workspace = workspace_path.stat().st_mtime_ns

    with state.open_state_repository(initialized.root, read_only=True) as repository:
        assert repository.status().record_count == 0

    assert database_path.stat().st_mtime_ns == before_database
    assert workspace_path.stat().st_mtime_ns == before_workspace


def test_future_schema_is_rejected_without_open_side_effect(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.initialize_state_repository(initialized.root):
        pass
    database_path = initialized.root / "state" / state.STATE_DATABASE_NAME
    connection = sqlite3.connect(database_path)
    try:
        connection.execute(
            "UPDATE schema_metadata SET schema_version = ? WHERE singleton = 1",
            (state.CURRENT_SCHEMA_VERSION + 1,),
        )
        connection.commit()
    finally:
        connection.close()
    before = database_path.stat().st_mtime_ns

    with pytest.raises(state.FutureSchemaVersionError):
        state.open_state_repository(initialized.root, read_only=True)
    assert database_path.stat().st_mtime_ns == before

    with pytest.raises(state.FutureSchemaVersionError):
        state.open_state_repository(initialized.root)


def test_database_workspace_identity_mismatch_is_rejected(tmp_path: Path) -> None:
    first = initialized_workspace(tmp_path, "first")
    second = initialized_workspace(tmp_path, "second")
    with state.initialize_state_repository(first.root):
        pass
    source = first.root / "state" / state.STATE_DATABASE_NAME
    destination = second.root / "state" / state.STATE_DATABASE_NAME
    destination.write_bytes(source.read_bytes())

    with pytest.raises(state.StateCorruptError):
        state.open_state_repository(second.root, read_only=True)


def test_workspace_revision_is_repaired_when_database_is_ahead(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.initialize_state_repository(initialized.root) as repository:
        repository.create_record(record_type="x")

    record_path = initialized.root / workspace.WORKSPACE_RECORD_NAME
    payload = json.loads(record_path.read_text(encoding="utf-8"))
    payload["state_revision"] = 0
    record_path.write_text(json.dumps(payload), encoding="utf-8")

    with state.open_state_repository(initialized.root) as repository:
        assert repository.status().state_revision == 1
    assert workspace.load_workspace(initialized.root).record.state_revision == 1


def test_workspace_ahead_of_database_is_rejected(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.initialize_state_repository(initialized.root):
        pass
    workspace.update_workspace_state_revision(initialized.root, 1)

    with pytest.raises(state.StateRevisionMismatchError):
        state.open_state_repository(initialized.root)


def test_missing_migration_and_corrupt_database_are_rejected(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    incomplete = (
        state.Migration(
            migration_id="wrong-start",
            from_version=5,
            to_version=6,
            statements=(),
        ),
    )
    with pytest.raises(state.StateCorruptError):
        state.initialize_state_repository(initialized.root, migrations=incomplete)

    other = initialized_workspace(tmp_path, "corrupt")
    database_path = other.root / "state" / state.STATE_DATABASE_NAME
    database_path.write_text("not a database", encoding="utf-8")
    with pytest.raises(state.StateCorruptError):
        state.open_state_repository(other.root, read_only=True)


def test_unicode_state_path_and_context_manager(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path, "日本語")
    repository = state.initialize_state_repository(initialized.root)
    assert repository.__enter__() is repository
    repository.__exit__(None, None, None)
    with state.open_state_repository(initialized.root, read_only=True) as reopened:
        assert reopened.status().database_path.parent.name == "state"
