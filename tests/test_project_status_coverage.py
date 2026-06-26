from __future__ import annotations

from pathlib import Path

import pytest

from doll import state, workspace
from doll.project_state import ProjectService
from doll.project_status import (
    ProjectStatusCorruptError,
    ProjectStatusService,
    ProjectStatusValidationError,
    _canonical_json,
    _render_work_section,
    _requires_validation,
)
from doll.state_repository import StateRepository
from doll.work_item import AcceptanceCriterion, WorkItemService


def _workspace(tmp_path: Path) -> workspace.InitializedWorkspace:
    initialized = workspace.initialize_workspace(tmp_path / "workspace")
    with state.initialize_state_repository(initialized.root):
        pass
    return initialized


def _project(repository: StateRepository) -> str:
    return ProjectService(repository).create_v2(
        name="Empty status project",
        description="Project-status defensive coverage fixture.",
        objective="Exercise empty and malformed derived status branches.",
        in_scope=("Derived status",),
        out_of_scope=("Resume Bundle",),
        success_criteria=("Defensive branches fail closed",),
        project_status="active",
        started_at="2026-06-25T00:00:00Z",
    ).project_id


def test_empty_project_status_text_uses_explicit_none_sections(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project_id = _project(repository)

    with state.open_state_repository(initialized.root, read_only=True) as repository:
        text = ProjectStatusService(repository).render_text(project_id)

    assert "Latest checkpoint: none" in text
    assert "Current phase: [no confirmed checkpoint]" in text
    assert "Current goal: [no confirmed checkpoint]" in text
    assert text.count("  none") >= 7


def test_validation_requirement_short_circuits_nonblocking_states(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project_id = _project(repository)
        service = WorkItemService(repository)
        proposed = service.propose(
            project_id=project_id,
            kind="task",
            title="Proposed validation fixture",
            description="Unaccepted work does not create pending validation.",
            acceptance_criteria=(
                AcceptanceCriterion("blocking", "Blocking criterion.", None, True),
            ),
        )
        passed = service.create(
            project_id=project_id,
            kind="task",
            title="Passed validation fixture",
            description="Passed work does not remain pending.",
            acceptance_criteria=(
                AcceptanceCriterion("blocking", "Blocking criterion.", None, True),
            ),
        )
        passed = service.set_verification(
            passed.work_item_id,
            expected_revision=passed.revision,
            verification_state="passed",
            evidence_ids=(),
        )
        nonblocking = service.create(
            project_id=project_id,
            kind="task",
            title="Nonblocking validation fixture",
            description="Nonblocking criteria do not create pending validation.",
            acceptance_criteria=(
                AcceptanceCriterion("advisory", "Advisory criterion.", None, False),
            ),
        )

    assert _requires_validation(proposed) is False
    assert _requires_validation(passed) is False
    assert _requires_validation(nonblocking) is False


def test_project_status_helpers_reject_non_json_and_render_empty_work() -> None:
    with pytest.raises(ProjectStatusValidationError):
        _canonical_json({"invalid": {1, 2}})
    assert _render_work_section("Work", ()) == ["Work:", "  none"]


def test_selected_project_malformed_work_item_fails_closed(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project_id = _project(repository)
        repository.create_record(
            record_type="work_item",
            metadata={"project_id": project_id},
        )

        with pytest.raises(ProjectStatusCorruptError):
            ProjectStatusService(repository).build(project_id)
