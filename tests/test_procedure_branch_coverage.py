from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from doll import state, workspace
from doll.procedure import (
    ProcedureService,
    ProcedureValidationError,
    _validate_persisted_semantics,
    _validate_procedure_links,
    _validated_values,
)
from doll.project_state import ProjectService
from doll.state_repository import StateRepository


def _project(repository: StateRepository, name: str = "Project") -> str:
    return (
        ProjectService(repository)
        .create_v2(
            name=name,
            description="Procedure branch-coverage project.",
            objective="Exercise ProcedureRecord defensive branches.",
            in_scope=("Procedure validation",),
            out_of_scope=("Procedure execution",),
            success_criteria=("Invalid relations fail closed",),
            project_status="active",
            started_at="2026-06-25T00:00:00Z",
        )
        .project_id
    )


def _values(
    repository: StateRepository,
    *,
    self_id: str,
    project_id: str,
    procedure_status: str = "draft",
    source_ids: tuple[str, ...] = (),
    last_verified_at: str | None = None,
    verification_evidence_ids: tuple[str, ...] = (),
    supersedes_id: str | None = None,
    superseded_by_id: str | None = None,
    approved_at: str | None = None,
) -> dict[str, object]:
    return _validated_values(
        repository,
        self_id=self_id,
        project_id=project_id,
        title="Procedure",
        purpose="Synthetic defensive validation procedure.",
        procedure_status=procedure_status,
        version=1,
        prerequisites=(),
        ordered_steps=("Step",),
        required_capability_ids=(),
        expected_outputs=(),
        validation_steps=("Validate",),
        rollback_steps=("Rollback",),
        platform_constraints=(),
        source_ids=source_ids,
        last_verified_at=last_verified_at,
        verification_evidence_ids=verification_evidence_ids,
        supersedes_id=supersedes_id,
        superseded_by_id=superseded_by_id,
        approved_at=approved_at,
    )


def test_requested_metadata_semantics_fail_closed(tmp_path: Path) -> None:
    initialized = workspace.initialize_workspace(tmp_path / "workspace")
    with state.initialize_state_repository(initialized.root):
        pass

    with state.open_state_repository(initialized.root) as repository:
        project_id = _project(repository)
        self_id = str(uuid4())
        other_id = str(uuid4())

        invalid_calls = (
            lambda: _values(
                repository,
                self_id=self_id,
                project_id=project_id,
                source_ids=(self_id,),
            ),
            lambda: _values(
                repository,
                self_id=self_id,
                project_id=project_id,
                approved_at="2026-06-25T01:00:00Z",
            ),
            lambda: _values(
                repository,
                self_id=self_id,
                project_id=project_id,
                procedure_status="approved",
            ),
            lambda: _values(
                repository,
                self_id=self_id,
                project_id=project_id,
                procedure_status="superseded",
                approved_at="2026-06-25T01:00:00Z",
            ),
            lambda: _values(
                repository,
                self_id=self_id,
                project_id=project_id,
                procedure_status="approved",
                approved_at="2026-06-25T01:00:00Z",
                superseded_by_id=other_id,
            ),
            lambda: _values(
                repository,
                self_id=self_id,
                project_id=project_id,
                verification_evidence_ids=(other_id,),
            ),
        )
        for invalid_call in invalid_calls:
            with pytest.raises(ProcedureValidationError):
                invalid_call()


def test_persisted_self_relation_fails_closed() -> None:
    procedure_id = str(uuid4())
    with pytest.raises(ProcedureValidationError):
        _validate_persisted_semantics(
            procedure_id,
            "draft",
            (),
            (),
            (),
            (procedure_id,),
            None,
            (),
            None,
            None,
            None,
        )


def test_procedure_relation_validation_branches(tmp_path: Path) -> None:
    initialized = workspace.initialize_workspace(tmp_path / "workspace")
    with state.initialize_state_repository(initialized.root):
        pass

    with state.open_state_repository(initialized.root) as repository:
        first_project = _project(repository, "First")
        second_project = _project(repository, "Second")
        service = ProcedureService(repository)
        draft = service.create_draft(
            project_id=first_project,
            title="Draft predecessor",
            purpose="Unaccepted predecessor fixture.",
            version=1,
        )
        approved_v2 = service.create_approved(
            project_id=first_project,
            title="Version two",
            purpose="Version ordering fixture.",
            version=2,
            ordered_steps=("Step",),
            validation_steps=("Validate",),
            rollback_steps=("Rollback",),
        )
        cross_project = service.create_approved(
            project_id=second_project,
            title="Cross-project procedure",
            purpose="Cross-project fixture.",
            version=1,
            ordered_steps=("Step",),
            validation_steps=("Validate",),
            rollback_steps=("Rollback",),
        )
        unrelated_predecessor = service.create_approved(
            project_id=first_project,
            title="Unrelated predecessor",
            purpose="Reciprocity fixture.",
            version=1,
            ordered_steps=("Step",),
            validation_steps=("Validate",),
            rollback_steps=("Rollback",),
        )
        replacement = service.create_approved(
            project_id=first_project,
            title="Unrelated replacement",
            purpose="Reciprocity fixture.",
            version=3,
            ordered_steps=("Step",),
            validation_steps=("Validate",),
            rollback_steps=("Rollback",),
            supersedes_id=unrelated_predecessor.procedure_id,
        )

        cases = (
            {
                "version": 2,
                "supersedes_id": str(uuid4()),
                "superseded_by_id": None,
            },
            {
                "version": 2,
                "supersedes_id": cross_project.procedure_id,
                "superseded_by_id": None,
            },
            {
                "version": 2,
                "supersedes_id": approved_v2.procedure_id,
                "superseded_by_id": None,
            },
            {
                "version": 2,
                "supersedes_id": draft.procedure_id,
                "superseded_by_id": None,
            },
            {
                "version": 2,
                "supersedes_id": None,
                "superseded_by_id": approved_v2.procedure_id,
            },
            {
                "version": 1,
                "supersedes_id": None,
                "superseded_by_id": replacement.procedure_id,
            },
        )
        for case in cases:
            with pytest.raises(ProcedureValidationError):
                _validate_procedure_links(
                    repository,
                    self_id=str(uuid4()),
                    project_id=first_project,
                    version=case["version"],
                    supersedes_id=case["supersedes_id"],
                    superseded_by_id=case["superseded_by_id"],
                )
