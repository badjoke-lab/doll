from __future__ import annotations

from pathlib import Path
from typing import cast
from uuid import uuid4

import pytest

from doll import audit, state, workspace
from doll.audit import AuditService, AuditValidationError


def initialized_workspace(tmp_path: Path) -> workspace.InitializedWorkspace:
    initialized = workspace.initialize_workspace(tmp_path / "workspace")
    return initialized


def test_append_wraps_database_error_and_rolls_back(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.initialize_state_repository(initialized.root) as repository:
        repository.connection.execute(
            "ALTER TABLE audit_events RENAME TO audit_events_missing"
        )
        with pytest.raises(state.StateCorruptError, match="could not be appended"):
            AuditService(repository).append(action="audit.append", result="failed")
        assert repository.connection.in_transaction is False


def test_append_rolls_back_unexpected_revision_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.initialize_state_repository(initialized.root) as repository:

        def fail_revision(self: state.StateRepository) -> int:
            raise RuntimeError("synthetic revision failure")

        monkeypatch.setattr(
            state.StateRepository,
            "_commit_state_revision",
            fail_revision,
        )
        with pytest.raises(RuntimeError, match="synthetic revision failure"):
            AuditService(repository).append(action="audit.rollback", result="failed")

        count = repository.connection.execute(
            "SELECT COUNT(*) FROM audit_events"
        ).fetchone()
        assert count is not None
        assert count[0] == 0
        assert repository.connection.in_transaction is False


def test_get_wraps_missing_audit_table(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.initialize_state_repository(initialized.root) as repository:
        repository.connection.execute(
            "ALTER TABLE audit_events RENAME TO audit_events_missing"
        )
        with pytest.raises(state.StateCorruptError, match="unreadable"):
            AuditService(repository).get(str(uuid4()))


def test_defensive_validation_branches(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    unusual_error = type("Bad Error", (Exception,), {})

    with state.initialize_state_repository(initialized.root) as repository:
        service = AuditService(repository)
        event = service.append(
            action="audit.safe-error",
            result="failed",
            summary="   ",
            error=unusual_error(),
        )
        assert event.summary is None
        assert event.error_class == "Error"

        with pytest.raises(AuditValidationError, match="keys must be strings"):
            audit._serialize_metadata(cast(dict[str, object], {1: "synthetic"}))
        with pytest.raises(AuditValidationError, match="control characters"):
            service.append(
                action="audit.identifier",
                result="denied",
                actor_id="synthetic\x00actor",
            )
        with pytest.raises(AuditValidationError, match="absolute path"):
            service.append(
                action="audit.path",
                result="denied",
                summary=r"opened C:\Users\synthetic\private.txt",
            )
        with pytest.raises(AuditValidationError, match="timestamp is invalid"):
            audit._validate_utc_timestamp("2026-99-99T00:00:00Z")
        with pytest.raises(ValueError, match="non-standard JSON"):
            audit._reject_nonstandard_json("NaN")
