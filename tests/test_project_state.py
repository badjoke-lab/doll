from __future__ import annotations

import json
from pathlib import Path

import pytest

from doll import state, workspace
from doll.artifact import WorkspaceFileService
from doll.audit import AuditService
from doll.memory import ConfirmedMemoryService
from doll.project_state import (
    DecisionService,
    ForbiddenAuthorityMutationError,
    ProjectDecisionCorruptError,
    ProjectDecisionExportError,
    ProjectDecisionValidationError,
    ProjectService,
)


def initialized_workspace(tmp_path: Path) -> workspace.InitializedWorkspace:
    initialized = workspace.initialize_workspace(tmp_path / "workspace")
    with state.initialize_state_repository(initialized.root):
        pass
    return initialized


def test_project_and_decision_persist_restart_with_typed_links(
    tmp_path: Path,
) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        memory = ConfirmedMemoryService(repository).create(
            subject="方針",
            content="ローカル優先で進める。",
        )
        artifact = WorkspaceFileService(repository).create_text(
            managed_path="imp-008/plan.txt",
            text="synthetic plan",
            title="計画",
            operation_id="artifact-project-plan",
        )
        project_service = ProjectService(repository)
        decision_service = DecisionService(repository)
        project = project_service.create(
            name="doll継続基盤",
            description="個人AIの状態をローカルに保持する。",
            project_status="active",
            started_at="2026-06-14T00:00:00Z",
            memory_ids=(memory.record_id,),
            artifact_ids=(artifact.artifact_id,),
            operation_id="project-create",
        )
        decision = decision_service.create(
            decision="confirmed memoryを先に実装する",
            reason="モデル切替より先に継続性を証明するため。",
            decision_status="accepted",
            decided_at="2026-06-14T01:00:00Z",
            alternatives=("モデル接続を先に作る",),
            constraints=("クラウドへ依存しない",),
            review_after="2026-07-14T01:00:00Z",
            project_id=project.project_id,
            memory_ids=(memory.record_id,),
            artifact_ids=(artifact.artifact_id,),
            operation_id="decision-create",
        )
        project = project_service.update(
            project.project_id,
            expected_revision=1,
            name=project.name,
            description=project.description,
            project_status="active",
            started_at=project.started_at,
            decision_ids=(decision.decision_id,),
            memory_ids=project.memory_ids,
            artifact_ids=project.artifact_ids,
            operation_id="project-link-decision",
        )
        assert project.decision_ids == (decision.decision_id,)

    with state.open_state_repository(
        initialized.root,
        read_only=True,
    ) as repository:
        project_service = ProjectService(repository)
        decision_service = DecisionService(repository)
        before_revision = repository.status().state_revision
        before_audit = len(AuditService(repository).list(limit=20))
        restored_project = project_service.get(project.project_id)
        restored_decision = decision_service.get(decision.decision_id)
        project_export = project_service.export_json(project.project_id)
        decision_export = decision_service.export_json(decision.decision_id)

        assert restored_project.name == "doll継続基盤"
        assert restored_decision.project_id == restored_project.project_id
        assert json.loads(project_export)["record"]["project"]["decision_ids"] == [
            decision.decision_id
        ]
        assert json.loads(decision_export)["record"]["decision"]["project_id"] == (
            project.project_id
        )
        assert repository.status().state_revision == before_revision
        assert len(AuditService(repository).list(limit=20)) == before_audit


def test_revision_safe_updates_archive_and_lists(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project_service = ProjectService(repository)
        decision_service = DecisionService(repository)
        project = project_service.create(
            name="Project",
            description="Initial",
            project_status="planned",
            started_at="2026-06-14T00:00:00Z",
        )
        updated_project = project_service.update(
            project.project_id,
            expected_revision=1,
            name="Project",
            description="Updated",
            project_status="active",
            started_at="2026-06-14T00:00:00Z",
        )
        assert updated_project.revision == 2
        with pytest.raises(state.StaleRevisionError):
            project_service.update(
                project.project_id,
                expected_revision=1,
                name="stale",
                description="stale",
                project_status="active",
                started_at="2026-06-14T00:00:00Z",
            )

        decision = decision_service.create(
            decision="Choose A",
            reason="Reason A",
            decision_status="accepted",
            decided_at="2026-06-14T01:00:00Z",
        )
        updated_decision = decision_service.update(
            decision.decision_id,
            expected_revision=1,
            decision="Choose A",
            reason="Updated reason",
            decision_status="accepted",
            decided_at="2026-06-14T01:00:00Z",
        )
        assert updated_decision.revision == 2
        archived_project = project_service.archive(
            project.project_id,
            expected_revision=2,
        )
        archived_decision = decision_service.archive(
            decision.decision_id,
            expected_revision=2,
        )
        assert archived_project.lifecycle_status == "archived"
        assert archived_decision.lifecycle_status == "archived"
        assert project_service.list() == ()
        assert decision_service.list() == ()
        assert project_service.list(include_archived=True) == (archived_project,)
        assert decision_service.list(include_archived=True) == (archived_decision,)

        with pytest.raises(ProjectDecisionValidationError):
            project_service.archive(project.project_id, expected_revision=3)
        with pytest.raises(ProjectDecisionValidationError):
            decision_service.update(
                decision.decision_id,
                expected_revision=3,
                decision="blocked",
                reason="blocked",
                decision_status="accepted",
                decided_at="2026-06-14T01:00:00Z",
            )

        actions = {event.action for event in AuditService(repository).list(limit=20)}
        assert {
            "project.create",
            "project.update",
            "project.archive",
            "decision.create",
            "decision.update",
            "decision.archive",
        } <= actions


def test_validation_authority_dates_and_links(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project_service = ProjectService(repository)
        decision_service = DecisionService(repository)

        with pytest.raises(ForbiddenAuthorityMutationError):
            project_service.create(
                name="model project",
                description="blocked",
                project_status="planned",
                started_at="2026-06-14T00:00:00Z",
                actor_type="model",
            )
        with pytest.raises(ForbiddenAuthorityMutationError):
            decision_service.create(
                decision="model decision",
                reason="blocked",
                decision_status="accepted",
                decided_at="2026-06-14T00:00:00Z",
                actor_type="model",
            )
        with pytest.raises(ProjectDecisionValidationError):
            project_service.create(
                name="bad status",
                description="bad",
                project_status="unknown",  # type: ignore[arg-type]
                started_at="2026-06-14T00:00:00Z",
            )
        with pytest.raises(ProjectDecisionValidationError):
            project_service.create(
                name="bad dates",
                description="bad",
                project_status="active",
                started_at="2026-06-15T00:00:00Z",
                ended_at="2026-06-14T00:00:00Z",
            )
        with pytest.raises(ProjectDecisionValidationError):
            decision_service.create(
                decision="bad review",
                reason="bad",
                decision_status="accepted",
                decided_at="2026-06-15T00:00:00Z",
                review_after="2026-06-14T00:00:00Z",
            )
        with pytest.raises(ProjectDecisionValidationError):
            project_service.create(
                name="bad path",
                description="/private/local/path",
                project_status="planned",
                started_at="2026-06-14T00:00:00Z",
            )

        other = repository.create_record(record_type="other", metadata={})
        with pytest.raises(ProjectDecisionValidationError):
            decision_service.create(
                decision="wrong project",
                reason="wrong",
                decision_status="accepted",
                decided_at="2026-06-14T00:00:00Z",
                project_id=other.id,
            )
        with pytest.raises(ProjectDecisionValidationError):
            project_service.create(
                name="wrong memory",
                description="wrong",
                project_status="planned",
                started_at="2026-06-14T00:00:00Z",
                memory_ids=(other.id,),
            )
        with pytest.raises(ProjectDecisionValidationError):
            project_service.create(
                name="duplicate",
                description="duplicate",
                project_status="planned",
                started_at="2026-06-14T00:00:00Z",
                artifact_ids=(other.id, other.id),
            )

        decision = decision_service.create(
            decision="base decision",
            reason="base",
            decision_status="accepted",
            decided_at="2026-06-14T00:00:00Z",
        )
        with pytest.raises(ProjectDecisionValidationError):
            decision_service.update(
                decision.decision_id,
                expected_revision=1,
                decision=decision.decision,
                reason=decision.reason,
                decision_status="accepted",
                decided_at=decision.decided_at,
                supersedes_id=decision.decision_id,
            )


def test_secret_export_read_only_and_rollback(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project_service = ProjectService(repository)
        decision_service = DecisionService(repository)
        project = project_service.create(
            name="secret project",
            description="synthetic secret category",
            project_status="planned",
            started_at="2026-06-14T00:00:00Z",
            sensitivity="secret",
        )
        decision = decision_service.create(
            decision="secret decision",
            reason="synthetic secret category",
            decision_status="accepted",
            decided_at="2026-06-14T00:00:00Z",
            sensitivity="secret",
        )
        with pytest.raises(ProjectDecisionExportError):
            project_service.export_json(project.project_id)
        with pytest.raises(ProjectDecisionExportError):
            decision_service.export_json(decision.decision_id)

    with state.open_state_repository(
        initialized.root,
        read_only=True,
    ) as repository:
        with pytest.raises(state.ReadOnlyStateError):
            ProjectService(repository).create(
                name="blocked",
                description="blocked",
                project_status="planned",
                started_at="2026-06-14T00:00:00Z",
            )

    second = initialized_workspace(tmp_path / "second")
    with state.open_state_repository(second.root) as repository:
        repository.connection.execute("DROP TABLE audit_events")
        with pytest.raises(state.StateCorruptError):
            ProjectService(repository).create(
                name="rollback",
                description="rollback",
                project_status="planned",
                started_at="2026-06-14T00:00:00Z",
            )
        row = repository.connection.execute(
            "SELECT COUNT(*) FROM records WHERE record_type = 'project'"
        ).fetchone()
        assert row is not None
        assert row[0] == 0
        assert repository.status().state_revision == 0


def test_corrupt_records_and_wrong_type_are_rejected(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        bad_project = repository.create_record(
            record_type="project",
            title="wrong",
            provenance="user-created",
            metadata={
                "name": "name",
                "description": "description",
                "status": "planned",
                "started_at": "2026-06-14T00:00:00Z",
                "ended_at": None,
                "decision_ids": [],
                "memory_ids": [],
                "artifact_ids": [],
            },
        )
        bad_decision = repository.create_record(
            record_type="decision",
            title="decision",
            provenance="user-confirmed",
            metadata={
                "decision": "decision",
                "reason": "reason",
                "status": "accepted",
                "decided_at": "bad",
                "alternatives": [],
                "constraints": [],
                "review_after": None,
                "supersedes_id": None,
                "project_id": None,
                "memory_ids": [],
                "artifact_ids": [],
            },
        )
        with pytest.raises(ProjectDecisionCorruptError):
            ProjectService(repository).get(bad_project.id)
        with pytest.raises(ProjectDecisionCorruptError):
            DecisionService(repository).get(bad_decision.id)
        with pytest.raises(KeyError):
            ProjectService(repository).get(bad_decision.id)
        with pytest.raises(ProjectDecisionValidationError):
            ProjectService(repository).list(limit=0)
