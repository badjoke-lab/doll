from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import cast

import pytest
from typer.testing import CliRunner

from doll import state, workspace
from doll.artifact import WorkspaceFileService
from doll.checkpoint import ProjectCheckpointService
from doll.cli import app
from doll.procedure import ProcedureService
from doll.project_state import DecisionService, ProjectService
from doll.project_status import ProjectStatusService, ProjectStatusValidationError
from doll.settings import PolicyService
from doll.state_repository import StateRepository
from doll.work_item import AcceptanceCriterion, WorkItemService

runner = CliRunner()


def _workspace(tmp_path: Path) -> workspace.InitializedWorkspace:
    initialized = workspace.initialize_workspace(tmp_path / "workspace")
    with state.initialize_state_repository(initialized.root):
        pass
    return initialized


def _fixture(repository: StateRepository) -> tuple[str, dict[str, str]]:
    policy = PolicyService(repository).create(
        key="project.local-only",
        rule="Project continuity remains local and model-independent.",
        enabled=True,
    )
    charter_decision = DecisionService(repository).create(
        decision="Keep project status derived",
        reason="A parallel mutable status file would create competing authority.",
        decision_status="accepted",
        decided_at="2026-06-25T00:10:00Z",
    )
    project = ProjectService(repository).create_v2(
        name="Derived status project",
        description="Synthetic deterministic project-status fixture.",
        objective="Produce a deterministic read-only project status view.",
        in_scope=("Derived status",),
        out_of_scope=("Resume Bundle",),
        success_criteria=("Status is byte-for-byte deterministic",),
        project_status="active",
        started_at="2026-06-25T00:00:00Z",
        decision_ids=(charter_decision.decision_id,),
        governing_policy_ids=(policy.record_id,),
    )
    scoped_decision = DecisionService(repository).create(
        decision="Use checkpoint phase when available",
        reason="Confirmed checkpoint context is explicit and inspectable.",
        decision_status="accepted",
        decided_at="2026-06-25T00:20:00Z",
        project_id=project.project_id,
        constraints=("Do not fabricate a phase when no checkpoint exists.",),
    )

    work = WorkItemService(repository)
    active = work.create(
        project_id=project.project_id,
        kind="task",
        title="Implement status service",
        description="Build deterministic derived status.",
        priority=10,
    )
    active = work.transition(
        active.work_item_id,
        expected_revision=active.revision,
        to_status="in_progress",
        occurred_at="2026-06-25T01:00:00Z",
    )
    ready = work.create(
        project_id=project.project_id,
        kind="task",
        title="Generate Resume Bundle",
        description="Next bounded Phase 4B implementation.",
        priority=20,
    )
    blocker = work.create(
        project_id=project.project_id,
        kind="investigation",
        title="Resolve bundle selection contract",
        description="Current blocker for bundle generation.",
        priority=5,
    )
    blocked = work.create(
        project_id=project.project_id,
        kind="task",
        title="Finalize bundle layout",
        description="Blocked until the selection contract is resolved.",
        priority=30,
    )
    blocked = work.transition(
        blocked.work_item_id,
        expected_revision=blocked.revision,
        to_status="blocked",
        blocked_by_ids=(blocker.work_item_id,),
    )
    milestone = work.create(
        project_id=project.project_id,
        kind="milestone",
        title="Checkpoint record complete",
        description="ProjectCheckpointRecord implementation milestone.",
        priority=40,
        acceptance_criteria=(
            AcceptanceCriterion(
                criterion_id="cross-platform-ci",
                description="Cross-platform CI remains green.",
                required_evidence_kind="record",
                blocking=True,
            ),
        ),
    )
    milestone = work.transition(
        milestone.work_item_id,
        expected_revision=milestone.revision,
        to_status="in_progress",
        occurred_at="2026-06-25T01:10:00Z",
    )
    milestone = work.transition(
        milestone.work_item_id,
        expected_revision=milestone.revision,
        to_status="completed",
        occurred_at="2026-06-25T02:00:00Z",
    )
    secret = work.create(
        project_id=project.project_id,
        kind="review",
        title="TOP SECRET STATUS TEXT",
        description="This secret record must be omitted from normal status.",
        sensitivity="secret",
    )

    procedure = ProcedureService(repository).create_approved(
        project_id=project.project_id,
        title="Inspect project status",
        purpose="Inspect current authoritative project records without mutation.",
        version=1,
        ordered_steps=("Open the repository read-only and derive status.",),
        validation_steps=("Compare canonical JSON output byte-for-byte.",),
        rollback_steps=("No rollback is required because status is read-only.",),
    )

    checkpoint_service = ProjectCheckpointService(repository)
    proposed = checkpoint_service.propose(
        project_id=project.project_id,
        as_of="2026-06-25T03:00:00Z",
        summary="Status implementation is active and Resume Bundle is next.",
        current_phase="Phase 4B",
        current_goal="Complete deterministic project status.",
        active_work_item_ids=(active.work_item_id,),
        next_work_item_ids=(ready.work_item_id,),
        blocked_work_item_ids=(blocked.work_item_id,),
        completed_milestone_ids=(milestone.work_item_id,),
        required_validation_ids=(blocker.work_item_id,),
        actor_type="model",
    )
    checkpoint = checkpoint_service.confirm(
        proposed.checkpoint_id,
        expected_revision=proposed.revision,
    )

    unrelated = ProjectService(repository).create_v2(
        name="Unrelated project",
        description="Must not contaminate derived status.",
        objective="Remain outside the selected project.",
        in_scope=("Other work",),
        out_of_scope=("Derived status project",),
        success_criteria=("No cross-project contamination",),
        project_status="active",
        started_at="2026-06-25T00:00:00Z",
    )
    unrelated_work = work.create(
        project_id=unrelated.project_id,
        kind="task",
        title="UNRELATED WORK ITEM",
        description="Must not appear in selected project status.",
    )

    return project.project_id, {
        "active": active.work_item_id,
        "ready": ready.work_item_id,
        "blocked": blocked.work_item_id,
        "blocker": blocker.work_item_id,
        "milestone": milestone.work_item_id,
        "secret": secret.work_item_id,
        "checkpoint": checkpoint.checkpoint_id,
        "decision": charter_decision.decision_id,
        "scoped_decision": scoped_decision.decision_id,
        "policy": policy.record_id,
        "procedure": procedure.procedure_id,
        "unrelated_work": unrelated_work.work_item_id,
    }


def _state_snapshot(repository: StateRepository) -> tuple[int, tuple[tuple[str, int], ...], int]:
    status = repository.status()
    rows = repository.connection.execute(
        "SELECT id, revision FROM records ORDER BY id"
    ).fetchall()
    revisions = tuple((cast(str, row[0]), cast(int, row[1])) for row in rows)
    audit_count = cast(
        int,
        repository.connection.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0],
    )
    return status.state_revision, revisions, audit_count


def test_project_status_is_deterministic_complete_and_project_scoped(
    tmp_path: Path,
) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project_id, ids = _fixture(repository)

    with state.open_state_repository(initialized.root, read_only=True) as repository:
        service = ProjectStatusService(repository)
        first = service.export_json(project_id)
        second = service.export_json(project_id)
        status = service.build(project_id)

    assert first == second
    payload = json.loads(first)
    assert payload["status_schema"] == "doll.project-status.v1"
    assert payload["objective"] == "Produce a deterministic read-only project status view."
    assert status.current_phase == "Phase 4B"
    assert status.current_goal == "Complete deterministic project status."
    assert tuple(item.work_item_id for item in status.active_work) == (ids["active"],)
    assert tuple(item.work_item_id for item in status.next_ready_work) == (ids["ready"],)
    assert tuple(item.work_item_id for item in status.blocked_work) == (ids["blocked"],)
    assert status.blocked_work[0].blocked_by_ids == (ids["blocker"],)
    assert tuple(
        item.work_item_id for item in status.pending_required_validation
    ) == (ids["milestone"],)
    assert status.latest_checkpoint is not None
    assert status.latest_checkpoint.checkpoint_id == ids["checkpoint"]
    assert status.latest_checkpoint.freshness == "current"
    assert {item.decision_id for item in status.governing_decisions} == {
        ids["decision"],
        ids["scoped_decision"],
    }
    assert tuple(item.policy_id for item in status.governing_policies) == (ids["policy"],)
    assert tuple(item.procedure_id for item in status.approved_procedures) == (
        ids["procedure"],
    )
    assert status.omitted_record_counts["work_items"] == 1
    assert "TOP SECRET STATUS TEXT" not in first
    assert "UNRELATED WORK ITEM" not in first
    assert ids["unrelated_work"] not in first


def test_project_status_read_only_generation_changes_no_state_or_artifact(
    tmp_path: Path,
) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project_id, _ = _fixture(repository)
        artifact = WorkspaceFileService(repository).create_bytes(
            managed_path="status/protected.txt",
            content=b"unchanged artifact bytes\n",
            title="Protected status fixture",
            artifact_type="text",
            format="txt",
            media_type="text/plain",
        )
        before = _state_snapshot(repository)
    artifact_path = initialized.root / "artifacts" / artifact.managed_path
    artifact_before = artifact_path.read_bytes()

    with state.open_state_repository(initialized.root, read_only=True) as repository:
        service = ProjectStatusService(repository)
        service.build(project_id)
        service.export_json(project_id)
        service.render_text(project_id)

    with state.open_state_repository(initialized.root, read_only=True) as repository:
        after = _state_snapshot(repository)

    assert after == before
    assert artifact_path.read_bytes() == artifact_before


def test_project_status_cli_json_and_text_are_read_only(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project_id, _ = _fixture(repository)
        before = _state_snapshot(repository)

    json_result = runner.invoke(
        app,
        [
            "project",
            "status",
            project_id,
            "--json",
            "--workspace",
            str(initialized.root),
        ],
    )
    text_result = runner.invoke(
        app,
        [
            "project",
            "status",
            project_id,
            "--workspace",
            str(initialized.root),
        ],
    )

    assert json_result.exit_code == 0
    assert json.loads(json_result.output)["project_id"] == project_id
    assert text_result.exit_code == 0
    assert "Current phase: Phase 4B" in text_result.output
    assert "Active work:" in text_result.output
    assert str(initialized.root) not in json_result.output
    assert str(initialized.root) not in text_result.output

    with state.open_state_repository(initialized.root, read_only=True) as repository:
        after = _state_snapshot(repository)
    assert after == before


def test_project_status_fresh_process_without_model_or_network(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project_id, _ = _fixture(repository)

    environment = dict(os.environ)
    environment["DOLL_DISABLE_MODEL_ADAPTERS"] = "1"
    environment["NO_PROXY"] = "*"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "doll",
            "project",
            "status",
            project_id,
            "--json",
            "--workspace",
            str(initialized.root),
        ],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert completed.returncode == 0
    assert json.loads(completed.stdout)["project_id"] == project_id
    assert completed.stderr == ""


def test_project_status_rejects_missing_archived_and_secret_projects(
    tmp_path: Path,
) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        service = ProjectStatusService(repository)
        with pytest.raises(ProjectStatusValidationError):
            service.build("not-a-uuid")

        archived = ProjectService(repository).create_v2(
            name="Archived project",
            description="Archived status fixture.",
            objective="Must not produce live status.",
            in_scope=("Archive",),
            out_of_scope=("Live status",),
            success_criteria=("Rejected",),
            project_status="completed",
            started_at="2026-06-25T00:00:00Z",
            ended_at="2026-06-25T01:00:00Z",
        )
        archived = ProjectService(repository).archive(
            archived.project_id,
            expected_revision=archived.revision,
        )
        with pytest.raises(ProjectStatusValidationError):
            service.build(archived.project_id)

        secret = ProjectService(repository).create_v2(
            name="Secret project",
            description="Secret project status fixture.",
            objective="Must not use normal output.",
            in_scope=("Secret",),
            out_of_scope=("Normal output",),
            success_criteria=("Rejected",),
            project_status="active",
            started_at="2026-06-25T00:00:00Z",
            sensitivity="secret",
        )
        with pytest.raises(ProjectStatusValidationError):
            service.build(secret.project_id)
