from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

from doll import state, workspace
from doll.audit import AuditService
from doll.memory import (
    ConfirmedMemoryService,
    ForbiddenMemoryMutationError,
    MemoryCorruptError,
    MemoryExportError,
    MemorySourceType,
    MemoryValidationError,
)


def initialized_workspace(tmp_path: Path) -> workspace.InitializedWorkspace:
    initialized = workspace.initialize_workspace(tmp_path / "workspace")
    with state.initialize_state_repository(initialized.root):
        pass
    return initialized


def test_confirmed_memory_persists_restart_and_exports_without_model(
    tmp_path: Path,
) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        service = ConfirmedMemoryService(repository)
        created = service.create(
            subject="表示言語",
            content="ユーザーは日本語での回答を好む。",
            source_type="user_statement",
            confidence=0.95,
            operation_id="memory-create",
        )
        assert created.revision == 1
        assert created.provenance == "user-confirmed"
        assert repository.status().state_revision == 1
        assert AuditService(repository).list(limit=10)[0].action == "memory.create"

    with state.open_state_repository(
        initialized.root,
        read_only=True,
    ) as repository:
        before = repository.status().state_revision
        audit_count = len(AuditService(repository).list(limit=10))
        restored = ConfirmedMemoryService(repository).get(created.record_id)
        payload = ConfirmedMemoryService(repository).export_json(created.record_id)
        assert restored.content == "ユーザーは日本語での回答を好む。"
        assert repository.status().state_revision == before
        assert len(AuditService(repository).list(limit=10)) == audit_count

    decoded = json.loads(payload)
    assert decoded["export_schema"] == "doll.confirmed-memory.v1"
    assert decoded["record"]["memory"]["content"] == restored.content
    assert (
        payload
        == json.dumps(
            decoded,
            ensure_ascii=False,
            sort_keys=True,
            allow_nan=False,
            separators=(",", ":"),
        )
        + "\n"
    )


def test_memory_update_stale_revision_archive_and_immutability(
    tmp_path: Path,
) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        service = ConfirmedMemoryService(repository)
        created = service.create(
            subject="出力形式",
            content="短い段落を優先する。",
        )
        updated = service.update(
            created.record_id,
            expected_revision=1,
            subject="出力形式",
            content="短く完全な段落を優先する。",
            source_type="user_statement",
            confidence=0.9,
            operation_id="memory-update",
        )
        assert updated.revision == 2
        assert updated.content == "短く完全な段落を優先する。"

        with pytest.raises(state.StaleRevisionError):
            service.update(
                created.record_id,
                expected_revision=1,
                subject="stale",
                content="stale",
                source_type="user_statement",
            )

        archived = service.archive(
            created.record_id,
            expected_revision=2,
            operation_id="memory-archive",
        )
        assert archived.status == "archived"
        assert service.list() == ()
        assert service.list(include_archived=True) == (archived,)

        with pytest.raises(MemoryValidationError):
            service.update(
                created.record_id,
                expected_revision=3,
                subject="変更",
                content="変更",
                source_type="user_statement",
            )
        with pytest.raises(MemoryValidationError):
            service.archive(created.record_id, expected_revision=3)

        assert repository.status().state_revision == 3
        actions = {event.action for event in AuditService(repository).list(limit=10)}
        assert actions == {"memory.create", "memory.update", "memory.archive"}


@pytest.mark.parametrize(
    ("source_type", "expected_provenance"),
    [
        ("user_statement", "user-confirmed"),
        ("approved_import", "imported"),
        ("migrated", "migrated"),
        ("restored", "restored"),
    ],
)
def test_memory_source_type_maps_to_common_provenance(
    tmp_path: Path,
    source_type: str,
    expected_provenance: str,
) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        created = ConfirmedMemoryService(repository).create(
            subject=f"source-{source_type}",
            content="portable confirmed fact",
            source_type=cast(MemorySourceType, source_type),
            source_reference="source-1",
        )
        assert created.provenance == expected_provenance


def test_accepted_suggestion_requires_complete_provenance_and_user_action(
    tmp_path: Path,
) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        service = ConfirmedMemoryService(repository)
        with pytest.raises(MemoryValidationError):
            service.create(
                subject="suggestion",
                content="accepted fact",
                source_type="accepted_suggestion",
            )
        with pytest.raises(ForbiddenMemoryMutationError):
            service.create(
                subject="model write",
                content="must not become authoritative",
                actor_type="model",
            )

        created = service.create(
            subject="accepted suggestion",
            content="explicitly accepted fact",
            source_type="accepted_suggestion",
            model_manifest_id="model-1",
            runtime_adapter_id="runtime-1",
            session_id="session-1",
            origin_operation_id="operation-1",
        )
        assert created.source_type == "accepted_suggestion"
        assert created.provenance == "user-confirmed"


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"confidence": -0.1}, "confidence"),
        ({"confidence": 1.1}, "confidence"),
        ({"confidence": float("nan")}, "confidence"),
        (
            {
                "valid_from": "2026-06-15T00:00:00Z",
                "valid_until": "2026-06-14T00:00:00Z",
            },
            "valid-until",
        ),
        ({"valid_from": "bad"}, "valid-from"),
        ({"content": "/private/path"}, "absolute"),
        ({"content": "C:\\private\\path"}, "absolute"),
    ],
)
def test_memory_validation_rejects_unsafe_values(
    tmp_path: Path,
    kwargs: dict[str, object],
    message: str,
) -> None:
    initialized = initialized_workspace(tmp_path)
    base: dict[str, object] = {
        "subject": "validation",
        "content": "valid fact",
    }
    base.update(kwargs)
    with state.open_state_repository(initialized.root) as repository:
        with pytest.raises(MemoryValidationError, match=message):
            ConfirmedMemoryService(repository).create(**base)  # type: ignore[arg-type]
        assert repository.status().state_revision == 0


def test_memory_references_are_typed_existing_and_non_overlapping(
    tmp_path: Path,
) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        service = ConfirmedMemoryService(repository)
        first = service.create(subject="first", content="first fact")
        second = service.create(
            subject="second",
            content="second fact",
            related_memory_ids=(first.record_id,),
        )
        assert second.related_memory_ids == (first.record_id,)

        with pytest.raises(MemoryValidationError):
            service.update(
                second.record_id,
                expected_revision=1,
                subject="second",
                content="second fact",
                source_type="user_statement",
                related_memory_ids=(second.record_id,),
            )
        with pytest.raises(MemoryValidationError):
            service.create(
                subject="overlap",
                content="overlap",
                related_memory_ids=(first.record_id,),
                contradicts_memory_ids=(first.record_id,),
            )
        with pytest.raises(MemoryValidationError):
            service.create(
                subject="missing",
                content="missing",
                related_memory_ids=("00000000-0000-0000-0000-000000000001",),
            )

        other = repository.create_record(
            record_type="other",
            metadata={},
        )
        with pytest.raises(MemoryValidationError):
            service.create(
                subject="wrong type",
                content="wrong type",
                related_memory_ids=(other.id,),
            )


def test_secret_memory_normal_export_is_denied_without_mutation(
    tmp_path: Path,
) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        service = ConfirmedMemoryService(repository)
        created = service.create(
            subject="secret category",
            content="synthetic private fact",
            sensitivity="secret",
        )
        before = repository.status().state_revision
        audit_before = len(AuditService(repository).list(limit=10))
        with pytest.raises(MemoryExportError):
            service.export_json(created.record_id)
        assert repository.status().state_revision == before
        assert len(AuditService(repository).list(limit=10)) == audit_before


def test_read_only_repository_allows_inspection_and_export_only(
    tmp_path: Path,
) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        created = ConfirmedMemoryService(repository).create(
            subject="read only",
            content="persisted fact",
        )

    with state.open_state_repository(
        initialized.root,
        read_only=True,
    ) as repository:
        service = ConfirmedMemoryService(repository)
        assert service.get(created.record_id).content == "persisted fact"
        assert "persisted fact" in service.export_json(created.record_id)
        with pytest.raises(state.ReadOnlyStateError):
            service.create(subject="blocked", content="blocked")


def test_corrupt_memory_records_are_normalized(
    tmp_path: Path,
) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        malformed = repository.create_record(
            record_type="memory",
            title="bad",
            provenance="user-confirmed",
            metadata={
                "memory_class": "confirmed",
                "subject": "bad",
                "content": "bad",
                "source_type": "accepted_suggestion",
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
            },
        )
        with pytest.raises(MemoryCorruptError):
            ConfirmedMemoryService(repository).get(malformed.id)

        wrong = repository.create_record(record_type="other", metadata={})
        with pytest.raises(KeyError):
            ConfirmedMemoryService(repository).get(wrong.id)


def test_database_failure_rolls_back_memory_and_revision(
    tmp_path: Path,
) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        repository.connection.execute("DROP TABLE audit_events")
        with pytest.raises(state.StateCorruptError):
            ConfirmedMemoryService(repository).create(
                subject="rollback",
                content="rollback fact",
            )
        row = repository.connection.execute(
            "SELECT COUNT(*) FROM records WHERE record_type = 'memory'"
        ).fetchone()
        assert row is not None
        assert row[0] == 0
        assert repository.status().state_revision == 0
        assert repository.connection.in_transaction is False
