from __future__ import annotations

from pathlib import Path

from doll import state, workspace
from doll.procedure import ProcedureService
from doll.project_state import ProjectService


def test_approved_procedure_preserves_required_content(tmp_path: Path) -> None:
    initialized = workspace.initialize_workspace(tmp_path / "workspace")
    with state.initialize_state_repository(initialized.root):
        pass

    with state.open_state_repository(initialized.root) as repository:
        project_id = (
            ProjectService(repository)
            .create_v2(
                name="Procedure content project",
                description="Approved procedure content test.",
                objective="Preserve inspectable accepted methods.",
                in_scope=("Procedure content",),
                out_of_scope=("Procedure execution",),
                success_criteria=("Required content survives restart",),
                project_status="active",
                started_at="2026-06-25T00:00:00Z",
            )
            .project_id
        )
        procedure = ProcedureService(repository).create_approved(
            project_id=project_id,
            title="Required content procedure",
            purpose="Preserve the accepted method fields.",
            version=1,
            ordered_steps=("Apply one bounded step.",),
            validation_steps=("Validate the bounded result.",),
            rollback_steps=("Restore the prior accepted state.",),
        )

    with state.open_state_repository(initialized.root, read_only=True) as repository:
        restored = ProcedureService(repository).get(procedure.procedure_id)

    assert restored.ordered_steps == ("Apply one bounded step.",)
    assert restored.validation_steps == ("Validate the bounded result.",)
    assert restored.rollback_steps == ("Restore the prior accepted state.",)
