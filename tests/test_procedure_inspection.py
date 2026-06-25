from __future__ import annotations

from pathlib import Path

from doll import state, workspace
from doll.procedure import ProcedureService
from doll.project_state import ProjectService


def test_superseded_procedure_remains_inspectable(tmp_path: Path) -> None:
    initialized = workspace.initialize_workspace(tmp_path / "workspace")
    with state.initialize_state_repository(initialized.root):
        pass

    with state.open_state_repository(initialized.root) as repository:
        project_id = (
            ProjectService(repository)
            .create_v2(
                name="Procedure inspection project",
                description="Superseded procedure inspection test.",
                objective="Preserve historical accepted methods.",
                in_scope=("Procedure supersession",),
                out_of_scope=("Procedure execution",),
                success_criteria=("Prior procedure remains inspectable",),
                project_status="active",
                started_at="2026-06-25T00:00:00Z",
            )
            .project_id
        )
        service = ProcedureService(repository)
        original = service.create_approved(
            project_id=project_id,
            title="Original method",
            purpose="Original accepted method.",
            version=1,
            ordered_steps=("Apply the original bounded step.",),
            validation_steps=("Validate the original result.",),
            rollback_steps=("Restore the previous state.",),
        )
        replacement = service.create_approved(
            project_id=project_id,
            title="Replacement method",
            purpose="Replacement accepted method.",
            version=2,
            ordered_steps=("Apply the replacement bounded step.",),
            validation_steps=("Validate the replacement result.",),
            rollback_steps=("Restore the previous state.",),
            supersedes_id=original.procedure_id,
        )
        superseded = service.supersede(
            original.procedure_id,
            replacement_id=replacement.procedure_id,
            expected_revision=original.revision,
        )
        inspected = service.get(original.procedure_id)

    assert inspected == superseded
    assert inspected.procedure_status == "superseded"
    assert inspected.superseded_by_id == replacement.procedure_id
