from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import cast
from uuid import uuid4

import pytest
from typer.testing import CliRunner

from doll import memory as memory_module
from doll import state, workspace
from doll.cli import app
from doll.memory import (
    ConfirmedMemoryService,
    MemoryCorruptError,
    MemoryValidationError,
    _insert_memory_audit,
    _metadata_reference_ids,
)

runner = CliRunner()


def initialized_workspace(tmp_path: Path) -> workspace.InitializedWorkspace:
    initialized = workspace.initialize_workspace(tmp_path / "workspace")
    with state.initialize_state_repository(initialized.root):
        pass
    return initialized


def base_metadata(
    *,
    subject: str = "subject",
    content: str = "content",
) -> dict[str, object]:
    return {
        "memory_class": "confirmed",
        "subject": subject,
        "content": content,
        "source_type": "user_statement",
        "confirmation_state": "confirmed",
        "valid_from": None,
        "valid_until": None,
        "confidence": 1.0,
        "related_memory_ids": [],
        "contradicts_memory_ids": [],
        "source_reference": None,
        "model_manifest_id": None,
        "runtime_adapter_id": None,
        "session_id": None,
        "origin_operation_id": None,
    }


def test_read_only_update_and_archive_are_rejected(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        created = ConfirmedMemoryService(repository).create(
            subject="read-only mutation",
            content="original fact",
        )

    with state.open_state_repository(
        initialized.root,
        read_only=True,
    ) as repository:
        service = ConfirmedMemoryService(repository)
        with pytest.raises(state.ReadOnlyStateError):
            service.update(
                created.record_id,
                expected_revision=1,
                subject="read-only mutation",
                content="changed fact",
                source_type="user_statement",
            )
        with pytest.raises(state.ReadOnlyStateError):
            service.archive(
                created.record_id,
                expected_revision=1,
            )


def test_create_runtime_failure_rolls_back(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    initialized = initialized_workspace(tmp_path)

    def fail_audit(*args: object, **kwargs: object) -> None:
        raise RuntimeError("synthetic audit failure")

    monkeypatch.setattr(memory_module, "_insert_memory_audit", fail_audit)

    with state.open_state_repository(initialized.root) as repository:
        with pytest.raises(RuntimeError, match="synthetic audit failure"):
            ConfirmedMemoryService(repository).create(
                subject="rollback create",
                content="must not persist",
            )

        row = repository.connection.execute(
            "SELECT COUNT(*) FROM records WHERE record_type = 'memory'"
        ).fetchone()
        assert row is not None
        assert row[0] == 0
        assert repository.status().state_revision == 0
        assert repository.connection.in_transaction is False


def test_update_runtime_failure_rolls_back(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        service = ConfirmedMemoryService(repository)
        created = service.create(
            subject="rollback update",
            content="original fact",
        )

        def fail_audit(*args: object, **kwargs: object) -> None:
            raise RuntimeError("synthetic update audit failure")

        monkeypatch.setattr(memory_module, "_insert_memory_audit", fail_audit)

        with pytest.raises(RuntimeError, match="synthetic update audit failure"):
            service.update(
                created.record_id,
                expected_revision=1,
                subject="rollback update",
                content="changed fact",
                source_type="user_statement",
            )

        restored = service.get(created.record_id)
        assert restored.revision == 1
        assert restored.content == "original fact"
        assert repository.status().state_revision == 1
        assert repository.connection.in_transaction is False


def test_audit_requires_valid_source_metadata(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        with pytest.raises(MemoryValidationError):
            _insert_memory_audit(
                repository,
                operation_id="memory-audit-test",
                action="memory.create",
                target_id=str(uuid4()),
                metadata={
                    "related_memory_ids": [],
                    "contradicts_memory_ids": [],
                },
                sensitivity="personal",
            )


@pytest.mark.parametrize(
    ("metadata_patch", "provenance"),
    [
        ({"memory_class": "suggested"}, "user-confirmed"),
        ({"confirmation_state": "pending"}, "user-confirmed"),
        ({"source_type": "unknown"}, "user-confirmed"),
        ({}, "imported"),
        (
            {
                "valid_from": "2026-06-15T00:00:00Z",
                "valid_until": "2026-06-14T00:00:00Z",
            },
            "user-confirmed",
        ),
        (
            {
                "related_memory_ids": ["00000000-0000-0000-0000-000000000001"],
                "contradicts_memory_ids": ["00000000-0000-0000-0000-000000000001"],
            },
            "user-confirmed",
        ),
    ],
)
def test_additional_corrupt_memory_variants(
    tmp_path: Path,
    metadata_patch: dict[str, object],
    provenance: str,
) -> None:
    initialized = initialized_workspace(tmp_path)
    metadata = base_metadata()
    metadata.update(metadata_patch)

    with state.open_state_repository(initialized.root) as repository:
        record = repository.create_record(
            record_type="memory",
            title="subject",
            provenance=cast(state.RecordProvenance, provenance),
            metadata=metadata,
        )
        with pytest.raises(MemoryCorruptError):
            ConfirmedMemoryService(repository).get(record.id)


def test_reference_metadata_rejects_non_text_entries() -> None:
    with pytest.raises(MemoryValidationError):
        _metadata_reference_ids(
            {"related_memory_ids": [1]},
            "related_memory_ids",
        )


def test_memory_cli_missing_record_failures_hide_workspace(
    tmp_path: Path,
) -> None:
    initialized = initialized_workspace(tmp_path)
    root = initialized.root
    missing = "00000000-0000-0000-0000-000000000001"

    update = runner.invoke(
        app,
        [
            "memory",
            "update",
            missing,
            "--revision",
            "1",
            "--subject",
            "missing",
            "--content",
            "missing",
            "--source-type",
            "user_statement",
            "--workspace",
            str(root),
        ],
    )
    assert update.exit_code == 2
    assert "memory update failed" in update.output
    assert str(root) not in update.output

    archive = runner.invoke(
        app,
        [
            "memory",
            "archive",
            missing,
            "--revision",
            "1",
            "--workspace",
            str(root),
        ],
    )
    assert archive.exit_code == 2
    assert "memory archive failed" in archive.output
    assert str(root) not in archive.output

    export = runner.invoke(
        app,
        [
            "memory",
            "export",
            missing,
            "--workspace",
            str(root),
        ],
    )
    assert export.exit_code == 2
    assert "memory export failed" in export.output
    assert str(root) not in export.output


@pytest.mark.parametrize(
    ("column", "value"),
    [
        ("schema_version", 2),
        ("status", "superseded"),
        ("provenance", "model-proposed"),
        ("created_at", "not-a-time"),
        ("updated_at", "not-a-time"),
    ],
)
def test_corrupt_memory_common_envelope_is_rejected(
    tmp_path: Path,
    column: str,
    value: object,
) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        created = ConfirmedMemoryService(repository).create(
            subject="envelope",
            content="valid fact",
        )
        repository.connection.execute(
            f"UPDATE records SET {column} = ? WHERE id = ?",
            (value, created.record_id),
        )
        with pytest.raises(MemoryCorruptError):
            ConfirmedMemoryService(repository).get(created.record_id)


@pytest.mark.parametrize(
    ("column", "value"),
    [
        ("revision", 0),
        ("sensitivity", "unknown"),
    ],
)
def test_memory_database_constraints_reject_invalid_envelope_values(
    tmp_path: Path,
    column: str,
    value: object,
) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        created = ConfirmedMemoryService(repository).create(
            subject="database constraint",
            content="valid fact",
        )
        before = ConfirmedMemoryService(repository).get(created.record_id)

        with pytest.raises(sqlite3.IntegrityError):
            repository.connection.execute(
                f"UPDATE records SET {column} = ? WHERE id = ?",
                (value, created.record_id),
            )

        after = ConfirmedMemoryService(repository).get(created.record_id)
        assert after == before
        assert repository.connection.in_transaction is False


def test_memory_updated_at_cannot_precede_created_at(
    tmp_path: Path,
) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        created = ConfirmedMemoryService(repository).create(
            subject="time order",
            content="valid fact",
        )
        repository.connection.execute(
            """
            UPDATE records
            SET created_at = '2026-06-15T00:00:00Z',
                updated_at = '2026-06-14T00:00:00Z'
            WHERE id = ?
            """,
            (created.record_id,),
        )
        with pytest.raises(MemoryCorruptError):
            ConfirmedMemoryService(repository).get(created.record_id)


def test_include_archived_excludes_other_record_statuses(
    tmp_path: Path,
) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        created = ConfirmedMemoryService(repository).create(
            subject="quarantined",
            content="valid fact",
        )
        repository.connection.execute(
            "UPDATE records SET status = 'invalid' WHERE id = ?",
            (created.record_id,),
        )

        service = ConfirmedMemoryService(repository)
        assert service.list() == ()
        assert service.list(include_archived=True) == ()
        with pytest.raises(MemoryCorruptError):
            service.get(created.record_id)
