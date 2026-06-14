from __future__ import annotations

import sqlite3
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from doll import state, workspace
from doll.audit import AuditService, AuditValidationError


def initialized_workspace(tmp_path: Path) -> workspace.InitializedWorkspace:
    return workspace.initialize_workspace(tmp_path / "workspace")


def test_append_get_list_and_filters_advance_revision(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.initialize_state_repository(initialized.root) as repository:
        service = AuditService(repository)
        first = service.append(
            operation_id="operation-1",
            actor_type="user",
            actor_id="synthetic-user",
            action="state.initialize",
            target_type="workspace",
            target_id="synthetic-target",
            result="success",
            summary="Initialized synthetic state",
            metadata={"records": 0, "language": "日本語"},
        )
        second = service.append(
            operation_id="operation-1",
            actor_type="system",
            action="state.verify",
            target_type="workspace",
            result="failed",
            summary="Synthetic verification failure",
            error=RuntimeError("password=must-not-be-persisted"),
            metadata={"attempt": 2},
        )

        assert first.sequence == 1
        assert second.sequence == 2
        UUID(first.event_id)
        UUID(second.event_id)
        assert first.operation_id == second.operation_id == "operation-1"
        assert first.metadata == {"records": 0, "language": "日本語"}
        assert second.error_class == "RuntimeError"
        assert "must-not-be-persisted" not in repr(second)
        assert service.get(first.event_id) == first
        assert [event.event_id for event in service.list()] == [
            second.event_id,
            first.event_id,
        ]
        assert service.list(operation_id="operation-1", limit=1) == (second,)
        assert service.list(action="state.initialize") == (first,)
        assert service.list(actor_type="user") == (first,)
        assert service.list(result="failed") == (second,)
        assert repository.status().state_revision == 2

    assert workspace.load_workspace(initialized.root).record.state_revision == 2


def test_read_only_listing_and_write_rejection_do_not_mutate_files(
    tmp_path: Path,
) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.initialize_state_repository(initialized.root) as repository:
        AuditService(repository).append(action="audit.test", result="success")

    database_path = initialized.root / "state" / state.STATE_DATABASE_NAME
    workspace_path = initialized.root / workspace.WORKSPACE_RECORD_NAME
    before_database = database_path.stat().st_mtime_ns
    before_workspace = workspace_path.stat().st_mtime_ns

    with state.open_state_repository(initialized.root, read_only=True) as repository:
        service = AuditService(repository)
        events = service.list()
        assert len(events) == 1
        with pytest.raises(state.ReadOnlyStateError):
            service.append(action="audit.blocked", result="denied")

    assert database_path.stat().st_mtime_ns == before_database
    assert workspace_path.stat().st_mtime_ns == before_workspace


def test_audit_validation_rejects_secrets_paths_and_invalid_values(
    tmp_path: Path,
) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.initialize_state_repository(initialized.root) as repository:
        service = AuditService(repository)

        invalid_calls = (
            {"action": "bad action", "result": "success"},
            {"action": "x", "result": "bogus"},
            {"action": "x", "result": "success", "actor_type": "bogus"},
            {"action": "x", "result": "success", "actor_id": "   "},
            {"action": "x", "result": "success", "summary": "password=hunter2"},
            {
                "action": "x",
                "result": "success",
                "summary": "opened /Users/example/private.txt",
            },
            {
                "action": "x",
                "result": "success",
                "metadata": {"api_key": "must-not-persist"},
            },
            {
                "action": "x",
                "result": "success",
                "metadata": {"note": "access_token=must-not-persist"},
            },
            {
                "action": "x",
                "result": "success",
                "metadata": {"bad": {1, 2}},
            },
            {
                "action": "x",
                "result": "success",
                "metadata": {"bad": float("nan")},
            },
            {
                "action": "x",
                "result": "success",
                "metadata": {"large": "x" * 9000},
            },
        )
        for kwargs in invalid_calls:
            with pytest.raises(AuditValidationError):
                service.append(**kwargs)  # type: ignore[arg-type]

        with pytest.raises(AuditValidationError):
            service.list(limit=0)
        with pytest.raises(AuditValidationError):
            service.list(limit=201)
        with pytest.raises(AuditValidationError):
            service.list(actor_type="bogus")  # type: ignore[arg-type]
        with pytest.raises(AuditValidationError):
            service.list(result="bogus")  # type: ignore[arg-type]
        with pytest.raises(KeyError):
            service.get(str(uuid4()))

        assert service.list() == ()
        assert repository.status().state_revision == 0


def test_database_triggers_prevent_update_and_delete(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.initialize_state_repository(initialized.root) as repository:
        event = AuditService(repository).append(action="audit.append", result="success")

        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            repository.connection.execute(
                "UPDATE audit_events SET summary = 'changed' WHERE event_id = ?",
                (event.event_id,),
            )
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            repository.connection.execute(
                "DELETE FROM audit_events WHERE event_id = ?",
                (event.event_id,),
            )

        assert AuditService(repository).get(event.event_id) == event


def test_corrupt_audit_metadata_is_detected(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.initialize_state_repository(initialized.root) as repository:
        repository.connection.execute(
            """
            INSERT INTO audit_events (
                event_id,
                operation_id,
                occurred_at,
                actor_type,
                action,
                result,
                metadata_json
            ) VALUES (?, ?, ?, 'system', 'audit.corrupt', 'failed', '[]')
            """,
            (str(uuid4()), str(uuid4()), "2026-06-14T00:00:00Z"),
        )
        with pytest.raises(state.StateCorruptError, match="JSON object"):
            AuditService(repository).list()


def test_audit_service_has_no_public_mutation_or_delete_api(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.initialize_state_repository(initialized.root) as repository:
        service = AuditService(repository)
        assert not hasattr(service, "update")
        assert not hasattr(service, "delete")
