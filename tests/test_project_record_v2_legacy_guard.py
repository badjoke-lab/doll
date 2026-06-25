from __future__ import annotations

from pathlib import Path

import pytest

from doll import state, workspace
from doll.project_state import ProjectDecisionValidationError, ProjectService


def test_legacy_update_cannot_drop_project_v2_charter(tmp_path: Path) -> None:
    initialized = workspace.initialize_workspace(tmp_path / "workspace")
    with state.initialize_state_repository(initialized.root):
        pass

    with state.open_state_repository(initialized.root) as repository:
        service = ProjectService(repository)
        project = service.create_v2(
            name="Protected v2 project",
            description="The v2 charter must not be lost through a v1 update.",
            objective="Preserve the accepted charter fields.",
            in_scope=("ProjectRecord v2",),
            out_of_scope=("Legacy field loss",),
            success_criteria=("The v1 update path is rejected",),
            project_status="active",
            started_at="2026-06-26T00:00:00Z",
        )

        with pytest.raises(ProjectDecisionValidationError):
            service.update(
                project.project_id,
                expected_revision=project.revision,
                name=project.name,
                description="Attempted legacy rewrite.",
                project_status=project.project_status,
                started_at=project.started_at,
            )

        unchanged = service.get(project.project_id)

    assert unchanged.revision == project.revision
    assert unchanged.schema_version == 2
    assert unchanged.objective == project.objective
    assert unchanged.in_scope == project.in_scope
    assert unchanged.out_of_scope == project.out_of_scope
    assert unchanged.success_criteria == project.success_criteria
