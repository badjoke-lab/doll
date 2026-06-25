from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest

from doll import state, workspace
from doll.procedure import ProcedureService, ProcedureValidationError
from doll.project_state import ProjectService


def test_external_origin_stays_draft(tmp_path: Path) -> None:
    initialized = workspace.initialize_workspace(tmp_path / "workspace")
    with state.initialize_state_repository(initialized.root):
        pass

    with state.open_state_repository(initialized.root) as repository:
        project_id = ProjectService(repository).create_v2(
            name="Procedure origin project",
            description="Procedure origin boundary test.",
            objective="Preserve external methods without acceptance.",
            in_scope=("Procedure drafts",),
            out_of_scope=("Automatic acceptance",),
            success_criteria=("External method remains draft",),
            project_status="active",
            started_at="2026-06-25T00:00:00Z",
        ).project_id
        service = ProcedureService(repository)
        draft = service.create_draft(
            project_id=project_id,
            title="External method",
            purpose="Retain external method text as data.",
            version=1,
            ordered_steps=("Inspect the method without executing it.",),
            validation_steps=("Confirm that the record remains a draft.",),
            rollback_steps=("Discard the draft if it is not accepted.",),
            actor_type="importer",
        )
        row = repository.connection.execute(
            "SELECT actor_type FROM audit_events "
            "WHERE target_id = ? ORDER BY sequence DESC LIMIT 1",
            (draft.procedure_id,),
        ).fetchone()
        assert row is not None
        audit_actor = cast(str, row["actor_type"])

        with pytest.raises(ProcedureValidationError):
            service.approve(
                draft.procedure_id,
                expected_revision=draft.revision,
                actor_type="importer",
            )

    assert draft.procedure_status == "draft"
    assert draft.provenance == "imported"
    assert audit_actor == "system"
