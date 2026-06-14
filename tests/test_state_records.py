from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from doll import state, workspace


def initialized_workspace(
    tmp_path: Path,
    name: str = "workspace",
) -> workspace.InitializedWorkspace:
    return workspace.initialize_workspace(tmp_path / name)


def test_create_and_update_record_advance_revisions(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.initialize_state_repository(initialized.root) as repository:
        created = repository.create_record(
            record_type="test-record",
            title="Initial",
            metadata={"language": "日本語"},
        )
        assert created.revision == 1
        assert created.status == "active"
        assert created.provenance == "user-created"
        assert created.sensitivity == "personal"
        assert created.metadata == {"language": "日本語"}
        assert repository.status().state_revision == 1
        assert workspace.load_workspace(initialized.root).record.state_revision == 1

        updated = repository.update_record(
            created.id,
            expected_revision=1,
            status="archived",
            title="Updated",
            metadata={"done": True},
        )
        assert updated.revision == 2
        assert updated.status == "archived"
        assert updated.title == "Updated"
        assert updated.metadata == {"done": True}
        assert repository.status().state_revision == 2
        assert workspace.load_workspace(initialized.root).record.state_revision == 2

        with pytest.raises(state.StaleRevisionError):
            repository.update_record(created.id, expected_revision=1)

        with pytest.raises(KeyError):
            repository.get_record("missing")


def test_record_validation_and_read_only_write_rejection(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.initialize_state_repository(initialized.root) as repository:
        for kwargs in (
            {"record_type": " "},
            {"record_type": "x", "schema_version": 0},
            {"record_type": "x", "status": "bogus"},
            {"record_type": "x", "provenance": "bogus"},
            {"record_type": "x", "sensitivity": "bogus"},
        ):
            with pytest.raises(state.RecordValidationError):
                repository.create_record(**kwargs)

        record = repository.create_record(record_type="x")

    with state.open_state_repository(initialized.root, read_only=True) as repository:
        assert repository.status().read_only is True
        assert repository.get_record(record.id).id == record.id
        with pytest.raises(state.ReadOnlyStateError):
            repository.create_record(record_type="blocked")
        with pytest.raises(state.ReadOnlyStateError):
            repository.update_record(record.id, expected_revision=1)


def test_invalid_record_metadata_is_detected(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.initialize_state_repository(initialized.root) as repository:
        record = repository.create_record(record_type="x")

    database_path = initialized.root / "state" / state.STATE_DATABASE_NAME
    connection = sqlite3.connect(database_path)
    try:
        connection.execute(
            "UPDATE records SET metadata_json = '[]' WHERE id = ?",
            (record.id,),
        )
        connection.commit()
    finally:
        connection.close()

    with state.open_state_repository(initialized.root, read_only=True) as repository:
        with pytest.raises(state.StateCorruptError):
            repository.get_record(record.id)


def test_create_record_rolls_back_when_revision_update_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.initialize_state_repository(initialized.root) as repository:

        def fail_revision(self: state.StateRepository) -> int:
            raise RuntimeError("revision failure")

        monkeypatch.setattr(state.StateRepository, "_commit_state_revision", fail_revision)
        with pytest.raises(RuntimeError, match="revision failure"):
            repository.create_record(record_type="x")
        assert repository.status().record_count == 0


def test_update_record_validation_race_and_rollback(
    tmp_path: Path,
) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.initialize_state_repository(initialized.root) as repository:
        record = repository.create_record(record_type="x", title="original")

        with pytest.raises(state.RecordValidationError):
            repository.update_record(
                record.id,
                expected_revision=1,
                status="bogus",  # type: ignore[arg-type]
            )

        repository.connection.execute(
            """
            CREATE TRIGGER ignore_record_update
            BEFORE UPDATE ON records
            BEGIN
                SELECT RAISE(IGNORE);
            END
            """
        )
        with pytest.raises(state.StaleRevisionError):
            repository.update_record(record.id, expected_revision=1)
        repository.connection.execute("DROP TRIGGER ignore_record_update")

        with pytest.raises(TypeError):
            repository.update_record(
                record.id,
                expected_revision=1,
                metadata={"bad": {1, 2}},
            )
        assert repository.get_record(record.id).revision == 1
