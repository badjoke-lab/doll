from __future__ import annotations

from pathlib import Path

from doll import state, workspace
from doll.project_experience import ProjectExperienceInfo, ProjectExperienceService
from doll.project_state import ProjectInfo, ProjectService
from doll.state_repository import StateRepository


def _workspace(tmp_path: Path) -> workspace.InitializedWorkspace:
    initialized = workspace.initialize_workspace(tmp_path / "workspace")
    with state.initialize_state_repository(initialized.root):
        pass
    return initialized


def _project(repository: StateRepository, name: str) -> ProjectInfo:
    return ProjectService(repository).create_v2(
        name=name,
        description="Synthetic project for ProjectExperienceRecord list coverage.",
        objective="Exercise project and lifecycle filters.",
        in_scope=("list coverage",),
        out_of_scope=("authority mutation",),
        success_criteria=("filters remain deterministic",),
        project_status="active",
        started_at="2026-08-15T00:00:00Z",
    )


def _experience(
    repository: StateRepository,
    project_id: str,
    summary: str,
) -> ProjectExperienceInfo:
    return ProjectExperienceService(repository).record(
        project_id=project_id,
        event_kind="observation",
        summary=summary,
        occurred_at="2026-08-15T00:01:00Z",
        assertion_state="user_recorded",
        actor_type="user",
    )


def test_imp_094_list_filters_project_and_archived_records(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        first_project = _project(repository, "First project")
        second_project = _project(repository, "Second project")
        first = _experience(repository, first_project.project_id, "First project experience.")
        _experience(repository, second_project.project_id, "Second project experience.")
        service = ProjectExperienceService(repository)

        assert service.list(project_id=first_project.project_id, limit=100) == (first,)

        repository.update_record(
            first.experience_id,
            expected_revision=first.revision,
            status="archived",
        )
        assert service.list(project_id=first_project.project_id) == ()
        archived = service.get(first.experience_id)
        assert archived.lifecycle_status == "archived"
        assert service.list(
            project_id=first_project.project_id,
            include_archived=True,
        ) == (archived,)
