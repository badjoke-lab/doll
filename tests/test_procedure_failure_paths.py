from __future__ import annotations

import sqlite3
from pathlib import Path
from uuid import uuid4

import pytest

from doll import state, workspace
from doll.procedure import (
    ProcedureService,
    ProcedureValidationError,
    _validate_persisted_semantics,
)
from doll.project_state import ProjectService
from doll.state import StateCorruptError
from doll.state_repository import StateRepository


def _workspace(tmp_path: Path) -> workspace.InitializedWorkspace:
    initialized = workspace.initialize_workspace(tmp_path / "workspace")
    with state.initialize_state_repository(initialized.root):
        pass
    return initialized


def _project(repository: StateRepository) -> str:
    return (
        ProjectService(repository)
        .create_v2(
            name="Procedure failure project",
            description="Procedure transaction rollback test.",
            objective="Preserve state when procedure writes fail.",
            in_scope=("Procedure transactions",),
            out_of_scope=("Procedure execution",),
            success_criteria=("Failed writes leave no partial state",),
            project_status="active",
            started_at="2026-06-25T00:00:00Z",
        )
        .project_id
    )


def _raise_database_error(_repository: StateRepository) -> int:
    raise sqlite3.DatabaseError("synthetic procedure database failure")


def _raise_runtime_error(_repository: StateRepository) -> int:
    raise RuntimeError("synthetic procedure runtime failure")


def test_create_database_failure_rolls_back(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project_id = _project(repository)
        before = repository.connection.execute(
            "SELECT COUNT(*) FROM records WHERE record_type = 'procedure'"
        ).fetchone()[0]
        monkeypatch.setattr(
            StateRepository,
            "_commit_state_revision",
            _raise_database_error,
        )

        with pytest.raises(StateCorruptError):
            ProcedureService(repository).create_draft(
                project_id=project_id,
                title="Database failure draft",
                purpose="Exercise the SQLite rollback branch.",
                version=1,
            )

        after = repository.connection.execute(
            "SELECT COUNT(*) FROM records WHERE record_type = 'procedure'"
        ).fetchone()[0]

    assert before == after == 0


def test_create_runtime_failure_rolls_back(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project_id = _project(repository)
        monkeypatch.setattr(
            StateRepository,
            "_commit_state_revision",
            _raise_runtime_error,
        )

        with pytest.raises(RuntimeError, match="synthetic procedure runtime failure"):
            ProcedureService(repository).create_draft(
                project_id=project_id,
                title="Runtime failure draft",
                purpose="Exercise the general rollback branch.",
                version=1,
            )

        count = repository.connection.execute(
            "SELECT COUNT(*) FROM records WHERE record_type = 'procedure'"
        ).fetchone()[0]

    assert count == 0


def test_update_database_failure_rolls_back(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project_id = _project(repository)
        service = ProcedureService(repository)
        draft = service.create_draft(
            project_id=project_id,
            title="Original draft",
            purpose="Original accepted storage state.",
            version=1,
        )
        monkeypatch.setattr(
            StateRepository,
            "_commit_state_revision",
            _raise_database_error,
        )

        with pytest.raises(StateCorruptError):
            service.update_draft(
                draft.procedure_id,
                expected_revision=draft.revision,
                title="Changed draft",
                purpose=draft.purpose,
                version=draft.version,
            )

        unchanged = service.get(draft.procedure_id)

    assert unchanged.title == "Original draft"
    assert unchanged.revision == draft.revision


def test_update_runtime_failure_rolls_back(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project_id = _project(repository)
        service = ProcedureService(repository)
        draft = service.create_draft(
            project_id=project_id,
            title="Original runtime draft",
            purpose="Original state before a runtime failure.",
            version=1,
        )
        monkeypatch.setattr(
            StateRepository,
            "_commit_state_revision",
            _raise_runtime_error,
        )

        with pytest.raises(RuntimeError, match="synthetic procedure runtime failure"):
            service.update_draft(
                draft.procedure_id,
                expected_revision=draft.revision,
                title="Changed runtime draft",
                purpose=draft.purpose,
                version=draft.version,
            )

        unchanged = service.get(draft.procedure_id)

    assert unchanged.title == "Original runtime draft"
    assert unchanged.revision == draft.revision


def test_persisted_self_supersession_relations_fail_closed() -> None:
    procedure_id = str(uuid4())

    with pytest.raises(ProcedureValidationError):
        _validate_persisted_semantics(
            procedure_id,
            "draft",
            (),
            (),
            (),
            (),
            None,
            (),
            procedure_id,
            None,
            None,
        )

    with pytest.raises(ProcedureValidationError):
        _validate_persisted_semantics(
            procedure_id,
            "approved",
            ("Step",),
            ("Validate",),
            ("Rollback",),
            (),
            None,
            (),
            None,
            procedure_id,
            "2026-06-25T01:00:00Z",
        )
